"""Every string the CLI prints is scanned for retired vocabulary.

The prose ban patterns are capitalisation-scoped on purpose: "before critical
changes land" is correct English, so a lowercase machine value like
`expedition` is invisible to them by design. The printed-output guard is the
only thing standing behind that gap, and it stood behind two of the CLI's
twenty-four commands - the two whose output a test happened to run.

Defence in depth only works if the second layer is complete. At two of
twenty-four, a retired name printed by any of the other twenty-two escaped
both layers. That is the defect ADR-018 names, one level up: coverage
asserted rather than established.

So this does not run commands and read their output. It walks the syntax tree
of every module under `cli/`, finds every call that writes to the terminal,
and reads the string literals those calls carry. Coverage is then a property
of the walk rather than a list somebody remembered to extend.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli"
sys.path.insert(0, str(ROOT / "tests"))

# The writers. `print` and the two file-object methods cover every terminal
# write in this codebase; a new one shows up as an uncovered call rather than
# as silence, because test_every_writer_is_known below enumerates them.
WRITER_NAMES = {"print"}
WRITER_ATTRS = {"write", "writelines"}
# A raised CompassError is printed without a traceback, so its message is
# terminal output too - and it is where most of the retired verbs were,
# because an error message is written once and rarely re-read.
RAISED_TO_USER = {"CompassError"}

# Retired names that must not reach a user, read from the `retired_in_output`
# block of governance/terminology.yml: one list, so retiring a name is one
# edit. Deliberately separate from the prose scan's patterns, which are
# capitalisation-scoped and cannot see a lowercase machine value.
def _retired_in_output():
    import yaml
    block = yaml.safe_load(
        (ROOT / "governance" / "terminology.yml").read_text(encoding="utf-8")
    ).get("retired_in_output") or []
    patterns = {}
    for entry in block:
        pattern = re.escape(entry["name"])
        if entry.get("whole_word"):
            pattern = rf"\b{pattern}\b"
        patterns[entry["name"]] = re.compile(pattern)
    return patterns


RETIRED_IN_OUTPUT = _retired_in_output()

# A printed string may name a retired spelling when naming it IS the message -
# a redirect telling someone the verb moved, or an error quoting what it read.
# Written per line, like every other exemption, so the list stays countable.
ALLOW = re.compile(r"vocabulary-scan:\s*allow\b")


def _modules():
    for path in sorted(CLI.rglob("*.py")):
        if "vendor" in path.parts:      # third-party; not our vocabulary
            continue
        yield path
    yield CLI / "compass"


def _is_writer(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name) and func.id in WRITER_NAMES | RAISED_TO_USER:
        return True
    return isinstance(func, ast.Attribute) and func.attr in WRITER_ATTRS


def _strings_in(node: ast.AST):
    """Every string literal reachable from a call's arguments, including the
    literal halves of an f-string, which is where most output lives."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            yield sub.value


def _printed_strings():
    """(path, line, text) for every string literal written to the terminal."""
    for path in _modules():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:                       # pragma: no cover
            raise AssertionError(f"{path} does not parse: {exc}")
        lines = path.read_text(encoding="utf-8").splitlines()
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and _is_writer(node)):
                continue
            for text in _strings_in(node):
                line = getattr(node, "lineno", 1)
                window = "\n".join(lines[max(0, line - 1):line + 3])
                if ALLOW.search(window):
                    continue
                yield path.relative_to(ROOT), line, text


def test_no_printed_string_names_a_retired_verb_or_value():
    """The guard the two hand-written command tests were standing in for."""
    hits = []
    for rel, line, text in _printed_strings():
        for name, pattern in RETIRED_IN_OUTPUT.items():
            if pattern.search(text):
                hits.append(f"{rel}:{line}: prints {name!r} -> {text[:70]!r}")
    assert not hits, (
        "the CLI prints retired vocabulary, so the tool teaches a name it has "
        "retired:\n  " + "\n  ".join(sorted(hits)))


def test_the_walk_reaches_far_more_than_the_two_commands_it_replaces():
    """Coverage has to be established, not asserted.

    Without a floor this test would still pass if the walk silently stopped
    finding anything - which is how the guard it replaces failed.
    """
    found = list(_printed_strings())
    modules = {rel for rel, _, _ in found}
    assert len(found) > 200, (
        f"the walk found only {len(found)} printed strings; it previously "
        f"found over 200, so it has stopped reaching the output it guards")
    assert len(modules) >= 10, (
        f"the walk reached only {len(modules)} modules: {sorted(modules)}")


def test_a_planted_retired_name_is_reported():
    """Prove the guard can fail. The walk is the interesting half, so the
    planted string goes through the same walk rather than the regex alone."""
    src = 'def f():\n    print("run compass land-commit to finish")\n'
    tree = ast.parse(src)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_writer(node):
            found.extend(_strings_in(node))
    assert any(RETIRED_IN_OUTPUT["compass land-commit"].search(t) for t in found), (
        "the walk did not see a retired verb inside a plain print call, so it "
        "would not see one in the CLI either")


def test_the_retired_names_come_from_terminology():
    """The names the CLI must never print are listed once, in
    governance/terminology.yml, so retiring a name is one edit there rather
    than a second list here that a reviewer has to remember."""
    import yaml
    block = yaml.safe_load(
        (ROOT / "governance" / "terminology.yml").read_text(encoding="utf-8")
    ).get("retired_in_output")
    assert block, "governance/terminology.yml has no retired_in_output block"
    assert set(RETIRED_IN_OUTPUT) == {entry["name"] for entry in block}
    for entry in block:
        # Each name, printed, is reported: a pattern built wrongly from the
        # block would pass the equality above and catch nothing.
        printed = f"run {entry['name']} to finish"
        assert RETIRED_IN_OUTPUT[entry["name"]].search(printed), entry["name"]
