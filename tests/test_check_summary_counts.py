"""`compass check`'s summary does not overstate what was checked.

The summary counts checks that inspected nothing apart from real passes.
Three of the sixteen checks clear with nothing to check: no BDD runner
wired, no claims recorded, no project guardrails declared. Each is honestly
labelled on its own line, but `PASS - all 16 check(s) passed` flattened
those three into the same count as thirteen real ones, and the summary is
the line a reader takes away.

The signal is structured rather than matched from the detail prose. A
check's nothing to check is a runtime property - "no BDD runner wired"
depends on the project - so a static list cannot express it, and matching
the message would be a guard that silently stops working the first time
someone improves the wording.

Scenario ids: see identifiers-and-vocabulary-in-printed-output/
acceptance-criteria.md (group D).
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

import compass_pkg                                              # noqa: F401,E402

# Imported inside each test rather than at module level. A module-level import
# of a symbol that does not exist yet is an ImportError, which makes the whole
# file uncollectable - and `compass tdd-red` correctly refuses to record that
# as a red, because no test ran. A red has to be a test that ran and failed.


def _summarise():
    from compass_pkg.check_cmd import summarise_counts
    return summarise_counts


# ---------------------------------------------------------------------------
# `TRC-D1` - checks that inspected nothing are counted apart
# ---------------------------------------------------------------------------

def test_trc_d1_empty_counted_apart():
    """Sixteen ran, three had nothing to check."""
    line = _summarise()(ran=16, failures=0, nothing_to_check=3)

    # The summary has no denominator, because "13 of 16 passed" reads as
    # three failures at a glance, and the total is not a constant - `G5` only
    # runs when the work touches auth, payments, personal data or
    # migrations. The count that matters is what passed.
    # tests/test_ceiling_and_honest_counts.py holds the current contract.
    assert "13 check(s) passed" in line, (
        f"the summary does not lead with how many checks verified something: "
        f"{line!r}")
    assert " of 16" not in line, (
        f"the summary prints a denominator again: {line!r}")
    assert re.search(r"3\b.*(nothing to check|empty)", line, re.I), (
        f"the three checks that inspected nothing are not reported as such: "
        f"{line!r}")
    assert line.startswith("compass check: PASS"), (
        f"a run with no failures must still read as a pass: {line!r}")


# ---------------------------------------------------------------------------
# `TRC-D2` - a real pass is not miscounted
# ---------------------------------------------------------------------------

def test_trc_d2_real_pass_not_miscounted():
    """The control.

    Without it, a change that labelled every check empty would satisfy
    `TRC-D1` while reporting that Compass checked nothing.
    """
    line = _summarise()(ran=16, failures=0, nothing_to_check=0)

    assert "16" in line, f"the total is no longer reported: {line!r}"
    assert not re.search(r"nothing to check|empty", line, re.I), (
        f"a run where every check had something to check still claims some "
        f"had nothing: {line!r}")
    assert line.startswith("compass check: PASS"), line


def test_trc_d2b_a_failure_still_reads_as_a_failure():
    """Nothing to check must not soften a real failure - the count is a caveat on a
    pass, never a way to report fewer failures than there were."""
    line = _summarise()(ran=16, failures=2, nothing_to_check=3)

    assert line.startswith("compass check: FAIL"), line
    assert "2" in line, f"the failure count is missing: {line!r}"


def test_trc_d2c_the_sentinel_is_truthy():
    """NOTHING_TO_CHECK stands in for True at every existing call site.

    A falsy sentinel would silently convert three passing checks into three
    failures, which is the opposite of what this change prevents.
    """
    from compass_pkg.checks import NOTHING_TO_CHECK

    assert NOTHING_TO_CHECK, "NOTHING_TO_CHECK is falsy - every empty check would count as a failure"
    assert NOTHING_TO_CHECK is not True, (
        "NOTHING_TO_CHECK is literally True, so the summary cannot tell a empty "
        "clearance from a verified one")


# ---------------------------------------------------------------------------
# The default view and --verbose give the same counts
# ---------------------------------------------------------------------------

def _run_with_a_check_under_two_guardrails():
    """A run where `changed-code-traces-to-scenario` and
    `scenario-has-id-and-intent` are each listed under two guardrails, as the
    shipped check set lists them under `G1`/`G2` and `G3`."""
    from types import SimpleNamespace

    from compass_pkg.check_results import ADVISORY_FAILURE, NOTHING_TO_CHECK
    results = [
        ("G1", "suite-passed", True, "green"),
        ("G1", "changed-code-traces-to-scenario", True, "traced"),
        ("G1", "scenarios-are-executable", NOTHING_TO_CHECK, "no runner"),
        ("G2", "scenario-has-id-and-intent", True, "ids"),
        ("G3", "changed-code-traces-to-scenario", True, "traced"),
        ("G3", "scenario-has-id-and-intent", True, "ids"),
        ("", "acceptance-support-present", ADVISORY_FAILURE, "missing support"),
    ]
    rows = []
    for g, n, p, d in results:
        rows += [("guardrail", (g, g, None)), ("result", (n, p, d))]
    return SimpleNamespace(
        slug="the-issue", approach="delivery", mode_banner="[mode: enforced]",
        rows=rows, results=results, ran=len(results), failures=0, nothing=1,
        advisory=1, waived=0, refused=set())


def test_the_verbose_footer_counts_each_check_once():
    """A check listed under two guardrails has two rows in --verbose, and is
    one check. Both views count it once, so they give the same numbers."""
    from compass_pkg.check_cmd import _summary_lines, _verbose_lines
    run = _run_with_a_check_under_two_guardrails()
    summary = _summary_lines(run)[0]
    footer = _verbose_lines(run)[-1]
    assert summary.startswith("PASS - 3 check(s) passed, 1 had nothing to check, "
                              "1 failed as advisory"), summary
    assert footer.startswith("compass check: PASS - 3 check(s) passed, "), footer
    assert "1 failed as advisory (does not block)" in footer, footer
    assert "1 had nothing to check" in footer, footer
