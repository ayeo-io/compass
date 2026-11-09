#!/usr/bin/env python3
# =============================================================================
# compass - the loop ceilings a configuration declares
# =============================================================================
# The `loop_ceilings` rules in routing-policy.yml bounded a
# multiagent run (tries per subtask, review rounds, replans and the same error
# reported in a row) and the unattended `compass run` (sessions, minutes and
# money). 9.0.0 removed both (ADR-090), so nothing applies the limits. They
# stay a readable part of a configuration, which the classifier compares,
# until the configuration layers are replaced.
#
# DEPENDENCY: standard library (datetime, os), compass_pkg.core and compass_pkg.effective.
# =============================================================================
"""The loop ceilings an issue's assessment earns, and the date they apply from."""
from __future__ import annotations

import datetime

#: An issue is compared with its loop ceilings by the check only if created
#: on or after the day the ceilings landed (ADR-006).
LOOP_CEILINGS_FROM = datetime.date(2026, 10, 3)

#: The ceilings a `loop_ceilings` rule in routing-policy.yml can set.
CEILINGS = ("builder_attempts", "review_rounds", "replans", "repeated_error",
            "run_cycles", "run_minutes", "run_cost_usd")


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


def loop_ceilings(task, task_dir=None):
    """`{ceiling: (limit, rule id)}` for this issue, from the routing policy
    in force: the issue's generation when `task_dir` names one, else the
    project's live configuration. For each ceiling the lowest limit among the rules whose
    `when` matches the assessment applies, so a rule can only lower a limit. A
    ceiling no rule sets is absent: there is no limit in code."""
    from compass_pkg import effective
    view = effective.effective_for(task_dir)
    rules, matches = view.loop_ceiling_rules(), view.matches
    readings = task.get("assessment") or {}
    found = {}
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("ceiling") not in CEILINGS:
            continue
        limit = rule.get("limit")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            continue
        if not matches(rule.get("when"), readings):
            continue
        name = rule["ceiling"]
        if name not in found or limit < found[name][0]:
            found[name] = (limit, str(rule.get("id", "?")))
    return found
