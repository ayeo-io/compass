# compass_pkg.policy_lint - the layered policy lint and the effective view
"""Check a configuration chain in a fixed order, and show what it resolves to.

The chain is the shipped parent, the project's `compass.yml` and, when asked,
one issue's `config:` (ADR-043, ADR-036). `lint_chain` runs five groups and
stops after the first group that has an error, so a person fixes the earliest
fault first and never sees a fault that only follows from it:

1. `layer`: each layer alone, before anything merges;
2. `merge`: the one merge grammar (ADR-035);
3. `resolved`: checks that need the merged result;
4. `locks`: what the locks above a layer refuse (ADR-039);
5. `classification`: waivers, the classifier's verdict and the vocabulary.

The functions are pure over layer documents. `load_parent` and `load_layers`
are the only readers of files. The text and JSON renderings are in this
module so the two views of one result cannot disagree. The JSON shapes are a
public contract (`docs/policy-lint.md`), and `tests/test_policy_lint.py` pins
both.
"""
# DEPENDENCY: standard library (dataclasses, datetime, json, os, re);
# compass_pkg.atomic_io, catalogue_check, catalogue_spec, check_registry,
# layers, locks, merge, waivers, core (CompassError, FRAMEWORK_ROOT).
from __future__ import annotations

import datetime
import json
import os
import re
from dataclasses import dataclass, field

from compass_pkg import catalogue_check, layers, locks, merge, parents, waivers
from compass_pkg import catalogue_spec as spec
from compass_pkg.atomic_io import StrictYamlError, load_yaml_strict
from compass_pkg.check_registry import REGISTRY
from compass_pkg.core import FRAMEWORK_ROOT, CompassError

JSON_SCHEMA_VERSION = 1

GROUPS = ("layer", "merge", "resolved", "locks", "classification")

# Every code the lint names itself. The merge's `M-*` codes and the waivers'
# `W-*` codes pass through under their own names (`docs/policy-lint.md`).
FINDING_CODES = (
    "L-LOAD", "L-KEY-NOT-TEXT", "L-SCHEMA", "L-SETTINGS-KEY", "L-UNLOCK-PLACEMENT", "L-IMPL-UNKNOWN",
    "L-IMPL-TEMPLATED", "L-IGNORED-FILE", "L-PARENT-FORM", "L-PARENT-NO-SHA",
    "L-PARENT-NOT-CACHED", "L-PARENT-FETCH", "L-PARENT-CONTENT", "L-PARENT-SHA-MISMATCH",
    "L-PARENT-SYMLINK", "L-PARENT-CACHE", "L-PARENT-CHAIN", "L-PARENT-SHA-AMBIGUOUS",
    "M-REF-UNKNOWN", "M-WEIGHT-TIE", "M-HIT-MISSING", "M-HIT-DISALLOWED", "M-CYCLE",
    "M-EFFECT-UNKNOWN",
    "K-LOCK-REFUSED", "K-UNLOCK-REFUSED", "K-UNPROVABLE",
    "E-EVALUATION",
    "C-LOOSENING", "C-INCOMPARABLE", "V-VOCABULARY-CHANGE",
    "W-APPROVED-ON-ISSUE", "W-UNNEEDED",
    "LEGACY-STRUCTURE", "LEGACY-WAIVER", "LEGACY-WAIVED", "LEGACY-DRIFT",
    "LEGACY-DRIFT-UNCOMPARED",
)
PRESET_DIR = os.path.join("governance", "presets", "default")
TEMPLATE_MARKS = ("{{", "{%", "${")


@dataclass
class Finding:
    code: str
    level: str          # "error", "warning", or "info" (a recorded decision)
    layer: str
    path: str
    group: str
    message: str
    detail: object = None


@dataclass
class Report:
    mode: str = "layered"
    layers: list = field(default_factory=list)      # [(name, kind)]
    findings: list = field(default_factory=list)
    stopped_after: object = None

    @property
    def errors(self):
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self):
        return [f for f in self.findings if f.level == "warning"]

    @property
    def ok(self):
        return not self.errors


@dataclass
class Loaded:
    """What `load_layers` read: the chain, the parent's identity, the issue's
    evidence registry and the findings of a layer that did not load."""
    parent: object
    meta: dict
    project: object = None
    issue: object = None
    registry: tuple = ()
    git_parents: list = field(default_factory=list)     # [parents.Parent], root first
    findings: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    failed: object = None       # (name, kind) of a layer that did not load


# --- loading -----------------------------------------------------------------------

