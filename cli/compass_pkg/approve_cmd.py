# compass_pkg.approve_cmd - `compass evidence approve`
"""Record a person's approval: of a human check, of a document or of a set of
decisions taken for the person.

The verb takes exactly one of five forms:

- `--check <id>` reads the check from the issue's effective view and registers
  a `human-approval` entry in the manifest's evidence, with `check: <id>`.
  `compass check` then reads it through `approval_records`. The record names
  a check, so it never clears the sign-off of guardrail `G5`.
- `--guardrail`, with the value `G5`, records the sign-off of that
  guardrail: one `human-approval` record whose `guardrail` key holds `G5`,
  with no other subject key, which `human-approval-present` counts
  (`approval_records.gives_g5`). Guardrail `G5` is the only guardrail with a
  sign-off, and the form records an approval only, so it refuses any other
  value and `--decision rejected`.
- `--artifact <kind>` approves a document that reads `awaiting-approval`. It
  registers one `artifact-approval` record for each human check on the
  document, which `approval_records` counts for that check, and sets the
  entry's `approved_by` and `approved_at`. It never writes a `human-approval`
  record, so it cannot clear the sign-off of guardrail `G5`.
- `--decisions` confirms the decisions an agent took for the person, through
  `decisions_taken.approve_set`.
- `--checkpoint <stage>` records a person's answer to a checkpoint hand-off:
  one `checkpoint-approval` record, with `checkpoint: <stage>` and no `check`,
  and the stage's `waited` outcome citing it (`checkpoint_outcomes`). No check
  reads the type, so the answer never clears guardrail `G5`, a human check or
  a waiver. `compass evidence add` refuses the type.

A record holds the issue, the issue's generation and the time, which the verb
stamps itself, so a person cannot record an approval for another issue or
generation by mistake.

The records are written by `approvals.record`, which the Claude Code prompt
hook also calls (ADR-068 decision 4), so both paths write the same records. A
record from this verb holds `via: terminal`.

The verb needs a terminal on its standard input. An approval is a person's act,
and an agent session has no terminal, so it cannot call the verb; the refusal
tells the agent to ask with `compass evidence request` instead. The verb also
refuses the approver `agent`. Nothing else guards the record: anyone who can
write `manifest.yml` can add one by hand.
"""
# DEPENDENCY: standard library (os, sys); compass_pkg.approval_records, approvals,
# core, terminal.
from __future__ import annotations

import os
import sys

from compass_pkg import approval_records, approvals
from compass_pkg.core import CompassError, issue_arg, resolve_issue_dir
from compass_pkg.terminal import say

DECISIONS = approval_records.DECISIONS
ARTIFACT_APPROVAL = approval_records.ARTIFACT_APPROVAL
CHECKPOINT_APPROVAL = approvals.CHECKPOINT_APPROVAL

#: The provenance of a record this verb writes (ADR-068 decision 7).
TERMINAL = {"via": "terminal"}


def _terminal_attached():
    """True when a person can type: standard input is a terminal."""
    return sys.stdin.isatty()


def _checks_for(args):
    """Refuse a call that has not one of the five forms (argparse also does)."""
    forms = [bool(args.check), bool(getattr(args, "guardrail", None)), bool(args.artifact),
             bool(args.decisions), bool(getattr(args, "checkpoint", None))]
    if sum(forms) != 1:
        raise CompassError("compass evidence approve: give exactly one of --check, "
                           "--guardrail, --artifact, --decisions or --checkpoint.")


def answer_of(args, provenance):
    """The `approvals.Answer` an argparse namespace of this verb gives."""
    _checks_for(args)
    for form in ("check", "guardrail", "artifact", "checkpoint"):
        value = getattr(args, form, None)
        if value:
            return approvals.Answer(form, value, args.decision, args.approver, args.role,
                                    args.scope or "", provenance)
    return approvals.Answer("decisions", None, args.decision, args.approver, args.role,
                            args.scope or "", provenance)


