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
A project with no `compass.yml` and its own copy of the governance files is
refused (`governance-copy-removed`): 9.0.0 does not read the copy (ADR-098),
and the project moves on 8.x with `compass policy migrate` first. A stored
generation is still read as stored.

Each generation commit also writes the manifest's `policy:` block: the check
set's id, version and sha256, the sha256 of `compass.yml`, the tightenings, the
autonomy and the digest of the stored `resolved.yml` (`policy_block`). When the
folder of the generation the manifest names is missing, as on a fresh clone of
an issue committed without its generation folders (#356), every reader here
rebuilds it from that block first (`restore_from_policy`), and uses it only
when the rebuilt `resolved.yml` has the digest the block records.

This module also builds the `generation.Resolution` a commit stores, and is
the one place the existing modules reach the store through
(`commit_generation`, `record_check_results`, `generation_report`).
"""
# DEPENDENCY: standard library (dataclasses, datetime, hashlib, os, re, subprocess);
# compass_pkg.atomic_io, catalogue_spec, check_registry, check_set, core, generation,
# obligations, project_settings, refusals, removed_parts, tighten.
from __future__ import annotations

import datetime
import hashlib
import os
import re
import subprocess
from dataclasses import dataclass, field

from compass_pkg import check_set, generation, project_settings, removed_parts, tighten
from compass_pkg import obligations, status_words
from compass_pkg import catalogue_spec as spec
from compass_pkg.atomic_io import digest
from compass_pkg.check_registry import REGISTRY
from compass_pkg.core import (AUTONOMY_VALUES, COMPASS_VERSION, CompassError,
                              load_manifest, reading_matches)
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
        the resolved configuration. `effective` is the one module that imports
        `obligations`; readers call this."""
        policy = obligations.policy_adapter(self.config)
        # The tighten-only settings the evidence evaluator reads: the labels that
        # owe what a `G5` label owes, and the evidence a project adds (ADR-094).
        # A configuration that holds neither adds nothing.
        policy = tighten.with_settings(policy, self.resolved)
        # The kinds every approach carries, with the stage whose depth each takes.
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
        (ADR-094), so such a `config:` changes nothing, now or at a commit.
        8.x stored the digest of the overlay as written (`atomic_io.digest`),
        so the raw `config:` is compared with it. A `config:` that is not a
        mapping, or that cannot be digested, is never the stored one."""
        if not isinstance(manifest, dict):
            try:
                manifest = load_manifest_mapping(os.fspath(manifest))
            except (CompassError, OSError, TypeError):
                return True
        raw = manifest.get("config") if isinstance(manifest, dict) else None
        if raw is None:
            return self.versions.get("issue_overlay_digest") is not None
        if not isinstance(raw, dict) or _non_text_keys(raw):
            return True
        return digest(raw) != self.versions.get("issue_overlay_digest")


# --- live resolution ----------------------------------------------------------------

#: The two files a 5.x project copied into its `governance/` folder. 9.0.0 reads
#: neither (ADR-098): a project that holds either one and no `compass.yml` is
#: refused, so its own guardrails are never dropped without a word.
COPIED_GOVERNANCE = ("routing-policy.yml", "guardrails.yml")


def has_governance_copy(root):
    """True when the project keeps a copy of either governance file and has no
    `compass.yml` Compass reads. Nothing is parsed."""
    if project_settings.compass_yml_counts(root):
        return False
    folder = os.path.join(root, "governance")
    return any(os.path.isfile(os.path.join(folder, name)) for name in COPIED_GOVERNANCE)


def refuse_governance_copy(root, verb="this command"):
    """Raise `CompassError` (`governance-copy-removed`, exit 2) for a project
    with copied governance and no `compass.yml`. 8.x moves such a project with
    `compass policy migrate`; 9.0.0 cannot read the copy."""
    if has_governance_copy(root):
        from compass_pkg import refusals
        raise CompassError(refusals.render("governance-copy-removed", verb=verb))


def _non_text_keys(doc, path=""):
    """`[(dotted path of the mapping, key)]` for each mapping key in `doc` that
    is not text. YAML reads an unquoted `on:` or `1:` as a boolean or a number,
    and a mapping that mixes those with text keys cannot be digested."""
    found = []
    if isinstance(doc, dict):
        for key, value in doc.items():
            if not isinstance(key, str):
                found.append((path or "(top level)", key))
            found += _non_text_keys(value, f"{path}.{key}" if path else str(key))
    elif isinstance(doc, (list, tuple)):
        for n, item in enumerate(doc):
            found += _non_text_keys(item, f"{path}[{n}]")
    return found



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


def refuse_git_parent(doc, where=project_settings.COMPASS_YML):
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
        raise CompassError(f"{os.path.join(root, project_settings.COMPASS_YML)}: expected a mapping")
    return doc


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
            f"nothing can be resolved: {project_settings.COMPASS_YML} does not pass the lint. First "
            f"error: {first.code} {first.path}: {first.message} ({len(errors)} "
            f"error(s) in all; run `compass policy lint` to see them)")


def resolve_live(root, manifest=None, slug=None, task_dir=None, validate=False, fetch=False):
    """The `generation.Resolution` of the project now: the check set with the
    tighten-only settings of `compass.yml` applied. An issue's `config:` is not
    read (ADR-094); `manifest` and `task_dir` are accepted for the callers and
    not read. A file that cannot be read, a `compass.yml` the settings lint
    refuses, a git parent in `extends:` and a project with copied governance
    and no `compass.yml` (`refuse_governance_copy`) raise `CompassError` at
    once. `validate` and `fetch` are accepted and not read: the lint always
    runs, and nothing is fetched."""
    root = os.path.abspath(root)
    refuse_governance_copy(root)
    doc = project_doc(root)
    refuse_git_parent(doc)
    autonomy = _autonomy(root)
    # Read, not changed: `resolved` and `tighten.apply` copy what they return.
    loaded = check_set.shared()
    base = check_set.resolved(loaded, autonomy=autonomy)
    if doc is not None:
        _refuse_lint_errors(doc, base)
    tightened = tighten.settings_of(doc)
    # `base` is already a copy, so with nothing to apply it is the result:
    # one copy per resolution, which `compass flow` does for every issue.
    resolved = tighten.apply(base, tightened, loaded) if tightened else base
    parent = _shipped_parent(loaded, check_set.sha256())
    project_path = os.path.join(root, project_settings.COMPASS_YML)
    versions = _versions(parent, tightened, _git_blob(project_path) if doc is not None
                         else None, doc is not None, resolved)
    return generation.Resolution(
        resolved=resolved,
        provenance={"fields": {}, "waivers": {}, "classification": {}},
        versions=versions,
        records=[],
        details={"tightened": tightened})


def _shipped_parent(loaded, sha256):
    """The `parents` entry of `versions.yml` for a resolution from a check set."""
    return {"ref": f"compass:checks@{loaded['version'].split('.')[0]}",
            "version": loaded["version"], "digest": digest(loaded),
            "sha256": sha256, "source": "shipped"}


def _versions(parent, tightened, git_blob, has_settings, resolved):
    """The body of `versions.yml`: what a resolution was resolved with."""
    return {
        "resolver": generation.RESOLVER_VERSION,
        "cli": COMPASS_VERSION,
        "parents": [parent],
        "project": ({"path": project_settings.COMPASS_YML, "digest": digest(tightened),
                     "git_blob": git_blob} if has_settings else None),
        "issue_overlay_digest": None,
        "implementations": _implementations(resolved.get("checks")),
    }


def file_sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def policy_block(root, resolution, resolved_digest):
    """The manifest's `policy:` block for a generation committed from
    `resolution` (ADR-094): the check set and its sha256, the sha256 of
    `compass.yml` (None without one), the tighten-only settings applied as
    written, the autonomy, and the digest of the generation's `resolved.yml`.
    The autonomy is the one input of `resolved.yml` that
    is not in `compass.yml`'s tightenings, so without it a missing folder could
    not be rebuilt (`restore_from_policy`, ADR-096 decision 5)."""
    details = resolution.details or {}
    settings_path = os.path.join(root, project_settings.COMPASS_YML)
    return {
        "check_set": check_set.ref(),
        "check_set_sha256": check_set.sha256(),
        "settings_sha256": (file_sha256(settings_path)
                            if project_settings.compass_yml_counts(root) else None),
        "tightened": dict(details.get("tightened") or {}),
        "autonomy": resolution.resolved.get("autonomy"),
        "resolved": resolved_digest,
    }


# --- the rebuild of a missing generation folder (#356) ----------------------------------

def _policy_resolution(block, autonomy):
    """The `generation.Resolution` the manifest's `policy:` block describes,
    resolved with `autonomy`, or `(None, reason)`. It reads the check set the
    block names, never the project's `compass.yml`: a settings change made
    since must not stop the rebuild, and the digest check catches any other
    difference."""
    loaded, reason = check_set.held(block.get("check_set"), block.get("check_set_sha256"))
    if loaded is None:
        return None, f"{reason}. Run that release, or restore the folder"
    tightened = block.get("tightened") or {}
    if not isinstance(tightened, dict):
        return None, "policy.tightened is not a mapping"
    try:
        base = check_set.resolved(loaded, autonomy=autonomy)
        resolved = tighten.apply(base, tightened, loaded) if tightened else base
    except CompassError as exc:
        return None, f"policy.tightened cannot be applied: {exc}"
    versions = _versions(_shipped_parent(loaded, block.get("check_set_sha256")), tightened,
                         None, block.get("settings_sha256") is not None, resolved)
    return generation.Resolution(
        resolved=resolved, provenance={"fields": {}, "waivers": {}, "classification": {}},
        versions=versions, records=[]), ""


def restore_from_policy(task_dir, manifest=None):
    """Rebuild the folder of the generation the manifest names when it is
    missing and the manifest holds a `policy:` block (#356, ADR-096). Returns
    "" when there is nothing to do or the folder was written, else why it could
    not be rebuilt; the caller's `generation.load` then refuses the issue as
    broken, with that reason.

    The block's check set and `tightened` settings are resolved with the
    recorded `autonomy`. A block written before the autonomy was recorded is
    tried with each of the three values. A result is used only when the digest
    of its `resolved.yml` equals `policy.resolved`, so a rebuild is the stored
    configuration or nothing. A folder that exists is never rebuilt, even when
    it is not whole."""
    task_dir = os.fspath(task_dir)
    if manifest is None:
        manifest, _ = load_manifest(task_dir)
    held = generation.number(manifest)
    if not held or os.path.lexists(generation.gen_dir(task_dir, held)):
        return ""
    block = manifest.get("policy")
    if not isinstance(block, dict):
        return ""
    recorded = block.get("autonomy")
    if recorded is not None and recorded not in AUTONOMY_VALUES:
        return f"policy.autonomy '{recorded}' is not one of {', '.join(AUTONOMY_VALUES)}"
    expected = block.get("resolved")
    found = []
    for autonomy in (recorded,) if recorded is not None else AUTONOMY_VALUES:
        resolution, reason = _policy_resolution(block, autonomy)
        if resolution is None:
            return reason
        got = generation.rebuilt_digest(task_dir, held, resolution)
        if got == expected:
            generation.restore(task_dir, held, resolution, expected)
            return ""
        found.append(f"{got} with autonomy {autonomy}")
    return (f"the rebuilt resolved.yml has the digest {'; '.join(found)}, and "
            f"policy.resolved is {expected}")


def _load(task_dir, held, manifest=None, *, any_major=False):
    """`generation.load`, after a missing folder is rebuilt from `policy:`
    where it can be. A refusal names why the rebuild failed, if one was tried."""
    task_dir = os.fspath(task_dir)
    why = restore_from_policy(task_dir, manifest)
    try:
        return generation.load(task_dir, held, any_major=any_major)
    except CompassError as exc:
        if why:
            raise CompassError(f"{exc}. It could not be rebuilt from the manifest's "
                               f"policy: block: {why}") from None
        raise


def _live_view(task_dir, manifest, slug, start=None):
    start = task_dir or start or os.getcwd()
    root = project_settings.find_project_root(start)
    resolution = resolve_live(root, manifest, slug, task_dir)
    return EffectiveView("live", slug, None, resolution.resolved, resolution.versions,
                         resolution.provenance)


def effective_for(task_dir=None, manifest=None, *, live=False, start=None):
    """The `EffectiveView` an issue runs against, or the project's live view
    for `task_dir=None`. See the module text for the three cases. `manifest`
    is the issue's manifest when the caller already holds it, so a render over
    every issue does not parse each one again; otherwise it is read from the
    file. With `live`, a stored generation is not read: the command is about
    to commit the configuration as it is now. With no issue, `start` is the
    directory whose project is meant (else the working directory). A live
    view of a project with copied governance and no `compass.yml` is refused
    (`resolve_live`)."""
    if task_dir is None:
        return _live_view(None, None, None, start)
    task_dir = os.fspath(task_dir)
    if manifest is None:
        manifest, _ = load_manifest(task_dir)
    slug = os.path.basename(os.path.normpath(task_dir))
    held = generation.number(manifest)
    if held is None or live:
        return _live_view(task_dir, manifest, slug)
    if held == 0:
        raise CompassError(
            f"issue {slug} is at generation 0: it was assessed but has no stored "
            f"configuration yet; run `{generation.FIX_ZERO} --issue {slug}`")
    stored = _load(task_dir, held, manifest, any_major=status_words.is_closed(manifest))
    return EffectiveView("generation", slug, held, stored["resolved"], stored["versions"],
                         stored["provenance"])


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
    _refuse_unrebuilt(task_dir)
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
    _refuse_unrebuilt(task_dir)
    generation.preflight(task_dir, resolution, manifest)
    return resolution


def _refuse_unrebuilt(task_dir):
    """Before a commit reads the generation in force from disk: rebuild its
    missing folder, or refuse with the reason it could not be rebuilt."""
    manifest, _ = load_manifest(task_dir)
    if restore_from_policy(task_dir, manifest):
        _load(task_dir, generation.number(manifest), manifest, any_major=True)


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
    return _load(task_dir, held, manifest,
                 any_major=status_words.is_closed(manifest)) if held else None


def require_whole(task_dir):
    """Refuse an issue whose manifest names a generation that is not whole
    (a missing folder or marker, or a file that does not match its digest).
    An issue with no generation, or at generation 0, is not refused: it has
    nothing stored to be broken."""
    manifest, _ = load_manifest(task_dir)
    held = generation.number(manifest)
    if held:
        _load(task_dir, held, manifest, any_major=status_words.is_closed(manifest))


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
    checks = _load(task_dir, held, manifest)["resolved"].get("checks") or {}
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
    why = restore_from_policy(task_dir, manifest)
    for found in generation.states(task_dir, manifest):
        if found.state == "superseded":
            continue
        broken = broken or found.state == "broken"
        detail = found.detail + (f"; it could not be rebuilt from policy: ({why})"
                                 if why and found.number == held else "")
        lines.append(f"  generation {found.number} ({found.state})"
                     + (f": {detail}" if detail else ""))
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
    return held, _load(task_dir, held, manifest)["versions"]


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
        # A pinned generation is not itself rebuilt, so the rebuild's note goes.
        provenance={k: v for k, v in stored["provenance"].items()
                    if k not in ("schema", "restored_from", "restored_at")},
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
        stored = _load(task_dir, held, manifest, any_major=True)
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
