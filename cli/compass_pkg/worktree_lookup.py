# compass_pkg.worktree_lookup - find an issue in any git worktree, and the common store
"""One lookup for every question that crosses git worktrees: which folder holds an
issue, and where the delegation store is (issue delegation-everywhere).

`list_worktrees` runs `git worktree list --porcelain` once and returns the
trees a command may read: bare and prunable entries and missing folders are
skipped. When git cannot list them, only this checkout is returned and the
listing carries a note that every refusal repeats.

`find_issue` finds the one folder that holds an issue by its exact slug. It
refuses a slug that two trees hold (`HeldTwice`) and one that none holds
(`NotFound`). A folder, or a manifest, that leads out of its tree by a link is
not found.

`common_store` finds the one delegation store that every worktree of the
repository shares: `.compass/delegations/` of the main checkout, at the same
path inside it as the session's project is inside its own worktree.

Standard library only, because a hook imports it.
"""
# DEPENDENCY: standard library (dataclasses, os, subprocess); compass_pkg.core
# for the manifest names only, read when an issue folder is checked.
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

GIT_TIMEOUT_SECONDS = 60
#: What the refusals say when a listing could not be made.
ONLY_HERE = "so only this checkout was searched"


@dataclass(frozen=True)
class Tree:
    """One worktree. `top` is the folder git lists; `project` is the Compass
    project inside it, at the same path as the session's own."""
    top: str
    project: str
    is_main: bool
    is_this: bool


@dataclass(frozen=True)
class Listing:
    """The trees to search, the main checkout first when git listed it, and a
    note when only this checkout was searched."""
    trees: tuple
    note: str | None = None


@dataclass(frozen=True)
class Store:
    """The common store. `folder` is `<main>/<project path>/.compass/delegations`
    and `project` is the folder whose `compass.yml` names the approver, or both
    are None with `why_none` saying why there is no store."""
    folder: str | None
    project: str | None
    why_none: str = ""


class NotFound(Exception):
    """No tree holds the issue. `searched` is the list of work folders looked in."""

    def __init__(self, slug, searched, note=None):
        super().__init__(slug)
        self.slug, self.searched, self.note = slug, tuple(searched), note


class HeldTwice(Exception):
    """Two or more trees hold the issue. `folders` names each one."""

    def __init__(self, slug, folders):
        super().__init__(slug)
        self.slug, self.folders = slug, tuple(folders)


def parse_porcelain(listing):
    """`git worktree list --porcelain` as dicts of `path`, `bare` and `prunable`."""
    entries = []
    for block in listing.split("\n\n"):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines or not lines[0].startswith("worktree "):
            continue
        flags = {ln.split(" ", 1)[0] for ln in lines[1:]}
        entries.append({
            "path": lines[0][len("worktree "):],
            "bare": "bare" in flags,
            "prunable": "prunable" in flags,
        })
    return entries


