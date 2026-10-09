# compass_pkg.word_map - read retired words through field-scoped tables
"""Map the words a Compass release retired to the words that replace them.

A word is mapped only in the fields that hold it, never as bare text: `full`
is a stage mode and an artifact depth, and is still the name of a delivery
approach; `standard` is a size, and `delivery_approach: standard` is a
different row. Each field has its own table in `cli/migrate-map.yml` (under
`values:`, and `friction_keys:`), with an in-module copy in `FALLBACK` for a
checkout with no framework install. A test keeps the copy equal to the file,
and keeps `retired_values:` in `governance/terminology.yml` equal to both.

There are two entry points, and one mapping behind each:

- a manifest, as `core.normalize_spine` loads it (`map_manifest`);
- a configuration layer, before `layers` checks it and again where `merge`
  applies it (`map_layer`). The paths come from
  `catalogue_spec.VALUE_DOMAINS`, so the mapping and the field catalogue
  cannot disagree about where a word sits.

A value that is neither an old word nor a new one passes through unchanged and
is rejected by the check that rejected it before. Every function here is
idempotent: a document already in the new words comes back unchanged.

`core` binds the reader of the data file (`bind`), because this module cannot
import `core`: `core` imports it, and the import graph is checked to have no
cycle (`tests/test_cli_module_split.py`).
"""
# DEPENDENCY: standard library (copy, os, shutil, sys);
# compass_pkg.catalogue_spec. It reads cli/migrate-map.yml only through the
# reader `core` binds, and imports nothing else from the package.
from __future__ import annotations

import copy
import os
import shutil
import sys

from compass_pkg import catalogue_spec as spec

# The tables that sit under `values:` in cli/migrate-map.yml, and the one
# top-level table. A manifest field and a layer field read the table named
# in the domain column of `catalogue_spec.VALUE_DOMAINS`.
VALUE_SECTIONS = ("stage_mode", "artifact_depth", "size", "issue_status",
                  "close_reason", "run_stage")
KEY_SECTIONS = ("friction_keys",)

# The in-module copy of the tables, for a checkout with no framework install.
# A table with a row is what turns a retired word into a new one on read and
# on write. Every table is wired.
FALLBACK = {name: {} for name in (*VALUE_SECTIONS, *KEY_SECTIONS)}
FALLBACK["stage_mode"] = {
    "full": "thorough",
    "light": "lightweight",
    "full-plus-backfill": "thorough-with-follow-up",
}
FALLBACK["artifact_depth"] = {
    "full": "thorough",
    "light": "lightweight",
}
FALLBACK["size"] = {"standard": "medium"}
# `active` stores nothing: the state of work in flight comes from the records.
FALLBACK["issue_status"] = {
    "queued": "backlog",
    "parked": "backlog",
    "active": None,
    "landed": "done",
    "abandoned": "done",
}
FALLBACK["close_reason"] = {"landed": "completed", "abandoned": "not-planned"}
FALLBACK["run_stage"] = {"build": "implement"}
FALLBACK["friction_keys"] = {"phase": "stage"}

_READ = None


def bind(reader):
    """Give this module the reader of `cli/migrate-map.yml`
    (`core.migrate_map_section`: `reader(name, fallback)`)."""
    global _READ
    _READ = reader


def tables():
    """`{section: {old: new}}` for every section, from the data file when it
    can be read and from `FALLBACK` otherwise. `new` is None for a word that
    is no longer stored (an issue status read from the records)."""
    rows = {name: dict(fallback) for name, fallback in FALLBACK.items()}
    if _READ is None:
        return rows
    values = _READ("values", {})
    for name in VALUE_SECTIONS:
        if isinstance(values.get(name), dict) and values[name]:
            rows[name] = dict(values[name])
    for name in KEY_SECTIONS:
        found = _READ(name, {})
        if isinstance(found, dict) and found:
            rows[name] = dict(found)
    return rows


def retired_triples(rows=None):
    """Every row as `(field, old, new)`, sorted. This is what
    `retired_values:` in `governance/terminology.yml` must equal."""
    rows = tables() if rows is None else rows
    return sorted(((field, old, new) for field, table in rows.items()
                   for old, new in table.items()), key=lambda t: (t[0], t[1]))


