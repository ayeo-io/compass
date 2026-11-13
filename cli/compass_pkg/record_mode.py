#!/usr/bin/env python3
# =============================================================================
# compass - whether an issue's record is committed with its code
# =============================================================================
# An issue folder (`.compass/work/<slug>/`) is the record of how the change
# was made. In committed mode it ships in the same commit as the code (#356),
# so a reviewer reads it in the pull request. In kept-out mode it stays out
# of the project's git history, and `compass record sync` is the only copy
# kept anywhere else.
#
# `mode(project_root, task_dir)` decides, in this order:
#
#   record.commit: false                       kept out
#   record.commit: true                        committed, then the git rows
#   record.remote set, record.commit not set   kept out: the project chose a
#                                              separate record store (VD-031)
#   neither set                                committed, then the git rows
#   not inside a git work tree                 kept out
#   git ignores the issue folder               kept out: the project's own
#                                              ignore rule wins; nothing is
#                                              force-added and nothing refused
#
# This module also holds the ignore lines Compass writes, and the helper that
# appends them, which `session_lease` shares. It stages nothing.
#
# DEPENDENCY: standard library (os, subprocess) and compass_pkg
# (core, project_settings, read lazily so the hook path stays light).
# =============================================================================
"""The record mode: whether an issue's folder is committed with its code."""
from __future__ import annotations

import os
import subprocess
from collections import namedtuple

COMMITTED = "committed"
KEPT_OUT = "kept-out"

#: The mode and, for kept out, the one line that says why. `reason` is None
#: in committed mode.
Mode = namedtuple("Mode", "mode reason")

#: `.compass/work/.gitignore`, written in every project. These files are
#: per-checkout state: generations are rebuilt from the manifest, lock files
#: and markers belong to one checkout, `.tdd-state.json` is a local run
#: counter, and a pending approval request holds a live single-use nonce.
WORK_IGNORE_HEADER = (
    "# Written by Compass. Each issue folder is the record that ships with the code;",
    "# these files are per-checkout state and stay out (#356).",
)
WORK_IGNORE_LINES = (
    "*/generations/",
    "*/.*.lock",
    "*/.red",
    "*/.acceptance",
    "*/start-state.json",
    "*/evidence/.tdd-state.json",
    "*/approval-requests/pending/",
)

#: The lines added to `.compass/.gitignore` in committed mode only. In kept-out
#: mode the project already keeps `.compass/` state out its own way, and a
#: tracked `.compass/.gitignore` must not change under it.
COMPASS_IGNORE_HEADER = (
    "# Written by Compass. Per-machine state that stays out of the commit (#356).",
)
COMPASS_IGNORE_LINES = (
    "delegations/",
    "cache/",
    "private/",
    "current-task",
    "interruptions.log",
)


def add_ignore_lines(path, lines, header=()):
    """Append each of `lines` that `path` does not hold yet, after `header`
    when the file does not hold its first line. Returns True when it wrote.

    The person's own lines are kept as they are, and a second run adds
    nothing. A blank line separates the new lines from what was there."""
    try:
        with open(path, encoding="utf-8") as fh:
            held = fh.read().splitlines()
    except OSError:
        held = []
    wanted = [line for line in lines if line not in held]
    if not wanted:
        return False
    if header and header[0] not in held:
        wanted = list(header) + wanted
    with open(path, "a", encoding="utf-8") as fh:
        if held and held[-1]:
            fh.write("\n")
        fh.write("\n".join(wanted) + "\n")
    return True


def _record_settings(project_root):
    from compass_pkg import project_settings
    from compass_pkg.core import CompassError
    record = project_settings.settings(project_root).get("record")
    if record is None:
        return {}
    if not isinstance(record, dict):
        raise CompassError("%s must be a mapping." % project_settings.named(
            project_root, "record"))
    commit = record.get("commit")
    if commit is not None and not isinstance(commit, bool):
        raise CompassError("%s must be true or false, not %r." % (
            project_settings.named(project_root, "record"), commit))
    return record


def _git(args, cwd):
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None


def _ignored_by(project_root, rel):
    """`<source>:<line>:<pattern>` of the rule that ignores `rel`, or None."""
    found = _git(["check-ignore", "-v", "--", rel], project_root)
    if found is None or found.returncode != 0 or not found.stdout.strip():
        return None
    return found.stdout.strip().split("\t", 1)[0]


def mode(project_root, task_dir=None):
    """The record mode of the issue folder `task_dir`, or of `.compass/work/`
    when no issue is named. Raises `CompassError` when `record.commit` is not
    a boolean."""
    record = _record_settings(project_root)
    commit = record.get("commit")
    if commit is False:
        return Mode(KEPT_OUT, "record.commit is false")
    remote = record.get("remote")
    if commit is None and isinstance(remote, str) and remote.strip():
        return Mode(KEPT_OUT, "the record is synced to %s; set record.commit "
                              "to choose" % remote.strip())
    inside = _git(["rev-parse", "--is-inside-work-tree"], project_root)
    if inside is None or inside.returncode != 0 \
            or inside.stdout.strip() != "true":
        return Mode(KEPT_OUT, "not a git repository")
    folder = task_dir or os.path.join(project_root, ".compass", "work")
    rel = os.path.relpath(os.path.abspath(folder),
                          os.path.abspath(project_root)).replace(os.sep, "/")
    rule = _ignored_by(project_root, rel + "/")
    if rule:
        return Mode(KEPT_OUT, "%s is ignored by %s" % (rel, rule))
    return Mode(COMMITTED, None)
