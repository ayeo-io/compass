# compass_pkg.effective - the reading interface to an issue's configuration
"""One place that answers "what configuration does this issue run against?"

`effective_for(task_dir)` returns an `EffectiveView`:

- an issue whose manifest names `generation: n` (n at least 1) gets generation
  n, read from its folder, and nothing else (ADR-036);
- an issue whose manifest has no `generation:` key predates 6.0.0 and gets the
  live configuration, as 5.6.0 read it (ADR-006);
- `generation: 0` is refused, naming the command that commits the first one;
- no issue (`task_dir=None`) gets the live configuration of the project.

"Live" means the shipped default, then the project's own layer, resolved now.
A project with no `compass.yml` and its own copies of the two governance files
has those files read through the legacy adapter in place of the shipped
default, so what an issue is stored against is what ran before.

This module also builds the `generation.Resolution` a commit stores, and is
the one place the existing modules reach the store through
(`commit_generation`, `record_check_results`, `generation_report`).
"""
# DEPENDENCY: standard library (copy, dataclasses, datetime, os, re, subprocess);
# compass_pkg.atomic_io, check_registry, core, generation, layers,
# legacy_adapter, locks, merge, obligations, policy_lint, project_settings, waivers.
from __future__ import annotations

import copy
import datetime
import os
import re
import subprocess
from dataclasses import dataclass, field

from compass_pkg import (generation, layers, legacy_adapter, locks, merge, policy_lint,
                         project_settings, waivers)
from compass_pkg import obligations
from compass_pkg import catalogue_spec as spec
from compass_pkg.atomic_io import digest, load_yaml_strict
from compass_pkg.check_registry import REGISTRY
from compass_pkg.core import (AUTONOMY_VALUES, COMPASS_VERSION, FRAMEWORK_ROOT,
                              GOVERNANCE_FILES, CompassError, load_manifest, load_yaml)

OUTCOME_KEYS = ("delivery_approach", "stages", "gates", "checkpoints",
                "policy_rules_fired", "subtask_ceiling", "artifacts")


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
        return obligations.policy_adapter(self.config)


# --- live resolution ----------------------------------------------------------------

def _legacy_parent(root):
    """`(Layer, meta)` for a project that keeps its own copies of the two
    governance files, or None when it has none (or is the framework's own
    repository, whose files are views of the shipped default)."""
    folder = os.path.join(root, "governance")
    if os.path.realpath(folder) == os.path.realpath(os.path.join(FRAMEWORK_ROOT, "governance")):
        return None
    if not all(os.path.isfile(os.path.join(folder, name)) for name in GOVERNANCE_FILES):
        return None
    policy = load_yaml(os.path.join(folder, "routing-policy.yml"))
    guardrails = load_yaml(os.path.join(folder, "guardrails.yml"))
    shipped, _ = policy_lint.load_parent()
    doc = legacy_adapter.adapt(policy, guardrails)
    doc["capabilities"] = dict(shipped.doc.get("capabilities") or {})
    layer = layers.Layer("legacy", "parent", doc, layers.layer_digest(doc, "parent"))
    return layer, {"id": "legacy", "version": str(policy.get("version", "")),
                   "source": "legacy", "guardrails": guardrails}


def _evidence_types(root, legacy):
    if legacy:
        return legacy_adapter.adapt_evidence_types(legacy[1]["guardrails"])["evidence_types"]
    path = os.path.join(FRAMEWORK_ROOT, policy_lint.PRESET_DIR, "evidence-types.yml")
    return (load_yaml_strict(path).get("evidence_types") or {}) if os.path.isfile(path) else {}


def _autonomy(root, overlay):
    """The issue overlay's `autonomy`, else the project's, else `balanced`."""
    value = (overlay or {}).get("autonomy") or project_settings.settings(root).get("autonomy")
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


def _steps(chain):
    """`({path: {steps: [{layer, op}]}}, config, per-layer configs)` from applying
    the chain one layer at a time, so a field keeps every layer that wrote it."""
    config, prov, history, configs = {}, {}, {}, []
    for layer in chain:
        before = dict(prov)
        config, prov = merge.apply(config, layer.doc, layer.kind, layer.name, prov)
        for path, step in prov.items():
            if before.get(path) != step:
                history.setdefault(path, {"steps": []})["steps"].append(
                    {"layer": step["layer"], "op": step["operation"]})
        configs.append(config)
    return history, config, configs


def _waiver_records(chain, configs, project_digest, project_doc):
    out = {}
    for index, layer in enumerate(chain):
        if layer.kind == "parent":
            continue
        scope = "issue" if layer.kind == "issue" else "project"
        found, _ = waivers.find(layer.doc, scope)
        covered = (waivers.covered_revision("project", extends=(project_doc or {}).get("extends"))
                   if scope == "project" else
                   waivers.covered_revision("issue", versions={"project": {"digest": project_digest}}))
        for waiver in found:
            record = waivers.describe(waiver, configs[index - 1], configs[index], covered)
            record["status"] = "valid"
            out[waiver.id] = record
    return out


