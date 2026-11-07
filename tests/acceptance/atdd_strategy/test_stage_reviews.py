"""Scenario group D of the four-layer acceptance strategy: the reviews that end
stages 2 and 3 of the model are the `build` and `ship` checkpoints of the
four-stage path (ADR-092: the stage reviews are at build and ship), and the
stage 1 review is the `specify` checkpoint.

`compass evidence request --checkpoint <stage>`, for `build` or `ship`,
asks a person for the review and lists the questions the atdd skill gives for
the stage. A person answers with `/compass:approve` or `/compass:reject`, or an
agent answers under a delegation. The two checkpoints are listed only where
the strategy applies, and a listed one with no outcome stops landing, not
`compass check`.

The specification is `acceptance-criteria.md` of the Compass issue
`atdd-strategy` (ayeo-io/compass-delivery#327). Each test names the scenario it
checks; `support.py` builds the projects.
"""
from __future__ import annotations

import datetime
import re
import sys

import pytest

from tests.acceptance.atdd_strategy import support
from tests.acceptance.atdd_strategy.support import ROOT

sys.path.insert(0, str(ROOT / "tests"))

OWNER = "jed72"
REVIEWER = "compass:reviewer"
SLUG = "change"
FAIL = "sh", "-c", "echo 'test_one FAILED'; exit 1"
FOUR = "assess, specify, build, ship"
PASS = "sh", "-c", "echo 'test_one PASSED'"
#: The atdd skill's stage of each checkpoint that ends one.
STAGE_OF = {"specify": "Stage 1", "build": "Stage 2", "ship": "Stage 3"}


def _project(tmp_path, autonomy="controlled"):
    project = support.Project(tmp_path / "repo")
    project.setting(None, owner=OWNER, autonomy=autonomy)
    return project


def _issue(project, expected=None):
    """A regular issue, assessed, with its delivery-approach record, made the
    project's current issue."""
    issue = project.issue(SLUG)
    code, out, err = issue.assess(expected=expected)
    assert code == 0, out + err
    (issue.dir / "delivery-approach.md").write_text("# Delivery approach\n", encoding="utf-8")
    (project.root / ".compass" / "current-task").write_text(SLUG + "\n", encoding="utf-8")
    return issue


def _specified(issue):
    """The records show specify done: one scenario with an id, an intent and a
    declared test, and the `specify` checkpoint answered where it is listed."""
    issue.must("scenario", "add", "S-1", "--issue", SLUG, "--title",
               "A person archives a workspace", "--intent", "INT-1",
               "--test", "tests/test_archive.py::test_archive")
    if "specify" in issue.manifest()["checkpoints"]:
        assert _request(issue, "specify")[0] == 0
        assert not _type(issue.project, "approve").block


def _end_of(issue, stage):
    """The records show `stage` done: specify, then a red and a green bound to
    the one scenario (`build`), and every gate passed (`ship`)."""
    _specified(issue)
    issue.must("tdd-red", "--issue", SLUG, "--scenario", "S-1", "--", *FAIL)
    issue.must("tdd-green", "--issue", SLUG, "--scenario", "S-1", "--", *PASS)
    if stage == "ship":
        body = issue.manifest()
        for gate in body["gates"]:
            gate["status"] = "pass"
        issue.write_manifest(body)


def _questions(stage):
    """The questions under the stage's heading in the atdd skill's stage reviews."""
    text = (ROOT / "skills" / "atdd" / "references" / "stage-reviews.md").read_text(
        encoding="utf-8")
    section = text.split(f"## {STAGE_OF[stage]} - ", 1)[1].split("\n## ", 1)[0]
    return [line[2:] for line in section.splitlines() if line.startswith("- ")]


def _pending(issue):
    import yaml
    folder = issue.dir / "approval-requests" / "pending"
    return [yaml.safe_load(p.read_text(encoding="utf-8"))
            for p in sorted(folder.glob("*.yml"))] if folder.is_dir() else []


def _closed(issue):
    import yaml
    folder = issue.dir / "approval-requests" / "closed"
    return [yaml.safe_load(p.read_text(encoding="utf-8"))
            for p in sorted(folder.glob("*.yml"))] if folder.is_dir() else []


def _request(issue, stage):
    return issue.run("evidence", "request", "--checkpoint", stage, "--issue", SLUG)


def _type(project, command, args=""):
    """The person types `/compass:<command> <args>` in Claude Code: the Stop hook
    shows the pending requests first, then the prompt hook answers."""
    from approval_support import event
    from compass_pkg import approval_requests, prompt_approval
    approval_requests.stop_message(str(project.root / ".compass"), {})
    return prompt_approval.handle(event(project.root, command=f"compass:{command}", args=args),
                                  {}, plugin_root=str(ROOT))


