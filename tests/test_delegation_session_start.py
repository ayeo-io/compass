"""What session start says about delegations that have no end time (issue
`delegation-everywhere`, group F).

A delegation with no end time stays in force until the person revokes it, so each
session start lists it: its age in whole days, who it covers, whether it covers the
session that is starting and how many approvals it has given. After `/clear` the
list also says that a session delegation of the earlier session no longer covers
this one. The common store is read from any worktree.

Scenario ids: `TRC-068` to `TRC-071`, `TRC-108` and `TRC-109`. Each test name starts
with its scenario id.
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from delegation_support import add_issue, add_worktree, repo  # noqa: E402
from test_delegation import _hook_json  # noqa: E402
from test_delegation_limits import _write_dl  # noqa: E402

ARCH = "compass:architect"


def _ago(days=0, hours=0):
    when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=days, hours=hours)
    return when.isoformat(timespec="seconds").replace("+00:00", "Z")


def _open(top, number, session=None, agent=None, days=3, uses=4, **more):
    """A delegation with no end time, as `/compass:delegate` writes it now."""
    fields = {"format": 2, "until": None, "issues": {}, "uses": uses,
              "created_at": _ago(days=days), "agent": agent,
              "covers_session": session}
    fields.update(more)
    return _write_dl(top, number, **fields)


def _start(root, session, source="startup"):
    out = _hook_json("session-start.sh", root, {"session_id": session, "source": source})
    return out.get("systemMessage", "")


def test_TRC_068_session_start_lists_each_open_ended_delegation_with_its_age_and_its(
        tmp_path):
    top = repo(tmp_path)
    _open(top, 2, session="sess-S")
    _open(top, 3, agent=ARCH, uses=1)
    here = _start(top, "sess-S")
    for needle in ("DL-2", "no end time", "3 days", "4 approvals", "/compass:revoke DL-2",
                   "the agents of the session it was typed in", "That is this session"):
        assert needle in here, (needle, here)
    for needle in ("DL-3", f"covers {ARCH} in every session", "1 approval."):
        assert needle in here, (needle, here)


def test_TRC_069_the_list_shows_when_nothing_waits_for_review(tmp_path):
    top = repo(tmp_path)
    _open(top, 2, session="sess-S", uses=0)
    assert "DL-2" in _start(top, "sess-S")


@pytest.mark.parametrize("state", ["ends 5 hours ahead", "was revoked", "reached its max"])
def test_TRC_070_a_delegation_that_has_an_end_time_or_is_no_longer_in(tmp_path, state):
    top = repo(tmp_path)
    if state == "ends 5 hours ahead":
        later = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5)
        _open(top, 3, session="sess-S", until=later.isoformat(timespec="seconds")
              .replace("+00:00", "Z"))
    elif state == "was revoked":
        _open(top, 3, session="sess-S", revoked_at=_ago(hours=1), revoked_by="jed72")
    else:
        _open(top, 3, session="sess-S", max_uses=2, uses=2)
    assert "DL-3 has no end time" not in _start(top, "sess-S")


def test_TRC_071_a_session_started_in_a_linked_worktree_lists_the_open_ended_delegations(
        tmp_path):
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    add_issue(work, "wt-issue", current=True)
    _open(top, 2, session="sess-S")
    message = _start(work, "sess-W")
    assert "DL-2" in message, message
    assert not (work / ".compass" / "delegations").exists()


def test_TRC_108_after_clear_session_start_says_the_earlier_sessions_delegation_no_longer_covers(
        tmp_path):
    top = repo(tmp_path)
    _open(top, 1, session="sess-before")
    _open(top, 3, agent=ARCH)
    message = _start(top, "sess-after", source="clear")
    for needle in ("/clear started a new session",
                   "A delegation typed before /clear without --agent does not cover this "
                   "session", "Type /compass:delegate to cover it",
                   f"DL-3 has no end time and covers {ARCH} in every session, including "
                   f"this one"):
        assert needle in message, (needle, message)
    assert "/clear started" not in _start(top, "sess-after", source="startup")


def test_TRC_109_session_start_says_compass_cannot_tell_whether_another_sessions_delegation_is_in_use(
        tmp_path):
    top = repo(tmp_path)
    _open(top, 2, session="sess-S")
    message = _start(top, "sess-T")
    for needle in ("DL-2 has no end time and covers the agents of the session it was typed in",
                   "That is not this session",
                   "Compass cannot tell whether that session is still open",
                   "it covers that session's agents until you type /compass:revoke DL-2"):
        assert needle in message, (needle, message)
