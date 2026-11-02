"""An outer-loop red or green goes to its own file (ADR-082).

`compass tdd-red --loop outer --scenario <id>` writes `evidence/red-<id>.outer.json`
and `compass tdd-green --loop outer --scenario <id>` writes
`evidence/green-<id>.outer.json`; with no `--scenario` they write `red.outer.json`
and `green.outer.json`. An inner-loop record keeps `red-<id>.json` and
`green-<id>.json`. So an inner-loop record bound to the same scenario does not
replace the stage 1 red, and `outer-loop-recorded` still finds it.

Decided by the owner for ayeo-io/compass-delivery#324, after the stage 1 red
(scenario group C of the issue `atdd-strategy`) showed the overwrite.
"""
from __future__ import annotations

import json

from tests.acceptance.atdd_strategy import support

CHECK = "outer-loop-recorded"
FAIL = "sh", "-c", "echo 'test_place_order FAILED'; exit 1"
PASS = "sh", "-c", "echo 'test_place_order PASSED'"


def _row(issue):
    code, document = issue.check()
    rows = [c for c in document["checks"] if c["name"] == CHECK]
    assert len(rows) == 1, document["checks"]
    return rows[0]


def _names(issue):
    return sorted(p.name for p in (issue.dir / "evidence").glob("*.json")
                  if p.name.startswith(("red", "green")))


def _record(issue, name):
    return json.loads((issue.dir / "evidence" / name).read_text(encoding="utf-8"))


def _run(issue, verb, loop, command, scenario="TRC-1"):
    argv = [verb, "--issue", issue.slug, "--loop", loop]
    if scenario:
        argv += ["--scenario", scenario]
    if verb == "tdd-green" and loop == "outer":
        argv += support.NAMED
    return issue.must(*argv, "--", *command)


def test_an_inner_red_after_the_stage_1_red_keeps_both_records(tmp_path):
    project = support.Project(tmp_path / "repo")
    issue = support.stage_one_issue(project)
    issue.must("tdd-red", "--issue", issue.slug, "--loop", "outer", "--scenario", "TRC-1",
               "--", *support.PYTEST)
    _run(issue, "tdd-red", "inner", FAIL)
    assert _names(issue) == ["red-TRC-1.json", "red-TRC-1.outer.json"]
    assert _record(issue, "red-TRC-1.outer.json")["before_implement"] is True
    assert _record(issue, "red-TRC-1.json")["loop"] == "inner"
    assert (issue.dir / ".red").exists()
    row = _row(issue)
    assert "no outer-loop red" not in row["detail"], row
    assert "no outer-loop green" in row["detail"], row


def test_an_outer_green_after_inner_greens_is_found(tmp_path):
    project = support.Project(tmp_path / "repo")
    issue = support.stage_one_issue(project)
    _run(issue, "tdd-red", "outer", FAIL)
    _run(issue, "tdd-red", "inner", FAIL)
    _run(issue, "tdd-green", "inner", PASS)
    _run(issue, "tdd-green", "outer", PASS)
    _run(issue, "tdd-green", "inner", ("sh", "-c", "echo 'test_place_order PASSED'; true"))
    assert _names(issue) == ["green-TRC-1.json", "green-TRC-1.outer.json",
                             "red-TRC-1.json", "red-TRC-1.outer.json"]
    registered = sorted(e["path"] for e in issue.manifest()["evidence"]
                        if e.get("type") == "test-run")
    assert registered == ["evidence/green-TRC-1.json", "evidence/green-TRC-1.outer.json"]
    row = _row(issue)
    assert row["status"] == "pass", row
    assert "evidence/green-TRC-1.outer.json" in row["detail"], row


def test_unbound_outer_records_have_their_own_files(tmp_path):
    project = support.Project(tmp_path / "repo")
    issue = support.stage_one_issue(project)
    _run(issue, "tdd-red", "outer", FAIL, scenario=None)
    _run(issue, "tdd-green", "outer", PASS, scenario=None)
    assert _names(issue) == ["green.outer.json", "red.outer.json"]
    assert _row(issue)["status"] == "pass"


def test_records_written_before_the_split_still_count(tmp_path):
    """A record with no loop field stays inner where it is, and an outer-loop record
    written to `red-<id>.json` before this change still reads as outer."""
    project = support.Project(tmp_path / "repo")
    issue = support.stage_one_issue(project, approach="quick-fix")
    _run(issue, "tdd-red", "outer", FAIL)
    evidence = issue.dir / "evidence"
    # The layout of ADR-080: one file per binding, whatever the loop.
    (evidence / "red-TRC-1.outer.json").rename(evidence / "red-TRC-1.json")
    (evidence / "red-TRC-1.outer.log").rename(evidence / "red-TRC-1.log")
    _run(issue, "tdd-green", "inner", PASS)
    support.without_loop(issue, "green-TRC-1")
    assert "loop" not in _record(issue, "green-TRC-1.json")
    row = _row(issue)
    assert "no outer-loop red" not in row["detail"], row
    assert "1 with no loop field, read as inner" in row["detail"], row
    _run(issue, "tdd-green", "outer", PASS)
    assert _names(issue) == ["green-TRC-1.json", "green-TRC-1.outer.json", "red-TRC-1.json"]
    assert _row(issue)["status"] == "pass"
