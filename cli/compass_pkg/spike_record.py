# compass_pkg.spike_record - the decision a spike closes with
"""The close-out decision of a spike, which the check `spike-conclusion-present` reads.

`compass evidence add --type spike-conclusion --decision D [--next-issue SLUG]` writes it
since 9.0.0 removed `compass issue artifact set` (ADR-091). The rules are the ones that
command applied, so a record written either way reads the same.
"""
# DEPENDENCY: compass_pkg.core (CompassError).
from __future__ import annotations

from compass_pkg.core import CompassError

SPIKE_DECISIONS = ("discard", "graduate-to-delivery", "defer")
SPIKE_EVIDENCE_ID = "EV-SPIKE-CONCLUSION"
NEXT_FLAG = "--next-issue"


def decision_arguments(args, kind):
    """The validated `(decision, next_issue)` of `--decision`, or `(None, None)`.
    Refuses before anything is written."""
    decision = getattr(args, "decision", None)
    next_issue = getattr(args, "next_issue", None)
    if decision is None and next_issue is None:
        return None, None
    if kind != "spike-conclusion":
        raise CompassError(
            "--decision and %s record how a spike closes, so they apply to "
            "spike-conclusion only, not to %r." % (NEXT_FLAG, kind))
    if decision is None:
        raise CompassError("%s goes with --decision graduate-to-delivery." % NEXT_FLAG)
    if decision not in SPIKE_DECISIONS:
        raise CompassError(
            "--decision %r is not a way a spike closes. The decisions are: %s."
            % (decision, ", ".join(SPIKE_DECISIONS)))
    if decision == "graduate-to-delivery" and not (next_issue or "").strip():
        raise CompassError(
            "--decision graduate-to-delivery needs %s <slug>, the delivery issue "
            "the spike graduates to. Graduation is a fresh assessment, not a merge." % NEXT_FLAG)
    if next_issue and decision != "graduate-to-delivery":
        raise CompassError("%s goes with --decision graduate-to-delivery only." % NEXT_FLAG)
    return decision, (next_issue or "").strip() or None
