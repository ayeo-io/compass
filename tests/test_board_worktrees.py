"""Reading the issue folders of other git worktrees for the board.

`board_trees.list_sources` lists the issue folders of this checkout and, with
worktrees on, of every other tree git reports. It chooses one folder per slug
by the modification time of its manifest, without opening any manifest, and
it never follows a link out of a tree. These tests build real repositories
with real linked worktrees under `tmp_path`.

Scenario ids: `TRC-W2`, `TRC-W3`, `TRC-W5`, `TRC-W7`, `TRC-W10`, plus the
supporting test for `TRC-W12` (a folder whose slug is done in this checkout
is never statted in another tree). Issue: `compass-board`.
"""
from __future__ import annotations

import builtins
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

THIS = "this checkout"


def _trees():
    """Import the module inside the test, so a missing module fails the test."""
    from compass_pkg import board_trees
    return board_trees


def _git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(cwd), env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _repo(tmp_path, name="main"):
    root = tmp_path / name
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "commit", "-q", "--allow-empty", "-m", "start")
    return root


def _worktree(repo, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-q", "--detach", str(path))
    return path


def _issue(tree, slug, mtime=None, manifest=True):
    folder = tree / ".compass" / "work" / slug
    folder.mkdir(parents=True, exist_ok=True)
    if manifest:
        path = folder / "manifest.yml"
        path.write_text(f"slug: {slug}\n", encoding="utf-8")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
    return folder


def _by_slug(sources):
    return {s["slug"]: s for s in sources if not s["refused"]}


def _snapshot(*trees):
    seen = {}
    for tree in trees:
        for here, dirs, files in os.walk(tree):
            dirs[:] = [d for d in dirs if d != ".git"]
            for name in files:
                p = os.path.join(here, name)
                if name == ".git":
                    continue
                st = os.lstat(p)
                seen[p] = (st.st_mtime_ns, st.st_size)
    return seen


def test_trc_w2_the_newest_manifest_decides_and_the_card_counts_the_others(tmp_path):
    bt = _trees()
    main = _repo(tmp_path)
    a = _worktree(main, tmp_path / "wt" / "a")
    b = _worktree(main, tmp_path / "wt" / "b")
    c = _worktree(main, tmp_path / "wt" / "c")
    _issue(a, "shared", 1_000)
    _issue(b, "shared", 3_000)
    _issue(c, "shared", 2_000)
    _issue(main, "solo", 1_000)

    sources, trees = bt.list_sources(main, True)

    shared = [s for s in sources if s["slug"] == "shared"]
    assert len(shared) == 1
    assert shared[0]["tree"] == "b"
    assert shared[0]["also_in"] == 2
    assert shared[0]["refused"] is None
    assert shared[0]["task_dir"] == str(b / ".compass" / "work" / "shared")
    assert shared[0]["tree_root"] == str(b)
    solo = [s for s in sources if s["slug"] == "solo"]
    assert [(s["tree"], s["also_in"]) for s in solo] == [(THIS, 0)]
    assert solo[0]["tree_root"] == str(main)
    assert trees["read"] == [THIS, "a", "b", "c"]


def test_trc_w2_a_tie_goes_to_this_checkout_then_to_the_first_path(tmp_path):
    bt = _trees()
    main = _repo(tmp_path)
    a = _worktree(main, tmp_path / "wt" / "a")
    b = _worktree(main, tmp_path / "wt" / "b")
    _issue(b, "tied", 5_000)
    _issue(a, "tied", 5_000)
    _issue(main, "tied", 5_000)
    _issue(b, "elsewhere", 5_000)
    _issue(a, "elsewhere", 5_000)

    sources, _ = bt.list_sources(main, True)

    chosen = _by_slug(sources)
    assert chosen["tied"]["tree"] == THIS
    assert chosen["tied"]["also_in"] == 2
    assert chosen["elsewhere"]["tree"] == "a"
    assert chosen["elsewhere"]["also_in"] == 1


def test_trc_w2_a_copy_with_no_manifest_ranks_below_any_copy_with_one(tmp_path):
    bt = _trees()
    main = _repo(tmp_path)
    a = _worktree(main, tmp_path / "wt" / "a")
    b = _worktree(main, tmp_path / "wt" / "b")
    _issue(a, "half", 1_000)
    _issue(b, "half", manifest=False)

    sources, _ = bt.list_sources(main, True)

    chosen = _by_slug(sources)
    assert chosen["half"]["tree"] == "a"
    assert chosen["half"]["also_in"] == 1


def test_trc_w2_trees_with_the_same_folder_name_are_told_apart_by_path(tmp_path):
    bt = _trees()
    main = _repo(tmp_path)
    one = _worktree(main, tmp_path / "x" / "side")
    two = _worktree(main, tmp_path / "y" / "side")
    _issue(one, "p", 1_000)
    _issue(two, "q", 1_000)

    sources, trees = bt.list_sources(main, True)

    chosen = _by_slug(sources)
    assert chosen["p"]["tree"] == str(one)
    assert chosen["q"]["tree"] == str(two)
    assert trees["read"] == [THIS, str(one), str(two)]


def test_trc_w2_a_project_below_the_git_top_is_read_below_each_tree_top(tmp_path):
    bt = _trees()
    main = _repo(tmp_path)
    side = _worktree(main, tmp_path / "wt" / "side")
    for tree in (main, side):
        (tree / "app").mkdir()
    _issue(main / "app", "here", 1_000)
    _issue(side / "app", "there", 1_000)
    _issue(side, "wrong-level", 1_000)

    sources, _ = bt.list_sources(main / "app", True)

    chosen = _by_slug(sources)
    assert sorted(chosen) == ["here", "there"]
    assert chosen["there"]["tree_root"] == str(side / "app")
    assert chosen["here"]["tree_root"] == str(main / "app")


def test_trc_w3_prunable_and_missing_trees_are_skipped_and_counted(tmp_path):
    bt = _trees()
    main = _repo(tmp_path)
    ok = _worktree(main, tmp_path / "wt" / "ok")
    gone = _worktree(main, tmp_path / "wt" / "gone")
    locked = _worktree(main, tmp_path / "wt" / "locked")
    _issue(main, "m", 1_000)
    _issue(ok, "o", 1_000)
    _issue(gone, "g", 1_000)
    _issue(locked, "l", 1_000)
    _git(main, "worktree", "lock", str(locked))
    shutil.rmtree(gone)
    shutil.rmtree(locked)

    listing = _git(main, "worktree", "list", "--porcelain")
    assert "prunable" in listing  # the fixture holds a prunable tree

    sources, trees = bt.list_sources(main, True)

    assert trees["read"] == [THIS, "ok"]
    assert trees["skipped"] == 2
    assert trees["note"] is None
    assert sorted(s["slug"] for s in sources) == ["m", "o"]


def test_trc_w7_outside_a_git_repository_this_checkout_is_read_and_the_note_says_why(tmp_path):
    bt = _trees()
    plain = tmp_path / "plain"
    _issue(plain, "only", 1_000)

    sources, trees = bt.list_sources(plain, True)

    assert [(s["slug"], s["tree"]) for s in sources] == [("only", THIS)]
    assert trees["read"] == [THIS]
    assert trees["skipped"] == 0
    assert trees["note"]
    assert "not a git repository" in trees["note"].lower()


def test_trc_w7_a_machine_without_git_reads_this_checkout_and_says_so(tmp_path, monkeypatch):
    bt = _trees()
    main = _repo(tmp_path)
    _issue(main, "only", 1_000)
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    sources, trees = bt.list_sources(main, True)

    assert [s["slug"] for s in sources] == ["only"]
    assert trees["read"] == [THIS]
    assert trees["note"] and "git" in trees["note"].lower()


def test_trc_w7_without_worktrees_git_is_not_asked_and_there_is_no_note(tmp_path, monkeypatch):
    bt = _trees()
    main = _repo(tmp_path)
    side = _worktree(main, tmp_path / "wt" / "side")
    _issue(main, "mine", 1_000)
    _issue(side, "theirs", 1_000)
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    sources, trees = bt.list_sources(main, False)

    assert [(s["slug"], s["also_in"]) for s in sources] == [("mine", 0)]
    assert trees == {"read": [THIS], "skipped": 0, "note": None}


def test_trc_w10_a_link_leading_out_of_a_tree_is_refused_and_never_read(tmp_path, monkeypatch):
    bt = _trees()
    main = _repo(tmp_path)
    side = _worktree(main, tmp_path / "wt" / "side")
    outside = tmp_path / "outside" / "escape"
    outside.mkdir(parents=True)
    (outside / "manifest.yml").write_text("slug: escape\n", encoding="utf-8")
    work = side / ".compass" / "work"
    work.mkdir(parents=True)
    os.symlink(outside, work / "escape")
    _issue(main, "escape", 1_000)
    opened = []
    real_open = builtins.open
    monkeypatch.setattr(
        builtins, "open",
        lambda f, *a, **k: (opened.append(str(f)), real_open(f, *a, **k))[1])

    sources, _ = bt.list_sources(main, True)

    refused = [s for s in sources if s["refused"]]
    assert [(s["slug"], s["tree"]) for s in refused] == [("escape", "side")]
    assert "leads out of the tree" in refused[0]["refused"]
    # The refused folder takes no part in choosing a copy: the readable copy
    # in this checkout is still the one shown.
    assert _by_slug(sources)["escape"]["tree"] == THIS
    assert not [p for p in opened if "outside" in p]


def test_trc_w10_a_manifest_that_is_a_link_out_of_the_tree_is_refused(tmp_path):
    bt = _trees()
    main = _repo(tmp_path)
    side = _worktree(main, tmp_path / "wt" / "side")
    target = tmp_path / "elsewhere.yml"
    target.write_text("slug: sneaky\n", encoding="utf-8")
    folder = side / ".compass" / "work" / "sneaky"
    folder.mkdir(parents=True)
    os.symlink(target, folder / "manifest.yml")

    sources, _ = bt.list_sources(main, True)

    assert [(s["slug"], s["tree"]) for s in sources if s["refused"]] == [("sneaky", "side")]
    assert not _by_slug(sources)


def test_trc_w10_a_link_that_stays_inside_the_tree_is_followed(tmp_path):
    bt = _trees()
    main = _repo(tmp_path)
    side = _worktree(main, tmp_path / "wt" / "side")
    real = _issue(side, "real", 1_000)
    os.symlink(real, side / ".compass" / "work" / "alias")

    sources, _ = bt.list_sources(main, True)

    assert sorted(_by_slug(sources)) == ["alias", "real"]
    assert not [s for s in sources if s["refused"]]


def test_trc_w5_one_folder_per_distinct_slug_chosen_by_stat_with_no_manifest_opened(tmp_path, monkeypatch):
    bt = _trees()
    main = _repo(tmp_path)
    trees = [_worktree(main, tmp_path / "wt" / n) for n in ("a", "b", "c")]
    newest = {}
    for i in range(50):
        slug = f"issue-{i:02d}"
        winner = i % 3
        newest[slug] = trees[winner].name
        for j, tree in enumerate(trees):
            _issue(tree, slug, 9_000 if j == winner else 1_000 + j)
    opened = []
    real_open = builtins.open
    monkeypatch.setattr(
        builtins, "open",
        lambda f, *a, **k: (opened.append(str(f)), real_open(f, *a, **k))[1])

    sources, _ = bt.list_sources(main, True)

    assert not [p for p in opened if p.endswith("manifest.yml")]
    assert len(sources) == 50
    assert {s["slug"]: s["tree"] for s in sources} == newest
    assert {s["also_in"] for s in sources} == {2}


def test_trc_w12_a_slug_done_in_this_checkout_is_never_statted_in_another_tree(tmp_path, monkeypatch):
    bt = _trees()
    main = _repo(tmp_path)
    side = _worktree(main, tmp_path / "wt" / "side")
    _issue(main, "finished", 1_000)
    _issue(side, "finished", 9_000)
    _issue(main, "elsewhere", 1_000)
    _issue(side, "elsewhere", 9_000)
    # A skipped slug that is a link out of the tree is not even looked at.
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, side / ".compass" / "work" / "finished-link")
    seen = []
    real_stat, real_lstat = os.stat, os.lstat
    monkeypatch.setattr(os, "stat", lambda p, *a, **k: (seen.append(str(p)), real_stat(p, *a, **k))[1])
    monkeypatch.setattr(os, "lstat", lambda p, *a, **k: (seen.append(str(p)), real_lstat(p, *a, **k))[1])

    sources, _ = bt.list_sources(main, True, skip_slugs={"finished", "finished-link"})

    monkeypatch.undo()
    chosen = _by_slug(sources)
    assert chosen["finished"]["tree"] == THIS
    assert chosen["finished"]["also_in"] == 0
    assert chosen["elsewhere"]["tree"] == "side"
    assert not [s for s in sources if s["slug"] == "finished-link"]
    side_seen = [p for p in seen if str(side) in p or "/side/" in p]
    assert side_seen, "the observer must see the other tree's reads"
    assert not [p for p in seen if "finished" in p and "/side/" in p]
    assert not [p for p in seen if "finished-link" in p]


def test_trc_w2_listing_changes_nothing_in_any_tree(tmp_path):
    bt = _trees()
    main = _repo(tmp_path)
    side = _worktree(main, tmp_path / "wt" / "side")
    _issue(main, "m", 1_000)
    _issue(side, "s", 1_000)
    before = _snapshot(main, side)

    bt.list_sources(main, True)

    assert _snapshot(main, side) == before
