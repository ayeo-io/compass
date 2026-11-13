# compass_pkg.outside_gate - the checks `compass check` runs outside every gate
"""One way to run a check that sits in no gate (ADR-050, ADR-064).

Most checks run because a guardrail lists them. A few are listed by no gate,
so adding one changes no gate, and a waiver a person approves can excuse one on
one issue. `compass check` runs each of them after the gate
loop, in the order of `CHECKS`, through `judged`.

A check runs only when the configuration the issue is judged by declares it:
the stored generation, or the live check set with the settings of
`compass.yml`. An issue stored before a check existed
does not run it until its next `compass approach evaluate --write` (ADR-036).
"""
# DEPENDENCY: compass_pkg.effective, imported when a check is judged. It imports no
# command module and no check module at load time, so a check module can import it.
from __future__ import annotations

#: The checks that sit in no gate, in the order `compass check` reports them. 9.0.0
#: removes `artifacts-approved`, `contracts-declared` and `design-within-word-ceiling`
#: (ADR-091); a stored configuration that declares one reports it as nothing to check.
CHECKS = ("request-recorded", "artifacts-approved", "nfr-rows-resolved", "contracts-declared",
          "design-within-word-ceiling", "acceptance-applicability-agrees",
          "outer-loop-recorded", "acceptance-support-present", "outer-loop-attempts-recorded",
          "isolation-proven", "layering-test-passed", "ship-approval-present")

#: Those a spike runs too. `artifacts-approved` judges what ships, and a spike ships
#: nothing; the section checks and the design-size check report that a spike
#: registers no spec or design. The four-layer acceptance strategy is suspended on
#: a spike, as strategy `S2` is, so none of its checks is here.
SPIKE_CHECKS = ("nfr-rows-resolved", "contracts-declared", "design-within-word-ceiling")

#: The label each check's row is reported under, where a gate row names its guardrail.
LABELS = {
    "request-recorded": "request",
    "artifacts-approved": "approved documents",
    "nfr-rows-resolved": "non-functional requirements",
    "contracts-declared": "data and interfaces",
    "design-within-word-ceiling": "design size",
    "acceptance-applicability-agrees": "four-layer acceptance strategy (`S17`)",
    "outer-loop-recorded": "four-layer acceptance strategy (`S17`)",
    "acceptance-support-present": "four-layer acceptance strategy (`S17`)",
    "outer-loop-attempts-recorded": "four-layer acceptance strategy (`S17`)",
    "isolation-proven": "four-layer acceptance strategy (`S17`)",
    "layering-test-passed": "four-layer acceptance strategy (`S17`)",
    "ship-approval-present": "ship approval",
}


def judged(check_id, fn, task, task_dir, judge):
    """`(passed, detail)` of the implementation `fn` on the issue, after what the
    issue's configuration declares for `check_id`, or None when the configuration does
    not declare the check. `judge` is `check_cmd._judge`, passed in by the
    caller so this module imports no command module. `passed` can be
    `ADVISORY_FAILURE` after a waiver."""
    from compass_pkg import effective

    try:
        view = effective.effective_for(task_dir)
        guardrails = view.guardrail_gates()
        matches = view.matches
        readings = view.listing_assessment(task.get("assessment") or {},
                                           task.get("delivery_approach"))
    except Exception:                                   # noqa: BLE001 - no configuration, nothing declared
        return None
    if check_id not in (guardrails.get("impl") or {}) and check_id not in (
            guardrails.get("checks") or {}):
        return None
    declared = (guardrails.get("checks") or {}).get(check_id) or {}
    try:
        passed, detail = fn(task, task_dir)
    except Exception as exc:                            # noqa: BLE001 - a check must not crash the run
        passed, detail = False, f"check errored: {exc}"
    return judge(passed, detail, declared, matches, readings)

