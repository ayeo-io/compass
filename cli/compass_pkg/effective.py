# compass_pkg.effective - the reading interface to an issue's configuration
"""One place that answers "what configuration does this issue run against?"

`effective_for(task_dir)` returns an `EffectiveView`:

- an issue whose manifest names `generation: n` (n at least 1) gets generation
  n, read from its folder, and nothing else (ADR-036);
- an issue whose manifest has no `generation:` key predates 6.0.0 and gets the
  live configuration, as 5.6.0 read it (ADR-006);
- `generation: 0` is refused, naming the command that commits the first one;
- no issue (`task_dir=None`) gets the live configuration of the project.

"Live" means the fixed check set (`check_set`), with the tighten-only
settings of the project's `compass.yml` applied (`tighten`), resolved now
(ADR-094). Nothing merges: a catalogue key in `compass.yml` is a removed
setting and is not read, and an `extends:` that names a git parent is refused.
An issue's own `config:` is not read: 9.0.0 has no issue layer. An 8.x issue
keeps the layer its stored generation was committed with.
A project with no `compass.yml` and its own copies of the two governance files
has those files read through the legacy adapter in place of the check set, so
what an issue is stored against is what ran before (until #359).

Each generation commit also writes the manifest's `policy:` block: the check
set's id, version and sha256, the sha256 of `compass.yml`, the tightenings and
the digest of the stored `resolved.yml` (`policy_block`).

This module also builds the `generation.Resolution` a commit stores, and is
the one place the existing modules reach the store through
(`commit_generation`, `record_check_results`, `generation_report`).
"""
# DEPENDENCY: standard library (dataclasses, datetime, hashlib, os, re, subprocess);
# compass_pkg.atomic_io, catalogue_check, check_registry, check_set, core, generation,
# layers (the 8.x issue layer of `pending_config` only), legacy_adapter, merge (the
# legacy copy only), obligations, project_settings, removed_parts, tighten, word_map.
from __future__ import annotations

import datetime
import hashlib
import os
import re
import subprocess
from dataclasses import dataclass, field

from compass_pkg import (catalogue_check, check_set, generation, layers, legacy_adapter, merge,
                         project_settings, removed_parts, tighten, word_map)
from compass_pkg import obligations, status_words
from compass_pkg import catalogue_spec as spec
from compass_pkg.atomic_io import digest
from compass_pkg.check_registry import REGISTRY
from compass_pkg.core import (AUTONOMY_VALUES, COMPASS_VERSION, FRAMEWORK_ROOT,
                              GOVERNANCE_FILES, CompassError, load_manifest,
                              load_yaml, reading_matches)
from compass_pkg.manifest_store import load_manifest_mapping
from compass_pkg.core import manifest_path

OUTCOME_KEYS = ("delivery_approach", "stages", "gates", "checkpoints",
                "policy_rules_fired", "subtask_ceiling", "artifacts", "models",
                "evidence_required")


