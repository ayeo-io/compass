# compass_pkg.settings_lint - lint compass.yml as a file of settings
"""The lint of `compass.yml` once Compass runs one fixed set of checks (ADR-094).

`compass.yml` holds settings and nothing else. The settings in `PLAIN_KEYS`
do not touch the check set. The settings in `catalogue_spec.TIGHTEN_KEYS`
only add to it, and `compass_pkg.tighten` applies them. This module:

- `lint(doc, base)` returns every finding for one `compass.yml`, as
  `Finding(code, level, path, message)`. It refuses a key the file cannot
  hold, a malformed value and a tighten-only value that is not one of the
  shapes that add. It warns about a key 9.0.0 removed, which is read as if
  absent. With `base`, the resolved check set, it also refuses a project
  check that reuses a shipped id and an assessment value the check set does
  not declare, and runs the integrity rule.
- `integrity(resolved)` is the integrity rule of safety-contract guarantee 2:
  every check names an implementation the CLI holds.
- `value_problems(doc, base)` is the shape check of the tighten-only
  settings.
- `schema()` builds the JSON Schema of `compass.yml` from the same keys, so
  the two cannot drift. `schemas/compass.schema.json` is generated from it,
  and a test keeps the two equal.

`compass policy lint` runs `lint` on `compass.yml`, and `effective.resolve_live`
runs it first and resolves nothing when it finds an error.
"""
# DEPENDENCY: standard library (dataclasses, re, types); compass_pkg.acceptance_strategy,
# compass_pkg.catalogue_spec, compass_pkg.check_registry (REGISTRY, DELETED_CHECKS),
# compass_pkg.evidence_required (TOKENS), compass_pkg.language and
# compass_pkg.removed_parts.
from __future__ import annotations

import re
import types
from dataclasses import dataclass

from compass_pkg import catalogue_spec as spec
from compass_pkg import removed_parts

#: The finding codes this lint writes.
CODES = ("L-SETTING-UNKNOWN", "L-SETTING-INVALID", "L-SETTING-REMOVED", "L-PARENT-REMOVED",
         "L-IMPL-UNKNOWN")

#: The settings that do not touch the check set.
PLAIN_KEYS = ("schema", "owner", "approvers", "autonomy", "adoption", "allow_project_commands",
              "enforcement", "record", "project", "language", "governance_drift",
              "acceptance_strategy")
#: Every key `compass.yml` can hold and have read.
KEYS = PLAIN_KEYS + spec.TIGHTEN_KEYS

ADR = "ADR-094"
REASON = "Compass runs one fixed set of checks"
#: The keys ADR-094 removed: what each set. A file that holds one is read without it.
REMOVED = {
    **{catalogue: f"the {catalogue} catalog of the configuration layers"
       for catalogue in ("dimensions", "stages", "rules", "checks", "gates", "vocabulary")},
    "extends": "the preset the file built on",
    "preset": "a published preset's own data",
    "preset_index": "the index of published presets",
    "approvers.project-waiver": "who approved a waiver in the project file",
}

#: The fields of one entry of each list setting, and which are required.
REQUIRE_EVIDENCE_FIELDS = ("when", "add")
PROJECT_CHECK_FIELDS = ("id", "name", "command", "stage", "when")
PROJECT_CHECK_REQUIRED = ("id", "name", "command", "stage")
#: The id of the judged check `agent_review` turns on, which a project check
#: cannot take.
AGENT_REVIEW = "agent-review"
AGENT_REVIEW_VALUES = (True, False, "on", "off")
#: The dimensions a `when:` can name when no check set is given.
DIMENSIONS = ("risk", "familiarity", "size", "goal", "urgency", "labels")

_ID = re.compile(spec.ID_PATTERN)
_ADDS = "a tighten-only setting can only add to what an issue owes"


@dataclass(frozen=True)
class Finding:
    code: str
    level: str          # "error" or "warning"
    path: str
    message: str
    #: What replaces a removed key (`L-SETTING-REMOVED` only), from
    #: `removed_parts.REPLACEMENTS`; None when nothing does.
    replacement: str | None = None


def _error(code, path, message):
    return Finding(code, "error", path, message)


def _warning(code, path, message):
    return Finding(code, "warning", path, message)


# --- the tighten-only settings ----------------------------------------------------

def _texts(value):
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def _dimensions(base):
    """`{dimension: (type, values)}` from the check set, or the shipped names
    with no values when there is none."""
    dims = (base or {}).get("dimensions")
    if not isinstance(dims, dict):
        return {name: (None, ()) for name in DIMENSIONS}
    return {name: (body.get("type"), tuple(body.get("values") or ()))
            for name, body in dims.items() if isinstance(body, dict)}


