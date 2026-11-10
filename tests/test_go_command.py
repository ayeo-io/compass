"""`/compass:go`: one command for the ordinary path, and a count of the
interruptions an issue took.

A new user had to know that `/compass:assess` starts an issue and
`/compass:quick-fix` is the light path. `/compass:go <what you want>` runs
init, assesses, shows a three-line decision view and follows the `next:`
line of each verb through the four stages of the path. Each hook block and each failing `compass check` appends a
line to `.compass/interruptions.log`, and `compass issue diagnose` reports
them, so "fewer interruptions" can be measured, not claimed.
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
    # ADR-099: `start` makes `.compass/` itself, `finish` writes the record and
    # commits once a person approves, so go names two commands and the one
    # request that asks for approval before code.
    for step in ("compass quick-fix start", "compass quick-fix finish",
                 "compass evidence request --checkpoint", "/compass:approve",
                 "/compass:assess", "`next:`"):
        assert step in text, step
    assert len(text.split()) < 350, len(text.split())


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
    view = _run(repo, "approach", "show", "--issue", "greeting")
    assert view.returncode == 0, view.stderr
    lines = view.stdout.strip().splitlines()
    assert len(lines) == 3, lines
    # The four-stage path (ADR-092): the one approach and the assessment, then the
    # evidence the change owes, in place of the 8.x approach name and gate list.
    assert lines[0].startswith("Approach: delivery (risk trivial"), lines
    assert lines[1].startswith("Evidence: ") and "correctness" in lines[1], lines
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


# --- GC-1: go does not stop at assess's confirmation (issue `go-confirms-on-the-heavier-route`) ----------------

def test_gc_1_go_and_assess_agree_that_go_does_not_wait_to_confirm():
    """`/compass:go` runs the whole path itself (ADR-092). Since ADR-099 it
    has no confirmation step, and stops only where a `next:` line asks for a
    person's approval. `/compass:assess` runs the same five steps and the
    same stop."""
    go = _flat(ROOT / "commands" / "go.md")
    assess = _flat(ROOT / "commands" / "assess.md")
    assert "confirm" not in go.lower(), "go must not wait for a confirmation"
    stop = "When its `next:` line asks for a person's approval, stop."
    assert stop in go, "go must say the one place it stops"
    assert stop in assess, "assess must stop in the same place as go"


def _flat(path: Path) -> str:
    """File text with each run of whitespace folded to one space, so a
    phrase wrapped across two lines still matches."""
    return " ".join(path.read_text(encoding="utf-8").split())


def test_go_command_names_the_architect_trigger_conditions():
    """The specify stage of commands/go.md names the three conditions that
    call for the architect's perspective: the `public-api` label, a service in
    architecture/relations.md, a `lens_trigger_tag` in
    architecture/invariants.yml (`TRC-001`). Moved here from
    `test_architect_lens.py` when `/compass:consult` was removed (ADR-093)."""
    go = _flat(ROOT / "commands" / "go.md")
    for term in ("public-api", "architecture/relations.md", "lens_trigger_tag"):
        assert term in go, f"commands/go.md does not name the trigger: {term}"


def test_go_command_takes_the_architect_perspective_before_the_scenarios():
    """commands/go.md takes the architect's perspective first, and writes
    architecture-notes.md, before the stage writes scenarios (`TRC-001`)."""
    go = _flat(ROOT / "commands" / "go.md").lower()
    first = go.find("take the architect's perspective first")
    notes = go.find("write `architecture-notes.md`")
    scenarios = go.find("before you write the scenarios")
    assert first != -1, "commands/go.md does not take the architect's perspective first"
    assert notes > first, "commands/go.md does not write architecture-notes.md after it"
    assert scenarios > notes, "commands/go.md does not write the notes before the scenarios"
