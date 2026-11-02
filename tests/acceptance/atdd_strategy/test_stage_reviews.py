"""Scenario group D of the four-layer acceptance strategy: the reviews that end
stages 2 and 3 of the model are the `implement` and `verify` checkpoints.

`compass evidence request --checkpoint <stage>`, for `implement` or `verify`,
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
SIX = "assess, define, refine, plan, implement, verify"
#: The atdd skill's stage of each checkpoint that ends one.
STAGE_OF = {"refine": "Stage 1", "implement": "Stage 2", "verify": "Stage 3"}


def _project(tmp_path, autonomy="controlled"):
    project = support.Project(tmp_path / "repo")
    project.setting(None, owner=OWNER, autonomy=autonomy)
    if autonomy == "autonomous":
        from tests.project_readiness_support import meet_readiness_floor
        meet_readiness_floor(project.root)
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


def _end_of(issue, stage):
    """The records show `stage` done: its one scenario has a test run bound to
    it (`implement`), and every gate passed (`verify`)."""
    body = issue.manifest()
    body["scenarios"] = [{"id": "S-1", "title": "A person archives a workspace"}]
    body["evidence"] = list(body.get("evidence") or []) + [
        {"id": "EV-S-1", "type": "test-run", "scenario": "S-1", "path": "evidence/green.json"}]
    if stage == "verify":
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


def _records(issue, kind="checkpoint-approval"):
    return [e for e in issue.manifest().get("evidence") or [] if e.get("type") == kind]


# --- `TRC-D1` ------------------------------------------------------------------------------

@pytest.mark.parametrize("stage, checkpoint", [("stage 2", "implement"), ("stage 3", "verify")])
def test_trc_d1(tmp_path, stage, checkpoint):
    """The end of stage 2 and stage 3 can each ask for a review."""
    project = _project(tmp_path)
    issue = _issue(project)
    _end_of(issue, checkpoint)
    code, out, err = _request(issue, checkpoint)
    assert code == 0, out + err
    [request] = _pending(issue)
    assert (request["form"], request["value"]) == ("checkpoint", checkpoint), request
    assert request["review"] == {"stage": stage, "questions": _questions(checkpoint)}, request
    flat = " ".join(out.split())
    assert f"the {stage} review" in flat, out
    for question in _questions(checkpoint):
        assert question in flat, (question, out)
    assert "/compass:approve 1" in flat and "/compass:reject 1" in flat, out


# --- `TRC-D2` ------------------------------------------------------------------------------

def test_trc_d2(tmp_path):
    """The refine checkpoint reviews stage 1."""
    project = _project(tmp_path)
    issue = _issue(project)
    issue.must("tdd-red", "--issue", SLUG, "--loop", "outer", "--", *FAIL)
    code, out, err = _request(issue, "refine")
    assert code == 0, out + err
    [request] = _pending(issue)
    assert request["review"] == {"stage": "stage 1", "questions": _questions("refine")}, request
    flat = " ".join(out.split())
    for question in _questions("refine"):
        assert question in flat, (question, out)


# --- `TRC-D3` ------------------------------------------------------------------------------

def test_trc_d3(tmp_path):
    """A person's approval of a stage review is recorded."""
    project = _project(tmp_path)
    issue = _issue(project)
    _end_of(issue, "implement")
    assert _request(issue, "implement")[0] == 0
    result = _type(project, "approve")
    assert not result.block, result
    [record] = _records(issue)
    assert record["checkpoint"] == "implement" and record["approver"] == OWNER, record
    assert record["decision"] == "approved", record
    outcome = [o for o in issue.manifest()["checkpoint_outcomes"] if o["stage"] == "implement"]
    assert outcome == [{"stage": "implement", "outcome": "waited", "by": OWNER,
                        "at": record["timestamp"], "evidence": record["id"]}], outcome


# --- `TRC-D4` ------------------------------------------------------------------------------

def test_trc_d4(tmp_path):
    """A rejected stage review returns the issue to its stage."""
    reason = "the archive scenario reuses a fixed email address"
    project = _project(tmp_path)
    issue = _issue(project)
    _end_of(issue, "verify")
    assert _request(issue, "implement")[0] == 0
    assert not _type(project, "approve").block
    assert _next(issue).startswith("Waiting at the verify checkpoint"), _next(issue)
    assert _request(issue, "verify")[0] == 0
    result = _type(project, "reject", f"2 {reason}")
    assert not result.block, result
    closed = [r for r in _closed(issue) if r["value"] == "verify"]
    assert [(r["outcome"], r["reason"]) for r in closed] == [("rejected", reason)], closed
    assert [r["checkpoint"] for r in _records(issue)] == ["implement"]
    line = _next(issue)
    assert line.startswith("Verify"), line
    assert "stage 3 review" in line and reason in line, line


# --- `TRC-D5` ------------------------------------------------------------------------------