def _new(rows, section, value):
    """The replacement for `value` in `section`, or None when it is not an
    old word there (or the old word is retired with no replacement)."""
    table = rows.get(section) or {}
    return table.get(value) if isinstance(value, str) else None


def _is_old(rows, section, value):
    return isinstance(value, str) and value in (rows.get(section) or {})


# --- configuration layers -----------------------------------------------------

def _olds(rows):
    out = set()
    for section in ("stage_mode", "artifact_depth", "size"):
        out.update(rows.get(section) or ())
    return out


def _mentions(node, olds):
    """True when any key or string in `node` is one of `olds`: the cheap
    test that lets a document with no old word skip the copy."""
    if isinstance(node, dict):
        return any((isinstance(k, str) and k in olds) or _mentions(v, olds)
                   for k, v in node.items())
    if isinstance(node, (list, tuple)):
        return any(_mentions(item, olds) for item in node)
    return isinstance(node, str) and node in olds


def map_layer(doc, rows=None):
    """`(mapped, changes)` for a configuration layer: a mapped deep copy and
    the list of `(path, old, new)` it changed. A document with nothing to map
    comes back as the same object with no changes."""
    rows = tables() if rows is None else rows
    olds = _olds(rows)
    if not olds or not isinstance(doc, dict) or not _mentions(doc, olds):
        return doc, []
    mapped, changes = copy.deepcopy(doc), []
    for catalogue, entry_id, field, shape, domain in spec.VALUE_DOMAINS:
        entries = mapped.get(catalogue)
        for name, entry in (entries.items() if isinstance(entries, dict) else ()):
            if entry_id not in ("*", name) or not isinstance(entry, dict):
                continue
            where = f"{catalogue}.{name}"
            holders = [(where, entry)]
            if isinstance(entry.get("set"), dict):
                holders.append((f"{where}.set", entry["set"]))
            for path, holder in holders:
                if field in holder:
                    holder[field] = _map_field(holder[field], shape, rows.get(domain) or {},
                                               f"{path}.{field}", changes)
    _walk_predicates(mapped, "", rows, changes)
    return (mapped, changes) if changes else (doc, [])


def _map_word(value, table, path, changes):
    if isinstance(value, str) and table.get(value) is not None:
        changes.append((path, value, table[value]))
        return table[value]
    return value


def _map_field(value, shape, table, path, changes):
    if shape == "value":
        return _map_word(value, table, path, changes)
    if shape == "items":
        if isinstance(value, list):
            return [_map_word(item, table, path, changes) for item in value]
        if isinstance(value, dict):
            return {key: ([_map_word(i, table, path, changes) for i in part]
                          if isinstance(part, list) else part)
                    for key, part in value.items()}
        return value
    if not isinstance(value, dict):
        return value
    operation = value and set(value) <= {"set", "remove"}
    if operation:
        out = dict(value)
        if isinstance(value.get("set"), dict):
            out["set"] = _map_pairs(value["set"], shape, table, path, changes)
        if shape == "keys" and isinstance(value.get("remove"), list):
            out["remove"] = [_map_word(i, table, path, changes) for i in value["remove"]]
        return out
    return _map_pairs(value, shape, table, path, changes)


def _map_pairs(pairs, shape, table, path, changes):
    out = {}
    for key, value in pairs.items():
        if shape == "keys":
            new = _map_word(key, table, path, changes)
            if new != key and new in pairs:
                continue            # the new word is already there and wins
            out[new] = value
        else:
            out[key] = _map_word(value, table, path, changes)
    return out


def _walk_predicates(node, path, rows, changes):
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else str(key)
            if key == "params":
                continue            # a check parameter is not an assessment
            if key in spec.PREDICATE_KEYS and isinstance(value, dict):
                _map_when(value, here, rows.get("size") or {}, changes)
            else:
                _walk_predicates(value, here, rows, changes)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _walk_predicates(item, f"{path}[{index}]", rows, changes)


