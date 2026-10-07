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
# DEPENDENCY: standard library (dataclasses, datetime, os, subprocess);
# compass_pkg.atomic_io, check_registry, core, generation, layers,
# legacy_adapter, locks, merge, obligations, policy_lint, project_settings, waivers.
from __future__ import annotations

import datetime
import os
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
        validate=check_chain)


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


def commit_generation(task_dir, manifest, invalidated=None, render=None):
    """Store the configuration the issue resolves to now as its next
    generation and replace its manifest, as `approach evaluate --write` does.
    `manifest` is the mapping to write, with the computed outcome folded in.
    The chain is resolved first, and linted only when a write follows, so a
    configuration that does not resolve or lint leaves every file as it was."""
    task_dir = os.path.abspath(os.fspath(task_dir))
    slug = os.path.basename(task_dir)
    resolution = resolve_live(layers.find_project_root(task_dir), manifest, slug, task_dir)
    return generation.commit(task_dir, resolution, manifest, invalidated, render)


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


def record_check_results(task_dir, verdicts):
    """Rewrite `results.yml` of the generation the issue runs against with the
    verdict of each check in `verdicts` (`{check id: pass | fail |
    nothing-to-check}`): when it ran, which implementation and version ran
    it, and a digest of the check's definition as the generation stores it.
    An issue with no generation gets no file. Returns the number of checks
    written, or None."""
    task_dir = os.fspath(task_dir)
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