def load_parent(root=None, directory=None):
    """`(Layer, meta)` for the shipped default preset: its eight catalogue
    files as one parent layer named `default`, and `{id, version}`. The
    capabilities come from `preset.yml`. `directory` names another preset
    folder (a major the framework keeps beside the shipped one) and wins
    over `root`."""
    directory = os.fspath(directory) if directory else os.path.join(
        os.fspath(root or FRAMEWORK_ROOT), PRESET_DIR)
    preset_file = os.path.join(directory, "preset.yml")
    try:
        meta = load_yaml_strict(preset_file)
    except StrictYamlError as exc:
        # The text already names the file; a command reports it, never a traceback.
        raise CompassError(f"the shipped default preset cannot be read: {exc}") from exc
    doc = {"schema": meta.get("schema", 1), "capabilities": dict(meta.get("capabilities") or {})}
    if meta.get("approvers") is not None:
        doc["approvers"] = meta["approvers"]
    for name in spec.CATALOGUES:
        path = os.path.join(directory, f"{name}.yml")
        if os.path.isfile(path):
            doc[name] = load_yaml_strict(path)[name]
    layer = layers.Layer("default", "parent", doc, layers.layer_digest(doc, "parent"))
    return layer, {"id": meta.get("id", "default"), "version": str(meta.get("version", ""))}


def _shown(path, root):
    """`path` as a person sees it: from the project root when it is inside,
    otherwise the file's own name. An absolute path is machine-specific, so
    it never reaches a finding."""
    absolute, base = os.path.abspath(path), os.path.abspath(root)
    inside = absolute.startswith(base + os.sep)
    return os.path.relpath(absolute, base) if inside else os.path.basename(absolute)


def _load_finding(layer, path, root, exc):
    shown = _shown(path, root).replace(os.sep, "/")
    message = str(exc).replace(os.path.abspath(path), shown)
    return Finding("L-LOAD", "error", layer, shown, "layer", " ".join(message.split()))


def _non_text_findings(out, layer, doc):
    """Add one `L-KEY-NOT-TEXT` finding per non-text key in `doc` to `out`
    and say whether there was any. It runs before the layer is digested,
    because a mapping that mixes such keys with text keys cannot be sorted."""
    keys = layers.non_text_keys(doc)
    for path, key in keys:
        out.findings.append(Finding("L-KEY-NOT-TEXT", "error", layer, path, "layer",
                                    layers.non_text_key_message(key)))
    return bool(keys)


def _ignored_file(root, cwd):
    """A warning when the working folder is below the project root and holds a
    `compass.yml`: the loader reads the root's file only (ADR-043)."""
    if not cwd or os.path.abspath(cwd) == os.path.abspath(root):
        return []
    path = os.path.join(os.path.abspath(cwd), layers.PROJECT_FILE)
    if not os.path.isfile(path):
        return []
    shown = os.path.relpath(path, os.path.abspath(root))
    return [Finding("L-IGNORED-FILE", "warning", "project", shown, "layer",
                    "this compass.yml is below the project root and is ignored; the "
                    "project's file is the one in the root")]


def _git_parent(out, root, extends, fetch):
    """Resolve the project's `extends:` when it names a git parent. A refusal
    is a finding on the project layer, and ends the lint at the first group."""
    try:
        found = parents.resolve(root, extends, fetch=fetch)
    except parents.ParentError as exc:
        out.findings.append(Finding(exc.code, "error", exc.layer, exc.path, "layer",
                                    exc.detail))
        out.failed = ("project", "project") if exc.layer == "project" \
            else (exc.layer, "parent")
        return
    if found:
        out.git_parents.append(found)


def load_layers(root, *, file=None, manifest=None, cwd=None, read_project=True,
                fetch=False):
    """The chain for a project. `file` lints one `compass.yml` over the
    shipped parent instead of the project's own. `manifest` is a parsed issue
    manifest, whose `config:` is the issue layer and whose `evidence:` is the
    registry an issue waiver's approval is looked up in. A file that does not
    load is a finding, not an exception; a file that is not there is an
    error for the caller."""
    parent, meta = load_parent()
    out = Loaded(parent, meta)
    if not file:
        out.warnings = _ignored_file(root, cwd)
    path = os.fspath(file) if file else os.path.join(os.fspath(root), layers.PROJECT_FILE)
    if file and not os.path.isfile(path):
        raise CompassError(f"no such file: {path}")
    if (read_project or file) and os.path.isfile(path):
        try:
            doc = load_yaml_strict(path)
            if _non_text_findings(out, "project", doc):
                out.failed = ("project", "project")
            else:
                out.project = layers.Layer("project", "project", doc,
                                           layers.layer_digest(doc, "project")
                                           if isinstance(doc, dict) else "")
                if isinstance(doc, dict):
                    _git_parent(out, root, doc.get("extends"), fetch)
        except StrictYamlError as exc:
            out.findings.append(_load_finding("project", path, root, exc))
            out.failed = ("project", "project")
    if manifest is not None:
        config = manifest.get("config")
        if config is not None:
            if _non_text_findings(out, "issue", config):
                out.failed = out.failed or ("issue", "issue")
            else:
                out.issue = layers.Layer("issue", "issue", config,
                                         layers.layer_digest(config, "issue")
                                         if isinstance(config, dict) else "")
        out.registry = tuple(manifest.get("evidence") or ())
    return out


