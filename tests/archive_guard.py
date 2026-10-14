"""A pytest plugin: a test session must leave this checkout's archive as it found it.

The archive is the issue records in `.compass/work` and the issue documents in
`docs/compass`. Compass keeps them out of git, so a test that writes into them
damages a maintainer's real records and nothing in git can restore them.

The plugin takes a digest of both folders (every file's path and content) when
the session starts and again when it ends. If the two differ, it names the
paths that were added, changed or removed (at most 20) and fails the session.
Because it looks at the whole session, it covers every test, not a list of
modules.

Under xdist the digests are taken in the controlling process only. It starts
before any worker does and ends after the last has stopped, so it sees every
worker's writes. A worker (a process with `workerinput`) does nothing.

The checkout is found from this file's own path, not from pytest's rootdir, so
a run started from another folder with `-p archive_guard` still guards it.

`tests/conftest.py` imports the two hooks, so every suite run is guarded. A
planted run outside `tests/` loads this module with `-p archive_guard`.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FOLDERS = (ROOT / ".compass" / "work", ROOT / "docs" / "compass")
MOST_PATHS_NAMED = 20

_START = pytest.StashKey[dict]()


def archive_digest() -> dict:
    """{path relative to this checkout: sha256 of the content} for every file
    under the archive folders. A folder that does not exist is empty."""
    found = {}
    for folder in FOLDERS:
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            try:
                if path.is_file():
                    found[path.relative_to(ROOT).as_posix()] = hashlib.sha256(
                        path.read_bytes()).hexdigest()
            except OSError:
                continue        # gone between the listing and the read: not a file now
    return found


def _in_worker(config) -> bool:
    return hasattr(config, "workerinput")


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    # tryfirst: xdist starts its workers in its own hook for this event.
    if not _in_worker(session.config):
        session.config.stash[_START] = archive_digest()


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    before = config.stash.get(_START, None)
    if _in_worker(config) or before is None:
        return
    after = archive_digest()
    if after == before:
        return
    lines = (["added: " + p for p in sorted(set(after) - set(before))]
             + ["changed: " + p for p in sorted(p for p in before if p in after
                                                 and before[p] != after[p])]
             + ["removed: " + p for p in sorted(set(before) - set(after))])
    shown = lines[:MOST_PATHS_NAMED]
    if len(lines) > len(shown):
        shown.append("... and %d more" % (len(lines) - len(shown)))
    message = ["The test session changed this checkout's archive (.compass/work or "
               "docs/compass), which no test may do:"] + ["  " + line for line in shown]
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    for line in message:
        if reporter is not None:
            reporter.write_line(line, red=True)
        else:
            print(line, file=sys.stderr)
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