def _map_when(when, path, table, changes):
    """Map each size test in one condition, as the evaluator reads it: a
    value, a list of values, `at_least:` and `any_of:` clauses."""
    for key in list(when):
        value, here = when[key], f"{path}.{key}"
        if key == "any_of":
            for index, clause in enumerate(value if isinstance(value, list) else []):
                if isinstance(clause, dict):
                    _map_when(clause, f"{here}[{index}]", table, changes)
        elif key in spec.SIZE_KEYS:
            if isinstance(value, dict) and "at_least" in value:
                value["at_least"] = _map_word(value["at_least"], table,
                                              f"{here}.at_least", changes)
            elif isinstance(value, list):
                when[key] = [_map_word(item, table, here, changes) for item in value]
            else:
                when[key] = _map_word(value, table, here, changes)


def map_fixture(doc, rows=None):
    """A policy-test fixture with its assessment size and its expected stage
    modes mapped: the words an older preset wrote."""
    rows = tables() if rows is None else rows
    if not isinstance(doc, dict):
        return doc
    out, changes = copy.deepcopy(doc), []
    assessment = out.get("assessment")
    if isinstance(assessment, dict) and "size" in assessment:
        assessment["size"] = _map_word(assessment["size"], rows.get("size") or {},
                                       "assessment.size", changes)
    expect = out.get("expect")
    if isinstance(expect, dict) and isinstance(expect.get("stages"), dict):
        modes = rows.get("stage_mode") or {}
        expect["stages"] = {stage: _map_word(mode, modes, f"expect.stages.{stage}", changes)
                            for stage, mode in expect["stages"].items()}
    return out


def _stale_shape(shape, modes, depths):
    if not isinstance(shape, dict):
        return False
    stages, artifacts = shape.get("stages"), shape.get("artifacts")
    return (isinstance(stages, dict) and any(m in modes for m in stages.values())
            or isinstance(artifacts, dict) and any(d in depths for d in artifacts.values()))


def map_policy(policy, rows=None):
    """A legacy routing policy (`governance/routing-policy.yml`) read through
    the tables: a project that copied `governance/` before the rename keeps
    its old words in the stage weights, the artifact depths, the size
    vocabulary and the size tests of its rules, and routes as it did.

    The evaluator reads the policy once for each assessment, so the check for
    an old word looks only at the places a word sits and returns `policy`
    itself, not a copy, when it finds none."""
    rows = tables() if rows is None else rows
    modes, depths = rows.get("stage_mode") or {}, rows.get("artifact_depth") or {}
    sizes = rows.get("size") or {}
    if not isinstance(policy, dict) or not (modes or depths or sizes):
        return policy
    vocabulary = policy.get("assessment_vocabulary") or {}
    old_size = isinstance(vocabulary, dict) and any(
        isinstance(w, str) and w in sizes for w in vocabulary.get("size") or ())
    shapes = policy.get("route_shapes") or {}
    ranks = policy.get("stage_mode_ranks")
    old_ranks = isinstance(ranks, dict) and any(
        isinstance(row, dict) and any(m in modes for m in row) for row in ranks.values())
    old_shape = isinstance(shapes, dict) and any(
        _stale_shape(shape, modes, depths) for shape in shapes.values())
    if not (old_size or old_ranks or old_shape):
        return policy
    out, changes = copy.deepcopy(policy), []
    if old_size:
        out["assessment_vocabulary"]["size"] = [
            _map_word(w, sizes, "assessment_vocabulary.size", changes)
            for w in out["assessment_vocabulary"]["size"]]
        _walk_predicates(out, "", rows, changes)
    for name, shape in (out.get("route_shapes") or {}).items():
        if isinstance(shape, dict):
            where = f"route_shapes.{name}"
            if isinstance(shape.get("stages"), dict):
                shape["stages"] = {k: _map_word(v, modes, f"{where}.stages.{k}", changes)
                                   for k, v in shape["stages"].items()}
            if isinstance(shape.get("artifacts"), dict):
                shape["artifacts"] = {k: _map_word(v, depths, f"{where}.artifacts.{k}", changes)
                                      for k, v in shape["artifacts"].items()}
    if old_ranks:
        out["stage_mode_ranks"] = {
            stage: {modes.get(m, m): rank for m, rank in row.items()}
            for stage, row in out["stage_mode_ranks"].items()}
    return out


