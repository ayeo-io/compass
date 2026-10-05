"""Three claims the tool made that it could not support.

Each is the same shape: output that reads as a decision or a verification when
it is neither.

* **Orchestration at assessment.** The evaluator printed `topology: swarm` for <!-- vocabulary-scan: allow - quotes the retired printed output this fix replaces -->
  work with one changed file. It cannot know: it has no concept of a work
  unit, and `routing-policy.yml` contains no reference to units, independence
  or subtasks. The distribution map that decides parallelism is written at
  plan, three stages later. So the evaluator now emits a *ceiling* - how many
  subtasks this approach permits - and breakdown sets the orchestration once
  the map exists.

* **The check summary's denominator.** `12 of 15 check(s) passed` reads as
  three failures at a glance. The total is also not a constant: it depends on
  the assessment, because `G5 A human signs off on the irreversible` only
  applies when the work touches auth, payments, personal data or migrations.

* **`suite-passed`'s wording.** It establishes that a green run is on record.
  It does not establish which scenarios that run exercised - `green.json`
  holds one exit code for one command and never enumerates the tests.

Scenario ids: see dry-run-2-rulings/acceptance-criteria.md.
"""

# These tests read the per-check detail, which the command prints only
# under --verbose.
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))


def _spine(**over):
    d = {
        "schema_version": "2.0", "task": "demo", "created": "2026-08-14",
        "status": "active",
        "assessment": {"risk": "critical", "familiarity": "brownfield-mapped",
                       "size": "small", "goal": "delivery", "role": "engineer",
                       "labels": ["auth"]},
    }
    d.update(over)
    return d


def _project(tmp_path, manifest=None):
    root = tmp_path / "proj"
    (root / ".compass" / "work" / "demo").mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (root / ".compass" / "work" / "demo" / "manifest.yml").write_text(
        yaml.safe_dump(manifest or _spine(), sort_keys=False))
    (root / ".compass" / "current-task").write_text("demo\n")
    return root


# ---------------------------------------------------------------------------
# Group A - the evaluator emits a ceiling, not a topology <!-- vocabulary-scan: allow - contrasts the retired concept with the ceiling -->
# ---------------------------------------------------------------------------

def test_trc_a1_evaluator_emits_a_ceiling_not_a_topology(tmp_path):
    """Assessment says how much parallelism is PERMITTED. It cannot say how
    much there is, because the work units are not known until plan."""
    root = _project(tmp_path)
    r = subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--verbose", "--issue", "demo",
         "--write"], cwd=str(root), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"

    assert not re.search(r"^\s*(topology|orchestration)\s*:", r.stdout, re.M), (
        f"the evaluator still prints a topology decision at triage, before "
        f"any work unit is known:\n{r.stdout}")
    assert re.search(r"parallel subtasks|subtask ceiling|permits", r.stdout, re.I), (
        f"the evaluator does not report the parallelism it permits:\n{r.stdout}")


def test_trc_a2_the_ceiling_is_a_number_not_a_sentence(tmp_path):
    """The bug this replaces: the evaluator wrote the string
    "solo (capped to 1 worktree)" into the manifest's topology field - a sentence <!-- vocabulary-scan: allow - names the retired field the bug wrote into -->
    in a machine field, which nothing downstream can compare against."""
    root = _project(tmp_path)
    subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--verbose", "--issue", "demo",
         "--write"], cwd=str(root), capture_output=True, text=True, timeout=60,
        check=True)
    manifest = yaml.safe_load(
        (root / ".compass" / "work" / "demo" / "manifest.yml").read_text())

    ceiling = manifest.get("subtask_ceiling")
    assert isinstance(ceiling, int), (
        f"subtask_ceiling is not an integer: {ceiling!r}")
    assert ceiling == 1, (
        f"critical risk caps parallelism at one worktree, so the ceiling is "
        f"1, not {ceiling!r}")
    assert not isinstance(manifest.get("orchestration"), str) or not manifest.get("orchestration"), (
        f"assess still writes an orchestration into the manifest: "
        f"{manifest.get('orchestration')!r} - breakdown owns that once the "
        f"distribution map exists")


