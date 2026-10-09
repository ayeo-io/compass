#!/usr/bin/env python3
# =============================================================================
# compass_pkg.status_cmd - `compass issue status set|remove` and
# `compass issue blocked set|remove`
# =============================================================================
"""The commands that write an issue's stored status and its blocked flag.

The stored status is `backlog` (a hold a person set) or `done` (closed, with a
close reason). The states `ready`, `in-progress` and `in-review` are read from
the issue's records (`lifecycle.state_of`), so a person cannot set them. The
blocked flag is a separate mapping, because it describes an issue that is in
flight rather than naming a state.
"""
# DEPENDENCY: compass_pkg.status_words (the words and the two writes),
# compass_pkg.lifecycle (the state a flag needs) and compass_pkg.core.
from __future__ import annotations

import os

from compass_pkg import lifecycle, status_words
from compass_pkg.core import (CompassError, load_manifest, now_iso, resolve_issue_dir,
                              save_manifest)
from compass_pkg.terminal import say

#: The words the setter takes.
TASK_STATUSES = status_words.STORED_STATES


def _stale_page(task_dir):
    """`say` detail lines: the one stale-page reminder, or none."""
    from compass_pkg.dashboard import stale_page_reminder
    line = stale_page_reminder(task_dir)
    return [line] if line else None


def _list(words):
    return ", ".join(words)


def _unmet_gates(task):
    return [g.get("id", "?") for g in (task.get("gates") or [])
            if isinstance(g, dict) and g.get("status") != "pass"]


def _close_reason(task, task_dir, close_reason, duplicate_of):
    """The close reason to store, or a refusal. Nothing is written here."""
    verb = "compass issue status set"
    if duplicate_of:
        if close_reason not in (None, status_words.DUPLICATE):
            raise CompassError(
                f"{verb}: --duplicate-of means the close reason is duplicate, "
                f"so it cannot come with --close-reason {close_reason}.")
        close_reason = status_words.DUPLICATE
    if close_reason is None:
        raise CompassError(
            f"{verb}: done needs --close-reason, one of "
            f"{_list(status_words.CLOSE_REASONS)}.")
    if close_reason not in status_words.CLOSE_REASONS:
        raise CompassError(
            f"{verb}: '{close_reason}' is not a close reason; use one of "
            f"{_list(status_words.CLOSE_REASONS)}.")
    if close_reason == status_words.DUPLICATE:
        if not duplicate_of:
            raise CompassError(
                f"{verb}: closing as a duplicate needs --duplicate-of SLUG, "
                "the issue that already covers this one.")
        own = task.get("issue") or os.path.basename(str(task_dir).rstrip("/"))
        other = os.path.join(os.path.dirname(str(task_dir).rstrip("/")), duplicate_of)
        if duplicate_of == own:
            raise CompassError(f"{verb}: an issue cannot be a duplicate of itself.")
        if (os.sep in duplicate_of or duplicate_of in (".", "..")
                or not os.path.isdir(other)):
            raise CompassError(
                f"{verb}: --duplicate-of names '{duplicate_of}', which is not an "
                "issue in this project.")
    if close_reason == status_words.COMPLETED:
        unmet = _unmet_gates(task)
        # `ship-commit` refuses to record a completed issue over gates that
        # have not passed. This command must not be an easier way to the same
        # state, or the refusal is advice rather than a rule.
        if unmet:
            raise CompassError(
                f"{verb}: refusing to mark '{task.get('issue')}' completed - "
                f"{len(unmet)} gate(s) have not passed ({', '.join(unmet)}). "
                "Completed means every gate passed. Clear the gates and re-run.")
    return close_reason


def cmd_task_set_status(args):
    status = args.status
    verb = "compass issue status set"
    if status in status_words.DERIVED_STATES:
        raise CompassError(
            f"{verb}: '{status}' is not set by hand. The issue's records move "
            f"{_list(status_words.DERIVED_STATES)}: write the documents, tests "
            "and gate results, and the state follows. A person sets only "
            f"{_list(TASK_STATUSES)}.")
    if status not in TASK_STATUSES:
        raise CompassError(
            f"{verb}: '{status}' is not an issue status. A person sets "
            f"{_list(TASK_STATUSES)}:\n"
            "  backlog - set aside; a hold that `compass issue status remove` ends\n"
            "  done    - closed; needs --close-reason completed, not-planned or duplicate")
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, path = load_manifest(task_dir)
    reason = getattr(args, "reason", None)
    close_reason = getattr(args, "close_reason", None)
    duplicate_of = getattr(args, "duplicate_of", None)
    if status == status_words.BACKLOG:
        if close_reason or duplicate_of:
            raise CompassError(
                f"{verb}: --close-reason and --duplicate-of go with done, not backlog.")
        status_words.hold(task)
        if reason:
            task["parked_reason"] = reason
            task["parked_at"] = now_iso()
    else:
        close_reason = _close_reason(task, task_dir, close_reason, duplicate_of)
        status_words.close(task, close_reason, duplicate_of)
        if close_reason == status_words.COMPLETED:
            task["land_timestamp"] = now_iso()
        if reason:
            # `status_reason`, not `note`: the schema forbids undeclared keys,
            # and the name must say which transition it records.
            task["status_reason"] = reason
    save_manifest(task, path)
    detail = f" ({reason})" if reason else ""
    shown = status if close_reason is None else f"{status} ({close_reason})"
    return say(args, f"{verb}: {task.get('issue')} -> {shown}{detail}.",
               detail=_stale_page(task_dir),
               issue=task.get("issue"), status=status, close_reason=close_reason,
               duplicate_of=duplicate_of, reason=reason or None)


