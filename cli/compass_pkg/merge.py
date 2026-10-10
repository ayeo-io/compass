# compass_pkg.merge - the one merge grammar and the resolved configuration
"""Turn a chain of configuration layers into one resolved configuration.

Every layer uses the same grammar (ADR-035), so a person learns one way to
write a change:

- a full entry under a new id adds it;
- `set:` changes named fields of an entry that exists;
- `replace: true` with a full entry swaps an entry that exists;
- `remove: true` deletes an entry, and fails while another entry still
  refers to it.

Inside `set:` a scalar replaces. A list takes a plain list (replaces) or
`{add, remove}`. A map takes a plain map (replaces) or `{set, remove}` that
change it key by key; a deep merge would change keys nobody named.

`apply` is pure: it copies its inputs, collects every fault in the layer
before it raises, and returns the new configuration with a provenance map
(`catalogue.id` and `catalogue.id.field` to the layer and operation that
last wrote it). It never classifies a change and never evaluates one.
Locks, unlocks and waivers ride on an entry but are applied by the modules
that own them, not here.

Checks on the resolved result as a whole (an id nothing defines, equal
approach weights, rule-set effects) are lint's, not the merge's.
"""
# DEPENDENCY: standard library (copy); compass_pkg.catalogue_spec,
# compass_pkg.core (CompassError, only); compass_pkg.word_map.
from __future__ import annotations

import copy

from compass_pkg import catalogue_spec as spec
from compass_pkg import word_map
from compass_pkg.core import CompassError

# Which field of which catalogue holds ids of another catalogue, and how:
# `list` items, `map` keys or a `scalar`. `remove: true` is checked against
# these. It lists only the references the field table makes certain.
REFERENCES = (
    ("gates", "checks", "checks", "list"),
    ("stages", "entry", "checks", "list"),
    ("stages", "exit", "checks", "list"),
    ("artifacts", "checks", "checks", "list"),
    ("artifacts", "depends_on", "artifacts", "list"),
    ("artifacts", "stage", "stages", "scalar"),
    ("approaches", "gates", "gates", "list"),
    ("approaches", "artifacts", "artifacts", "map"),
    ("approaches", "stages", "stages", "map"),
    ("approaches", "extends", "approaches", "scalar"),
    ("gates", "stage", "stages", "scalar"),
)

# A stage's `mode` is the issue layer's choice; no other layer sets one.
ISSUE_ONLY_FIELDS = {("stages", "mode")}

_LIST_FORM = {"add", "remove"}
_MAP_FORM = {"set", "remove"}


class MergeError(CompassError):
    """A layer that does not apply. `errors` holds `(code, path, message)`
    for every fault found; the text names each code and key path."""

    def __init__(self, layer, errors):
        self.layer = layer
        self.errors = list(errors)
        super().__init__(f"{layer}: " + "; ".join(
            f"{code} {path}: {message}" for code, path, message in self.errors))


def apply(config, layer_doc, kind, name, provenance=None):
    """`(config, provenance)` after applying one layer to `config`.
    `kind` is `parent`, `project` or `issue`; `name` labels the layer in
    provenance. Raises `MergeError` listing every fault in the layer.

    The layer is read through the retired-word tables again here. A layer that
    `layers` already mapped costs a walk and changes nothing; one that came by
    another road (the classifier's chain, a policy test) is mapped too."""
    layer_doc = word_map.map_layer(layer_doc)[0]
    work = copy.deepcopy(config)
    prov = dict(provenance or {})
    errors = []
    removed = []
    ctx = _Context(kind, name, errors, prov)
    for catalogue in spec.CATALOGUES:
        if catalogue not in layer_doc:
            continue
        entries = layer_doc[catalogue]
        if not isinstance(entries, dict):
            errors.append(("M-FIELD-SHAPE", catalogue, "expected a mapping keyed by id"))
            continue
        table = work.setdefault(catalogue, {})
        for entry_id, entry in entries.items():
            if _apply_entry(ctx, table, catalogue, entry_id, entry):
                removed.append((catalogue, entry_id))
    errors += _dangling_references(work, removed)
    if errors:
        raise MergeError(name, errors)
    return {k: v for k, v in work.items() if v or k in config}, prov


def resolve(chain):
    """`(config, provenance)` after applying each layer of `chain` in
    order, root first. Each item has `name`, `kind` and `doc`."""
    config, prov = {}, {}
    for layer in chain:
        config, prov = apply(config, layer.doc, layer.kind, layer.name, prov)
    return config, prov


