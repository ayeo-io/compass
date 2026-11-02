"""Scenario group E of the four-layer acceptance strategy, and scenario `TRC-A17`:
red and green records say which loop they belong to, and the check
`outer-loop-recorded` fails an in-scope issue with no outer-loop red, no
outer-loop green, or an outer-loop green from an older tree.

The specification is `acceptance-criteria.md` of the Compass issue
`loop-marking` (ayeo-io/compass-delivery#323). Each test names the scenario it
checks; `support.py` builds the projects.
"""
from __future__ import annotations

import json
import sys

import pytest

from tests.acceptance.atdd_strategy import support

CHECK = "outer-loop-recorded"
FAIL = "sh", "-c", "echo 'test_one FAILED'; exit 1"
PASS = "sh", "-c", "echo 'test_one PASSED'"


def _in_scope(tmp_path, slug="change", expected=None):
    project = support.Project(tmp_path / "repo")
    issue = project.issue(slug)
    code, out, err = issue.assess(expected=expected)
    assert code == 0, out + err
    return project, issue


def _record(issue, command, loop=None):
    """Run `compass tdd-red` or `compass tdd-green`, unbound, with `--loop` when given."""
    argv = [command, "--issue", issue.slug]
    if loop is not None:
        argv += ["--loop", loop]
    if command == "tdd-green" and loop == "outer":
        argv += support.NAMED
    return issue.must(*argv, "--", *(FAIL if command == "tdd-red" else PASS))


def _evidence(issue, name, loop=None):
    """`evidence/<name>.json`; an outer-loop record has `.outer` before `.json` (ADR-082)."""
    name += ".outer" if loop == "outer" else ""
    return json.loads((issue.dir / "evidence" / f"{name}.json").read_text(encoding="utf-8"))


def _row(document):
    rows = [c for c in document["checks"] if c["name"] == CHECK]
    assert len(rows) == 1, document["checks"]
    return rows[0]


# --- `TRC-E1` ------------------------------------------------------------------------------

@pytest.mark.parametrize("command, given, recorded", [
    ("tdd-red", "outer", "outer"),
    ("tdd-red", "inner", "inner"),
    ("tdd-green", "outer", "outer"),
    ("tdd-green", None, "inner"),
])
def test_trc_e1(tmp_path, command, given, recorded):
    """Red and green records say which loop they belong to."""
    _, issue = _in_scope(tmp_path)
    _record(issue, command, given)
    kind = "red" if command == "tdd-red" else "green"
    assert _evidence(issue, kind, recorded)["loop"] == recorded


# --- `TRC-E2` ------------------------------------------------------------------------------

def test_trc_e2(tmp_path):
    """A record with no loop field is read as inner."""
    _, issue = _in_scope(tmp_path)
    _record(issue, "tdd-red", "outer")
    _record(issue, "tdd-green", "outer")
    support.without_loop(issue, "green.outer")
    assert "loop" not in _evidence(issue, "green.outer")
    code, document = issue.check()
    row = _row(document)
    assert row["status"] == "fail", row
    assert "no outer-loop green" in row["detail"], row
    assert "1 with no loop field, read as inner" in row["detail"], row


# --- `TRC-E3` ------------------------------------------------------------------------------

def test_trc_e3(tmp_path):
    """An in-scope issue with only an inner-loop green fails the outer-loop check."""
    _, issue = _in_scope(tmp_path, slug="inner-only")
    _record(issue, "tdd-red", "outer")
    _record(issue, "tdd-green", "inner")
    code, document = issue.check()
    assert code == 1
    row = _row(document)
    assert row["status"] == "fail", row
    assert "inner-only" in row["detail"] and "no outer-loop green" in row["detail"], row
    assert "no outer-loop red" not in row["detail"], row


# --- `TRC-E4` ------------------------------------------------------------------------------

def test_trc_e4(tmp_path):
    """An unknown loop value is refused, and no record is written."""
    _, issue = _in_scope(tmp_path)
    code, out, err = issue.run("tdd-green", "--issue", issue.slug, "--loop", "middle",
                               "--", *PASS)
    assert code == 2, out + err
    assert not (issue.dir / "evidence" / "green.json").exists()
    assert "'outer'" in err and "'inner'" in err, err


# --- `TRC-E5` ------------------------------------------------------------------------------