# --- the groups ----------------------------------------------------------------------

def _finding(group, code, layer, path, message, level="error", detail=None):
    return Finding(code, level, layer.name if hasattr(layer, "name") else layer, path,
                   group, message, detail)


def _schema_code(path, message):
    key = path.rsplit(".", 1)[-1]
    if "settings key" in message:
        return "L-SETTINGS-KEY"
    if key in ("unlock", "unlocks"):
        return "L-UNLOCK-PLACEMENT"
    return "L-SCHEMA"


def _impl_findings(layer):
    out = []
    checks = layer.doc.get("checks") if isinstance(layer.doc, dict) else None
    for check_id, entry in (checks.items() if isinstance(checks, dict) else ()):
        if not isinstance(entry, dict):
            continue
        changes = entry.get("set")
        for path, value in ((f"checks.{check_id}.impl", entry.get("impl")),
                            (f"checks.{check_id}.set.impl",
                             changes.get("impl") if isinstance(changes, dict) else None)):
            if not isinstance(value, str):
                continue
            if any(mark in value for mark in TEMPLATE_MARKS):
                out.append(_finding("layer", "L-IMPL-TEMPLATED", layer, path,
                                    f"impl '{value}' is a template; name a check "
                                    f"implementation from the registry"))
            elif value not in REGISTRY:
                out.append(_finding("layer", "L-IMPL-UNKNOWN", layer, path,
                                    f"impl '{value}' is not in the check registry "
                                    f"({', '.join(sorted(REGISTRY))})"))
    return out


def _layer_group(state):
    out = []
    for layer in state["chain"]:
        for text in catalogue_check.check_layer(layer.doc, layer.kind):
            path, _, message = text.partition(": ")
            out.append(_finding("layer", _schema_code(path, message), layer, path,
                                message or text))
        if not isinstance(layer.doc, dict):
            continue
        out += _impl_findings(layer)
        if layer.kind == "issue":
            found, _ = waivers.find(layer.doc, "issue")
            for waiver in found:
                out += [_finding("layer", f.code, layer, waiver.id, f.message)
                        for f in waivers.check_shape(waiver, state["today"])
                        if f.code == "W-APPROVED-ON-ISSUE"]
    return out


def _merge_group(state):
    """Merge each layer on the one before it. The first layer the merge
    refuses ends the group, with every fault of that layer reported; a later
    layer cannot be merged on a result that does not exist. The resolved
    configuration after each layer is kept for the groups that follow."""
    config, provenance, out = {}, {}, []
    state["configs"] = []
    for layer in state["chain"]:
        try:
            config, provenance = merge.apply(config, layer.doc, layer.kind, layer.name,
                                             provenance)
        except merge.MergeError as exc:
            out += [_finding("merge", code, layer, path, message)
                    for code, path, message in exc.errors]
            break
        state["configs"].append(config)
    state["config"], state["provenance"] = config, provenance
    return out


def _layer_of(state, path):
    """The layer that wrote the longest prefix of `path` the provenance
    knows, or the last layer of the chain when it knows none. Ids can hold
    dots, so the prefix is shortened one part at a time."""
    parts = path.split(".")
    for n in range(len(parts), 0, -1):
        written = state["provenance"].get(".".join(parts[:n]))
        if written:
            return written["layer"]
    return state["chain"][-1].name


def _names(value, shape):
    if shape == "list" and isinstance(value, list):
        return value
    if shape == "map" and isinstance(value, dict):
        return list(value)
    if shape == "scalar" and isinstance(value, str):
        return [value]
    return []


def _unknown_references(state):
    out, config = [], state["config"]
    for catalogue, name, target, shape in merge.REFERENCES:
        known = config.get(target) or {}
        for entry_id, entry in (config.get(catalogue) or {}).items():
            missing = [n for n in _names(entry.get(name) if isinstance(entry, dict)
                                         else None, shape)
                       if isinstance(n, str) and n not in known]
            if missing:
                path = f"{catalogue}.{entry_id}.{name}"
                out.append(_finding("resolved", "M-REF-UNKNOWN", _layer_of(state, path),
                                    path, f"names {', '.join(missing)}, which {target} "
                                    f"does not define"))
    return out


def _weight_ties(state):
    by_weight, out = {}, []
    for approach_id, entry in (state["config"].get("approaches") or {}).items():
        weight = entry.get("weight") if isinstance(entry, dict) else None
        if isinstance(weight, int) and not isinstance(weight, bool):
            by_weight.setdefault(weight, []).append(approach_id)
    names = [layer.name for layer in state["chain"]]
    for weight, ids in sorted(by_weight.items()):
        if len(ids) < 2:
            continue
        # The tie is blamed on the entry the latest layer wrote.
        blamed = max(sorted(ids), key=lambda i: names.index(
            _layer_of(state, f"approaches.{i}.weight")))
        path = f"approaches.{blamed}.weight"
        out.append(_finding("resolved", "M-WEIGHT-TIE", _layer_of(state, path), path,
                            f"approaches {', '.join(sorted(ids))} have the same weight "
                            f"{weight}; a route is picked by weight, so each needs its own"))
    return out


