# compass_pkg.approve_cmd - `compass evidence approve`
"""Record a person's approval: of a human check, of a document or of a set of
decisions taken for the person.

The verb takes exactly one of three forms:

- `--check <id>` reads the check from the issue's effective view and registers
  a `human-approval` entry in the manifest's evidence, with `check: <id>`.
  `compass check` then reads it through `approval_records`.
- `--artifact <kind>` approves a document that reads `awaiting-approval`. It
  registers one `artifact-approval` record for each human check on the
  document, which `approval_records` counts for that check, and sets the
  entry's `approved_by` and `approved_at`. It never writes a `human-approval`
  record, so it cannot clear the sign-off of guardrail `G5`.
- `--decisions` confirms the decisions an agent took for the person, through
  `decisions_taken.approve_set`.

A record holds the issue, the issue's generation and the time, which the verb
stamps itself, so a person cannot record an approval for another issue or
generation by mistake.

The verb needs a terminal on its standard input. An approval is a person's act,
and an agent session has no terminal, so it cannot call the verb. The verb also
refuses the approver `agent`. Nothing else guards the record: anyone who can
write `manifest.yml` can add one by hand.
"""
# DEPENDENCY: standard library (os, sys); compass_pkg.approval_records,
# core, effective, terminal.
from __future__ import annotations

import os
import sys

from compass_pkg import approval_records, effective
from compass_pkg.core import (CompassError, issue_arg, load_manifest, now_iso,
                              resolve_issue_dir, save_manifest)
from compass_pkg.terminal import say

DECISIONS = approval_records.DECISIONS
ARTIFACT_APPROVAL = approval_records.ARTIFACT_APPROVAL


def _terminal_attached():
    """True when a person can type: standard input is a terminal."""
    return sys.stdin.isatty()


def _text(value):
    return " ".join(str(value or "").split())


def _approver(text):
    """The approver's name, or a refusal: empty, or an agent."""
    name = _text(text)
    if not name:
        raise CompassError("compass evidence approve: --approver must name the person "
                           "who approves.")
    if name.lower() == "agent" or name.lower().startswith("agent:"):
        raise CompassError("compass evidence approve: an agent cannot approve. An approval "
                           "is a person's; give that person's id with --approver.")
    return name


def _check_of(view, check_id):
    if view is None:
        raise CompassError("compass evidence approve: this issue has no configuration to "
                           "read its checks from. Run `compass approach evaluate --write`.")
    checks = view.config.get("checks") or {}
    check = checks.get(check_id)
    approvable = sorted(name for name, body in checks.items()
                        if isinstance(body, dict) and body.get("kind") == "human"
                        and body.get("approvers"))
    known = (f"the human checks that list approvers are {', '.join(approvable)}"
             if approvable else "it configures no human check that lists approvers")
    if not isinstance(check, dict):
        raise CompassError(f"compass evidence approve: no such check '{check_id}' in this "
                           f"issue's configuration; {known}.")
    if check.get("kind") != "human":
        raise CompassError(f"compass evidence approve: '{check_id}' is a {check.get('kind')} "
                           f"check, not a human check. Only a human check takes an approval.")
    if not check.get("approvers"):
        raise CompassError(f"compass evidence approve: '{check_id}' lists no approvers, so "
                           f"a tick is enough and an approval would not be read; {known}.")
    return check


def _numbered(task, check_id):
    """The next number for a record of the check, and an evidence id no entry
    already uses."""
    taken = {e.get("id") for e in task.get("evidence") or [] if isinstance(e, dict)}
    number = 1 + len([e for e in task.get("evidence") or []
                      if isinstance(e, dict) and e.get("type") == "human-approval"
                      and e.get("check") == check_id])
    while f"EV-APPROVAL-{check_id}-{number}" in taken:
        number += 1
    return number, f"EV-APPROVAL-{check_id}-{number}"


def _checks_for(args):
    """Refuse a call that has not one of the three forms (argparse also does)."""
    forms = [bool(args.check), bool(args.artifact), bool(args.decisions)]
    if sum(forms) != 1:
        raise CompassError("compass evidence approve: give exactly one of --check, "
                           "--artifact or --decisions.")


def cmd_evidence_approve(args):
    if not _terminal_attached():
        raise CompassError("compass evidence approve: this needs a terminal on standard "
                           "input. An approval is a person's act, so run the command "
                           "yourself in a terminal; an agent session cannot record one.")
    _checks_for(args)
    if args.decision not in DECISIONS:
        raise CompassError(f"compass evidence approve: the decision must be one of "
                           f"{' or '.join(DECISIONS)}, not '{args.decision}'.")
    approver = _approver(args.approver)
    role, scope = _text(args.role), _text(args.scope)
    required = (("--role", role), ("--scope", scope)) if args.check else (("--role", role),)
    for flag, value in required:
        if not value:
            raise CompassError(f"compass evidence approve: {flag} must not be empty; a "
                               f"record says in what role and for what the person approved.")
    args.approver, args.role, args.scope = approver, role, scope
    if args.artifact:
        return _approve_artifact(args)
    if args.decisions:
        from compass_pkg import decisions_taken
        return decisions_taken.approve_set(args)
    return _approve_check(args)


def _stamp(task, task_dir, evidence_id, **fields):
    """A record of the new type, with the issue, generation and time the verb
    stamps."""
    entry = {"id": evidence_id, "type": ARTIFACT_APPROVAL}
    entry.update({k: v for k, v in fields.items() if v not in (None, "")})
    entry.update(issue=os.path.basename(os.path.normpath(task_dir)),
                 generation=task.get("generation"))
    return entry


