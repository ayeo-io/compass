"""The pre-tool hook judges an edit by the issue of the tree it names.

A builder in a sibling git worktree was refused for an issue that was not
theirs (GitHub issues #216 and #58). The hook found the right project from the
edited path but chose the issue from the session: `COMPASS_ISSUE` came first,
and a copied session table raised `pointer-moved`. A project that is not the
session's own (a foreign project) is now judged by its own pointer, with
`COMPASS_ISSUE` as a fallback for an empty pointer only, and it must be tied
to the session's repository.

Every hook scenario uses a real `git worktree add`, the real hook and a JSON
payload that names a production-code file.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from test_session_issue import _issue

ROOT = Path(__file__).resolve().parent.parent
PRE = ROOT / "hooks" / "pre-tool.sh"

_GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
        "-c", "commit.gpgsign=false"]


def _git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run([*_GIT, *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True, env=env)


def _repo(root):
    """A git repository with one commit and a `src/` folder."""
    root = Path(root).resolve()
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "src")
    _git(root, "commit", "-q", "-m", "first")
    return root


def _linked(main, name="wt"):
    """A linked worktree of `main`, placed beside it."""
    wt = main.parent / name
    _git(main, "worktree", "add", "-q", "--detach", str(wt))
    return wt.resolve()


def _setup(tmp_path, *, main_issues=(("alpha", True), ("beta", False)),
           main_pointer="beta"):
    """The session's project `main` and nothing else yet."""
    main = _repo(tmp_path / "main")
    for slug, red in main_issues:
        _issue(main, slug, red=red)
    if main_pointer:
        (main / ".compass" / "current-task").write_text(main_pointer + "\n")
    return main


def _wt_issues(wt, issues, pointer):
    for slug, red in issues:
        _issue(wt, slug, red=red)
    if pointer is not None:
        (wt / ".compass").mkdir(exist_ok=True)
        (wt / ".compass" / "current-task").write_text(pointer + "\n")


def _env(project, issue=None):
    env = {k: v for k, v in os.environ.items()
           if k not in ("COMPASS_ISSUE", "CLAUDE_CODE_SESSION_ID")
           and not k.startswith("GIT_")}
    env["CLAUDE_PROJECT_DIR"] = str(project)
    if issue is not None:
        env["COMPASS_ISSUE"] = issue
    return env


def _hook(project, target, *, issue=None, session=None, tool="Write",
          cwd=None, command=None):
    tool_input = ({"command": command} if tool == "Bash"
                  else {"file_path": str(target), "content": "x = 2\n"})
    payload = {"tool_name": tool, "tool_input": tool_input}
    if session:
        payload["session_id"] = session
    return subprocess.run(
        ["bash", str(PRE)], input=json.dumps(payload), capture_output=True,
        text=True, env=_env(project, issue), cwd=str(cwd or project),
        timeout=60)


def _flat(result):
    return " ".join((result.stdout + result.stderr).split())


# --- group A: which issue judges an edit ----------------------------------------

def test_session_project_edit_is_judged_by_the_session_issue(tmp_path):
    """Scenario id: `TRC-001` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path)
    r = _hook(main, main / "src" / "app.py", issue="alpha")
    assert r.returncode == 0, r.stderr


def test_session_started_below_the_root_is_not_foreign(tmp_path):
    """Scenario id: `TRC-001` in worktree-issue-from-edited-path/acceptance-criteria.md

    The session project is the Compass root found from CLAUDE_PROJECT_DIR, so
    a session started in a sub-folder keeps COMPASS_ISSUE.
    """
    main = _setup(tmp_path)
    (main / "sub").mkdir()
    r = _hook(main / "sub", main / "src" / "app.py", issue="alpha")
    assert r.returncode == 0, r.stderr


def test_worktree_pointer_beats_the_session_variable(tmp_path):
    """Scenario id: `TRC-002` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path)
    wt = _linked(main)
    _wt_issues(wt, [("alpha", False), ("beta", True)], "beta")
    r = _hook(main, wt / "src" / "app.py", issue="alpha")
    assert r.returncode == 0, r.stderr


