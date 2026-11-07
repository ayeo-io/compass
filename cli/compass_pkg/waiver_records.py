# compass_pkg.waiver_records - a waiver of one check on one issue, and its approval
"""A waiver excuses one check on one issue (ADR-094, #357 section 4). It needs
a reason and a person's approval.

The issue's manifest holds the waivers:

    waivers:
      - {id: W-1, check: suite-passed, reason: "...", requested_at: ..., requested_by: ...}

`compass waiver add` writes one and `compass waiver withdraw` removes an
unapproved one or marks an approved one withdrawn (`waiver_cmd`). A waiver
excuses nothing until a person approves it. The approval is a
`human-approval` record that names the waiver (`waiver: W-1`), the check it
excuses (`waived_check`) and the reason the person saw (`waiver_reason`).
`approvals.record` writes it, from a typed `/compass:approve`, a terminal or a
delegation typed with `--for waivers`. The record names a subject, so it never
clears guardrail `G5` (`approval_records.gives_g5`).

`excused` is what `compass check` reads. A waiver excuses its check only when:

- it has a reason and names a check;
- it is not withdrawn;
- its check is not one the check set never waives (`never_waived`): the check
  `human-approval-present` and every check of gate `G5`;
- a `human-approval` record names it, holds `decision: approved` and the four
  fields, is for this issue at its current generation, names the same check
  and reason, is by an allowed approver, and no `approval-withdrawal` record
  withdraws it. A reassessment that moves the issue to a new generation asks
  for a new approval.

Who may approve: the names in `approvers.waiver` of `compass.yml`, else in
`approvers.issue-waiver` (its 8.x name), else the project's `owner`. With no
owner, nobody may (`W-NO-OWNER`). The CLI checks a name; it never
authenticates the person, as for every approval.

A waiver an issue layer holds in `config:` (ADR-039) is not read here: the
issue layer and `compass_pkg.waivers` keep reading it until the layer goes.
"""
# DEPENDENCY: standard library (os, re); compass_pkg.approval_records, check_set, core
# (CompassError, now_iso). compass_pkg.project_settings is imported inside `approvers` to
# read the project file, and compass_pkg.effective inside `policy_checks`.
from __future__ import annotations

import os
import re

from compass_pkg import approval_records, check_set
from compass_pkg.core import CompassError

KEY = "waivers"
ID = re.compile(r"W-[1-9][0-9]*")
#: The approver list a project names in `approvers:`, and its 8.x name.
KIND, OLD_KIND = "waiver", "issue-waiver"
NO_OWNER = "W-NO-OWNER"
#: The fields of a waiver's approval record besides the four every approval holds.
SUBJECT, CHECK, REASON = "waiver", "waived_check", "waiver_reason"

APPROVED, UNAPPROVED, WITHDRAWN = "approved", "unapproved", "withdrawn"


def text(value):
    """A value as one line, or '' when it holds no text."""
    return " ".join(str(value).split()) if isinstance(value, str) else ""


def listed(task):
    """The waivers of an issue's manifest, in order. An entry that is not a
    mapping is skipped. A manifest written before 9.0.0 has none."""
    held = (task or {}).get(KEY)
    return [w for w in held if isinstance(w, dict)] if isinstance(held, list) else []


def find(task, waiver_id):
    """The waiver with this id, or None."""
    return next((w for w in listed(task) if w.get("id") == waiver_id), None)


def never_waived(doc=None):
    """The ids of the checks no waiver excuses, from the check set's
    `never_waived`: a `checks.<id>` entry names the check, and a `gates.<id>`
    entry names every check the gate lists."""
    doc = doc if doc is not None else check_set.load()
    out = set()
    for name in doc.get("never_waived") or []:
        catalogue, _, entry = str(name).partition(".")
        if catalogue == "checks":
            out.add(entry)
        elif catalogue == "gates":
            out.update((doc.get("gates") or {}).get(entry, {}).get("checks") or [])
    return out