def _next(issue):
    code, out, err = issue.run("next", "--issue", SLUG)
    assert code == 0, out + err
    return out


def _stage(issue):
    """The legacy stage the resolver gives, which the reviews act on. `compass
    next` shows it as the path stage it maps to (ADR-092)."""
    from compass_pkg import next_cmd
    from compass_pkg.core import normalize_spine
    return next_cmd._current_phase_from_task(
        next_cmd._typed(normalize_spine(issue.manifest())), str(issue.dir))


def _records(issue, kind="checkpoint-approval"):
    return [e for e in issue.manifest().get("evidence") or [] if e.get("type") == kind]


# --- `TRC-D1` ------------------------------------------------------------------------------

@pytest.mark.parametrize("stage, checkpoint", [("stage 2", "build"), ("stage 3", "ship")])
def test_trc_d1(tmp_path, stage, checkpoint):
    """The end of stage 2 and stage 3 can each ask for a review."""
    project = _project(tmp_path)
    issue = _issue(project)
    _end_of(issue, checkpoint)
    code, out, err = _request(issue, checkpoint)
    assert code == 0, out + err
    # Request 1 was the `specify` checkpoint, which controlled autonomy lists.
    [request] = _pending(issue)
    assert (request["form"], request["value"]) == ("checkpoint", checkpoint), request
    assert request["review"] == {"stage": stage, "questions": _questions(checkpoint)}, request
    flat = " ".join(out.split())
    assert f"the {stage} review" in flat, out
    for question in _questions(checkpoint):
        assert question in flat, (question, out)
    assert "/compass:approve 2" in flat and "/compass:reject 2" in flat, out


# --- `TRC-D2` ------------------------------------------------------------------------------

def test_trc_d2(tmp_path):
    """The specify checkpoint reviews stage 1."""
    project = _project(tmp_path)
    issue = _issue(project)
    # The end of specify is its scenario with an id, an intent and a test. The
    # outer-loop red is a stage 1 red, which by design does not mark a stage
    # done (ADR-081).
    issue.must("scenario", "add", "S-1", "--issue", SLUG, "--title",
               "A person archives a workspace", "--intent", "INT-1",
               "--test", "tests/test_archive.py::test_archive")
    issue.must("tdd-red", "--issue", SLUG, "--loop", "outer", "--", *FAIL)
    code, out, err = _request(issue, "specify")
    assert code == 0, out + err
    [request] = _pending(issue)
    assert request["review"] == {"stage": "stage 1", "questions": _questions("specify")}, request
    flat = " ".join(out.split())
    for question in _questions("specify"):
        assert question in flat, (question, out)


# --- `TRC-D3` ------------------------------------------------------------------------------

def test_trc_d3(tmp_path):
    """A person's approval of a stage review is recorded."""
    project = _project(tmp_path)
    issue = _issue(project)
    _end_of(issue, "build")
    assert _request(issue, "build")[0] == 0
    result = _type(project, "approve")
    assert not result.block, result
    # The first record is the `specify` checkpoint's, which `_end_of` answered.
    assert [r["checkpoint"] for r in _records(issue)] == ["specify", "build"]
    record = _records(issue)[-1]
    assert record["checkpoint"] == "build" and record["approver"] == OWNER, record
    assert record["decision"] == "approved", record
    outcome = [o for o in issue.manifest()["checkpoint_outcomes"] if o["stage"] == "build"]
    assert outcome == [{"stage": "build", "outcome": "waited", "by": OWNER,
                        "at": record["timestamp"], "evidence": record["id"]}], outcome


# --- `TRC-D4` ------------------------------------------------------------------------------

def test_trc_d4(tmp_path):
    """A rejected stage review returns the issue to its stage."""
    reason = "the archive scenario reuses a fixed email address"
    project = _project(tmp_path)
    issue = _issue(project)
    _end_of(issue, "ship")
    assert _request(issue, "build")[0] == 0
    assert not _type(project, "approve").block
    assert _next(issue).startswith("Waiting at the ship checkpoint"), _next(issue)
    assert _request(issue, "ship")[0] == 0
    # Requests 1 and 2 were the `specify` and `build` checkpoints.
    result = _type(project, "reject", f"3 {reason}")
    assert not result.block, result
    closed = [r for r in _closed(issue) if r["value"] == "ship"]
    assert [(r["outcome"], r["reason"]) for r in closed] == [("rejected", reason)], closed
    assert [r["checkpoint"] for r in _records(issue)] == ["specify", "build"]
    line = _next(issue)
    # The stage 3 review sends the issue back to `ship`.
    assert line.startswith("Ship"), line
    assert "stage 3 review" in line and reason in line, line