def test_trc_a3_an_uncapped_approach_permits_more_than_one(tmp_path):
    """The control. Without it, a change that hardcoded 1 would pass A2 while
    reporting that Compass never permits parallel work."""
    root = _project(tmp_path, _spine(assessment={
        "risk": "contained", "familiarity": "brownfield-mapped",
        "size": "large", "goal": "delivery", "role": "engineer",
        "labels": []}))
    subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--verbose", "--issue", "demo",
         "--write"], cwd=str(root), capture_output=True, text=True, timeout=60,
        check=True)
    manifest = yaml.safe_load(
        (root / ".compass" / "work" / "demo" / "manifest.yml").read_text())
    # None means unbounded, which is what an uncapped multiagent actually
    # permits. The assertion is "not pinned to one", not "greater than one" -
    # a fixed ceiling such as 8 would also satisfy "greater than one" without
    # being unbounded.
    assert manifest["subtask_ceiling"] != 1, (
        f"large work on contained risk permits parallel streams; the ceiling "
        f"came out {manifest['subtask_ceiling']!r}")


# ---------------------------------------------------------------------------
# Group B - the check summary drops its denominator
# ---------------------------------------------------------------------------

def test_trc_b1_summary_has_no_denominator():
    """`12 of 15` reads as three failures on the screen people share, and
    the 15 is not a constant - it depends on whether `G5` applies."""
    from compass_pkg.check_cmd import summarise_counts

    line = summarise_counts(ran=15, failures=0, nothing_to_check=3)
    assert "12 check(s) passed" in line, (
        f"the summary does not lead with what actually passed: {line!r}")
    assert "3 had nothing to check" in line, line
    assert " of 15" not in line and " of 16" not in line, (
        f"the summary still prints a denominator, which reads as failures: "
        f"{line!r}")


def test_trc_b2_a_failure_still_names_its_denominator():
    """The control: a denominator is the right thing to print when checks
    FAILED - "2 of 12 failed" is the number a reader needs. The checks that
    inspected nothing are counted apart, not in the denominator (#110)."""
    from compass_pkg.check_cmd import summarise_counts

    line = summarise_counts(ran=15, failures=2, nothing_to_check=3)
    assert line.startswith("compass check: FAIL"), line
    assert "2 of 12" in line, (
        f"a failing run must still say how many of how many: {line!r}")
    assert "3 had nothing to check" in line, line


# ---------------------------------------------------------------------------
# Group C - suite-passed claims only what it establishes
# ---------------------------------------------------------------------------

def test_trc_c1_suite_passed_does_not_imply_scenario_coverage(tmp_path):
    """The wording must not read as per-scenario proof.

    `green.json` records one exit code for one command. Which scenarios that
    command exercised is not recorded anywhere, so a message naming scenarios
    beside "all green" invites a reading the evidence does not support.
    """
    from compass_pkg.checks import _check_suite_passed

    d = tmp_path / "t"
    (d / "evidence").mkdir(parents=True)
    (d / "evidence" / "green.json").write_text(json.dumps({"exit_code": 0}))
    task = {
        "evidence": [{"id": "EV-T", "type": "test-run",
                      "path": "evidence/green.json", "scenario": "TRC-1"}],
        "scenarios": [{"id": "TRC-1"}, {"id": "TRC-2"}, {"id": "TRC-3"}],
    }
    passed, detail = _check_suite_passed(task, str(d))

    assert passed, detail
    assert "bound to scenarios" not in detail, (
        f"the message still presents the evidence's scenario label as though "
        f"it were coverage: {detail!r}")
    assert re.search(r"which scenario|not establish|does not record", detail, re.I), (
        f"the message does not say what it leaves unestablished - that a "
        f"green run does not record which scenarios it exercised: {detail!r}")


def test_trc_c2_declared_tests_resolve_refuses_a_skipped_test(tmp_path, monkeypatch):
    """A scenario may name a test that resolves and never runs.

    This repository's own suite contains a todo/skipped test, so this
    happens in practice: `declared-tests-resolve` passed on a scenario whose
    only test was permanently skipped, which is a declared test that nobody
    runs.
    """
    from compass_pkg.checks import _check_declared_tests_resolve

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_thing.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.skip(reason='not written yet')\n"
        "def test_covered():\n    pass\n")
    d = tmp_path / ".compass" / "work" / "demo"
    d.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    # The check resolves declared paths against the project root it finds by
    # walking up from the working directory, so the fixture has to BE that
    # project rather than sit beside it.
    monkeypatch.chdir(tmp_path)
    task = {
        "status": "active",
        "gates": [{"id": "verify.correctness", "status": "pass"}],
        "scenarios": [{"id": "TRC-1", "tests": [
            "tests/test_thing.py::test_covered"]}],
    }
    passed, detail = _check_declared_tests_resolve(task, str(d))

    assert not passed, (
        f"a scenario whose only test is permanently skipped was accepted as "
        f"having a resolving test: {detail!r}")
    assert re.search(r"skip", detail, re.I), (
        f"the failure does not say the test is skipped, so the author cannot "
        f"tell what to fix: {detail!r}")


