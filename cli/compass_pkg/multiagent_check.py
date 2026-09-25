#!/usr/bin/env python3
# =============================================================================
# compass - did a multiagent run leave a complete subtask record
# =============================================================================
# `compass issue subtask` (subtasks.py) is the only writer of a multiagent
# issue's `subtasks:` list: each entry's status and review rounds. Nothing
# read that record back - an issue could clear every gate and land with a
# subtask never marked done, or one still failing its last review round, and
# `compass check` said nothing. `multiagent-run-recorded` reads the manifest
# and fails a multiagent issue whose run left no complete record.
#
# It reads only an issue created on or after the date the protocol landed:
# an issue built before that recorded its run however the process of the day
# required, and this check must not start failing it retroactively
# (ADR-006: a new mechanism no-ops for issues that predate it).
#
# DEPENDENCY: standard library (datetime) and compass_pkg.check_results.
# =============================================================================
"""`multiagent-run-recorded`: does a multiagent issue's manifest show its run
completed - every subtask done, with a passing last review round?"""
from __future__ import annotations

import datetime

from compass_pkg.check_results import NOTHING_TO_CHECK

#: Issues created on or after this date are read by the check. An earlier
#: issue is left alone, as `RED_REQUIRED_FROM` leaves earlier issues alone in
#: red_first.py.
RUN_RECORD_REQUIRED_FROM = datetime.date(2026, 9, 25)


def _applies_from(created):
    """Was the issue created on or after the cutoff? A missing or blank
    `created:` does not apply - an issue with no date at all predates the
    field. A value present but not an ISO date is not trusted to mean "old",
    so the check still applies to it."""
    if isinstance(created, datetime.datetime):
        created = created.date()
    if isinstance(created, datetime.date):
        return created >= RUN_RECORD_REQUIRED_FROM
    text = "" if created is None else str(created).strip()
    if not text:
        return False
    try:
        return datetime.date.fromisoformat(text[:10]) >= RUN_RECORD_REQUIRED_FROM
    except ValueError:
        return True


def _ready(task):
    """Has every gate passed, or has the issue landed? A run still in flight
    is not judged: a subtask legitimately has no final record yet while the
    work is under way. A landed issue is ready whatever its gates say - it is
    not "still in flight" by definition."""
    if task.get("status") == "landed":
        return True
    gates = [g for g in task.get("gates") or [] if isinstance(g, dict)]
    return bool(gates) and all(g.get("status") == "pass" for g in gates)


def _last_round_passed(subtask):
    rounds = [r for r in subtask.get("review_rounds") or [] if isinstance(r, dict)]
    last = rounds[-1] if rounds else None
    return last is not None and last.get("verdict") == "pass"


def _check_multiagent_run_recorded(task, task_dir):
    """multiagent-run-recorded: `subtasks:` records a complete run.

    Declines to check for an issue whose breakdown stage is not multiagent,
    one created before the protocol's start date (or with no `created:` at
    all), or one still in flight - not every gate has passed and the issue
    has not landed. Once the issue is ready it fails on a manifest with no
    `subtasks:`, a subtask that is not `done`, or a subtask whose last review
    round is missing or `fail` (a later verdict is the last word on it, so a
    fail after an earlier pass still fails - the requirements review's Q1).
    """
    stages = task.get("stages")
    breakdown = stages.get("breakdown") if isinstance(stages, dict) else None
    if breakdown != "multiagent":
        return NOTHING_TO_CHECK, (
            "breakdown stage is %r, not multiagent - this check only reads a "
            "multiagent run" % (breakdown,))

    if not _applies_from(task.get("created")):
        return NOTHING_TO_CHECK, (
            "created %r is before %s, or missing - this issue predates the "
            "protocol the check reads"
            % (task.get("created"), RUN_RECORD_REQUIRED_FROM.isoformat()))

    if not _ready(task):
        return NOTHING_TO_CHECK, (
            "not every gate has passed and the issue has not landed - the "
            "run is still in flight, so a subtask legitimately has no final "
            "record yet")

    subtasks = [s for s in task.get("subtasks") or [] if isinstance(s, dict)]
    if not subtasks:
        return False, (
            "the manifest has no `subtasks:` recorded for a multiagent run - "
            "record each one with `compass issue subtask add` and `update` "
            "as it completes")

    not_done = [s.get("id", "?") for s in subtasks if s.get("status") != "done"]
    if not_done:
        return False, (
            "subtask(s) not done: %s - record their status with `compass "
            "issue subtask update --status done`" % ", ".join(not_done))

    no_pass = [s.get("id", "?") for s in subtasks if not _last_round_passed(s)]
    if no_pass:
        return False, (
            "subtask(s) with no passing review round: %s - record one with "
            "`compass issue subtask update --round pass`" % ", ".join(no_pass))

    return True, ("every subtask is done with a passing review round (%d "
                  "subtask(s))" % len(subtasks))