def test_worktree_pointer_judges_the_edit_without_the_variable(tmp_path):
    """Scenario id: `TRC-003` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path)
    wt = _linked(main)
    _wt_issues(wt, [("beta", True)], "beta")
    r = _hook(main, wt / "src" / "app.py")
    assert r.returncode == 0, r.stderr


def test_worktree_issue_without_red_is_refused_though_the_session_issue_has_one(
        tmp_path):
    """Scenario id: `TRC-004` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path)
    wt = _linked(main)
    _wt_issues(wt, [("alpha", True), ("beta", False)], "beta")
    r = _hook(main, wt / "src" / "app.py", issue="alpha")
    assert r.returncode == 2, r.stderr
    assert "no-red-on-record" in r.stderr
    assert "beta" in r.stderr


def test_variable_names_the_issue_of_a_worktree_without_a_pointer(tmp_path):
    """Scenario id: `TRC-005` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path)
    wt = _linked(main)
    _wt_issues(wt, [("alpha", True)], None)
    r = _hook(main, wt / "src" / "app.py", issue="alpha")
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("pointer,variable", [
    (None, None),
    ("missing", None),
    (None, "missing"),
    ("missing", "gamma"),
])
def test_worktree_with_no_issue_to_name_is_refused(tmp_path, pointer, variable):
    """Scenario id: `TRC-006` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path)
    wt = _linked(main)
    _wt_issues(wt, [("gamma", True)], pointer)
    r = _hook(main, wt / "src" / "app.py", issue=variable)
    assert r.returncode == 2, r.stderr
    assert "bad-session-issue" in r.stderr, r.stderr
    assert str(wt) in _flat(r)


def _other_repo_project(tmp_path):
    other = _repo(tmp_path / "other")
    _issue(other, "beta", red=True)
    (other / ".compass" / "current-task").write_text("beta\n")
    return other


def _plain_project(tmp_path):
    plain = tmp_path / "plain"
    (plain / "src").mkdir(parents=True)
    _issue(plain, "beta", red=True)
    (plain / ".compass" / "current-task").write_text("beta\n")
    return plain


def _unreadable_worktree(tmp_path):
    main = tmp_path / "main"
    wt = _linked(main)
    _wt_issues(wt, [("beta", True)], "beta")
    gitdir = next((main / ".git" / "worktrees").iterdir())
    for child in sorted(gitdir.rglob("*"), reverse=True):
        child.unlink() if not child.is_dir() else child.rmdir()
    gitdir.rmdir()
    return wt


@pytest.mark.parametrize("kind", ["other-repository", "no-repository",
                                  "git-folder-removed"])
