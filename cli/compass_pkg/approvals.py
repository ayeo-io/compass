# compass_pkg.approvals - the one writer of an approval record
"""Write a person's answer as an approval record, for every path that records
one (ADR-068 decision 4).

Three paths give an answer:

- `compass evidence approve` at a terminal (`approve_cmd`), with
  `via: terminal`;
- the Claude Code prompt hook, from a typed `/compass:approve` or
  `/compass:reject` (`prompt_approval`), with `via: prompt`;
- an agent under a delegation a person typed (ADR-069), with
  `via: delegation`.

Each builds an `Answer` and calls `record`. The paths differ only in how they
gather the answer and in what they check first: the terminal check stays in
`approve_cmd`, and the prompt hook checks the request it answers. So a record
from any path has the same fields, plus the path's `provenance`, and the
writer enumeration test of ADR-066 decision 1 reads the writers here.

`record(..., save=False)` runs every refusal and writes nothing.
`compass evidence request` uses it, so a request the approval would refuse is
refused when it is asked for, with the same words. A request does not yet
know who will answer it, so its `Answer` holds `approver=None`, and the
refusals that depend on the approver wait for the answer.

The forms:

- `check` reads the check from the issue's effective view and registers a
  `human-approval` entry with `check: <id>`. It never clears the sign-off of
  guardrail `G5`.
- `guardrail`, with the value `G5`, records the sign-off of that guardrail:
  one `human-approval` record whose `guardrail` key holds `G5`, with no other
  subject key, which `human-approval-present` counts
  (`approval_records.gives_g5`). It records an approval only.
- `artifact` approves a document that reads `awaiting-approval`: one
  `artifact-approval` record for each human check on the document, and the
  entry's `approved_by` and `approved_at`.
- `decisions` confirms the decisions an agent took for the person, through
  `decisions_taken.approve_set`.
- `checkpoint` records a person's answer to a checkpoint hand-off: one
  `checkpoint-approval` record, and the stage's `waited` outcome citing it.

A record holds the issue, the issue's generation and the time, which the
writer stamps itself. Callers hold `lock(task_dir)` around a record and any
state they change with it, so two answers cannot interleave.
"""
# DEPENDENCY: standard library (contextlib, dataclasses, os); compass_pkg.
# approval_records, atomic_io, core, effective. artifact_status,
# checkpoint_outcomes, decisions_taken, item_records and next_cmd are imported
# inside the functions that need them, as approve_cmd did.
from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass, field

from compass_pkg import approval_records, atomic_io, effective
from compass_pkg.core import CompassError, load_manifest, now_iso, save_manifest

VERB = "compass evidence approve"
DECISIONS = approval_records.DECISIONS
ARTIFACT_APPROVAL = approval_records.ARTIFACT_APPROVAL
#: A person's answer to one checkpoint hand-off. Kept apart from
#: `human-approval` so that no reader of that type, `human-approval-present`
#: (the check of guardrail `G5`), a human check or a waiver, meets it.
CHECKPOINT_APPROVAL = "checkpoint-approval"

#: The five subject forms, as `Answer.form` names them.
FORMS = ("check", "guardrail", "artifact", "checkpoint", "decisions")

#: Held while an answer is recorded and the state that goes with it changes.
LOCK = ".approval.lock"


@dataclass(frozen=True)
class Answer:
    """One person's answer to one subject, however it was gathered."""
    form: str                  # one of FORMS
    value: str | None          # check id, guardrail (`G5`), document kind, stage, or None
    decision: str              # "approved" or "rejected"
    approver: str
    role: str
    scope: str = ""
    provenance: dict = field(default_factory=dict)


@dataclass
class Recorded:
    """What `record` wrote, for the caller to report."""
    outcome: str
    detail: list
    data: dict
    evidence_ids: list
    note: str | None = None


@contextlib.contextmanager
def lock(task_dir):
    """Hold the issue's approval lock while the block runs."""
    with atomic_io.locked(os.path.join(task_dir, LOCK)):
        yield