@dataclass(frozen=True)
class EffectiveView:
    """The configuration an issue runs against. `source` is `generation` or
    `live`. `resolved` is the whole `resolved.yml` mapping; `config` is its
    catalogues alone."""
    source: str
    issue: object
    generation: object
    resolved: dict = field(default_factory=dict)
    versions: dict = field(default_factory=dict)
    # `provenance.yml`: the layer and operation behind each field, the waivers
    # and the classification of each layer.
    provenance: dict = field(default_factory=dict)

    @property
    def config(self):
        return {k: v for k, v in self.resolved.items() if k in spec.CATALOGUES}

    @property
    def capabilities(self):
        return dict(self.resolved.get("capabilities") or {})

    @property
    def autonomy(self):
        return self.resolved.get("autonomy")

    def evaluator_policy(self):
        """The routing policy in the shape `evaluate_route` takes, built from
        the resolved configuration. `effective` is, with `classify`, one of the
        two modules that may import `obligations` (ADR-037); readers call this."""
        policy = obligations.policy_adapter(self.config)
        # The tighten-only settings the evidence evaluator reads: the labels that
        # owe what a `G5` label owes, and the evidence a project adds (ADR-094).
        # A configuration that holds neither adds nothing.
        policy = tighten.with_settings(policy, self.resolved)
        # The kinds every approach carries, with the stage whose depth each takes. The
        # classifier prepares its policy from `policy_adapter` and does not see this key,
        # so a stored generation owes nothing new (I-7).
        every = {kind: body.get("stage") for kind, body in (self.config.get("artifacts") or {}).items()
                 if isinstance(body, dict) and body.get("every_approach")}
        if every:
            policy["every_approach"] = every
        return policy

    def evaluator_issue(self):
        """The issue's own layer in the shape `evaluate_route` takes as `issue`:
        the approach it names, the stage modes it sets and the subtask ceiling
        it sets (`obligations.issue_input`), or None when it sets none of them.
        The layer is rebuilt from `resolved`, so a stored generation gives what
        the commit stored and a live view what the manifest's `config:` gives
        now.

        The stages the issue waives come from the waivers the provenance
        records, so their modes hold on an approach a floor raised. A stale
        waiver's entry is left out of the resolution, so its stage holds no
        issue mode and is not passed as waived."""
        layer = {key: self.resolved[key] for key in ("approach", "ceilings")
                 if self.resolved.get(key)}
        waived = []
        for record in ((self.provenance or {}).get("waivers") or {}).values():
            if not isinstance(record, dict) or record.get("scope") != "issue":
                continue
            entry = record.get("entry")
            if isinstance(entry, str) and entry.startswith("stages."):
                waived.append(entry[len("stages."):])
        return obligations.issue_input(self.config, layer, waived) or None

    # --- the accessors the reader modules call --------------------------------------
    # Each returns the data in the shape the reader already consumed from the
    # governance file, so a reader changes its source and not its logic.

    @property
    def orders(self):
        """The ordered dimensions, for a `when:` that uses `at_least`."""
        return obligations.dimension_orders(self.resolved.get("dimensions") or {})

    def matches(self, when, assessment):
        """Whether a `when:` clause of this configuration holds for an assessment."""
        return reading_matches(when, assessment, self.orders)

    def listing_assessment(self, assessment, approach_name):
        """What a check's `when` reads for an issue: its assessment and the
        derived key `ships`, whether the approach it was routed to ships."""
        approaches = self.resolved.get("approaches") or {}
        return obligations.listing_assessment(assessment, approaches.get(approach_name))

    def guardrail_gates(self):
        """The guardrails in the legacy shape: `defaults` (gates that apply to
        an approach that ships) and `spike_guardrails` (those that do not), each
        entry with `id`, `name`, `statement`, `checks` and `applies_when`;
        `project` is always empty, because a project's own guardrails are
        gates of the same catalogue. `checks` maps a check id to the
        `severity`, `on_skipped` and `blocking_when` it declares, and `impl`
        maps it to the implementation it runs."""
        out = {"defaults": [], "project": [], "spike_guardrails": [], "checks": {},
               "impl": {}}
        for gate_id, gate in (self.resolved.get("gates") or {}).items():
            if not isinstance(gate, dict) or gate.get("kind") != "guardrail":
                continue
            entry = {"id": gate_id, "name": gate.get("name", ""),
                     "statement": gate.get("statement", ""),
                     "checks": list(gate.get("checks") or [])}
            if "when" in gate:
                entry["applies_when"] = gate["when"]
            ships = (gate.get("applies_to") or {}).get("ships", True)
            out["spike_guardrails" if ships is False else "defaults"].append(entry)
        for check_id, check in (self.resolved.get("checks") or {}).items():
            if not isinstance(check, dict):
                continue
            declared = {key: check[key] for key in ("severity", "on_skipped", "blocking_when")
                        if key in check}
            if declared:
                out["checks"][check_id] = declared
            out["impl"][check_id] = check.get("impl", check_id)
        return out

    def gate_requirements(self):
        """`(gate -> accepted evidence types, known evidence types)`. A gate that
        lists no types accepts any, and is absent from the first."""
        gates = self.resolved.get("gates") or {}
        requirements = {gate_id: list(gate["accepts"]) for gate_id, gate in gates.items()
                        if isinstance(gate, dict) and isinstance(gate.get("accepts"), list)}
        return requirements, set(self.resolved.get("evidence_types") or {})

    def command_checks(self):
        """The checks that run a command the project wrote: those whose
        implementation is `command-passes` and which carry parameters. Each is
        returned as `{id, name, checks, params}`, named for the guardrail that
        lists it, else for itself."""
        listed = {}
        for gate_id, gate in (self.resolved.get("gates") or {}).items():
            if isinstance(gate, dict) and gate.get("kind") == "guardrail":
                for check_id in gate.get("checks") or []:
                    listed.setdefault(check_id, (gate_id, gate.get("name") or gate_id))
        out = []
        for check_id, check in (self.resolved.get("checks") or {}).items():
            if (isinstance(check, dict) and check.get("impl") == "command-passes"
                    and check.get("params")):
                gate_id, name = listed.get(check_id, (check_id, check_id))
                out.append({"id": gate_id, "name": name, "checks": ["command-passes"],
                            "params": dict(check["params"])})
        return out

    def stage_order(self):
        """The stage names in the order they run, as a tuple."""
        stages = self.resolved.get("stages") or {}
        return tuple(name for name, _ in sorted(
            stages.items(), key=lambda item: item[1].get("order", 0)))

    def loop_ceiling_rules(self):
        """The loop-ceiling rules in the shape the evaluator reads."""
        return list(self.evaluator_policy()["routing_guardrails"]["loop_ceilings"])

    def from_governance_copy(self):
        """True when the configuration was resolved over the project's own copies
        of the two governance files, which can omit what the framework ships."""
        parents = self.versions.get("parents") or []
        return bool(parents) and parents[0].get("source") == "legacy"

    def known_ids(self):
        """The ids of the guardrails that apply to an approach that ships."""
        return {gate_id for gate_id, gate in (self.resolved.get("gates") or {}).items()
                if isinstance(gate, dict) and gate.get("kind") == "guardrail"
                and (gate.get("applies_to") or {}).get("ships", True) is not False}

    def parent_version(self):
        """The version of the parent the configuration was resolved over."""
        parents = self.versions.get("parents") or []
        return (parents[0].get("version") or None) if parents else None

    def pending_config(self, manifest):
        """True when the manifest's `config:` is not the overlay this
        generation was committed with. 9.0.0 does not read `config:`
        (ADR-094), so such a `config:` changes nothing, now or at a commit."""
        try:
            layer = layers.load_issue_layer(manifest)
        except CompassError:
            return True
        return (layer.digest if layer else None) != self.versions.get("issue_overlay_digest")


