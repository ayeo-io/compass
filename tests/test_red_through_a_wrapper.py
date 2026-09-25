"""A pytest red is judged by pytest's report however pytest is started.

`compass tdd-red` sets `--junitxml` through `PYTEST_ADDOPTS`, which pytest
reads wherever it runs: called directly, as `py.test`, or inside a
`bash -c` string or a `make` target. So a wrapper cannot turn a run in which
no test failed into a red. A command that writes no report is a runner
Compass does not recognise; it is judged by its exit code, and the record
says so with `red_kind: exit-code`.

Scenario ids: DSW-1 to DSW-3, in the delivery approach of issue
`red-through-a-shell-wrapper`.
"""
from __future__ import annotations

import json
import shutil

import pytest

SLUG = "wrapped"
BODY = {"assessment": {"risk": "contained", "familiarity": "greenfield",
                       "size": "small", "goal": "delivery",
                       "role": "engineer", "labels": []},
        "scenarios": []}
FAIL = "def test_go():\n    assert 1 == 2\n"
SETUP_ERROR = ("import pytest\n\n@pytest.fixture\ndef boom():\n"
               "    raise RuntimeError('setup')\n\n"
               "def test_go(boom):\n    assert True\n")


@pytest.fixture
def red(make_task, run_cli, project):
    """Write a test file, then run tdd-red with the given command words."""
    task_dir = make_task(SLUG, BODY)
    (project / "tests_red").mkdir()

    def _run(test_body, *command):
        (project / "tests_red" / "test_thing.py").write_text(test_body)
        result = run_cli("tdd-red", "--issue", SLUG, "--", *command, timeout=60)
        path = task_dir / "evidence" / "red.json"
        record = json.loads(path.read_text()) if path.exists() else None
        return result, record
    return _run


PYTEST = "python3 -m pytest -q -p no:cacheprovider tests_red/test_thing.py"


@pytest.mark.skipif(shutil.which("py.test") is None, reason="no py.test on PATH")
def test_dsw_1_py_test_gets_the_pytest_rule(red):
    result, record = red(SETUP_ERROR, "py.test", "-q", "-p", "no:cacheprovider",
                         "tests_red/test_thing.py")
    assert result.returncode != 0, result.combined
    assert "no failed test" in result.combined.lower(), result.combined
    assert record is None


def test_dsw_1_py_test_is_recognised_as_pytest():
    from compass_pkg.tdd import _is_pytest_command
    assert _is_pytest_command(["py.test", "tests/"])
    assert _is_pytest_command(["/usr/local/bin/py.test"])


def test_dsw_2_a_wrapped_run_with_no_failure_is_refused(red):
    result, record = red(SETUP_ERROR, "bash", "-c", PYTEST + " | tail -5")
    assert result.returncode != 0, result.combined
    assert "no failed test" in result.combined.lower(), result.combined
    assert record is None


def test_dsw_2_a_wrapped_genuine_failure_is_a_red(red):
    result, record = red(FAIL, "bash", "-c", PYTEST + " | tail -5")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "failure"


def test_dsw_3_a_runner_that_writes_no_report_is_marked_exit_code(red):
    result, record = red(FAIL, "false")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "exit-code"
    assert "exit code only" in result.combined.lower(), result.combined
