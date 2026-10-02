"""A scenario title that would break a check on the living spec is refused
when it is recorded: the titles-checked-before-ship issue, GitHub issue #283.

`compass ship-commit` copies scenario titles into docs/system-spec.md after
the suite has run, so a title the spec's checks reject used to pass locally
and fail in CI (#224, #281).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"


def _compass(root: Path, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True)


def _start(root: Path, title: str, slug: str = "demo"):
    return _compass(root, "quick-fix", "start", slug, "--risk", "trivial - x",
                    "--familiarity", "brownfield-mapped - x", "--size", "small - x",
                    "--intent", "INT-1", "--scenario", title, "--test", "tests/t.py")


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "docs").mkdir()
    (root / "docs" / "real.md").write_text("x\n")
    return root


@pytest.fixture
def with_evals(project):
    (project / "evals" / "scenarios" / "cmp-edge-case").mkdir(parents=True)
    (project / "evals" / "scenarios" / "cmp-edge-case" / "scenario.yml").write_text("x: 1\n")
    (project / "evals" / "judge.py").write_text(
        'BEHAVIOURS = {\n    "assessed_before_first_edit": "x",\n}\n')
    return project


def test_a_plain_title_is_recorded(project):
    r = _start(project, "Given a request over the limit, then it is refused")
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_title_naming_a_missing_path_is_refused(project):
    r = _start(project, "Given docs/missing.md, then it is read")
    assert r.returncode != 0
    assert "docs/missing.md" in r.stdout + r.stderr
    assert not (project / ".compass" / "work" / "demo").exists(), "nothing is written"


def test_a_title_naming_a_real_path_is_recorded(project):
    r = _start(project, "Given docs/real.md, then it is read")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("title", [
    "Given the cmp-edge-case run, then it passes",
    "Given assessed_before_first_edit, then it is judged",
])
def test_an_eval_scenario_or_behaviour_id_is_refused(with_evals, title):
    r = _start(with_evals, title)
    assert r.returncode != 0, r.stdout
    assert "eval" in (r.stdout + r.stderr).lower()


def test_without_evals_the_same_words_are_recorded(project):
    r = _start(project, "Given the cmp-edge-case run, then it passes")
    assert r.returncode == 0, r.stdout + r.stderr


def test_scenario_add_refuses_too(project):
    assert _start(project, "Given x, then y").returncode == 0
    r = _compass(project, "scenario", "add", "TRC-002", "--intent", "INT-1",
                 "--title", "Given a/missing/file.yml, then y", "--issue", "demo")
    assert r.returncode != 0
    assert "a/missing/file.yml" in r.stdout + r.stderr
