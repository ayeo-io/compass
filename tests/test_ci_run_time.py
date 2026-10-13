"""Tests for the pieces of the CI run-time work that are not workflow structure.

Three things are checked here, all without the network or GitHub:

- the compat test module still collects the node ids it collected before its
  setup was reworked, so no test was lost or renamed;
- the pytest options the CI jobs pass print a test count and the slowest
  tests;
- the command that measures a CI run reads the JSON `gh run view --json jobs`
  prints and reports the figures it holds.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "ci-run-time"
MINUTES = ROOT / "scripts" / "ci-run-minutes.py"


def test_crt_18_compat_node_ids_unchanged():
    """A rework of the compat setup must not add, drop or rename a test: the
    node ids collected now are the ones recorded before the rework."""
    recorded = [line.strip() for line in
                (FIXTURES / "compat-node-ids.txt").read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")]
    assert recorded, "the recorded node ids are empty"
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-o", "addopts=",
         "-p", "no:cacheprovider", "tests/test_compat_configurations.py"],
        cwd=ROOT, capture_output=True, text=True, env=env, timeout=120)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    now = [line.strip() for line in run.stdout.splitlines()
           if line.startswith("tests/test_compat_configurations.py::")]
    assert now == recorded, (
        "node ids changed. Lost: %s. Added: %s." % (
            sorted(set(recorded) - set(now))[:10], sorted(set(now) - set(recorded))[:10]))


def _minutes(*args, stdin=None):
    return subprocess.run([sys.executable, str(MINUTES), *args], input=stdin,
                          capture_output=True, text=True, timeout=30)


def test_crt_20_measuring_command_reads_a_run():
    """The fixture has known times: the first job starts at 10:00:03 and the
    last ends at 10:10:40, so the wall time is 637 seconds (10.6 minutes).
    The job minutes are 3.5, 2.5, 8.0, 7.5, 9.5 and 1.0, which sum to 32.0.
    The wall time is shorter than the sum because the jobs overlap, so a
    command that confused the two would print the wrong figure for one."""
    fixture = FIXTURES / "run-jobs.json"
    for run in (_minutes(str(fixture)), _minutes(stdin=fixture.read_text(encoding="utf-8"))):
        assert run.returncode == 0, run.stderr
        lines = run.stdout.splitlines()
        assert lines == [
            "already-tested: skipped",
            "checks: 3.5 minutes",
            "count: 2.5 minutes",
            "shard (0): 8.0 minutes",
            "shard (1): 7.5 minutes",
            "serial: 9.5 minutes",
            "self-check: 1.0 minutes",
            "Wall time: 10.6 minutes",
            "Sum of job minutes: 32.0",
        ], run.stdout


def test_crt_20_measuring_command_refuses_what_it_cannot_read(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    run = _minutes(str(bad))
    assert run.returncode != 0 and run.stdout == ""
    assert "cannot read" in run.stderr


# --- the options CI passes to pytest print counts and the slowest tests -------

WORKFLOW = ROOT / ".github" / "workflows" / "compass.yml"

THREE_TESTS = '''\
import time

import pytest
{mark}

def test_fast_one():
    assert True


def test_fast_two():
    assert True


def test_sleeps_a_little():
    time.sleep(0.2)
'''


def _pytest_options(job_name):
    """The pytest arguments a job's test step passes, as a list, with the
    place where the job names its test files left as the one token `<tests>`.

    The step is the one that runs pytest and does not only collect."""
    import shlex

    import yaml
    job = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"][job_name]
    runs = [step["run"] for step in job["steps"]
            if "-m pytest" in step.get("run", "") and "--collect-only" not in step["run"]]
    assert len(runs) == 1, f"job {job_name} has {len(runs)} steps that run the tests"
    line = next(l for l in runs[0].splitlines() if "-m pytest" in l)
    tokens = shlex.split(line.split("-m pytest", 1)[1])
    return ["<tests>" if t in ("tests/", "${files[@]}") else t for t in tokens]


def _run_options(options, tmp_path, serial):
    """Run pytest with `options` and this project's pytest.ini over three
    passing tests, one of which sleeps 0.2 seconds."""
    folder = tmp_path / ("serial" if serial else "parallel")
    folder.mkdir()
    mark = "\npytestmark = pytest.mark.serial\n" if serial else ""
    (folder / "test_three.py").write_text(THREE_TESTS.format(mark=mark), encoding="utf-8")
    # -n auto starts a worker per CPU, and a shard job already uses every CPU
    # for its own run. Two workers prove the same thing: the counts line and the
    # durations heading survive xdist.
    run_options = ["2" if t == "auto" else t for t in options]
    changed = [(a, b) for a, b in zip(options, run_options) if a != b]
    assert changed in ([], [("auto", "2")]), changed
    run_options = [str(folder) if t == "<tests>" else t for t in run_options]
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-c", str(ROOT / "pytest.ini"), *run_options],
        cwd=tmp_path, capture_output=True, text=True, env=env, timeout=120)


def test_crt_19_ci_prints_counts_and_durations(tmp_path):
    import re
    for job, serial, uses_workers in (("shard", False, True), ("serial", True, False)):
        options = _pytest_options(job)
        assert "<tests>" in options, (job, options)
        assert any(t.startswith("--durations=") for t in options), (job, options)
        assert ("-n" in options) is uses_workers, (job, options)
        run = _run_options(options, tmp_path, serial)
        output = run.stdout + run.stderr
        assert run.returncode == 0, (job, output[-2000:])
        assert "3 passed" in output, (job, output[-2000:])
        assert re.search(r"slowest \d+ durations", output), (job, output[-2000:])
        assert "test_sleeps_a_little" in output, (job, output[-2000:])
