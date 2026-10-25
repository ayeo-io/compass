"""Resolving a scenario's declared test ids against the tree.

A scenario names the test(s) that exercise it, and two questions follow from
that name: does the test exist, and does it actually run. Compass answers
both by reading the file, not by asking a test runner - it ships to projects
using pytest, jest, go test and cargo, and a per-runner adapter is far more
surface than the problem needs.

Kept apart from checks.py, which has a line cap; these two functions are one
job.
"""
from __future__ import annotations

# DEPENDENCY: standard library only.

import os
import re as _re


# Markers that mean "this test does not run". A scenario naming a permanently
# skipped test satisfies "the test exists" while proving nothing - a
# declaration that looks like coverage, which the traceability guardrail
# exists to stop.
#
# Text-based, like _test_id_resolves and for the same reason: Compass ships to
# pytest, jest, go test and cargo, and a per-runner adapter is more surface
# than the problem needs. It reads the lines immediately above the definition,
# where every one of these markers sits.
_SKIP_MARKERS = (
    "@pytest.mark.skip", "@pytest.mark.xfail", "@unittest.skip",
    "@skip", "@Ignore", "@Disabled",
)
_SKIP_CALL_FORMS = (".skip(", ".todo(", ".xfail(")


def _test_is_skipped(test_id, project_root):
    """Is this declared test marked so it never runs? True/False/None.

    None means no opinion - the id is not file-shaped, or the file cannot be
    read. Only a marker attached to THIS test counts; a skip elsewhere in the
    file is somebody else's.
    """
    tid = (test_id or "").strip()
    if "::" not in tid:
        return None
    file_part, name_part = tid.split("::", 1)
    name = name_part.split("::")[-1].split("[", 1)[0].strip()
    path = os.path.join(project_root, file_part.strip())
    if not name or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None

    for i, line in enumerate(lines):
        stripped = line.strip()
        is_def = (stripped.startswith(("def ", "async def ", "func "))
                  and name in stripped)
        if is_def:
            # Walk back over the decorator block directly above it.
            j = i - 1
            while j >= 0 and lines[j].strip().startswith("@"):
                if any(m in lines[j] for m in _SKIP_MARKERS):
                    return True
                j -= 1
            return False
        # jest/mocha style: it.skip("name", ...) / test.todo("name")
        if name in stripped and any(f in stripped for f in _SKIP_CALL_FORMS):
            return True
    return None


def _test_id_resolves(test_id, project_root):
    """Does this declared test id point at something real on disk?

    Returns True (resolves), False (does not), or None (not file-shaped, so
    this check has no opinion).

    Resolution is by text, not by asking a test runner. Compass ships to
    projects using pytest, jest, go test and cargo, and a per-runner adapter is
    far more surface than the problem needs. The trade is that a name appearing
    only inside a comment would pass; the failure being caught is a name that
    appears nowhere at all.

    Ids that are not file-shaped are skipped rather than failed. Test ids in the
    wild are not all file references, and a false positive on a legitimate id
    teaches people to switch the check off. `verifiable: narrative` remains the
    sanctioned way to declare a scenario has no automated test.
    """
    import re as _re
    _re_ws = _re.compile(r"\s")
    tid = (test_id or "").strip()
    if not tid:
        return None

    if "::" in tid:
        file_part, name_part = tid.split("::", 1)
        name = name_part.split("::")[-1]
        name = name.split("[", 1)[0].strip()      # drop pytest parametrisation
    else:
        file_part, name = tid, None
        # Only treat it as a path if it looks like one; otherwise no opinion.
        if "/" not in file_part or "." not in os.path.basename(file_part):
            return None

    # A path has no whitespace in it. Prose that happens to mention a file -
    # "grep: governance/strategies.md carries S7" - is a description, not a
    # reference, and must not be reported as a broken path.
    file_part = file_part.strip()
    if not file_part or _re_ws.search(file_part):
        return None

    path = os.path.join(project_root, file_part.strip())
    if not os.path.isfile(path):
        return False
    if not name:
        return True

    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
    except OSError:
        return False
    return _name_appears(name, body)


def _name_appears(name, body):
    """Is this test name written in this file?

    Two id shapes have to work.

    A flat id names the test directly. A NESTED id - jest's
    `outer > inner > the test` - names a path through describe blocks, and
    only its final segment is the test's own name. The chain as a whole is
    never written anywhere, so searching for it verbatim could not succeed on
    any correctly-declared id.

    Word boundaries are applied only on an end where they can be satisfied.
    `\\b` after a name ending in `@`, `)` or `.` needs a word character
    next, so such ids would never resolve, whatever is on disk. Dropping the
    boundaries entirely would be the opposite error - `test_plain` would match
    `test_plain_name`, letting a truncated or misspelled id pass - so each end
    keeps its boundary when that end is a word character.
    """
    import re as _re

    candidates = [name]
    if ">" in name:
        candidates.append(name.rsplit(">", 1)[-1])

    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        pattern = ""
        if candidate[0].isalnum() or candidate[0] == "_":
            pattern += r"(?<!\w)"
        pattern += _re.escape(candidate)
        if candidate[-1].isalnum() or candidate[-1] == "_":
            pattern += r"(?!\w)"
        if _re.search(pattern, body):
            return True
    return False