def test_trc_d5(tmp_path):
    """An agent under a delegation can approve a stage review."""
    from delegation_support import delegated
    project = _project(tmp_path)
    issue = _issue(project)
    _end_of(issue, "implement")
    until = (datetime.datetime.now().astimezone() + datetime.timedelta(hours=2)).strftime(
        "%Y-%m-%dT%H:%M")
    typed = _type(project, "delegate",
                  f"--agent {REVIEWER} --until {until} --on {SLUG} --for checkpoints")
    assert not typed.block, typed
    code, out, err = delegated(project.root, REVIEWER, "--issue", SLUG,
                               "--checkpoint", "implement")
    assert code == 0, out + err
    [record] = _records(issue)
    assert record["checkpoint"] == "implement", record
    assert record["via"] == "delegation" and record["delegation"] == "DL-1", record
    assert record["approved_by_agent"] == REVIEWER, record


# --- `TRC-D6` ------------------------------------------------------------------------------

def test_trc_d6(tmp_path):
    """An agent with no delegation cannot approve a stage review."""
    from delegation_support import delegated
    project = _project(tmp_path)
    issue = _issue(project)
    _end_of(issue, "verify")
    before = (issue.dir / "manifest.yml").read_bytes()
    code, out, err = delegated(project.root, REVIEWER, "--issue", SLUG, "--checkpoint", "verify")
    assert code == 2, out + err
    assert (issue.dir / "manifest.yml").read_bytes() == before
    assert "/compass:approve" in " ".join(err.split()), err


# --- `TRC-D7` ------------------------------------------------------------------------------

def test_trc_d7(tmp_path):
    """An unknown checkpoint name is refused."""
    project = _project(tmp_path)
    issue = _issue(project)
    _end_of(issue, "implement")
    code, out, err = _request(issue, "stage-4")
    assert code == 2, out + err
    assert not _pending(issue) and not _closed(issue)
    assert SIX in " ".join(err.split()), err


# --- `TRC-D8` ------------------------------------------------------------------------------

def test_trc_d8_controlled(tmp_path):
    """Under controlled autonomy, compass next stops and asks for the stage 2 review."""
    project = _project(tmp_path, "controlled")
    issue = _issue(project)
    _end_of(issue, "implement")
    out = _next(issue)
    flat = " ".join(out.split())
    assert out.startswith("Waiting at the implement checkpoint"), out
    assert "stage 2 review" in flat, out
    assert "compass evidence request --checkpoint implement" in flat, out


def test_trc_d8_autonomous(tmp_path):
    """Under autonomous autonomy, compass next shows the stage 2 hand-off, does not
    stop, and names the command that records the outcome skipped."""
    project = _project(tmp_path, "autonomous")
    issue = _issue(project)
    assert issue.manifest()["checkpoints"] == []
    _end_of(issue, "implement")
    out = _next(issue)
    flat = " ".join(out.split())
    assert out.startswith("Verify"), out
    assert "stage 2 review" in flat, out
    record = "compass issue checkpoint add implement --outcome skipped --by builder"
    assert record in flat, out
    issue.must(*record.split()[1:], "--issue", SLUG)
    outcome = [o for o in issue.manifest()["checkpoint_outcomes"] if o["stage"] == "implement"]
    assert [(o["outcome"], o["by"]) for o in outcome] == [("skipped", "builder")], outcome
    assert "stage 2 review" not in _next(issue)


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
    issue.must("tdd-green", "--issue", SLUG, "--loop", "outer", "--scenario", "S-1", *run)
    issue.must("issue", "render", "--issue", SLUG)
    return issue


def test_trc_d9(tmp_path):
    """A listed stage review with no outcome stops landing, not compass check."""
    project = _project(tmp_path)
    issue = _tested_issue(project)
    assert "verify" in issue.manifest()["checkpoints"]
    for stage in ("assess", "define", "refine", "plan", "implement"):
        assert _request(issue, stage)[0] == 0, stage
        assert not _type(project, "approve").block, stage
    assert "verify" not in {o["stage"] for o in issue.manifest()["checkpoint_outcomes"]}
    code, document = issue.check()
    assert code == 0, support.findings(document)
    assert not support.findings(document), support.findings(document)
    support.git(project.root, "add", "archive.py")
    code, out, err = issue.run("ship-commit", "-m", "Archive a workspace", "--issue", SLUG)
    assert code == 2, out + err
    flat = " ".join(err.split())
    assert "verify is listed in checkpoints with no outcome recorded" in flat, err
    assert "compass evidence approve --checkpoint verify" in flat, err
    assert "land_timestamp" not in issue.manifest()


# --- `TRC-D10` -----------------------------------------------------------------------------

@pytest.mark.parametrize("expected, checkpoints", [
    (None, ["assess", "define", "refine", "plan", "implement", "verify"]),
    ("validation", ["assess", "define", "refine", "plan"]),
])
def test_trc_d10(tmp_path, expected, checkpoints):
    """The `implement` and `verify` checkpoints are listed only where the strategy applies."""
    project = _project(tmp_path)
    issue = _issue(project, expected=expected)
    assert issue.manifest()["checkpoints"] == checkpoints
    assert issue.manifest()["acceptance_strategy"]["applies"] is (expected is None)
