"""`/compass:go`: one command for the ordinary path, and a count of the
interruptions an issue took.

A new user had to know that `/compass:assess` starts an issue and
`/compass:quick-fix` is the light path. `/compass:go <what you want>` runs
init, assesses, shows a three-line decision view and continues into the
first stage. Each hook block and each failing `compass check` appends a
line to `.compass/interruptions.log`, and `compass retro` reports the
totals, so "fewer interruptions" can be measured, not claimed.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "tests"))
from test_refusal_registry import _hook, install  # noqa: E402,F401
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


# --- ONE-1: the command --------------------------------------------------------

def test_go_is_a_command_that_assesses_shows_the_view_and_continues():
    text = (ROOT / "commands" / "go.md").read_text(encoding="utf-8")
    for step in ("compass init", "compass quick-fix start",
                 "compass approach summary --issue <slug>", "/compass:assess",
                 "--no-commit"):
        assert step in text, step
    assert len(text.split()) < 700, len(text.split())


# --- ONE-2: the three-line decision view ----------------------------------------

@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=root, check=True)
    return root


def _run(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True)


def test_the_decision_view_is_three_lines(repo):
    r = _run(repo, "quick-fix", "start", "greeting",
             "--risk", "trivial - one string", "--familiarity",
             "brownfield-mapped - the file and its test exist",
             "--size", "atomic - one line", "--intent", "the greeting is right",
             "--scenario", "Given the greeting, when read, then it says hello",
             "--test", "tests/test_greeting.py")
    assert r.returncode == 0, r.stdout + r.stderr
    view = _run(repo, "approach", "summary", "--issue", "greeting")
    assert view.returncode == 0, view.stderr
    lines = view.stdout.strip().splitlines()
    assert len(lines) == 3, lines
    assert lines[0].startswith("Approach: quick fix"), lines
    assert lines[1].startswith("Gates: ") and "verify.correctness" in lines[1], lines
    assert lines[2].startswith("Writes: ") and ".compass/work/greeting/" in lines[2], lines


# --- ONE-3 and ONE-4: interruptions are counted --------------------------------

def _log(root):
    p = root / ".compass" / "interruptions.log"
    return p.read_text().splitlines() if p.exists() else []


def _counted(root, slug, kind):
    return sum(1 for line in _log(root) if line.split("\t")[1:] == [slug, kind])


def test_a_hook_block_is_counted_in_the_log_not_the_manifest(install):
    manifest = install / ".compass" / "work" / "matrix" / "manifest.yml"
    before = manifest.read_bytes()
    (install / ".compass" / "work" / "matrix" / ".red").unlink()
    first = _hook(install, "src/app.py")
    second = _hook(install, "src/app.py")
    assert first.returncode == 2 and second.returncode == 2, first.stderr
    assert _counted(install, "matrix", "hook_blocks") == 2, _log(install)
    assert manifest.read_bytes() == before


def test_an_allowed_edit_is_not_counted(install):
    result = _hook(install, "src/app.py")
    assert result.returncode == 0, result.stderr
    assert _log(install) == []


def test_a_task_dir_from_the_environment_is_not_counted(install, tmp_path, monkeypatch):
    """The hook clears TASK_DIR itself. With no issue folder at all, it
    refuses before it resolves an issue, and a TASK_DIR exported by the
    caller, naming a real issue folder elsewhere, must not be counted."""
    import shutil
    victim = tmp_path / "other" / ".compass" / "work" / "victim"
    victim.mkdir(parents=True)
    shutil.rmtree(install / ".compass" / "work")
    monkeypatch.setenv("TASK_DIR", str(victim))
    result = _hook(install, "src/app.py")
    assert result.returncode == 2, result.stderr
    assert not (tmp_path / "other" / ".compass" / "interruptions.log").exists()
    assert _log(install) == []


def _start(root, slug="greeting"):
    return _run(root, "quick-fix", "start", slug,
                "--risk", "trivial - one string", "--familiarity",
                "brownfield-mapped - the file and its test exist",
                "--size", "atomic - one line", "--intent", "the greeting is right",
                "--scenario", "Given the greeting, when read, then it says hello",
                "--test", "tests/test_greeting.py")


def test_a_failing_check_is_counted_and_the_issue_folder_is_untouched(repo):
    _start(repo)
    work = repo / ".compass" / "work" / "greeting"

    # The count goes to the interruptions log. `compass check` also files its
    # verdicts in the generation's results.yml by design; nothing else moves.
    def files():
        return {p: p.read_bytes() for p in work.rglob("*")
                if p.is_file() and not (p.name == "results.yml" and "generations" in p.parts)}

    before = files()
    r = _run(repo, "check", "--issue", "greeting")
    assert r.returncode != 0, r.stdout
    assert _counted(repo, "greeting", "check_failures") == 1, _log(repo)
    assert files() == before


def test_a_ci_sweep_does_not_count(repo):
    _start(repo)
    _run(repo, "ci")
    assert _counted(repo, "greeting", "check_failures") == 0, _log(repo)


# --- ONE-5: retro reports them ----------------------------------------------------

def test_retro_reports_the_interruptions(repo):
    _start(repo)
    _run(repo, "check", "--issue", "greeting")
    log = repo / ".compass" / "interruptions.log"
    with log.open("a") as fh:
        fh.write("not a valid line\n")
    r = _run(repo, "retro")
    assert r.returncode == 0, r.stderr
    assert "interruptions" in r.stdout.lower(), r.stdout
    assert "1 check failure" in r.stdout, r.stdout


# --- GC-1: go does not stop at assess's confirmation (issue `go-confirms-on-the-heavier-route`) ----------------

def test_gc_1_go_and_assess_agree_that_go_does_not_wait_to_confirm():
    """`/compass:go` hands a heavier route to `/compass:assess` from step 4.
    Assess step 7 asks for a confirmation; go says not to stop. Both texts
    must say the same thing: under go, the summary already shown is the
    confirmation."""
    go = (ROOT / "commands" / "go.md").read_text(encoding="utf-8")
    assess = (ROOT / "commands" / "assess.md").read_text(encoding="utf-8") \
        + (ROOT / "approaches" / "assess-procedure.md").read_text(encoding="utf-8")
    assert "steps 4 to 6" in go, "go must name the assess steps it runs"
    assert "step 7" in go and "do not wait" in go.lower(), \
        "go must say it does not wait at assess step 7"
    step7 = assess[assess.index("7. **Confirm.**"):assess.index("## Voice")]
    assert "/compass:go" in step7, "assess step 7 must say what go does"