def when_problems(path, when, base=None):
    """The problems of one `when:` clause: the keys an assessment has, plus
    `labels_any` and `any_of`. With `base`, a value must be one the check set
    declares, because a misspelt value would match nothing and the setting
    would add nothing without a word."""
    if when is None:
        return []
    if not isinstance(when, dict):
        return [(path, "expected a mapping of assessment key to value, such as "
                       "`risk: [critical]`")]
    dims = _dimensions(base)
    out = []
    for key, value in when.items():
        where = f"{path}.{key}"
        if key == "any_of":
            if not isinstance(value, list) or not value:
                out.append((where, "expected a list of conditions"))
                continue
            for i, clause in enumerate(value):
                out += when_problems(f"{where}[{i}]", clause, base)
        elif key in ("labels", "labels_any"):
            if not (isinstance(value, str) and value.strip()) and not _texts(value):
                out.append((where, "expected a label or a list of labels"))
        elif key not in dims:
            out.append((where, f"not a key of the assessment; the keys are "
                               f"{', '.join(sorted(dims))}, labels_any and any_of"))
        else:
            kind, allowed = dims[key]
            if isinstance(value, dict) and set(value) == {"at_least"}:
                if kind != "ordered-enum" and base is not None:
                    out.append((where, f"at_least needs an ordered dimension, and {key} "
                                       f"is not one"))
                    continue
                values = [value["at_least"]]
            else:
                values = value if isinstance(value, list) else [value]
            if not values or not all(isinstance(v, str) for v in values):
                out.append((where, "expected a value or a list of values"))
            elif allowed and kind != "set":
                unknown = [v for v in values if v not in allowed]
                if unknown:
                    out.append((where, f"{', '.join(map(repr, unknown))} is not a value of "
                                       f"{key} ({', '.join(allowed)})"))
    return out


def _signoff_problems(value):
    if not _texts(value):
        return [("signoff_labels", "expected a list of label names")]
    return []


def _require_evidence_problems(value, base):
    from compass_pkg.evidence_required import TOKENS
    if not isinstance(value, list):
        return [("require_evidence", "expected a list of `{when, add}` rules")]
    out = []
    for i, entry in enumerate(value):
        path = f"require_evidence[{i}]"
        if not isinstance(entry, dict):
            out.append((path, "expected a mapping with `when` and `add`"))
            continue
        for key in entry:
            if key not in REQUIRE_EVIDENCE_FIELDS:
                out.append((f"{path}.{key}", f"not a field of a rule, which holds "
                                             f"{' and '.join(REQUIRE_EVIDENCE_FIELDS)}; "
                                             f"{_ADDS}"))
        add = entry.get("add")
        if not isinstance(add, list) or not add:
            out.append((f"{path}.add", "expected a list of one or more evidence tokens"))
        else:
            unknown = [str(t) for t in add if t not in TOKENS]
            if unknown:
                out.append((f"{path}.add", f"{', '.join(map(repr, unknown))} is not an "
                                           f"evidence token; the tokens are "
                                           f"{', '.join(TOKENS)}"))
        out += when_problems(f"{path}.when", entry.get("when"), base)
    return out


def _agent_review_problems(value):
    # `1 == True` in Python, so a number is refused before the membership test.
    numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
    if numeric or value not in AGENT_REVIEW_VALUES:
        return [("agent_review", "expected `on` (or `true`) to turn the agent review on, "
                                 "or `off` (or `false`)")]
    return []


def _shipped_ids(base):
    ids = set()
    for catalogue in ("checks", "gates"):
        held = (base or {}).get(catalogue)
        if isinstance(held, dict):
            ids |= set(held)
    return ids