# --- live resolution ----------------------------------------------------------------

def _holds_copy(root):
    """True when the project keeps its own copies of the two governance files.
    The framework's own repository does not: its files are frozen copies of
    the 8.x default. Nothing is parsed."""
    folder = os.path.join(root, "governance")
    if os.path.realpath(folder) == os.path.realpath(os.path.join(FRAMEWORK_ROOT, "governance")):
        return False
    return all(os.path.isfile(os.path.join(folder, name)) for name in GOVERNANCE_FILES)


def _legacy_parent(root):
    """`(doc, meta)` for a project that keeps its own copies of the two
    governance files (`_holds_copy`), or None. `doc` is the copy in catalogue
    form (`legacy_adapter.adapt`), with the check set's capabilities."""
    if not _holds_copy(root):
        return None
    folder = os.path.join(root, "governance")
    policy = load_yaml(os.path.join(folder, "routing-policy.yml"))
    guardrails = load_yaml(os.path.join(folder, "guardrails.yml"))
    doc = legacy_adapter.adapt(policy, guardrails)
    doc["capabilities"] = dict(check_set.load()["capabilities"])
    return doc, {"id": "legacy", "version": str(policy.get("version", "")),
                 "source": "legacy", "guardrails": guardrails}


def _legacy_config(doc):
    """`(config, provenance)` of an adapted copy. The copy is the whole
    configuration: it is read as one layer through the 8.x merge, which maps
    a gate at a legacy stage to the path stage that shows it (L-STAGE-MAPPED).
    #359 deletes this with the adapter."""
    mapped, _ = word_map.map_layer(doc)
    for key in mapped:
        if key in spec.SETTINGS_KEYS:
            raise CompassError(f"legacy: {key} is a settings key and belongs in the "
                               f"project's own compass.yml, never in a parent (ADR-043)")
    layers.refuse_non_text_keys(mapped, "legacy")
    errors = catalogue_check.check_layer(mapped, "parent", name="legacy")
    if errors:
        raise CompassError("legacy: " + "; ".join(errors))
    return merge.apply({}, mapped, "parent", "legacy")


def _legacy_digest(doc):
    """The digest of an adapted copy's catalogue keys, as 8.x stored it."""
    return digest({k: v for k, v in doc.items() if k in spec.LAYER_KEYS})


def legacy_resolved(root):
    """The resolved mapping of the project's own copy of the governance files,
    whatever its `compass.yml` says. The compatibility contracts read it."""
    legacy = _legacy_parent(os.path.abspath(root))
    if legacy is None:
        raise CompassError(f"{root} holds no copy of the governance files")
    doc, meta = legacy
    config, _ = _legacy_config(doc)
    return _resolved(config, dict(doc.get("capabilities") or {}), "balanced",
                     legacy_adapter.adapt_evidence_types(meta["guardrails"])["evidence_types"])


GOVERNANCE_COPY_NOTICE = (
    "  This unmigrated 5.x project has no compass.yml and runs on its own copy of "
    "governance/. The rows below are the check set, not what compass approach "
    "evaluate reads. Run compass policy migrate on 8.x to convert the copy; the "
    "upgrade guide names the 9.0.0 settings.")