def advisory_lines(layer):
    """One advisory line per change the mapping made to `layer`, for the lint
    and the preset test. It names the layer, the path and the new word."""
    return [f"advisory: {layer.name}: {path} reads '{old}' as '{new}'; "
            f"the old word is read until 7.0.0"
            for path, old, new in getattr(layer, "changes", ())]


# --- manifests ----------------------------------------------------------------

def _map_manifest(manifest, rows, changes):
    """Map the fields of a manifest in place, appending `(path, old, new)`."""
    if not isinstance(manifest, dict):
        return
    modes = rows.get("stage_mode") or {}
    stages = manifest.get("stages")
    if isinstance(stages, dict):
        for stage, mode in list(stages.items()):
            stages[stage] = _map_word(mode, modes, f"stages.{stage}", changes)
    for index, art in enumerate(manifest.get("artifacts") if isinstance(
            manifest.get("artifacts"), list) else []):
        if isinstance(art, dict) and "depth" in art:
            art["depth"] = _map_word(art["depth"], rows.get("artifact_depth") or {},
                                     f"artifacts[{index}].depth", changes)
    for key in ("assessment", "evaluated_assessment"):
        block = manifest.get(key)
        if isinstance(block, dict) and "size" in block:
            block["size"] = _map_word(block["size"], rows.get("size") or {},
                                      f"{key}.size", changes)
    for index, run in enumerate(manifest.get("runs") if isinstance(
            manifest.get("runs"), list) else []):
        if isinstance(run, dict) and "stage" in run:
            run["stage"] = _map_word(run["stage"], rows.get("run_stage") or {},
                                     f"runs[{index}].stage", changes)
    _map_friction(manifest, rows, changes)
    _map_status(manifest, rows, changes)


def _map_friction(manifest, rows, changes):
    keys = rows.get("friction_keys") or {}
    stage_keys = _READ("stage_keys", {}) if _READ is not None else {}
    entries = manifest.get("friction")
    for index, entry in enumerate(entries if isinstance(entries, list) else []):
        if not isinstance(entry, dict):
            continue
        for old, new in keys.items():
            if old not in entry:
                continue
            value = entry.pop(old)
            if new not in entry:        # a key already in the new word wins
                entry[new] = stage_keys.get(value, value) if isinstance(value, str) else value
            changes.append((f"friction[{index}].{old}", old, new))


def _map_status(manifest, rows, changes):
    status = manifest.get("status")
    if not _is_old(rows, "issue_status", status):
        return
    new = rows["issue_status"][status]
    if new is None:
        del manifest["status"]
    else:
        manifest["status"] = new
    changes.append(("status", status, new))
    reason = (rows.get("close_reason") or {}).get(status)
    if reason is not None and "close_reason" not in manifest:
        manifest["close_reason"] = reason
        changes.append(("close_reason", status, reason))


def map_manifest(manifest, rows=None):
    """The manifest with every mapped field in the new words, changed in place
    and returned."""
    _map_manifest(manifest, tables() if rows is None else rows, [])
    return manifest


def old_words(raw, rows=None):
    """The `(path, old, new)` a save would rewrite in a manifest as it is on
    disk. `raw` is the parsed file, not the mapped copy a command holds."""
    if not isinstance(raw, dict):
        return []
    changes = []
    _map_manifest(copy.deepcopy(raw), tables() if rows is None else rows, changes)
    return changes


def reverse_manifest(manifest, rows=None):
    """The manifest in the old words, for the rollback procedure. Mapping the
    result forward again gives the manifest back, except that a close reason
    of `duplicate` returns as `not-planned` (v5 has no such reason)."""
    rows = tables() if rows is None else rows
    back = {section: {new: old for old, new in table.items() if new is not None}
            for section, table in rows.items()}
    _map_manifest_back(manifest, rows, back)
    return manifest


