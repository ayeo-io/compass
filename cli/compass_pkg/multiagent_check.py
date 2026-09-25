#!/usr/bin/env python3
# =============================================================================
# compass - does a multiagent run leave a complete subtask record
# =============================================================================
# `compass issue subtask` (subtasks.py) is the only writer of a multiagent
# issue's `subtasks:` list: each entry's status and review rounds. The check
# exists so that an issue cannot land with a subtask record that shows an
# unfinished run - one never marked done, or one whose last review round did
# not pass. It reads the manifest and fails a multiagent issue whose run left
# no complete record.
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
    """Does the subtask's LAST recorded review round show `verdict: pass`?

    Takes the last entry of the raw list, before dropping anything that is
    not a mapping - filtering first let a malformed trailing entry fall
    away and an earlier pass stand in as "last" for it. The last entry is
    the last word on the subtask (the requirements review's Q1), so a
    malformed one must read as a fail, not be skipped.
    """
    rounds = subtask.get("review_rounds") or []
    if not rounds:
        return False
    last = rounds[-1]
    return isinstance(last, dict) and last.get("verdict") == "pass"


def _subtask_label(entry, index):
    """A name for a `subtasks:` list entry to use in a check message: its
    recorded id when the entry is a mapping, its position when it is not.
    A malformed entry must still be named and judged, not dropped from the
    list before the check reaches it."""
    if isinstance(entry, dict):
        return str(entry.get("id", "?"))
    return "subtasks[%d]" % index


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

    subtasks = task.get("subtasks")
    if not isinstance(subtasks, list) or not subtasks:
        return False, (
            "the manifest has no `subtasks:` recorded for a multiagent run - "
            "record each one with `compass issue subtask add` and `update` "
            "as it completes")

    # Every entry is judged, in the order the manifest holds it. A subtask
    # entry that is not a mapping cannot be a passing one, so it is named by
    # its position and counted as not done; it is not dropped from the list
    # before judgement, the way a filter-first read would drop it.
    not_done = []
    no_pass = []
    for index, entry in enumerate(subtasks):
        label = _subtask_label(entry, index)
        if not isinstance(entry, dict) or entry.get("status") != "done":
            not_done.append(label)
        if not isinstance(entry, dict) or not _last_round_passed(entry):
            no_pass.append(label)

    if not_done or no_pass:
        problems = []
        if not_done:
            problems.append("not done: %s" % ", ".join(not_done))
        if no_pass:
            problems.append("no passing last review round: %s" % ", ".join(no_pass))
        return False, (
            "subtask(s) with an incomplete run record - %s. Record status "
            "with `compass issue subtask update --status done`, and a "
            "passing round with `--round pass`." % "; ".join(problems))

    return True, ("every subtask is done with a passing review round (%d "
                  "subtask(s))" % len(subtasks))