def has_governance_copy(root):
    """True when the project keeps its own copy of the two governance files
    and has no `compass.yml` Compass reads, so `resolve_live` runs on the copy."""
    return not project_settings.compass_yml_counts(root) and _holds_copy(root)


def _autonomy(root):
    """The project's `autonomy`, else `balanced`. An issue sets none (ADR-094)."""
    value = project_settings.settings(root).get("autonomy")
    value = "balanced" if value is None else str(value).strip().lower()
    if value not in AUTONOMY_VALUES:
        raise CompassError(f"autonomy '{value}' is not one of {', '.join(AUTONOMY_VALUES)}")
    return value


def _git_blob(path):
    """The git object name of a file, or None outside a repository."""
    try:
        out = subprocess.run(["git", "hash-object", path], capture_output=True, text=True,
                             timeout=10, cwd=os.path.dirname(path))
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def git_parent_of(doc):
    """The `extends:` text of a `compass.yml` mapping when it names a git
    parent, else None."""
    extends = (doc or {}).get("extends") if isinstance(doc, dict) else None
    ref = extends.get("from") if isinstance(extends, dict) else extends
    return ref if isinstance(ref, str) and ref.startswith(removed_parts.GIT_PARENT_SCHEME) \
        else None


def refuse_git_parent(doc, where=layers.PROJECT_FILE):
    """Raise `CompassError` when `doc` extends a git parent (L-PARENT-REMOVED)."""
    ref = git_parent_of(doc)
    if ref:
        raise CompassError(
            f"nothing can be resolved: {where} extends the git parent {ref}, and git "
            f"parents were removed in {removed_parts.RELEASE} (ADR-094, L-PARENT-REMOVED). "
            f"{removed_parts.GIT_PARENT_FIX}.")


def project_doc(root):
    """The parsed `compass.yml` of the project at `root` when Compass reads it,
    else None. Raises `CompassError` when it cannot be read or is not a
    mapping."""
    if not project_settings.compass_yml_counts(root):
        return None
    doc = project_settings.settings(root)
    if not isinstance(doc, dict):
        raise CompassError(f"{os.path.join(root, layers.PROJECT_FILE)}: expected a mapping")
    return doc


def _resolved(config, capabilities, autonomy, evidence_types):
    """The mapping a generation's `resolved.yml` holds, from resolved catalogues."""
    return {
        "capabilities": capabilities,
        # An 8.x issue layer could pick an approach and set ceilings, and its
        # stored generation keeps them. With no issue layer the key is always
        # empty; it stays so that a generation committed without a layer keeps
        # the same resolved document, and a reassess commits no new one for it.
        "approach": None,
        "autonomy": autonomy,
        # No lock exists to unlock (ADR-094); the key keeps the stored shape.
        "conformance": {"status": "conformant", "unlocked": []},
        **{name: config[name] for name in spec.CATALOGUES if name in config},
        "evidence_types": evidence_types,
    }


def _implementations(checks):
    return {check["impl"]: REGISTRY[check["impl"]].version
            for check in (checks or {}).values()
            if isinstance(check, dict) and check.get("impl") in REGISTRY}


def _refuse_lint_errors(doc, base):
    """Raise `CompassError` when the settings lint finds an error in
    `compass.yml`. Nothing is resolved from such a file, so no command reads,
    and no generation stores, a configuration the lint refuses; 8.x refused a
    project layer that did not pass its check the same way."""
    from compass_pkg import settings_lint
    errors = [f for f in settings_lint.lint(doc, base) if f.level == "error"]
    if errors:
        first = errors[0]
        raise CompassError(
            f"nothing can be resolved: {layers.PROJECT_FILE} does not pass the lint. First "
            f"error: {first.code} {first.path}: {first.message} ({len(errors)} "
            f"error(s) in all; run `compass policy lint` to see them)")


def _gates_before_write(resolved):
    """The check `generation.commit` runs before it writes a generation read
    from a project's own copy of the governance files: every check a gate
    names is one the copy declares. A project guardrail can name a check no
    implementation runs, such as the `coverage-floor` example of 5.x; no
    generation may store it, because `compass check` would read that gate from
    the generation from then on. 8.x ran the layer lint here, which refused
    it. A check the copy declares under a name 9.0.0 removed is accepted, as
    8.x accepted it: `compass check` reports it as nothing to check."""
    checks = resolved.get("checks") or {}
    unknown = [f"gates.{gate_id}.checks: '{check}'"
               for gate_id, gate in (resolved.get("gates") or {}).items()
               if isinstance(gate, dict)
               for check in gate.get("checks") or () if check not in checks]
    if unknown:
        raise CompassError(
            "nothing was written: the governance copy names a check it does not "
            "declare, which no implementation runs: " + "; ".join(unknown))


