"""An issue still in flight has its declared test ids checked.

Scenario QRL-1, in `queued-issues-read-as-landed/delivery-approach.md`.

`_check_declared_tests_resolve` closes the gap: a scenario can name a test
nobody wrote and still report green, because `G1` and `G3` are satisfied by
a test being named. The check is meant to be scoped away from landed
issues, whose manifests are historical records that a moving codebase would
fail for no actionable reason.

The check skips only a closed issue (`done`, with any close reason). An issue
in the backlog or in flight is still being worked on, so the check runs on it.
A manifest written before 6.0.0 reads the same way: `landed` and `abandoned`
are closed, `queued`, `parked` and `active` are not.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPASS_CLI = ROOT / "cli" / "compass"

sys.path.insert(0, str(ROOT / "cli"))
from compass_pkg import status_words  # noqa: E402

#: An issue whose work is over, as `(status, other keys, the status the check
#: reads)`. Its manifest is a record of what was true then, and re-validating
#: it against a codebase that has moved produces failures nobody can act on
#: (ADR-006).
TERMINAL = (
    ("done", {"close_reason": "completed"}, "done"),
    ("done", {"close_reason": "not-planned"}, "done"),
    ("landed", {}, "done"),
    ("abandoned", {}, "done"),
)

#: Still being worked on, whatever the board calls it: no stored status, a
#: backlog hold, and the words stored before 6.0.0.
IN_FLIGHT = (
    (None, {}), ("backlog", {}), ("queued", {}), ("parked", {}), ("active", {}),
)


def _issue(tmp_path, status, slug="an-issue", extra=None):
    """An issue claiming correctness, naming a test that does not exist."""
    work = tmp_path / ".compass" / "work" / slug
    (work / "evidence").mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n",
                                                      encoding="utf-8")
    (work / "evidence" / "green.json").write_text(
        '{"command": "pytest -q", "exit_code": 0, "passed": true, '
        '"attempts": 1, "timestamp": "2026-09-11T09:00:00+00:00", '
        '"log_excerpt": "1 passed"}', encoding="utf-8")
    (work / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": slug, "created": "2026-09-11",
        **({"status": status} if status else {}), **(extra or {}),
        "assessment": {"risk": "trivial", "familiarity": "brownfield-mapped",
                       "size": "atomic", "goal": "delivery", "role": "engineer"},
        "delivery_approach": "express",
        "stages": {"assess": "full", "define": "light", "refine": "collapsed",
                   "plan": "collapsed", "breakdown": "skipped",
                   "implement": "full", "verify": "light", "ship": "light"},
        "evidence": [{"id": "EV-T", "type": "test-run",
                      "path": "evidence/green.json"}],
        "gates": [{"id": "verify.correctness", "status": "pass",
                   "evidence": ["EV-T"]},
                  {"id": "verify.governance", "status": "pass",
                   "evidence": ["EV-T"]},
                  {"id": "verify.traceability", "status": "pass",
                   "evidence": ["EV-T"]}],
        "scenarios": [{"id": "S-1", "title": "a thing", "intent": "INT-1",
                       "tests": ["tests/test_nobody_wrote_this.py::test_x"]}],
        "changed_files": [], "claims": [], "follow_ups": [],
    }, sort_keys=False), encoding="utf-8")
    return work


def _check(project, slug="an-issue"):
    return subprocess.run(
        [sys.executable, str(COMPASS_CLI), "check", "--issue", slug,
         "--verbose"],
        capture_output=True, text=True, timeout=120, cwd=str(project))


@pytest.mark.parametrize("status,extra", IN_FLIGHT)
def test_qrl_1_an_in_flight_issue_has_its_declared_tests_checked(
        tmp_path, status, extra):
    """The gap, on every status that is not closed."""
    _issue(tmp_path, status, extra=extra)
    r = _check(tmp_path)
    assert "declared-tests-resolve" in r.stdout
    assert r.returncode != 0, (
        f"an issue with status {status!r} claims correctness and names a test "
        f"nobody wrote, and the check passed:\n" + r.stdout[-1500:])
    assert "test_nobody_wrote_this" in r.stdout, (
        "the check failed without naming the test that does not resolve:\n"
        + r.stdout[-1500:])


@pytest.mark.parametrize("status,extra,shown", TERMINAL)
def test_qrl_1_a_finished_issue_is_still_left_alone(tmp_path, status, extra, shown):
    """The control. Scoping the skip correctly must not start failing the
    records it was written to leave alone."""
    _issue(tmp_path, status, extra=extra)
    r = _check(tmp_path)
    assert "test_nobody_wrote_this" not in r.stdout, (
        f"an issue with status {status!r} had its historical record "
        f"re-validated against the current tree:\n" + r.stdout[-1500:])


@pytest.mark.parametrize("status,extra,shown", TERMINAL)
def test_qrl_1_the_skip_names_the_status_it_read(tmp_path, status, extra, shown):
    """The PASS line names the status the manifest records."""
    _issue(tmp_path, status, extra=extra)
    r = _check(tmp_path)
    line = next((l for l in r.stdout.splitlines()
                 if "declared-tests-resolve" in l), "")
    assert shown in line, (
        f"the skip line does not name the status it read ({shown!r}):\n"
        f"  {line.strip()}")


def test_qrl_1_the_two_status_sets_cover_the_vocabulary():
    """A status added later must land on one side or the other deliberately.

    Without this, a sixth status is silently in-flight or silently terminal
    depending on how the condition happens to be written.
    """
    known = set(status_words.STORED_STATES) | set(status_words.RETIRED_STATUSES)
    closed = {s for s, _extra, _shown in TERMINAL}
    open_ = {s for s, _extra in IN_FLIGHT if s}
    assert closed | open_ == known, (
        f"the status vocabulary is {sorted(known)}, and this file "
        f"accounts for {sorted(closed | open_)}")
    assert closed.isdisjoint(open_)
