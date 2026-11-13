"""The issue record of a committed landing: written, staged and checked by `compass ship-commit`.

In committed mode (`record_mode`) an issue's folder ships in the same commit
as its code (#356). `compass ship-commit` then does what the agent must not
do by hand: it stages `.compass/work/<slug>/` and the issue's documents
folder. This module holds those steps, so `manifest.cmd_land_commit` keeps
its order of refusals and only calls them.

- `Record.land` writes the landing into the manifest in one save (status
  `completed`, `land_timestamp`, `landed_with_record: true`, no
  `land_commit`), writes `trail.md`, and stages the record. The manifest
  cannot name the commit that holds it, so `landing.land_commit` reads that
  commit from git later.
- `Record.refresh` writes `trail.md` again when a pre-commit step changed a
  file the trail names, and stages it, so the committed pair matches.
- `Record.take_back` restores the manifest and `trail.md` and unstages what
  `land` staged, when no commit was made.
- `Record.unland` restores the working manifest after a commit that holds
  the landed record failed a check after the commit.
- `Record.changed_in(commit)` names each file `trail.md` names whose copy
  in the commit differs from its sum line: a git hook that staged a change
  during the commit.

`git add` of a folder skips the files `.compass/work/.gitignore` names
(generations, lock files, markers, a pending approval request). A folder git
ignores as a whole is not staged and not force-added.

DEPENDENCY: standard library (hashlib, os, re, subprocess) and compass_pkg
(core, init_cmd, record_mode, status_words, trail, evidence_sums).
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess

from compass_pkg import record_mode, status_words
from compass_pkg.core import (CompassError, docs_dir, find_upwards, load_manifest,
                              manifest_path, now_iso, save_manifest)

#: A sum line of `trail.md`: an optional escape flag, the digest, two spaces, the name.
_SUM = re.compile(r"^(\\?)([0-9a-f]{64})  (.+)$")


def is_committed(task_dir, verb="compass ship-commit"):
    """True when the issue's record is committed with its code. Raises
    `CompassError` when `record.commit` is not a boolean, so a landing refuses
    before it writes or stages anything.

    When git ignores the issue folder and no setting chose the mode, it
    prints one line naming the rule: the project's ignore rule wins, and
    `record.commit: false` says so without the line."""
    root = find_upwards(task_dir, ".compass")
    if not root:
        return False
    found = record_mode.mode(root, task_dir)
    if found.mode == record_mode.COMMITTED:
        return True
    if " is ignored by " in (found.reason or ""):
        print(f"{verb}: the issue record stays out of the commit, because "
              f"{found.reason}. Set `record.commit: false` to keep it out "
              f"without this line.")
    return False


def write_trail(task_dir):
    """Write `trail.md`, or nothing for a spike, which has no trail. Returns
    True when it wrote."""
    from compass_pkg import trail
    try:
        trail.write(task_dir)
    except CompassError:
        return False
    return True


def _git(args, cwd):
    # The paths this module passes are names, never pathspec magic.
    return subprocess.run(["git", "--literal-pathspecs", *args], cwd=cwd,
                          capture_output=True)


def _read(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _restore(path, data):
    if data is None:
        try:
            os.remove(path)
        except OSError:
            pass
        return
    with open(path, "wb") as fh:
        fh.write(data)


def _names(out):
    return {n for n in out.decode("utf-8", "surrogateescape").split("\0") if n}


class Record:
    """One issue's record, landed in committed mode from the work tree `cwd`."""

    def __init__(self, cwd, task_dir):
        from compass_pkg import trail
        self.cwd = cwd
        self.task_dir = os.path.realpath(str(task_dir))
        self.root = os.path.realpath(find_upwards(self.task_dir, ".compass"))
        self.manifest = manifest_path(self.task_dir)
        self.trail = trail.path_of(self.task_dir)
        self._held = {p: _read(p) for p in (self.manifest, self.trail)}
        self._staged_before = self._staged()
        self.written = False

    # --- the paths -------------------------------------------------------------------------

    def _ignored(self, path):
        return _git(["check-ignore", "-q", "--", path], self.cwd).returncode == 0

    def folders(self):
        """The record's paths that git does not ignore: the issue folder, the
        documents folder when it exists, and both ignore files.

        `.compass/.gitignore` holds the per-machine lines `compass init` adds
        in committed mode. The agent never stages `.compass/`, so without this
        the file stays untracked and a clone does not skip those files."""
        out = [self.task_dir]
        docs = os.path.join(self.root, docs_dir(self.task_dir))
        if os.path.isdir(docs) and not self._ignored(docs + "/"):
            out.append(docs)
        for ignore in (os.path.join(self.root, ".compass", "work", ".gitignore"),
                       os.path.join(self.root, ".compass", ".gitignore")):
            if os.path.isfile(ignore) and not self._ignored(ignore):
                out.append(ignore)
        return out

    def _staged(self):
        return _names(_git(["diff", "--cached", "--name-only", "-z"], self.cwd).stdout)

    # --- the landing -----------------------------------------------------------------------

    def land(self):
        """Write the landing into the manifest, write `trail.md` and stage the record."""
        task = load_manifest(self.task_dir)[0]
        status_words.close(task, status_words.COMPLETED)
        task["land_timestamp"] = now_iso()
        task["landed_with_record"] = True
        # The manifest cannot hold the id of the commit that holds it; a stored
        # value from an earlier landing would win over the one git gives.
        task.pop("land_commit", None)
        save_manifest(task, self.manifest)
        self.written = True
        write_trail(self.task_dir)
        self.stage()

    def stage(self):
        """Stage the record. The ignore file is completed first, so the
        per-checkout files stay out even where `compass init` never ran."""
        from compass_pkg.init_cmd import write_ignore_files
        write_ignore_files(self.root)
        for path in self.folders():
            _git(["add", "--", path], self.cwd)

    def refresh(self):
        """Write `trail.md` again and stage the record when a file the trail
        names no longer has the digest it states, as after a pre-commit step
        rewrote a record file. Returns True when it wrote."""
        from compass_pkg import trail
        if not self.written or not os.path.isfile(self.trail):
            return False
        try:
            if trail.first_difference(self.task_dir) is None:
                return False
        except CompassError:
            return False
        write_trail(self.task_dir)
        self.stage()
        return True

    def take_back(self):
        """No commit was made: restore the manifest and `trail.md` and unstage
        the record paths this landing staged."""
        if not self.written:
            return
        top = self._top()
        # A folder ends in `/`, so `fix-a/` never matches `fix-ab/`.
        prefixes = tuple(os.path.relpath(p, top).replace(os.sep, "/")
                         + ("/" if os.path.isdir(p) else "") for p in self.folders())
        newly = sorted(p for p in self._staged() - self._staged_before
                       if p.startswith(prefixes))
        for path, data in self._held.items():
            _restore(path, data)
        if newly:
            if _git(["rev-parse", "--verify", "-q", "HEAD"], top).returncode == 0:
                _git(["reset", "-q", "--", *newly], top)
            else:
                _git(["rm", "-q", "--cached", "--", *newly], top)
        self.written = False

    def unland(self):
        """A commit that holds the landed record failed a check after the
        commit: put the manifest back as it was before the landing in the
        working copy, and write `trail.md` again to match it."""
        _restore(self.manifest, self._held[self.manifest])
        write_trail(self.task_dir)

    # --- after the commit ------------------------------------------------------------------

    def _top(self):
        found = _git(["rev-parse", "--show-toplevel"], self.cwd)
        return os.path.realpath(found.stdout.decode().strip()) if found.returncode == 0 \
            else self.root

    def changed_in(self, commit):
        """`(path, why)` for each file the committed `trail.md` names whose
        copy in `commit` differs from its sum line; `why` is "changed" or
        "missing". Empty when the commit holds no trail."""
        from compass_pkg.evidence_sums import _unescape
        top = self._top()
        rel = os.path.relpath(self.trail, top).replace(os.sep, "/")
        shown = _git(["show", f"{commit}:{rel}"], top)
        if shown.returncode != 0:
            return []
        out = []
        for line in shown.stdout.decode("utf-8", "replace").splitlines():
            found = _SUM.match(line)
            if not found:
                continue
            flag, digest, name = found.groups()
            path = _unescape(flag, name)
            blob = _git(["cat-file", "blob", f"{commit}:{path}"], top)
            if blob.returncode != 0:
                out.append((path, "missing"))
            elif hashlib.sha256(blob.stdout).hexdigest() != digest:
                out.append((path, "changed"))
        return out


def warnings(changed):
    """The lines `ship-commit` prints for `Record.changed_in`. They never
    change its exit code: the commit stands, and the person decides."""
    lines = []
    for path, why in changed:
        if why == "changed":
            lines.append(f"compass ship-commit: a git hook changed {path} during the commit; "
                         f"`trail.md` no longer matches it.")
        else:
            lines.append(f"compass ship-commit: `trail.md` names {path}, which the commit "
                         f"does not hold.")
    return lines
