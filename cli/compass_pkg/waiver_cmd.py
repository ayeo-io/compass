# compass_pkg.waiver_cmd - `compass waiver add` and `compass waiver withdraw`
"""Write and withdraw the waivers of one issue (ADR-094; `waiver_records`).

- `compass waiver add --check <id> --reason "..."` writes one waiver to the
  issue's manifest, with the next free id `W-<n>`. It refuses an empty
  reason, a reason that holds a control character, a check the check set never waives (`never_waived`), a check
  Compass deleted (`check_registry.DELETED_CHECKS`), a check the
  issue's policy does not hold, and a second waiver in force for the same
  check. A new waiver excuses nothing until a person approves it: the agent
  asks with `compass evidence request --waiver W-<n>` and stops.
- `compass waiver withdraw W-<n>` removes a waiver nobody approved, and
  closes a pending request for it. An approved waiver is marked withdrawn,
  with the time, so the approval stays on record and the check runs again.

Neither verb approves anything, and withdrawing only makes the issue owe
more, so an agent may run both.
"""
# DEPENDENCY: standard library (os); compass_pkg.approval_requests, approvals (the
# issue's approval lock), check_registry, core, terminal, waiver_records.
from __future__ import annotations

import os
import unicodedata

from compass_pkg import approval_records, approval_requests, approvals, waiver_records
from compass_pkg.check_registry import DELETED_CHECKS
from compass_pkg.core import (CompassError, issue_arg, load_manifest, now_iso,
                              resolve_issue_dir, save_manifest)
from compass_pkg.terminal import say

ADD, WITHDRAW = "compass waiver add", "compass waiver withdraw"


def _stamp():
    return now_iso().replace("+00:00", "Z")


def _hidden(text):
    """True when `text` holds a control, format or line-separator character.
    Such a character, an escape sequence or a direction override, could move
    the cursor or reorder the request the person is shown."""
    return any(unicodedata.category(c) in approval_records.HIDDEN for c in str(text))


def _refuse_add(task, task_dir, check, reason):
    """The reason `compass waiver add` refuses, or None."""
    if not reason:
        return "a waiver needs a reason: say with --reason why the check may be excused"
    if not check:
        return "--check must name a check"
    if check in waiver_records.never_waived():
        return (f"{check} is never waived: the check set lists it under never_waived, "
                f"because a person's sign-off of irreversible work cannot be excused")
    if check in DELETED_CHECKS:
        return (f"{check} is a check Compass no longer has, so a waiver of it would excuse "
                f"nothing, and compass check refuses an issue whose open waiver names one")
    if check not in waiver_records.policy_checks(task_dir):
        return f"this issue's policy holds no check '{check}', so there is nothing to waive"
    held = next((w for w in waiver_records.listed(task)
                 if w.get("check") == check and not w.get("withdrawn_at")), None)
    if held is not None:
        return (f"{held.get('id')} already waives {check} on this issue; withdraw it first "
                f"with `compass waiver withdraw {held.get('id')}`")
    return None


def cmd_waiver_add(args):
    if _hidden(args.reason) or _hidden(args.check):
        raise CompassError(f"{ADD}: the reason or the check holds a control character (an "
                           f"escape sequence, a direction override or a line break). The "
                           f"person is shown the reason, so it must be plain text on one "
                           f"line. Nothing was written.")
    check = approvals.text(args.check)
    reason = approvals.text(args.reason)
    by = approvals.text(args.by) or "agent"
    task_dir = resolve_issue_dir(args.task)
    slug = os.path.basename(os.path.normpath(task_dir))
    with approvals.lock(task_dir):
        task, path = load_manifest(task_dir)
        why = _refuse_add(task, task_dir, check, reason)
        if why:
            raise CompassError(f"{ADD}: {why}. Nothing was written.")
        waiver = {"id": waiver_records.next_id(task, task_dir), "check": check,
                  "reason": reason, "requested_at": _stamp(), "requested_by": by}
        task.setdefault(waiver_records.KEY, []).append(waiver)
        save_manifest(task, path)
    tell = (f"The waiver excuses nothing until a person approves it. Ask with `compass "
            f"evidence request --waiver {waiver['id']} --issue {slug}`, and stop.")
    code = say(args, f"{ADD}: {waiver['id']} written - waives {check} on issue {slug} "
                     f"once approved.",
               detail=[f"waiver     : {waiver['id']} in manifest.yml waivers",
                       f"reason     : {reason}", f"next       : {tell}"],
               waiver=waiver["id"], check=check, reason=reason, issue=slug,
               approved=False, next=tell)
    return code


