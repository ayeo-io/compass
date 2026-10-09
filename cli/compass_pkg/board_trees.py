"""Find the issue folders the delivery board reads, in this checkout and in
other git worktrees.

`list_sources` returns one source per slug: a dict that says where the issue
folder is and which tree it came from. It does not open or parse any
manifest and it writes nothing. It only lists folders and reads
modification times, so reading dozens of worktrees stays affordable.

With worktrees, the folder shown for a slug is the one whose manifest was
changed most recently. On a tie this checkout wins, then the tree whose path
sorts first. A copy with no manifest ranks below every copy that has one. A
slug listed in `skip_slugs` (done in this checkout) is read from this
checkout only: its folders in other trees are never listed or statted.

Nothing here follows a link out of a tree. A folder in another tree that
leads out of that tree comes back as a source with `refused` set, and takes
no part in choosing a copy.

The source dict (technical design 5.2):

    slug       the folder name
    task_dir   absolute path of the issue folder (not read when refused)
    tree       "this checkout", or the other tree's folder name (its full
               path when two trees share a folder name)
    tree_root  the project root inside that tree
    also_in    how many other trees hold a readable folder with this slug
    refused    a reason the folder is not read, or None

The `trees` summary: {"read": [labels], "skipped": int, "note": str or None}.
`note` says why worktrees could not be listed.
"""
from __future__ import annotations

import os
import stat
import subprocess

from compass_pkg.core import manifest_path

THIS_CHECKOUT = "this checkout"
_GIT_TIMEOUT_SECONDS = 60


def _git(project_root, *args):
    """Run git with a fixed argument list and no shell. Returns (ok, text)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        done = subprocess.run(
            ["git", "-C", str(project_root), *args],
            capture_output=True, text=True, env=env,
            timeout=_GIT_TIMEOUT_SECONDS)
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


def _worktree_entries(listing):
    """Parse `git worktree list --porcelain` into dicts of path and flags."""
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


def _inside(path, top):
    return path == top or path.startswith(top.rstrip(os.sep) + os.sep)


def _folder_names(work_dir):
    try:
        return sorted(os.listdir(work_dir))
    except OSError:
        return []


def _this_checkout(project_root):
    """slug -> task_dir for each folder under this checkout's work folder."""
    work = os.path.join(project_root, ".compass", "work")
    return {name: os.path.join(work, name) for name in _folder_names(work)
            if os.path.isdir(os.path.join(work, name))}


def _manifest_mtime(task_dir, tree_real=None):
    """(mtime_ns or None, refusal or None) for a folder's manifest.

    With `tree_real` set, a manifest that is a link leading out of that tree
    is refused rather than read.
    """
    path = manifest_path(task_dir)
    try:
        mode = os.lstat(path).st_mode
    except OSError:
        return None, None
    if stat.S_ISLNK(mode):
        if tree_real is not None and not _inside(os.path.realpath(path), tree_real):
            return None, "its manifest leads out of the tree"
        try:
            return os.stat(path).st_mtime_ns, None
        except OSError:
            return None, None
    return os.lstat(path).st_mtime_ns, None


def _other_tree(tree_path, tree_root, label, skip_slugs):
    """(copies, refused) for one other tree: copies is slug -> (mtime, task_dir)."""
    copies, refused = {}, []
    tree_real = os.path.realpath(tree_path)
    work = os.path.join(tree_root, ".compass", "work")
    if not os.path.isdir(work) or not _inside(os.path.realpath(work), tree_real):
        return copies, refused
    for name in _folder_names(work):
        if name in skip_slugs:
            continue
        task_dir = os.path.join(work, name)
        try:
            mode = os.lstat(task_dir).st_mode
        except OSError:
            continue
        if stat.S_ISLNK(mode):
            if not _inside(os.path.realpath(task_dir), tree_real):
                refused.append((name, task_dir, "its folder leads out of the tree"))
                continue
            if not os.path.isdir(task_dir):
                continue
        elif not stat.S_ISDIR(mode):
            continue
        mtime, why = _manifest_mtime(task_dir, tree_real)
        if why:
            refused.append((name, task_dir, why))
            continue
        copies[name] = (mtime, task_dir)
    return copies, refused


def _source(slug, task_dir, tree, tree_root, also_in, refused=None):
    return {"slug": slug, "task_dir": task_dir, "tree": tree,
            "tree_root": tree_root, "also_in": also_in, "refused": refused}


def list_sources(project_root, worktrees, skip_slugs=frozenset()):
    """Return (sources, trees). See the module docstring."""
    project_root = os.path.abspath(str(project_root))
    skip_slugs = frozenset(skip_slugs)
    here = _this_checkout(project_root)
    trees = {"read": [THIS_CHECKOUT], "skipped": 0, "note": None}

    others = []  # (label, tree_path, tree_root)
    if worktrees:
        ok, top = _git(project_root, "rev-parse", "--show-toplevel")
        listing = ""
        if ok:
            ok, listing = _git(project_root, "worktree", "list", "--porcelain")
        if ok:
            others = _plan_trees(project_root, top.strip(), listing, trees)
        else:
            reason = top if not listing else listing
            trees["note"] = f"worktrees could not be listed: {reason.strip()}"

    # copies[slug] -> list of (mtime, tree_path, label, tree_root, task_dir)
    copies, refused_sources = {}, []
    for label, tree_path, tree_root in others:
        found, refused = _other_tree(tree_path, tree_root, label, skip_slugs)
        for slug, (mtime, task_dir) in found.items():
            copies.setdefault(slug, []).append(
                (mtime, tree_path, label, tree_root, task_dir))
        for slug, task_dir, why in refused:
            refused_sources.append(
                _source(slug, task_dir, label, tree_root, 0, why))

    sources = []
    for slug in sorted(set(here) | set(copies)):
        candidates = list(copies.get(slug, []))
        if slug in here:
            if slug in copies:  # only now does this copy's age matter
                mtime, _ = _manifest_mtime(here[slug])
                candidates.append(
                    (mtime, "", THIS_CHECKOUT, project_root, here[slug]))
            else:
                sources.append(_source(slug, here[slug], THIS_CHECKOUT,
                                       project_root, 0))
                continue
        # Newest first; on a tie this checkout (empty path), then the path
        # that sorts first. A copy with no manifest ranks below the rest.
        best = min(candidates, key=lambda c: (
            -(c[0] if c[0] is not None else -1), c[1]))
        _, _, label, tree_root, task_dir = best
        sources.append(_source(slug, task_dir, label, tree_root,
                               len(candidates) - 1))

    sources.extend(sorted(refused_sources,
                          key=lambda s: (s["slug"], s["tree"])))
    return sources, trees


def _plan_trees(project_root, top, listing, trees):
    """Choose the other trees to read; fill `trees` with the read and skipped."""
    this_real = os.path.realpath(top)
    rel = os.path.relpath(os.path.realpath(project_root), this_real)
    entries = [e for e in _worktree_entries(listing)
               if os.path.realpath(e["path"]) != this_real]
    names = [os.path.basename(e["path"].rstrip(os.sep)) for e in entries]
    plan, labels = [], []
    for entry, name in zip(entries, names):
        if entry["bare"] or entry["prunable"] or not os.path.isdir(entry["path"]):
            trees["skipped"] += 1
            continue
        label = entry["path"] if names.count(name) > 1 else name
        tree_root = entry["path"] if rel == "." else os.path.join(entry["path"], rel)
        plan.append((label, entry["path"], tree_root))
        labels.append(label)
    trees["read"] = [THIS_CHECKOUT] + sorted(labels)
    return sorted(plan, key=lambda p: p[1])
