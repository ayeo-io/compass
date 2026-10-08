#!/usr/bin/env python3
"""Aliases for renamed CLI verbs, and hints for spellings no release holds.

`cli/aliases.yml` is the one table. `rewrite` turns a released old spelling
into the new one before the command line is parsed, so the command that runs,
its standard output and its exit code are the new verb's. The only difference
is one notice on standard error. `hint_for` adds one line to the error of a
command line that fails to parse, when it starts with an old spelling that no
release holds. Nothing runs for a hint.

The notice and the hint are built from the table, so the old spellings appear
in this module only as data.

DEPENDENCY: the bundled PyYAML.
"""
from __future__ import annotations

import os
import sys

import yaml

TABLE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "aliases.yml")
HELP_FLAGS = ("-h", "--help")
REMOVED_AT = (7, 0, 0)


def load_table(path=None):
    """The alias and hint rows, as `{"aliases": [...], "hints": [...]}`."""
    with open(path or TABLE_PATH, encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return {"aliases": list(data.get("aliases") or []),
            "hints": list(data.get("hints") or [])}


def _starts_with(argv, tokens):
    return list(argv[:len(tokens)]) == list(tokens)


def rewrite(argv, table=None):
    """`(argv, notice)`: the command line with a released old spelling replaced
    by the new one, and the notice to print; `(argv, None)` when no row
    matches. The longest matching `old` wins."""
    table = table or load_table()
    argv = list(argv)
    best = None
    for row in table["aliases"]:
        if _starts_with(argv, row["old"]) and (
                best is None or len(row["old"]) > len(best["old"])):
            best = row
    if best is None:
        return argv, None
    old, new = best["old"], best["new"]
    rest = argv[len(old):]
    if _starts_with(new, old):
        extra = new[len(old):]
        # Already the new spelling, or a request for the group's own help.
        if _starts_with(rest, extra) or (rest and rest[0] in HELP_FLAGS):
            return argv, None
    notice = (f"compass: '{' '.join(old)}' is now '{' '.join(new)}'; "
              f"the old spelling works until 7.0.0.")
    return list(new) + rest, notice


def hint_for(argv, table=None):
    """The line to add to a parse error, or None. It names the new spelling of
    an old spelling no release holds, unless the command line already uses the
    new one."""
    table = table or load_table()
    for row in table["hints"]:
        if _starts_with(argv, row["old"]) and not _starts_with(argv, row["new"]):
            return f"'{' '.join(row['old'])}' is now '{' '.join(row['new'])}'."
    return None


def _version_tuple(version):
    parts = []
    for piece in str(version).split(".")[:3]:
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts + [0] * (3 - len(parts)))


def removal_problems(version, table=None):
    """What stops the table from ending at 7.0.0: a row still listed once the
    package version is 7.0.0 or later."""
    table = table or load_table()
    if _version_tuple(version) < REMOVED_AT:
        return []
    return [f"{kind}: '{' '.join(row['old'])}' is still listed at version {version}; "
            f"remove it, the aliases and hints end at 7.0.0"
            for kind in ("aliases", "hints") for row in table[kind]]


def parse_with_aliases(build_parser, raw, parse):
    """Rewrite a released old spelling, print its notice, then parse.

    `parse(parser, argv)` is `verb_help.parse_command_line`. When the parse
    fails with a usage error, a hint for an unreleased old spelling follows
    the error."""
    argv, notice = rewrite(raw)
    if notice:
        sys.stderr.write(notice + "\n")
    try:
        return parse(build_parser(), argv)
    except SystemExit as exc:
        if exc.code == 2:
            line = hint_for(argv)
            if line:
                sys.stderr.write(line + "\n")
        raise