def combine(documents):
    """One layer from the documents it is split across. An id, or a top
    level key, in two documents is `M-OP-DUPLICATE`: which one wins would
    depend on file order, and the strict loader sees one file only."""
    combined, errors = {}, []
    for doc in documents:
        for key, value in doc.items():
            if key in spec.CATALOGUES and isinstance(value, dict):
                target = combined.setdefault(key, {})
                for entry_id, entry in value.items():
                    if entry_id in target:
                        errors.append(("M-OP-DUPLICATE", f"{key}.{entry_id}",
                                       "the id appears in two documents of one layer"))
                    else:
                        target[entry_id] = entry
            elif key in combined:
                errors.append(("M-OP-DUPLICATE", key,
                               "the key appears in two documents of one layer"))
            else:
                combined[key] = value
    if errors:
        raise MergeError("layer", errors)
    return combined


class _Context:
    def __init__(self, kind, name, errors, prov):
        self.kind, self.name, self.errors, self.prov = kind, name, errors, prov

    def fail(self, code, path, message):
        self.errors.append((code, path, message))

    def mark(self, path, operation):
        self.prov[path] = {"layer": self.name, "operation": operation}

    def forget(self, path, catalogue):
        """Drop the provenance of one entry and its fields only. A prefix
        match would also drop `gates.build.tests` when `gates.build` goes, because ids may contain dots."""
        names = {path} | {f"{path}.{field}" for field in spec.FIELDS[catalogue]}
        for key in names & set(self.prov):
            del self.prov[key]


def _apply_entry(ctx, table, catalogue, entry_id, entry):
    """Apply one entry. True when it removed an entry."""
    path = f"{catalogue}.{entry_id}"
    fields = spec.FIELDS[catalogue]
    if not isinstance(entry, dict):
        ctx.fail("M-FIELD-SHAPE", path, "expected a mapping")
        return False
    may_use = spec.LAYER_OPERATIONS[ctx.kind]
    refused = False
    for key in entry:
        if key in spec.ENTRY_OPERATIONS and key not in may_use:
            ctx.fail("M-OP-LAYER", f"{path}.{key}",
                     f"a {ctx.kind} layer cannot use {key}")
            refused = True
        elif key not in spec.ENTRY_OPERATIONS and key not in fields:
            ctx.fail("M-FIELD-UNKNOWN", f"{path}.{key}", f"not a field of {catalogue}")
            refused = True
    for key in ("replace", "remove"):
        if key in entry and key in may_use and entry[key] is not True:
            ctx.fail("M-FIELD-SHAPE", f"{path}.{key}", f"write {key}: true")
            refused = True
    if refused:
        return False
    # `locked` is both an entry operation and a field of checks and gates;
    # it never makes an entry a full one.
    body = [k for k in entry if k in fields and k != "locked"]
    is_set, is_replace, is_remove = "set" in entry, entry.get("replace") is True, \
        entry.get("remove") is True
    if (is_remove and (is_set or is_replace or body)) or (is_set and (is_replace or body)):
        ctx.fail("M-OP-CONFLICT", path,
                 "an entry is one of a full entry, set, replace or remove, not several")
        return False
    present = entry_id in table
    if is_remove:
        if not present:
            ctx.fail("M-REMOVE-UNKNOWN", path, "remove: the parent does not hold this id")
            return False
        del table[entry_id]
        ctx.forget(path, catalogue)
        return True
    if is_set:
        if not present:
            ctx.fail("M-SET-UNKNOWN", path, "set: the parent does not hold this id")
            return False
        _apply_set(ctx, table[entry_id], catalogue, path, entry)
        return False
    if is_replace and not present:
        ctx.fail("M-REPLACE-UNKNOWN", path, "replace: the parent does not hold this id")
        return False
    if is_replace and not body:
        ctx.fail("M-ADD-PARTIAL", path, "replace: true needs a full entry")
        return False
    if body:
        if present and not is_replace:
            ctx.fail("M-ADD-EXISTS", path,
                     "the id exists; use set to change it or replace: true to swap it")
            return False
        _apply_full(ctx, table, catalogue, path, entry_id, entry, is_replace)
        return False
    if not present:
        ctx.fail("M-ADD-PARTIAL", path, "a new entry needs its required fields: "
                 + ", ".join(f for f, s in fields.items() if s["required"]))
    elif "locked" in entry and "locked" in fields:
        table[entry_id]["locked"] = entry["locked"]
        ctx.mark(f"{path}.locked", "set")
    return False


def _apply_full(ctx, table, catalogue, path, entry_id, entry, replacing):
    fields = spec.FIELDS[catalogue]
    values = {k: v for k, v in entry.items() if k in fields}
    missing = [f for f, s in fields.items() if s["required"] and f not in values]
    if missing:
        ctx.fail("M-ADD-PARTIAL", path,
                 f"a full entry is needed; missing {', '.join(missing)}")
        return
    resolved = {}
    for key, value in values.items():
        new, ok = _field(ctx, catalogue, f"{path}.{key}", fields[key], None, value, False)
        if ok:
            resolved[key] = new
    if len(resolved) != len(values):
        return
    operation = "replace" if replacing else "add"
    if replacing:
        ctx.forget(path, catalogue)
    table[entry_id] = resolved
    ctx.mark(path, operation)
    for key in resolved:
        ctx.mark(f"{path}.{key}", operation)