def resolve_live(root, manifest=None, slug=None, task_dir=None, validate=False, fetch=False):
    """The `generation.Resolution` of the project now: the check set with the
    tighten-only settings of `compass.yml` applied, or, for a project with no
    `compass.yml` and its own copy of the governance files, that copy. An
    issue's `config:` is not read (ADR-094); `manifest` and `task_dir` are
    accepted for the callers and not read. A file that cannot be read, a
    `compass.yml` the settings lint refuses and a git parent in `extends:`
    raise `CompassError` at once. A governance copy is checked only before a
    generation is written (the result's `validate`, `_gates_before_write`),
    so a read of it still reports each check it cannot run.
    `validate` and `fetch` are accepted and not read: the lint always runs,
    and nothing is fetched."""
    root = os.path.abspath(root)
    doc = project_doc(root)
    refuse_git_parent(doc)
    autonomy = _autonomy(root)
    legacy = None if doc is not None else _legacy_parent(root)
    if legacy:
        legacy_doc, meta = legacy
        config, prov = _legacy_config(legacy_doc)
        resolved = _resolved(
            config, dict(legacy_doc.get("capabilities") or {}), autonomy,
            legacy_adapter.adapt_evidence_types(meta["guardrails"])["evidence_types"])
        history = {path: {"steps": [{"layer": step["layer"], "op": step["operation"]}]}
                   for path, step in prov.items()}
        parent = {"ref": "legacy", "version": meta["version"],
                  "digest": _legacy_digest(legacy_doc), "source": "legacy"}
        tightened = {}
    else:
        # Read, not changed: `resolved` and `tighten.apply` copy what they return.
        loaded = check_set.shared()
        base = check_set.resolved(loaded, autonomy=autonomy)
        if doc is not None:
            _refuse_lint_errors(doc, base)
        tightened = tighten.settings_of(doc)
        # `base` is already a copy, so with nothing to apply it is the result:
        # one copy per resolution, which `compass flow` does for every issue.
        resolved = tighten.apply(base, tightened, loaded) if tightened else base
        history = {}
        parent = {"ref": f"compass:checks@{loaded['version'].split('.')[0]}",
                  "version": loaded["version"], "digest": digest(loaded),
                  "sha256": check_set.sha256(), "source": "shipped"}
    project_path = os.path.join(root, layers.PROJECT_FILE)
    versions = {
        "resolver": generation.RESOLVER_VERSION,
        "cli": COMPASS_VERSION,
        "parents": [parent],
        "project": ({"path": layers.PROJECT_FILE, "digest": digest(tightened),
                     "git_blob": _git_blob(project_path)} if doc is not None else None),
        "issue_overlay_digest": None,
        "implementations": _implementations(resolved.get("checks")),
    }
    return generation.Resolution(
        resolved=resolved,
        provenance={"fields": history, "waivers": {}, "classification": {}},
        versions=versions,
        records=[],
        validate=(lambda: _gates_before_write(resolved)) if legacy else None,
        details={"tightened": tightened, "legacy": bool(legacy)})


def file_sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def policy_block(root, resolution, resolved_digest):
    """The manifest's `policy:` block for a generation committed from
    `resolution` (ADR-094): the check set and its sha256, the sha256 of
    `compass.yml` (None without one), the tighten-only settings applied as
    written, and the digest of the generation's `resolved.yml`. A project that
    runs its own copy of the governance files names `legacy` and no check set
    digest."""
    details = resolution.details or {}
    legacy = details.get("legacy")
    settings_path = os.path.join(root, layers.PROJECT_FILE)
    return {
        "check_set": "legacy" if legacy else check_set.ref(),
        "check_set_sha256": None if legacy else check_set.sha256(),
        "settings_sha256": (file_sha256(settings_path)
                            if project_settings.compass_yml_counts(root) else None),
        "tightened": dict(details.get("tightened") or {}),
        "resolved": resolved_digest,
    }


def _live_view(task_dir, manifest, slug, start=None):
    start = task_dir or start or os.getcwd()
    root = project_settings.find_project_root(start)
    try:
        resolution = resolve_live(root, manifest, slug, task_dir)
    except merge.MergeError as exc:
        # A command that only reads the configuration gives the way to see the rest.
        # Only a project's own copy of the governance files merges.
        raise CompassError(f"{exc}. Run `compass policy lint` to see the cause.")
    return EffectiveView("live", slug, None, resolution.resolved, resolution.versions,
                         resolution.provenance)