def cmd_waiver_withdraw(args):
    waiver_id = approvals.text(args.waiver)
    if not waiver_records.ID.fullmatch(waiver_id):
        raise CompassError(f"{WITHDRAW}: give a waiver id such as W-1, not '{waiver_id}'. "
                           f"Nothing was written.")
    task_dir = resolve_issue_dir(args.task)
    with approvals.lock(task_dir):
        task, path = load_manifest(task_dir)
        waiver = waiver_records.find(task, waiver_id)
        if waiver is None:
            raise CompassError(f"{WITHDRAW}: no waiver {waiver_id} on this issue. Nothing was "
                               f"written.")
        if waiver.get("withdrawn_at"):
            raise CompassError(f"{WITHDRAW}: {waiver_id} was already withdrawn at "
                               f"{waiver['withdrawn_at']}. Nothing was written.")
        held, record, _ = waiver_records.state(task, task_dir, waiver)
        if held == waiver_records.APPROVED or _named_by_a_record(task, waiver_id):
            # Kept, so the approval record still names a waiver on the issue.
            waiver["withdrawn_at"] = _stamp()
            outcome = f"{waiver_id} withdrawn - {waiver.get('check')} runs again on this issue."
        else:
            task[waiver_records.KEY] = [w for w in waiver_records.listed(task)
                                        if w.get("id") != waiver_id]
            if not task[waiver_records.KEY]:
                del task[waiver_records.KEY]
            outcome = f"{waiver_id} removed - nobody had approved it."
        save_manifest(task, path)
        for request in approval_requests.pending(task_dir):
            if request.get("form") == waiver_records.SUBJECT and \
                    request.get("value") == waiver_id:
                approval_requests.close(task_dir, request, approval_requests.STALE,
                                        reason="the waiver was withdrawn")
    return say(args, f"{WITHDRAW}: {outcome}", waiver=waiver_id,
               check=waiver.get("check"), approved=record is not None)


def _named_by_a_record(task, waiver_id):
    return any(isinstance(e, dict) and e.get(waiver_records.SUBJECT) == waiver_id
               for e in task.get("evidence") or [])


def register(sub):
    """Add the `waiver` group: `add` and `withdraw`."""
    p = sub.add_parser("waiver", help="waive one check on one issue, with a reason and a "
                                      "person's approval")
    verbs = p.add_subparsers(dest="waiver_cmd", required=True)
    add = verbs.add_parser("add", help="write a waiver of one check on the issue; it excuses "
                                       "nothing until a person approves it",
                           allow_abbrev=False)
    add.add_argument("--check", required=True, help="id of the check to waive")
    add.add_argument("--reason", required=True, help="why the check may be excused")
    add.add_argument("--by", default="", help="who asks for the waiver (default: agent)")
    issue_arg(add)
    add.set_defaults(func=cmd_waiver_add, output_kind="hand-off")
    out = verbs.add_parser("withdraw", help="remove an unapproved waiver, or mark an approved "
                                            "one withdrawn", allow_abbrev=False)
    out.add_argument("waiver", metavar="W-N", help="the waiver's id")
    issue_arg(out)
    out.set_defaults(func=cmd_waiver_withdraw, output_kind="hand-off")
