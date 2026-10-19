# compass_pkg.old_names - read the old typed names that 7.0.0 still accepts
"""One reader-side table of old typed names, each with the version that ends it.

The table is the `old_names:` section of `cli/migrate-map.yml`: kind, then old
word, then `{new, removed_in}`. Every row ends at 8.0.0. A reader of one kind
(the `--kind` argument, the state key, the readiness record, a skill, a check
id) asks this module for the current word. A stored value in a manifest keeps
the `word_map` mapping and its `.v5.bak` backup; `word_map.tables()` builds its
`reassessment_kind` and `check_id` sections from this table.

`cli/aliases.yml` stays empty: these are values and keys, not CLI spellings.

This is a leaf. It imports nothing from `compass_pkg`, because `core` and
`word_map` both reach it. `word_map.bind` hands it the same reader of the data
file that `core` binds, and `_FALLBACK` is the copy for a checkout with no
framework install; a test keeps the copy equal to the file.
"""
# DEPENDENCY: standard library (functools, sys); nothing from compass_pkg.
from __future__ import annotations

import functools
import sys

# The notice names the kind of name. Keys are the table's kinds.
LABELS = {
    "reassessment_kind": "kind",
    "check_id": "check",
    "skill": "skill",
    "refusal_code": "refusal code",
    "state_key": "state key",
    "readiness_key": "readiness key",
    "json_key": "JSON key",
    "spec_heading": "heading",
    "term": "term",
}


def _row(new):
    return {"new": new, "removed_in": "8.0.0"}


_FALLBACK = {
    "reassessment_kind": {"judgement": _row("judgment")},  # us-english-scan: allow - old name read until 8.0.0
    "check_id": {"dor-behaviour-is-gwt": _row("dor-behavior-is-gwt")},  # us-english-scan: allow - old name read until 8.0.0
    "skill": {"behaviour-mapping": _row("behavior-mapping")},  # us-english-scan: allow - old name read until 8.0.0
    "refusal_code": {"not-initialised": _row("not-initialized")},  # us-english-scan: allow - old name read until 8.0.0
    "state_key": {"initialised": _row("initialized")},  # us-english-scan: allow - old name read until 8.0.0
    "readiness_key": {"catalogue_digest": _row("catalog_digest")},  # us-english-scan: allow - old name read until 8.0.0
    "json_key": {"behaviour": _row("behavior"), "behaviours": _row("behaviors")},  # us-english-scan: allow - old name read until 8.0.0
    "spec_heading": {"Current Behaviour": _row("Current Behavior"),  # us-english-scan: allow - old name read until 8.0.0
                     "Archived Behaviour": _row("Archived Behavior")},  # us-english-scan: allow - old name read until 8.0.0
    "term": {"catalogue": _row("catalog")},  # us-english-scan: allow - old name read until 8.0.0
}

_READ = None
_SEEN: set = set()


def bind(reader):
    """Give this module the reader of `cli/migrate-map.yml`
    (`reader(name, fallback)`)."""
    global _READ
    _READ = reader


def _table():
    if _READ is None:
        return _FALLBACK
    found = _READ("old_names", _FALLBACK)
    return found if isinstance(found, dict) and found else _FALLBACK


def rows(kind=None):
    """Every row as `{kind, old, new, removed_in}`, in table order; only the
    rows of `kind` when it is given."""
    out = []
    for name, words in _table().items():
        if kind is not None and name != kind:
            continue
        for old, row in (words or {}).items():
            out.append({"kind": name, "old": old, "new": row["new"],
                        "removed_in": str(row["removed_in"])})
    return out


def is_old(kind, value):
    return isinstance(value, str) and any(r["old"] == value for r in rows(kind))


def current(kind, value):
    """The current word for `value`: the new word of an old one, else `value`."""
    for row in rows(kind):
        if isinstance(value, str) and row["old"] == value:
            return row["new"]
    return value


def _notice(kind, old, new):
    key = (kind, old)
    if key in _SEEN:
        return
    _SEEN.add(key)
    print(f"compass: {LABELS.get(kind, kind)} {old} is now {new}; "
          f"the old word is read until 8.0.0.", file=sys.stderr)


def read(kind, value):
    """`current(kind, value)`; an old word prints one notice per run."""
    new = current(kind, value)
    if new != value:
        _notice(kind, value, new)
    return new


def pick(mapping, kind, new, default=None):
    """`mapping[new]` when present (the new word wins when both are), else the
    value under its old word, with the notice, else `default`."""
    if new in mapping:
        return mapping[new]
    for row in rows(kind):
        if row["new"] == new and row["old"] in mapping:
            _notice(kind, row["old"], new)
            return mapping[row["old"]]
    return default


def twins(kind, mapping):
    """A copy of `mapping` that also holds, for each new key present, its old
    twin with the same value (a record that older readers still parse)."""
    out = dict(mapping)
    for row in rows(kind):
        if row["new"] in mapping and row["old"] not in out:
            out[row["old"]] = mapping[row["new"]]
    return out


def _version(text):
    return tuple(int(part) for part in str(text).split(".") if part.isdigit())


def removal_problems(version):
    """One line for each row that ends at or before `version`; the row and the
    code that reads it must be deleted then."""
    now = _version(version)
    return [f"old_names: {r['kind']} '{r['old']}' ends at {r['removed_in']} "
            f"and is still read at version {version}; remove the row and its readers"
            for r in rows() if now >= _version(r["removed_in"])]


# The parser type of `--kind`: an old word is read as the current one.
kind_type = functools.partial(read, "reassessment_kind")

# The parser type of a check id given to `compass evidence approve`, `request`
# and `review`: a script written for 6.x still passes the old id until 8.0.0.
check_type = functools.partial(read, "check_id")
