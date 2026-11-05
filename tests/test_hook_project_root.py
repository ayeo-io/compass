"""The pre-tool hook finds the project it is enforcing, or refuses.

`PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"` assumed the working directory
is the repository root. When Claude Code is started anywhere else - a
subdirectory, or a parent - the hook looked for `.compass/` in the wrong
place, found nothing, and blocked every code edit while reporting that
assessment had not run. It had.

The fix walks up from the working directory, and refuses when it finds
nothing - an enforcement path that cannot tell what it is enforcing must
never let an edit through.

Scenario ids: see the issue's acceptance criteria (group A).
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

from conftest import write_red_record

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "pre-tool.sh"

BLOCK, ALLOW = 2, 0

SPINE = """schema_version: "2.0"
task: "{slug}"
created: "2026-08-13"
status: active
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: small
  goal: delivery
  role: engineer
  labels: []
delivery_approach: quick-fix
topology: solo
policy_rules_fired: []
stages: {{frame: full, specify: light, clarify: collapsed, plan: collapsed,
  distribute: skipped, build: full, verify: light, land: light}}
evidence: []
gates: []
scenarios: []
changed_files: []
claims: []
follow_ups: []
reassessments: []
friction: []
"""


def _project(tmp_path: pathlib.Path, *, with_work: bool = True) -> pathlib.Path:
    """A minimal project tree: .compass/ with one assessed issue."""
    proj = tmp_path / "proj"
    (proj / "src" / "deep" / "deeper").mkdir(parents=True)
    (proj / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    compass = proj / ".compass"
    compass.mkdir()
    (compass / "config.yml").write_text("version: 1.0.0\n", encoding="utf-8")
    if with_work:
        work = compass / "work" / "demo"
        work.mkdir(parents=True)
        (work / "manifest.yml").write_text(SPINE.format(slug="demo"), encoding="utf-8")
        (work / "delivery-approach.md").write_text("# approach\n", encoding="utf-8")
        (compass / "current-task").write_text("demo\n", encoding="utf-8")
        # The `.red` marker matters to the test, not just to the fixture: it
        # is what makes a correctly-resolved project ALLOW the edit. Without
        # it both the resolved and the unresolved case block - for completely
        # different reasons - and a test comparing exit codes passes while
        # measuring nothing.
        write_red_record(work)
    return proj


def _run(cwd: pathlib.Path, target: pathlib.Path, env_project=None):
    """Invoke the hook as the runtime does: JSON on stdin, verdict as exit code."""
    payload = json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(target)},
    })
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(cwd)}
    if env_project is not None:
        env["CLAUDE_PROJECT_DIR"] = str(env_project)
    return subprocess.run(
        ["bash", str(HOOK)], input=payload, cwd=str(cwd),
        capture_output=True, text=True, timeout=120, env=env,
    )


def test_rcd_a1_resolves_from_subdirectory(tmp_path):
    """The verdict must not depend on which directory the session started in."""
    proj = _project(tmp_path)
    target = proj / "src" / "app.py"

    from_root = _run(proj, target)
    from_deep = _run(proj / "src" / "deep" / "deeper", target)

    assert from_deep.returncode == from_root.returncode, (
        f"the hook gave a different verdict from a subdirectory "
        f"(root={from_root.returncode}, subdir={from_deep.returncode}). It "
        f"resolved a different project root, so it enforced a different "
        f"issue - or none.\nsubdir stderr: {from_deep.stderr}"
    )


def test_rcd_a2_a_repository_that_never_opted_in_is_silent(tmp_path):
    """No .compass/ anywhere: pass through, and say nothing.

    The hook runs in every repository on the machine, so a repository with
    no `.compass/` passes through silently.

    The case that still refuses is a project that HAS opted in and cannot be
    read - see test_rcd_a4b below.
    """
    outside = tmp_path / "elsewhere"
    (outside / "src").mkdir(parents=True)
    target = outside / "src" / "app.py"
    target.write_text("x = 1\n", encoding="utf-8")

    result = _run(outside, target)

    assert result.returncode == ALLOW, (
        f"the hook exited {result.returncode} in a repository that has never "
        f"opted into Compass. It runs in every repository on the machine, so "
        f"this is every unrelated project the user owns.\nstderr: {result.stderr}"
    )
    assert not (result.stdout + result.stderr).strip(), (
        "the hook spoke to a repository that never asked for it:\n"
        + result.stdout + result.stderr
    )
def test_rcd_a3_an_opted_in_project_names_the_real_cause(tmp_path):
    """The diagnostic still names the real cause where it still speaks.

    An opted-in project that has not been assessed must be told to assess,
    not that its working directory is wrong.
    """
    proj = tmp_path / "opted-in"
    (proj / ".compass").mkdir(parents=True)
    (proj / "src").mkdir()
    target = proj / "src" / "app.py"
    target.write_text("x = 1\n", encoding="utf-8")

    result = _run(proj, target, env_project=proj)
    err = result.stderr.lower()

    assert result.returncode == BLOCK, (
        "a project that has opted in was waved through - the boundary is "
        "meant to scope the check, not remove it")
    assert "triage" in err or "assess" in err, (
        f"the block does not say what to run:\n{err}")
    assert "could not locate" not in err, (
        f"the hook blames a working directory that is already correct:\n{err}")
def test_rcd_a4_missing_work_dir_still_says_so(tmp_path):
    """The control for A3: a genuine "no issue has been assessed" still says so.

    Without this, A3 passes against a hook that has simply stopped telling
    the two cases apart.
    """
    proj = _project(tmp_path, with_work=False)
    target = proj / "src" / "app.py"

    result = _run(proj, target)
    err = result.stderr.lower()

    assert result.returncode == BLOCK, (
        f"a project with no triaged issue must block, got {result.returncode}"
    )
    assert "no issue has been assessed" in err, (
        f"the hook resolved the project but did not say that no issue has "
        f"been assessed - the two failures are now indistinguishable in the "
        f"other direction:\n{err}"
    )


def test_rcd_a2b_the_walk_does_not_escape_the_repository(tmp_path):
    """A repository with no .compass/ must not inherit an ancestor's issue.

    Walking up from the working directory is right; walking up *without a
    bound* is not. A user
    working in a repository that has never opted in, underneath a parent that
    happens to hold a .compass/ - a monorepo, or a stray one in $HOME - would
    have the hook resolve the stranger's issue and enforce it. If that issue
    holds a `.red` marker the edit is ALLOWED: a fail-open path.

    Silence and a fail-open borrow reach the same exit code, so the exit code
    cannot tell them apart. What can: the hook must never NAME the stranger's
    issue, and must never consult it. This test therefore checks the output,
    not the verdict.
    """
    outer = tmp_path / "outer"
    (outer / ".compass" / "work" / "someone-elses").mkdir(parents=True)
    (outer / ".compass" / "config.yml").write_text("version: 1.0.0\n", encoding="utf-8")
    (outer / ".compass" / "work" / "someone-elses" / "manifest.yml").write_text(
        SPINE.format(slug="someone-elses"), encoding="utf-8")
    (outer / ".compass" / "work" / "someone-elses" / "delivery-approach.md").write_text(
        "# approach\n", encoding="utf-8")
    (outer / ".compass" / "current-task").write_text("someone-elses\n", encoding="utf-8")
    (outer / ".compass" / "work" / "someone-elses" / ".red").write_text("", encoding="utf-8")

    inner = outer / "untriaged-repo"
    (inner / ".git").mkdir(parents=True)
    (inner / "src").mkdir()
    target = inner / "src" / "app.py"
    target.write_text("x = 1\n", encoding="utf-8")

    result = _run(inner, target)
    out = result.stdout + result.stderr

    assert "someone-elses" not in out, (
        f"the hook resolved another project's issue for an edit in a "
        f"repository that is not part of it:\n{out}")
    assert not out.strip(), (
        f"the hook spoke in a repository that has no .compass/ of its own:\n{out}")
def test_rcd_a4b_an_opted_in_project_before_its_first_triage_is_told_to_triage(tmp_path):
    """An opted-in project with no work/ yet means assessment, not lost.

    What this guards is the message: a project that HAS opted in and has not
    been assessed must be told to assess, and must not be told its working
    directory is wrong.
    """
    proj = tmp_path / "fresh"
    (proj / ".compass").mkdir(parents=True)
    (proj / "src").mkdir()
    target = proj / "src" / "app.py"
    target.write_text("x = 1\n", encoding="utf-8")

    result = _run(proj, target, env_project=proj)
    err = result.stderr.lower()

    assert result.returncode == BLOCK, "an untriaged project must still block"
    assert "triage" in err or "assess" in err, (
        f"the hook did not mention triage on a project that simply has not "
        f"been triaged yet:\n{err}"
    )
    assert "could not locate" not in err, (
        f"the hook claims it could not find the project, though the project "
        f"root was given to it explicitly:\n{err}"
    )
def test_rcd_a1b_explicit_project_dir_still_wins(tmp_path):
    """CLAUDE_PROJECT_DIR stays authoritative when the host sets it.

    The fix replaces the *fallback*, not the contract. Without this, a change
    that ignored the variable entirely would pass every scenario above.
    """
    proj = _project(tmp_path)
    target = proj / "src" / "app.py"

    explicit = _run(tmp_path, target, env_project=proj)
    implicit = _run(proj, target)

    assert explicit.returncode == implicit.returncode, (
        f"setting CLAUDE_PROJECT_DIR gave a different verdict "
        f"({explicit.returncode}) than resolving from inside the project "
        f"({implicit.returncode})\nstderr: {explicit.stderr}"
    )
