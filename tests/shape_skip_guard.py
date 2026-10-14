"""A pytest plugin: a skip in a shape test fails the run that skipped it.

The shape tests (`archive.SHAPE_TESTS`) read the archive sample, which is
tracked, so they must run on every machine. A skip there means a check ran
against nothing, and a skipped test passes. While `COMPASS_FULL_ARCHIVE` is not
`1`, this plugin turns such a skip into a failure that names the test and the
skip reason. It covers both ways a test is skipped:

- a skipped test report (a skip marker, a `pytest.skip` call, a skipping fixture);
- a skipped collection (a module-level `pytest.importorskip` or `pytest.skip`).

A report is made in the process that runs the test, so the plugin acts in every
process, workers included. An expected failure (xfail) is not a skip.

`tests/conftest.py` imports the two hooks, so every suite run is guarded. A
planted run outside `tests/` loads this module with `-p shape_skip_guard`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from archive import SHAPE_TESTS, full_archive


def _is_shape_file(path) -> bool:
    return path is not None and Path(str(path)).name in SHAPE_TESTS


def _skip_reason(report) -> str:
    longrepr = report.longrepr
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        return str(longrepr[2])
    return str(longrepr)


def _failure(what: str, reason: str) -> str:
    return (f"{what} was skipped, and a shape test must not skip while "
            f"COMPASS_FULL_ARCHIVE is not 1 (it reads the archive sample, which is "
            f"always present). Skip reason: {reason}")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    if (report.skipped and not hasattr(report, "wasxfail") and not full_archive()
            and _is_shape_file(getattr(item, "path", None))):
        reason = _skip_reason(report)
        report.outcome = "failed"
        report.longrepr = _failure(item.nodeid, reason)
    return report


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(collector):
    report = yield
    if (report.skipped and not full_archive() and isinstance(collector, pytest.Module)
            and _is_shape_file(getattr(collector, "path", None))):
        reason = _skip_reason(report)
        report.outcome = "failed"
        report.longrepr = _failure(collector.nodeid, reason)
    return report
