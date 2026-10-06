# compass_pkg.start_state - what a quick fix's tree held when it started
"""What `quick-fix start` records about the working tree, and what has
changed since. `quick-fix finish` reads it to commit only the fix's own
files; `compass acceptance start` reads it to refuse a validation declared
after the change. Kept apart from `quick_fix_cmd` so `tdd` can use it
without importing the verb that imports `tdd`.
"""
# DEPENDENCY: standard library (json, os, subprocess).
from __future__ import annotations

import json
import os
import subprocess


# Directories a test run or an interpreter writes, never a person. A
# project with no .gitignore for them still shows them as untracked, and
# they change between the green and the commit: traced and committed, they
# make the landed files differ from the tested ones and fail the check on
# the issue just landed.
_GENERATED_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache",
                   ".ruff_cache", ".tox", ".nox"}


def _is_generated(path):
    """True for caches, and for the living spec files: ship-commit derives
    those at landing, after the green, so tracing them would always name an
    older version than the one that lands."""
    from compass_pkg.flow import LIVING_SPEC_FILES
    parts = path.split("/")
    return (any(p in _GENERATED_DIRS for p in parts[:-1])
            or path.endswith((".pyc", ".pyo"))
            or path in LIVING_SPEC_FILES)


def _git_changed_paths(root):
    """Every changed path git sees, relative to `root`, the project root
    (QFG-2), less generated caches. Read with `-z`, so a name with spaces,
    quotes or non-ASCII characters arrives as the file's real name, not
    git's escaped form. `git status` names paths from the repository top,
    so joining them to `root` assumes `.compass/` sits there, as `compass
    init` puts it. The guard below never fires in that case; it is not a
    check that the assumption holds."""
    out = subprocess.run(
        ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout
    fields = out.split("\0")
    paths, i = [], 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        status, raw = entry[:2], entry[3:]
        if "R" in status or "C" in status:
            i += 1  # the next field is the old name of a rename or copy
        rel = os.path.relpath(os.path.normpath(os.path.join(root, raw)), root)
        if rel == os.pardir or rel.startswith(os.pardir + os.sep):
            continue  # outside the project root - not this issue's to trace
        rel = rel.replace(os.sep, "/")
        if not _is_generated(rel):
            paths.append(rel)
    return paths


def _record_path(project_root, slug):
    """Where `start` keeps its record: inside the git directory (the
    worktree's own, in a worktree), where nothing is ever committed."""
    out = subprocess.run(
        ["git", "rev-parse", "--git-path",
         f"compass/start-state/{slug}.json"],
        cwd=project_root, capture_output=True, text=True, check=True).stdout
    return os.path.join(project_root, out.strip())


def _tracked_paths(project_root):
    """Every path git tracks, or an empty set when git cannot say."""
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=project_root,
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return set()
    return {p for p in out.split("\0") if p}


# Compass's own state under `.compass/`. A project that uses Compass commits
# `.compass/work/`, so being tracked does not make these the fix's change.
_STATE_PATHS = (".compass/work/", ".compass/flow/", ".compass/current-task",
                ".compass/sessions.json", ".compass/.sessions.lock",
                ".compass/interruptions.log")


def _is_issue_state(path, tracked):
    """Is `path` Compass's own state, kept out of a quick fix's commit? A
    path under `.compass/` is when it is one of `_STATE_PATHS` or git does
    not track it. Any other tracked file there, such as
    `.compass/config.yml`, is the project's own and is traced like any other
    change."""
    if not path.startswith(".compass/"):
        return False
    return path.startswith(_STATE_PATHS) or path not in tracked


def changed_since_start(project_root, slug, keep=()):
    """Uncommitted files changed since `quick-fix start`: staged, unstaged
    or new, from `git status`, so a `git add` does not hide a change.
    Commits are left out: a pull or a parallel session's commit after
    `start` is not this fix's change, and a quick fix commits only at
    `finish`. Files already changed at start, Compass's own records, the
    issue's documents and the paths in `keep` are left out too. Ignored
    paths are not seen. None when the issue has no start record (not a
    quick fix)."""
    try:
        with open(_record_path(project_root, slug), encoding="utf-8") as fh:
            record = json.load(fh)
        paths = set(_git_changed_paths(project_root))
    except (OSError, ValueError, AttributeError, subprocess.CalledProcessError):
        return None
    before = set(record.get("changed_before_start") or [])
    local_dirs = tuple(record.get("local_dirs_before_start") or [])
    tracked = _tracked_paths(project_root)
    return sorted(p for p in paths
                  if p not in before and p not in keep
                  and not _is_issue_state(p, tracked)
                  and not p.startswith("docs/compass/")
                  and not p.startswith(local_dirs))