def effective_for(task_dir=None, manifest=None):
    """The `EffectiveView` an issue runs against, or the project's live view
    for `task_dir=None`. See the module text for the three cases. `manifest`
    is the issue's manifest when the caller already holds it; otherwise it is
    read from the file."""
    if task_dir is None:
        return _live_view(None, None, None)
    task_dir = os.fspath(task_dir)
    if manifest is None:
        manifest, _ = load_manifest(task_dir)
    slug = os.path.basename(os.path.normpath(task_dir))
    held = generation.number(manifest)
    if held is None:
        return _live_view(task_dir, manifest, slug)
    if held == 0:
        raise CompassError(
            f"issue {slug} is at generation 0: it was assessed but has no stored "
            f"configuration yet; run `{generation.FIX_ZERO} --issue {slug}`")
    stored = generation.load(task_dir, held, any_major=status_words.is_closed(manifest))
    return EffectiveView("generation", slug, held, stored["resolved"], stored["versions"],
                         stored["provenance"])


def _layered(root):
    """Whether a project reads the check set: every project but one with its
    own copy of the governance files and no `compass.yml` Compass reads
    (ADR-094). The framework's own repository reads the check set too."""
    return not has_governance_copy(root)


def view_or_legacy(task_dir=None, live=False, start=None, manifest=None):
    """The view a reader module reads, or None when it must read the governance
    files as 5.6.0 did. That is the case only for an issue with no
    `generation:` key (or no issue) in a project that keeps its own copy of
    the governance files and has no `compass.yml`. Otherwise it is
    `effective_for`: the stored generation, a live view of the check set, or a
    refusal for generation 0 or a generation that is not whole. With `live`, a stored generation is not
    read: the command is about to commit the configuration as it is now. With
    no issue, `start` is the directory whose project is meant (else the
    working directory). `manifest` is the issue's manifest when the caller
    already holds it, so a render over every issue does not parse each one
    again; otherwise it is read from the file."""
    if task_dir is not None:
        task_dir = os.fspath(task_dir)
        if manifest is None:
            manifest, _ = load_manifest(task_dir)
        if generation.number(manifest) is not None and not live:
            return effective_for(task_dir, manifest)
    if not _layered(project_settings.find_project_root(task_dir or start or os.getcwd())):
        return None
    if live and task_dir is not None:
        return _live_view(task_dir, manifest, os.path.basename(os.path.normpath(task_dir)))
    if task_dir is None:
        return _live_view(None, None, None, start)
    return effective_for(task_dir, manifest)


def commit_generation(task_dir, manifest, invalidated=None, render=None, *, stamp=None,
                      resolution=None):
    """Store the configuration the issue resolves to now as its next
    generation and replace its manifest, as `approach evaluate --write` does.
    `manifest` is the mapping to write, with the computed outcome folded in.
    The chain is resolved first, and linted only when a write follows, so a
    configuration that does not resolve or lint leaves every file as it was.

    `resolution` is a resolution already made (`reassess_resolution` makes it
    before anything prints); otherwise it is made here. `stamp` is that of
    `generation.commit`; after it, the manifest's `policy:` block is written
    for the generation in force (`policy_block`), whether or not a new one was
    committed."""
    task_dir = os.path.abspath(os.fspath(task_dir))
    slug = os.path.basename(task_dir)
    root = project_settings.find_project_root(task_dir)
    if resolution is None:
        resolution = resolve_live(root, manifest, slug, task_dir)
    caller_stamp = stamp

    def stamp_policy(mapping, old, new):
        if caller_stamp is not None:
            caller_stamp(mapping, old, new)
        marker = generation.marker_digests(task_dir, new) if new else None
        if marker and marker.get("resolved.yml"):
            mapping["policy"] = policy_block(root, resolution, marker["resolved.yml"])
    wrapped = None
    if render is not None:
        # `render(text, gate_requirements)` sees the types the generation being
        # stored accepts, not whatever the live files now say.
        requirements = {gate_id: list(gate["accepts"])
                        for gate_id, gate in (resolution.resolved.get("gates") or {}).items()
                        if isinstance(gate, dict) and isinstance(gate.get("accepts"), list)}
        wrapped = lambda text: render(text, requirements)  # noqa: E731
    return generation.commit(task_dir, resolution, manifest, invalidated, wrapped,
                             stamp=stamp_policy)


def reassess_resolution(task_dir, manifest):
    """The `generation.Resolution` that `approach evaluate --write` commits for
    the issue in `task_dir`, made before anything prints. What the commit would
    refuse later for a reason already known (a closed issue, a configuration
    the lint refuses) is refused here, so a refusal never follows a printed
    result (`generation.preflight`)."""
    task_dir = os.fspath(task_dir)
    resolution = resolve_live(project_settings.find_project_root(task_dir), manifest,
                              os.path.basename(os.path.normpath(task_dir)), task_dir)
    generation.preflight(task_dir, resolution, manifest)
    return resolution


