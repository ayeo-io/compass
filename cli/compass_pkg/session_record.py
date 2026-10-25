# compass_pkg.session_record - add a session id to an issue's usage.sessions
"""Record that a Claude Code session worked on an issue.

The pre-tool hook calls `record` the first time it sees a session id for an
issue: a `grep` in the hook finds an id already recorded, so a recorded id
starts no Python process. `compass ship-commit` later reads the transcripts
of every session listed here (`issue_usage`).

The hook judges every tool call, so this never stops one:

- it never raises: any fault leaves the manifest as it was;
- it never waits: it tries the issue's manifest lock once, without blocking,
  and does nothing when another writer holds it, so a later call records the
  id;
- it changes only `usage.sessions`: the id is inserted into the file's text,
  and the result is parsed and compared with the data it was read from, so
  no other byte moves;
- it replaces the file atomically, and just before the rename it compares
  the bytes on disk with those it read. A writer that changed the file in
  between, without the lock, is merged: the insert is made again on the new
  bytes, up to three times.

`core.save_manifest` holds the same lock while it writes, so a CLI command
and the hook never replace the manifest at the same time. Owning decision:
`architecture/decisions/ADR-063-*.md`.
"""
# DEPENDENCY: standard library (copy, os, re); the bundled PyYAML;
# compass_pkg.atomic_io, core (the manifest's name) and session_lease (the
# session table), which the hook's one process imports as other readers do.
from __future__ import annotations

import copy
import os
import re

import yaml

from compass_pkg.atomic_io import atomic_write_text

try:
    import fcntl
except ImportError:                                     # pragma: no cover
    fcntl = None                                        # no file locks here

#: The issue's manifest lock, beside `.render.lock` and `.generation.lock`.
#: `core.MANIFEST_LOCK` names the same file.
LOCK = ".manifest.lock"

#: How many times a write is made again after another writer changed the file.
TRIES = 3

#: A session id goes into a regular expression, a file name and the manifest,
#: so only an id of this shape is recorded (the shape `session_usage` reads).
_SESSION_ID = re.compile(r"[A-Za-z0-9_-]+")


class _Changed(Exception):
    """The file changed on disk after it was read."""


def record(task_dir, session, via="pointer") -> None:
    """Add `session` to the `usage.sessions` of the issue in `task_dir`, or do
    nothing. `via` says how the hook resolved the issue: `env` (COMPASS_ISSUE),
    `pointer` (`.compass/current-task`) or `tree` (the issue of another
    tree the edit names, ADR-074). Only `pointer` reads the session table.
    Never raises."""
    try:
        _record(os.path.abspath(str(task_dir)), session, via)
    except Exception:                                   # noqa: BLE001 - never stop a tool call
        return


def _read(path):
    """The manifest's bytes: the read every insert starts from."""
    with open(path, "rb") as fh:
        return fh.read()


def _record(task_dir, session, via):
    if not isinstance(session, str) or not _SESSION_ID.fullmatch(session):
        return
    if via == "pointer" and _moved(task_dir, session):
        return
    from compass_pkg.core import manifest_path
    path = manifest_path(task_dir)
    # A rename would replace a file the person made read-only.
    if not os.path.isfile(path) or not os.access(path, os.W_OK):
        return
    with open(os.path.join(task_dir, LOCK), "a") as lock:
        if fcntl is not None:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return                                  # another writer holds it
        try:
            for _ in range(TRIES):
                data = _read(path)
                text = _inserted(data, session)
                if text is None:
                    return

                def unchanged(_tmp, read=data):
                    with open(path, "rb") as fh:
                        if fh.read() != read:
                            raise _Changed
                try:
                    atomic_write_text(path, text, newline="", before_replace=unchanged)
                    return
                except _Changed:
                    continue
        finally:
            if fcntl is not None:
                fcntl.flock(lock, fcntl.LOCK_UN)


def _moved(task_dir, session):
    """True when the session's live entry in the session table that
    `session_lease` keeps names another issue: another session moved the
    pointer, and this session's work is elsewhere. A copied entry (another
    root, or none) is not live. Read without the table's lock; a table that
    cannot be read moves nothing."""
    from compass_pkg import session_lease
    entry = session_lease.live_entry(os.path.dirname(os.path.dirname(task_dir)), session)
    return bool(entry) and bool(entry.get("issue")) and entry["issue"] != os.path.basename(task_dir)


def _inserted(data, session):
    """The manifest's text with `session` added to `usage.sessions`, or None
    when it is there already or the file has a form this does not edit."""
    text = data.decode("utf-8")
    body = yaml.safe_load(text)
    if not isinstance(body, dict):
        return None
    usage = body.get("usage")
    if usage is not None and not isinstance(usage, dict):
        return None
    sessions = (usage or {}).get("sessions")
    if sessions is not None and not isinstance(sessions, list):
        return None
    if session in (sessions or []):
        return None
    # The item as PyYAML writes it, quoted when the id would read as a number.
    item = "  " + yaml.safe_dump([session], default_flow_style=False)
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    if "usage" not in body:
        lines.append("usage:\n  sessions:\n" + item)
    else:
        start = next((i for i, line in enumerate(lines)
                      if re.match(r"usage:\s*$", line)), None)
        if start is None:
            return None                                 # a flow mapping or another form
        end = next((i for i in range(start + 1, len(lines))
                    if lines[i].strip() and not lines[i].startswith(" ")), len(lines))
        head = next((i for i in range(start + 1, end)
                     if re.match(r"  sessions:\s*$", lines[i])), None)
        if sessions is None:
            lines.insert(start + 1, "  sessions:\n" + item)
        elif head is None:
            return None
        else:
            last = head
            while last + 1 < end and lines[last + 1].startswith("  - "):
                last += 1
            lines.insert(last + 1, item)
    result = "".join(lines)
    expected = copy.deepcopy(body)
    if not isinstance(expected.get("usage"), dict):
        expected["usage"] = {}
    expected["usage"]["sessions"] = list(sessions or []) + [session]
    return result if yaml.safe_load(result) == expected else None