def _approval_records(manifest, root, task_dir, waiver_records):
    """One record per waiver, and one per evidence entry an issue waiver
    names as its approval, with the digest of the file it read."""
    out = [{"id": f"waiver:{wid}", "kind": "waiver", "status": "valid"}
           for wid in sorted(waiver_records)]
    registry = {e.get("id"): e for e in manifest.get("evidence") or () if isinstance(e, dict)}
    for wid, record in sorted(waiver_records.items()):
        entry = registry.get(record.get("approved_by")) if record["scope"] == "issue" else None
        if not entry:
            continue
        item = {"id": entry["id"], "kind": "approval", "status": "valid"}
        if entry.get("path"):
            item["path"] = entry["path"]
            full = os.path.join(task_dir, entry["path"]) if task_dir else None
            if full and os.path.isfile(full):
                with open(full, "rb") as fh:
                    item["input_digest"] = digest(fh.read().decode("utf-8", "replace"))
        out.append(item)
    return out


def resolve_live(root, manifest=None, slug=None, task_dir=None, validate=False):
    """The `generation.Resolution` of the project's chain now: the shipped
    default (or the project's legacy copies), the project's `compass.yml` and,
    for an issue, its manifest's `config:`. The result carries `validate`, which
    raises `CompassError` when the layered lint refuses the chain; `commit`
    calls it before it writes, so a generation never stores such a chain. With
    `validate=True` it is called here too. A chain that does not load or merge
    raises `CompassError` at once."""
    root = os.path.abspath(root)
    counts = project_settings.compass_yml_counts(root)
    loaded = policy_lint.load_layers(root, manifest=manifest, read_project=counts)
    if loaded.findings:
        first = loaded.findings[0]
        raise CompassError(f"nothing can be resolved: {first.code} {first.path}: "
                           f"{first.message}")
    legacy = None if counts else _legacy_parent(root)
    parent, meta = legacy if legacy else (loaded.parent, loaded.meta)
    if legacy:
        loaded.parent = parent
    # Each layer is checked alone before anything merges. The full lint, which
    # includes the classifier and is slow on a project layer, runs only when a
    # write follows: `generation.commit` calls `validate` then.
    chain = layers.build_chain(parent, loaded.project, loaded.issue)

    def check_chain():
        report = policy_lint.lint_loaded(loaded)
        if not report.ok:
            first = report.errors[0]
            where = {"project": layers.PROJECT_FILE, "issue": "the config: of manifest.yml"
                     }.get(first.layer, f"the {first.layer} configuration")
            raise CompassError(
                f"nothing was written: {where} does not pass the lint. First error: "
                f"{first.code} {first.path}: {first.message} ({len(report.errors)} error(s) "
                f"in all; run `compass policy lint"
                + (f" --issue {slug}" if slug else "") + "` to see them)")

    if validate:
        check_chain()
    history, config, configs = _steps(chain)
    overlay = loaded.issue.doc if loaded.issue else None
    project_doc = loaded.project.doc if loaded.project else None
    project_digest = loaded.project.digest if loaded.project else None
    capabilities = {}
    for layer in chain:
        capabilities.update(layer.doc.get("capabilities") or {})
    project_path = os.path.join(root, layers.PROJECT_FILE)
    conformance = (locks.conformance(loaded.project, locks.shipped_locks())
                   if loaded.project else locks.Conformance("conformant", (), ()))
    waiver_records = _waiver_records(chain, configs, project_digest, project_doc)
    classification = {
        layer.name: {"result": "accepted",
                     "waivers": sorted(w for w, r in waiver_records.items()
                                       if r["scope"] == ("issue" if layer.kind == "issue"
                                                         else "project"))}
        for layer in chain if layer.kind != "parent"}
    resolved = {
        "capabilities": capabilities,
        "approach": (overlay or {}).get("approach"),
        "autonomy": _autonomy(root, overlay),
        "conformance": {"status": conformance.status, "unlocked": list(conformance.unlocked)},
        **{name: config[name] for name in spec.CATALOGUES if name in config},
        "evidence_types": _evidence_types(root, legacy),
    }
    major = str(meta.get("version", "")).split(".")[0]
    versions = {
        "resolver": generation.RESOLVER_VERSION,
        "cli": COMPASS_VERSION,
        "parents": [{"ref": f"compass:{meta['id']}@{major}" if not legacy else "legacy",
                     "version": meta.get("version", ""), "digest": parent.digest,
                     "source": "legacy" if legacy else "shipped"}],
        "project": ({"path": layers.PROJECT_FILE, "digest": project_digest,
                     "git_blob": _git_blob(project_path)} if loaded.project else None),
        "issue_overlay_digest": loaded.issue.digest if loaded.issue else None,
        "implementations": {check["impl"]: REGISTRY[check["impl"]].version
                            for check in (config.get("checks") or {}).values()
                            if isinstance(check, dict) and check.get("impl") in REGISTRY},
    }
    return generation.Resolution(
        resolved=resolved,
        provenance={"fields": history, "waivers": waiver_records,
                    "classification": classification},
        versions=versions,
        records=_approval_records(manifest or {}, root, task_dir, waiver_records),
        validate=check_chain,
        details={"loaded": loaded, "chain": chain, "configs": configs})