# --- `TRC-D5` ------------------------------------------------------------------------------

def test_trc_d5(tmp_path):
    """An agent under a delegation can approve a stage review."""
    from delegation_support import delegated
    project = _project(tmp_path)
    issue = _issue(project)
    _end_of(issue, "build")
    until = (datetime.datetime.now().astimezone() + datetime.timedelta(hours=2)).strftime(
        "%Y-%m-%dT%H:%M")
    typed = _type(project, "delegate",
                  f"--agent {REVIEWER} --until {until} --on {SLUG} --for checkpoints")
    assert not typed.block, typed
    code, out, err = delegated(project.root, REVIEWER, "--issue", SLUG,
                               "--checkpoint", "build")
    assert code == 0, out + err
    # The person answered the `specify` checkpoint in `_end_of`.
    specify, record = _records(issue)
    assert specify["checkpoint"] == "specify" and specify["via"] != "delegation", specify
    assert record["checkpoint"] == "build", record
    assert record["via"] == "delegation" and record["delegation"] == "DL-1", record
    assert record["approved_by_agent"] == REVIEWER, record


# --- `TRC-D6` ------------------------------------------------------------------------------

def test_trc_d6(tmp_path):
    """An agent with no delegation cannot approve a stage review."""
    from delegation_support import delegated
    project = _project(tmp_path)
    issue = _issue(project)
    _end_of(issue, "ship")
    before = (issue.dir / "manifest.yml").read_bytes()
    code, out, err = delegated(project.root, REVIEWER, "--issue", SLUG, "--checkpoint", "ship")
    assert code == 2, out + err
    assert (issue.dir / "manifest.yml").read_bytes() == before
    assert "/compass:approve" in " ".join(err.split()), err


# --- `TRC-D7` ------------------------------------------------------------------------------

def test_trc_d7(tmp_path):
    """An unknown checkpoint name is refused."""
    project = _project(tmp_path)
    issue = _issue(project)
    _end_of(issue, "build")
    pending, closed = _pending(issue), _closed(issue)
    code, out, err = _request(issue, "stage-4")
    assert code == 2, out + err
    assert _pending(issue) == pending and _closed(issue) == closed
    assert FOUR in " ".join(err.split()), err


# --- `TRC-D8` ------------------------------------------------------------------------------

def test_trc_d8_controlled(tmp_path):
    """Under controlled autonomy, compass next stops and asks for the stage 2 review."""
    project = _project(tmp_path, "controlled")
    issue = _issue(project)
    _end_of(issue, "build")
    out = _next(issue)
    flat = " ".join(out.split())
    assert out.startswith("Waiting at the build checkpoint"), out
    assert "stage 2 review" in flat, out
    assert "compass evidence request --checkpoint build" in flat, out


def test_trc_d8_autonomous(tmp_path):
    """Under autonomous autonomy, compass next shows the stage 2 hand-off, does not
    stop, and names the command that records the outcome skipped."""
    project = _project(tmp_path, "autonomous")
    issue = _issue(project)
    assert issue.manifest()["checkpoints"] == []
    _end_of(issue, "build")
    out = _next(issue)
    flat = " ".join(out.split())
    assert _stage(issue) == "ship"
    assert out.startswith("Ship"), out
    assert "stage 2 review" in flat, out
    record = "compass issue checkpoint add build --outcome skipped --by builder"
    assert record in flat, out
    issue.must(*record.split()[1:], "--issue", SLUG)
    outcome = [o for o in issue.manifest()["checkpoint_outcomes"] if o["stage"] == "build"]
    assert [(o["outcome"], o["by"]) for o in outcome] == [("skipped", "builder")], outcome
    assert "stage 2 review" not in _next(issue)


def test_trc_d8_autonomous_the_stage_3_review_is_named_once_every_gate_passed(tmp_path):
    """Under autonomous autonomy, the path's `ship` stage is done only once the
    issue closes, so its hand-off is named once every gate has passed."""
    project = _project(tmp_path, "autonomous")
    issue = _issue(project)
    _end_of(issue, "ship")
    issue.must("issue", "checkpoint", "add", "build", "--outcome", "skipped", "--by",
               "builder", "--issue", SLUG)
    flat = " ".join(_next(issue).split())
    record = "compass issue checkpoint add ship --outcome skipped --by verifier"
    assert "stage 3 review" in flat and record in flat, flat


# --- `TRC-D9` ------------------------------------------------------------------------------