def _approve_artifact(args):
    from compass_pkg import artifact_status

    kind = args.artifact
    if args.decision != approval_records.APPROVED:
        raise CompassError("compass evidence approve: --artifact records an approval only. "
                           f"To send {kind} back, run `compass issue artifact set {kind} "
                           "--status draft`.")
    task_dir = resolve_issue_dir(args.task)
    task, task_path = load_manifest(task_dir)
    entry = next((a for a in task.get("artifacts") or []
                  if isinstance(a, dict) and a.get("kind") == kind), None)
    if entry is None:
        raise CompassError(f"compass evidence approve: '{kind}' is not a document this issue "
                           f"registered.")
    if entry.get("status") != artifact_status.AWAITING:
        raise CompassError(
            f"compass evidence approve: {kind} reads {entry.get('status')}, not "
            f"awaiting-approval, so there is nothing to approve. A document with a human "
            f"check moves to awaiting-approval when the stage after it records its work; "
            f"to ask for approval now, run `compass issue artifact set {kind} --status "
            f"awaiting-approval`.")
    view = effective.view_or_legacy(task_dir)
    checks = artifact_status.human_checks(view, kind)
    owner = approval_records.project_owner(task_dir)
    for check_id in checks:
        listed = [str(one) for one in (view.config["checks"][check_id].get("approvers") or [])]
        if listed and not approval_records.approver_listed(listed, args.approver, owner):
            raise CompassError(
                f"compass evidence approve: {args.approver} is not an approver of "
                f"'{check_id}', which {kind} carries, so the record would not count. "
                f"{approval_records.listing(check_id, listed, owner)}.")
    stamp = now_iso().replace("+00:00", "Z")
    taken = {e.get("id") for e in task.get("evidence") or [] if isinstance(e, dict)}
    number = 1
    for check_id in checks or [None]:
        while f"EV-APPROVAL-ARTIFACT-{kind}-{number}" in taken:
            number += 1
        evidence_id = f"EV-APPROVAL-ARTIFACT-{kind}-{number}"
        taken.add(evidence_id)
        task.setdefault("evidence", []).append(_stamp(
            task, task_dir, evidence_id, artifact=kind, check=check_id,
            approver=args.approver, role=args.role, decision=args.decision,
            timestamp=stamp, scope=args.scope))
    artifact_status.clear_approver(entry)
    entry.update(status=artifact_status.APPROVED, approved_by=args.approver, approved_at=stamp)
    save_manifest(task, task_path)
    ids = [e["id"] for e in task["evidence"][-(len(checks) or 1):]]
    return say(args, f"compass evidence approve: {kind} - approved by {args.approver} "
                     f"recorded as {', '.join(ids)}.",
               detail=[f"record     : {', '.join(ids)} in manifest.yml evidence",
                       f"document   : {kind} -> approved by {args.approver}"],
               artifact=kind, answer=args.decision, evidence_id=ids[0], evidence_ids=ids,
               approver=args.approver, role=args.role, scope=args.scope or None,
               at=stamp, status=artifact_status.APPROVED)


def _approve_check(args):
    check_id = args.check
    task_dir = resolve_issue_dir(args.task)
    task, task_path = load_manifest(task_dir)
    approver, role, scope = args.approver, args.role, args.scope
    check = _check_of(effective.view_or_legacy(task_dir), check_id)
    owner = approval_records.project_owner(task_dir)
    listed = [str(one) for one in check["approvers"]]
    if not approval_records.approver_listed(listed, approver, owner):
        raise CompassError(f"compass evidence approve: {approver} is not an approver of "
                           f"'{check_id}', so the record would not count. "
                           f"{approval_records.listing(check_id, listed, owner)}.")
    number, evidence_id = _numbered(task, check_id)
    entry = {"id": evidence_id, "type": "human-approval", "check": check_id,
             "approver": approver, "role": role, "scope": scope, "decision": args.decision,
             "timestamp": now_iso().replace("+00:00", "Z"),
             "issue": os.path.basename(os.path.normpath(task_dir)),
             "generation": task.get("generation")}
    task.setdefault("evidence", []).append(entry)
    save_manifest(task, task_path)
    return say(args, f"compass evidence approve: {check_id} - {args.decision} by {approver} "
                     f"recorded as {evidence_id}.",
               detail=[f"record     : {evidence_id} in manifest.yml evidence",
                       f"issue      : {entry['issue']}",
                       f"generation : {approval_records.shown(entry['generation'])}"],
               check=check_id, answer=args.decision, evidence_id=evidence_id,
               approver=approver, role=role, scope=scope, issue=entry["issue"],
               generation=entry["generation"], at=entry["timestamp"])


def register(evidence_subs):
    """Add `approve` to the `evidence` group."""
    p = evidence_subs.add_parser(
        "approve", help="record a person's approval of a human check, a document or the "
                        "decisions taken for the person")
    form = p.add_mutually_exclusive_group(required=True)
    form.add_argument("--check", help="id of the human check")
    form.add_argument("--artifact", metavar="KIND",
                      help="approve this document, which reads awaiting-approval")
    form.add_argument("--decisions", action="store_true",
                      help="confirm the decisions taken for the person")
    issue_arg(p)
    p.add_argument("--approver", required=True, help="the approver's person id")
    p.add_argument("--role", required=True, help="the role the approver acts in")
    p.add_argument("--scope", default="",
                   help="what the approval covers; required with --check")
    p.add_argument("--decision", default="approved", choices=DECISIONS,
                   help="approved (default) or rejected; a later rejection withdraws an "
                        "approval")
    p.set_defaults(func=cmd_evidence_approve, output_kind="hand-off")
