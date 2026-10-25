# compass_pkg.g5_label_prompt - the assess line that names guardrail 5's labels
"""The line `compass approach evaluate` adds when risk is critical and the
trigger of guardrail `G5` in force does not match the assessment.

From 7.0.0 the shipped trigger is the four irreversible labels, and critical
risk alone does not bring the human sign-off (governance decision
2026-10-12-guardrail-5-triggers-on-the-irreversible-labels). A critical-risk
change that is a migration but was not labelled would ship without one, so the
assessor is told which labels the trigger reads. The label stays their
judgement (ADR-001). The trigger is read from the configuration in force, so a
project that put critical risk back gets no line.

A project that runs on copied governance has no effective view and gets no
line: its copied `guardrails.yml` holds the trigger it copied, which before
7.0.0 already fired on critical risk.

The owning doc is `governance/routing-policy.md`.
"""
# DEPENDENCY: standard library only; compass_pkg.stable_ids.
from __future__ import annotations

from compass_pkg.stable_ids import GATE_G5


def labels_read(when):
    """The labels a `when:` clause reads, in order, through `any_of`."""
    out = []
    for key, val in (when or {}).items():
        if key in ("labels_any", "touches_any"):
            out += [v for v in (val if isinstance(val, list) else [val]) if v not in out]
        elif key == "any_of":
            for clause in (val if isinstance(val, list) else [val]):
                out += [v for v in labels_read(clause) if v not in out]
    return out


def prompt(view, readings):
    """The concern line, or `None`. `view` is the issue's effective view, or
    `None` for a project that runs on copied governance."""
    if view is None or (readings or {}).get("risk") != "critical":
        return None
    gates = view.guardrail_gates()["defaults"]
    g5 = next((g for g in gates if isinstance(g, dict) and g.get("id") == GATE_G5), None)
    when = (g5 or {}).get("applies_when")
    labels = labels_read(when)
    if not when or not labels or view.matches(when, readings):
        return None
    named = ", ".join(labels[:-1]) + " or " + labels[-1] if len(labels) > 1 else labels[0]
    # One line of at most 100 columns, so the four default labels fit whole.
    return f"risk is critical, but the `G5` sign-off needs {named}"
