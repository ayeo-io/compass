"""Colour codes in pytest's output do not hide what it reports.

With FORCE_COLOR set, as many terminals and CI services do, pytest puts ANSI
colour codes around `E`, `PASSED`, `FAILED` and the summary counts. Compass
matched those words in plain text, so `compass tdd-red` refused a genuine
import red, and the eval harness and judge read no outcomes and no failures
(#403).

Scenario id: CL-1 (issue `colour-hides-an-import-red`).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals"))

from test_red_must_show_a_failure import red  # noqa: E402,F401

# The end of `pytest -q -rA` under FORCE_COLOR=3 (pytest 9.0.2), with one
# passing and one failing test.
ESC = "\x1b"
COLOURED = (
    f"{ESC}[36m{ESC}[1m=========================== short test summary info "
    f"============================{ESC}[0m\n"
    f"{ESC}[32mPASSED{ESC}[0m test_x.py::{ESC}[1mtest_a{ESC}[0m\n"
    f"{ESC}[31mFAILED{ESC}[0m test_x.py::{ESC}[1mtest_b{ESC}[0m - assert 1 == 2\n"
    f"{ESC}[31m{ESC}[31m{ESC}[1m1 failed{ESC}[0m, {ESC}[32m1 passed{ESC}[0m"
    f"{ESC}[31m in 0.02s{ESC}[0m{ESC}[0m\n")


def test_cl_1_an_import_red_is_recorded_with_colour_forced(red, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "3")
    result, record = red("from src.thing import go\n\n"
                         "def test_go():\n    assert go() == 1\n")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "import"


def test_cl_1_the_harness_reads_outcomes_and_counts_through_colour():
    import harness
    assert harness._pytest_outcomes(COLOURED) == {
        "test_x.py::test_a": "PASSED", "test_x.py::test_b": "FAILED"}
    assert harness._pytest_summary_counts(COLOURED) == (1, 1)


def test_cl_1_the_judge_sees_a_coloured_failure():
    import judge
    assert judge._pytest_summary_reports_failure(COLOURED)


def test_cl_1_the_suite_runs_without_the_callers_colour_settings():
    """Tests that read pytest's text from a subprocess must not depend on
    the shell they were started from; conftest removes the colour settings."""
    for name in ("FORCE_COLOR", "PY_COLORS", "CLICOLOR_FORCE"):
        assert name not in os.environ, name