def test_trc_e5(tmp_path):
    """An outer-loop green from an older tree does not count."""
    project, issue = _in_scope(tmp_path)
    _record(issue, "tdd-red", "outer")
    _record(issue, "tdd-green", "outer")
    code, document = issue.check()
    assert _row(document)["status"] == "pass", _row(document)
    older = _evidence(issue, "green", "outer")["tree_id"]
    (project.root / "README.md").write_text("changed after the green\n", encoding="utf-8")
    code, document = issue.check()
    assert code == 1
    row = _row(document)
    assert row["status"] == "fail", row
    assert "evidence/green.outer.json" in row["detail"], row
    assert f"recorded on tree {older[:12]}" in row["detail"], row
    assert "a different tree from the current one" in row["detail"], row


# --- `TRC-E6` ------------------------------------------------------------------------------

@pytest.mark.parametrize("reds", ["inner", "no loop field"])
def test_trc_e6(tmp_path, reds):
    """An in-scope issue with no outer-loop red fails."""
    _, issue = _in_scope(tmp_path, slug="no-outer-red")
    _record(issue, "tdd-red", "inner")
    if reds == "no loop field":
        support.without_loop(issue, "red")
        assert "loop" not in _evidence(issue, "red")
    # The candidate and the client are written from ayeo-io/compass-delivery#326; this
    # issue's green carries `attempts` 1 (requirements review Q1).
    _record(issue, "tdd-green", "outer")
    assert _evidence(issue, "green", "outer")["attempts"] == 1
    code, document = issue.check()
    assert code == 1
    row = _row(document)
    assert row["status"] == "fail", row
    assert "no-outer-red" in row["detail"] and "no outer-loop red" in row["detail"], row
    assert "no outer-loop green" not in row["detail"], row


# --- `TRC-A17` -----------------------------------------------------------------------------

@pytest.mark.parametrize("records", ["red and green", "validation, red and green"])
def test_trc_a17(tmp_path, records):
    """The records decide whether the strategy applies."""
    _, issue = _in_scope(tmp_path, expected="validation")
    assert issue.manifest()["acceptance_strategy"]["applies"] is False
    if records.startswith("validation"):
        issue.acceptance_start("validation")
    issue.red()
    issue.green()
    code, document = issue.check()
    assert code == 1
    row = _row(document)
    assert row["status"] == "fail", row
    assert "no outer-loop green" in row["detail"], row


# --- `TRC-E7` ------------------------------------------------------------------------------

def _quick_fix(tmp_path):
    """A quick fix in a project with the strategy on, its test committed and failing."""
    project = support.Project(tmp_path / "repo")
    root = project.root
    (root / "data").mkdir()
    (root / "data" / "greeting.txt").write_text("Hi\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_greeting.py").write_text(
        "import pathlib\n\n\ndef test_greeting():\n"
        "    p = pathlib.Path(__file__).resolve().parent.parent / 'data' / 'greeting.txt'\n"
        "    assert p.read_text().strip() == 'Hello'\n", encoding="utf-8")
    support.git(root, "add", "data/greeting.txt", "tests/test_greeting.py")
    support.git(root, "commit", "-q", "-m", "greeting")
    issue = support.Issue(project, "greet")
    issue.must("quick-fix", "start", "greet", "--risk", "trivial - a text change",
               "--familiarity", "brownfield-mapped - the file and its test exist",
               "--size", "atomic - one line", "--intent", "The greeting says Hello.",
               "--scenario", "Given the greeting, when it is read, then it says Hello.",
               "--test", "tests/test_greeting.py::test_greeting")
    return project, issue


@pytest.mark.parametrize("given, recorded, result", [
    (None, "outer", "pass"),
    ("inner", "inner", "fail"),
])
def test_trc_e7(tmp_path, given, recorded, result):
    """An in-scope quick fix records the outer loop by default."""
    project, issue = _quick_fix(tmp_path)
    assert issue.manifest()["delivery_approach"] == "quick-fix"
    loop = ["--loop", given] if given else []
    command = ["--", sys.executable, "-m", "pytest", "-q", "tests/test_greeting.py::test_greeting"]
    issue.must("tdd-red", "--issue", "greet", "--scenario", "TRC-001", *loop, *command)
    (project.root / "data" / "greeting.txt").write_text("Hello\n", encoding="utf-8")
    code, out, err = issue.run("quick-fix", "finish", "--issue", "greet", "--no-commit",
                               "-m", "Say Hello", "--release-note", "The greeting says Hello.",
                               *loop, *(() if given else support.NAMED), *command)
    assert _evidence(issue, "red-TRC-001", recorded)["loop"] == recorded
    assert _evidence(issue, "green-TRC-001", recorded)["loop"] == recorded
    assert (code == 0) == (result == "pass"), out + err
    code, document = issue.check()
    assert _row(document)["status"] == result, _row(document)
