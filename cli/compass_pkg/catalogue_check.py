# compass_pkg.catalogue_check - check a layer file against the field table
"""Structural checks of a configuration layer, with no `jsonschema` needed.

A layer is one source of configuration: a project's `compass.yml`, a parent
it extends, or an issue's own `config:`. `check_layer` refuses what the
field table in `catalogue_spec` does not allow, naming the key path, so a
typo is caught before anything merges it. It always runs, because
`jsonschema` is optional, so it checks at least what the schema checks:
keys, field types, the enumerations, the operations each layer may use, and
`at_least:` thresholds. `schema()` builds the JSON Schema for `compass.yml`
from the same table; the committed copy in `schemas/` is generated from it
and a test keeps the two equal.

`check_vocabulary` is the one check on a resolved configuration here: it
refuses a vocabulary key that names nothing and a name or alias that two
entries share.

What this does not check yet: whether an entry is complete enough to add
(the merge), and whether a value loosens its parent (the classifier).
"""
# DEPENDENCY: standard library (copy, datetime, re); compass_pkg.catalogue_spec;
# compass_pkg.vocabulary. It does not import compass_pkg.waivers: the list of
# modules that may is pinned, so the one date reader it needs is written here.
from __future__ import annotations

import copy
import datetime
import re

from compass_pkg import catalogue_spec as spec
from compass_pkg import vocabulary

_ID = re.compile(spec.ID_PATTERN)

# The enumerated values of particular fields, by catalogue and field.
_ENUMS = {
    ("checks", "kind"): spec.CHECK_KINDS,
    ("checks", "severity"): spec.SEVERITIES,
    ("checks", "on_skipped"): spec.ON_SKIPPED,
    ("checks", "locked"): spec.LOCKS,
    ("gates", "kind"): spec.GATE_KINDS,
    ("gates", "locked"): spec.LOCKS,
    ("dimensions", "type"): spec.DIMENSION_TYPES,
    ("dimensions", "tighter"): spec.TIGHTER,
}
_SETTINGS_ENUMS = {"autonomy": spec.AUTONOMY, "adoption": spec.ADOPTION}


def check_layer(doc, layer):
    """Every structural problem in `doc`, as text naming its key path.
    `layer` is `project`, `parent` or `issue`. Empty means well formed."""
    if not isinstance(doc, dict):
        return [f"{layer} layer: expected a mapping, found {type(doc).__name__}"]
    errors = []
    allowed = _allowed_top_level(layer)
    for key in doc:
        if key == "unlocks":
            errors.append("unlocks: not allowed at the top level; an unlock sits in "
                          "the entry it lifts, in the project file only (ADR-039)")
        elif layer == "parent" and key in spec.SETTINGS_KEYS:
            errors.append(f"{key}: a settings key belongs in the project's own "
                          f"compass.yml, never in a parent (ADR-043)")
        elif key not in allowed:
            errors.append(f"{key}: not a key a {layer} layer can hold")
    errors += _check_top_values(doc)
    ordered = _ordered_dimensions(doc)
    for catalogue in spec.CATALOGUES:
        if catalogue in doc and catalogue in allowed:
            errors += _check_catalogue(catalogue, doc[catalogue], ordered, layer)
    return errors


def _allowed_top_level(layer):
    if layer == "issue":
        return set(spec.ISSUE_KEYS)
    keys = set(spec.LAYER_KEYS) | set(spec.RESERVED_KEYS)
    if layer == "project":
        keys |= set(spec.SETTINGS_KEYS)
    return keys