def text(value):
    """A value as one line, with runs of white space made single spaces."""
    return " ".join(str(value or "").split())


def approver_name(value):
    """The approver's name, or a refusal: empty, or an agent."""
    name = text(value)
    if not name:
        raise CompassError(f"{VERB}: --approver must name the person who approves.")
    if name.lower() == "agent" or name.lower().startswith("agent:"):
        raise CompassError(f"{VERB}: an agent cannot approve. An approval is a person's; "
                           f"give that person's id with --approver.")
    return name


def checked(answer):
    """The answer with its text normalised, or the refusal every path gives
    before reading the issue."""
    if answer.form not in FORMS:
        raise CompassError(f"{VERB}: give exactly one of --check, --guardrail, --artifact, "
                           f"--decisions or --checkpoint.")
    if answer.decision not in DECISIONS:
        raise CompassError(f"{VERB}: the decision must be one of {' or '.join(DECISIONS)}, "
                           f"not '{answer.decision}'.")
    if answer.form == "guardrail":
        _guardrail_form(answer)
    approver = None if answer.approver is None else approver_name(answer.approver)
    role, scope = text(answer.role), text(answer.scope)
    required = ((("--role", role), ("--scope", scope)) if answer.form in ("check", "guardrail")
                else (("--role", role),))
    if approver is None:
        required = [one for one in required if one[0] != "--role"]
    for flag, value in required:
        if not value:
            raise CompassError(f"{VERB}: {flag} must not be empty; a record says in what role "
                               f"and for what the person approved.")
    return Answer(answer.form, answer.value, answer.decision, approver, role, scope,
                  dict(answer.provenance))


def _guardrail_form(answer):
    """Refuse a `guardrail` answer the form cannot record: a guardrail other
    than `G5`, or a rejection."""
    if answer.value != approval_records.G5:
        raise CompassError(f"{VERB}: --guardrail takes `G5` only, not '{answer.value}'; `G5` "
                           f"is the only guardrail with a sign-off. Nothing was written.")
    if answer.decision != approval_records.APPROVED:
        raise CompassError(f"{VERB}: `--guardrail G5` records an approval only, not "
                           f"--decision {answer.decision}. A rejected record would not "
                           f"withdraw an earlier sign-off. Nothing was written.")


def record(task_dir, answer, save=True):
    """Write `answer` as its records and return what was written. Raises
    CompassError, writing nothing, on any refusal. With `save` false, runs
    every refusal and writes nothing."""
    answer = checked(answer)
    writer = {"check": _record_check, "guardrail": _record_guardrail,
              "artifact": _record_artifact, "checkpoint": _record_checkpoint,
              "decisions": _record_decisions}[answer.form]
    return writer(task_dir, answer, save)


def refusal(task_dir, answer):
    """The reason `record` would refuse the answer, or None."""
    try:
        record(task_dir, answer, save=False)
    except CompassError as exc:
        return str(exc)
    return None


def _slug(task_dir):
    return os.path.basename(os.path.normpath(task_dir))


def _stamp():
    return now_iso().replace("+00:00", "Z")


def _taken(task):
    return {e.get("id") for e in task.get("evidence") or [] if isinstance(e, dict)}


# --- the forms ----------------------------------------------------------------------

def _check_of(view, check_id):
    if view is None:
        raise CompassError(f"{VERB}: this issue has no configuration to read its checks from. "
                           f"Run `compass approach evaluate --write`.")
    checks = view.config.get("checks") or {}
    check = checks.get(check_id)
    approvable = sorted(name for name, body in checks.items()
                        if isinstance(body, dict) and body.get("kind") == "human"
                        and body.get("approvers"))
    known = (f"the human checks that list approvers are {', '.join(approvable)}"
             if approvable else "it configures no human check that lists approvers")
    if not isinstance(check, dict):
        raise CompassError(f"{VERB}: no such check '{check_id}' in this issue's "
                           f"configuration; {known}.")
    if check.get("kind") != "human":
        raise CompassError(f"{VERB}: '{check_id}' is a {check.get('kind')} check, not a human "
                           f"check. Only a human check takes an approval.")
    if not check.get("approvers"):
        # An item of the Definition of Ready or Done is ticked by a person even when
        # its check lists no approvers (the declared approvers, or the owner, tick it).
        from compass_pkg import item_records
        if item_records.unlisted_problem(view, check_id, VERB) is None:
            return check
        raise CompassError(f"{VERB}: '{check_id}' lists no approvers and is not an item of "
                           f"this issue's Definition of Ready or Done, so an approval would "
                           f"not be read; {known}.")
    return check


