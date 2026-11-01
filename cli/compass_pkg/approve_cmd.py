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
# core, old_names, terminal.
from __future__ import annotations

import os
import re
import sys

from compass_pkg import approval_records, approvals, launcher, old_names
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
        word, hint = launcher.terminal_command()
        raise CompassError("compass evidence approve: this needs a terminal on standard "
                           "input. An approval is a person's act, so run the command "
                           f"yourself in a terminal, as `{word} evidence approve ...`; an "
                           "agent session cannot record one. An agent asks for an "
                           "approval with `compass evidence request`."
                           + (f" {hint}" if hint else ""))
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


def _delegated_places(slug):
    """`(issue folder, store folder)` of a delegated approval. The issue is found
    by its exact slug in every worktree of the repository, so a slug that two
    hold is refused, naming both. The store is the common store."""
    from compass_pkg import worktree_lookup
    project = worktree_lookup.project_folder(os.getcwd())
    listing = worktree_lookup.list_worktrees(project)
    try:
        task_dir = worktree_lookup.find_issue(listing, slug)
    except worktree_lookup.HeldTwice as exc:
        raise CompassError(f"compass evidence approve: the issue '{slug}' is held by more "
                           f"than one worktree: {' and '.join(exc.folders)}. Compass cannot "
                           f"tell which one is meant, and an agent's approval never chooses. Ask "
                           f"the person: `compass evidence request`, then they type "
                           f"/compass:approve in the worktree whose record they mean. "
                           f"Nothing was written.") from None
    except worktree_lookup.NotFound as exc:
        note = f" {exc.note[0].upper()}{exc.note[1:]}." if exc.note else ""
        raise CompassError(f"compass evidence approve: the issue '{slug}' is in none of the "
                           f"work folders searched: {', '.join(exc.searched)}.{note} "
                           f"Nothing was written.") from None
    store = worktree_lookup.common_store(project)
    if store.folder is None:
        raise CompassError(f"compass evidence approve: {store.why_none}. Nothing was "
                           f"written.")
    return task_dir, store.folder


def _raw_words():
    """The words the command line gave after `evidence approve`, which the
    pre-tool hook's ticket binds to."""
    argv = sys.argv[1:]
    for i in range(len(argv) - 1):
        if argv[i] == "evidence" and argv[i + 1] == "approve":
            return argv[i + 2:]
    raise CompassError("compass evidence approve: Compass could not read this command line, "
                       "so it cannot match it to the pre-tool hook's ticket. Nothing was "
                       "written.")


def _take_ticket(store, agent):
    """The pre-tool hook's ticket for this call, taken under the store lock.
    The session comes from it and never from the environment, which a command
    can set to any value."""
    from compass_pkg import delegation_tickets
    try:
        return delegation_tickets.take(store, _raw_words(), agent)
    except delegation_tickets.TicketRefused as exc:
        raise CompassError(f"compass evidence approve: {exc} Nothing was written.") from None


def _stray_files(task_dir, store_compass):
    """A sentence that names each delegation file in the issue's own `.compass/`
    when that is not the common store: Compass 7.0.0 read it, and no longer does."""
    own = os.path.dirname(os.path.dirname(os.path.normpath(task_dir)))
    if os.path.realpath(own) == os.path.realpath(store_compass):
        return ""
    folder = os.path.join(own, "delegations")
    try:
        names = sorted(n for n in os.listdir(folder) if re.fullmatch(r"DL-\d+\.yml", n))
    except OSError:
        return ""
    if not names:
        return ""
    paths = ", ".join(os.path.join(folder, n) for n in names)
    return (f" {paths} is a delegation file that Compass no longer reads: a delegation is "
            f"kept in the main checkout's common store now. Type /compass:delegate again.")


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
    if not args.task:
        raise CompassError("compass evidence approve: a delegated approval names its issue "
                           "with --issue <slug>, such as --issue my-issue. Nothing was "
                           "written.")
    draft = answer_of(args, {})
    task_dir, store = _delegated_places(args.task)
    store_compass = os.path.dirname(store)
    if not os.path.isdir(store):
        # No delegation was ever made: refuse without creating the folder.
        raise CompassError(f"compass evidence approve: no delegation in force names "
                           f"{agent}. Ask the person with `compass evidence request` and "
                           f"stop. Nothing was written."
                           + _stray_files(task_dir, store_compass))
    try:
        # The delegation lock, taken inside the issue lock in the order the prompt
        # hook takes them, keeps a /compass:revoke or another use from landing
        # between the check and the count. The ticket is taken under it too.
        with approvals.lock(task_dir), delegations.locked(store_compass):
            ticket = _take_ticket(store, agent)
            delegation = delegations.authorise(task_dir, draft.form, draft.value, agent,
                                               ticket["session_id"], store_compass)
            provenance = {"via": "delegation", "approved_by_agent": agent,
                          "delegation": delegation["id"],
                          "session_id": ticket["session_id"]}
            answer = approvals.checked(approvals.Answer(
                draft.form, draft.value, approval_records.APPROVED,
                delegation["delegated_by"], delegation.get("role") or "owner", draft.scope,
                provenance))
            done = approvals.record(task_dir, answer)
            delegations.record_use(task_dir, delegation, agent, done, done.outcome,
                                   store_compass)
    except CompassError as exc:
        raise CompassError(str(exc) + _stray_files(task_dir, store_compass)) from None
    if done.note:
        print(done.note)
    return say(args, done.outcome + f" Under {delegation['id']}, by {agent}.",
               detail=done.detail, **done.data)


def register(evidence_subs):
    """Add `approve` to the `evidence` group."""
    p = evidence_subs.add_parser(
        "approve", help="record a person's approval of a human check, a document or the "
                        "decisions taken for the person",
        # No abbreviated flag: the pre-tool hook recognises `--delegated` by name,
        # and a prefix such as `--deleg` must not reach the delegated path unseen.
        allow_abbrev=False)
    form = p.add_mutually_exclusive_group(required=True)
    form.add_argument("--check", type=old_names.check_type, help="id of the human check")
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
    # `compass evidence request`, which asks for what this verb records, is
    # registered beside it so the entry point stays thin.
    from compass_pkg import approval_requests
    approval_requests.register(evidence_subs)
