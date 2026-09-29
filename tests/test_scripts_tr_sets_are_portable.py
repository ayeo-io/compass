"""No `tr` character set in the shell scripts reads differently on Linux.

GNU `tr` reads a `-` between two characters as a range; macOS's `tr` can
read it as a literal. A set such as `'|:- '` is a backwards range to GNU
`tr`, which then fails and prints nothing, so a script that works on a Mac
breaks in CI. A `-` is safe first or last in a set.

Scenario id: DTR-1, in the delivery approach of issue
`tr-range-fails-on-linux`.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TR_SET = re.compile(r"""\btr\s+(?:-[a-zA-Z]+\s+)*(['"])(.*?)\1""")


def _unsafe_sets(text):
    """Each set with a `-` that is not a plain range such as `a-z` or `0-9`.

    A range between two letters or two digits, in order, reads the same to
    both `tr`s. Any other `-` between two characters does not.
    """
    for match in TR_SET.finditer(text):
        chars = match.group(2)
        for i in range(1, len(chars) - 1):
            if chars[i] != "-":
                continue
            left, right = chars[i - 1], chars[i + 1]
            same_kind = ((left.islower() and right.islower())
                         or (left.isupper() and right.isupper())
                         or (left.isdigit() and right.isdigit()))
            if not (same_kind and left <= right):
                yield chars
                break


def test_dtr_1_no_tr_set_has_a_dash_between_two_characters():
    found = []
    for script in sorted((ROOT / "scripts").rglob("*.sh")):
        for n, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
            for chars in _unsafe_sets(line):
                found.append(f"{script.relative_to(ROOT)}:{n}: tr set '{chars}'")
    assert not found, "\n".join(found)


def test_dtr_1_the_scan_finds_a_planted_unsafe_set():
    assert list(_unsafe_sets("x=$(echo a | tr -d '|:- ')")) == ["|:- "]
    assert list(_unsafe_sets("x=$(echo a | tr -d '|: -')")) == []
    assert list(_unsafe_sets("x=$(echo a | tr 'a-z' 'A-Z')")) == []
