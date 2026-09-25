#!/usr/bin/env python3
# =============================================================================
# compass - binding a test record to the tree it ran on
# =============================================================================
# A green record proves a command passed once. Without a name for the tree it
# ran on, code can change after the green and the record still clears
# `suite-passed`. So every red, green and acceptance record carries two ids,
# and `evidence-matches-tree` compares them with the tree now, or, for a
# landed issue, with the commit that landed it.
#
# `tree_id` is the git tree id of the tracked files on disk, plus the
# untracked files the issue lists in `changed_files`, leaving out `.compass/`
# and `docs/compass/`: a project may commit those, and the CLI writes them
# after it names the tree, so a green would never match. Any other tracked
# edit makes the record stale. It is built from a copy of the real index, so
# git re-hashes only the files that changed.
#
# `changes_id` is a tree of the issue's own files: its `changed_files` and the
# test files its scenarios declare, which a record marks with
# `changes_scope`. A landed issue is judged by it: the commit that landed the
# issue also carries its artifacts, and HEAD moves on afterwards, but the
# issue's own files in that commit must be the files that were tested. A
# declared test counts even when `changed_files` does not list it, because
# the green stood on it. Re-running the suite on any checkout where
# they are the same clears a mismatch.
#
# WHAT IT DOES NOT PROVE. The ids are written by the process that ran the test
# and are covered by the record's digest. They show which tree a record
# claims; they do not prove a trusted runner made the claim.
#
# DEPENDENCY: standard library (os, re, shutil, subprocess, tempfile) and
# compass_pkg.core, check_results and red_first. tdd.py imports from here, so
# this module must not import tdd.py.
# =============================================================================
"""Which tree a test record ran on, and whether that is still the tree."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile

from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.core import CompassError, find_upwards, load_manifest
from compass_pkg.red_first import load_record

#: Paths a record cannot affect and the CLI rewrites after naming the tree.
_OUTSIDE_THE_TREE = (".compass", "docs/compass")

_COMMIT_ID = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")


def _git(args, cwd, env=None):
    # Claimed paths are file names, never pathspec magic: `:x.py` means a
    # file called `:x.py`.
    env = dict(env or os.environ, GIT_LITERAL_PATHSPECS="1")
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, timeout=60, env=env)
    except (OSError, subprocess.SubprocessError):
        return None


def _ok(result):
    return result is not None and result.returncode == 0


def _toplevel(project_root):
    top = _git(["rev-parse", "--show-toplevel"], project_root)
    return os.path.realpath(top.stdout.strip()) if _ok(top) else None


def _relative(top, project_root, paths):
    """Claimed paths, relative to the repository top, that exist as regular
    files inside it."""
    root = os.path.realpath(project_root)
    out = []
    for rel in paths:
        full = os.path.join(root, rel)
        if os.path.islink(full) or not os.path.isfile(full):
            continue
        full = os.path.realpath(full)
        if os.path.commonpath([top, full]) != top:
            continue
        out.append(os.path.relpath(full, top))
    return out


def _in_temp_index(top, steps, seed=None):
    """Run git `steps` against a temporary index, seeded from `seed` if
    given, and return the tree it writes, or None. The real index - what the
    user has staged - is never touched."""
    with tempfile.TemporaryDirectory() as tmp:
        index = os.path.join(tmp, "index")
        if seed and os.path.isfile(seed):
            shutil.copyfile(seed, index)
        env = dict(os.environ, GIT_INDEX_FILE=index)
        for args, required in steps:
            done = _git(args, top, env)
            if required and not _ok(done):
                return None
        tree = _git(["write-tree"], top, env)
    return tree.stdout.strip() if _ok(tree) and tree.stdout.strip() else None


def work_tree_id(project_root, claimed=()):
    """`tree_id`: tracked files on disk plus the claimed untracked files,
    without `.compass/` and `docs/compass/`. None outside a git repository or
    on any git failure."""
    top = _toplevel(project_root)
    if top is None:
        return None
    real_index = _git(["rev-parse", "--path-format=absolute", "--git-path",
                       "index"], top)
    seed = real_index.stdout.strip() if _ok(real_index) else None
    head = _git(["rev-parse", "--verify", "-q", "HEAD"], top)
    steps = []
    if not (seed and os.path.isfile(seed)):
        steps.append((["read-tree", "HEAD"] if _ok(head)
                      else ["read-tree", "--empty"], True))
    steps.append((["add", "-u", "--", "."], True))
    for rel in _relative(top, project_root, claimed):
        # An ignored path is refused by `git add` and stays out.
        steps.append((["add", "--", rel], False))
    for rel in _OUTSIDE_THE_TREE:
        steps.append((["rm", "--cached", "-r", "-q", "--ignore-unmatch", "--",
                       rel], True))
    return _in_temp_index(top, steps, seed)


def changes_id(project_root, claimed=()):
    """`changes_id`: a tree of the claimed files alone, as they are on disk."""
    top = _toplevel(project_root)
    if top is None:
        return None
    steps = [(["read-tree", "--empty"], True)]
    steps += [(["add", "--", rel], False)
              for rel in _relative(top, project_root, claimed)]
    return _in_temp_index(top, steps)


def _changes_id_at(project_root, commit, claimed):
    """The same tree, built from the claimed files as `commit` holds them."""
    top = _toplevel(project_root)
    if top is None:
        return None
    root = os.path.realpath(project_root)
    steps = [(["read-tree", "--empty"], True)]
    for rel in claimed:
        path = os.path.relpath(os.path.join(root, rel), top)
        entry = _git(["ls-tree", commit, "--", path], top)
        if not _ok(entry) or not entry.stdout.strip():
            continue
        meta, _, name = entry.stdout.strip().partition("\t")
        mode, kind, blob = meta.split()
        if kind == "blob":
            steps.append((["update-index", "--add", "--cacheinfo",
                           "%s,%s,%s" % (mode, blob, name)], True))
    return _in_temp_index(top, steps)


def claimed_paths(task):
    return [e["path"] for e in (task.get("changed_files") or [])
            if isinstance(e, dict) and isinstance(e.get("path"), str)]


#: The `changes_scope` of a record whose `changes_id` covers the declared
#: tests too. A record without it was built from `changed_files` alone.
CHANGES_SCOPE = "changed-files-and-declared-tests"


def declared_test_paths(task):
    """The test files the issue's scenarios declare, as relative paths.

    A scenario names a test as `path::name`; the file is the part before
    `::`. An absolute path, or one that climbs out with `..`, is left out.
    """
    paths = []
    for scenario in task.get("scenarios") or []:
        if not isinstance(scenario, dict):
            continue
        for test in scenario.get("tests") or []:
            if not isinstance(test, str):
                continue
            path = test.split("::", 1)[0].strip()
            parts = path.replace("\\", "/").split("/")
            if path and not os.path.isabs(path) and ".." not in parts:
                paths.append(path)
    return paths


def changes_paths(task, record=None):
    """The files `changes_id` covers: `changed_files` and the declared tests,
    or, for a record built without `changes_scope`, `changed_files` alone."""
    claimed = claimed_paths(task)
    if record is not None and record.get("changes_scope") != CHANGES_SCOPE:
        return claimed
    seen, paths = set(), []
    for path in claimed + declared_test_paths(task):
        if path not in seen and not any(
                path == d or path.startswith(d + "/") for d in _OUTSIDE_THE_TREE):
            seen.add(path)
            paths.append(path)
    return paths


def ids_for(task_dir):
    """The two ids a record written for this issue now should carry, as a
    dict with only the ids git could name."""
    root = find_upwards(task_dir, ".compass")
    if not root:
        return {}
    try:
        task, _ = load_manifest(task_dir)
    except (CompassError, OSError, ValueError):
        task = {}
    task = task if isinstance(task, dict) else {}
    ids = {"tree_id": work_tree_id(root, claimed_paths(task)),
           "changes_id": changes_id(root, changes_paths(task))}
    ids = {k: v for k, v in ids.items() if v}
    if "changes_id" in ids:
        ids["changes_scope"] = CHANGES_SCOPE
    return ids


def _newest_bound_record(task, task_dir):
    """The newest test-run record that carries a tree id, as (path, record).
    Only the newest is judged: it is the run the issue ships on."""
    root = os.path.realpath(task_dir)
    newest = None
    for entry in task.get("evidence") or []:
        if not isinstance(entry, dict) or entry.get("type") != "test-run":
            continue
        full = os.path.realpath(os.path.join(task_dir, entry.get("path") or ""))
        if os.path.commonpath([root, full]) != root:
            continue
        record = load_record(full)
        if not record.get("tree_id") or not isinstance(record.get("timestamp"), str):
            continue
        if newest is None or record["timestamp"] > newest[1]["timestamp"]:
            newest = (entry.get("path"), record)
    return newest


def _check_landed(task, root, path, record):
    land = task.get("land_commit")
    if not land:
        return NOTHING_TO_CHECK, ("landed with no land_commit recorded, so "
                                  "there is no landed tree to compare")
    # All zeros is git's null id, which no commit ever has.
    if not isinstance(land, str) or not _COMMIT_ID.match(land) \
            or set(land) == {"0"}:
        return False, ("land_commit %r is not a commit id - ship-commit writes "
                       "the full hexadecimal id of the commit it made" % (land,))
    found = _git(["rev-parse", "--verify", "-q", "--end-of-options",
                  land + "^{commit}"], root)
    if not _ok(found):
        return NOTHING_TO_CHECK, ("land_commit %s is not in this clone - a "
                                  "squash merge or a shallow clone - so the "
                                  "landed files cannot be compared" % land[:12])
    if not record.get("changes_id"):
        return NOTHING_TO_CHECK, ("%s carries no changes_id, so the issue's "
                                  "own files cannot be compared" % path)
    landed = _changes_id_at(root, land, changes_paths(task, record))
    if landed is None:
        return False, ("the files this issue changed could not be read from "
                       "land_commit %s" % land[:12])
    if landed != record["changes_id"]:
        return False, ("%s tested this issue's changed files as tree %s, but "
                       "the commit that landed them (%s) holds tree %s: the "
                       "landed files are not the tested files"
                       % (path, record["changes_id"][:12], land[:12],
                          landed[:12]))
    return True, ("%s tested the files the landing commit %s holds"
                  % (path, land[:12]))


def _check_evidence_matches_tree(task, task_dir):
    """Is the newest test record still a record for this tree?

    For an issue in flight, the tree now; a mismatch fails only once every
    gate has passed, because a record goes stale on every edit while the work
    is under way. For a landed issue, the issue's own files in the commit
    `ship-commit` recorded.
    """
    newest = _newest_bound_record(task, task_dir)
    if newest is None:
        return NOTHING_TO_CHECK, ("no test record carries a tree id - it was "
                                  "written before records named their tree, "
                                  "or outside a git repository")
    path, record = newest
    root = find_upwards(task_dir, ".compass") or task_dir
    if task.get("status") == "landed":
        return _check_landed(task, root, path, record)

    gates = [g for g in task.get("gates") or [] if isinstance(g, dict)]
    ready = bool(gates) and all(g.get("status") == "pass" for g in gates)
    now = work_tree_id(root, claimed_paths(task))
    if now is None:
        why = "git cannot name the tree now, so %s cannot be compared" % path
        return (False, why) if ready else (NOTHING_TO_CHECK, why)
    if now == record["tree_id"]:
        return True, "%s was recorded on the tree as it is now" % path
    stale = ("%s is stale: the tree changed after it was recorded - a file "
             "was edited, or the issue's changed_files grew, so it no longer "
             "shows this tree passing - re-run the suite with `compass "
             "tdd-green` before ship" % path)
    if ready:
        return False, stale
    return True, stale + " (a note until every gate has passed)"