def cmd_evidence_approve(args):
    if getattr(args, "delegated", False):
        return _delegated(args)
    if getattr(args, "as_agent", None):
        raise CompassError("compass evidence approve: --as names the agent of a delegated "
                           "approval, so it needs --delegated.")
    if not _terminal_attached():
        raise CompassError("compass evidence approve: this needs a terminal on standard "
                           "input. An approval is a person's act, so run the command "
                           "yourself in a terminal; an agent session cannot record one. "
                           "An agent asks for an approval with `compass evidence request`.")
    missing = [flag for flag, value in (("--approver", args.approver), ("--role", args.role))
               if value is None]
    if missing:
        raise CompassError(f"compass evidence approve: the following arguments are required: "
                           f"{', '.join(missing)}.")
    answer = approvals.checked(answer_of(args, TERMINAL))
    task_dir = resolve_issue_dir(args.task)
    with approvals.lock(task_dir):
        done = approvals.record(task_dir, answer)
    if done.note:
        print(done.note)
    return say(args, done.outcome, detail=done.detail, **done.data)


def _delegated(args):
    """An agent's approval under a delegation a person typed (ADR-069). It needs
    no terminal: the delegation is the person's decision. The record names the
    person as `approver`, the agent and the delegation. The pre-tool hook has
    already checked that `--as` is the agent Claude Code reports."""
    from compass_pkg import delegations
    agent = " ".join(str(args.as_agent or "").split())
    if not agent:
        raise CompassError("compass evidence approve: --delegated needs --as <agent>, the "
                           "agent's full name, such as compass:architect.")
    if args.approver or args.role:
        raise CompassError("compass evidence approve: a delegated approval names the person "
                           "who delegated; give no --approver or --role.")
    if args.decision != approval_records.APPROVED:
        raise CompassError("compass evidence approve: a delegation never covers a rejection. "
                           "Tell the person what you found, and stop.")
    draft = answer_of(args, {})
    task_dir = resolve_issue_dir(args.task)
    with approvals.lock(task_dir):
        delegation = delegations.authorise(task_dir, draft.form, draft.value, agent)
        provenance = {"via": "delegation", "approved_by_agent": agent,
                      "delegation": delegation["id"],
                      "session_id": os.environ.get("CLAUDE_CODE_SESSION_ID", "")}
        answer = approvals.checked(approvals.Answer(
            draft.form, draft.value, approval_records.APPROVED,
            delegation["delegated_by"], delegation.get("role") or "owner", draft.scope,
            provenance))
        done = approvals.record(task_dir, answer)
        delegations.record_use(task_dir, delegation, agent, done, done.outcome)
    if done.note:
        print(done.note)
    return say(args, done.outcome + f" Under {delegation['id']}, by {agent}.",
               detail=done.detail, **done.data)


def register(evidence_subs):
    """Add `approve` to the `evidence` group."""
    p = evidence_subs.add_parser(
        "approve", help="record a person's approval of a human check, a document or the "
                        "decisions taken for the person")
    form = p.add_mutually_exclusive_group(required=True)
    form.add_argument("--check", help="id of the human check")
    form.add_argument("--guardrail", metavar=approval_records.G5,
                      help="sign off guardrail `G5`, the only guardrail with a sign-off; "
                           "needs --scope and records an approval only")
    form.add_argument("--artifact", metavar="KIND",
                      help="approve this document, which reads awaiting-approval")
    form.add_argument("--decisions", action="store_true",
                      help="confirm the decisions taken for the person")
    form.add_argument("--checkpoint", metavar="STAGE",
                      help="answer the hand-off of this checkpoint stage (assess, define, "
                           "refine or plan)")
    issue_arg(p)
    p.add_argument("--approver", help="the approver's person id; required unless --delegated")
    p.add_argument("--role", help="the role the approver acts in; required unless --delegated")
    p.add_argument("--delegated", action="store_true",
                   help="record as the agent a person delegated to (/compass:delegate); "
                        "needs --as and no terminal")
    p.add_argument("--as", dest="as_agent", metavar="AGENT",
                   help="with --delegated: the agent's full name, as Claude Code reports it")
    p.add_argument("--scope", default="",
                   help="what the approval covers; required with --check and --guardrail")
    p.add_argument("--decision", default="approved", choices=DECISIONS,
                   help="approved (default) or rejected; a later rejection withdraws an "
                        "approval")
    p.set_defaults(func=cmd_evidence_approve, output_kind="hand-off")
