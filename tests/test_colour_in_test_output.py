"""Colour codes in pytest's output do not hide what it reports.

With FORCE_COLOR set, as many terminals and CI services do, pytest puts ANSI
colour codes around `E`, `PASSED`, `FAILED` and the summary counts. Compass
matched those words in plain text, so `compass tdd-red` refused a genuine
import red (#403). The eval harness and judge that also read that output,
and their colour tests, left Compass with ADR-093.

Scenario id: CL-1 (issue `colour-hides-an-import-red`).
"""
from __future__ import annotations

import os

from test_red_must_show_a_failure import red  # noqa: F401


def test_cl_1_an_import_red_is_recorded_with_colour_forced(red, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "3")
    result, record = red("from src.thing import go\n\n"
                         "def test_go():\n    assert go() == 1\n")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "import"


def test_cl_1_the_suite_runs_without_the_callers_colour_settings():
    """Tests that read pytest's text from a subprocess must not depend on
    the shell they were started from; conftest removes the colour settings."""
    for name in ("FORCE_COLOR", "PY_COLORS", "CLICOLOR_FORCE"):
        assert name not in os.environ, name
