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
    return issue.must(*argv, "--", *(FAIL if command == "tdd-red" else PASS))


def _evidence(issue, name):
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
    assert _evidence(issue, "red" if command == "tdd-red" else "green")["loop"] == recorded


# --- `TRC-E2` ------------------------------------------------------------------------------

def test_trc_e2(tmp_path):
    """A record with no loop field is read as inner."""
    _, issue = _in_scope(tmp_path)
    _record(issue, "tdd-red", "outer")
    _record(issue, "tdd-green", "outer")
    support.without_loop(issue, "green")
    assert "loop" not in _evidence(issue, "green")
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
    older = _evidence(issue, "green")["tree_id"]
    (project.root / "README.md").write_text("changed after the green\n", encoding="utf-8")
    code, document = issue.check()
    assert code == 1
    row = _row(document)
    assert row["status"] == "fail", row
    assert "evidence/green.json" in row["detail"], row
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
    # issue's green carries attempts 1 (requirements review Q1).
    _record(issue, "tdd-green", "outer")
    assert _evidence(issue, "green")["attempts"] == 1
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
