# compass_pkg.request_link - who asked for an issue, and the link to the request
"""The request link and the requester of an issue, and the check
`request-recorded` (#356).

Every delivery row of `evidence_required` owes the token `request`; a spike
owes nothing. An issue owes it only when its stored `evidence_required` lists
it, so an issue assessed before the token existed gains no row. The manifest
holds the record:

    request:
      link: https://github.com/acme/widgets/issues/42
      requester: Dana Smith
      recorded_at: 2026-11-07T10:00:00Z

`compass issue link set --request <url> --requester <name>` writes it, and
`compass quick-fix start` takes the same two flags. A GitHub issue named with
`--github` also counts as the link: its URL is written to `request.link` when
none is recorded.

The requester is free text that the session records. It is a claim, not an
approval: no approval rule reads it, and Compass makes no `gh` call to
confirm it. The check is not a stop. It fails until both parts are recorded,
`compass next` asks for them first, and no command refuses on it. A change
with no request to link is excused by a waiver of the check that a person
approves (ADR-094), so it is not in the check set's `never_waived`.
"""
# DEPENDENCY: standard library (os, re, unicodedata); compass_pkg.check_results and
# core (CompassError, now_iso). It imports no command module, so the check registry
# can import it, and issue_link and quick_fix_cmd call `record`.
from __future__ import annotations

import os
import re
import unicodedata

from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.core import CompassError, now_iso

#: The token every delivery issue owes.
TOKEN = "request"
#: The check of the token.
CHECK = "request-recorded"
#: The manifest key that holds the record.
KEY = "request"
#: The longest link and requester Compass stores.
LINK_MAX = 2000
REQUESTER_MAX = 100
#: A request link: an https URL with no white space.
_HTTPS = re.compile(r"https://[^\s/?#]+[^\s]*")


def owed(task):
    """True when the issue's stored `evidence_required` lists the token."""
    owed_tokens = task.get("evidence_required") if isinstance(task, dict) else None
    return isinstance(owed_tokens, list) and TOKEN in owed_tokens


def _has_control(text):
    return any(unicodedata.category(ch).startswith("C") for ch in text)


def issue_url(repo, number):
    """The URL of a GitHub issue."""
    return f"https://github.com/{repo}/issues/{number}"


def parse_link(text, verb):
    """`(link, github target or None)` for a `--request` value, or a CompassError
    that names the forms it takes. `owner/repo#N` and a GitHub issue URL also
    give the GitHub issue, so the caller writes `github` as `--github` does."""
    from compass_pkg.issue_link import parse_target
    value = text if isinstance(text, str) else ""
    target = parse_target(value)
    if target is not None:
        return issue_url(*target), target
    if (len(value) <= LINK_MAX and not _has_control(value)
            and _HTTPS.fullmatch(value)):
        return value, None
    raise CompassError(
        f"{verb}: --request {value[:80]!r} is not a request link; use an https:// URL "
        f"with no spaces, at most {LINK_MAX} characters, or owner/repo#number. "
        "Nothing was written.")


def parse_requester(text, verb):
    """The requester as one stripped line, or a CompassError."""
    value = text.strip() if isinstance(text, str) else ""
    if not value or len(value) > REQUESTER_MAX or _has_control(value):
        raise CompassError(
            f"{verb}: --requester must name who asked, on one line of at most "
            f"{REQUESTER_MAX} characters with no control characters. Nothing was written.")
    return value


def parse(request, requester, verb):
    """`(link, target, requester)` from the two flag values, each None when not
    given. Checked before anything is written."""
    link, target = parse_link(request, verb) if request is not None else (None, None)
    who = parse_requester(requester, verb) if requester is not None else None
    return link, target, who


def record(task, link=None, requester=None):
    """Write the parts given into the manifest's `request` record, keeping a
    part already recorded that is not given. Return the record, or None when
    nothing was given."""
    if link is None and requester is None:
        return None
    held = task.get(KEY) if isinstance(task.get(KEY), dict) else {}
    held = dict(held)
    if link is not None:
        held["link"] = link
    if requester is not None:
        held["requester"] = requester
    held["recorded_at"] = now_iso()
    task[KEY] = held
    return held


def link_from_github(task, target):
    """After `--github`, the issue's URL as `request.link` when no link is held."""
    held = task.get(KEY) if isinstance(task.get(KEY), dict) else {}
    if not held.get("link"):
        record(task, link=issue_url(*target))


def recorded(task):
    """`(link, requester)` the manifest holds, each '' when missing. A linked
    GitHub issue gives the link when `request.link` is missing."""
    held = task.get(KEY) if isinstance(task.get(KEY), dict) else {}
    link = held.get("link") if isinstance(held.get("link"), str) else ""
    requester = held.get("requester") if isinstance(held.get("requester"), str) else ""
    if not link.strip():
        github = task.get("github")
        if (isinstance(github, dict) and isinstance(github.get("repo"), str)
                and isinstance(github.get("number"), int)):
            link = issue_url(github["repo"], github["number"])
    return link.strip(), requester.strip()


def command(task_dir):
    """The command that records the request."""
    slug = os.path.basename(os.path.normpath(task_dir)) if task_dir else "<slug>"
    return (f"compass issue link set --issue {slug} --request <url> "
            f"--requester <name>")


def _check_request_recorded(task, task_dir):
    """The verdict of `request-recorded` 1.0.0 (#356): both the link and the
    requester on record pass; a missing part fails and is named."""
    if not owed(task):
        return NOTHING_TO_CHECK, "this issue does not owe a request link"
    link, requester = recorded(task)
    if link and requester:
        return True, (f"requested by {requester} (as the session recorded it, a claim), "
                      f"{link}")
    missing = " and ".join(part for part, held in (("the request link", link),
                                                    ("the requester", requester))
                           if not held)
    return False, f"no request on record: missing {missing}; run `{command(task_dir)}`"