# --- the stored copy ------------------------------------------------------------------

generation_number = generation.number
FIX_ZERO = generation.FIX_ZERO
evaluate_command = generation.evaluate_command
# A generation built by another resolver or schema major (ADR-038): only this module
# imports `generation`, so the readers and the entry point take these from here.
FIX_MAJOR = generation.FIX_MAJOR
MajorRefusal = generation.MajorRefusal
refuse_other_major = generation.refuse_other_major
version_major = generation._major
# `record restore` names a generation's stored files to refuse a redacted copy.
GENERATION_DIRECTORY = generation.DIRECTORY
GENERATION_FILES = generation.FILES


def stored_documents(task_dir, manifest):
    """The four documents of the generation the manifest names, or None when
    it names none yet. A generation that is not whole raises `CompassError`."""
    held = generation.number(manifest)
    return generation.load(os.fspath(task_dir), held,
                           any_major=status_words.is_closed(manifest)) if held else None


def require_whole(task_dir):
    """Refuse an issue whose manifest names a generation that is not whole
    (a missing folder or marker, or a file that does not match its digest).
    An issue with no generation, or at generation 0, is not refused: it has
    nothing stored to be broken."""
    manifest, _ = load_manifest(task_dir)
    held = generation.number(manifest)
    if held:
        generation.load(os.fspath(task_dir), held, any_major=status_words.is_closed(manifest))


def _verdict_rank(verdict):
    return ("pass", "nothing-to-check", "advisory", "fail").index(verdict)


def record_check_results(task_dir, verdicts, manifest=None):
    """Rewrite `results.yml` of the generation the issue runs against with the
    verdict of each check in `verdicts` (`{check id: pass | fail | advisory |
    nothing-to-check}`): when it ran, which implementation and version ran
    it, and a digest of the check's definition as the generation stores it.
    An issue with no generation gets no file. Returns the number of checks
    written, or None. `compass check` passes the manifest it already loaded,
    so the verdicts are filed against the generation that run checked."""
    task_dir = os.fspath(task_dir)
    if manifest is None:
        manifest, _ = load_manifest(task_dir)
    held = generation.number(manifest)
    if not held:
        return None
    checks = generation.load(task_dir, held)["resolved"].get("checks") or {}
    at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    runs = {}
    for name, verdict in sorted(verdicts.items()):
        body = checks.get(name) if isinstance(checks.get(name), dict) else None
        impl = (body or {}).get("impl") or name
        entry = REGISTRY.get(impl)
        runs[name] = {
            "verdict": verdict, "at": at,
            "impl": {"id": entry.name, "version": entry.version} if entry else None,
            "definition_digest": digest(body) if body is not None else None,
            "inputs": {}, "status": "valid"}
    generation.write_results(task_dir, held, runs)
    return len(runs)


def generation_report(task_dir):
    """`(lines, broken)` for `compass ci`: one line for each generation folder
    that is current or a leftover, and for generation 0 the command that
    commits the first. Nothing for an issue with no `generation:` key. A
    generation the manifest names that is not whole is `broken`, which fails
    the run; a leftover does not, because nothing depends on it."""
    task_dir = os.fspath(task_dir)
    try:
        manifest, _ = load_manifest(task_dir)
        held = generation.number(manifest)
    except CompassError as exc:
        return [f"  generation: {exc}"], True
    if held is None:
        return [], False
    if held == 0:
        return [f"  generation 0: no stored configuration yet; run "
                f"{generation.FIX_ZERO} --issue {os.path.basename(task_dir)}"], False
    lines, broken = [], False
    for found in generation.states(task_dir, manifest):
        if found.state == "superseded":
            continue
        broken = broken or found.state == "broken"
        lines.append(f"  generation {found.number} ({found.state})"
                     + (f": {found.detail}" if found.detail else ""))
    return lines, broken


# --- implementation versions and the second commit path (ADR-038) -------------------------

def stored_versions(task_dir, manifest):
    """`(n, versions)`: the generation the manifest names and what its
    `versions.yml` records, or `(None, {})` for an issue with no stored
    generation. The comparison with the installed versions is
    `impl_versions.refusals`."""
    held = generation.number(manifest)
    if not held:
        return None, {}
    return held, generation.load(os.fspath(task_dir), held)["versions"]


def _installed_implementations(checks):
    return {c["impl"]: REGISTRY[c["impl"]].version for c in (checks or {}).values()
            if isinstance(c, dict) and c.get("impl") in REGISTRY}


