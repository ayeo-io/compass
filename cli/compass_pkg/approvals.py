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
- `decisions` confirms the decisions an agent took for the person, through
  `decisions_taken.approve_set`.
- `checkpoint` records a person's answer to a checkpoint hand-off: one
  `checkpoint-approval` record, and the stage's `waited` outcome citing it.
- `waiver` approves one waiver of the issue (`waiver_records`): one
  `human-approval` record with `waiver: W-<n>`, the check it excuses and the
  reason. It records an approval only, and never clears guardrail `G5`.
- `ship` approves the change of an issue that owes the ship approval
  (`ship_approval`, #355): one `human-approval` record with `ship: <slug>`,
  the issue's generation and the `HEAD` commit when it was recorded. It
  records an approval only. It never clears guardrail `G5`, and a `G5`
  sign-off is not a ship approval (VD-029).

A record holds the issue, the issue's generation and the time, which the
writer stamps itself. Callers hold `lock(task_dir)` around a record and any
state they change with it, so two answers cannot interleave.
"""
# DEPENDENCY: standard library (contextlib, dataclasses, os); compass_pkg.
# approval_records, atomic_io, core, effective. checkpoint_outcomes, decisions_taken, item_records, next_cmd and next_step are imported
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

#: The types `compass evidence add` refuses, and why. Each has its own writer:
#: an approval is a person's act, written only by the writers here, and a record
#: of the four-layer acceptance strategy only by its command. A `human-approval`
#: record added by hand held only an id, a type and a path, which no approval
#: reader counts (GitHub issue #571).
EVIDENCE_ADD_REFUSALS = {
    CHECKPOINT_APPROVAL: (
        "compass evidence add: a checkpoint-approval record is a person's answer; run "
        "compass evidence approve --checkpoint <stage> at a terminal."),
    "human-approval": (
        "compass evidence add: a human-approval record is a person's approval. In "
        "Claude Code the person types /compass:approve after the agent asks with "
        "compass evidence request; an agent the person delegated to runs compass "
        "evidence approve --delegated --as <agent>; at a terminal the person runs "
        "compass evidence approve. Nothing was written."),
    # The records of the four-layer acceptance strategy (ADR-086): each is the run of
    # the project's own commands, so a file added by hand is a claim, not a record.
    "isolation-proof": (
        "compass evidence add: an isolation-proof record is written only by compass "
        "isolation record, which runs the project's own suite in parallel and each "
        "scenario's tests twice. A written note does not prove isolation. Nothing was "
        "written."),
    "layering": (
        "compass evidence add: a layering record is written only by compass layering "
        "record, which runs the project's own layering test. A written note does not "
        "prove the layer rules hold. Nothing was written."),
}

#: The subject forms, as `Answer.form` names them. 9.0.0 removed `artifact`, which
#: approved a document, with the document statuses (ADR-091), and added `waiver`
#: (ADR-094), and 9.0.0 added `ship`, the typed ship approval (#355).
FORMS = ("check", "guardrail", "checkpoint", "decisions", "waiver", "ship")
#: What every refusal of a missing or doubled form says.
ONE_FORM = ("give exactly one of --check, --guardrail, --decisions, --checkpoint, --waiver "
            "or --ship")

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
    # For an answer under a delegation: `(id, copy)` from `delegations.copy_of`,
    # which each writer keeps in the manifest in the same save as the record.
    authority: tuple | None = None


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


def lock_all(task_dirs):
    """Hold the approval lock of every issue in `task_dirs` while the block
    runs, taken in one sorted order (`atomic_io.locked_all`)."""
    return atomic_io.locked_all(os.path.join(d, LOCK) for d in task_dirs)


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
        raise CompassError(f"{VERB}: {ONE_FORM}.")
    if answer.decision not in DECISIONS:
        raise CompassError(f"{VERB}: the decision must be one of {' or '.join(DECISIONS)}, "
                           f"not '{answer.decision}'.")
    if answer.form == "guardrail":
        _guardrail_form(answer)
    if answer.form == "waiver" and answer.decision != approval_records.APPROVED:
        raise CompassError(f"{VERB}: --waiver records an approval only, not --decision "
                           f"{answer.decision}. A waiver nobody approves excuses nothing, "
                           f"and `compass waiver withdraw` removes it. Nothing was written.")
    if answer.form == "ship" and answer.decision != approval_records.APPROVED:
        raise CompassError(f"{VERB}: --ship records an approval only, not --decision "
                           f"{answer.decision}. To hold the change back, say so to the "
                           f"agent. Nothing was written.")
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
                  dict(answer.provenance), answer.authority)


def keep_authority(task, answer):
    """Copy the delegation that authorized `answer`, if any, into the manifest
    dict (`delegations.keep_copy`). Each writer calls it just before the save
    that writes the record, so the record and its authority land together."""
    if answer.authority is not None:
        from compass_pkg import delegations
        delegations.keep_copy(task, answer.authority)


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
              "checkpoint": _record_checkpoint,
              "decisions": _record_decisions, "waiver": _record_waiver,
              "ship": _record_ship}[answer.form]
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

def _check_of(view, check_id, task=None):
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
        if item_records.unlisted_problem(view, check_id, VERB, task=task) is None:
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
    check = _check_of(effective.view_or_legacy(task_dir), check_id, task)
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
        keep_authority(task, answer)
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
        keep_authority(task, answer)
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


def _checkpoint_approver(task_dir, approver, subject="answer a checkpoint"):
    """Refuse a name that may not answer a checkpoint (or give the ship
    approval): a name in any `approvers:` list of the project file, else its
    owner. Returns the line to print when the project declares neither, so any
    person may answer."""
    from compass_pkg import decisions_taken
    declared, owner = decisions_taken.project_approvers(task_dir)
    if not declared and not owner:
        return (f"{VERB}: this project declares no approvers or owner, so any person may "
                f"{subject}.")
    allowed = declared or [approval_records.OWNER]
    if approval_records.approver_listed(allowed, approver, owner):
        return None
    named = (f"it declares {', '.join(sorted(set(declared)))}" if declared
             else f"its owner is {owner}")
    raise CompassError(f"{VERB}: {approver} is not an approver of this project ({named}), so "
                       f"the answer would not count. Nothing was written.")


def _hand_off_reached(task, task_dir, stage):
    """True when the stage's work is on record, so its hand-off can be answered.
    On the four-stage path (ADR-092) specify counts as done only once its listed
    checkpoint has an outcome, and ship only once the issue is closed, so those
    two hand-offs are read from the work they hand off: the written scenarios,
    and a finished build."""
    from compass_pkg import next_cmd, next_step
    from compass_pkg.path_stages import is_path_issue
    from compass_pkg.stable_ids import STAGE_BUILD, STAGE_SHIP, STAGE_SPECIFY
    typed = next_cmd._typed(task)
    if is_path_issue(typed) and stage == STAGE_SPECIFY:
        return next_step.specify_written(typed)
    done = next_cmd._stages_on_record(typed, task_dir)
    if is_path_issue(typed) and stage == STAGE_SHIP:
        return STAGE_BUILD in done
    return stage in done


def _record_checkpoint(task_dir, answer, save):
    from compass_pkg import checkpoint_outcomes
    stage = answer.value
    if answer.decision != approval_records.APPROVED:
        raise CompassError(f"{VERB}: --checkpoint records an approval only, not "
                           f"--decision {answer.decision}. To send the issue back, say so at "
                           f"the {stage} hand-off. Nothing was written.")
    task, task_path = load_manifest(task_dir)
    checkpoint_outcomes.refuse_unjudged(task, task_dir, VERB)
    checkpoint_outcomes.refuse_stage(task, stage, VERB)
    if not _hand_off_reached(task, task_dir, stage):
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
        keep_authority(task, answer)
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


def _record_decisions(task_dir, answer, save):
    from compass_pkg import decisions_taken
    outcome, detail, data, ids = decisions_taken.approve_set(task_dir, answer, save)
    return Recorded(outcome, detail, data, ids)


def _record_waiver(task_dir, answer, save):
    """The approval of one waiver of the issue. The record copies the check and
    the reason the waiver names now, so a waiver changed after it was approved
    no longer reads as approved (`waiver_records.approval`)."""
    from compass_pkg import waiver_records
    waiver_id = answer.value
    if not isinstance(waiver_id, str) or not waiver_records.ID.fullmatch(waiver_id):
        raise CompassError(f"{VERB}: --waiver takes a waiver id such as W-1, not "
                           f"'{waiver_id}'. Nothing was written.")
    task, task_path = load_manifest(task_dir)
    why = waiver_records.refusal(task, task_dir, waiver_id, answer.approver)
    if why:
        raise CompassError(f"{VERB}: {why}. Nothing was written.")
    waiver = waiver_records.find(task, waiver_id)
    taken = _taken(task)
    number = 1
    while f"EV-WAIVER-{waiver_id}-{number}" in taken:
        number += 1
    evidence_id = f"EV-WAIVER-{waiver_id}-{number}"
    scope = answer.scope or f"waiver {waiver_id} of {waiver['check']}"
    entry = {"id": evidence_id, "type": "human-approval",
             waiver_records.SUBJECT: waiver_id,
             waiver_records.CHECK: waiver["check"],
             waiver_records.REASON: waiver["reason"],
             "approver": answer.approver, "role": answer.role, "scope": scope,
             "decision": approval_records.APPROVED, "timestamp": _stamp(),
             "issue": _slug(task_dir), "generation": task.get("generation")}
    entry.update(answer.provenance)
    if save:
        task.setdefault("evidence", []).append(entry)
        keep_authority(task, answer)
        save_manifest(task, task_path)
    return Recorded(
        f"{VERB}: waiver {waiver_id} of {waiver['check']} - approved by {answer.approver} "
        f"recorded as {evidence_id}.",
        [f"record     : {evidence_id} in manifest.yml evidence",
         f"waives     : {waiver['check']} on issue {entry['issue']} only",
         f"reason     : {waiver['reason']}"],
        dict(waiver=waiver_id, check=waiver["check"], answer=entry["decision"],
             evidence_id=evidence_id, approver=answer.approver, role=answer.role,
             scope=scope, issue=entry["issue"], generation=entry["generation"],
             at=entry["timestamp"]),
        [evidence_id])


def _head(task_dir):
    """The project's `HEAD` commit, or None outside a git repository. The record
    holds it for a reader: no check compares it."""
    import subprocess

    from compass_pkg import project_settings
    try:
        done = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=10, cwd=project_settings.find_project_root(task_dir))
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def _record_ship(task_dir, answer, save):
    """The typed ship approval (#355): a person approves the change of this
    issue at ship. The record names the issue under `ship`, a subject key, so
    it never clears guardrail `G5`; `ship-approval-present` reads it with the
    issue's generation. It refuses an issue that does not owe the ship
    approval, and a second approval while one stands."""
    from compass_pkg import ship_approval
    task, task_path = load_manifest(task_dir)
    slug = _slug(task_dir)
    if not ship_approval.owed(task):
        raise CompassError(f"{VERB}: issue {slug} does not owe the ship approval: its "
                           f"`evidence_required` does not list `{ship_approval.TOKEN}`. "
                           f"Nothing was written.")
    note = (None if answer.approver is None
            else _checkpoint_approver(task_dir, answer.approver, "give the ship approval"))
    evidence = [e for e in task.get("evidence") or [] if isinstance(e, dict)]
    withdrawn = {e.get("withdraws") for e in evidence
                 if e.get("type") == approval_records.WITHDRAWAL}
    standing = [e.get("id") for e in evidence
                if e.get("type") == "human-approval" and e.get(ship_approval.SHIP) == slug
                and e.get("generation") == task.get("generation")
                and e.get("decision") == approval_records.APPROVED
                and e.get("id") not in withdrawn]
    if standing:
        raise CompassError(f"{VERB}: the change of issue {slug} is already approved at ship "
                           f"({standing[0]}). Nothing was written.")
    taken = _taken(task)
    number = 1
    while f"EV-SHIP-APPROVAL-{number}" in taken:
        number += 1
    evidence_id = f"EV-SHIP-APPROVAL-{number}"
    scope = answer.scope or f"the change of issue {slug} at ship"
    entry = {"id": evidence_id, "type": "human-approval", ship_approval.SHIP: slug,
             "head": _head(task_dir) if save else None,
             "approver": answer.approver, "role": answer.role, "scope": scope,
             "decision": approval_records.APPROVED, "timestamp": _stamp(),
             "issue": slug, "generation": task.get("generation")}
    entry.update(answer.provenance)
    if save:
        task.setdefault("evidence", []).append(entry)
        keep_authority(task, answer)
        save_manifest(task, task_path)
    return Recorded(
        f"{VERB}: the change of issue {slug} - approved at ship by {answer.approver}, "
        f"recorded as {evidence_id}.",
        [f"record     : {evidence_id} in manifest.yml evidence",
         f"issue      : {slug}",
         f"generation : {approval_records.shown(entry['generation'])}",
         f"head       : {entry['head'] or 'none'}"],
        dict(ship=slug, answer=entry["decision"], evidence_id=evidence_id,
             approver=answer.approver, role=answer.role, scope=scope, issue=slug,
             generation=entry["generation"], head=entry["head"], at=entry["timestamp"]),
        [evidence_id], note)