def test_project_outside_the_session_repository_is_refused(tmp_path, kind):
    """Scenario id: `TRC-007` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path)
    if kind == "other-repository":
        project = _other_repo_project(tmp_path)
    elif kind == "no-repository":
        project = _plain_project(tmp_path)
    else:
        project = _unreadable_worktree(tmp_path)
    r = _hook(main, project / "src" / "app.py")
    assert r.returncode == 2, r.stderr
    assert "tree-not-tied" in r.stderr, r.stderr


@pytest.mark.parametrize("kind", ["other-repository", "no-repository"])
def test_untied_tree_refusal_does_not_call_none_an_issue(tmp_path, kind):
    """Scenario id: `TRC-007` in worktree-issue-from-edited-path/acceptance-criteria.md

    A tree that is not tied to the session's repository has no issue to
    name, so the refusal says the tree is not tied, not that 'none' is not
    an issue.
    """
    main = _setup(tmp_path)
    project = (_other_repo_project(tmp_path) if kind == "other-repository"
               else _plain_project(tmp_path))
    r = _hook(main, project / "src" / "app.py")
    assert r.returncode == 2, r.stderr
    text = _flat(r)
    assert "'none'" not in text, text
    assert "not tied to the session's repository" in text, text


def test_relative_session_project_directory_ends_the_search(tmp_path):
    """Scenario id: `TRC-007` in worktree-issue-from-edited-path/acceptance-criteria.md

    A relative CLAUDE_PROJECT_DIR has no Compass folder to find. The upward
    search must stop at the top of the relative path, and the edit is judged
    as before: by the project the edited path names (no red on record here).
    """
    main = _setup(tmp_path, main_issues=(("beta", False),))
    outside = tmp_path / "outside"
    outside.mkdir()
    payload = {"tool_name": "Write", "tool_input": {
        "file_path": str(main / "src" / "app.py"), "content": "x = 2\n"}}
    try:
        r = subprocess.run(
            ["bash", str(PRE)], input=json.dumps(payload),
            capture_output=True, text=True, env=_env("main"),
            cwd=str(outside), timeout=10)
    except subprocess.TimeoutExpired:
        pytest.fail("the hook did not end: the search for the session's "
                    "Compass folder looped on a relative path")
    assert r.returncode == 2, r.stderr
    assert "no-red-on-record" in r.stderr, r.stderr


def test_case_variant_spelling_of_the_session_project_is_the_session_project(
        tmp_path):
    """Scenario id: `TRC-009` in worktree-issue-from-edited-path/acceptance-criteria.md

    On a case-insensitive file system `MAIN` and `main` are one folder. The
    comparison follows the file system, so the variant is not foreign and
    COMPASS_ISSUE keeps its place.
    """
    main = _setup(tmp_path)
    variant = tmp_path / "MAIN"
    if not variant.exists():
        pytest.skip("this file system is case-sensitive: `MAIN` is not the "
                    "folder `main`, so there is no case variant to test")
    r = _hook(main, variant / "src" / "app.py", issue="alpha")
    assert r.returncode == 0, r.stderr


def test_case_variant_session_directory_still_ties_a_worktree(tmp_path):
    """Scenario id: `TRC-009` in worktree-issue-from-edited-path/acceptance-criteria.md

    The session is started in `MAIN`, which is the folder `main` on a
    case-insensitive file system. A worktree of that repository is still tied
    to it, so the worktree's own issue judges the edit.
    """
    main = _setup(tmp_path)
    wt = _linked(main)
    _wt_issues(wt, [("beta", True)], "beta")
    variant = tmp_path / "MAIN"
    if not variant.exists():
        pytest.skip("this file system is case-sensitive: `MAIN` is not the "
                    "folder `main`, so there is no case variant to test")
    r = _hook(variant, wt / "src" / "app.py", cwd=main)
    assert r.returncode == 0, r.stderr


def test_stale_session_variable_in_the_session_project_is_refused(tmp_path):
    """Scenario id: `TRC-008` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path)
    r = _hook(main, main / "src" / "app.py", issue="removed-issue")
    assert r.returncode == 2, r.stderr
    assert "bad-session-issue" in r.stderr
    assert "removed-issue" in r.stderr


def test_symbolic_link_to_the_session_project_is_the_session_project(tmp_path):
    """Scenario id: `TRC-009` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(main, target_is_directory=True)
    r = _hook(main, link / "src" / "app.py", issue="alpha")
    assert r.returncode == 0, r.stderr


def test_tree_with_no_compass_project_is_allowed(tmp_path):
    """Scenario id: `TRC-010` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path)
    wt = _linked(main)
    outside = tmp_path / "outside"
    (outside / "src").mkdir(parents=True)
    for target in (wt / "src" / "app.py", outside / "src" / "app.py"):
        r = _hook(main, target, issue="alpha")
        assert r.returncode == 0, (target, r.stderr)


def test_session_with_no_compass_project_is_never_foreign(tmp_path):
    """Scenario id: `TRC-010` in worktree-issue-from-edited-path/acceptance-criteria.md

    A hook installed at user scope runs in repositories that never opted in.
    Such a session has no issue to borrow, so another project is judged as
    before: by its own pointer, and by the red on record.
    """
    bare = tmp_path / "bare"
    bare.mkdir()
    allowed = _plain_project(tmp_path)
    r = _hook(bare, allowed / "src" / "app.py")
    assert r.returncode == 0, r.stderr
    _issue(tmp_path / "plain", "gamma", red=False)
    (tmp_path / "plain" / ".compass" / "current-task").write_text("gamma\n")
    r = _hook(bare, allowed / "src" / "app.py")
    assert r.returncode == 2 and "no-red-on-record" in r.stderr, r.stderr


