"""A multiagent run stops at a ceiling, and goes past one only with a reason.

The subtask record counted tries and review rounds but capped neither, so
a run could retry one failing builder without limit. The ceilings are rules
in `governance/routing-policy.yml`; `compass issue subtask` refuses to open
work past them, and `compass check` refuses to land a run past them without
a stop reason backed by an evidence file.

Scenario ids: LC-A to LC-F, in the acceptance criteria of the issue
`loop-ceilings` (GitHub issue #300).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.governance import governance_drift  # noqa: E402
from compass_pkg.multiagent_check import (  # noqa: E402
    _check_multiagent_run_recorded)


def loop_ceilings(task):
    # Imported when called, so each test fails on its own behaviour while
    # the function is missing, not the whole file at collection.
    from compass_pkg.subtasks import loop_ceilings as resolve
    return resolve(task)

SLUG = "multi"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]
DOCS = "docs/compass/2026-10-03-multi"
ERROR = "AssertionError: expected 2, got 3\n  at tests/test_app.py:12"


def _git(root, *args):
    return subprocess.run([*GIT, *args], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()


def _manifest(root, risk="cross-cutting", created="2026-10-03"):
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True, exist_ok=True)
    (task / "manifest.yml").write_text(
        f"schema_version: '2.0'\nissue: {SLUG}\ncreated: '{created}'\n"
        f"status: active\nassessment: {{risk: {risk}, familiarity: "
        "brownfield-mapped, size: large, goal: delivery, role: engineer, "
        "labels: []}\n")
    evaluate = subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--issue", SLUG,
         "--write"], cwd=root, capture_output=True, text=True)
    assert evaluate.returncode == 0, evaluate.stderr


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("x = 1\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    _manifest(root)
    brief = root / DOCS / "subtasks" / "S1"
    brief.mkdir(parents=True)
    (brief / "briefing.md").write_text("Implement scenario A-1.\n")
    (brief / "stop.md").write_text("The builder failed the same way three "
                                   "times; the orchestrator stopped it.\n")
    return root


def _cli(root, *args):
    return subprocess.run([sys.executable, str(CLI), "issue", "subtask", *args,
                           "--issue", SLUG], cwd=root, capture_output=True,
                          text=True,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})


def _ok(root, *args):
    result = _cli(root, *args)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def _task(root):
    return yaml.safe_load((root / ".compass" / "work" / SLUG / "manifest.yml")
                          .read_text())


def _subtask(root, sid="S1"):
    return {s["id"]: s for s in _task(root).get("subtasks") or []}[sid]


def _add(root, sid="S1"):
    _ok(root, "add", sid, "--brief", f"{DOCS}/subtasks/S1/briefing.md",
        "--model", "sonnet", "--budget", "50000")


def _check(root):
    """Run the check from inside the fixture project, as `compass check`
    does, with every gate passed so the run is judged."""
    task = _task(root)
    for gate in task.get("gates") or []:
        gate["status"] = "pass"
    old = os.getcwd()
    os.chdir(root)
    try:
        return _check_multiagent_run_recorded(
            task, str(root / ".compass" / "work" / SLUG))
    finally:
        os.chdir(old)


# --- LC-A: the ceilings are policy rules -------------------------------------

def test_lc_a_shipped_ceilings_resolve_by_risk(repo):
    old = os.getcwd()
    os.chdir(repo)
    try:
        wide = loop_ceilings(_task(repo))
        _manifest(repo, risk="contained")
        narrow = loop_ceilings(_task(repo))
    finally:
        os.chdir(old)
    assert wide["builder_attempts"] == (3, "RP-LOOP-001")
    assert wide["review_rounds"] == (3, "RP-LOOP-002")
    assert wide["replans"] == (2, "RP-LOOP-004")
    assert wide["repeated_error"] == (3, "RP-LOOP-005")
    # The lowest matching limit wins, so the contained rule lowers it.
    assert narrow["review_rounds"] == (2, "RP-LOOP-003")


def test_lc_a_a_policy_without_the_rules_gives_no_ceiling_and_drift(repo):
    gov = repo / "governance"
    gov.mkdir()
    shutil.copy(ROOT / "governance" / "guardrails.yml", gov)
    policy = yaml.safe_load((ROOT / "governance" / "routing-policy.yml")
                            .read_text())
    del policy["routing_guardrails"]["loop_ceilings"]
    (gov / "routing-policy.yml").write_text(yaml.safe_dump(policy))
    old = os.getcwd()
    os.chdir(repo)
    try:
        assert loop_ceilings(_task(repo)) == {}
    finally:
        os.chdir(old)
    missing = " ".join(str(r) for r in
                       governance_drift(str(gov),
                                        str(ROOT / "governance")).missing_rules)
    for rid in ("RP-LOOP-001", "RP-LOOP-002", "RP-LOOP-003", "RP-LOOP-004",
                "RP-LOOP-005"):
        assert rid in missing, missing


# --- LC-B: the same error three times stops the subtask ----------------------

def test_lc_b_a_repeated_error_refuses_another_attempt(repo):
    _add(repo)
    # Whitespace differences are the same error.
    _ok(repo, "update", "S1", "--status", "reported")
    for text in (ERROR, ERROR.replace("\n  ", "\n    "), ERROR + "\n"):
        _ok(repo, "update", "S1", "--error", text)
    s = _subtask(repo)
    assert s["error_repeat_count"] == 3
    assert len(s["last_error_digest"]) == 16
    refused = _cli(repo, "update", "S1", "--attempt")
    assert refused.returncode != 0
    assert "same error 3 times" in refused.stderr
    assert "RP-LOOP-005" in refused.stderr
    assert "--stop-reason" in refused.stderr
    assert _subtask(repo)["attempts"] == 1
    listed = _ok(repo, "next").stdout
    assert "S1  refused" in listed and "same error 3 times" in listed


def test_lc_b_a_different_error_starts_the_count_again(repo):
    _add(repo)
    _ok(repo, "update", "S1", "--error", ERROR)
    _ok(repo, "update", "S1", "--error", ERROR)
    _ok(repo, "update", "S1", "--error", "ImportError: no module named app")
    assert _subtask(repo)["error_repeat_count"] == 1
    _ok(repo, "update", "S1", "--attempt")


# --- LC-C: the try ceiling ----------------------------------------------------

def test_lc_c_the_attempt_ceiling_refuses_a_fourth_attempt(repo):
    _add(repo)
    _ok(repo, "update", "S1", "--attempt")
    _ok(repo, "update", "S1", "--attempt")
    # The third try is under way and permitted: `next` says it is the
    # last one, not that the subtask is refused.
    listed = _ok(repo, "next").stdout
    assert "S1  refused" not in listed
    assert "attempt 3 of 3" in listed
    refused = _cli(repo, "update", "S1", "--attempt")
    assert refused.returncode != 0
    assert "3 attempts" in refused.stderr and "RP-LOOP-001" in refused.stderr
    assert _subtask(repo)["attempts"] == 3


def test_lc_c_a_refused_attempt_keeps_the_rest_of_the_call(repo):
    _add(repo)
    _ok(repo, "update", "S1", "--error", ERROR)
    _ok(repo, "update", "S1", "--error", ERROR)
    refused = _cli(repo, "update", "S1", "--error", ERROR, "--round", "fail",
                   "--attempt")
    assert refused.returncode != 0
    s = _subtask(repo)
    assert s["error_repeat_count"] == 3 and s["attempts"] == 1
    assert [r["verdict"] for r in s["review_rounds"]] == ["fail"]
    # The count the refused call recorded refuses the next try too.
    assert _cli(repo, "update", "S1", "--attempt").returncode != 0


# --- LC-D: past the review-round ceiling, landing needs a reason --------------

def _past_the_round_ceiling(repo):
    _add(repo)
    for verdict in ("fail", "fail", "fail", "pass"):
        _ok(repo, "update", "S1", "--round", verdict)
    _ok(repo, "update", "S1", "--status", "done")


def test_lc_d_rounds_past_the_ceiling_fail_the_check(repo):
    _past_the_round_ceiling(repo)
    passed, detail = _check(repo)
    assert passed is False
    assert "S1" in detail and "4 review rounds" in detail
    assert "RP-LOOP-002" in detail and "--stop-reason" in detail


def test_lc_d_the_round_past_the_ceiling_is_recorded_with_a_warning(repo):
    _add(repo)
    for verdict in ("fail", "fail", "fail"):
        _ok(repo, "update", "S1", "--round", verdict)
    out = _ok(repo, "update", "S1", "--round", "fail").stdout
    assert len(_subtask(repo)["review_rounds"]) == 4
    assert "past its ceiling" in out


def test_lc_d_a_stop_reason_with_evidence_lets_it_land(repo):
    _past_the_round_ceiling(repo)
    _ok(repo, "update", "S1", "--stop-reason", "four rounds: the brief was "
        "wrong twice", "--stop-evidence", f"{DOCS}/subtasks/S1/stop.md")
    stop = _subtask(repo)["stopped_reason"]
    assert stop["evidence"] == f"{DOCS}/subtasks/S1/stop.md"
    passed, detail = _check(repo)
    assert passed is True, detail


def test_lc_d_a_stopped_subtask_passes_without_being_done(repo):
    _add(repo)
    for _ in range(3):
        _ok(repo, "update", "S1", "--error", ERROR)
    _ok(repo, "update", "S1", "--stop-reason", "same error three times",
        "--stop-evidence", f"{DOCS}/subtasks/S1/stop.md")
    passed, detail = _check(repo)
    assert passed is True, detail


def test_lc_d_a_stop_reason_needs_an_existing_evidence_file(repo):
    _add(repo)
    missing = _cli(repo, "update", "S1", "--stop-reason", "stopped",
                   "--stop-evidence", f"{DOCS}/nope.md")
    assert missing.returncode != 0
    alone = _cli(repo, "update", "S1", "--stop-reason", "stopped")
    assert alone.returncode != 0
    assert "stopped_reason" not in _subtask(repo)


def test_lc_d_a_stop_whose_evidence_was_deleted_fails(repo):
    _past_the_round_ceiling(repo)
    _ok(repo, "update", "S1", "--stop-reason", "four rounds",
        "--stop-evidence", f"{DOCS}/subtasks/S1/stop.md")
    (repo / DOCS / "subtasks" / "S1" / "stop.md").unlink()
    passed, detail = _check(repo)
    assert passed is False and "stop.md" in detail


# --- LC-E: issues from before the ceilings ------------------------------------

def test_lc_e_an_older_issue_is_judged_as_before(repo):
    _manifest(repo, created="2026-10-02")
    _past_the_round_ceiling(repo)
    passed, detail = _check(repo)
    assert passed is True, detail


# --- LC-F: the replan ceiling --------------------------------------------------

def test_lc_f_the_replan_ceiling_refuses_a_third_replan(repo):
    _add(repo)
    _ok(repo, "replan", "--reason", "subtask S1 was two pieces of work")
    _ok(repo, "replan", "--reason", "S2 depends on S1 after all")
    refused = _cli(repo, "replan", "--reason", "one more try")
    assert refused.returncode != 0
    assert "2 replans" in refused.stderr and "RP-LOOP-004" in refused.stderr
    assert [r["reason"] for r in _task(repo)["replans"]] == [
        "subtask S1 was two pieces of work", "S2 depends on S1 after all"]
