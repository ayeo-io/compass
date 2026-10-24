"""Where a delegation lives and who the approver is, with sessions in linked
worktrees (issue `delegation-everywhere`, group C, store location).

`/compass:delegate` and `/compass:revoke` need no current issue. They keep the
delegation in the common store, in the main checkout, and take the approver
from that folder's `compass.yml`.

Scenario ids: `TRC-041`, `TRC-091`, `TRC-092`, `TRC-093`. Each test name starts
with its scenario id.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import OWNER  # noqa: E402
from delegation_support import (add_issue, add_worktree, delegations,  # noqa: E402
                                repo, set_owner, type_)
from test_delegation_limits import _write_dl  # noqa: E402


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
