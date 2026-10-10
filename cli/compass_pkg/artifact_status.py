# compass_pkg.artifact_status - the status of each registered document
"""Who moves an artifact's status, and the check that stops an unapproved
document from shipping (ADR-050).

The artifact registry in `manifest.yml` gives each document a status: `draft`,
`awaiting-approval`, `approved`, `superseded` or `omitted`. Every command that
writes the record of a stage calls `stage_exit`, which moves the documents of
earlier stages on:

- a `draft` entry that has a `path` and an owning stage earlier than the stage
  being written moves;
- with no human check on the artifact it becomes `approved`, and `approved_by`
  names the command that wrote the record;
- with a human check it becomes `awaiting-approval`, and a person approves it
  with `compass evidence approve --artifact <kind>`;
- an entry with no `path` never moves, because no document has been written.

The owning stage is the `stage` key of the artifact's catalogue entry. A kind
with no `stage` is owned by ship. An issue stored before the key existed reads
the shipped default preset's value for a shipped kind.

A quick fix has one document and no stage hand-offs, so a stage command leaves
it alone and `compass quick-fix finish` approves it.

`artifacts-approved` is the blocking check that `compass ship-commit` and
`compass check` run: it judges a copy of the issue with the ship exit applied,
which is the state `ship-commit` would leave.
"""
# DEPENDENCY: standard library (copy, os); compass_pkg.core, compass_pkg.stable_ids,
# compass_pkg.status_words, compass_pkg.check_results. It imports no command
# module at load time, so every writer can import it.
from __future__ import annotations

import copy
import os

from compass_pkg import status_words
from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.core import FRAMEWORK_ROOT, CompassError, load_yaml, reading_matches
from compass_pkg.stable_ids import APPROACH_QUICK_FIX, APPROACH_SPIKE, STAGE_SHIP

DRAFT, AWAITING, APPROVED = "draft", "awaiting-approval", "approved"
SUPERSEDED, OMITTED = "superseded", "omitted"

#: The `approved_by` value of each command that moves a status.
BY_ARTIFACT_SET = "compass issue artifact set"
BY_SUBTASK_ADD = "compass issue subtask add"
BY_TDD_RED = "compass tdd-red"
BY_ACCEPTANCE = "compass acceptance record"
BY_GATE_PASS = "compass gate pass"
BY_SHIP_COMMIT = "compass ship-commit"
BY_QUICK_FIX = "compass quick-fix finish"
BY_MIGRATE = "compass issue migrate"

#: The stages that write a record, by the command that writes it.
STAGE_BREAKDOWN, STAGE_IMPLEMENT, STAGE_VERIFY = "breakdown", "implement", "verify"

CHECK_ID = "artifacts-approved"


def now():
    from compass_pkg.core import now_iso
    return now_iso().replace("+00:00", "Z")


def _shipped(name):
    """A catalogue of the shipped default preset, or {} when it cannot be read."""
    try:
        doc = load_yaml(os.path.join(FRAMEWORK_ROOT, "governance", "presets", "default",
                                     name + ".yml"))
    except (CompassError, OSError):
        return {}
    body = doc.get(name) if isinstance(doc, dict) else None
    return body if isinstance(body, dict) else {}


def _catalogue(view, name):
    body = (view.config.get(name) if view is not None else None)
    return body if isinstance(body, dict) else {}


def owning_stage(view, kind):
    """The stage that owns `kind`: the catalogue's `stage`, else the shipped
    preset's for a shipped kind, else ship."""
    entry = _catalogue(view, "artifacts").get(kind)
    if isinstance(entry, dict) and entry.get("stage"):
        return str(entry["stage"])
    shipped = _shipped("artifacts").get(kind)
    if isinstance(shipped, dict) and shipped.get("stage"):
        return str(shipped["stage"])
    return STAGE_SHIP


def _order(view):
    stages = _catalogue(view, "stages") or _shipped("stages")
    found = {name: body["order"] for name, body in stages.items()
             if isinstance(body, dict) and isinstance(body.get("order"), int)}
    return found


def _rank(order, stage):
    # A stage the catalogue does not define sorts with ship, the last one.
    return order.get(stage, order.get(STAGE_SHIP, max(order.values(), default=0)))


def human_checks(view, kind):
    """The ids of the human checks on `kind`, in the catalogue's order."""
    entry = _catalogue(view, "artifacts").get(kind)
    checks = _catalogue(view, "checks")
    if not isinstance(entry, dict):
        return []
    return [str(one) for one in (entry.get("checks") or [])
            if isinstance(checks.get(one), dict) and checks[one].get("kind") == "human"]