def _may_tick(task_dir, approver, check_id):
    """Who may tick an item whose check lists no approvers: a name in any
    `approvers:` list of the project file, else its owner."""
    from compass_pkg import decisions_taken
    declared, owner = decisions_taken.project_approvers(task_dir)
    if declared:
        if approval_records.approver_listed(declared, approver, owner):
            return
        raise CompassError(
            f"{VERB}: {approver} is not among the approvers this project declares "
            f"({', '.join(sorted(set(declared)))}), so the tick of '{check_id}' would not "
            f"count.")
    if approval_records.approver_listed([approval_records.OWNER], approver, owner):
        return
    raise CompassError(
        f"{VERB}: this project declares no approvers, so only its owner may tick "
        f"'{check_id}'" + (f" ({owner})." if owner else
                          "; it declares no owner either, so add `owner:` or an "
                          "`approvers:` list to compass.yml."))


def _record_check(task_dir, answer, save):
    check_id = answer.value
    task, task_path = load_manifest(task_dir)
    check = _check_of(effective.view_or_legacy(task_dir), check_id)
    owner = approval_records.project_owner(task_dir)
    if answer.approver is None:
        pass
    elif check.get("approvers"):
        listed = [str(one) for one in check["approvers"]]
        if not approval_records.approver_listed(listed, answer.approver, owner):
            raise CompassError(f"{VERB}: {answer.approver} is not an approver of "
                               f"'{check_id}', so the record would not count. "
                               f"{approval_records.listing(check_id, listed, owner)}.")
    else:
        _may_tick(task_dir, answer.approver, check_id)
    taken = _taken(task)
    number = 1 + len([e for e in task.get("evidence") or []
                      if isinstance(e, dict) and e.get("type") == "human-approval"
                      and e.get("check") == check_id])
    while f"EV-APPROVAL-{check_id}-{number}" in taken:
        number += 1
    evidence_id = f"EV-APPROVAL-{check_id}-{number}"
    entry = {"id": evidence_id, "type": "human-approval", "check": check_id,
             "approver": answer.approver, "role": answer.role, "scope": answer.scope,
             "decision": answer.decision, "timestamp": _stamp(), "issue": _slug(task_dir),
             "generation": task.get("generation")}
    entry.update(answer.provenance)
    if save:
        task.setdefault("evidence", []).append(entry)
        save_manifest(task, task_path)
    return Recorded(
        f"{VERB}: {check_id} - {answer.decision} by {answer.approver} recorded as "
        f"{evidence_id}.",
        [f"record     : {evidence_id} in manifest.yml evidence",
         f"issue      : {entry['issue']}",
         f"generation : {approval_records.shown(entry['generation'])}"],
        dict(check=check_id, answer=answer.decision, evidence_id=evidence_id,
             approver=answer.approver, role=answer.role, scope=answer.scope,
             issue=entry["issue"], generation=entry["generation"], at=entry["timestamp"]),
        [evidence_id])