def _hit_policies(state):
    out = []
    for set_id, rule_set in (state["config"].get("rules") or {}).items():
        if not isinstance(rule_set, dict):
            continue
        hit = rule_set.get("hit") if isinstance(rule_set.get("hit"), dict) else {}
        used = []
        for rule in (rule_set.get("rules") or {}).values():
            then = rule.get("then") if isinstance(rule, dict) else None
            used += [e for e in (then or {}) if e in spec.EFFECT_POLICIES and e not in used]
        for effect in used:
            if effect not in hit:
                path = f"rules.{set_id}.hit.{effect}"
                out.append(_finding("resolved", "M-HIT-MISSING", _layer_of(state, path),
                                    path, f"the rule set uses {effect} but names no hit "
                                    f"policy for it; it allows "
                                    f"{', '.join(spec.EFFECT_POLICIES[effect])}"))
        for effect, policy in hit.items():
            allowed = spec.EFFECT_POLICIES.get(effect)
            if allowed is None or policy not in allowed:
                path = f"rules.{set_id}.hit.{effect}"
                what = (f"{effect} allows {', '.join(allowed)}" if allowed
                        else f"{effect} is not an effect a rule can have")
                out.append(_finding("resolved", "M-HIT-DISALLOWED", _layer_of(state, path),
                                    path, f"'{policy}' is not allowed: {what}"))
    return out


def _cycles(state):
    graph = {i: [d for d in (e.get("depends_on") or []) if isinstance(d, str)]
             for i, e in (state["config"].get("artifacts") or {}).items()
             if isinstance(e, dict) and isinstance(e.get("depends_on") or [], list)}
    seen, out, reported = set(), [], set()

    def walk(node, trail):
        if node in trail:
            cycle = trail[trail.index(node):]
            key = frozenset(cycle)
            if key not in reported:
                reported.add(key)
                first = min(cycle)
                turn = cycle.index(first)
                ring = cycle[turn:] + cycle[:turn]
                path = f"artifacts.{first}.depends_on"
                out.append(_finding("resolved", "M-CYCLE", _layer_of(state, path), path,
                                    "artifacts depend on each other in a cycle: "
                                    + " -> ".join(ring + [first])))
            return
        if node in seen or node not in graph:
            return
        for nxt in graph[node]:
            walk(nxt, trail + [node])
        seen.add(node)

    for node in sorted(graph):
        walk(node, [])
    return out


def _effect_targets(state):
    """The ids a rule's effects name, checked against the catalogue each
    effect points at (`EFFECT_TARGETS`), and the keys of a `then:` that are
    neither an effect nor a qualifier (a misspelt effect would be ignored)."""
    out, config = [], state["config"]
    for set_id, rule_set in (config.get("rules") or {}).items():
        rules = rule_set.get("rules") if isinstance(rule_set, dict) else None
        for rule_id, rule in (rules.items() if isinstance(rules, dict) else ()):
            then = rule.get("then") if isinstance(rule, dict) else None
            for key, value in (then.items() if isinstance(then, dict) else ()):
                path = f"rules.{set_id}.rules.{rule_id}.then.{key}"
                target = spec.EFFECT_TARGETS.get(key)
                if key not in spec.EFFECT_POLICIES and key not in spec.EFFECT_QUALIFIERS:
                    out.append(_finding("resolved", "M-EFFECT-UNKNOWN", _layer_of(state, path),
                                        path, f"{key} is not an effect a rule can have, nor "
                                        f"a qualifier ({', '.join(spec.EFFECT_QUALIFIERS)})"))
                elif target:
                    known = config.get(target) or {}
                    missing = [v for v in (value if isinstance(value, list) else [value])
                               if isinstance(v, str) and v not in known]
                    if missing:
                        out.append(_finding("resolved", "M-REF-UNKNOWN",
                                            _layer_of(state, path), path,
                                            f"names {', '.join(missing)}, which {target} "
                                            f"does not define"))
    return out


def _resolved_group(state):
    out = _unknown_references(state) + _effect_targets(state)
    out += _weight_ties(state) + _hit_policies(state)
    out += [_finding("resolved", code, _layer_of(state, path), path, message)
            for code, path, message in catalogue_check.check_vocabulary(state["config"])]
    return out + _cycles(state)


EVALUATOR_LEAD = "the evaluator cannot read the configuration: "
EVALUATOR_TAIL = ". An unlock cannot help; fix the configuration"
EVALUATION_PATH = "configuration"


def _evaluation_finding(group, layer, message):
    """The one finding for a configuration the evaluator rejects. The lock
    refusal that says the same thing is turned into this, so a project that
    fixes the fault sees one line go, not two."""
    if EVALUATOR_LEAD in message:
        message = message.split(EVALUATOR_LEAD, 1)[1]
        message = message[:-len(EVALUATOR_TAIL)] if message.endswith(EVALUATOR_TAIL) \
            else message
    return _finding(group, "E-EVALUATION", layer, EVALUATION_PATH,
                    f"the evaluator cannot read the configuration: {message}")


