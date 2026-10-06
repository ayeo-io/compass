#!/usr/bin/env python3
# =============================================================================
# compass - a failure observed first
# =============================================================================
# A green record shows the suite passes; it does not show that a test ever
# failed. `suite-passed`, the check behind "tested before it lands"
# (guardrail `G1`), accepted any green, and an unbound green needs no red. So
# an issue could pass it having never seen a failure: 9 of 110 archived
# issues did, as the issue `unbound-green-needs-no-red` measured. This module
# holds the one extra condition `suite-passed` now applies.
#
# Kept apart from checks.py, which is near its line cap.
#
# It also gives the one verdict on an issue's red records that the pre-tool
# hook and `suite-passed` both use, so the two cannot disagree about what
# counts as a red.
#
# DEPENDENCY: standard library (datetime, hashlib, json, os, stat) and
# compass_pkg.core for the config reader. tdd.py imports from here, so this
# module must not import tdd.py.
# =============================================================================
"""Does an issue that declares scenarios show a failure observed first?"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import stat

from compass_pkg import project_settings
from compass_pkg.core import CompassError, find_upwards, load_yaml

#: Issues created on or after this date, or with evidence recorded on or
#: after it, must show a failure first. Issues created and worked before it
#: keep the result they had: their records say what was required when they
#: were written, and failing them now would rewrite that. A manifest with no
#: `created:` predates the field and counts as before, unless its evidence
#: is dated since.
RED_REQUIRED_FROM = datetime.date(2026, 9, 24)

#: The kinds `compass acceptance start` accepts, for work with no natural red.
#: Defined here, not in tdd.py, so the check and the verb read one list.
ACCEPTANCE_KINDS = ("validation", "refactor")


def _load(path):
    """A record's payload, or {} for anything that is not a JSON object in a
    regular file. A FIFO would block the read, and a symlink could stand
    another issue's record in for this one's."""
    try:
        mode = os.lstat(path).st_mode
    except OSError:
        return {}
    if not stat.S_ISREG(mode):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


#: The public name for other modules; `_load` stays for this module's own use.
load_record = _load


def _is_failed_run(record):
    """True only for what `compass tdd-red` writes: `passed` false and an
    integer exit code that is not 0. Either field alone is not enough - a
    green record with `passed` flipped still says exit code 0."""
    code = record.get("exit_code")
    return (record.get("passed") is False and isinstance(code, int)
            and not isinstance(code, bool) and code != 0)


def signed_since(task_dir, compass_dir=None):
    """The project's `records_signed_since` date, or None when it declares none.

    From that date on, a red record must carry the identity `compass tdd-red`
    stamps on it. A project that declares nothing keeps the older allowance
    for unstamped records.

    `compass_dir` names the project's `.compass/` when the caller has already
    resolved it, as the pre-tool hook has; the issue directory's own ancestors
    are the fallback.

    Returns None - no cutoff - only when the key is absent or empty, or when
    there is no config file. Anything else that cannot be read as a date,
    including a config file that does not parse, counts as a cutoff in the far
    past: a broken config must not turn the cutoff off without a word.
    """
    if compass_dir is None:
        root = find_upwards(task_dir, ".compass")
        if not root:
            return None
        compass_dir = os.path.join(root, ".compass")
    project_root = os.path.dirname(os.path.normpath(compass_dir))
    if project_settings.state_source(project_root) is None:
        return None
    try:
        config = project_settings.state(project_root)
    except (CompassError, OSError, ValueError):
        return datetime.date.min
    value = config.get("records_signed_since")
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return datetime.date.min


def content_digest(payload):
    """A stable digest over a record's content, excluding the digest itself.
    `compass tdd-red` stamps records with it, and `red_verdict` checks them
    with it, so writer and reader cannot drift apart."""
    body = {k: v for k, v in payload.items() if k != "content_digest"}
    encoded = json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _written_before(record, cutoff):
    """Does the record's own timestamp put it before the cutoff? A record
    with no readable timestamp is not."""
    try:
        written = datetime.date.fromisoformat(str(record.get("timestamp"))[:10])
    except ValueError:
        return False
    return written < cutoff


def red_verdict(task_dir, compass_dir=None):
    """The verdict on an issue's red records, as one word:

      ok               a failed run is on record and counts
      no-record        no red record file at all
      unsigned         failed runs are on record, but each lacks the identity
                       this project has required since `records_signed_since`
      no-valid-record  anything else: no failed run, or a stamped record
                       edited after it was written

    `compass tdd-red` writes `evidence/red.json` unbound and
    `evidence/red-<scenario>.json` bound. A red record is not registered in
    `evidence:`, so this reads the directory.
    """
    evidence = os.path.join(task_dir, "evidence")
    if os.path.islink(evidence):
        return "no-valid-record"
    try:
        names = sorted(os.listdir(evidence))
    except OSError:
        return "no-record"
    names = [n for n in names
             if n == "red.json" or (n.startswith("red-") and n.endswith(".json"))]
    if not names:
        return "no-record"
    cutoff = signed_since(task_dir, compass_dir)
    unsigned = False
    for name in names:
        record = _load(os.path.join(evidence, name))
        if not _is_failed_run(record):
            continue
        if record.get("content_digest"):
            if content_digest(record) == record["content_digest"]:
                return "ok"
            continue
        # Written before records carried an identity. Accepted unless the
        # project has declared a date from which every record must carry one.
        if cutoff is None or _written_before(record, cutoff):
            return "ok"
        unsigned = True
    return "unsigned" if unsigned else "no-valid-record"


def verdict_line(task_dir, compass_dir=None):
    """The verdict and the cutoff it applied, on one line, for the pre-tool
    hook: `unsigned 2026-09-24`. The hook prints the date from here rather
    than parsing the config itself, so the refusal names the date the reader
    actually used."""
    verdict = red_verdict(task_dir, compass_dir)
    if verdict != "unsigned":
        return verdict
    cutoff = signed_since(task_dir, compass_dir)
    shown = "an unreadable value" if cutoff == datetime.date.min else cutoff.isoformat()
    return "unsigned " + shown


def has_red(task_dir):
    """Is a failed run on record that counts? See `red_verdict`."""
    return red_verdict(task_dir) == "ok"


def _first_green(task, task_dir):
    """The earliest timestamp among the issue's green records that are not
    acceptance records, as an ISO string, or None."""
    root = os.path.realpath(task_dir)
    stamps = []
    for entry in task.get("evidence") or []:
        if not isinstance(entry, dict) or entry.get("type") != "test-run":
            continue
        full = os.path.realpath(os.path.join(task_dir, entry.get("path") or ""))
        if os.path.commonpath([root, full]) != root:
            continue
        record = _load(full)
        if record.get("kind") in ACCEPTANCE_KINDS:
            continue
        if isinstance(record.get("timestamp"), str):
            stamps.append(record["timestamp"])
    return min(stamps) if stamps else None


def _acceptance(task, task_dir):
    """Is an acceptance record among the issue's test-run evidence, and was
    it declared in time? Returns (counts, late) where `late` names a record
    declared after the first green, for the failure message.

    Only a path inside the issue directory counts. A record with no
    `declared_at` was written before records carried one, and counts as it
    did then."""
    root = os.path.realpath(task_dir)
    first_green = _first_green(task, task_dir)
    late = None
    for entry in task.get("evidence") or []:
        if not isinstance(entry, dict) or entry.get("type") != "test-run":
            continue
        full = os.path.realpath(os.path.join(task_dir, entry.get("path") or ""))
        if os.path.commonpath([root, full]) != root:
            continue
        record = _load(full)
        if record.get("kind") not in ACCEPTANCE_KINDS:
            continue
        declared = record.get("declared_at")
        if not isinstance(declared, str) or first_green is None \
                or declared < first_green:
            return True, None
        late = (entry.get("path"), declared, first_green)
    return False, late


def _has_acceptance(task, task_dir):
    return _acceptance(task, task_dir)[0]


def _rule_applies(created):
    """Was the issue created on or after the cutoff? A missing or blank
    `created:` is the one exemption. A value that is present but not an ISO
    date is not trusted to mean "old", so the rule applies to it."""
    if isinstance(created, datetime.datetime):
        created = created.date()
    if isinstance(created, datetime.date):
        return created >= RED_REQUIRED_FROM
    text = "" if created is None else str(created).strip()
    if not text:
        return False
    try:
        return datetime.date.fromisoformat(text[:10]) >= RED_REQUIRED_FROM
    except ValueError:
        return True


def _work_dated_since(task_dir):
    """The first evidence record dated on or after the cutoff, as
    (relative path, date), or None.

    `created:` can be edited; the evidence the CLI writes carries the time of
    the run. So work recorded since the cutoff brings an issue under the rule
    whatever `created:` says. Symlinks and anything that is not a JSON object
    are skipped by `_load`, as for red records.
    """
    evidence = os.path.join(task_dir, "evidence")
    if os.path.islink(evidence):
        return None
    try:
        names = sorted(os.listdir(evidence))
    except OSError:
        return None
    for name in names:
        if not name.endswith(".json"):
            continue
        stamp = _load(os.path.join(evidence, name)).get("timestamp")
        try:
            day = datetime.date.fromisoformat(str(stamp)[:10])
        except ValueError:
            continue
        if day >= RED_REQUIRED_FROM:
            return "evidence/" + name, day
    return None


def missing_first_failure(task, task_dir):
    """The failure message when the rule applies and is not met, else None.

    The rule applies to an issue created on or after the cutoff, or with any
    evidence record dated on or after it."""
    if not task.get("scenarios"):
        return None
    dated_by = None
    if not _rule_applies(task.get("created")):
        dated_by = _work_dated_since(task_dir)
        if dated_by is None:
            return None
    if has_red(task_dir):
        return None
    counts, late = _acceptance(task, task_dir)
    if counts:
        return None
    why = ""
    if late:
        why += (" The acceptance in %s was declared at %s, after the first "
                "green at %s, so it does not stand in for a red."
                % late)
    if dated_by:
        why = (" The rule applies although `created:` is earlier, because "
               "%s is dated %s." % (dated_by[0], dated_by[1].isoformat()))
    return ("the greens on record show the suite passes, but no red is on "
            "record for this issue, so nothing shows a test failed first. Run "
            "`compass tdd-red -- <test command>` on a failing test. For work "
            "with no natural red - config, docs, a behaviour-preserving "
            "refactor - declare it before the change with `compass "
            "acceptance start --kind validation|refactor -- <command>` and "
            "finish with `compass acceptance record`." + why)
