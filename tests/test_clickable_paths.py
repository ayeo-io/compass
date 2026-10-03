"""Every path the CLI prints opens with one click: GitHub issue #291.

Paths are printed relative to the project root, as `path:line` where the
line is known, and piped output carries no escape code.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))
from compass_pkg import render  # noqa: E402

ESC = "\x1b"


def _compass(root: Path, *args):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    env["COMPASS_HYPERLINKS"] = "1"
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root, env=env,
                          capture_output=True, text=True)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    (root / "tests").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "tests" / "test_x.py").write_text("def test_x():\n    assert False\n")
    r = _compass(root, "quick-fix", "start", "demo", "--risk", "trivial - x",
                 "--familiarity", "brownfield-mapped - x", "--size", "small - x",
                 "--intent", "INT-1", "--scenario", "Given x, then y",
                 "--test", "tests/test_x.py")
    assert r.returncode == 0, r.stdout + r.stderr
    return root


def _no_absolute(root: Path, r) -> None:
    out = r.stdout + r.stderr
    for form in {str(root), os.path.realpath(root)}:
        assert form not in out, f"absolute path printed:\n{out}"


def test_the_verbs_print_no_absolute_project_path(project):
    """CP-A: no absolute project path. CP-D: no escape code in piped
    output. The escape-code half pins behaviour that already held before
    #291; it fails when an escape code is planted in say()'s output."""
    runs = [
        ("tdd-red", "--scenario", "TRC-001", "--", sys.executable, "-m", "pytest", "-q",
         "-p", "no:cacheprovider", "tests/test_x.py"),
    ]
    for args in runs:
        r = _compass(project, *args)
        _no_absolute(project, r)
        assert ESC not in r.stdout + r.stderr
    (project / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")
    for args in [
        ("tdd-green", "--scenario", "TRC-001", "--", sys.executable, "-m", "pytest", "-q",
         "-p", "no:cacheprovider", "tests/test_x.py"),
        ("flow", "--digest"),
        ("adr", "new", "a-decision"),
        ("issue", "lint", "--issue", "demo"),
        ("ci",),
    ]:
        r = _compass(project, *args)
        _no_absolute(project, r)
        assert ESC not in r.stdout + r.stderr, args


def test_tdd_names_the_scenario_line(project):
    """CP-B."""
    ac = next(project.glob("docs/compass/*-demo/acceptance-criteria.md"), None)
    if ac is None:
        ac = project / "docs" / "compass" / "x-demo" / "acceptance-criteria.md"
        ac.parent.mkdir(parents=True)
    lines = ac.read_text().splitlines() if ac.exists() else ["# Acceptance criteria", ""]
    lines += ["", "| Id | Criterion |", "|---|---|", "| TRC-001 | Given x, then y |"]
    ac.write_text("\n".join(lines) + "\n")
    line = len(lines)
    m = project / ".compass" / "work" / "demo" / "manifest.yml"
    import yaml
    data = yaml.safe_load(m.read_text())
    rel = str(ac.relative_to(project))
    arts = [a for a in data.get("artifacts") or [] if a.get("kind") != "acceptance-criteria"]
    arts.append({"id": "ART-ACCEPTANCE_CRITERIA", "kind": "acceptance-criteria",
                 "status": "draft", "path": rel})
    data["artifacts"] = arts
    m.write_text(yaml.safe_dump(data, sort_keys=False))
    r = _compass(project, "tdd-red", "--scenario", "TRC-001", "--", sys.executable, "-m",
                 "pytest", "-q", "-p", "no:cacheprovider", "tests/test_x.py")
    assert f"{rel}:{line}" in r.stdout, r.stdout


# --- review round 1: the root is replaced only where it starts a path ----------

@pytest.mark.parametrize("root, text, expected", [
    ("/a/proj", "evidence : /a/proj/.compass/work/x.json",
     "evidence : .compass/work/x.json"),
    ("/a/proj", "see `/a/proj/docs/a.md`", "see `docs/a.md`"),
    ("/compass", "https://github.com/jed72/compass/issues/291",
     "https://github.com/jed72/compass/issues/291"),
    ("/app", "/usr/src/app/main.py", "/usr/src/app/main.py"),
    ("/", "https://example.com/x", "https://example.com/x"),
    ("/a/proj", "`/a/proj/`", "`/a/proj/`"),
    ("/a/proj", "/a/project-x/file.md", "/a/project-x/file.md"),
    ("/s/mirror", "read /s/mirror$R/brief.md", "read /s/mirror$R/brief.md"),
])
def test_relative_paths_touches_only_paths_under_the_root(root, text, expected):
    assert render.relative_paths(text, root) == expected


# --- error messages and the Read line (#293) ------------------------------------

def test_an_error_names_a_project_file_relatively(project):
    import shutil
    shutil.rmtree(project / ".compass" / "work" / "demo" )
    (project / ".compass" / "work" / "demo").mkdir()
    r = _compass(project, "issue", "lint", "--issue", "demo")
    assert r.returncode != 0
    _no_absolute(project, r)
    assert ".compass/work/demo" in r.stdout + r.stderr


def test_approach_evaluate_reads_a_relative_path(project):
    # The Read line names the approach record when it sits beside the manifest.
    (project / ".compass" / "work" / "demo" / "delivery-approach.md").write_text("# x\n")
    r = _compass(project, "approach", "evaluate", "--issue", "demo")
    assert "Read" in r.stdout, r.stdout
    _no_absolute(project, r)