def _lock_finding(refusal, layer):
    prefix = f"{refusal.layer} layer: "
    message = refusal.message[len(prefix):] if refusal.message.startswith(prefix) \
        else refusal.message
    if refusal.entry == "configuration":
        if refusal.field == "evaluation":
            return _evaluation_finding("locks", layer, message)
        return _finding("locks", "K-UNPROVABLE", layer, EVALUATION_PATH, message)
    if refusal.field == "unlock":
        return _finding("locks", "K-UNLOCK-REFUSED", layer, refusal.entry, message)
    return _finding("locks", "K-LOCK-REFUSED", layer, refusal.entry, message, detail={
        "field": refusal.field, "key": refusal.key, "outcome": refusal.outcome,
        "level": refusal.level, "parent": refusal.parent, "child": refusal.child,
        "where": refusal.where})


def _locks_group(state):
    """What the locks above each layer refuse. Every refusal is collected, not
    only the first."""
    try:
        result = locks.enforce_chain(state["chain"], cache=state["cache"],
                                     early_exit=False)
    except CompassError as exc:
        return [_evaluation_finding("locks", state["chain"][-1], str(exc))]
    return [_lock_finding(r, r.layer or state["chain"][-1].name) for r in result.refusals]


def _capabilities(chain):
    """The capability switches that are on after `chain`; a later layer
    overrides an earlier one."""
    state = {}
    for layer in chain:
        state.update(layer.doc.get("capabilities") or {})
    return tuple(sorted(k for k, v in state.items() if v is True))


def _refusal_path(change, parent_config, child_config):
    """The key path of the entry a classifier change belongs to. A check, gate
    or stage change is keyed by the entry's id. An approach change is keyed by
    a part of the approach (a stage, an autonomy level) or by nothing, because
    the approach is the one the assessment chose; the approaches whose value
    differs say which entry changed, and the first by id is named."""
    field, key = change.get("field") or "", change.get("key")
    head, _, rest = field.partition(".")
    if head == "approaches" and rest:
        before, after = parent_config.get("approaches") or {}, child_config.get("approaches") or {}

        def held(table, approach):
            value = (table.get(approach) or {}).get(rest)
            return value.get(key) if key and isinstance(value, dict) else value

        changed = sorted(a for a in set(before) | set(after)
                         if held(before, a) != held(after, a))
        if changed:
            return f"approaches.{changed[0]}.{rest}" + (f".{key}" if key else "")
        return field
    return f"{head}.{key}.{rest}" if key and rest else (field or EVALUATION_PATH)


def _refusal_finding(layer, refusal, parent_config, child_config):
    """`C-LOOSENING` or `C-INCOMPARABLE` for a layer the classifier refuses,
    with the first assessment it shows at, the field and both values."""
    point = refusal["point"]
    change = next((c for c in (point or {}).get("changes", ())
                   if c["outcome"] != "tighter"), None) or {}
    code = "C-LOOSENING" if refusal["result"] == "loosening" else "C-INCOMPARABLE"
    detail = {"result": refusal["result"],
              "assessment": point["assessment"] if point else None,
              "outcome": change.get("outcome"), "field": change.get("field"),
              "key": change.get("key"), "parent": change.get("parent"),
              "child": change.get("child")}
    return _finding("classification", code, layer,
                    _refusal_path(change, parent_config, child_config),
                    refusal["reason"] + "; a waiver on the entry, approved by the "
                    "layer above, excuses it", detail=detail)


def _waiver_findings(state, index, layer, parent_config, child_config):
    """`(findings, valid waivers)` for the waivers of one layer."""
    scope = "issue" if layer.kind == "issue" else "project"
    project = next((l.doc for l in state["chain"] if l.kind == "project"), None)
    # The layer above approves a waiver (ADR-039). For a git parent that is the
    # layer before it, and its own `owner` is the fallback approver, never the
    # project's.
    shipped = state["chain"][index - 1].doc
    if layer.kind == "parent":
        project = layer.doc
    found, faults = waivers.find(layer.doc, scope)
    out = [_finding("classification", f.code, layer, f.waiver_id, f.message, f.level)
           for f in faults]
    valid = []
    for waiver in found:
        described = (waivers.describe(waiver, parent_config, child_config, None)
                     if scope == "issue" else None)
        checked = waivers.check(waiver, today=state["today"], project=project,
                                parent=shipped, registry=state["registry"],
                                described=described)
        out += [_finding("classification", f.code, layer, waiver.id, f.message, f.level)
                for f in checked]
        if not any(f.level == "error" for f in checked):
            valid.append(waiver)
    return out, valid