def _project_check_problems(value, base):
    if not isinstance(value, list):
        return [("project_checks", "expected a list of `{id, name, command, stage}` checks")]
    from compass_pkg.check_registry import DELETED_CHECKS
    out = []
    shipped = _shipped_ids(base) | {AGENT_REVIEW}
    seen = set()
    for i, entry in enumerate(value):
        path = f"project_checks[{i}]"
        if not isinstance(entry, dict):
            out.append((path, "expected a mapping with `id`, `name`, `command` and `stage`"))
            continue
        for key in entry:
            if key not in PROJECT_CHECK_FIELDS:
                out.append((f"{path}.{key}", f"not a field of a project check, which holds "
                                             f"{', '.join(PROJECT_CHECK_FIELDS)}; {_ADDS}"))
        for key in PROJECT_CHECK_REQUIRED:
            if key not in entry:
                out.append((f"{path}.{key}", "required"))
        check_id = entry.get("id")
        if "id" in entry:
            if not isinstance(check_id, str) or not _ID.match(check_id):
                out.append((f"{path}.id", f"expected an id matching {spec.ID_PATTERN}"))
            elif check_id in shipped:
                out.append((f"{path}.id", f"'{check_id}' is the id of a shipped check or "
                                          f"gate; a project check adds one of its own"))
            elif check_id in DELETED_CHECKS:
                out.append((f"{path}.id", f"'{check_id}' is the id of a check Compass "
                                          f"deleted; compass check refuses a project "
                                          f"check of that id, so give it another id"))
            elif check_id in seen:
                out.append((f"{path}.id", f"'{check_id}' is the id of an earlier project "
                                          f"check"))
            else:
                seen.add(check_id)
        for key in ("name", "command"):
            if key in entry and not (isinstance(entry[key], str) and entry[key].strip()):
                out.append((f"{path}.{key}", "expected text"))
        if "stage" in entry and entry["stage"] not in spec.PROJECT_CHECK_STAGES:
            out.append((f"{path}.stage", f"'{entry['stage']}' is not one of "
                                         f"{', '.join(spec.PROJECT_CHECK_STAGES)}"))
        out += when_problems(f"{path}.when", entry.get("when"), base)
    return out


def _capability_problems(value):
    if not isinstance(value, dict):
        return [("capabilities", "expected a mapping of capability to true or false")]
    out = []
    for name, on in value.items():
        if name in removed_parts.CAPABILITIES:
            continue        # removed: named by the L-SETTING-REMOVED warning, not read
        if name != "entry-exit-evaluation":
            out.append((f"capabilities.{name}", "not a capability a project can turn on; "
                                                "the one capability is entry-exit-evaluation"))
        elif not isinstance(on, bool):
            out.append((f"capabilities.{name}", "expected true or false"))
    return out


def value_problems(doc, base=None):
    """`(path, message)` for each tighten-only setting of `doc` whose value is
    not a shape that adds. `base`, the resolved check set, also refuses a
    project check that reuses a shipped id and an assessment value the set
    does not declare. `capabilities: {entry-exit-evaluation: false}` and
    `agent_review: off` are the defaults, so they are accepted and change
    nothing."""
    if not isinstance(doc, dict):
        return []
    out = []
    if "signoff_labels" in doc:
        out += _signoff_problems(doc["signoff_labels"])
    if "require_evidence" in doc:
        out += _require_evidence_problems(doc["require_evidence"], base)
    if "agent_review" in doc:
        out += _agent_review_problems(doc["agent_review"])
    if "project_checks" in doc:
        out += _project_check_problems(doc["project_checks"], base)
    if "capabilities" in doc:
        out += _capability_problems(doc["capabilities"])
    return out


# --- the integrity rule ------------------------------------------------------------

def integrity(resolved):
    """`(path, message)` for each check of a resolved configuration that names
    an implementation the CLI does not hold, or is deterministic and names
    none. A check the CLI cannot run must not reach `compass check`, where it
    would pass by default (safety-contract guarantee 2)."""
    from compass_pkg.check_registry import REGISTRY
    out = []
    for check_id, check in ((resolved or {}).get("checks") or {}).items():
        if not isinstance(check, dict):
            continue
        impl = check.get("impl")
        if impl is None and check.get("kind") != "deterministic":
            continue
        if impl not in REGISTRY:
            out.append((f"checks.{check_id}.impl",
                        f"impl '{impl}' is not in the check registry "
                        f"({', '.join(sorted(REGISTRY))})"))
    return out


# --- the lint ------------------------------------------------------------------------

def _git_parent(extends):
    ref = extends.get("from") if isinstance(extends, dict) else extends
    return isinstance(ref, str) and ref.startswith(removed_parts.GIT_PARENT_SCHEME)


def _pinned_below(extends):
    """True when `extends:` pins the shipped default below the first major that
    carries the acceptance strategy (`acceptance_strategy.pinned_below`)."""
    from compass_pkg import acceptance_strategy
    ref = extends.get("from") if isinstance(extends, dict) else extends
    found = re.fullmatch(r"compass:default@(\d+)", ref) if isinstance(ref, str) else None
    return bool(found) and int(found.group(1)) < acceptance_strategy.FIRST_MAJOR


