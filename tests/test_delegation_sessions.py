"""Where a delegation lives and who the approver is, with sessions in linked
worktrees (issue `delegation-everywhere`, group C, store location).

`/compass:delegate` and `/compass:revoke` need no current issue. They keep the
delegation in the common store, in the main checkout, and take the approver
from that folder's `compass.yml`.

Scenario ids: `TRC-033` to `TRC-043`, `TRC-091` to `TRC-094`, `TRC-098`, `TRC-106`
and `TRC-107`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import CHECK, OWNER, SLUG, run, task_dir  # noqa: E402
from conftest import write_red_record  # noqa: E402
from delegation_support import (add_issue, add_worktree, copy_issue,  # noqa: E402
                                delegated, delegations, evidence_count, repo, set_owner,
                                type_)
from test_delegation_limits import _write_dl  # noqa: E402

ARCH = "compass:architect"


def test_TRC_041_a_delegation_typed_in_a_session_in_a_linked_worktree_is_kept(tmp_path):
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    add_issue(work, "wt-issue", current=True)
    result = type_(work, "", session="sess-w")
    assert not result.block, result
    assert delegations(top)["DL-1"]["covers_session"] == "sess-w"
    assert not delegations(work)


def test_TRC_091_compass_delegate_takes_the_approver_from_the_folder_that_holds_the_common(
        tmp_path):
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    add_issue(work, "wt-issue", current=True)
    set_owner(work, "pat")
    result = type_(work, "", session="sess-w")
    assert not result.block, result
    assert delegations(top)["DL-1"]["delegated_by"] == OWNER


def test_TRC_092_compass_delegate_is_refused_when_the_folder_that_holds_the_common_store(
        tmp_path):
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    add_issue(work, "wt-issue", current=True)
    set_owner(work, "pat")
    (top / "compass.yml").unlink()
    result = type_(work, "", session="sess-w")
    assert result.block and str(top) in result.message, result
    assert "compass.yml" in result.message, result.message
    assert not delegations(top) and not delegations(work)


@pytest.mark.parametrize("command", ["delegate", "revoke"])
def test_TRC_093_compass_delegate_and_compass_revoke_work_when_the_session_s_folder_names(
        tmp_path, command):
    top = repo(tmp_path)
    (top / ".compass" / "current-task").unlink()
    _write_dl(top, 1, until=None, format=2)
    result = type_(top, "", command=f"compass:{command}")
    assert not result.block, result
    found = delegations(top)
    if command == "delegate":
        assert found["DL-2"]["covers_session"] == "sess-1"
    else:
        assert found["DL-1"]["revoked_at"]


# --- who may approve under a delegation ----------------------------------------------------
# A delegated approval runs on a call ticket the pre-tool hook writes: the CLI takes the
# session and the caller from it and never from the environment.

def _yaml_of(path):
    import yaml
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _shown(path, cwd, text):
    """True when the CLI names `path`, in full or as it shortens it from `cwd`."""
    return str(path) in text or os.path.relpath(path, cwd) in text


def _linked(tmp_path, slug="wt-issue"):
    """A repository with a linked worktree W that holds the issue `slug`."""
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    copy_issue(top, work, slug)
    (work / ".compass" / "current-task").write_text(slug + "\n", encoding="utf-8")
    return top, work


def _approve_args(slug=SLUG):
    return ["--check", CHECK, "--scope", "s", "--issue", slug]


def test_TRC_033_the_main_agent_of_the_delegating_session_approves_under_a_session_delegation(
        tmp_path):
    top = repo(tmp_path)
    assert not type_(top, "", session="sess-S").block
    code, out, err = delegated(top, "main", *_approve_args(), session="sess-S")
    assert code == 0, out + err
    last = _yaml_of(task_dir(top) / "manifest.yml")["evidence"][-1]
    assert (last["approver"], last["approved_by_agent"], last["delegation"], last["via"]) == (
        OWNER, "main", "DL-1", "delegation")
    assert last["session_id"] == "sess-S"
    assert delegations(top)["DL-1"]["uses"] == 1


def test_TRC_034_a_subagent_of_the_delegating_session_approves_on_an_issue_in_another(
        tmp_path):
    top, work = _linked(tmp_path)
    assert not type_(top, "", session="sess-S").block
    code, out, err = delegated(work, ARCH, *_approve_args("wt-issue"), session="sess-S")
    assert code == 0, out + err
    wt = work / ".compass" / "work" / "wt-issue"
    last = _yaml_of(wt / "manifest.yml")["evidence"][-1]
    assert (last["approver"], last["approved_by_agent"], last["delegation"]) == (
        OWNER, ARCH, "DL-1")
    assert delegations(top)["DL-1"]["uses"] == 1
    devlog = (wt / "devlog.md").read_text(encoding="utf-8")
    assert ARCH in devlog and "DL-1" in devlog
    assert not delegations(work)


def test_TRC_035_an_agent_of_another_session_is_refused_under_a_session_delegation(
        tmp_path):
    top = repo(tmp_path)
    assert not type_(top, "", session="sess-S").block
    before = evidence_count(task_dir(top))
    code, out, err = delegated(top, ARCH, *_approve_args(), session="sess-T")
    assert code != 0 and "DL-1" in out + err, out + err
    assert "only the agents of the session it was typed in" in out + err, out + err
    assert evidence_count(task_dir(top)) == before


def test_TRC_036_an_agent_that_claims_the_delegating_session_s_id_in_its_command(tmp_path):
    top = repo(tmp_path)
    assert not type_(top, "", session="sess-S").block
    before = evidence_count(task_dir(top))
    code, out, err = delegated(top, "main", *_approve_args(), session="sess-T",
                               env={"CLAUDE_CODE_SESSION_ID": "sess-S"})
    assert code != 0, out + err
    assert evidence_count(task_dir(top)) == before
    assert delegations(top)["DL-1"]["uses"] == 0


def test_TRC_037_a_delegated_approval_that_reports_no_session_id_is_not_covered_by(tmp_path):
    top = repo(tmp_path)
    assert not type_(top, "", session="sess-S").block
    code, out, err = delegated(top, ARCH, *_approve_args(), session="")
    assert code != 0 and "DL-1" in out + err, out + err
    assert delegations(top)["DL-1"]["uses"] == 0


def test_TRC_038_two_sessions_delegations_each_cover_only_their_own_session(tmp_path):
    top, work = _linked(tmp_path)
    assert not type_(top, "", session="sess-S").block
    assert not type_(top, "", session="sess-T").block
    code, out, err = delegated(work, ARCH, *_approve_args("wt-issue"), session="sess-T")
    assert code == 0, out + err
    wt = work / ".compass" / "work" / "wt-issue"
    assert _yaml_of(wt / "manifest.yml")["evidence"][-1]["delegation"] == "DL-2"
    found = delegations(top)
    assert found["DL-1"]["uses"] == 0 and found["DL-2"]["uses"] == 1


def test_TRC_039_a_delegation_that_names_an_agent_covers_that_agent_in_any_session(
        tmp_path):
    top = repo(tmp_path)
    assert not type_(top, f"--agent {ARCH}", session="sess-S").block
    code, out, err = delegated(top, ARCH, *_approve_args(), session="sess-T")
    assert code == 0, out + err
    last = _yaml_of(task_dir(top) / "manifest.yml")["evidence"][-1]
    assert last["delegation"] == "DL-1" and last["approved_by_agent"] == ARCH


def test_TRC_040_a_delegation_that_names_an_agent_refuses_every_other_agent(tmp_path):
    top = repo(tmp_path)
    assert not type_(top, f"--agent {ARCH}", session="sess-S").block
    code, out, err = delegated(top, "compass:planner", *_approve_args(), session="sess-S")
    assert code != 0 and "no delegation in force names compass:planner" in out + err, out + err


def test_TRC_042_a_delegation_file_in_a_linked_worktree_s_own_folder_gives_no(tmp_path):
    top, work = _linked(tmp_path)
    stray = work / ".compass" / "delegations" / "DL-1.yml"
    _write_dl(work, 1, issues={"wt-issue": 1})
    before = stray.read_bytes()
    wt = work / ".compass" / "work" / "wt-issue"
    count = evidence_count(wt)
    code, out, err = delegated(work, ARCH, *_approve_args("wt-issue"))
    assert code != 0, out + err
    assert _shown(stray, work, out + err) and "no longer reads" in out + err, out + err
    assert "/compass:delegate" in out + err, out + err
    assert evidence_count(wt) == count and stray.read_bytes() == before


def test_TRC_043_a_delegation_written_by_compass_7_0_0_keeps_its_limits(tmp_path):
    top = repo(tmp_path)
    _write_dl(top, 1, issues={SLUG: 1}, labels=["auth"])
    code, out, err = delegated(top, ARCH, *_approve_args())
    assert code != 0 and "DL-1 covers only issues labeled auth" in out + err, out + err


def test_TRC_094_when_the_main_checkout_has_no_compass_folder_a_delegation_still_reaches(
        tmp_path):
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    work2 = add_worktree(top, "w2")
    copy_issue(top, work, "w-issue")
    copy_issue(top, work2, "w2-issue")
    for tree, slug in ((work, "w-issue"), (work2, "w2-issue")):
        (tree / ".compass" / "current-task").write_text(slug + "\n", encoding="utf-8")
    shutil.rmtree(top / ".compass")
    first = type_(work, "", session="sess-S")
    assert not first.block and "DL-1" in first.message, first
    code, out, err = delegated(work2, ARCH, *_approve_args("w2-issue"), session="sess-S")
    assert code == 0, out + err
    wt = work2 / ".compass" / "work" / "w2-issue"
    assert _yaml_of(wt / "manifest.yml")["evidence"][-1]["delegation"] == "DL-1"
    assert list(delegations(top)) == ["DL-1"]
    assert not delegations(work) and not delegations(work2)


def test_TRC_098_a_recorded_hook_input_from_a_real_subagent_in_a_linked_worktree(tmp_path):
    """The input Claude Code 2.1.309 sent for a subagent that changed into a linked
    worktree, through the real pre-tool hook, then the CLI."""
    import json
    import subprocess
    recorded = json.loads((ROOT / "tests" / "fixtures"
                           / "delegation-subagent-bash-input.json").read_text())["input"]
    top, work = _linked(tmp_path)
    write_red_record(task_dir(top))
    assert not type_(top, "", session=recorded["session_id"]).block
    words = ["--check", CHECK, "--scope", "s", "--issue", "wt-issue", "--delegated", "--as",
             recorded["agent_type"]]
    command = f"cd {work} && compass evidence approve " + " ".join(words)
    body = json.loads(json.dumps(recorded).replace("{{CWD}}", str(top)).replace(
        "{{TRANSCRIPT}}", str(tmp_path.parent / ("tr-" + tmp_path.name) / "t.jsonl")).replace("{{COMMAND}}", command))
    assert body["agent_id"] and body["agent_type"] == "general-purpose"
    hook = subprocess.run(["bash", str(ROOT / "hooks" / "pre-tool.sh")], input=json.dumps(body),
                          capture_output=True, text=True, cwd=top,
                          env=dict(os.environ, CLAUDE_PROJECT_DIR=str(top)))
    assert hook.returncode == 0, hook.stderr
    code, out, err = run(work, "evidence", "approve", *words)
    assert code == 0, out + err
    wt = work / ".compass" / "work" / "wt-issue"
    assert _yaml_of(wt / "manifest.yml")["evidence"][-1]["delegation"] == "DL-1"


@pytest.mark.parametrize("how", ["a script the hook never read", "outside Claude Code"])
def test_TRC_106_a_delegated_approval_with_no_pre_tool_hook_ticket_is_refused(
        tmp_path, how):
    top = repo(tmp_path)
    assert not type_(top, "", session="sess-S").block
    before = evidence_count(task_dir(top))
    env = {"CLAUDE_CODE_SESSION_ID": "sess-S"} if how == "outside Claude Code" else {}
    code, out, err = delegated(top, "main", "--check", CHECK, "--scope", "s", "--issue", SLUG,
                               session="sess-S", ticket=False, env=env)
    assert code != 0, out + err
    assert evidence_count(task_dir(top)) == before
    assert delegations(top)["DL-1"]["uses"] == 0


def test_TRC_107_a_delegated_approval_with_no_issue_is_refused_and_shows_the_issue_form(
        tmp_path):
    top = repo(tmp_path)
    assert not type_(top, "", session="sess-S").block
    before = evidence_count(task_dir(top))
    code, out, err = delegated(top, "main", "--check", CHECK, "--scope", "s",
                               session="sess-S")
    assert code != 0 and "--issue <slug>" in out + err, out + err
    assert evidence_count(task_dir(top)) == before
