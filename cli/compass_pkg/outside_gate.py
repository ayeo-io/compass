# compass_pkg.outside_gate - the checks `compass check` runs outside every gate
"""One way to run a check that sits in no gate (ADR-050, ADR-064).

Most checks run because a guardrail lists them. A few are listed by no gate,
so a locked guardrail does not change when they are added and an issue waiver
can make them advisory. `compass check` runs each of them after the gate
loop, in the order of `CHECKS`, through `judged`.

A check runs only when the configuration the issue is judged by declares it:
the stored generation, the live view of a project with a `compass.yml`, or the
legacy `governance/guardrails.yml`. An issue stored before a check existed
does not run it until its next `compass approach evaluate --write` (ADR-036).
"""
# DEPENDENCY: standard library (os); compass_pkg.core. It imports no command
# module and no check module at load time, so a check module can import it.
from __future__ import annotations

import os

from compass_pkg.core import load_yaml, reading_matches

#: The checks that sit in no gate, in the order `compass check` reports them.
CHECKS = ("artifacts-approved", "nfr-rows-resolved", "contracts-declared")

#: Those a spike runs too. `artifacts-approved` judges what ships, and a spike ships
#: nothing; the section checks report that a spike registers no spec or design.
SPIKE_CHECKS = ("nfr-rows-resolved", "contracts-declared")

#: The label each check's row is reported under, where a gate row names its guardrail.
LABELS = {
    "artifacts-approved": "approved documents",
    "nfr-rows-resolved": "non-functional requirements",
    "contracts-declared": "data and interfaces",
}


def judged(check_id, fn, task, task_dir, judge):
    """`(passed, detail)` of the implementation `fn` on the issue, after what the
    issue's configuration declares for `check_id`, or None when the configuration does
    not declare the check. `judge` is `check_cmd._judge`, passed in by the
    caller so this module imports no command module. `passed` can be
    `ADVISORY_FAILURE` after a waiver."""
    from compass_pkg import effective
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
    if check_id not in (guardrails.get("impl") or {}) and check_id not in (
            guardrails.get("checks") or {}):
        return None
    try:
        passed, detail = fn(task, task_dir)
    except Exception as exc:                            # noqa: BLE001 - a check must not crash the run
        passed, detail = False, f"check errored: {exc}"
    return judge(passed, detail, (guardrails.get("checks") or {}).get(check_id) or {},
                 matches, readings)
