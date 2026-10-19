#!/usr/bin/env python3
# =============================================================================
# compass - does a multiagent run leave a complete subtask record
# =============================================================================
# `compass issue subtask` (subtasks.py) writes a multiagent issue's
# `subtasks:` list: each entry's status and review rounds. Registering a
# distribution map that declares one work unit writes one more kind of entry
# (see below). The check
# exists so that an issue cannot land with a subtask record that shows an
# unfinished run - one never marked done, or one whose last review round did
# not pass. It reads the manifest and fails a multiagent issue whose run left
# no complete record.
#
# An issue that already records a `subtasks:` key is judged on it, whatever
# its date. An issue with no `subtasks:` key is judged only if it was
# created on or after 2026-09-26, the first full day the protocol existed -
# one built before that recorded its run however the process of the day
# required, and a new mechanism must not judge work that predates it
# (ADR-006).
#
# A subtask may instead record a stop reason with an evidence file: the run
# stopped it, and says why. For an issue created on or after 2026-10-03, a
# subtask past its try or review-round ceiling (the `loop_ceilings`
# rules in routing-policy.yml) needs that stop reason to land. An issue
# created earlier is not compared with ceilings that did not exist when it
# ran.
#
# A distribution map that declares one work unit (`units: 1`) needs no split.
# Registering it records one subtask run by the main session, marked
# `orchestration: single-unit` (subtasks.py). Without it, a one-unit change
# on a route whose breakdown is multiagent could land only by a waiver or by
# a hand-made record of a dispatch that never happened. The check accepts a
# single-unit record once every gate has passed, the map still declares one
# unit and the issue's verification report exists: the gates stand in for
# the package review a separate builder gets, because with one unit the
# package is the integrated result the verify stage reviews. Critical risk
# also needs a passing review round, because its review cadence adds a
# second reviewer, and its one-worktree cap (RP-CAP-001) makes one unit the
# usual shape of critical work (ADR-071).
#
# DEPENDENCY: standard library (datetime, os, re), compass_pkg.check_results
# and compass_pkg.loop_ceilings.
# =============================================================================
"""`multiagent-run-recorded`: does a multiagent issue's manifest show its run
completed - every subtask done, with a passing last review round?"""
from __future__ import annotations

import datetime
import os
import re

from compass_pkg import status_words
from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.core import FOUND, find_upwards, resolve_artifact
from compass_pkg.stable_ids import STAGE_BREAKDOWN
from compass_pkg.loop_ceilings import (LOOP_CEILINGS_FROM, loop_ceilings,
                                       on_or_after)

#: An issue with no `subtasks:` key is read by the check only if created on
#: or after this date; an issue that already has the key is read whatever
#: its date (the requirements review's Q2). As `RED_REQUIRED_FROM` does in
#: red_first.py.
RUN_RECORD_REQUIRED_FROM = datetime.date(2026, 9, 26)

#: The `orchestration:` value of a subtask the main session ran itself,
#: because the distribution map declares one work unit.
SINGLE_UNIT = "single-unit"

#: The map's machine-readable line: `units: 1`, or a list such as
#: `units: [U1, U2]`, alone on a line or as a list item, so prose that
#: mentions units does not count.
_UNITS_LINE = re.compile(r"^units:\s*(\S.*?)\s*$")

#: How a message names the line and its two forms.
UNITS_FORMS = "`units: 1` for one unit of work, or a list such as `units: [U1, U2]`"


def _applies_from(created, cutoff=RUN_RECORD_REQUIRED_FROM):
    """Was the issue created on or after the cutoff? See `on_or_after`."""
    return on_or_after(created, cutoff)


def _stop_problem(stop, task_dir):
    """What is wrong with a recorded stop reason, or None when it has a
    reason and an evidence file that exists inside the project."""
    if not isinstance(stop, dict) or not str(stop.get("reason") or "").strip():
        return "a stop with no reason"
    evidence = stop.get("evidence")
    if not isinstance(evidence, str) or not evidence:
        return "a stop with no evidence file"
    root = os.path.realpath(find_upwards(task_dir, ".compass") or task_dir)
    full = os.path.realpath(os.path.join(root, evidence))
    if os.path.commonpath([root, full]) != root or not os.path.isfile(full):
        return "its stop evidence %s does not exist" % evidence
    return None