def test_session_is_recorded_on_the_worktree_issue(tmp_path):
    """Scenario id: `TRC-011` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path)
    wt = _linked(main)
    _wt_issues(wt, [("alpha", False), ("beta", True)], "beta")
    r = _hook(main, wt / "src" / "app.py", issue="alpha", session="S1")
    assert r.returncode == 0, r.stderr
    beta = (wt / ".compass" / "work" / "beta" / "manifest.yml").read_text()
    alpha = (wt / ".compass" / "work" / "alpha" / "manifest.yml").read_text()
    assert re.search(r"-\s+['\"]?S1['\"]?\s*$", beta, re.M), beta
    assert "S1" not in alpha, alpha


# --- group B: the session table ------------------------------------------------

def _table(compass_dir, session, slug, root):
    entry = {"issue": slug, "at": _now()}
    if root is not None:
        entry["root"] = str(root)
    (compass_dir / "sessions.json").write_text(
        json.dumps({session: entry}), encoding="utf-8")


def _now():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")


def test_copied_session_table_does_not_refuse_a_write_in_the_worktree(tmp_path):
    """Scenario id: `TRC-016` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path)
    wt = _linked(main)
    _wt_issues(wt, [("alpha", True), ("beta", True)], "beta")
    _table(wt / ".compass", "S1", "alpha", (main / ".compass").resolve())
    r = _hook(wt, wt / "src" / "app.py", session="S1")
    assert r.returncode == 0, r.stderr


def test_pointer_moved_in_the_session_project_is_still_refused(tmp_path):
    """Scenario id: `TRC-017` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path)
    wt = _linked(main)
    _wt_issues(wt, [("alpha", True), ("beta", True)], "alpha")
    first = _hook(wt, wt / "src" / "app.py", session="S1")
    assert first.returncode == 0, first.stderr
    (wt / ".compass" / "current-task").write_text("beta\n")
    r = _hook(wt, wt / "src" / "app.py", session="S1")
    assert r.returncode == 2, r.stderr
    assert "pointer-moved" in r.stderr
    assert "'alpha'" in r.stderr


def test_foreign_worktree_edit_skips_the_session_table(tmp_path):
    """Scenario id: `TRC-018` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path)
    wt = _linked(main)
    _wt_issues(wt, [("alpha", True), ("beta", True)], "beta")
    _table(wt / ".compass", "S1", "alpha", (wt / ".compass").resolve())
    before = (wt / ".compass" / "sessions.json").read_bytes()
    r = _hook(main, wt / "src" / "app.py", session="S1")
    assert r.returncode == 0, r.stderr
    assert (wt / ".compass" / "sessions.json").read_bytes() == before


# --- group C: Bash and the documents -------------------------------------------

def test_bash_still_resolves_from_the_session_project(tmp_path):
    """Scenario id: `TRC-019` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    main = _setup(tmp_path, main_issues=(("alpha", False),),
                  main_pointer="alpha")
    wt = _linked(main)
    _wt_issues(wt, [("beta", True)], "beta")
    r = _hook(main, None, tool="Bash", cwd=wt,
              command="echo x > src/app.py")
    assert r.returncode == 2, r.stderr
    assert "no-red-on-record" in r.stderr
    assert "alpha" in r.stderr


def test_safety_contract_states_the_worktree_issue_rules():
    """Scenario id: `TRC-020` in worktree-issue-from-edited-path/acceptance-criteria.md"""
    text = " ".join((ROOT / "docs" / "safety-contract.md").read_text().split())
    for phrase in (
            "Edit and Write follow the worktree's own issue",
            "COMPASS_ISSUE applies in the session's own project",
            "only when the worktree's pointer is empty",
            "a shell write still resolves from the session's project",
            "worktree of a different repository is refused"):
        assert phrase in text, phrase


def test_refusal_text_and_claude_md_describe_the_new_rules():
    """Scenario id: `TRC-021` in worktree-issue-from-edited-path/acceptance-criteria.md

    The generated page matches the registry in
    tests/test_refusal_registry.py::test_rtp_4_docs_page_is_not_stale.
    """
    import sys
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg.refusals import render

    bad = " ".join(render("bad-session-issue", slug="x", project="/p").split())
    assert "worktree" in bad and "/p" in bad
    moved = " ".join(render("pointer-moved", slug="a", previous="b").split())
    assert "own project" in moved
    claude = " ".join((ROOT / "CLAUDE.md").read_text().split())
    assert "(`pointer-moved`)" in claude
    assert "session's own project" in claude