def run_git(folder, *args, timeout=GIT_TIMEOUT_SECONDS):
    """Run git with a fixed argument list and no shell. Returns (ok, text)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        done = subprocess.run(["git", "-C", str(folder), *args], capture_output=True,
                              text=True, env=env, timeout=timeout)
    except FileNotFoundError:
        return False, "git is not installed or not on the path"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"git could not run: {exc}"
    if done.returncode != 0:
        lines = (done.stderr or done.stdout).strip().splitlines()
        reason = lines[0] if lines else f"git exited with {done.returncode}"
        if reason.startswith("fatal: "):
            reason = reason[len("fatal: "):]
        return False, reason
    return True, done.stdout


def _inside(path, top):
    return path == top or path.startswith(top.rstrip(os.sep) + os.sep)


def _repo_top(start):
    """The first folder at or above `start` that holds `.git`, and whether
    that is a folder (a main checkout) or a file (a linked worktree)."""
    node = os.path.realpath(start)
    while True:
        marker = os.path.join(node, ".git")
        if os.path.isdir(marker):
            return node, True
        if os.path.exists(marker):
            return node, False
        up = os.path.dirname(node)
        if up == node:
            return None, False
        node = up


def project_folder(cwd):
    """The Compass project a working folder is in: the nearest folder at or
    above it that holds `.compass`, stopping at the top of the repository, else
    the folder itself."""
    node = os.path.abspath(cwd)
    while True:
        if (os.path.isdir(os.path.join(node, ".compass"))
                or os.path.exists(os.path.join(node, ".git"))):
            return node
        up = os.path.dirname(node)
        if up == node:
            return os.path.abspath(cwd)
        node = up


def _here_only(project, why):
    project = os.path.abspath(project)
    tree = Tree(project, project, True, True)
    return Listing((tree,), f"the worktrees could not be listed ({why}), "
                            f"{ONLY_HERE}")


def list_worktrees(project, timeout=GIT_TIMEOUT_SECONDS):
    """The trees a command may read. `project` is the session's project folder."""
    top, _ = _repo_top(project)
    if top is None:
        return _here_only(project, "this is not a git repository")
    ok, text = run_git(top, "worktree", "list", "--porcelain", timeout=timeout)
    if not ok:
        return _here_only(project, text.strip())
    rel = os.path.relpath(os.path.realpath(project), top)
    entries = parse_porcelain(text)
    trees = []
    for number, entry in enumerate(entries):
        path = entry["path"]
        if entry["bare"] or entry["prunable"] or not os.path.isdir(path):
            continue
        inner = path if rel == "." else os.path.join(path, rel)
        trees.append(Tree(path, inner, number == 0,
                          os.path.realpath(path) == top))
    if not any(t.is_this for t in trees):
        here = os.path.abspath(project)
        trees.append(Tree(top, here, False, True))
    return Listing(tuple(trees))


def _has_manifest(task_dir, tree_real):
    """True when the folder holds a manifest that stays inside the tree."""
    from compass_pkg.core import MANIFEST_NAMES
    for name in MANIFEST_NAMES:
        path = os.path.join(task_dir, name)
        if os.path.isfile(path):
            return _inside(os.path.realpath(path), tree_real)
    return False


def _issue_in(tree, slug):
    """The folder of `slug` in one tree, or None. The name must match exactly,
    with no case folding, and neither the folder nor its manifest may lead out
    of the tree."""
    work = os.path.join(tree.project, ".compass", "work")
    try:
        names = os.listdir(work)
    except OSError:
        return None
    if slug not in names:
        return None
    task_dir = os.path.join(work, slug)
    tree_real = os.path.realpath(tree.top)
    if not os.path.isdir(task_dir) or not _inside(os.path.realpath(task_dir), tree_real):
        return None
    return task_dir if _has_manifest(task_dir, tree_real) else None


def find_issue(listing, slug):
    """The folder that holds `slug`. Raises `NotFound` or `HeldTwice`."""
    found = []
    for tree in listing.trees:
        task_dir = _issue_in(tree, slug)
        if task_dir:
            found.append(task_dir)
    if len(found) > 1:
        raise HeldTwice(slug, found)
    if not found:
        raise NotFound(slug, [os.path.join(t.project, ".compass", "work")
                              for t in listing.trees], listing.note)
    return found[0]


def common_store(start, timeout=GIT_TIMEOUT_SECONDS):
    """The common store for a session whose project folder is `start`."""
    start = os.path.abspath(start)
    top, is_dir = _repo_top(start)
    if top is None:
        return Store(os.path.join(start, ".compass", "delegations"), start)
    rel = os.path.relpath(os.path.realpath(start), top)
    main = top
    if not is_dir:
        ok, text = run_git(top, "worktree", "list", "--porcelain", timeout=timeout)
        entries = parse_porcelain(text) if ok else []
        if not entries:
            return Store(None, None, f"the worktrees could not be listed"
                                     f"{': ' + text.strip() if not ok else ''}, so Compass "
                                     f"cannot find the common store")
        if entries[0]["bare"]:
            return Store(None, None, f"the main entry {entries[0]['path']} is a bare "
                                     f"repository, which has no common store")
        main = entries[0]["path"]
    project = main if rel == "." else os.path.join(main, rel)
    if not os.path.isdir(project):
        return Store(None, None, f"{project} does not exist in the main checkout, so "
                                 f"the common store has no folder")
    return Store(os.path.join(project, ".compass", "delegations"), project)
