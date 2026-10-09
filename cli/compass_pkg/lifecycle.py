# compass_pkg.lifecycle - the state of an issue, read from its records
"""`state_of(manifest, task_dir)` names the state of one issue.

Only two states are stored (`backlog`, a hold a person set, and `done`). The
others are read from the records, because no command marks the start of plan
or of review, and a stored state would need a writer at every place a record is
written.
"""
# DEPENDENCY: compass_pkg.next_cmd (the record readers it already has) and
# compass_pkg.status_words. `core` never imports this module.
from __future__ import annotations

from compass_pkg import next_cmd, status_words
from compass_pkg.stable_ids import (
    STAGE_ASSESS, STAGE_BREAKDOWN, STAGE_DEFINE, STAGE_IMPLEMENT, STAGE_PLAN,
    STAGE_REFINE, STAGE_SHIP, STAGE_VERIFY)


def _define_finished(manifest):
    return (next_cmd._registered(manifest, "acceptance-criteria")
            or bool(next_cmd._entries(manifest, "scenarios")))


def _refine_finished(manifest, task_dir):
    stages = manifest.get("stages")
    weight = stages.get(STAGE_REFINE) if isinstance(stages, dict) else None
    if isinstance(weight, str) and weight.strip().lower() in next_cmd._SKIPPED_WEIGHTS:
        return True
    return (next_cmd._registered(manifest, "requirements-review")
            or (not next_cmd._earned(manifest, "requirements-review")
                and next_cmd._review_written(task_dir)))


def _work_started(manifest, task_dir):
    return (next_cmd._registered(manifest, "technical-design")
            or next_cmd._registered(manifest, "distribution-map")
            or bool(next_cmd._entries(manifest, "subtasks"))
            or next_cmd._testing_started(manifest, task_dir))


def _review_started(manifest):
    """Verify has started when a gate left `pending` or a verification report
    is registered with a path (the architect's ruling, recorded in ADR-045).
    Manifest only, no disk read."""
    gates = next_cmd._entries(manifest, "gates")
    if any((g.get("status") or "pending") != "pending" for g in gates):
        return True
    return any(a.get("kind") == "verification-report" and a.get("path")
               for a in next_cmd._entries(manifest, "artifacts"))


_STATE_OF_STAGE = {STAGE_ASSESS: "backlog", STAGE_DEFINE: "backlog",
                   STAGE_REFINE: "backlog", STAGE_PLAN: "in-progress",
                   STAGE_BREAKDOWN: "in-progress", STAGE_IMPLEMENT: "in-progress",
                   STAGE_VERIFY: "in-review", STAGE_SHIP: "in-review"}


def _state_of_named_stage(manifest):
    """A top-level `current_phase` key wins over the records, as in
    `compass next`. A name no stage has says nothing."""
    named = manifest.get("current_phase")
    if isinstance(named, str):
        return _STATE_OF_STAGE.get(named.strip().lower())
    return None


#: The states in which the blocked flag counts: work is under way or in review.
BLOCKABLE_STATES = ("in-progress", "in-review")


def blocked_flag(manifest, task_dir):
    """The `blocked` mapping (`reason` and `at`) while the state allows it,
    else None. A flag left on a held, ready or closed issue is ignored."""
    flag = manifest.get("blocked") if isinstance(manifest, dict) else None
    if not isinstance(flag, dict):
        return None
    return flag if state_of(manifest, task_dir) in BLOCKABLE_STATES else None


def status_errors(manifest, raw, task_dir):
    """What `issue lint` reports about the status keys. `manifest` is the
    loaded issue, `raw` the parsed file as it is on disk (a status word that
    was mapped on load shows only there)."""
    errors = []
    reason = status_words.close_reason(manifest)
    if status_words.is_closed(manifest) and reason is None:
        errors.append(
            "`status: done` has no `close_reason`; give one of "
            + ", ".join(status_words.CLOSE_REASONS))
    words = status_words._RETIRED_CLOSE_REASON
    if isinstance(raw, dict) and raw.get("status") in words:
        old, given = raw["status"], raw.get("close_reason")
        stood_for = words[old]
        fits = given in (None, stood_for) or (
            stood_for == status_words.NOT_PLANNED and given == status_words.DUPLICATE)
        if not fits:
            errors.append(
                f"`status: {old}` contradicts `close_reason: {given}`; the "
                f"close reason is used, so change or remove one of them")
    if manifest.get("duplicate_of") and reason != status_words.DUPLICATE:
        errors.append("`duplicate_of` is set but the close reason is not duplicate")
    if status_words.has_blocked_key(manifest) and blocked_flag(manifest, task_dir) is None:
        errors.append(
            f"`blocked` is set on an issue that is {state_of(manifest, task_dir)}; "
            "only an in-progress or in-review issue can be blocked, and readers "
            "ignore the flag")
    return errors


def state_of(manifest, task_dir):
    if status_words.is_closed(manifest):
        return "done"
    if status_words.is_held(manifest):
        return "backlog"
    if _review_started(manifest):
        return "in-review"
    named = _state_of_named_stage(manifest)
    if named:
        return named
    if _work_started(manifest, task_dir):
        return "in-progress"
    if _define_finished(manifest) and _refine_finished(manifest, task_dir):
        return "ready"
    return "backlog"