def _record_guardrail(task_dir, answer, save):
    """The sign-off of guardrail `G5`. It names no other subject, so
    `human-approval-present` counts it and no human check, item or waiver
    reads it. No approver list is checked: guardrail `G5` lists none."""
    task, task_path = load_manifest(task_dir)
    taken = _taken(task)
    number = 1 + len([e for e in task.get("evidence") or []
                      if isinstance(e, dict) and e.get("type") == "human-approval"
                      and e.get("decision") in DECISIONS
                      and approval_records.gives_g5(e)])
    while f"EV-APPROVAL-G5-{number}" in taken:
        number += 1
    evidence_id = f"EV-APPROVAL-G5-{number}"
    entry = {"id": evidence_id, "type": "human-approval", "guardrail": approval_records.G5,
             "approver": answer.approver, "role": answer.role, "scope": answer.scope,
             "decision": approval_records.APPROVED, "timestamp": _stamp(),
             "issue": _slug(task_dir), "generation": task.get("generation")}
    entry.update(answer.provenance)
    if save:
        task.setdefault("evidence", []).append(entry)
        save_manifest(task, task_path)
    return Recorded(
        f"{VERB}: guardrail `G5` - signed off by {answer.approver} recorded as "
        f"{evidence_id}.",
        [f"record     : {evidence_id} in manifest.yml evidence",
         f"issue      : {entry['issue']}",
         f"generation : {approval_records.shown(entry['generation'])}"],
        dict(guardrail=approval_records.G5, answer=entry["decision"],
             evidence_id=evidence_id, approver=answer.approver, role=answer.role,
             scope=answer.scope, issue=entry["issue"], generation=entry["generation"],
             at=entry["timestamp"]),
        [evidence_id])


def _checkpoint_approver(task_dir, approver):
    """Refuse a name that may not answer a checkpoint: a name in any
    `approvers:` list of the project file, else its owner. Returns the line to
    print when the project declares neither, so any person may answer."""
    from compass_pkg import decisions_taken
    declared, owner = decisions_taken.project_approvers(task_dir)
    if not declared and not owner:
        return (f"{VERB}: this project declares no approvers or owner, so any person may "
                f"answer a checkpoint.")
    allowed = declared or [approval_records.OWNER]
    if approval_records.approver_listed(allowed, approver, owner):
        return None
    named = (f"it declares {', '.join(sorted(set(declared)))}" if declared
             else f"its owner is {owner}")
    raise CompassError(f"{VERB}: {approver} is not an approver of this project ({named}), so "
                       f"the answer would not count. Nothing was written.")


def _record_checkpoint(task_dir, answer, save):
    from compass_pkg import checkpoint_outcomes, next_cmd
    stage = answer.value
    if answer.decision != approval_records.APPROVED:
        raise CompassError(f"{VERB}: --checkpoint records an approval only, not "
                           f"--decision {answer.decision}. To send the issue back, say so at "
                           f"the {stage} hand-off. Nothing was written.")
    task, task_path = load_manifest(task_dir)
    checkpoint_outcomes.refuse_unjudged(task, task_dir, VERB)
    checkpoint_outcomes.refuse_stage(task, stage, VERB)
    if stage not in next_cmd._stages_on_record(next_cmd._typed(task), task_dir):
        raise CompassError(f"{VERB}: {stage} has not run: its record is not written, so there "
                           f"is no hand-off to answer yet. Nothing was written.")
    note = (None if answer.approver is None
            else _checkpoint_approver(task_dir, answer.approver))
    stamp = _stamp()
    taken = _taken(task)
    number = 1
    while f"EV-CHECKPOINT-{stage}-{number}" in taken:
        number += 1
    evidence_id = f"EV-CHECKPOINT-{stage}-{number}"
    entry = {"id": evidence_id, "type": CHECKPOINT_APPROVAL, "checkpoint": stage,
             "approver": answer.approver, "role": answer.role,
             "scope": answer.scope or f"the {stage} hand-off",
             "decision": approval_records.APPROVED, "timestamp": stamp,
             "issue": _slug(task_dir), "generation": task.get("generation")}
    entry.update(answer.provenance)
    if save:
        task.setdefault("evidence", []).append(entry)
        checkpoint_outcomes.set_outcome(task, {
            "stage": stage, "outcome": checkpoint_outcomes.WAITED, "by": answer.approver,
            "at": stamp, "evidence": evidence_id})
        save_manifest(task, task_path)
    return Recorded(
        f"{VERB}: the {stage} checkpoint - answered by {answer.approver}, recorded as "
        f"{evidence_id}.",
        [f"record     : {evidence_id} in manifest.yml evidence",
         f"outcome    : {stage} -> waited"],
        dict(checkpoint=stage, answer=entry["decision"], evidence_id=evidence_id,
             approver=answer.approver, role=answer.role, scope=entry["scope"],
             issue=entry["issue"], generation=entry["generation"], at=stamp),
        [evidence_id], note)