def _past_ceilings(subtask, ceilings):
    """The ceilings this subtask went past, as phrases for the message."""
    past = []
    attempts = subtask.get("attempts")
    rounds = subtask.get("review_rounds")
    counts = (("builder_attempts", attempts if isinstance(attempts, int) else 0,
               "attempts"),
              ("review_rounds", len(rounds) if isinstance(rounds, list) else 0,
               "review rounds"))
    for name, count, noun in counts:
        if name in ceilings and count > ceilings[name][0]:
            limit, rid = ceilings[name]
            past.append("%d %s, past the ceiling of %d (%s)"
                        % (count, noun, limit, rid))
    return past


def _ready(task):
    """Has every gate passed, or is the issue completed? A run still in flight
    is not judged: a subtask legitimately has no final record yet while the
    work is under way. A completed issue is ready whatever its gates say - it
    is not "still in flight" by definition. An issue closed as not planned is
    not ready: its run never finished, and v5.6.0 did not judge it."""
    if status_words.is_completed(task):
        return True
    gates = [g for g in task.get("gates") or [] if isinstance(g, dict)]
    return bool(gates) and all(g.get("status") == "pass" for g in gates)


def _last_round_passed(subtask):
    """Does the subtask's LAST recorded review round show `verdict: pass`?

    Reads the last entry of the raw list, whatever its type, because the
    last entry is the last word on the subtask (the requirements review's
    Q1): a malformed one, or a `review_rounds:` value that is not a list at
    all, must read as a fail, not raise an error or let an earlier entry
    stand in for it.
    """
    rounds = subtask.get("review_rounds") or []
    if not isinstance(rounds, list) or not rounds:
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


#: A row the scripts do not provision, so it is no subtask to record.
_NOT_A_WORKTREE = ("not a parallel worktree", "not a worktree",
                   "non-provisioning", "integration/verify")


def declared_units(path):
    """How many work units the distribution map at `path` declares on its
    `units:` line, or None when it has none. The first line whose value is
    a whole number or a bracketed list counts; a template placeholder such
    as `{{N}}` is skipped."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    for line in lines:
        found = _UNITS_LINE.match(line.strip().lstrip("-* ").strip("`"))
        if not found:
            continue
        value = found.group(1).strip("`").strip()
        if value.isdecimal():
            return int(value)
        if value.startswith("[") and value.endswith("]"):
            return len([u for u in value[1:-1].split(",") if u.strip()])
    return None


def map_units(task_dir):
    """The units the issue's registered distribution map declares, or None
    when no map is found or it declares none."""
    try:
        state, path, _ = resolve_artifact(str(task_dir), "distribution-map")
    except Exception:
        return None
    if state != FOUND or not path:
        return None
    return declared_units(path)


def _single_unit_problem(entry, task, task_dir):
    """What stops a single-unit record from counting as a complete run, or
    None. See the header: every gate passed, the map still declares one
    unit, a verification report exists, and on critical risk a passing last
    review round."""
    gates = [g for g in task.get("gates") or [] if isinstance(g, dict)]
    unmet = [str(g.get("id", "?")) for g in gates if g.get("status") != "pass"]
    if not gates or unmet:
        return ("gate(s) not passed: %s - the gates stand in for a separate "
                "builder's review" % (", ".join(unmet) or "none recorded"))
    if map_units(task_dir) != 1:
        return ("the distribution map no longer declares `units: 1` - record "
                "each unit with `compass issue subtask add`, or put the line "
                "back")
    assessment = task.get("assessment")
    risk = assessment.get("risk") if isinstance(assessment, dict) else None
    if risk == "critical" and not _last_round_passed(entry):
        return ("critical risk needs a second reviewer, and the record has no "
                "passing last review round - record it with `compass issue "
                "subtask set %s --round pass`" % entry.get("id", "<id>"))
    root = os.path.realpath(find_upwards(task_dir, ".compass") or task_dir)
    report = entry.get("report")
    if isinstance(report, str) and report:
        full = os.path.realpath(os.path.join(root, report))
        if os.path.commonpath([root, full]) == root and os.path.isfile(full):
            return None
    try:
        state, _, _ = resolve_artifact(str(task_dir), "verification-report")
    except Exception:
        state = None
    if state == FOUND:
        return None
    return ("no verification report - register it with `compass issue "
            "artifact set verification-report --status draft --path <path>`")


def mapped_subtask_ids(task_dir):
    """The subtask ids the issue's distribution map names, in its order, or
    None when no map is found.

    The map is found through the artifact registry, as the scripts find it.
    Only the table whose header's first cell is `Subtask` is read, and only
    rows whose first cell is a subtask id, so a note in another table that
    mentions a subtask does not count. A row marked as not a worktree is
    skipped, as `multiagent.sh` skips it.
    """
    try:
        state, path, _ = resolve_artifact(str(task_dir), "distribution-map")
    except Exception:
        return None
    if state != FOUND or not path:
        return None
    return subtask_ids_in(path)


def subtask_ids_in(path):
    """The subtask ids the distribution map at `path` names, read as
    `mapped_subtask_ids` reads them, or None when the file cannot be read."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    ids, in_table = [], False
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            continue
        cells = [c.strip().strip("`*").strip() for c in stripped.strip("|").split("|")]
        first = cells[0] if cells else ""
        if first.lower() == "subtask":
            in_table = True
            continue
        if not in_table or set(first) <= set("-: "):
            continue
        if any(marker in stripped for marker in _NOT_A_WORKTREE):
            continue
        if first.startswith(("subtask-", "stream-")):  # vocabulary-scan: allow - reads the retired spelling for back-compat (ADR-006)
            ids.append(first)
    return ids