def _live_view(task_dir, manifest, slug):
    start = task_dir if task_dir else os.getcwd()
    root = layers.find_project_root(start)
    resolution = resolve_live(root, manifest, slug, task_dir)
    return EffectiveView("live", slug, None, resolution.resolved, resolution.versions)


def effective_for(task_dir=None):
    """The `EffectiveView` an issue runs against, or the project's live view
    for `task_dir=None`. See the module text for the three cases."""
    if task_dir is None:
        return _live_view(None, None, None)
    task_dir = os.fspath(task_dir)
    manifest, _ = load_manifest(task_dir)
    slug = os.path.basename(os.path.normpath(task_dir))
    held = generation.number(manifest)
    if held is None:
        return _live_view(task_dir, manifest, slug)
    if held == 0:
        raise CompassError(
            f"issue {slug} is at generation 0: it was assessed but has no stored "
            f"configuration yet; run `{generation.FIX_ZERO} --issue {slug}`")
    stored = generation.load(task_dir, held)
    return EffectiveView("generation", slug, held, stored["resolved"], stored["versions"])


def commit_generation(task_dir, manifest, invalidated=None, render=None, *, adopt=None,
                      proposal=None, stamp=None, resolve_with=None, resolution=None):
    """Store the configuration the issue resolves to now as its next
    generation and replace its manifest, as `approach evaluate --write` does.
    `manifest` is the mapping to write, with the computed outcome folded in.
    The chain is resolved first, and linted only when a write follows, so a
    configuration that does not resolve or lint leaves every file as it was.

    `resolution` is a resolution already made (the reassess plan makes it
    before anything prints); otherwise it is made here from `resolve_with`,
    the manifest to resolve from when it is not the one written (a waiver the
    reassess invalidated is left out of the resolution and stays in the file).
    `adopt`, `proposal` and `stamp` are those of `generation.commit`."""
    task_dir = os.path.abspath(os.fspath(task_dir))
    slug = os.path.basename(task_dir)
    if resolution is None:
        resolution = resolve_live(layers.find_project_root(task_dir),
                                  manifest if resolve_with is None else resolve_with,
                                  slug, task_dir)
    return generation.commit(task_dir, resolution, manifest, invalidated, render,
                             adopt=adopt, proposal=proposal, stamp=stamp)


def preflight(task_dir, resolution, manifest, invalidated=None, adopt=None, stored=None):
    """Settle, before the reassess prints anything, what the commit would
    refuse later (`generation.preflight`). A refusal that names a waiver the
    generation in force invalidated gets the reason and the two ways out."""
    try:
        generation.preflight(os.fspath(task_dir), resolution, manifest, invalidated, adopt)
    except CompassError as exc:
        raise CompassError(str(exc) + _invalidated_advice(str(exc), stored)) from None


def ways_out(reason):
    """What to do about an invalidated waiver, and when it holds again."""
    seen = re.search(r"changed from (.+?) to ", reason or "")
    back = seen.group(1) if seen else "what the approval named"
    return ("To keep the change, approve it again with a new human-approval record that "
            "names the new values; otherwise remove the entry from config:. It is valid "
            f"again if the parent value returns to {back}.")


def _invalidated_advice(message, stored):
    """For each waiver of the generation in force that `records.yml` marks
    invalidated and the message names: why, and how to settle it."""
    out = []
    for record in ((stored or {}).get("records") or {}).get("records") or ():
        if record.get("kind") != "waiver" or record.get("status") != "invalidated":
            continue
        if record["id"].split(":", 1)[1] in message:
            out.append(f" {record['id']} was invalidated in generation "
                       f"{(stored.get('resolved') or {}).get('generation')}: "
                       f"{record.get('reason')}. {ways_out(record.get('reason'))}")
    return "".join(out)


def leftover_overlay_digest(task_dir, number):
    """The `issue_overlay_digest` a whole leftover folder recorded, or the
    string `unreadable` when the folder is not whole."""
    try:
        return generation.load(os.fspath(task_dir), number)["versions"].get(
            "issue_overlay_digest")
    except CompassError:
        return "unreadable"