def _set_awaiting(entry):
    entry["status"] = AWAITING
    entry.pop("approved_by", None)
    entry.pop("approved_at", None)


def _set_approved(entry, by, when):
    entry["status"] = APPROVED
    entry["approved_by"] = by
    entry["approved_at"] = when


def clear_approver(entry):
    entry.pop("approved_by", None)
    entry.pop("approved_at", None)


def stage_exit(task, view, stage, by, when=None, include_own=False, earlier=True):
    """Move the documents the record of `stage` leaves behind. Mutates `task`
    and returns `[{kind, from, to}]` for each entry moved.

    `earlier` moves the `draft` entries with a path that stages before `stage`
    own; `include_own` also moves those `stage` owns (a verify gate pass and the
    ship exit do). A quick fix is left to `compass quick-fix finish`."""
    if task.get("delivery_approach") == APPROACH_QUICK_FIX:
        return []
    when = when or now()
    order = _order(view)
    here = _rank(order, stage)
    moved = []
    for entry in task.get("artifacts") or []:
        if not isinstance(entry, dict) or entry.get("status") != DRAFT or not entry.get("path"):
            continue
        kind = entry.get("kind")
        owner = _rank(order, owning_stage(view, kind))
        if not ((earlier and owner < here) or (include_own and owner == here)):
            continue
        if human_checks(view, kind):
            _set_awaiting(entry)
        else:
            _set_approved(entry, by, when)
        moved.append({"kind": kind, "from": DRAFT, "to": entry["status"]})
    return moved


def approve_documents(task, by, when=None):
    """Approve every entry that has a path and reads `draft`, for the command
    `by`. `compass quick-fix finish` calls it once `compass check` has passed,
    so a quick fix gains no stop. Returns the moves."""
    when = when or now()
    moved = []
    for entry in task.get("artifacts") or []:
        if (isinstance(entry, dict) and entry.get("path")
                and entry.get("status") in (DRAFT, AWAITING)):
            moved.append({"kind": entry.get("kind"), "from": entry["status"], "to": APPROVED})
            _set_approved(entry, by, when)
    return moved


def record_stage(task_dir, stage, by, include_own=False, earlier=True):
    """Load the issue's manifest, apply `stage_exit` and save it when an entry
    moved. Returns the moves. Called by a command that has written the record
    of `stage`, after its own save."""
    from compass_pkg import effective
    from compass_pkg.core import load_manifest, save_manifest

    task, path = load_manifest(task_dir)
    if not task.get("artifacts"):
        return []
    try:
        view = effective.view_or_legacy(task_dir)
    except Exception:                                   # noqa: BLE001 - no configuration, no human checks
        view = None
    moved = stage_exit(task, view, stage, by, include_own=include_own, earlier=earlier)
    if moved:
        save_manifest(task, path)
    return moved


def moved_line(moved):
    """One line for a command to print, or none."""
    if not moved:
        return []
    return ["documents : " + ", ".join(f"{m['kind']} -> {m['to']}" for m in moved)]


def register(task, view, entry, requested, digest_now, by=BY_ARTIFACT_SET, when=None):
    """Set `requested` on a registry entry that `compass issue artifact set` has
    just given its path. Raises `CompassError` for a refusal, before any change.
    Returns True when an approved entry was moved back to `draft` because its
    file changed, so the caller keeps the reason this sets.

    - An `approved` entry whose recorded digest differs from the file's goes
      back to `draft` whatever was asked, with its approver removed and a
      reason; an unchanged one keeps `approved` for `draft` and
      `awaiting-approval`.
    - `approved` is refused for an artifact with a human check: a person
      approves it with `compass evidence approve --artifact`."""
    when = when or now()
    kind = entry.get("kind")
    recorded = entry.get("digest")
    unchanged = (entry.get("status") == APPROVED
                 and not (recorded and digest_now and recorded != digest_now))
    if entry.get("status") == APPROVED and not unchanged:
        approver = entry.get("approved_by") or "an approver"
        clear_approver(entry)
        entry["status"] = DRAFT
        entry["reason"] = ("changed after it was approved by %s (digest %s then %s)"
                           % (approver, _short(recorded), _short(digest_now)))
        return True
    if unchanged and requested in (DRAFT, AWAITING, APPROVED):
        return False
    if requested == APPROVED:
        if human_checks(view, kind):
            raise CompassError(
                "compass issue artifact set: %s has a human check, so a person approves it. "
                "Set it to awaiting-approval with `compass issue artifact set %s --status "
                "awaiting-approval`, then run `compass evidence approve --artifact %s "
                "--approver <name> --role <role> --scope <text>` at a terminal."
                % (kind, kind, kind))
        _set_approved(entry, by, when)
        return False
    entry["status"] = requested
    clear_approver(entry)
    return False