def _check_multiagent_run_recorded(task, task_dir):
    """multiagent-run-recorded: `subtasks:` records a complete run.

    Declines to check for an issue whose breakdown stage is not multiagent,
    or one still in flight - not every gate has passed and the issue has
    not landed. An issue that already records a `subtasks:` key is judged
    on it whatever its date; one with no `subtasks:` key is declined too,
    unless it was created on or after the protocol's start date (the
    requirements review's Q2 - a new mechanism must not judge work that
    predates it, ADR-006). Once the issue is ready it fails on a manifest
    with no `subtasks:`, a subtask that is not `done`, or a subtask whose
    last review round is missing or `fail` (a later verdict is the last
    word on it, so a fail after an earlier pass still fails - the
    requirements review's Q1). A single-unit record is judged by
    `_single_unit_problem` instead of on its status.
    """
    stages = task.get("stages")
    breakdown = stages.get(STAGE_BREAKDOWN) if isinstance(stages, dict) else None
    if breakdown != "multiagent":
        return NOTHING_TO_CHECK, (
            "breakdown stage is %r, not multiagent - this check only reads a "
            "multiagent run" % (breakdown,))

    if "subtasks" not in task and not _applies_from(task.get("created")):
        return NOTHING_TO_CHECK, (
            "no `subtasks:` key, and created %r is before %s, or missing - "
            "this issue predates the protocol the check reads"
            % (task.get("created"), RUN_RECORD_REQUIRED_FROM.isoformat()))

    if not _ready(task):
        return NOTHING_TO_CHECK, (
            "not every gate has passed and the issue has not landed - the "
            "run is still in flight, so a subtask legitimately has no final "
            "record yet")

    subtasks = task.get("subtasks")
    if subtasks is None or (isinstance(subtasks, list) and not subtasks):
        return False, (
            "the manifest has no `subtasks:` recorded for a multiagent run - "
            "record each one with `compass issue subtask add` and `update` "
            "as it completes")
    if not isinstance(subtasks, list):
        return False, (
            "`subtasks:` is not a list (it is %s) - record each subtask "
            "with `compass issue subtask add` and `update` as it completes"
            % type(subtasks).__name__)

    # Every entry is judged, in the order the manifest holds it. A subtask
    # entry that is not a mapping cannot be a passing one, so it is named by
    # its position and counted as not done.
    # A subtask with a stop reason is judged on the stop alone.
    ceilings = {}
    if _applies_from(task.get("created"), LOOP_CEILINGS_FROM):
        ceilings = loop_ceilings(task, task_dir)
    not_done = []
    no_pass = []
    bad_stop = []
    bad_single = []
    past = []
    for index, entry in enumerate(subtasks):
        label = _subtask_label(entry, index)
        if isinstance(entry, dict) and entry.get("orchestration") == SINGLE_UNIT:
            problem = _single_unit_problem(entry, task, task_dir)
            if problem:
                bad_single.append("%s (%s)" % (label, problem))
            if _past_ceilings(entry, ceilings):
                past.append("%s: %s" % (label,
                                        "; ".join(_past_ceilings(entry, ceilings))))
            continue
        if isinstance(entry, dict) and "stopped_reason" in entry:
            problem = _stop_problem(entry["stopped_reason"], task_dir)
            if problem:
                bad_stop.append("%s (%s)" % (label, problem))
            continue
        if not isinstance(entry, dict) or entry.get("status") != "done":
            not_done.append(label)
        if not isinstance(entry, dict) or not _last_round_passed(entry):
            no_pass.append(label)
        if isinstance(entry, dict) and _past_ceilings(entry, ceilings):
            past.append("%s: %s" % (label,
                                    "; ".join(_past_ceilings(entry, ceilings))))

    singles = [e for e in subtasks
               if isinstance(e, dict) and e.get("orchestration") == SINGLE_UNIT]
    if singles and len(subtasks) > len(singles):
        # A record that says this session ran the one unit cannot sit beside a
        # dispatched subtask: one of the two is untrue.
        others = [_subtask_label(e, i) for i, e in enumerate(subtasks) if e not in singles]
        return False, (
            "the record says the map's one unit was run by this session, but it "
            "also records %s. Record two or more units in the map's `units:` "
            "line and register it again, or take the other subtask out."
            % ", ".join(others))
    if bad_single:
        return False, ("one-unit run not complete: %s." % "; ".join(bad_single))

    if not_done or no_pass or bad_stop:
        problems = []
        if not_done:
            problems.append("not done: %s" % ", ".join(not_done))
        if no_pass:
            problems.append("no passing last review round: %s" % ", ".join(no_pass))
        if bad_stop:
            problems.append("stopped without a usable record: %s"
                            % ", ".join(bad_stop))
        return False, (
            "subtask(s) with an incomplete run record - %s. Record status "
            "with `compass issue subtask set --status done`, a passing "
            "round with `--round pass`, or why it stopped with "
            "`--stop-reason` and `--stop-evidence`." % "; ".join(problems))

    if past:
        return False, (
            "subtask(s) past a loop ceiling with no stop reason - %s. Record "
            "why with `compass issue subtask set <id> --stop-reason TEXT "
            "--stop-evidence FILE`." % "; ".join(past))

    mapped = mapped_subtask_ids(task_dir)
    if mapped:
        recorded = {str(e.get("id")) for e in subtasks if isinstance(e, dict)}
        unrecorded = [sid for sid in mapped if sid not in recorded]
        if unrecorded:
            return False, (
                "the distribution map names subtask(s) the manifest does not "
                "record: %s. Dispatch and record each with `compass issue "
                "subtask add`, or take it out of the map." % ", ".join(unrecorded))

    stopped = sum(1 for e in subtasks
                  if isinstance(e, dict) and "stopped_reason" in e)
    if any(isinstance(e, dict) and e.get("orchestration") == SINGLE_UNIT
           for e in subtasks):
        return True, ("the distribution map declares one unit, which this "
                      "session ran itself; every gate has passed and the "
                      "verification report exists (%d subtask(s))" % len(subtasks))
    return True, ("every subtask is done with a passing review round, or "
                  "stopped with a recorded reason (%d subtask(s), %d stopped)"
                  % (len(subtasks), stopped))
