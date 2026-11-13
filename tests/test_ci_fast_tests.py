"""The `fast-tests` job and the command that lists its test files.

On a pull request, `.github/workflows/compass.yml` runs the test files the
pull request changes and a fixed set of house-rule test files, and the
merge queue runs the whole suite once (ayeo-io/compass-delivery#362).
`scripts/ci-fast-tests.py` lists the files. These tests run it in
temporary git repositories, and run the job's serial step with a stand-in
`python3`.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ci-fast-tests.py"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_expr  # noqa: E402


def _module():
    spec = importlib.util.spec_from_file_location("ci_fast_tests", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HOUSE_RULES = _module().HOUSE_RULES


def _job() -> dict:
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "compass.yml")
                         .read_text(encoding="utf-8"))
    return doc["jobs"]["fast-tests"]


def _step(job: dict, name: str) -> dict:
    found = [s for s in job["steps"] if s.get("name") == name]
    assert len(found) == 1, [s.get("name") for s in job["steps"]]
    return found[0]


def _git(cwd: Path, *args: str) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          env=env, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A checkout with this pytest.ini, the house-rule files and two other
    test files at the base commit."""
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "pytest.ini").write_text((ROOT / "pytest.ini").read_text())
    for rel in (*HOUSE_RULES, "tests/test_kept.py", "tests/test_gone.py"):
        (root / rel).write_text("def test_x():\n    pass\n")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "base")
    return root, _git(root, "rev-parse", "HEAD")


def _run(root: Path, base: str, head: str):
    return subprocess.run([sys.executable, str(SCRIPT), "--base", base,
                           "--head", head, "--root", str(root)],
                          capture_output=True, text=True, timeout=60)


def test_mq_2_lists_the_house_rules_and_the_changed_test_files(repo):
    root, base = repo
    (root / "tests" / "test_new.py").write_text("def test_y():\n    pass\n")
    (root / "tests" / "sub").mkdir()
    (root / "tests" / "sub" / "test_deep.py").write_text("def test_z():\n    pass\n")
    (root / "tests" / "helper.py").write_text("X = 1\n")
    (root / "cli.py").write_text("X = 1\n")
    (root / HOUSE_RULES[0]).write_text("def test_x():\n    assert True\n")
    (root / "tests" / "test_gone.py").unlink()
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "head")
    head = _git(root, "rev-parse", "HEAD")

    r = _run(root, base, head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.splitlines() == sorted(
        [*HOUSE_RULES, "tests/test_new.py", "tests/sub/test_deep.py"])
    assert "Test files this change edits: 2" in r.stderr, r.stderr
    assert f"House-rule test files: {len(HOUSE_RULES)}" in r.stderr, r.stderr


def test_mq_2_a_change_with_no_test_file_runs_the_house_rules_only(repo):
    root, base = repo
    (root / "cli.py").write_text("X = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "head")
    r = _run(root, base, _git(root, "rev-parse", "HEAD"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.splitlines() == sorted(HOUSE_RULES)


@pytest.mark.parametrize("base", ["", "0" * 40, "1234567890abcdef" * 2 + "12345678",
                                  "--output=x"])
def test_mq_2_refuses_when_the_change_cannot_be_computed(repo, base):
    """Running fewer tests than asked is the one wrong answer, so a missing
    base fails the job instead of running the house rules alone."""
    root, head = repo
    r = _run(root, base, head)
    assert r.returncode == 2, r.stdout + r.stderr
    assert r.stdout == ""
    assert "ci-fast-tests.py:" in r.stderr


def test_mq_2_refuses_when_a_house_rule_file_is_missing(repo):
    root, base = repo
    (root / HOUSE_RULES[-1]).unlink()
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "head")
    r = _run(root, base, _git(root, "rev-parse", "HEAD"))
    assert r.returncode == 2 and r.stdout == "", r.stdout + r.stderr
    assert HOUSE_RULES[-1] in r.stderr, r.stderr


def test_mq_2_the_house_rules_are_real_and_fast():
    """Each house-rule file is a test file of this checkout, and together
    they took under three minutes of test time in the recorded CI run, so
    the fast job stays near its target of a few minutes."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    r = _run(ROOT, head, head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.splitlines() == sorted(HOUSE_RULES)
    seconds = json.loads((ROOT / "tests" / "ci-durations.json").read_text())["seconds"]
    assert sum(seconds.get(f, 0.0) for f in HOUSE_RULES) < 180
    assert "tests/test_writing_style.py" not in HOUSE_RULES


def test_mq_3_the_job_runs_the_listed_files():
    job = _job()
    # Room for a release, whose changed test files are most of the suite: as
    # long as one full-suite shard.
    assert job["timeout-minutes"] <= 45
    assert job["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert job["steps"][0]["with"]["fetch-depth"] == 0
    listing = _step(job, "List the test files this pull request runs")
    assert shlex.split(listing["run"]) == [
        "python3", "scripts/ci-fast-tests.py", "--base", "$BASE_SHA", "--head",
        "$HEAD_SHA", ">", "$RUNNER_TEMP/fast-files.txt"]
    pr = {"event": {"pull_request": {"base": {"sha": "b" * 40},
                                     "head": {"sha": "h" * 40}}}}
    assert ci_expr.render(listing["env"]["BASE_SHA"], github=pr) == "b" * 40
    assert ci_expr.render(listing["env"]["HEAD_SHA"], github=pr) == "h" * 40
    parallel = _step(job, "Run their tests on parallel workers")["run"]
    assert ('python3 -m pytest -p xdist.plugin -n auto -m "not serial" "${files[@]}"'
            in parallel), parallel
    serial = _step(job, "Run their tests marked serial alone")
    assert 'python3 -m pytest -m serial "${files[@]}"' in serial["run"]
    assert serial.get("shell") == "bash"


def _bash_with_mapfile():
    """A bash of version 4 or later, as on the runner. macOS ships 3.2."""
    for bash in ("bash", "/opt/homebrew/bin/bash", "/usr/local/bin/bash"):
        r = subprocess.run([bash, "-c", "mapfile -t x < /dev/null"],
                           capture_output=True) if shutil.which(bash) else None
        if r is not None and r.returncode == 0:
            return bash
    return None


@pytest.mark.parametrize("pytest_exit,step_exit", [(0, 0), (5, 0), (1, 1), (2, 2)])
def test_mq_3_the_serial_step_passes_when_no_serial_test_is_listed(
        tmp_path, pytest_exit, step_exit):
    """pytest exits 5 when the listed files hold no serial test; any other
    failure fails the step."""
    bash = _bash_with_mapfile()
    if bash is None:
        pytest.skip("no bash of version 4 or later here; the runner has one")
    step = _step(_job(), "Run their tests marked serial alone")
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "python3").write_text(f"#!/bin/sh\nexit {pytest_exit}\n")
    (stub / "python3").chmod(0o755)
    (tmp_path / "fast-files.txt").write_text("tests/test_a.py\n")
    env = dict(os.environ, PATH=f"{stub}{os.pathsep}{os.environ['PATH']}",
               RUNNER_TEMP=str(tmp_path))
    r = subprocess.run([bash, "-e", "-o", "pipefail", "-c", step["run"]],
                       env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == step_exit, r.stdout + r.stderr