def _short(digest):
    text = str(digest or "")
    return text[7:19] if text.startswith("sha256:") else text[:12]


def ship_projection(task, view):
    """A copy of the task with the ship exit applied: the state `compass
    ship-commit` leaves. It approves only the documents ship owns."""
    projected = copy.deepcopy(task)
    stage_exit(projected, view, STAGE_SHIP, BY_SHIP_COMMIT, include_own=True, earlier=False)
    return projected


def _ships(view, task):
    approach = task.get("delivery_approach")
    body = _catalogue(view, "approaches").get(approach)
    if isinstance(body, dict) and "ships" in body:
        return bool(body["ships"])
    return approach != APPROACH_SPIKE


def _command_for(entry, view):
    kind = entry.get("kind")
    status = entry.get("status")
    if status == AWAITING:
        return f"`compass evidence approve --artifact {kind} --approver <name> --role <role> --scope <text>`"
    if status == OMITTED:
        return f'`compass issue artifact set {kind} --status omitted --reason "<why>"`'
    if human_checks(view, kind):
        return (f"`compass issue artifact set {kind} --status awaiting-approval`, then "
                f"`compass evidence approve --artifact {kind} --approver <name> --role <role> "
                f"--scope <text>`")
    return f"`compass issue artifact set {kind} --status approved`"


def _check_artifacts_approved(task, task_dir):
    """`(passed, detail)`: every registered document is accepted once `ship-commit`
    has applied the ship exit. Declines until every gate has passed."""
    from compass_pkg import effective

    if status_words.is_closed(task):
        return NOTHING_TO_CHECK, "the issue is closed, so there is no land to stop"
    try:
        view = effective.view_or_legacy(task_dir)
    except Exception:                                   # noqa: BLE001 - judged without human checks
        view = None
    if not _ships(view, task):
        return NOTHING_TO_CHECK, "this approach ships nothing, so no document is owed"
    gates = [g for g in (task.get("gates") or []) if isinstance(g, dict)]
    unmet = [g.get("id", "?") for g in gates if g.get("status") != "pass"]
    if unmet:
        return NOTHING_TO_CHECK, (f"{len(unmet)} gate(s) have not passed, so the documents are "
                                  f"judged when the last one does")
    entries = [e for e in ship_projection(task, view).get("artifacts") or []
               if isinstance(e, dict)]
    problems = []
    for entry in entries:
        status = entry.get("status")
        if status == OMITTED and str(entry.get("reason") or "").strip():
            continue
        if status in (DRAFT, AWAITING, OMITTED):
            what = ("omitted with no reason" if status == OMITTED else
                    "reads draft" if status == DRAFT and entry.get("path") else
                    "reads draft and has no path" if status == DRAFT else
                    "is awaiting approval")
            problems.append(f"{entry.get('kind')} {what} - run {_command_for(entry, view)}")
    if problems:
        return False, (f"{len(problems)} document(s) are not approved: " + "; ".join(problems))
    return True, f"{len(entries)} registered document(s) are approved, superseded or omitted with a reason"


def judged(task, task_dir):
    """The verdict of `artifacts-approved` after what the issue's configuration
    declares for it, or None when the configuration does not declare the check.
    Returns `(passed, detail)` as `check_cmd._judge` does: `passed` can be
    `ADVISORY_FAILURE` after a waiver."""
    from compass_pkg import effective
    from compass_pkg.check_cmd import _judge
    from compass_pkg.core import find_governance

    try:
        view = effective.view_or_legacy(task_dir)
        if view is None:
            guardrails = load_yaml(os.path.join(find_governance(), "guardrails.yml"))
            matches = reading_matches
            readings = task.get("assessment") or {}
        else:
            guardrails = view.guardrail_gates()
            matches = view.matches
            readings = view.listing_assessment(task.get("assessment") or {},
                                               task.get("delivery_approach"))
    except Exception:                                   # noqa: BLE001 - no configuration, nothing declared
        return None
    if CHECK_ID not in (guardrails.get("impl") or {}) and CHECK_ID not in (
            guardrails.get("checks") or {}):
        return None
    try:
        passed, detail = _check_artifacts_approved(task, task_dir)
    except Exception as exc:                            # noqa: BLE001 - a check must not crash the run
        passed, detail = False, f"check errored: {exc}"
    return _judge(passed, detail, (guardrails.get("checks") or {}).get(CHECK_ID) or {},
                  matches, readings)