def test_trc_c3_a_real_test_still_resolves(tmp_path, monkeypatch):
    """The control. Without it, a change that failed every declared test would
    satisfy C2 while making the check useless."""
    from compass_pkg.checks import _check_declared_tests_resolve

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_thing.py").write_text("def test_covered():\n    pass\n")
    d = tmp_path / ".compass" / "work" / "demo"
    d.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    # The check resolves declared paths against the project root it finds by
    # walking up from the working directory, so the fixture has to BE that
    # project rather than sit beside it.
    monkeypatch.chdir(tmp_path)
    task = {
        "status": "active",
        "gates": [{"id": "verify.correctness", "status": "pass"}],
        "scenarios": [{"id": "TRC-1", "tests": [
            "tests/test_thing.py::test_covered"]}],
    }
    passed, detail = _check_declared_tests_resolve(task, str(d))
    assert passed, f"an ordinary passing test was refused: {detail!r}"


# ---------------------------------------------------------------------------
# Group E - the ceiling is derived, and an old manifest still reads
# ---------------------------------------------------------------------------

def test_trc_e1_swarm_has_no_invented_ceiling():
    """`swarm` is unbounded in the policy - no number exists to encode. <!-- vocabulary-scan: allow - names the retired shape word this test reads -->

    Nothing in `routing-policy.yml` or `.compass/config.yml` says a fixed
    number for it; the only cap in the policy is RP-CAP-001's
    `max_worktrees: 1`, and the config file states that the worktree cap is
    a routing concern it deliberately does not hold. A configurable-looking
    number frozen into a literal would misreport the day anyone set a real
    cap.
    """
    # The property under test: the unbounded shape must carry no invented
    # number.
    import yaml

    shapes = yaml.safe_load(
        (ROOT / "governance" / "routing-policy.yml").read_text()
    )["route_shapes"]

    assert shapes["full"]["subtask_ceiling"] is None, (
        f"the unbounded shape carries an invented ceiling of "
        f"{shapes['full']['subtask_ceiling']!r}. Unbounded is the honest "
        f"value: the policy states no number, so only a cap can produce one")
    assert shapes["quick-fix"]["subtask_ceiling"] == 1
    assert shapes["regular"]["subtask_ceiling"] == 2


def test_trc_e2_a_cap_still_produces_a_number(tmp_path):
    """The control: unbounded must not mean uncappable."""
    root = _project(tmp_path)          # critical risk -> RP-CAP-001 fires
    subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--verbose", "--issue", "demo",
         "--write"], cwd=str(root), capture_output=True, text=True, timeout=60,
        check=True)
    manifest = yaml.safe_load(
        (root / ".compass" / "work" / "demo" / "manifest.yml").read_text())
    assert manifest["subtask_ceiling"] == 1, manifest.get("subtask_ceiling")


def test_trc_e3_an_old_spine_normalises_to_a_ceiling():
    """A manifest carrying `topology: swarm` and no ceiling must still be <!-- vocabulary-scan: allow - names the retired keys an old manifest carries -->
    readable - ADR-006's tolerant read side - so the old word normalises to
    the ceiling it always implied."""
    from compass_pkg.core import normalize_spine

    for word, expected in (("solo", 1), ("solo-or-pair", 2), ("swarm", None)):
        out = normalize_spine({"task": "old", "topology": word})
        assert "subtask_ceiling" in out, (
            f"an old manifest carrying `topology: {word}` does not normalise to a "
            f"subtask_ceiling, so every reader of the new field sees None")
        assert out["subtask_ceiling"] == expected, (
            f"topology {word!r} normalised to {out['subtask_ceiling']!r}, "
            f"expected {expected!r}")
        assert out.get("orchestration") == word, (
            "normalisation destroyed the recorded word - an archived manifest "
            "keeps what it said, under the current key name")


def test_trc_e4_a_new_spine_is_not_overwritten():
    """The control. A manifest that already carries a ceiling must keep it, or
    normalisation would silently re-derive a number breakdown had refined."""
    from compass_pkg.core import normalize_spine

    out = normalize_spine({"task": "t", "topology": "swarm", "subtask_ceiling": 3})
    assert out["subtask_ceiling"] == 3, out["subtask_ceiling"]
