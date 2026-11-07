"""The land commit of an issue: the one place every reader gets it from.

A manifest can name its land commit in two ways:

- a stored `land_commit` string. `compass ship-commit` writes it when the
  issue record stays out of the code commit, and so does every issue landed
  before 9.0.0;
- `landed_with_record: true`. The record was committed with the code, so the
  manifest cannot name the commit that holds it. The land commit is the
  newest commit that added the manifest's current `land_timestamp` line.

The second way is read from git, so it follows the commit onto the default
branch. After a squash merge, git finds the squash commit, which adds the
line; after a rebase, the rebased commit; after a merge commit, the branch
commit that the default branch reaches. A stored id would still name the
commit on the branch, which a squash merge leaves off the default branch.

Only a manifest that holds `landed_with_record: true` is read from git. A
landed manifest without the key (every archived issue, and the tracked
example `examples/quick-fix-typo`) keeps the verdict it had.
"""

from __future__ import annotations

import os
import subprocess

import yaml

from compass_pkg import status_words

# Characters that carry a meaning in a POSIX extended regular expression,
# which `git log -G` uses.
_ERE_SPECIAL = set("\\.[]()*+?{}|^$")


def land_commit(task, task_dir):
    """The full id of the commit the issue landed in, or None.

    The first argument is the loaded manifest, and the second the issue
    folder that holds `manifest.yml`. A stored `land_commit` is returned as it is, even when a
    hand edit made it something other than a commit id, so the readers that
    judge it (`binding._check_landed`) still see the bad value. None when the
    issue has not landed, when it landed with no `land_commit` and no
    committed record, or when this clone does not hold the commit that added
    the `land_timestamp` line (a shallow clone).
    """
    stored = task.get("land_commit")
    if stored:
        return stored
    if task.get("landed_with_record") is not True or not status_words.is_completed(task):
        return None
    stamp = task.get("land_timestamp")
    if not isinstance(stamp, str) or not stamp:
        return None
    return _commit_that_added(task_dir, stamp)


def _commit_that_added(task_dir, stamp):
    """The newest commit, from HEAD, that added `land_timestamp: <stamp>` to
    the manifest in `task_dir` and whose copy of the manifest still holds it."""
    pattern = "^land_timestamp: .?%s.?$" % _ere_escape(stamp)
    listed = _git(["log", "--format=%H", "-G", pattern, "--", "manifest.yml"], task_dir)
    if listed is None or listed.returncode != 0:
        return None
    shallow = _shallow_commits(task_dir)
    for commit in listed.stdout.split():
        # A shallow clone shows its oldest commit as if it added every file,
        # so a match there does not say which commit added the line.
        if commit in shallow:
            return None
        if _holds_stamp(task_dir, commit, stamp):
            return commit
    return None


def _holds_stamp(task_dir, commit, stamp):
    shown = _git(["show", "%s:./manifest.yml" % commit], task_dir)
    if shown is None or shown.returncode != 0:
        return False
    try:
        copy = yaml.safe_load(shown.stdout)
    except yaml.YAMLError:
        return False
    return isinstance(copy, dict) and copy.get("land_timestamp") == stamp


def _shallow_commits(task_dir):
    found = _git(["rev-parse", "--git-path", "shallow"], task_dir)
    if found is None or found.returncode != 0:
        return set()
    path = os.path.join(task_dir, found.stdout.strip())
    try:
        with open(path, encoding="utf-8") as fh:
            return set(fh.read().split())
    except OSError:
        return set()


def _ere_escape(text):
    return "".join("\\" + ch if ch in _ERE_SPECIAL else ch for ch in text)


def _git(args, cwd):
    # The manifest path is a file name, never pathspec magic.
    env = dict(os.environ, GIT_LITERAL_PATHSPECS="1")
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, timeout=60, env=env)
    except (OSError, subprocess.SubprocessError):
        return None
