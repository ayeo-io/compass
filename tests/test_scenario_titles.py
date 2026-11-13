"""A scenario title that would break a check on the living spec is refused
when it is recorded: the titles-checked-before-ship issue, GitHub issue #283.

Before 9.0.0 `compass ship-commit` copied scenario titles into the living
spec after the suite had run, so a title the spec's checks rejected used to
pass locally and fail in CI (#224, #281). The release line and the board
still print titles, so the guard stays (ADR-091).
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
    (project / "evals" / "scenarios" / "zz-made-up-run").mkdir(parents=True)
    (project / "evals" / "scenarios" / "zz-made-up-run" / "scenario.yml").write_text("x: 1\n")
    (project / "evals" / "judge.py").write_text(
        'BEHAVIOURS = {\n    "zz_made_up_behaviour": "x",\n}\n')
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
    "Given the zz-made-up-run run, then it passes",
    "Given zz_made_up_behaviour, then it is judged",
])
def test_a_project_eval_id_in_a_title_is_recorded(with_evals, title):
    """A project's `evals/` folder is not a Compass concept since the harness
    moved to sdd-bench (ADR-093), so a title that names one of its ids is
    recorded like any other."""
    r = _start(with_evals, title)
    assert r.returncode == 0, r.stdout + r.stderr


def test_scenario_add_refuses_too(project):
    assert _start(project, "Given x, then y").returncode == 0
    r = _compass(project, "scenario", "add", "TRC-002", "--intent", "INT-1",
                 "--title", "Given a/missing/file.yml, then y", "--issue", "demo")
    assert r.returncode != 0
    assert "a/missing/file.yml" in r.stdout + r.stderr