def _apply_set(ctx, current, catalogue, path, entry):
    fields = spec.FIELDS[catalogue]
    changes = entry["set"]
    if not isinstance(changes, dict):
        ctx.fail("M-FIELD-SHAPE", f"{path}.set", "expected a mapping of field to value")
        return
    changes = dict(changes)
    if "locked" in entry and "locked" in fields:
        changes["locked"] = entry["locked"]
    for key, value in changes.items():
        where = f"{path}.set.{key}"
        if key not in fields:
            ctx.fail("M-FIELD-UNKNOWN", where, f"not a field of {catalogue}")
            continue
        new, ok = _field(ctx, catalogue, where, fields[key], current.get(key), value, True)
        if ok:
            current[key] = new
            ctx.mark(f"{path}.{key}", "set")


def _field(ctx, catalogue, path, field_spec, current, value, in_set):
    """`(new value, ok)` for one field under the field operations."""
    key = path.rsplit(".", 1)[1]
    if (catalogue, key) in ISSUE_ONLY_FIELDS and ctx.kind != "issue":
        ctx.fail("M-FIELD-LAYER", path,
                 f"{key} is the issue layer's choice; a {ctx.kind} layer cannot set it")
        return None, False
    kind = field_spec["merge"]
    if kind == "list" and isinstance(value, dict):
        return _list_operation(ctx, path, current, value, in_set)
    if kind == "map" and isinstance(value, dict) and value and set(value) <= _MAP_FORM:
        return _map_operation(ctx, path, current, value, in_set)
    return copy.deepcopy(value), True


def _list_operation(ctx, path, current, op, in_set):
    if not in_set:
        ctx.fail("M-LIST-OP-OUTSIDE-SET", path,
                 "add and remove on a list belong inside set:")
        return None, False
    add, remove = op.get("add", []), op.get("remove", [])
    if not op or set(op) - _LIST_FORM or not isinstance(add, list) \
            or not isinstance(remove, list):
        ctx.fail("M-FIELD-SHAPE", path,
                 "a list operation is {add: [...], remove: [...]} and nothing else")
        return None, False
    if len({repr(i) for i in add}) != len(add) or len({repr(i) for i in remove}) != len(remove):
        ctx.fail("M-FIELD-SHAPE", path, "a list operation names an item once")
        return None, False
    held = list(current or [])
    absent = [i for i in remove if i not in held]
    present = [i for i in add if i in held]
    if absent:
        ctx.fail("M-LIST-REMOVE-ABSENT", path,
                 f"remove: the list does not hold {', '.join(map(str, absent))}")
    if present:
        ctx.fail("M-LIST-ADD-PRESENT", path,
                 f"add: the list already holds {', '.join(map(str, present))}")
    if absent or present:
        return None, False
    return [i for i in held if i not in remove] + copy.deepcopy(add), True


def _map_operation(ctx, path, current, op, in_set):
    if not in_set:
        ctx.fail("M-MAP-OP-OUTSIDE-SET", path,
                 "set and remove on a map belong inside set:")
        return None, False
    to_set, remove = op.get("set", {}), op.get("remove", [])
    if not isinstance(to_set, dict) or not isinstance(remove, list):
        ctx.fail("M-FIELD-SHAPE", path,
                 "a map operation is {set: {...}, remove: [keys]} and nothing else")
        return None, False
    both = [k for k in remove if k in to_set]
    if both:
        ctx.fail("M-OP-CONFLICT", path, "a map key is set or removed, not both: "
                 + ", ".join(map(str, both)))
        return None, False
    held = dict(current or {})
    absent = [k for k in remove if k not in held]
    if absent:
        ctx.fail("M-MAP-REMOVE-ABSENT", path,
                 f"remove: the map does not hold {', '.join(map(str, absent))}")
        return None, False
    result = {k: v for k, v in held.items() if k not in remove}
    result.update(copy.deepcopy(to_set))
    return result, True


def _dangling_references(work, removed):
    """`M-REF-REMOVED` for each removed id something in the result still
    names. Checked on the result, so a layer can detach and remove at once."""
    errors = []
    for catalogue, entry_id in removed:
        found = []
        for ref_catalogue, field, target, shape in REFERENCES:
            if target != catalogue:
                continue
            for ref_id, entry in work.get(ref_catalogue, {}).items():
                value = entry.get(field)
                held = (shape == "list" and isinstance(value, list) and entry_id in value) \
                    or (shape == "map" and isinstance(value, dict) and entry_id in value) \
                    or (shape == "scalar" and value == entry_id)
                if held:
                    found.append(f"{ref_catalogue}.{ref_id}.{field}")
        if found:
            errors.append(("M-REF-REMOVED", f"{catalogue}.{entry_id}",
                           "remove: still referred to by " + ", ".join(found)
                           + "; detach it first"))
    return errors