def cmd_task_status_remove(args):
    verb = "compass issue status remove"
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, path = load_manifest(task_dir)
    reopening = status_words.is_closed(task)
    if not (status_words.is_held(task) or reopening):
        state = lifecycle.state_of(task, task_dir)
        raise CompassError(
            f"{verb}: '{task.get('issue')}' has no backlog hold or close to remove "
            f"(its state is {state}). Only a hold or a close a person set is "
            "removed; nothing was written.")
    # v5.6.0 `issue set-status active` reopened a closed issue, and that
    # spelling keeps working until 7.0.0, so removing a close reopens it too.
    # The land time stays: it is history, not state.
    del task["status"]
    for key in ("close_reason", "duplicate_of"):
        task.pop(key, None)
    reason = getattr(args, "reason", None)
    if reason:
        task["status_reason"] = reason
    elif reopening:
        task["status_reason"] = "reopened with compass issue status remove"
    save_manifest(task, path)
    state = lifecycle.state_of(task, task_dir)
    kind = "closed" if reopening else "held"
    return say(args, f"{verb}: {task.get('issue')} is no longer {kind}; its state "
                     f"is {state}, read from its records.",
               detail=_stale_page(task_dir), issue=task.get("issue"), state=state)


def cmd_issue_blocked_set(args):
    verb = "compass issue blocked set"
    reason = (getattr(args, "reason", None) or "").strip()
    if not reason:
        raise CompassError(f"{verb}: --reason is required; say what the issue waits for.")
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, path = load_manifest(task_dir)
    state = lifecycle.state_of(task, task_dir)
    if state not in lifecycle.BLOCKABLE_STATES:
        raise CompassError(
            f"{verb}: '{task.get('issue')}' is {state}. Only an issue that is "
            f"{' or '.join(lifecycle.BLOCKABLE_STATES)} can be blocked; "
            "nothing was written.")
    task["blocked"] = {"reason": reason, "at": now_iso()}
    save_manifest(task, path)
    return say(args, f"{verb}: {task.get('issue')} is blocked ({reason}); it stays {state}.",
               detail=_stale_page(task_dir), issue=task.get("issue"), blocked=task["blocked"])


def cmd_issue_blocked_remove(args):
    verb = "compass issue blocked remove"
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, path = load_manifest(task_dir)
    if not status_words.has_blocked_key(task):
        raise CompassError(f"{verb}: '{task.get('issue')}' is not blocked; "
                           "nothing was written.")
    del task["blocked"]
    save_manifest(task, path)
    return say(args, f"{verb}: {task.get('issue')} is no longer blocked.",
               detail=_stale_page(task_dir), issue=task.get("issue"))


def register(pts, issue_arg):
    """The `status` and `blocked` groups under `compass issue`."""
    group = pts.add_parser("status", help="an issue's lifecycle status")
    verbs = group.add_subparsers(dest="status_cmd", required=True)
    setter = verbs.add_parser(
        "set", help="set an issue's stored status: backlog, or done with a close reason")
    setter.add_argument("status", help="backlog or done")
    issue_arg(setter)
    setter.add_argument("--reason", help="why - recorded as parked_reason for backlog, "
                                         "else as status_reason")
    setter.add_argument("--close-reason", dest="close_reason",
                        help="why it is done: completed, not-planned or duplicate")
    setter.add_argument("--duplicate-of", dest="duplicate_of", metavar="SLUG",
                        help="close as a duplicate of this issue (implies --close-reason duplicate)")
    setter.set_defaults(func=cmd_task_set_status, output_kind="hand-off")
    remover = verbs.add_parser("remove", help="end a backlog hold, or reopen a closed issue")
    issue_arg(remover)
    remover.add_argument("--reason", help="why the hold ends - recorded as status_reason")
    remover.set_defaults(func=cmd_task_status_remove, output_kind="hand-off")

    blocked = pts.add_parser("blocked", help="the flag that marks an in-flight issue as blocked")
    flag = blocked.add_subparsers(dest="blocked_cmd", required=True)
    put = flag.add_parser("set", help="mark an in-progress or in-review issue as blocked")
    put.add_argument("--reason", required=True, help="what the issue waits for")
    issue_arg(put)
    put.set_defaults(func=cmd_issue_blocked_set, output_kind="hand-off")
    drop = flag.add_parser("remove", help="clear the blocked flag")
    issue_arg(drop)
    drop.set_defaults(func=cmd_issue_blocked_remove, output_kind="hand-off")
