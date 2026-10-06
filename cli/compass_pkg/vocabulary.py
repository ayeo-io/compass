# compass_pkg.vocabulary - display names and aliases for catalogue ids
"""Look up a catalogue entry's display name and resolve an alias to its id.

The `vocabulary` catalogue is keyed `<catalogue>.<id>` and holds a display
`name` and a list of `aliases`. An id is stable and is what every other part
of the configuration refers to; a name is what a person reads, and an alias is
another word a person may type for the same entry. These functions read a
resolved configuration (the output of `merge.resolve`) and change nothing.

Whether a name or alias is ambiguous is not decided here. `catalogue_check`
`check_vocabulary` refuses a resolved configuration in which one text belongs
to two entries, so `resolve` can take the first match without guessing.
"""
# DEPENDENCY: compass_pkg.catalogue_spec.
from __future__ import annotations

from compass_pkg import catalogue_spec as spec


def split_key(key):
    """`(catalogue, id)` for a vocabulary key, or None when the key is not
    `<catalogue>.<id>` with a catalogue that has display names. Ids can hold
    dots and catalogue names cannot, so the first dot separates them. The
    `vocabulary` catalogue has no names of its own."""
    if not isinstance(key, str) or "." not in key:
        return None
    catalogue, entry_id = key.split(".", 1)
    if catalogue not in spec.CATALOGUES or catalogue == "vocabulary" or not entry_id:
        return None
    return catalogue, entry_id


def normal(text):
    """`text` with spaces collapsed and case folded, so "Suite  Passed" and
    "suite passed" are one name. This is the one rule resolution and the
    collision check both apply to ids, names and aliases, so they cannot
    disagree."""
    return " ".join(str(text).split()).casefold()


def texts(entry):
    """`(role, text)` for one vocabulary entry: its display name, then each
    alias. An entry that is not a mapping has none; a malformed field is
    skipped, because `check_layer` already refuses it in a layer."""
    if not isinstance(entry, dict):
        return []
    found = [("name", entry["name"])] if isinstance(entry.get("name"), str) else []
    aliases = entry.get("aliases")
    if isinstance(aliases, list):
        found += [("alias", a) for a in aliases if isinstance(a, str)]
    return found


def display_name(config, catalogue, entry_id):
    """What to show for a catalogue entry: its vocabulary name, or the id
    when the vocabulary gives it none."""
    entry = (config.get("vocabulary") or {}).get(f"{catalogue}.{entry_id}")
    given = entry.get("name") if isinstance(entry, dict) else None
    return given if isinstance(given, str) and normal(given) else entry_id


def resolve(config, catalogue, text):
    """The id in `catalogue` that `text` names, or None. An exact id wins.
    Then an id, a display name or an alias matches ignoring case and extra
    spaces, the same rule the collision check applies, so a text that
    resolves here is never ambiguous in a configuration that passes it.
    Text that is not a string, or is blank, names nothing."""
    if not isinstance(text, str):
        return None
    table = config.get(catalogue) or {}
    if text in table:
        return text
    wanted = normal(text)
    if not wanted:
        return None
    for entry_id in table:
        if normal(entry_id) == wanted:
            return entry_id
    for key, entry in (config.get("vocabulary") or {}).items():
        parts = split_key(key)
        if parts is None or parts[0] != catalogue:
            continue
        if any(normal(candidate) == wanted for _, candidate in texts(entry)):
            return parts[1]
    return None
