#!/usr/bin/env python3
# =============================================================================
# compass - the check result sentinel
# =============================================================================
# One value, in its own module so that both the check registry (checks.py) and
# the checks split out of it can use it without importing each other.
#
# DEPENDENCY: standard library only.
# =============================================================================
"""The sentinel for a check that passed without checking anything."""
from __future__ import annotations


class _NothingToCheck(int):
    """A pass that checked nothing, distinguishable from one that did.

    A check passes without checking anything when the thing it inspects does not exist in
    this project - no BDD runner wired, no claims recorded, no project
    guardrails declared. That is a legitimate pass, but counting it beside a
    real one lets the summary overstate what was checked.

    It subclasses int and is truthy, so every existing `if not passed` and
    every caller that only cares pass/fail keeps working untouched; only the
    summary asks whether a result `is NOTHING_TO_CHECK`.
    """

    def __repr__(self):
        return "NOTHING_TO_CHECK"


NOTHING_TO_CHECK = _NothingToCheck(1)


class _AdvisoryFailure(int):
    """A check that failed and does not block: its effective severity is
    advisory. Like `NOTHING_TO_CHECK` it is truthy, so every caller that only
    asks pass or fail sees a run that is not failed; the views ask whether a
    result `is ADVISORY_FAILURE` so the finding is never shown as a pass."""

    def __repr__(self):
        return "ADVISORY_FAILURE"


ADVISORY_FAILURE = _AdvisoryFailure(1)