def never_waived_gates(doc=None):
    """The ids of the gates whose rows no waiver excuses."""
    doc = doc if doc is not None else check_set.load()
    return {str(n).partition(".")[2] for n in doc.get("never_waived") or []
            if str(n).startswith("gates.")}


def policy_checks(task_dir):
    """The ids of the checks the issue's policy holds: its stored generation,
    else the live view, else the check set itself."""
    from compass_pkg import effective
    try:
        view = effective.view_or_legacy(task_dir)
    except CompassError:
        view = None
    checks = (view.config.get("checks") if view is not None else None) or \
        check_set.load().get("checks") or {}
    return set(checks)


def approvers(task_dir):
    """`(names, owner, fault)`: who may approve a waiver on this issue. `names`
    may hold `owner`, which `approval_records.approver_listed` reads as the
    project's owner. `fault` names why nobody may, or is None."""
    from compass_pkg import project_settings
    owner = approval_records.project_owner(task_dir)
    if not owner:
        return [], None, (f"{NO_OWNER}: no owner is declared in compass.yml, so nobody may "
                          f"approve a waiver")
    try:
        loaded = project_settings.project_file(project_settings.find_project_root(task_dir))
    except Exception:                                      # noqa: BLE001
        loaded = None
    held = (loaded.get("approvers") if loaded else None) or {}
    names = held.get(KIND) if isinstance(held, dict) else None
    if names is None and isinstance(held, dict):
        names = held.get(OLD_KIND)
    if names is None:
        return [approval_records.OWNER], owner, None
    if not isinstance(names, list) or not all(text(n) for n in names):
        return [], owner, f"approvers.{KIND} is not a list of names, so nobody may approve"
    return [str(n) for n in names], owner, None


def refusal(task, task_dir, waiver_id, approver=None):
    """Why a person may not approve this waiver now, or None. `approver` is the
    person's name, or None when it is not known yet (a request)."""
    waiver = find(task, waiver_id)
    if waiver is None:
        known = ", ".join(str(w.get("id")) for w in listed(task)) or "none"
        return f"no waiver {waiver_id} on this issue (its waivers: {known})"
    if waiver.get("withdrawn_at"):
        return f"{waiver_id} was withdrawn at {waiver['withdrawn_at']}"
    if not text(waiver.get("reason")):
        return f"{waiver_id} has no reason, so it cannot be approved"
    check = text(waiver.get("check"))
    if not check:
        return f"{waiver_id} names no check"
    if check in never_waived():
        return (f"{waiver_id} waives {check}, which no waiver may excuse (the check set's "
                f"never_waived)")
    standing = approval(task, task_dir, waiver)[0]
    if standing is not None:
        return f"{waiver_id} is already approved by {standing['id']}"
    names, owner, fault = approvers(task_dir)
    if fault:
        return fault
    if approver is not None and not approval_records.approver_listed(names, approver, owner):
        return f"{approver} may not approve a waiver; {_who(names, owner)}"
    return None


def _who(names, owner):
    shown = [f"owner ({owner})" if n == approval_records.OWNER else n for n in names]
    return "the approvers are " + ", ".join(shown) if shown else "no approver is named"


def _withdrawn(registry):
    return {e.get("withdraws"): e.get("id") for e in registry
            if isinstance(e, dict) and e.get("type") == approval_records.WITHDRAWAL}


