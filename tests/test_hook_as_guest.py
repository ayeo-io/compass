"""A repository that never opted into Compass never hears from it.

Installed at user scope - the default marketplace path - `hooks/pre-tool.sh`
runs in every repository on the machine. In one with no `.compass/` it refused
every Write, Edit and Bash write to a code path, and told the user to start
Claude Code inside the project. Someone trying Compass on one project lost the
ability to edit code in every other one.

`.compass/` is the opt-in, and since `init-is-the-opt-in` only `compass init`
creates it - run by the five entry points, so it appears the moment a user runs
a Compass command deliberately. That is what makes silence safe here: a
repository with no `.compass/` has genuinely never been asked to use Compass.

Fail-closed behaviour inside an opted-in project is unchanged.

Scenario ids: HAG-A1, HAG-A2, HAG-B1..B4, HAG-C1, HAG-C3, HAG-C4, HAG-D1 in
hook-as-guest/acceptance-criteria.md
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import write_red_record

REPO_ROOT = Path(__file__).resolve().parent.parent
PRE_TOOL = REPO_ROOT / "hooks" / "pre-tool.sh"
STOP = REPO_ROOT / "hooks" / "stop.sh"
CLI = REPO_ROOT / "cli" / "compass"

ALLOW, BLOCK = 0, 2

pytestmark = pytest.mark.skipif(
    not PRE_TOOL.exists(), reason="hooks/pre-tool.sh missing")


def _run_hook(cwd, payload, hook=PRE_TOOL, project_dir=None):
    """Run a hook the way Claude Code does.

    The hook reads `INVOKED_FROM="$(pwd)"`, not the payload's `cwd`, so the
    subprocess must actually run in the repository under test. Run anywhere
    else, every block looks like silence.
    """
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    if project_dir:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        ["bash", str(hook)], input=json.dumps(payload), capture_output=True,
        text=True, env=env, cwd=str(cwd), timeout=60)


def _repo(tmp_path, name="repo", *, git=True, compass=False, work=False):
    # .resolve(): on macOS /var is a symlink to /private/var, and an
    # unresolved payload path against a resolved `pwd` reads as outside the
    # project - silent for a reason that has nothing to do with guests.
    root = (tmp_path / name).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if git:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
    if compass:
        (root / ".compass").mkdir(exist_ok=True)
    if work:
        (root / ".compass" / "work").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(exist_ok=True)
    target = root / "src" / "widget.py"
    target.write_text("print(1)\n", encoding="utf-8")
    return root, target


def _edit(target):
    return {"tool_name": "Edit",
            "tool_input": {"file_path": str(target),
                           "old_string": "print(1)", "new_string": "print(2)"}}


def _write(target):
    return {"tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": "print(2)\n"}}


def _bash(target):
    return {"tool_name": "Bash",
            "tool_input": {"command": "echo x > " + str(target)}}


# ---------------------------------------------------------------------------
# HAG-A1 / HAG-A2 - a guest repository is silent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("shape", [_edit, _write, _bash])
@pytest.mark.parametrize("explicit", [False, True],
                         ids=["walked", "CLAUDE_PROJECT_DIR"])
def test_hag_a1_a_guest_repository_is_silent(tmp_path, shape, explicit):
    """Both refusal branches, because a guest reaches a different one.

    Without the variable the walk fails and the hook says "could not locate a
    Compass project"; with it the explicit root is taken at its word and the
    hook says "no .compass/work/". A fix that closes one leaves the other.
    """
    root, target = _repo(tmp_path)
    r = _run_hook(root, shape(target), project_dir=root if explicit else None)
    out = (r.stdout + r.stderr).strip()

    assert r.returncode == ALLOW, (
        "the hook blocked an edit in a repository that has never opted into "
        f"Compass:\n{out}")
    assert not out, (
        f"the hook spoke to a repository that never asked for it:\n{out}")


def test_hag_a2_a_bare_directory_is_silent(tmp_path):
    root, target = _repo(tmp_path, git=False)
    r = _run_hook(root, _edit(target))
    assert r.returncode == ALLOW, (r.stdout + r.stderr)
    assert not (r.stdout + r.stderr).strip()


# ---------------------------------------------------------------------------
# HAG-B1..B3 - an opted-in project is unchanged
# ---------------------------------------------------------------------------

def test_hag_b1_an_opted_in_project_before_triage_still_blocks(tmp_path):
    """`.compass/` is the opt-in, so from here Compass is entitled to speak."""
    root, target = _repo(tmp_path, compass=True)
    r = _run_hook(root, _edit(target), project_dir=root)
    err = (r.stdout + r.stderr).lower()

    assert r.returncode == BLOCK, (
        "a project that has opted in was waved through - the fix is meant to "
        "scope the check, not remove it")
    assert "triage" in err or "assess" in err, (
        f"the block does not tell the user what to run:\n{err}")


def test_hag_b2_an_opted_in_project_with_no_issue_still_blocks(tmp_path):
    root, target = _repo(tmp_path, compass=True, work=True)
    r = _run_hook(root, _edit(target), project_dir=root)
    err = (r.stdout + r.stderr).lower()

    assert r.returncode == BLOCK, "an opted-in project with no issue was waved through"
    assert "no issue" in err or "triage" in err, err


def test_hag_b3_an_unreadable_opted_in_project_fails_closed(tmp_path):
    """The distinction that matters is how this fails.

    "No `.compass/`" and "could not read the project" are not the same case.
    The first is a stranger's repository. The second is Compass unable to tell
    what it is enforcing, and answering "allow" to a question it could not ask
    is a guardrail switched off silently.
    """
    root, target = _repo(tmp_path, compass=True, work=True)
    issue = root / ".compass" / "work" / "an-issue"
    issue.mkdir()
    (root / ".compass" / "current-task").write_text("an-issue\n")
    # An issue directory the hook cannot read the approach from.
    (issue / "manifest.yml").write_text("schema_version: '2.0'\ntask: an-issue\n")

    r = _run_hook(root, _edit(target), project_dir=root)
    assert r.returncode == BLOCK, (
        "an opted-in project the hook could not read was waved through:\n"
        + r.stdout + r.stderr)


def test_hag_b4_silence_is_not_bought_by_widening_the_search(tmp_path):
    """The failure mode this change could introduce.

    An unbounded walk would resolve a stranger's issue - a monorepo sibling, a
    stray .compass/ in $HOME - and if that issue were mid-red it would ALLOW
    the edit. Silence in a guest repository and a fail-open borrow of someone
    else's red marker are different outcomes.
    """
    outer, _ = _repo(tmp_path, "outer", compass=True, work=True)
    issue = outer / ".compass" / "work" / "an-issue"
    issue.mkdir()
    (issue / "manifest.yml").write_text("schema_version: '2.0'\ntask: an-issue\n")
    (issue / "delivery-approach.md").write_text("# approach\n")
    (outer / ".compass" / "current-task").write_text("an-issue\n")
    write_red_record(issue)          # mid-red: edits allowed in OUTER

    inner = outer / "vendor" / "submodule"
    inner.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(inner)], check=True)
    (inner / "src").mkdir()
    inner_target = inner / "src" / "widget.py"
    inner_target.write_text("print(1)\n")

    r = _run_hook(inner, _edit(inner_target))
    out = (r.stdout + r.stderr).strip()

    assert not out, (
        "the hook spoke in a nested repository that has no .compass/ of its "
        f"own:\n{out}")
    # It is allowed BECAUSE it is a guest, not because it borrowed the outer
    # project's red. The distinction is invisible in the exit code, so the
    # check is that the outer issue was never consulted.
    assert "an-issue" not in out, (
        "the hook resolved the parent project's issue for an edit in a "
        "repository that is not part of it")


# ---------------------------------------------------------------------------
# HAG-D1 - enforcement inside a Compass project is untouched
# ---------------------------------------------------------------------------

def _compass_project(tmp_path):
    root, target = _repo(tmp_path, compass=True, work=True)
    issue = root / ".compass" / "work" / "an-issue"
    issue.mkdir()
    (issue / "manifest.yml").write_text(
        "schema_version: '2.0'\ntask: an-issue\ndelivery_approach: feature\n")
    (issue / "delivery-approach.md").write_text("# approach\n")
    (root / ".compass" / "current-task").write_text("an-issue\n")
    return root, target, issue


def test_hag_d1_a_compass_project_still_blocks_without_a_red(tmp_path):
    root, target, _ = _compass_project(tmp_path)
    r = _run_hook(root, _edit(target), project_dir=root)
    assert r.returncode == BLOCK, (
        "the hook's actual job stopped working:\n" + r.stdout + r.stderr)


def test_hag_d1b_a_compass_project_allows_under_a_red(tmp_path):
    root, target, issue = _compass_project(tmp_path)
    write_red_record(issue)
    r = _run_hook(root, _edit(target), project_dir=root)
    assert r.returncode == ALLOW, (
        "a project with a red on record was blocked:\n" + r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# HAG-C1 - the stop hook is silent too
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not STOP.exists(), reason="hooks/stop.sh missing")
def test_hag_c1_the_stop_hook_is_silent_outside_a_compass_project(tmp_path):
    """It never blocked - it always exits 0 - but it spoke."""
    root, _ = _repo(tmp_path)
    r = _run_hook(root, {"tool_name": "Stop", "tool_input": {}}, hook=STOP)
    out = (r.stdout + r.stderr).strip()
    assert r.returncode == ALLOW, out
    assert not out, (
        "the stop hook told a repository that never opted into Compass that "
        f"it could not find a Compass project:\n{out}")


# ---------------------------------------------------------------------------
# HAG-C3 - init and the hook agree on where the project is
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("start_in", ["root", "nested"])
def test_hag_c3_init_and_the_hook_agree_on_the_project_root(tmp_path, start_in):
    """`.compass/` is the opt-in and only `compass init` creates it, so the
    two must not disagree about which directory that is.

    They resolve differently on purpose - the hook walks up looking for
    `.compass/` and stops at `.git`; init takes the nearest `.git` - and "they
    agree in practice" is the kind of claim that is true until it is not.
    """
    root, target = _repo(tmp_path)
    deep = root / "src" / "nested" / "deeper"
    deep.mkdir(parents=True)
    start = root if start_in == "root" else deep

    subprocess.run([sys.executable, str(CLI), "init", "--quiet"],
                   cwd=str(start), capture_output=True, text=True, timeout=60)
    assert (root / ".compass").is_dir(), (
        f"init run from {start_in} did not create the project at the "
        "repository root")

    # Now the hook must see the project init just made, from the same place.
    r = _run_hook(start, _edit(target))
    out = (r.stdout + r.stderr).strip()
    assert r.returncode == BLOCK, (
        "the hook does not see the project `compass init` just created from "
        f"the same directory - the two disagree about where the project is:\n{out}")


# ---------------------------------------------------------------------------
# HAG-C4 - the first block explains the opt-in
# ---------------------------------------------------------------------------

def test_hag_c4_the_first_block_explains_an_automatic_opt_in(tmp_path):
    """A user whose project an entry point initialised did not run init.

    Their first sight of Compass refusing an edit must not be an unexplained
    refusal - it should say when the project opted in and what did it.
    """
    root, target = _repo(tmp_path)
    subprocess.run([sys.executable, str(CLI), "init", "--quiet"],
                   cwd=str(root), capture_output=True, text=True, timeout=60)

    r = _run_hook(root, _edit(target), project_dir=root)
    out = (r.stdout + r.stderr)

    assert r.returncode == BLOCK, out
    assert "initializ" in out.lower(), (
        "the block does not mention that the project was initialised, so a "
        f"user who never ran init has no idea why Compass is here:\n{out}")
    assert "compass init" in out.lower(), (
        f"the block does not name what initialised the project:\n{out}")
