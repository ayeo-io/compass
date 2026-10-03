#!/usr/bin/env python3
# =============================================================================
# compass - which issue each Claude Code session is working on
# =============================================================================
# Two interactive sessions in one project share `.compass/current-task`.
# When one moves it, the other's edits were judged against an issue it was
# not working on, with no word said. A `sessions.json` file in `.compass/`
# records, per Claude Code session id, the issue the session last worked on.
# The pre-tool hook refuses an edit when the pointer no longer names that
# issue (`pointer-moved`), and `compass issue use <slug>` is how a session
# says which issue it means.
#
# A record older than LEASE_HOURS is stale and ignored: a session that ended
# hours ago is not working on anything. A session with COMPASS_ISSUE set, or
# a runtime that gives no session id, is not tracked at all.
#
# DEPENDENCY: standard library (datetime, json, os, tempfile) and
# compass_pkg.core.
# =============================================================================
"""The per-session issue record behind the `pointer-moved` refusal."""
from __future__ import annotations

import datetime
import json
import os
import tempfile

from compass_pkg.core import CompassError, _one_segment, find_compass_dir

#: How long a session's record counts.
LEASE_HOURS = 12

#: Where Claude Code puts the session id in a command's environment.
SESSION_ENV = "CLAUDE_CODE_SESSION_ID"


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _table_path(compass_dir):
    return os.path.join(compass_dir, "sessions.json")


def _load(compass_dir):
    try:
        with open(_table_path(compass_dir), encoding="utf-8") as fh:
            table = json.load(fh)
    except (OSError, ValueError):
        return {}
    return table if isinstance(table, dict) else {}


def _save(compass_dir, table):
    """Written to a temporary file and moved into place, so a reader never
    sees half a table."""
    fd, tmp = tempfile.mkstemp(dir=compass_dir, prefix=".sessions-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(table, fh, indent=2, sort_keys=True)
    os.replace(tmp, _table_path(compass_dir))


def _fresh(entry):
    try:
        at = datetime.datetime.fromisoformat(str(entry.get("at")))
    except ValueError:
        return False
    if at.tzinfo is None:
        at = at.replace(tzinfo=datetime.timezone.utc)
    return _now() - at < datetime.timedelta(hours=LEASE_HOURS)


def record(compass_dir, session, slug):
    """Note that `session` works on `slug` now."""
    if not session:
        return
    table = _load(compass_dir)
    table[session] = {"issue": slug, "at": _now().isoformat(timespec="seconds")}
    _save(compass_dir, table)


def check(compass_dir, session, slug):
    """`ok`, recording the session on `slug`; or `moved:<previous>` when
    the session's fresh record names another issue than the pointer now
    does. A moved pointer is not recorded: the session must say which issue
    it means, with `compass issue use`."""
    entry = _load(compass_dir).get(session)
    if isinstance(entry, dict) and _fresh(entry) and entry.get("issue") \
            and entry.get("issue") != slug:
        return f"moved:{entry['issue']}"
    record(compass_dir, session, slug)
    return "ok"


def cmd_issue_use(args):
    compass_dir = find_compass_dir()
    slug = _one_segment(args.slug, "compass issue use")
    if not os.path.isdir(os.path.join(compass_dir, "work", slug)):
        raise CompassError(f"compass issue use: no issue '{slug}' under "
                           f".compass/work/.")
    with open(os.path.join(compass_dir, "current-task"), "w",
              encoding="utf-8") as fh:
        fh.write(slug + "\n")
    session = os.environ.get(SESSION_ENV, "")
    record(compass_dir, session, slug)
    print(f"compass issue use: the current issue is {slug}"
          + (" for this session." if session else "."))
    return 0


def register(issue_subparsers):
    """Add `compass issue use` to the `issue` verb."""
    u = issue_subparsers.add_parser(
        "use", help="make an issue the current one, for this session",
        description="Write the issue to .compass/current-task and record it "
                    "as the one this Claude Code session works on. After "
                    "another session moved the pointer, this is how a "
                    "session says which issue it means: the pre-tool hook "
                    "refuses its edits (pointer-moved) until it does.")
    u.add_argument("slug", help="the issue to work on")
    u.set_defaults(func=cmd_issue_use, output_kind="hand-off")
