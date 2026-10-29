"""Which worktree's record an approval goes to (ayeo-io/compass-delivery#317).

An issue triaged on `main` is committed there, then worked in a worktree, so
two trees hold its record. A person's `/compass:approve --issue` and
`/compass:reject --issue` take the record in the tree they type it in, as every
other Compass command reads the issue from the current checkout. A delegated
approval and `/compass:delegate --on` still refuse a slug that two trees hold:
an agent's identical words must name one issue (jed72, 2026-10-23, and the
threat model of delegation-everywhere).

| Scenario | What it checks |
|---|---|
| `TRC-001` | for a person, a linked worktree that holds the issue wins over the main checkout |
| `TRC-002` | for a person, the main checkout wins when they type it there |
| `TRC-003` | two holders, neither of them here: refused, naming both and the fix |
| `TRC-004` | one holder elsewhere is found, as before |
| `TRC-005` | an agent's delegated approval and `--on` still refuse two holders |

Each scenario uses a real `git worktree add`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from compass_pkg import approve_cmd, delegations, prompt_approval, worktree_lookup  # noqa: E402,E501
from compass_pkg.core import CompassError  # noqa: E402

_GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
        "-c", "commit.gpgsign=false"]


def _git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run([*_GIT, *args], cwd=str(cwd), check=True, capture_output=True,
                   text=True, env=env)


def _hold(tree, slug="alpha"):
    folder = tree / ".compass" / "work" / slug
    folder.mkdir(parents=True)
    (folder / "manifest.yml").write_text(f"issue: {slug}\n", encoding="utf-8")
    return str(folder)


def _repo(tmp_path, *linked):
    """A repository `main` with one commit and the linked worktrees named."""
    main = (tmp_path / "main").resolve()
    main.mkdir()
    (main / "README.md").write_text("x\n", encoding="utf-8")
    _git(main, "init", "-q")
    _git(main, "add", "README.md")
    _git(main, "commit", "-q", "-m", "first")
    trees = {"main": main}
    for name in linked:
        _git(main, "worktree", "add", "-q", "--detach", str(tmp_path / name))
        trees[name] = (tmp_path / name).resolve()
    return trees


def _find_from(tree, slug="alpha"):
    """The lookup a person's `/compass:approve --issue` makes in `tree`."""
    return prompt_approval._find(worktree_lookup.list_worktrees(str(tree)), slug)


def test_trc_001_the_worktree_the_command_runs_in_wins(tmp_path):
    trees = _repo(tmp_path, "wt")
    _hold(trees["main"])
    here = _hold(trees["wt"])
    assert os.path.realpath(_find_from(trees["wt"])) == os.path.realpath(here)


def test_trc_002_the_main_checkout_wins_when_the_command_runs_there(tmp_path):
    trees = _repo(tmp_path, "wt")
    here = _hold(trees["main"])
    _hold(trees["wt"])
    assert os.path.realpath(_find_from(trees["main"])) == os.path.realpath(here)


def test_trc_003_two_holders_and_neither_here_is_refused(tmp_path):
    trees = _repo(tmp_path, "wt-a", "wt-b")
    held = {os.path.realpath(_hold(trees["main"])), os.path.realpath(_hold(trees["wt-a"]))}
    with pytest.raises(worktree_lookup.HeldTwice) as caught:
        worktree_lookup.find_issue(worktree_lookup.list_worktrees(str(trees["wt-b"])), "alpha",
                                   prefer_here=True)
    assert {os.path.realpath(f) for f in caught.value.folders} == held


def test_trc_003_the_refusals_name_the_fix(tmp_path):
    trees = _repo(tmp_path, "wt-a", "wt-b")
    _hold(trees["main"])
    _hold(trees["wt-a"])
    with pytest.raises(prompt_approval.Refused) as refused:
        _find_from(trees["wt-b"])
    assert "held by more than one worktree" in str(refused.value)
    assert "type it in the worktree whose record you mean" in str(refused.value)


def test_trc_004_one_holder_elsewhere_is_found(tmp_path):
    trees = _repo(tmp_path, "wt-a")
    there = _hold(trees["wt-a"])
    assert os.path.realpath(_find_from(trees["main"])) == os.path.realpath(there)


def test_trc_005_an_agent_approval_still_refuses_two_holders(tmp_path, monkeypatch):
    trees = _repo(tmp_path, "wt")
    _hold(trees["main"])
    _hold(trees["wt"])
    with pytest.raises(worktree_lookup.HeldTwice):
        worktree_lookup.find_issue(worktree_lookup.list_worktrees(str(trees["wt"])), "alpha")
    monkeypatch.chdir(trees["wt"])
    with pytest.raises(CompassError, match="held by more than one worktree"):
        approve_cmd._delegated_places("alpha")
    session = type("Session", (), {"project": str(trees["wt"])})()
    with pytest.raises(Exception, match="held by more than one worktree"):
        delegations._issues_named(["alpha"], session)


def test_trc_001_typed_in_the_worktree_records_there_and_not_on_main(tmp_path):
    """The first success signal, through the approval hook itself."""
    import test_prompt_approval_worktrees as hook
    from delegation_support import copy_issue
    top, work = hook._setup(tmp_path)
    copy_issue(top, top, hook.WT)
    hook._request(top, hook.WT)
    hook._request(work, hook.WT)
    result = hook._approve(work, f"1 --issue {hook.WT}")
    assert not result.block, result.message
    assert len(hook._records(work, hook.WT)) == 1
    assert hook._records(top, hook.WT) == []


def test_trc_005_the_agent_refusal_names_the_route_for_a_person(tmp_path, monkeypatch):
    trees = _repo(tmp_path, "wt")
    _hold(trees["main"])
    _hold(trees["wt"])
    monkeypatch.chdir(trees["wt"])
    with pytest.raises(CompassError) as refused:
        approve_cmd._delegated_places("alpha")
    assert "/compass:approve" in str(refused.value)