def _map_manifest_back(manifest, rows, back):
    if not isinstance(manifest, dict):
        return
    stages = manifest.get("stages")
    if isinstance(stages, dict):
        for stage, mode in list(stages.items()):
            stages[stage] = back["stage_mode"].get(mode, mode)
    for art in manifest.get("artifacts") if isinstance(
            manifest.get("artifacts"), list) else []:
        if isinstance(art, dict) and "depth" in art:
            art["depth"] = back["artifact_depth"].get(art["depth"], art["depth"])
    for key in ("assessment", "evaluated_assessment"):
        block = manifest.get(key)
        if isinstance(block, dict) and "size" in block:
            block["size"] = back["size"].get(block["size"], block["size"])
    for run in manifest.get("runs") if isinstance(manifest.get("runs"), list) else []:
        if isinstance(run, dict) and "stage" in run:
            run["stage"] = back["run_stage"].get(run["stage"], run["stage"])
    for new, old in back["friction_keys"].items():
        for entry in manifest.get("friction") if isinstance(
                manifest.get("friction"), list) else []:
            if isinstance(entry, dict) and new in entry and old not in entry:
                entry[old] = entry.pop(new)
    _status_back(manifest, rows)


def _status_back(manifest, rows):
    table = rows.get("issue_status") or {}
    if not table:
        return
    status = manifest.get("status")
    if status is None:
        gone = [old for old, new in table.items() if new is None]
        if gone:
            manifest["status"] = gone[0]
    elif status == "done":
        reason = manifest.get("close_reason")
        # `duplicate` has no old word, so it returns as the not-planned one.
        reason = "not-planned" if reason == "duplicate" else reason
        old = next((o for o, r in (rows.get("close_reason") or {}).items()
                    if r == reason), None)
        if old is not None:
            manifest["status"] = old
            manifest.pop("close_reason", None)
    else:
        olds = [old for old, new in table.items() if new == status]
        # Two old words share `backlog`: a hold that records why or when it
        # was set aside was `parked`, and a bare backlog entry was `queued`.
        if "parked" in olds and (manifest.get("parked_reason")
                                 or manifest.get("parked_at")):
            manifest["status"] = "parked"
        elif olds:
            manifest["status"] = olds[0]


# --- the write path -----------------------------------------------------------

def _reading(manifest, path):
    """The state the records give a manifest that stores no status, for the
    notice. None when it cannot be read."""
    if not isinstance(manifest, dict):
        return None
    from compass_pkg import lifecycle   # lifecycle imports core, which imports this module
    try:
        return lifecycle.state_of(manifest, os.path.dirname(os.path.abspath(path)))
    except Exception:                                       # noqa: BLE001
        return None


def _notice(path, old, new, backup, reading=None):
    if new is None:
        shown = f" ({reading})" if reading else ""
        return (f"compass: {path}: '{old}' is no longer stored; the state now comes "
                f"from the records{shown}. The original is in {backup}.")
    return (f"compass: {path}: '{old}' is now '{new}'; the old word is read until "
            f"7.0.0. The original is in {backup}.")


def backup_and_notice(path, raw, rows=None, mapped=None):
    """Before a save over a manifest that holds old words: copy the file to
    `<name>.v5.bak` unless that copy exists, and print one notice line per old
    word on standard error. The backup is never overwritten. Returns the
    changes. `raw` is the parsed file as it is on disk; `mapped` is the
    manifest being written, which the notice reads a dropped status from."""
    changes = old_words(raw, rows)
    if not changes:
        return []
    backup = path + ".v5.bak"
    if not os.path.exists(backup):
        shutil.copyfile(path, backup)
    shown = set()
    for where, old, new in changes:
        key = (where.split(".")[0].split("[")[0], old, new)
        if key not in shown:
            shown.add(key)
            reading = _reading(mapped, path) if new is None else None
            print(_notice(where, old, new, os.path.basename(backup), reading),
                  file=sys.stderr)
    return changes


def prepare(manifest, path, raw, schema_version=None, rows=None):
    """The mapping to write for `manifest`: it keeps the backup and says what
    it rewrites (`backup_and_notice`), then returns the manifest in the new
    words. A manifest with nothing to map comes back as the same object.
    `schema_version` is stamped on the result when it is given, so a CLI that
    reads only older majors refuses the file instead of misreading it."""
    rows = tables() if rows is None else rows
    backup_and_notice(path, raw, rows, mapped=manifest)
    changes, probe = [], copy.deepcopy(manifest)
    _map_manifest(probe, rows, changes)
    out = probe if changes else manifest
    if schema_version and isinstance(out, dict):
        out["schema_version"] = schema_version
    return out