# --- the waiver re-check at reassess ----------------------------------------------------

def _issue_waivers(stored):
    records = ((stored or {}).get("provenance") or {}).get("waivers") or {}
    return [r for r in records.values() if isinstance(r, dict) and r.get("scope") == "issue"]


def stale_waivers(stored, details):
    """The issue waivers of the generation in force that the configuration now
    resolved leaves without an approval: `({waiver id: reason}, [(catalogue,
    entry)])`, the entries being those the overlay still holds.

    A waiver is stale when the parent value of a waived field changed since the
    approval was given (`waivers.recheck`), or when the overlay now sets a waived
    field to another value, because the approval named the values it saw. A
    waiver the overlay no longer holds is not stale: nothing is left to excuse."""
    chain, configs = details["chain"], details["configs"]
    layer = chain[-1] if chain and chain[-1].kind == "issue" else None
    records = _issue_waivers(stored)
    if layer is None or not records:
        return {}, []
    found, _ = waivers.find(layer.doc, "issue")
    held = {w.id: w for w in found}
    parent, child = configs[-2], configs[-1]
    stale = {}
    for moved in waivers.recheck([r for r in records if r["id"] in held], parent):
        stale.setdefault(moved.waiver_id, moved.reason)
    for record in records:
        waiver = held.get(record["id"])
        if waiver is None or record["id"] in stale:
            continue
        now = waivers.describe(waiver, parent, child, None)["fields"]
        for name, seen in record["fields"].items():
            if now.get(name, {}).get("to") != seen["to"]:
                stale[record["id"]] = (
                    f"{record['entry']}.{name}: the issue's value changed from "
                    f"{seen['to']!r} to {now.get(name, {}).get('to')!r}, so the approval "
                    f"no longer matches the waiver")
                break
    return stale, [(held[w].catalogue, held[w].entry) for w in sorted(stale)]


def invalidated_records(stored, stale):
    """`{record id: reason}` for the waiver records and the approvals that back
    them, from the `stale` map `stale_waivers` returned."""
    by_id = {r["id"]: r for r in _issue_waivers(stored)}
    out = {}
    for waiver_id, reason in stale.items():
        out[f"waiver:{waiver_id}"] = reason
        backing = by_id.get(waiver_id, {}).get("approved_by")
        if backing:
            out[str(backing)] = f"it approved waiver:{waiver_id}, which is invalid: {reason}"
    return out


def without_entries(manifest, entries):
    """A copy of `manifest` whose `config:` no longer holds the given
    `(catalogue, entry)` pairs, so the field reverts to the parent's value. The
    manifest that is written keeps them."""
    if not entries:
        return manifest
    out = copy.deepcopy(manifest)
    config = out.get("config") or {}
    for catalogue, entry in entries:
        table = config.get(catalogue)
        if isinstance(table, dict):
            table.pop(entry, None)
            if not table:
                config.pop(catalogue)
    if config:
        out["config"] = config
    else:
        out.pop("config", None)
    return out


# --- proposals, leftovers and the stored copy ---------------------------------------

config_digest = generation.config_digest
generation_number = generation.number
FIX_ZERO = generation.FIX_ZERO


def stored_documents(task_dir, manifest):
    """The four documents of the generation the manifest names, or None when
    it names none yet. A generation that is not whole raises `CompassError`."""
    held = generation.number(manifest)
    return generation.load(os.fspath(task_dir), held) if held else None


def pending_proposal(task_dir, manifest):
    """The `generation.Proposal` waiting above the generation in force, or None."""
    return generation.pending_proposal(os.fspath(task_dir), manifest)


def write_proposal(task_dir, manifest, overlay):
    """Park `overlay` as the issue's pending `config:`; the manifest is untouched."""
    return generation.write_proposal(task_dir, manifest, overlay)


def leftover(task_dir, number):
    """The `GenState` of the folder for generation `number`, or None when
    there is none."""
    return next((g for g in generation.states(os.fspath(task_dir)) if g.number == number),
                None)


def discard(task_dir, number=None):
    """Remove a proposal or leftover folder above the generation in force."""
    return generation.discard(task_dir, number)


def require_whole(task_dir):
    """Refuse an issue whose manifest names a generation that is not whole
    (a missing folder or marker, or a file that does not match its digest).
    An issue with no generation, or at generation 0, is not refused: it has
    nothing stored to be broken."""
    manifest, _ = load_manifest(task_dir)
    held = generation.number(manifest)
    if held:
        generation.load(os.fspath(task_dir), held)


def _verdict_rank(verdict):
    return ("pass", "nothing-to-check", "fail").index(verdict)


def record_check_results(task_dir, verdicts, manifest=None):
    """Rewrite `results.yml` of the generation the issue runs against with the
    verdict of each check in `verdicts` (`{check id: pass | fail |
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