def _vocabulary_changes(layer, parent_config, child_config):
    """A warning for each dimension whose list of values this layer changed.
    The classifier leaves a value that no predicate reads out of its grid, so
    it compares such a change as equivalent (ADR-037); a value that is gone
    still stops a stored assessment holding it from running again. That is
    reported here, on its own, so the classification does not carry it."""
    out = []
    before, after = parent_config.get("dimensions") or {}, child_config.get("dimensions") or {}
    for name in sorted(set(before) & set(after)):
        old, new = before[name].get("values"), after[name].get("values")
        if not isinstance(old, list) or not isinstance(new, list) or old == new:
            continue
        removed = [v for v in old if v not in new]
        added = [v for v in new if v not in old]
        if not (removed or added):
            continue
        said = []
        if removed:
            said.append(f"removed {', '.join(map(str, removed))}; a stored assessment "
                        f"holding it can no longer run")
        if added:
            said.append(f"added {', '.join(map(str, added))}")
        out.append(_finding("classification", "V-VOCABULARY-CHANGE", layer,
                            f"dimensions.{name}.values", f"{name}: {'; '.join(said)}",
                            "warning", {"dimension": name, "added": added,
                                        "removed": removed}))
    return out


def _classification_group(state):
    out, seen = [], set()
    chain, configs = state["chain"], state["configs"]
    for index, layer in enumerate(chain[1:], 1):
        parent_config, child_config = configs[index - 1], configs[index]
        found, valid = _waiver_findings(state, index, layer, parent_config, child_config)
        out += found + _vocabulary_changes(layer, parent_config, child_config)
        try:
            attribution = waivers.attribute(
                parent_config, child_config, valid,
                parent_capabilities=_capabilities(chain[:index]),
                child_capabilities=_capabilities(chain[:index + 1]),
                child_issue=layer.doc if layer.kind == "issue" else None,
                exhaustive=state["exhaustive"], cache=state["cache"])
        except CompassError as exc:
            if str(exc) not in seen:
                seen.add(str(exc))
                out.append(_evaluation_finding("classification", layer, str(exc)))
            continue
        if attribution.result == "refused":
            out.append(_refusal_finding(layer, attribution.refusal, parent_config,
                                        child_config))
        out += [_finding("classification", "W-UNNEEDED", layer, waiver_id,
                         "this waiver excuses nothing: the entry is no looser than the "
                         "layer above without it", "warning")
                for waiver_id in attribution.unneeded]
    return out


GROUP_RUNNERS = (("layer", _layer_group), ("merge", _merge_group),
                 ("resolved", _resolved_group), ("locks", _locks_group),
                 ("classification", _classification_group))


def _order(state, findings):
    names = [layer.name for layer in state["chain"]]
    return sorted(findings, key=lambda f: (
        names.index(f.layer) if f.layer in names else len(names), f.path, f.code,
        f.message))


def lint_chain(parent, project, issue=None, *, exhaustive=False, today=None,
               registry=(), cache=None, extra_parents=()):
    """The `Report` for a chain of layers, each a `layers.Layer` or None.
    `extra_parents` are git parents, root first, between `parent` and the
    project. `today` is the date a waiver's `approved_on` is checked against.
    `registry` is the issue's evidence records. `cache` is shared with the
    classifier across calls."""
    chain = [layer for layer in (parent, *extra_parents, project, issue) if layer is not None]
    state = {"chain": chain, "today": today or datetime.date.today(),
             "registry": tuple(registry), "exhaustive": exhaustive,
             "cache": {} if cache is None else cache}
    report = Report(layers=[(layer.name, layer.kind) for layer in chain])
    for group, run in GROUP_RUNNERS:
        found = _order(state, run(state))
        report.findings += found
        if any(f.level == "error" for f in found):
            report.stopped_after = group
            break
    return report


def lint_loaded(loaded, **kwargs):
    """`lint_chain` over what `load_layers` read. A layer that did not load
    ends the lint at the first group."""
    if loaded.findings:
        named = [(loaded.parent.name, loaded.parent.kind)]
        named += [loaded.failed] if loaded.failed else []
        named += [(layer.name, layer.kind) for layer in (loaded.project, loaded.issue) if layer]
        named = list(dict.fromkeys(named))      # a project that loaded but was refused
        return Report(layers=named,
                      findings=loaded.warnings + loaded.findings, stopped_after="layer")
    report = lint_chain(loaded.parent, loaded.project, loaded.issue,
                        registry=loaded.registry,
                        extra_parents=[p.layer for p in loaded.git_parents], **kwargs)
    report.findings = loaded.warnings + report.findings
    return report


# --- the effective view ------------------------------------------------------------------

@dataclass
class Row:
    path: str
    value: object
    source: str
    op: str
    waiver: object = None
    note: object = None


@dataclass
class Effective:
    layers: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    issue: object = None


# The stage lists a capability switches on: until it is on, the evaluator
# reads them and nothing blocks on them, so the view says so.
INACTIVE_UNTIL = {("stages", "entry"): "entry-exit-evaluation",
                  ("stages", "exit"): "entry-exit-evaluation"}


