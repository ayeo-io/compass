#!/usr/bin/env python3
# =============================================================================
# compass - evidence identity
# =============================================================================
# Does a registry entry still name the record it was created from?
#
# Kept apart from checks.py because it is about the link between a citation
# and the file it cites, not a guardrail check.
#
# The write side lives in compass_pkg.tdd (`_stamp_identity`). The two halves
# have to agree on the field names and nothing else, which is why they can sit
# in different modules.
#
# DEPENDENCY: standard library only (json, os).
# =============================================================================
"""Checking that a cited evidence record is the one that was recorded."""
from __future__ import annotations

import json
import os

from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.red_first import content_digest


def _check_evidence_identity_matches(task, task_dir):
    """Is each registry entry still naming the record it was created from?

    `gate-evidence-present` checks that the path resolves, not that the file
    is the run the entry was made for. Without this check, a record replaced
    after it was cited leaves every check green.

    Two stamps, two different failures:
      record_id      - unique per write. A different one means the file is a
                       different record under the same name.
      content_digest - over the payload. A matching record_id with a different
                       digest means this record was edited in place.

    A record written before stamping existed carries neither. That is
    UNVERIFIABLE, not a pass and not a failure: an unstamped record cannot be
    checked against its citation, and calling it checked would be a check that
    cannot fail. Where nothing in the issue is stamped, the whole check returns
    NOTHING_TO_CHECK so it is counted apart from the passes rather than
    inflating them.
    """
    registry = [e for e in (task.get("evidence") or []) if isinstance(e, dict)]
    if not registry:
        return NOTHING_TO_CHECK, "no evidence recorded yet - nothing to verify"

    problems, verified, unverifiable = [], 0, 0
    for entry in registry:
        ev_id = entry.get("id", "?")
        claimed = entry.get("record_id")
        if not claimed:
            unverifiable += 1
            continue
        path = entry.get("path")
        if not path:
            problems.append(f"{ev_id}: carries a record_id but no path")
            continue
        full = path if os.path.isabs(path) else os.path.join(task_dir, path)
        if not os.path.isfile(full):
            # gate-evidence-present reports a missing file. Count it here as
            # unverifiable, so this check does not report a pass for it.
            unverifiable += 1
            continue
        try:
            record = json.load(open(full, encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{ev_id}: {path} could not be read ({exc})")
            continue
        actual = record.get("record_id")
        if actual != claimed:
            problems.append(
                f"{ev_id} was created from record {claimed} but {path} now "
                f"holds record {actual or '(unstamped)'} - the file was "
                f"replaced after it was cited"
            )
            continue
        claimed_digest = entry.get("content_digest")
        actual_digest = record.get("content_digest")
        # The stored digest only says what the record claimed when it was
        # written. Recompute it from the content, so an edit that leaves
        # the digest field alone is caught too.
        if actual_digest and content_digest(record) != actual_digest:
            problems.append(
                f"{ev_id}: {path} was edited after it was written - its "
                f"contents no longer match its own digest"
            )
            continue
        if claimed_digest and actual_digest != claimed_digest:
            problems.append(
                f"{ev_id}: {path} is the right record but its contents changed "
                f"after it was cited - it was edited in place"
            )
            continue
        verified += 1

    if problems:
        return False, "; ".join(problems)
    if not verified:
        return NOTHING_TO_CHECK, (
            f"{unverifiable} evidence record(s) carry no identity - they were "
            f"written before records were stamped, so their citations cannot "
            f"be verified. This checked nothing"
        )
    note = (f", {unverifiable} unverifiable (written before records were "
            f"stamped)") if unverifiable else ""
    return True, f"{verified} citation(s) match the record they name{note}"
