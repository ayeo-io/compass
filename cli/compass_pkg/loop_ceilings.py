#!/usr/bin/env python3
# =============================================================================
# compass - the loop ceilings of a multiagent run
# =============================================================================
# The `loop_ceilings` rules in governance/routing-policy.yml bound a
# multiagent run: tries per subtask, review rounds, replans, and the same
# error reported in a row. `compass issue subtask` (subtasks.py) refuses
# work past them, and `multiagent-run-recorded` (multiagent_check.py) refuses
# to land a subtask past them without a stop reason. Both read the limits
# and the cutoff date here, so neither module imports the other. Two more
# bound an unattended `compass run` (run_cmd.py): the sessions it may start
# and the minutes it may take.
#
# DEPENDENCY: standard library (datetime, os) and compass_pkg.core.
# =============================================================================
"""The loop ceilings an issue's assessment earns, and the date they apply from."""
from __future__ import annotations

import datetime
import os

from compass_pkg.core import find_governance, load_yaml, reading_matches

#: An issue is compared with its loop ceilings by the check only if created
#: on or after the day the ceilings landed (ADR-006).
LOOP_CEILINGS_FROM = datetime.date(2026, 10, 3)

#: The ceilings a `loop_ceilings` rule in routing-policy.yml can set.
CEILINGS = ("builder_attempts", "review_rounds", "replans", "repeated_error",
            "run_cycles", "run_minutes")


def on_or_after(created, cutoff):
    """Was the issue created on or after the cutoff? A missing or blank
    `created:` does not apply - an issue with no date at all predates the
    field. A value present but not an ISO date is not trusted to mean
    "old", so the cutoff still applies to it."""
    if isinstance(created, datetime.datetime):
        created = created.date()
    if isinstance(created, datetime.date):
        return created >= cutoff
    text = "" if created is None else str(created).strip()
    if not text:
        return False
    try:
        return datetime.date.fromisoformat(text[:10]) >= cutoff
    except ValueError:
        return True


def loop_ceilings(task):
    """`{ceiling: (limit, rule id)}` for this issue, from the routing policy
    in force. For each ceiling the lowest limit among the rules whose `when`
    matches the assessment applies, so a rule can only lower a limit. A
    ceiling no rule sets is absent: there is no limit in code."""
    policy = load_yaml(os.path.join(find_governance(), "routing-policy.yml"))
    guardrails = (policy or {}).get("routing_guardrails") or {}
    readings = task.get("assessment") or {}
    found = {}
    for rule in guardrails.get("loop_ceilings") or []:
        if not isinstance(rule, dict) or rule.get("ceiling") not in CEILINGS:
            continue
        limit = rule.get("limit")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            continue
        if not reading_matches(rule.get("when"), readings):
            continue
        name = rule["ceiling"]
        if name not in found or limit < found[name][0]:
            found[name] = (limit, str(rule.get("id", "?")))
    return found