def _label(layer, meta):
    if layer.kind == "parent" and meta:
        return f"{meta.get('id', layer.name)}@{meta.get('version', '')}"
    return layer.name


def _waiver_record(waiver):
    body = waiver.body if isinstance(waiver.body, dict) else {}
    given = body.get("approved_on")
    return {"id": waiver.id, "scope": waiver.scope,
            "approved_by": body.get("approved_by"),
            "approved_on": given.isoformat() if hasattr(given, "isoformat")
            else (str(given) if given is not None else None)}


def _waived_fields(chain):
    """`{(layer name, catalogue, entry, field): waiver record}`."""
    out = {}
    for layer in chain:
        if layer.kind == "parent":
            continue
        found, _ = waivers.find(layer.doc, "issue" if layer.kind == "issue" else "project")
        for waiver in found:
            for name in waiver.fields:
                out[(layer.name, waiver.catalogue, waiver.entry, name)] = _waiver_record(waiver)
    return out


def _top_rows(chain, labels):
    """The rows for `capabilities`, `owner` and `approvers`: each name takes
    the value of the last layer that holds it. `labels` maps a layer name to
    the source shown."""
    def gather(section):
        held = {}
        for layer in chain:
            value = layer.doc.get(section)
            if isinstance(value, dict):
                for name, item in value.items():
                    held[name] = (item, layer, "set" if name in held else "add")
        return [Row(f"{section}.{name}", item, labels[layer.name], op)
                for name, (item, layer, op) in sorted(held.items())]

    owner = None
    for layer in chain:
        if "owner" in layer.doc:
            owner = Row("owner", layer.doc["owner"], labels[layer.name],
                        "set" if owner else "add")
    return gather("capabilities") + ([owner] if owner else []) + gather("approvers")


def resolve_effective(parent, project, issue=None, *, meta=None, slug=None,
                      git_parents=()):
    """The `Effective` view of a chain: every resolved field with its value,
    the layer that wrote it and how, and the waiver that excuses it.
    `git_parents` are `parents.Parent`s, root first, between `parent` and the
    project; each is its own source. A chain that does not load or merge
    cannot be resolved, so it raises `CompassError` and points to
    `policy lint`."""
    chain = [layer for layer in (parent, *[p.layer for p in git_parents], project, issue)
             if layer is not None]
    versions = {p.layer.name: p.version or None for p in git_parents}
    state = {"chain": chain, "today": datetime.date.today()}
    problems = _layer_group(state) or _merge_group(state)
    if problems:
        first = problems[0]
        raise CompassError(
            f"nothing can be resolved: {first.code} [{first.layer}] {first.path}: "
            f"{first.message} ({len(problems)} problem(s); run compass policy lint)")
    labels = {layer.name: layer.name if layer.name in versions else _label(layer, meta)
              for layer in chain}
    waived = _waived_fields(chain)
    rows = _top_rows(chain, labels)
    on = {r.path.split(".", 1)[1] for r in rows
          if r.path.startswith("capabilities.") and r.value is True}
    held = locks.lock_set(chain)
    for catalogue in spec.CATALOGUES:
        for entry_id, entry in sorted((state["config"].get(catalogue) or {}).items()):
            for name in spec.FIELDS[catalogue]:
                # A lock is read from the layers, not from the merged entry: the
                # merge keeps `locked` only on checks and gates, and keeps it
                # after an unlock lifts it.
                if name not in entry or name == "locked":
                    continue
                path = f"{catalogue}.{entry_id}.{name}"
                written = (state["provenance"].get(path)
                           or state["provenance"].get(f"{catalogue}.{entry_id}")
                           or {"layer": chain[0].name, "operation": "add"})
                needs = INACTIVE_UNTIL.get((catalogue, name))
                rows.append(Row(
                    path, entry[name], labels[written["layer"]], written["operation"],
                    waived.get((written["layer"], catalogue, entry_id, name)),
                    f"inactive: {needs} off" if needs and needs not in on else None))
            lock = held.get(f"{catalogue}.{entry_id}")
            if lock:
                kind = next(l.kind for l in chain if l.name == lock.layer)
                rows.append(Row(f"{catalogue}.{entry_id}.locked", lock.level,
                                labels[lock.layer], "add" if kind == "parent" else "set"))
    return Effective(
        layers=[{"name": l.name, "kind": l.kind,
                 "version": versions[l.name] if l.name in versions
                 else (meta or {}).get("version") if l.kind == "parent" else None,
                 "digest": l.digest} for l in chain],
        rows=rows, issue=slug)


def _show(value, limit=44):
    text = value if isinstance(value, str) else json.dumps(
        value, default=str, ensure_ascii=False, separators=(", ", ": "))
    return text if len(text) <= limit else text[:limit - 3] + "..."


