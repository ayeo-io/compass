"""The check-mutation runner proves each register test can fail.

`tests/mutation_proofs.yml` names a pair of tests for every shipped check,
and `tests/test_mutation_proof_register.py` proves they exist. An
independent review of that register found four of 22 cited tests still
passed with their check disabled: one matched text a passing check also
prints, another passed because a different check failed in its fixture.
`.github/scripts/check_mutation_runner.py` breaks each check in a copy of
the checkout, to always pass and then always fail, and reports any test
that stayed green.

These tests run it on a small project with one check, so each way a test
can fail to prove its check is shown on its own.

Scenario id: CM-1 (issue `check-mutation-runner`).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / ".github" / "scripts" / "check_mutation_runner.py"

CHECKS = '''
def _check_named(task, task_dir):
    if not task.get("name"):
        return False, "the issue has no name"
    return True, "named"
'''

CHECK_CMD = '''
from compass_pkg.checks import _check_named

CHECK_FNS = {"named": _check_named}
'''

TESTS = '''
import pytest
from compass_pkg.check_cmd import CHECK_FNS

check = CHECK_FNS["named"]


def test_an_unnamed_issue_fails():
    assert check({}, None)[0] is False


def test_a_named_issue_passes():
    assert check({"name": "x"}, None)[0] is True


def test_weak_only_looks_at_the_detail():
    # Passes whatever the check decides: "named" or "mutated" both hold.
    assert isinstance(check({}, None)[1], str)


@pytest.mark.skip(reason="never runs")
def test_skipped():
    assert check({}, None)[0] is False


class TestNotCollected:
    def __init__(self):
        pass

    def test_inside(self):
        assert check({}, None)[0] is False
'''


def _project(tmp_path, fails, restores):
    root = tmp_path / "proj"
    (root / "cli" / "compass_pkg").mkdir(parents=True)
    # Like the real package, the fixture loads the bundled PyYAML from
    # `cli/vendor`: a CI runner has no PyYAML installed.
    shutil.copytree(ROOT / "cli" / "vendor", root / "cli" / "vendor")
    (root / "cli" / "compass_pkg" / "__init__.py").write_text(
        "import os, sys\n"
        "sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),"
        " os.pardir, 'vendor'))\n")
    (root / "cli" / "compass_pkg" / "checks.py").write_text(CHECKS)
    # The runner reads the register through `compass_pkg.core.yaml`, the
    # one way this repository reads YAML.
    (root / "cli" / "compass_pkg" / "core.py").write_text("import yaml  # noqa: F401\n")
    (root / "cli" / "compass_pkg" / "check_cmd.py").write_text(CHECK_CMD)
    (root / "tests").mkdir()
    (root / "tests" / "conftest.py").write_text(
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'cli'))\n")
    (root / "tests" / "test_named.py").write_text(TESTS)
    (root / "tests" / "mutation_proofs.yml").write_text(
        f"- check: named\n  broken: an issue with no name\n"
        f"  fails: tests/test_named.py::{fails}\n"
        f"  restores: tests/test_named.py::{restores}\n")
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.email=t@example.com", "-c", "user.name=t",
                  "commit", "-q", "-m", "base"]):
        subprocess.run(["git", *args], cwd=root, check=True)
    return root


def _run(root):
    return subprocess.run([sys.executable, str(RUNNER), "--root", str(root)],
                          capture_output=True, text=True, timeout=300)


def _tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file() and ".git" not in p.parts}


def test_cm_1_proofs_that_go_red_both_ways_pass(tmp_path):
    root = _project(tmp_path, "test_an_unnamed_issue_fails",
                    "test_a_named_issue_passes")
    before = _tree(root)
    result = _run(root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "named: fails with the check always passing: red" in result.stdout
    assert "named: restores with the check always failing: red" in result.stdout
    assert _tree(root) == before, "the runner changed the checkout"


@pytest.mark.parametrize("weak", ["test_weak_only_looks_at_the_detail",
                                  "test_skipped",
                                  "TestNotCollected::test_inside"])
def test_cm_1_a_test_that_cannot_show_its_check_works_is_named(tmp_path, weak):
    root = _project(tmp_path, weak, "test_a_named_issue_passes")
    result = _run(root)
    assert result.returncode != 0, result.stdout
    assert f"named: `fails` (tests/test_named.py::{weak})" in result.stdout, result.stdout


def test_cm_1_a_check_missing_from_the_registry_is_named(tmp_path):
    root = _project(tmp_path, "test_an_unnamed_issue_fails",
                    "test_a_named_issue_passes")
    (root / "tests" / "mutation_proofs.yml").write_text(
        "- check: gone\n  broken: x\n  fails: tests/test_named.py::test_skipped\n"
        "  restores: tests/test_named.py::test_skipped\n")
    result = _run(root)
    assert result.returncode != 0
    assert "gone: no function" in result.stdout, result.stdout