def _date(value):
    """A date from a date or an ISO date string, or None. The same reading as the
    waiver check gives an `approved_on`."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            return None
    return None


EXTENDS_MAP_KEYS = ("from", "approved_by", "approved_on")


def _check_extends_map(extends):
    """The problems in the map form of `extends:`. The string form is checked
    where the parent is resolved, so a string is not looked at here. The map
    holds `from` (text, required) and the approval of a parent that loosens
    the default: `approved_by` (text) and `approved_on` (text or a date)."""
    if not isinstance(extends, dict):
        return []
    errors = [f"extends.{key}: not a key of the map form; it holds "
              f"{', '.join(EXTENDS_MAP_KEYS)}" for key in extends if key not in EXTENDS_MAP_KEYS]
    if not isinstance(extends.get("from"), str):
        errors.append("extends.from: the map form needs the parent as text, written as the "
                      "string form is")
    if "approved_by" in extends and not isinstance(extends["approved_by"], str):
        errors.append("extends.approved_by: expected text")
    if "approved_on" in extends:
        given = _date(extends["approved_on"])
        if given is None:
            errors.append("extends.approved_on: expected a date written YYYY-MM-DD")
        elif given > datetime.date.today():
            errors.append(f"extends.approved_on: {given.isoformat()} is later than today")
    return errors


def _check_top_values(doc):
    errors = []
    for key, allowed in _SETTINGS_ENUMS.items():
        if key in doc and doc[key] not in allowed:
            errors.append(f"{key}: '{doc[key]}' is not one of {', '.join(allowed)}")
    caps = doc.get("capabilities")
    if caps is not None:
        if not isinstance(caps, dict):
            errors.append("capabilities: expected a mapping of capability to true or false")
        else:
            for name, value in caps.items():
                if name not in spec.CAPABILITIES:
                    errors.append(f"capabilities.{name}: not a capability; the "
                                  f"capabilities are {', '.join(spec.CAPABILITIES)}")
                elif not isinstance(value, bool):
                    errors.append(f"capabilities.{name}: expected true or false")
    errors += _check_extends_map(doc.get("extends"))
    if "preset" in doc and not isinstance(doc["preset"], dict):
        errors.append("preset: expected a mapping; Compass reserves the key and reads "
                      "nothing from it")
    approvers = doc.get("approvers")
    if approvers is not None:
        if not isinstance(approvers, dict):
            errors.append("approvers: expected a mapping of approver list by kind")
        else:
            for kind in approvers:
                if kind not in spec.APPROVER_KINDS:
                    errors.append(f"approvers.{kind}: not an approver list; the lists "
                                  f"are {', '.join(spec.APPROVER_KINDS)} (ADR-039)")
    return errors


def _ordered_dimensions(doc):
    """The ordered dimensions `at_least:` may name, with their values: the
    shipped ones and any this layer declares as `ordered-enum`."""
    ordered = {name: list(values) for name, values in spec.SHIPPED_ORDERS.items()}
    dims = doc.get("dimensions")
    for name, entry in (dims.items() if isinstance(dims, dict) else []):
        if isinstance(entry, dict) and entry.get("type") == "ordered-enum" \
                and isinstance(entry.get("values"), list):
            ordered[name] = list(entry["values"])
    return ordered


def _check_catalogue(catalogue, entries, ordered, layer):
    if not isinstance(entries, dict):
        return [f"{catalogue}: expected a mapping keyed by id"]
    errors = []
    fields = spec.FIELDS[catalogue]
    may_use = spec.LAYER_OPERATIONS[layer]
    for entry_id, entry in entries.items():
        path = f"{catalogue}.{entry_id}"
        if not isinstance(entry_id, str) or not _ID.match(entry_id):
            errors.append(f"{path}: '{entry_id}' is not a valid id "
                          f"(a letter, then letters, digits, '.', '_' or '-')")
            continue
        if not isinstance(entry, dict):
            errors.append(f"{path}: expected a mapping")
            continue
        for key in entry:
            if key in spec.ENTRY_OPERATIONS:
                if key not in may_use:
                    errors.append(f"{path}.{key}: a {layer} layer cannot use {key}")
            elif key not in fields:
                errors.append(f"{path}.{key}: not a field of {catalogue}")
        values = {k: v for k, v in entry.items() if k in fields}
        changes = entry.get("set")
        if changes is not None:
            if not isinstance(changes, dict):
                errors.append(f"{path}.set: expected a mapping of field to value")
            else:
                for key, value in changes.items():
                    if not isinstance(key, str) or key not in fields:
                        errors.append(f"{path}.set: '{key}' is not a field of {catalogue}")
                    else:
                        values[key] = value
        errors += _check_values(catalogue, path, values, entry, fields)
        for key in ("when", "blocking_when"):
            if isinstance(values.get(key), dict):
                errors += _check_when(f"{path}.{key}", values[key], ordered)
        if catalogue == "rules" and isinstance(values.get("rules"), dict):
            for rule_id, rule in values["rules"].items():
                if isinstance(rule, dict) and isinstance(rule.get("when"), dict):
                    errors += _check_when(f"{path}.rules.{rule_id}.when",
                                          rule["when"], ordered)
    return errors


def _check_values(catalogue, path, values, entry, fields):
    errors = []
    for key, value in values.items():
        expected = fields[key]["type"]
        list_op = expected == "list" and isinstance(value, dict) \
            and set(value) <= {"add", "remove"}
        map_op = expected == "map" and isinstance(value, dict)
        if not (list_op or map_op or _is_type(value, expected)):
            errors.append(f"{path}.{key}: expected {expected.replace('-', ' ')}, "
                          f"found {value!r}")
            continue
        allowed = _ENUMS.get((catalogue, key))
        if allowed is not None and value not in allowed:
            errors.append(f"{path}.{key}: '{value}' is not one of "
                          f"{', '.join(str(a) for a in allowed)}")
    # A dimension is checked whole only when the entry defines one; an entry
    # that only changes, locks or waives an inherited one has nothing to add.
    defines = "type" in values and "set" not in entry and "remove" not in entry
    if catalogue == "dimensions" and defines and values.get("type") in spec.DIMENSION_TYPES:
        kind = values["type"]
        if kind in ("ordered-enum", "enum") and not isinstance(values.get("values"), list):
            errors.append(f"{path}.values: an {kind} lists its values")
        if kind == "ordered-enum" and values.get("tighter") not in spec.TIGHTER:
            errors.append(f"{path}.tighter: an ordered-enum says which way is "
                          f"stricter: {', '.join(spec.TIGHTER)}")
        if kind == "set" and not isinstance(values.get("open"), bool):
            errors.append(f"{path}.open: a set says whether it is open (true or false)")
    elif catalogue == "dimensions" and "set" not in entry and "remove" not in entry \
            and any(k in values for k in ("values", "tighter", "open")):
        errors.append(f"{path}.type: a dimension names its type: "
                      f"{', '.join(spec.DIMENSION_TYPES)}")
    return errors


def _is_type(value, expected):
    if expected == "string":
        return isinstance(value, str)
    if expected == "list":
        return isinstance(value, list)
    if expected == "map":
        return isinstance(value, dict)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer-or-null":
        return value is None or (isinstance(value, int) and not isinstance(value, bool))
    if expected == "boolean-or-hard":
        return value is True or value == "hard"
    return True


def _check_when(path, when, ordered):
    """`at_least:` compares by order, so it needs an ordered dimension and a
    threshold among its values; a misspelt threshold would otherwise match
    nothing and quietly turn the entry off."""
    errors = []
    for key, value in when.items():
        if key == "any_of" and isinstance(value, list):
            for i, clause in enumerate(value):
                if isinstance(clause, dict):
                    errors += _check_when(f"{path}.any_of[{i}]", clause, ordered)
        elif isinstance(value, dict) and "at_least" in value:
            if key not in ordered:
                errors.append(f"{path}.{key}: at_least needs an ordered dimension, "
                              f"and {key} is not one")
            elif value["at_least"] not in ordered[key]:
                errors.append(f"{path}.{key}: at_least '{value['at_least']}' is not a "
                              f"value of {key} ({', '.join(ordered[key])})")
    return errors


def at_least(dimension, threshold, value, orders=None):
    """Does `value` reach `threshold` on an ordered dimension? The order is
    `orders[dimension]` when given, else the shipped order of risk and size
    (ADR-035). A value or threshold outside the order never matches."""
    if orders is not None and dimension in orders:
        order = list(orders[dimension] or ())
    else:
        order = list(spec.SHIPPED_ORDERS.get(dimension) or ())
    return (threshold in order and value in order
            and order.index(value) >= order.index(threshold))


# --- the JSON Schema for compass.yml ---------------------------------------------

_JSON_TYPES = {
    "string": {"type": "string"},
    "list": {"type": "array"},
    "map": {"type": "object"},
    "integer": {"type": "integer"},
    "boolean": {"type": "boolean"},
    "integer-or-null": {"type": ["integer", "null"]},
    "boolean-or-hard": {"enum": [True, "hard"]},
}


def _field_schema(catalogue, name, field):
    text = spec.FIELD_DESCRIPTIONS[catalogue][name]
    allowed = _ENUMS.get((catalogue, name))
    if allowed is not None:
        return {"description": text, "enum": list(allowed)}
    if field["type"] == "list":
        # A list field also takes the list operations in a layer.
        lists = spec.LIST_DESCRIPTIONS
        return {"description": text, "oneOf": [
            {"description": lists["whole"], "type": "array"},
            {"description": lists["changes"], "type": "object", "properties": {
                "add": {"description": lists["add"], "type": "array"},
                "remove": {"description": lists["remove"], "type": "array"}},
             "additionalProperties": False}]}
    return {"description": text, **_JSON_TYPES[field["type"]]}


def schema():
    """The JSON Schema for a project's `compass.yml`, built from the field
    table so the two cannot drift. Every node carries a description from
    the same table."""
    top = spec.TOP_DESCRIPTIONS
    ops = spec.OPERATION_DESCRIPTIONS

    def entry_schema(catalogue):
        fields = {name: _field_schema(catalogue, name, f)
                  for name, f in spec.FIELDS[catalogue].items()}
        properties = dict(fields)
        properties.update({
            "set": {"description": ops["set"], "type": "object",
                    "properties": copy.deepcopy(fields),
                    "additionalProperties": False},
            "replace": {"description": ops["replace"], "const": True},
            "remove": {"description": ops["remove"], "const": True},
            "locked": {"description": ops["locked"], "enum": [True, "hard"]},
            "unlock": {"description": ops["unlock"], "const": True},
            "waiver": {"description": ops["waiver"], "type": "object"},
        })
        return {"description": spec.ENTRY_DESCRIPTIONS[catalogue], "type": "object",
                "properties": properties, "additionalProperties": False}

    properties = {
        "schema": {"description": top["schema"], "type": "integer"},
        "extends": {"description": top["extends"], "oneOf": [
            {"description": top["extends.name"], "type": "string"},
            {"description": top["extends.object"], "type": "object", "properties": {
                "from": {"description": top["extends.from"], "type": "string"},
                "approved_by": {"description": top["extends.approved_by"],
                                "type": "string"},
                "approved_on": {"description": top["extends.approved_on"],
                                "format": "date", "type": "string"}},
             "required": ["from"], "additionalProperties": False}]},
        "owner": {"description": top["owner"], "type": "string"},
        "approvers": {"description": top["approvers"], "type": "object",
                      "properties": {k: {"description": top[f"approvers.{k}"],
                                         "type": "array"}
                                     for k in spec.APPROVER_KINDS},
                      "additionalProperties": False},
        "capabilities": {"description": top["capabilities"], "type": "object",
                         "properties": {c: {"description": top[f"capabilities.{c}"],
                                            "type": "boolean"}
                                        for c in spec.CAPABILITIES},
                         "additionalProperties": False},
        "autonomy": {"description": top["autonomy"], "enum": list(spec.AUTONOMY)},
        "adoption": {"description": top["adoption"], "enum": list(spec.ADOPTION)},
        "governance_drift": {"description": top["governance_drift"],
                             "enum": list(spec.GOVERNANCE_DRIFT)},
        "allow_project_commands": {"description": top["allow_project_commands"],
                                   "type": "boolean"},
        "enforcement": {"description": top["enforcement"], "type": "object"},
        "record": {"description": top["record"], "type": "object"},
        "project": {"description": top["project"], "type": "object"},
        "prices": {"description": top["prices"], "type": "object"},
        "multiagent": {"description": top["multiagent"], "type": "object"},
        "preset_index": {"description": top["preset_index"], "type": "string"},
        "github_labels": {"description": top["github_labels"], "type": "object",
                          "properties": {s: {"description": top[f"github_labels.{s}"],
                                             "type": "boolean"}
                                         for s in spec.GITHUB_LABEL_SWITCHES},
                          "additionalProperties": False},
        "preset": {"description": top["preset"], "type": "object"},
    }
    for catalogue in spec.CATALOGUES:
        properties[catalogue] = {
            "description": spec.CATALOGUE_DESCRIPTIONS[catalogue],
            "type": "object",
            "patternProperties": {spec.ID_PATTERN: entry_schema(catalogue)},
            "additionalProperties": False,
        }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "compass.yml",
        "description": top[""],
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }


def check_vocabulary(config):
    """Every problem in the `vocabulary` of a resolved configuration, as
    `(code, path, message)` like the merge's errors. Empty means every key
    names a real entry and no name or alias is ambiguous.

    This reads the resolved result, not one layer: a collision is between
    entries that may come from different layers, and a layer on its own
    cannot see the parent's names. `policy lint` will call it.

    - `M-REF-UNKNOWN`: a key that is not `<catalogue>.<id>`, names a
      catalogue with no display names, or names an id the catalogue lacks.
    - `M-ALIAS-COLLISION`: one text, ignoring case and spacing, belongs to
      two entries of one catalogue, as an id, a name or an alias. The same
      text in two catalogues is fine, because a person types it against one.
      Two ids that differ only by case are not reported: no name or alias
      is involved.
    - `M-FIELD-SHAPE`: a name or an alias that is empty or blank.
    """
    vocabulary_entries = config.get("vocabulary")
    if not isinstance(vocabulary_entries, dict):
        return []
    errors = []
    owners = {}       # (catalogue, normalised text) -> [(entry key, role, text)]
    for catalogue in spec.CATALOGUES:
        table = config.get(catalogue)
        if catalogue != "vocabulary" and isinstance(table, dict):  # no names of its own
            for entry_id in table:
                owners.setdefault((catalogue, vocabulary.normal(entry_id)), []).append(
                    (f"{catalogue}.{entry_id}", "id", str(entry_id)))
    for key, entry in vocabulary_entries.items():
        parts = vocabulary.split_key(key)
        if parts is None:
            errors.append(("M-REF-UNKNOWN", f"vocabulary.{key}",
                           f"'{key}' is not <catalogue>.<id> for a catalogue that "
                           f"has display names"))
            continue
        catalogue, entry_id = parts
        if entry_id not in (config.get(catalogue) or {}):
            errors.append(("M-REF-UNKNOWN", f"vocabulary.{key}",
                           f"{catalogue} has no entry '{entry_id}' to name"))
            continue
        for role, text in vocabulary.texts(entry):
            if not vocabulary.normal(text):
                # A blank name shows nothing and a blank alias is typed by no
                # one; two blanks would also collide with each other.
                errors.append(("M-FIELD-SHAPE", f"vocabulary.{key}",
                               f"the {role} is empty or blank"))
                continue
            owners.setdefault((catalogue, vocabulary.normal(text)), []).append(
                (key, role, text))
    for (catalogue, _), holders in owners.items():
        distinct = {key for key, _, _ in holders}
        if len(distinct) < 2 or all(role == "id" for _, role, _ in holders):
            continue
        shown = next(text for _, role, text in holders if role != "id")
        who = " and ".join(f"the {role} of {key}"
                           for key, role in dict.fromkeys((k, r) for k, r, _ in holders))
        errors.append(("M-ALIAS-COLLISION", "vocabulary",
                       f"'{shown}' is {who}, so it does not name one entry of "
                       f"{catalogue}"))
    return errors