#: Fields of a locked check that moved with its implementation major, so a pinned generation
#: takes them from the shipped definition. `dod-evidence-typed` 2.0.0 reads "no verification
#: report" and "no list on a closed issue's page" as nothing to check; the 6.x definition said
#: `on_skipped: fail`, which was never reached because 1.0.0 passed both. Pinned to 2.0.0 with
#: the old value, those issues would fail (ADR-051, decision 17). The check is locked, so the
#: stored value is the shipped one of its time and never a project's choice.
_MOVED_WITH_THE_MAJOR = {"dod-evidence-typed": ("on_skipped",)}


def _moved_check_fields(resolved):
    """`resolved` with the fields of `_MOVED_WITH_THE_MAJOR` taken from the check set."""
    checks = resolved.get("checks")
    if not isinstance(checks, dict):
        return resolved
    shipped = check_set.load().get("checks") or {}
    checks = dict(checks)
    for check_id, fields in _MOVED_WITH_THE_MAJOR.items():
        if isinstance(checks.get(check_id), dict) and isinstance(shipped.get(check_id), dict):
            checks[check_id] = dict(checks[check_id], **{
                f: shipped[check_id][f] for f in fields if f in shipped[check_id]})
    return dict(resolved, checks=checks)


def _pin(stored):
    """The stored generation's configuration with its versions replaced by the
    installed ones. Only `versions.yml` changes, and the fields of a locked check that
    moved with its major (`_MOVED_WITH_THE_MAJOR`): a project edit made since must
    reach the issue through a reassess, which classifies it, and never through
    `migrate_generation`."""
    versions = {k: v for k, v in stored["versions"].items() if k != "schema"}
    versions.update(resolver=generation.RESOLVER_VERSION, cli=COMPASS_VERSION,
                    implementations=_installed_implementations(
                        stored["resolved"].get("checks")))
    return generation.Resolution(
        resolved=_moved_check_fields({k: v for k, v in stored["resolved"].items()
                                      if k not in ("schema", "issue", "generation")}),
        provenance={k: v for k, v in stored["provenance"].items() if k != "schema"},
        versions=versions,
        records=[r for r in stored["records"].get("records", [])
                 if r.get("status") == "valid"])


def _set_generation_line(path, target):
    """A function that gives the manifest's own text back with `generation:` set,
    so its comments, key order and gate comments survive the commit."""
    def render(_dumped):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        line = f"generation: {target}"
        if re.search(r"^generation:.*$", text, re.M):
            return re.sub(r"^generation:.*$", line, text, count=1, flags=re.M)
        return text + ("" if text.endswith("\n") else "\n") + line + "\n"
    return render


def migrate_generation(task_dir, *, closed_ok=False):
    """Store the next generation of the issue pinned to the installed versions
    (`compass issue migrate --config`), the second of the three commit paths.
    Returns `(Committed, notes)`. The stored configuration is kept as it is and
    every check result the old generation recorded is invalidated. An issue
    with no stored generation is adopted: its live configuration becomes
    generation 1. Raises `CompassError` for a closed issue, which keeps the
    configuration it closed under. `closed_ok` is for `compass issue migrate`,
    which pins a closed issue that records an implementation major the CLI lacks
    so its check runs; it changes the versions only and keeps the configuration."""
    task_dir = os.path.abspath(os.fspath(task_dir))
    slug = os.path.basename(task_dir)
    path = manifest_path(task_dir)
    manifest = load_manifest_mapping(path)
    if status_words.is_closed(manifest) and not closed_ok:
        raise CompassError(
            f"issue {slug} is closed and keeps the configuration it closed under, so "
            f"`compass issue migrate --config` did not change it")
    held = generation.number(manifest)
    invalidated = {}
    if held:
        stored = generation.load(task_dir, held, any_major=True)
        resolution = _pin(stored)
        if stored["versions"].get("schema") == generation.SCHEMA and all(
                stored["versions"].get(k) == resolution.versions[k]
                for k in ("resolver", "cli", "implementations")):
            return generation.Committed(held, False, (
                f"no change: generation {held} is already pinned to the installed "
                f"versions")), []
        runs = (generation.read_results(task_dir, held) or {}).get("runs") or {}
        invalidated = {f"result:{name}": f"recorded under the versions of generation {held}"
                       for name in sorted(runs)}
    else:
        resolution = resolve_live(project_settings.find_project_root(task_dir), manifest,
                                  slug, task_dir)
        resolution.provenance["adopted"] = "adopted from live governance"
    committed = generation.commit(task_dir, resolution, manifest, invalidated,
                                  render=_set_generation_line(path, (held or 0) + 1),
                                  force=True, closed_ok=closed_ok)
    return committed, ([f"{len(invalidated)} recorded result(s) invalidated"]
                       if invalidated else [])
