# compass_pkg.old_names - the old names a stored record still holds
"""One reader-side table of old names, each with the version that ends it.

The table is the `old_names:` section of `cli/migrate-map.yml`: kind, then old
word, then `{new, removed_in}`. 9.0.0 reads no typed old name from this
table (ADR-098): an old `--kind`, `--check` or refusal code given on the
command line fails as any unknown name does. The rows left are read from stored files only, and
a compatibility contract or a stored generation still needs each (VD-040):

- `reassessment_kind` and `check_id`: `word_map.tables()` builds those two
  sections from this table for a stored manifest (contract 3 reads the
  archive sample through `compass issue migrate`);
- `check_id` and `skill`: a stored generation and a copied 5.x governance are
  read through `word_map.map_layer`; 73 archived generations hold the old
  check id and skill name. 9.0.0 merged `behavior-mapping` and
  `bdd-specification` into `atdd` (#360): `bdd-specification` maps to `atdd`
  until 10.0.0, one major later, as a rename asks (ADR-024). Neither
  spelling of `behavior-mapping` maps to `atdd`, and the British row keeps
  its 7.0.0 target: a closed archived issue loads no skill, and `compass
  migrate` writes a new generation from the check set, which names `atdd`,
  for every open 8.x issue. So no session that needs the skill reads a
  stored generation that names either spelling. Contract 1 records the
  8.0.4 and 5.6.0 copies as they routed, so the skill name each holds stays
  (VD-042);
- `state_key` and `refusal_code`: contract 5 builds its project with
  `initialised` in the settings (`project_settings.state` reads it) and
  reads its recorded refusal code through `current`;
- `term`: `catalogue` stays the other form of the term `catalog`, which the
  accepted vocabulary decision (ADR-041) defines; the glossary marks it
  (`terminology_cmd`). #359 step 12 decides the words.

Every row but `bdd-specification` says `removed_in: 9.0.0`, so
`removal_problems` lists it until the owner answers the contract questions of
ADR-098 and the row goes.

`cli/aliases.yml` stays empty: these are values and keys, not CLI spellings.

This is a leaf. It imports nothing from `compass_pkg`, because `core` and
`word_map` both reach it. `word_map.bind` hands it the same reader of the data
file that `core` binds, and `_FALLBACK` is the copy for a checkout with no
framework install; a test keeps the copy equal to the file.
"""
# DEPENDENCY: standard library (sys); nothing from compass_pkg.
from __future__ import annotations

import sys

# The notice names the kind of name. Keys are the table's kinds.
LABELS = {
    "reassessment_kind": "kind",
    "check_id": "check",
    "skill": "skill",
    "refusal_code": "refusal code",
    "state_key": "state key",
    "term": "term",
}


def _row(new, removed_in="9.0.0"):
    return {"new": new, "removed_in": removed_in}


_FALLBACK = {
    "reassessment_kind": {"judgement": _row("judgment")},  # us-english-scan: allow - old name read until 9.0.0
    "check_id": {"dor-behaviour-is-gwt": _row("dor-behavior-is-gwt")},  # us-english-scan: allow - old name read until 9.0.0
    "skill": {"behaviour-mapping": _row("behavior-mapping"),  # us-english-scan: allow - old name read until 9.0.0
              "bdd-specification": _row("atdd", "10.0.0")},
    "refusal_code": {"not-initialised": _row("not-initialized")},  # us-english-scan: allow - old name read until 9.0.0
    "state_key": {"initialised": _row("initialized")},  # us-english-scan: allow - old name read until 9.0.0
    "term": {"catalogue": _row("catalog")},  # us-english-scan: allow - old name read until 9.0.0
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


def _notice(kind, old, new, removed_in="9.0.0"):
    key = (kind, old)
    if key in _SEEN:
        return
    _SEEN.add(key)
    print(f"compass: {LABELS.get(kind, kind)} {old} is now {new}; "
          f"the old word is read until {removed_in}.", file=sys.stderr)


def pick(mapping, kind, new, default=None):
    """`mapping[new]` when present (the new word wins when both are), else the
    value under its old word, with the notice, else `default`."""
    if new in mapping:
        return mapping[new]
    for row in rows(kind):
        if row["new"] == new and row["old"] in mapping:
            _notice(kind, row["old"], new, row["removed_in"])
            return mapping[row["old"]]
    return default


def _version(text):
    return tuple(int(part) for part in str(text).split(".") if part.isdigit())


def removal_problems(version):
    """One line for each row that ends at or before `version`; the row and the
    code that reads it must be deleted then."""
    now = _version(version)
    return [f"old_names: {r['kind']} '{r['old']}' ends at {r['removed_in']} "
            f"and is still read at version {version}; remove the row and its readers"
            for r in rows() if now >= _version(r["removed_in"])]