def _removed_findings(doc):
    out = []
    for key, what in REMOVED.items():
        top, _, sub = key.partition(".")
        held = doc.get(top)
        if sub and not (isinstance(held, dict) and sub in held):
            continue
        if not sub and top not in doc:
            continue
        if key == "extends" and _git_parent(held):
            out.append(_error("L-PARENT-REMOVED", key,
                              f"a git parent was removed in {removed_parts.RELEASE} ({ADR}): "
                              f"{REASON}; a team parent can hold checks this file does not "
                              f"show, so nothing is resolved until it is deleted. "
                              f"{removed_parts.GIT_PARENT_FIX}"))
            continue
        reason = REASON
        if key == "extends" and _pinned_below(held):
            # ADR-094 open question 7: the pin keeps the owner decision of
            # 2026-10-30 until `compass migrate` writes `acceptance_strategy: off`
            # in its place (ADR-098 decision 6).
            reason = (f"{REASON}; only its pin below @8 is read, and it keeps the "
                      f"acceptance strategy `S17` off")
        out.append(Finding("L-SETTING-REMOVED", "warning", key,
                           removed_parts.removed_message(key, what, ADR, reason, held),
                           removed_parts.replacement_text(key, held)))
    named = {f.path for f in out}
    # The 9.0.0 removals of earlier decision records, unless a whole key above
    # already names the key that holds them.
    project = types.SimpleNamespace(kind="project", name="project", doc=doc)
    for _layer, path, message in removed_parts.setting_findings([project]):
        if path.split(".", 1)[0] not in named:
            out.append(Finding("L-SETTING-REMOVED", "warning", path, message,
                               removed_parts.replacement_text(path)))
    return out


def _plain_problems(doc):
    """`(path, message)` for each malformed value of a setting in `PLAIN_KEYS`
    that has a closed set of values or a shape of its own."""
    from compass_pkg import acceptance_strategy, language
    out = [(key, f"'{doc[key]}' is not one of {', '.join(allowed)}")
           for key, allowed in (("autonomy", spec.AUTONOMY), ("adoption", spec.ADOPTION))
           if key in doc and doc[key] not in allowed]
    if "language" in doc:
        text = language.problem(doc["language"])
        if text:
            out.append(("language", text))
    if "acceptance_strategy" in doc:
        text = acceptance_strategy.problem(doc["acceptance_strategy"])
        if text:
            out.append(("acceptance_strategy", text))
    record = doc.get("record")
    if isinstance(record, dict) and "commit" in record \
            and not isinstance(record["commit"], bool):
        out.append(("record.commit", f"'{record['commit']}' is not true or false"))
    approvers = doc.get("approvers")
    if approvers is not None:
        if not isinstance(approvers, dict):
            out.append(("approvers", "expected a mapping of approver list by kind"))
        else:
            out += [(f"approvers.{kind}", f"not an approver list; the lists are "
                     f"{', '.join(spec.APPROVER_KINDS)} (ADR-039)")
                    for kind in approvers if kind not in spec.APPROVER_KINDS]
    return out


def _removed_top_keys():
    return {key for key in REMOVED if "." not in key} | {
        key for key in removed_parts.SETTINGS if "." not in key}


def lint(doc, base=None):
    """Every finding for one `compass.yml`, errors first in file order, then
    warnings. `base` is the resolved check set; without it the checks that
    need it (a clash with a shipped id, an assessment value, the integrity
    rule) do not run."""
    if not isinstance(doc, dict):
        return [_error("L-SETTING-INVALID", "(top level)",
                       f"expected a mapping, found {type(doc).__name__}")]
    removed = _removed_top_keys()
    findings = []
    for key in doc:
        if key not in KEYS and key not in removed:
            findings.append(_error("L-SETTING-UNKNOWN", str(key),
                                   "not a setting compass.yml can hold"))
    plain = {k: v for k, v in doc.items() if k in PLAIN_KEYS}
    if isinstance(plain.get("approvers"), dict):
        plain["approvers"] = {k: v for k, v in plain["approvers"].items()
                              if k != "project-waiver"}
    findings += [_error("L-SETTING-INVALID", path, message)
                 for path, message in _plain_problems(plain)]
    if "owner" in doc and not (isinstance(doc["owner"], str) and doc["owner"].strip()):
        findings.append(_error("L-SETTING-INVALID", "owner", "expected a person's name"))
    findings += [_error("L-SETTING-INVALID", path, message)
                 for path, message in value_problems(doc, base)]
    findings += _removed_findings(doc)
    if base is not None and not any(f.level == "error" for f in findings):
        from compass_pkg import tighten
        applied = tighten.apply(base, tighten.settings_of(doc))
        findings += [_error("L-IMPL-UNKNOWN", path, message)
                     for path, message in integrity(applied)]
    return sorted(findings, key=lambda f: f.level != "error")


# --- the schema ------------------------------------------------------------------------