def _record_artifact(task_dir, answer, save):
    from compass_pkg import artifact_status
    kind = answer.value
    if answer.decision != approval_records.APPROVED:
        raise CompassError(f"{VERB}: --artifact records an approval only. To send {kind} "
                           f"back, run `compass issue artifact set {kind} --status draft`.")
    task, task_path = load_manifest(task_dir)
    entry = next((a for a in task.get("artifacts") or []
                  if isinstance(a, dict) and a.get("kind") == kind), None)
    if entry is None:
        raise CompassError(f"{VERB}: '{kind}' is not a document this issue registered.")
    if entry.get("status") != artifact_status.AWAITING:
        raise CompassError(
            f"{VERB}: {kind} reads {entry.get('status')}, not awaiting-approval, so there is "
            f"nothing to approve. A document with a human check moves to awaiting-approval "
            f"when the stage after it records its work; to ask for approval now, run "
            f"`compass issue artifact set {kind} --status awaiting-approval`.")
    view = effective.view_or_legacy(task_dir)
    checks = artifact_status.human_checks(view, kind)
    owner = approval_records.project_owner(task_dir)
    for check_id in checks if answer.approver is not None else []:
        listed = [str(one) for one in (view.config["checks"][check_id].get("approvers") or [])]
        if listed and not approval_records.approver_listed(listed, answer.approver, owner):
            raise CompassError(
                f"{VERB}: {answer.approver} is not an approver of '{check_id}', which {kind} "
                f"carries, so the record would not count. "
                f"{approval_records.listing(check_id, listed, owner)}.")
    stamp = _stamp()
    taken = _taken(task)
    number = 1
    records = []
    for check_id in checks or [None]:
        while f"EV-APPROVAL-ARTIFACT-{kind}-{number}" in taken:
            number += 1
        evidence_id = f"EV-APPROVAL-ARTIFACT-{kind}-{number}"
        taken.add(evidence_id)
        fields = dict(artifact=kind, check=check_id, approver=answer.approver,
                      role=answer.role, decision=answer.decision, timestamp=stamp,
                      scope=answer.scope)
        one = {"id": evidence_id, "type": ARTIFACT_APPROVAL}
        one.update({k: v for k, v in fields.items() if v not in (None, "")})
        one.update(issue=_slug(task_dir), generation=task.get("generation"))
        one.update(answer.provenance)
        records.append(one)
    ids = [one["id"] for one in records]
    if save:
        task.setdefault("evidence", []).extend(records)
        artifact_status.clear_approver(entry)
        entry.update(status=artifact_status.APPROVED, approved_by=answer.approver,
                     approved_at=stamp)
        save_manifest(task, task_path)
    return Recorded(
        f"{VERB}: {kind} - approved by {answer.approver} recorded as {', '.join(ids)}.",
        [f"record     : {', '.join(ids)} in manifest.yml evidence",
         f"document   : {kind} -> approved by {answer.approver}"],
        dict(artifact=kind, answer=answer.decision, evidence_id=ids[0], evidence_ids=ids,
             approver=answer.approver, role=answer.role, scope=answer.scope or None,
             at=stamp, status=artifact_status.APPROVED),
        ids)


def _record_decisions(task_dir, answer, save):
    from compass_pkg import decisions_taken
    outcome, detail, data, ids = decisions_taken.approve_set(task_dir, answer, save)
    return Recorded(outcome, detail, data, ids)