def _source_text(row):
    said = row.op
    if row.waiver:
        who = row.waiver["approved_by"]
        said += (f", waiver by {who}, {row.waiver['approved_on']}"
                 if row.waiver["scope"] == "project" else f", waiver {who}")
    return f"{row.source} ({said})" + (f"  ({row.note})" if row.note else "")


def effective_json(effective):
    """The view as the documented dictionary."""
    return {
        "schema": JSON_SCHEMA_VERSION,
        "scope": {"kind": "issue" if effective.issue else "project",
                  "issue": effective.issue, "resolved": "live"},
        "layers": [dict(layer) for layer in effective.layers],
        "fields": [{"path": r.path, "value": r.value, "source": r.source, "op": r.op,
                    "waiver": r.waiver, "note": r.note} for r in effective.rows],
    }


def effective_text(effective):
    scope = f"issue {effective.issue}" if effective.issue else "project"
    names = [l["name"] if l["version"] is None else f"{l['name']}@{l['version']}"
             for l in effective.layers]
    lines = [f"compass policy effective: {scope} - layers: {', '.join(names)}",
             "  This is what the configuration resolves to. compass check and the "
             "evaluator still read the legacy governance files until the generation "
             "store lands."]
    if effective.issue:
        lines.append("  Resolved from the live project file; no generation is stored yet.")
    width = min(max((len(r.path) for r in effective.rows), default=0), 56)
    shown = [_show(r.value) for r in effective.rows]
    value_width = max((len(s) for s in shown), default=0)
    lines += [f"{r.path:<{width}}  {text:<{value_width}}  {_source_text(r)}"
              for r, text in zip(effective.rows, shown)]
    return lines


# --- the legacy view ---------------------------------------------------------------------

_LEGACY_FILE = re.compile(r"^(?:\[([^\]]+)\]|([\w.-]+\.yml):) ")


def _legacy_split(text):
    """`(file, message)` from a legacy error line that starts `[file]` or
    `file.yml:`, or `("", text)`."""
    found = _LEGACY_FILE.match(text)
    return ((found.group(1) or found.group(2)), text[found.end():]) if found else ("", text)


def legacy_report(errors, drift=None, strict=False):
    """The `Report` for a project with no `compass.yml`, from the legacy
    lint's error lines and its drift report (`governance.DriftReport`). The
    drift is only looked at when the structure is clean, as the printed lint
    does. Drift is a warning, and an error when the project makes it strict."""
    level = "error" if strict else "warning"
    out = []
    for text in errors:
        path, message = _legacy_split(text)
        out.append(Finding("LEGACY-STRUCTURE", "error", "legacy", path, "legacy", message))
    if not errors and drift is not None and not drift.same_dir:
        if not drift.comparable:
            out.append(Finding("LEGACY-DRIFT-UNCOMPARED", "warning", "legacy", "",
                               "legacy", f"could not compare against the framework's "
                               f"governance: {drift.reason}"))
        else:
            out += [Finding("LEGACY-WAIVER", "error", "legacy", "", "legacy", text)
                    for text in drift.waiver_errors]
            out += [Finding("LEGACY-WAIVED", "info", "legacy", rule_id, "legacy",
                            f"waived by this project, a recorded decision and not drift: "
                            f"{reason}")
                    for rule_id, reason in drift.waived]
            out += [Finding("LEGACY-DRIFT", level, "legacy", f"{name}:{rule_id}", "legacy",
                            f"project governance is missing the {kind} {rule_id} the "
                            f"framework ships")
                    for name, rule_id, kind in drift.missing_rules]
            out += [Finding("LEGACY-DRIFT", level, "legacy", f"{name}:{check}", "legacy",
                            f"project governance is missing the check {check} the "
                            f"framework ships")
                    for name, check in drift.missing_checks]
    out.sort(key=lambda f: (f.path, f.code, f.message))
    return Report(mode="legacy", layers=[("legacy", "legacy")], findings=out,
                  stopped_after="legacy" if errors else None)


# --- rendering --------------------------------------------------------------------------

def lint_json(report):
    """The report as the documented dictionary."""
    return {
        "schema": JSON_SCHEMA_VERSION,
        "mode": report.mode,
        "result": "pass" if report.ok else "fail",
        "layers": [{"name": n, "kind": k} for n, k in report.layers],
        "stopped_after": report.stopped_after,
        "counts": {"errors": len(report.errors), "warnings": len(report.warnings)},
        "findings": [{"code": f.code, "level": f.level, "layer": f.layer,
                      "path": f.path, "group": f.group, "message": f.message,
                      "detail": f.detail} for f in report.findings],
    }


def lint_text(report):
    lines = ["compass policy lint: " + ("PASS" if report.ok else "FAIL")]
    for f in report.findings:
        mark = f"{f.level} " if f.level != "error" else ""
        lines.append(f"  - {mark}{f.code} [{f.layer}] {f.path}: {f.message}")
    return lines


def dumps(document):
    return json.dumps(document, indent=2, default=str)