def approval(task, task_dir, waiver):
    """`(record, why)`: the newest record that approves this waiver, or None
    with the reason none does."""
    wid = waiver.get("id")
    registry = [e for e in (task or {}).get("evidence") or [] if isinstance(e, dict)]
    records = [e for e in registry if e.get("type") == "human-approval"
               and e.get(SUBJECT) == wid]
    if not records:
        return None, f"no approval record names {wid}"
    names, owner, fault = approvers(task_dir)
    slug = os.path.basename(os.path.normpath(task_dir))
    withdrawn = _withdrawn(registry)
    why = None
    for record in reversed(records):
        rid = record.get("id")
        missing = [k for k in approval_records.REQUIRED if not record.get(k)]
        if record.get("decision") != approval_records.APPROVED:
            reason = f"{rid} does not hold decision: approved"
        elif missing:
            reason = f"{rid} is missing {', '.join(missing)}"
        elif rid in withdrawn:
            reason = f"{rid} was withdrawn by {withdrawn[rid]}"
        elif record.get("issue") != slug:
            reason = f"{rid} is for issue {record.get('issue')!r}, not {slug}"
        elif record.get("generation") != (task or {}).get("generation"):
            # A reassessment can raise what the issue owes, so an approval holds
            # only at the generation it was given for, as a human check's does.
            reason = (f"{rid} was given at generation {record.get('generation')!r} and the "
                      f"issue is at generation {(task or {}).get('generation')!r}, so the "
                      f"waiver needs a new approval at this generation")
        elif record.get(CHECK) != waiver.get("check") or \
                record.get(REASON) != waiver.get("reason"):
            reason = (f"{rid} approved another check or reason than {wid} now names, so the "
                      f"waiver needs a new approval")
        elif fault:
            reason = fault
        elif not approval_records.approver_listed(names, record["approver"], owner):
            reason = f"{record['approver']} may not approve a waiver; {_who(names, owner)}"
        else:
            return record, None
        why = why or reason
    return None, why


def state(task, task_dir, waiver):
    """`(state, record, why)`: approved with its record, unapproved with the
    reason, or withdrawn. A waiver with no reason, or on a check the set never
    waives, is unapproved whatever a record says."""
    if waiver.get("withdrawn_at"):
        return WITHDRAWN, None, f"withdrawn at {waiver['withdrawn_at']}"
    if not text(waiver.get("reason")):
        return UNAPPROVED, None, "it has no reason"
    if not text(waiver.get("check")):
        return UNAPPROVED, None, "it names no check"
    if waiver.get("check") in never_waived():
        return UNAPPROVED, None, f"{waiver.get('check')} is never waived"
    record, why = approval(task, task_dir, waiver)
    if record is None:
        return UNAPPROVED, None, why
    return APPROVED, record, None


def excused(task, task_dir):
    """`{check id: (waiver, record)}` for each approved waiver of the issue.
    When two approved waivers name one check, the first counts."""
    out = {}
    for waiver in listed(task):
        held, record, _ = state(task, task_dir, waiver)
        if held == APPROVED and waiver["check"] not in out:
            out[waiver["check"]] = (waiver, record)
    return out


def notices(task, task_dir):
    """One line per unapproved, unwithdrawn waiver: the check stays as it was,
    and the line names the request command."""
    lines = []
    slug = os.path.basename(os.path.normpath(task_dir))
    for waiver in listed(task):
        held, _, why = state(task, task_dir, waiver)
        if held != UNAPPROVED:
            continue
        lines.append(f"waiver {waiver.get('id')} of {waiver.get('check')} is not approved "
                     f"({why}), so the check runs as it is; ask with `compass evidence "
                     f"request --waiver {waiver.get('id')} --issue {slug}`")
    return lines


def next_id(task, task_dir):
    """The next free waiver id. An id that a waiver, a record or a request
    holds is not given again, so an approval or a request never meets a
    waiver it was not given for. A removed waiver that nothing named can
    have its id given again."""
    from compass_pkg import approval_requests
    used = [str(w.get("id")) for w in listed(task)]
    used += [str(e.get(SUBJECT)) for e in (task or {}).get("evidence") or []
             if isinstance(e, dict) and isinstance(e.get(SUBJECT), str)]
    used += [str(r.get("value")) for r in approval_requests.pending(task_dir)
             + approval_requests.closed(task_dir) if r.get("form") == SUBJECT]
    numbers = [int(u[2:]) for u in used if ID.fullmatch(u)]
    return f"W-{max(numbers + [0]) + 1}"