def _tested_issue(project):
    """An in-scope issue whose one scenario has an outer-loop red and green from a
    real pytest run, its pages rendered: an issue `compass check` passes."""
    issue = _issue(project)
    root, test = project.root, "tests/test_archive.py::test_archive"
    run = ["--", sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", test]
    (root / "archive.py").write_text("def archive():\n    return None\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_archive.py").write_text(
        "from archive import archive\n\n\ndef test_archive():\n"
        "    assert archive() == 'archived'\n", encoding="utf-8")
    support.git(root, "add", "-A")
    support.git(root, "commit", "-q", "-m", "archive test")
    issue.must("scenario", "add", "S-1", "--issue", SLUG, "--title",
               "A person archives a workspace", "--intent", "INT-1", "--test", test)
    issue.must("tdd-red", "--issue", SLUG, "--loop", "outer", "--scenario", "S-1", *run)
    (root / "archive.py").write_text("def archive():\n    return 'archived'\n", encoding="utf-8")
    issue.must("tdd-green", "--issue", SLUG, "--loop", "outer", "--scenario", "S-1",
               *support.NAMED, *run)
    # The isolation proof and the layering record (ADR-086), which the regular
    # approach needs at verify.
    suite = " ".join(run[1:-1])
    issue.must("isolation", "record", "--issue", SLUG, *support.NAMED, "--parallel",
               f"{suite} tests", "--repeat", f"{suite} {{tests}}")
    issue.must("layering", "record", "--issue", SLUG, "--", "sh", "-c", "exit 0")
    return issue


def test_trc_d9(tmp_path):
    """A listed stage review with no outcome stops landing, not compass check."""
    project = _project(tmp_path)
    issue = _tested_issue(project)
    assert "ship" in issue.manifest()["checkpoints"]
    for stage in ("assess", "specify", "build"):
        assert _request(issue, stage)[0] == 0, stage
        assert not _type(project, "approve").block, stage
    assert "ship" not in {o["stage"] for o in issue.manifest()["checkpoint_outcomes"]}
    code, document = issue.check()
    assert code == 0, support.findings(document)
    # Advice never stops an issue: this project names no acceptance support
    # code, so `acceptance-support-present` adds its claim limit as advice.
    blocking = [f for f in support.findings(document) if f[1] != "advisory"]
    assert not blocking, blocking
    support.git(project.root, "add", "archive.py")
    code, out, err = issue.run("ship-commit", "-m", "Archive a workspace", "--issue", SLUG)
    assert code == 2, out + err
    flat = " ".join(err.split())
    assert "ship is listed in checkpoints with no outcome recorded" in flat, err
    # Commit 1608539a (ADR-097 decision 5): the fix line asks the person
    # for an answer and stops; it no longer tells an agent to approve.
    assert "compass evidence request --checkpoint ship --issue " + SLUG in flat, err
    assert "/compass:approve" in flat, err
    assert "land_timestamp" not in issue.manifest()


def test_trc_d9_compass_next_asks_for_the_stage_3_review_once_every_gate_passed(tmp_path):
    """The `next:` command names the listed `ship` checkpoint once nothing else is
    owed, so the agent asks for the review before `compass ship-commit` refuses."""
    import json

    from compass_pkg import effective, item_records
    project = _project(tmp_path)
    issue = _tested_issue(project)
    for stage in ("assess", "specify", "build"):
        assert _request(issue, stage)[0] == 0, stage
        assert not _type(project, "approve").block, stage
    body = issue.manifest()
    items = [c for c, _ in item_records.listed_checks(effective.view_or_legacy(str(issue.dir)),
                                                      "dod")]
    (issue.dir / "evidence" / "review.txt").write_text("reviewed\n", encoding="utf-8")
    body["evidence"] = body["evidence"] + [
        {"id": "EV-DOD", "type": "manual-review", "path": "evidence/review.txt",
         "meets": items},
        {"id": "EV-GATE", "type": "command-output", "path": "evidence/review.txt"}]
    for gate in body["gates"]:
        gate.update(status="pass", evidence=["EV-GATE"])
    issue.write_manifest(body)
    code, out, err = issue.run("next", "--issue", SLUG, "--json")
    assert code == 0, out + err
    assert json.loads(out)["next"] == ("compass evidence request --checkpoint ship, "
                                       "then stop for /compass:approve"), out


# --- `TRC-D10` -----------------------------------------------------------------------------

@pytest.mark.parametrize("expected, checkpoints", [
    (None, ["assess", "specify", "build", "ship"]),
    ("validation", ["assess", "specify"]),
])
def test_trc_d10(tmp_path, expected, checkpoints):
    """The `build` and `ship` checkpoints are listed only where the strategy applies."""
    project = _project(tmp_path)
    issue = _issue(project, expected=expected)
    assert issue.manifest()["checkpoints"] == checkpoints
    assert issue.manifest()["acceptance_strategy"]["applies"] is (expected is None)
