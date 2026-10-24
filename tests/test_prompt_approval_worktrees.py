"""/compass:approve and /compass:reject across git worktrees (issue
`delegation-everywhere`, group D).

A number names a pending request on the current issue of a worktree (the issue
its `.compass/current-task` names). `--issue <slug>` reaches any issue in any
worktree. The approver is read from the folder that holds the chosen request,
after the choice.

Scenario ids: `TRC-044` to `TRC-058`, `TRC-084` to `TRC-090` and `TRC-097`. Each
test name starts with its scenario id.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import CHECK, OWNER, SLUG, run  # noqa: E402
from delegation_support import (add_worktree, copy_issue, repo, set_owner,  # noqa: E402
                                type_)

WT = "wt-issue"


def _setup(tmp_path):
    """The main checkout (issue `feature` is its current issue) and a linked
    worktree W whose current issue is `wt-issue`."""
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    copy_issue(top, work, WT)
    (work / ".compass" / "current-task").write_text(WT + "\n", encoding="utf-8")
    return top, work


def _task(project, slug):
    return project / ".compass" / "work" / slug


def _request(project, slug, shown=True, form="check", value=CHECK):
    from compass_pkg import approval_requests
    task = str(_task(project, slug))
    request = approval_requests.write(task, form, value, "the scope")
    if shown:
        request = approval_requests.mark_shown(task, request)
    return request


def _records(project, slug):
    body = yaml.safe_load((_task(project, slug) / "manifest.yml").read_text())
    return [e for e in body.get("evidence") or [] if e.get("type") == "human-approval"]


def _pending(project, slug):
    from compass_pkg import approval_requests
    return [r["number"] for r in approval_requests.pending(str(_task(project, slug)))]


def _closed(project, slug):
    from compass_pkg import approval_requests
    return {r["number"]: r for r in approval_requests.closed(str(_task(project, slug)))}


def _approve(project, args, **kw):
    return type_(project, args, command="compass:approve", **kw)


def _reject(project, args, **kw):
    return type_(project, args, command="compass:reject", **kw)


def test_TRC_044_compass_approve_n_records_the_request_on_the_issue_in_the_worktree(
        tmp_path):
    top, work = _setup(tmp_path)
    set_owner(top, "pat")
    set_owner(work, "jed")
    _request(work, WT)
    before = _records(top, SLUG)
    result = _approve(top, "1")
    assert not result.block, result
    assert _records(work, WT)[-1]["check"] == CHECK
    assert _records(work, WT)[-1]["approver"] == "jed"
    assert 1 in _closed(work, WT) and not _pending(work, WT)
    assert _records(top, SLUG) == before
    assert WT in result.message and str(work) in result.message, result.message


def test_TRC_045_the_request_is_found_when_the_session_s_folder_has_no_compass(tmp_path):
    top, work = _setup(tmp_path)
    (top / "compass.yml").unlink()
    _request(work, WT)
    result = _approve(top, "1")
    assert not result.block, result
    assert _records(work, WT)[-1]["approver"] == OWNER


def test_TRC_046_compass_approver_names_the_approver_for_a_request_in_another_worktree(
        tmp_path):
    top, work = _setup(tmp_path)
    _request(work, WT, form="guardrail", value="G5")
    result = _approve(top, "1", env={"COMPASS_APPROVER": "ana"})
    assert not result.block, result
    last = _records(work, WT)[-1]
    assert last["approver"] == "ana" and last["approver_source"] == "environment"


def test_TRC_047_a_request_in_another_worktree_that_was_not_shown_is_shown_first(tmp_path):
    top, work = _setup(tmp_path)
    _request(work, WT, shown=False)
    result = _approve(top, "1")
    assert result.block and "Nothing was written yet" in result.message, result
    assert "/compass:approve again" in result.message or "again" in result.message
    from compass_pkg import approval_requests
    request = approval_requests.pending(str(_task(work, WT)))[0]
    assert request["shown_at"] and request["shown_digest"]
    assert not _records(work, WT)


def test_TRC_048_two_worktrees_with_pending_request_n_are_refused_and_the_refusal_lists(
        tmp_path):
    top, work = _setup(tmp_path)
    _request(top, SLUG)
    _request(work, WT)
    result = _approve(top, "1")
    assert result.block, result
    for needle in (SLUG, str(top), WT, str(work), f"/compass:approve 1 --issue {SLUG}",
                   f"/compass:approve 1 --issue {WT}"):
        assert needle in result.message, (needle, result.message)
    assert _pending(top, SLUG) == [1] and _pending(work, WT) == [1]
    assert not _records(top, SLUG) and not _records(work, WT)


def test_TRC_049_compass_approve_issue_n_records_request_n_of_that_issue(tmp_path):
    top, work = _setup(tmp_path)
    _request(top, SLUG)
    _request(work, WT)
    result = _approve(top, f"1 --issue {WT}")
    assert not result.block, result
    assert len(_records(work, WT)) == 1
    assert WT in result.message and str(work) in result.message, result.message
    assert _pending(top, SLUG) == [1]


def test_TRC_050_compass_approve_issue_n_refuses_an_issue_that_two_worktrees_hold(
        tmp_path):
    top, work = _setup(tmp_path)
    copy_issue(top, top, WT)
    _request(top, WT)
    _request(work, WT)
    result = _approve(top, f"1 --issue {WT}")
    assert result.block, result
    assert str(_task(top, WT)) in result.message and str(_task(work, WT)) in result.message
    assert not _records(top, WT) and not _records(work, WT)


def test_TRC_051_compass_approve_issue_n_refuses_an_issue_that_no_worktree_holds(tmp_path):
    top, work = _setup(tmp_path)
    result = _approve(top, "1 --issue gone-issue")
    assert result.block and "'gone-issue'" in result.message, result
    assert str(top) in result.message and str(work) in result.message, result.message
    assert "is not an issue in this project" not in result.message


def test_TRC_052_when_no_worktree_holds_pending_request_n_the_refusal_says_so_and(tmp_path):
    top, work = _setup(tmp_path)
    (top / "compass.yml").unlink()
    result = _approve(top, "3")
    assert result.block, result
    assert "no worktree holds a pending request 3" in result.message, result.message
    assert str(top) in result.message and str(work) in result.message, result.message
    for banned in ("owner:", "COMPASS_APPROVER", "is not an issue in this project"):
        assert banned not in result.message, (banned, result.message)


def test_TRC_053_the_worktree_that_holds_the_request_has_no_approver(tmp_path):
    top, work = _setup(tmp_path)
    (work / "compass.yml").unlink()
    _request(work, WT)
    result = _approve(top, "1")
    assert result.block and str(work) in result.message, result
    assert "compass.yml" in result.message, result.message
    assert not _records(work, WT)


@pytest.mark.parametrize("arguments", ["1 2", "one", "1 --issue", "1 --issue wt-issue --issue x",
                                       "--issue wt-issue", "1 --isue wt-issue"])
def test_TRC_054_compass_approve_with_arguments_of_neither_form_is_refused_with_both_forms(
        tmp_path, arguments):
    top, work = _setup(tmp_path)
    _request(work, WT)
    result = _approve(top, arguments)
    assert result.block, result
    assert "/compass:approve <n>" in result.message, result.message
    assert "/compass:approve <n> --issue <issue>" in result.message, result.message
    assert not _records(work, WT) and _pending(work, WT) == [1]


def test_TRC_055_a_typed_command_already_answered_on_an_issue_in_another_worktree_is(
        tmp_path):
    from approval_support import manifest_of
    top, work = _setup(tmp_path)
    _request(top, SLUG)
    path = _task(work, WT) / "manifest.yml"
    body = yaml.safe_load(path.read_text())
    body["evidence"].append({"id": "EV-X-1", "type": "human-approval", "prompt_id": "P"})
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    result = _approve(top, "1", prompt_id="P")
    assert result.block and "already answered" in result.message, result
    assert _pending(top, SLUG) == [1] and not manifest_of(top)["evidence"]


def test_TRC_056_compass_reject_n_reason_rejects_the_request_in_the_worktree_that_holds(
        tmp_path):
    top, work = _setup(tmp_path)
    _request(work, WT)
    result = _reject(top, "1 the rollback plan is missing")
    assert not result.block, result
    last = _records(work, WT)[-1]
    assert last["check"] == CHECK and last["decision"] == "rejected"
    assert last["reason"] == "the rollback plan is missing"
    assert _closed(work, WT)[1]["outcome"] == "rejected"
    assert WT in result.message and str(work) in result.message, result.message


def test_TRC_057_compass_reject_refuses_two_worktrees_with_pending_request_n_and_lists_the(
        tmp_path):
    top, work = _setup(tmp_path)
    _request(top, SLUG)
    _request(work, WT)
    result = _reject(top, "1 not ready")
    assert result.block, result
    assert f"/compass:reject 1 <reason> --issue {SLUG}" in result.message, result.message
    assert f"/compass:reject 1 <reason> --issue {WT}" in result.message, result.message
    assert _pending(top, SLUG) == [1] and _pending(work, WT) == [1]


def test_TRC_058_compass_reject_issue_n_reason_rejects_request_n_of_that_issue(tmp_path):
    top, work = _setup(tmp_path)
    _request(top, SLUG)
    _request(work, WT)
    result = _reject(top, f"1 not ready --issue {WT}")
    assert not result.block, result
    last = _records(work, WT)[-1]
    assert last["decision"] == "rejected" and last["reason"] == "not ready"
    assert _pending(top, SLUG) == [1]


def test_TRC_084_a_pending_request_on_an_issue_that_is_not_its_worktree_s(tmp_path):
    top, work = _setup(tmp_path)
    copy_issue(top, work, "other-issue")
    _request(work, "other-issue")
    result = _approve(top, "1")
    assert result.block and "no worktree holds a pending request 1" in result.message, result
    assert _pending(work, "other-issue") == [1]


def test_TRC_085_compass_approve_n_issue_slug_reaches_an_issue_that_is_not_a(tmp_path):
    top, work = _setup(tmp_path)
    copy_issue(top, work, "other-issue")
    _request(work, "other-issue")
    result = _approve(top, "1 --issue other-issue")
    assert not result.block, result
    assert len(_records(work, "other-issue")) == 1


def test_TRC_086_a_worktree_with_no_current_issue_is_skipped(tmp_path):
    top, work = _setup(tmp_path)
    work2 = add_worktree(top, "w2")
    copy_issue(top, work2, "w2-issue")
    _request(work, WT)
    result = _approve(top, "1")
    assert not result.block, result
    assert len(_records(work, WT)) == 1


def test_TRC_087_a_bare_compass_approve_answers_the_one_request_pending_across_worktrees(
        tmp_path):
    top, work = _setup(tmp_path)
    _request(work, WT)
    path = _task(top, SLUG) / "manifest.yml"
    body = yaml.safe_load(path.read_text())
    body["evidence"].append({"id": "EV-APPROVAL-c-1", "type": "human-approval",
                             "via": "delegation", "check": CHECK})
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    result = _approve(top, "")
    assert not result.block, result
    assert len(_records(work, WT)) == 1
    kept = [e for e in yaml.safe_load(path.read_text())["evidence"]
            if e["id"] == "EV-APPROVAL-c-1"][0]
    assert not kept.get("reviewed_at")


def test_TRC_088_a_bare_compass_approve_refuses_when_more_than_one_request_is_pending(
        tmp_path):
    top, work = _setup(tmp_path)
    _request(top, SLUG)
    _request(work, WT)
    _request(work, WT, form="guardrail", value="G5")
    result = _approve(top, "")
    assert result.block, result
    for needle in (SLUG, str(top), WT, str(work), f"/compass:approve 1 --issue {SLUG}",
                   f"/compass:approve 2 --issue {WT}"):
        assert needle in result.message, (needle, result.message)


def test_TRC_089_a_bare_compass_reject_reason_rejects_the_one_request_pending_across_worktrees(
        tmp_path):
    top, work = _setup(tmp_path)
    _request(work, WT)
    result = _reject(top, "the scope is wrong")
    assert not result.block, result
    last = _records(work, WT)[-1]
    assert last["decision"] == "rejected" and last["reason"] == "the scope is wrong"


def test_TRC_090_issue_can_come_anywhere_in_compass_reject_and_is_not_part_of(tmp_path):
    top, work = _setup(tmp_path)
    _request(top, SLUG)
    _request(work, WT)
    result = _reject(top, f"1 --issue {WT} not ready")
    assert not result.block, result
    last = _records(work, WT)[-1]
    assert last["decision"] == "rejected" and last["reason"] == "not ready"
    assert _pending(top, SLUG) == [1]


def test_TRC_097_the_request_names_issue_when_another_worktree_s_current_issue_holds(
        tmp_path):
    from compass_pkg import approval_requests
    top, work = _setup(tmp_path)
    _request(top, SLUG)
    code, out, err = run(work, "evidence", "request", "--check", CHECK, "--scope", "s",
                         "--issue", WT)
    assert code == 0, out + err
    said = " ".join((out + err).split())
    assert f"/compass:approve 1 --issue {WT}" in said, said
    shown = approval_requests.stop_message(str(work / ".compass"), {})
    assert f"/compass:approve 1 --issue {WT}" in shown, shown
    assert f"/compass:reject 1 <reason> --issue {WT}" in shown, shown