def schema_properties():
    """The JSON Schema of the four tighten-only keys that are not layer keys,
    each node described from `catalogue_spec.TOP_DESCRIPTIONS`. The fifth,
    `capabilities`, is a layer key and keeps its own node."""
    from compass_pkg.evidence_required import TOKENS
    top = spec.TOP_DESCRIPTIONS

    def text(key):
        return {"description": top[key]}

    def when(key):
        return {**text(key), "type": "object"}

    return {
        "signoff_labels": {**text("signoff_labels"), "type": "array",
                           "items": {**text("signoff_labels.item"), "type": "string",
                                     "minLength": 1}},
        "require_evidence": {**text("require_evidence"), "type": "array", "items": {
            **text("require_evidence.item"), "type": "object",
            "properties": {
                "when": when("require_evidence.when"),
                "add": {**text("require_evidence.add"), "type": "array", "minItems": 1,
                        "items": {**text("require_evidence.token"), "enum": list(TOKENS)}}},
            "required": ["add"], "additionalProperties": False}},
        "agent_review": {**text("agent_review"), "oneOf": [
            {**text("agent_review.switch"), "type": "boolean"},
            {**text("agent_review.word"), "enum": ["on", "off"]}]},
        "project_checks": {**text("project_checks"), "type": "array", "items": {
            **text("project_checks.item"), "type": "object",
            "properties": {
                "id": {**text("project_checks.id"), "type": "string",
                       "pattern": spec.ID_PATTERN},
                "name": {**text("project_checks.name"), "type": "string", "minLength": 1},
                "command": {**text("project_checks.command"), "type": "string",
                            "minLength": 1},
                "stage": {**text("project_checks.stage"),
                          "enum": list(spec.PROJECT_CHECK_STAGES)},
                "when": when("project_checks.when")},
            "required": list(PROJECT_CHECK_REQUIRED), "additionalProperties": False}},
    }


def schema():
    """The JSON Schema of `compass.yml`: the keys of `KEYS` and nothing else, so
    an editor marks a removed setting as one the file cannot hold. Every node
    carries a description from `catalogue_spec.TOP_DESCRIPTIONS`.
    `schemas/compass.schema.json` is this, written with
    `json.dumps(schema(), indent=2, sort_keys=True)`."""
    from compass_pkg import acceptance_strategy
    top = spec.TOP_DESCRIPTIONS
    approvers = [kind for kind in spec.APPROVER_KINDS if f"approvers.{kind}" not in REMOVED]
    capabilities = [name for name in spec.CAPABILITIES
                    if name not in removed_parts.CAPABILITIES]
    properties = {
        "schema": {"description": top["schema"], "type": "integer"},
        "owner": {"description": top["owner"], "type": "string"},
        "approvers": {"description": top["approvers"], "type": "object",
                      "properties": {k: {"description": top[f"approvers.{k}"],
                                         "type": "array"} for k in approvers},
                      "additionalProperties": False},
        "autonomy": {"description": top["autonomy"], "enum": list(spec.AUTONOMY)},
        "adoption": {"description": top["adoption"], "enum": list(spec.ADOPTION)},
        "allow_project_commands": {"description": top["allow_project_commands"],
                                   "type": "boolean"},
        "enforcement": {"description": top["enforcement"], "type": "object"},
        "record": {"description": top["record"], "type": "object", "properties": {
            "commit": {"description": top["record.commit"], "type": "boolean"}}},
        "project": {"description": top["project"], "type": "object", "properties": {
            "acceptance_support": {
                "description": top["project.acceptance_support"], "type": "object",
                "properties": {k: {"description": top[f"project.acceptance_support.{k}"],
                                   "type": "string"} for k in spec.ACCEPTANCE_SUPPORT},
                "additionalProperties": False}}},
        "language": {"description": top["language"], "type": "string"},
        "governance_drift": {"description": top["governance_drift"],
                             "enum": list(spec.GOVERNANCE_DRIFT)},
        "acceptance_strategy": {
            "description": top["acceptance_strategy"], "type": "object",
            "properties": {
                "state": {"description": top["acceptance_strategy.state"],
                          "enum": list(acceptance_strategy.STATES)},
                "reason": {"description": top["acceptance_strategy.reason"],
                           "type": "string"}},
            "required": ["state"], "additionalProperties": False},
        "capabilities": {"description": top["capabilities"], "type": "object",
                         "properties": {c: {"description": top[f"capabilities.{c}"],
                                            "type": "boolean"} for c in capabilities},
                         "additionalProperties": False},
        **schema_properties(),
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "compass.yml",
        "description": top[""],
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
