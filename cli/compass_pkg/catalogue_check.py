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
# DEPENDENCY: standard library (datetime, re); compass_pkg.catalogue_spec;
# compass_pkg.vocabulary; compass_pkg.waivers (its date reader).
from __future__ import annotations

import datetime
import re

from compass_pkg import catalogue_spec as spec
from compass_pkg import vocabulary, waivers

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
        given = waivers._date(extends["approved_on"])
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
    allowed = _ENUMS.get((catalogue, name))
    if allowed is not None:
        return {"enum": list(allowed)}
    if field["type"] == "list":
        # A list field also takes the list operations in a layer.
        return {"oneOf": [{"type": "array"},
                          {"type": "object", "properties": {
                              "add": {"type": "array"}, "remove": {"type": "array"}},
                           "additionalProperties": False}]}
    return dict(_JSON_TYPES[field["type"]])


def schema():
    """The JSON Schema for a project's `compass.yml`, built from the field
    table so the two cannot drift."""
    def entry_schema(catalogue):
        fields = {name: _field_schema(catalogue, name, f)
                  for name, f in spec.FIELDS[catalogue].items()}
        properties = dict(fields)
        properties.update({
            "set": {"type": "object", "properties": dict(fields),
                    "additionalProperties": False},
            "replace": {"const": True}, "remove": {"const": True},
            "locked": {"enum": [True, "hard"]}, "unlock": {"const": True},
            "waiver": {"type": "object"},
        })
        return {"type": "object", "properties": properties,
                "additionalProperties": False}

    properties = {
        "schema": {"type": "integer"},
        "extends": {"oneOf": [
            {"type": "string"},
            {"type": "object", "properties": {
                "from": {"type": "string"}, "approved_by": {"type": "string"},
                "approved_on": {"type": "string", "format": "date"}},
             "required": ["from"], "additionalProperties": False}]},
        "owner": {"type": "string"},
        "approvers": {"type": "object",
                      "properties": {k: {"type": "array"} for k in spec.APPROVER_KINDS},
                      "additionalProperties": False},
        "capabilities": {"type": "object",
                         "properties": {c: {"type": "boolean"} for c in spec.CAPABILITIES},
                         "additionalProperties": False},
        "autonomy": {"enum": list(spec.AUTONOMY)},
        "adoption": {"enum": list(spec.ADOPTION)},
        "allow_project_commands": {"type": "boolean"},
        "enforcement": {"type": "object"},
        "record": {"type": "object"},
        "project": {"type": "object"},
        "prices": {"type": "object"},
        "multiagent": {"type": "object"},
        "preset_index": {"type": "string"},
        "preset": {"type": "object"},
    }
    for catalogue in spec.CATALOGUES:
        properties[catalogue] = {
            "type": "object",
            "patternProperties": {spec.ID_PATTERN: entry_schema(catalogue)},
            "additionalProperties": False,
        }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "compass.yml",
        "description": "A project's one configuration file: its overlay on the "
                       "shipped default and its settings (ADR-043). Generated "
                       "from cli/compass_pkg/catalogue_spec.py; do not edit by hand.",
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
