# compass_pkg.readiness_record - the one reader and writer of the readiness record
"""The readiness record, `.compass/readiness.yml`, and everything read from it
(ADR-060).

`compass readiness` writes the record. Every reader - `approach evaluate
--write`, the session-start hook, init, retro, the receipt, the board and the
delivery approach - reads it through this module, so no two readers can
disagree about whether it is fresh or what line to show.

Fresh means all of these hold, tested in this order; the reason of a stale
record names the first that failed:

1. the settings file (`compass.yml`, or `.compass/config.yml` in a project
   without one) has the digest the record holds;
2. the shipped readiness catalogue has the digest the record holds, and every
   implementation version the record holds is the one this CLI ships;
3. `measured_at` is at most seven days before now, and not after now;
4. the recorded commit exists, and HEAD is at most 25 commits past it.

Without Git history only the first three apply. A layer change is a change of
the settings file and a preset change is a change of the shipped catalogue, so
freshness needs neither the layer chain nor the check implementations.
"""
# DEPENDENCY: standard library (dataclasses, datetime, hashlib, os, subprocess),
# the bundled PyYAML, compass_pkg.atomic_io (the YAML reader and the atomic
# writer), compass_pkg.project_settings (which settings file counts) and
# compass_pkg.readiness_registry (the shipped versions). A leaf: the
# session-start hook imports it, so it must not load the policy, the checks
# or a command module. tests/test_project_readiness.py pins this list.
from __future__ import annotations

import datetime
import hashlib
import os
import subprocess
from dataclasses import dataclass

import yaml

from compass_pkg import atomic_io, project_settings, readiness_registry

RECORD = ".compass/readiness.yml"
SCHEMA = 1
MAX_AGE = datetime.timedelta(days=7)
MAX_COMMITS = 25
SHIPPED_CATALOGUE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "governance", "presets", "default", "readiness.yml")
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
MEASURE = "run `compass readiness`"


@dataclass(frozen=True)
class Reading:
    """`status` is `ok`, `missing` or `unreadable`; `record` is the mapping
    when it is `ok`; `detail` says what went wrong otherwise."""
    status: str
    record: dict | None = None
    detail: str = ""


@dataclass(frozen=True)
class Freshness:
    fresh: bool
    reason: str = ""


def _digest_file(path):
    try:
        with open(path, "rb") as handle:
            return "sha256:" + hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None


def settings_identity(root):
    """`{path, digest}` of the settings file the project reads, relative to
    the root; both null when the project has neither file."""
    source = project_settings.settings_source(root)
    if source is None:
        return {"path": None, "digest": None}
    return {"path": os.path.relpath(source, root).replace(os.sep, "/"),
            "digest": _digest_file(source)}


def catalogue_digest():
    """The digest of the readiness catalogue this CLI ships."""
    return _digest_file(SHIPPED_CATALOGUE)


def _git(root, *argv):
    """Git's output, or None when Git fails or the folder has no repository."""
    try:
        done = subprocess.run(["git", *argv], cwd=root, capture_output=True, text=True,
                              timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def head(root):
    """The HEAD commit, or None in a folder with no Git history."""
    return _git(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def new_record(root, signals, budget, measured_at=None):
    """A record for `root`: the signals as measured, with the time, the
    commit, the settings file and the shipped catalogue they were measured
    against."""
    when = measured_at or now_utc()
    return {"schema": SCHEMA, "measured_at": when.strftime(TIME_FORMAT), "head": head(root),
            "settings": settings_identity(root), "catalogue_digest": catalogue_digest(),
            "budget": budget, "signals": list(signals)}


def write(root, record):
    """Write the record atomically, so a reader never sees half of one."""
    text = yaml.safe_dump(record, sort_keys=False, allow_unicode=True)
    atomic_io.atomic_write_text(os.path.join(root, RECORD), text)


def read(root):
    path = os.path.join(root, RECORD)
    if not os.path.exists(path):
        return Reading("missing", detail=f"no record at {RECORD} - {MEASURE}")
    try:
        record = atomic_io.load_yaml_strict(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        return Reading("unreadable", detail=f"{RECORD} could not be read ({first}) - {MEASURE}")
    problem = _shape_problem(record)
    if problem:
        return Reading("unreadable", detail=f"{RECORD} could not be read ({problem}) - {MEASURE}")
    return Reading("ok", record=record)


def _shape_problem(record):
    if not isinstance(record, dict):
        return "it does not hold a mapping"
    if record.get("schema") != SCHEMA:
        return f"schema is {record.get('schema')!r}, not {SCHEMA}"
    signals = record.get("signals")
    if not isinstance(signals, list) or not all(
            isinstance(s, dict) and isinstance(s.get("id"), str)
            and s.get("result") in ("present", "absent") for s in signals):
        return "signals is not a list of measured signals"
    try:
        datetime.datetime.strptime(str(record.get("measured_at")), TIME_FORMAT)
    except ValueError:
        return "measured_at is not a time"
    if not isinstance(record.get("settings"), dict):
        return "settings is not a mapping"
    return None


def fresh(root, record, now=None):
    """Whether `record` still describes the checkout at `root`."""
    now = now or now_utc()
    recorded = record.get("settings") or {}
    current = settings_identity(root)
    if current != {"path": recorded.get("path"), "digest": recorded.get("digest")}:
        name = current["path"] or recorded.get("path") or "the settings file"
        return Freshness(False, f"{name} changed since the record was written")
    if record.get("catalogue_digest") != catalogue_digest():
        return Freshness(False, "the readiness catalogue this CLI ships changed since the "
                                "record was written")
    for signal in record["signals"]:
        shipped = readiness_registry.installed_version(signal.get("impl"))
        if shipped != signal.get("version"):
            return Freshness(False, f"{signal['id']} is measured by {signal.get('impl')} "
                                    f"version {shipped}, and the record holds version "
                                    f"{signal.get('version')}")
    measured = datetime.datetime.strptime(record["measured_at"], TIME_FORMAT).replace(
        tzinfo=datetime.timezone.utc)
    if measured > now:
        return Freshness(False, "the record's measured_at is in the future")
    if now - measured > MAX_AGE:
        return Freshness(False, "the record is older than seven days")
    current_head = head(root)
    if current_head is None:
        return Freshness(True)
    recorded_head = record.get("head")
    if not recorded_head:
        return Freshness(False, "the record holds no commit, and this repository has history")
    if _git(root, "cat-file", "-e", f"{recorded_head}^{{commit}}") is None:
        return Freshness(False, f"the recorded commit {recorded_head[:12]} is unknown: it is "
                                f"not in this repository")
    # A commit from another branch can be a few commits from HEAD by count
    # yet describe a tree HEAD never had, so it must be in HEAD's history.
    if _git(root, "merge-base", "--is-ancestor", recorded_head, "HEAD") is None:
        return Freshness(False, f"the record was measured on a commit that is not in HEAD's "
                                f"history ({recorded_head[:12]}); the branch has changed "
                                f"since it was written")
    count =_git(root, "rev-list", "--count", f"{recorded_head}..HEAD")
    if count is None or int(count) > MAX_COMMITS:
        return Freshness(False, f"HEAD is {count} commits past the recorded commit; the "
                                f"limit is {MAX_COMMITS}")
    return Freshness(True)


def floor_absent(record):
    """The ids of the signals on the floor that the record holds absent."""
    return [s["id"] for s in record["signals"]
            if s.get("required_for_autonomous") is True and s["result"] == "absent"]


def summary(root, now=None):
    """The manifest's `readiness:` mapping for the checkout at `root`."""
    reading = read(root)
    if reading.status != "ok":
        return {"status": "not-measured", "reason": reading.status, "detail": reading.detail}
    verdict = fresh(root, reading.record, now=now)
    if not verdict.fresh:
        return {"status": "not-measured", "reason": "stale", "detail": verdict.reason}
    signals = reading.record["signals"]
    return {"status": "measured",
            "score": sum(1 for s in signals if s["result"] == "present"),
            "signals": len(signals), "floor_met": not floor_absent(reading.record),
            "absent": [s["id"] for s in signals if s["result"] == "absent"],
            "measured_at": reading.record["measured_at"]}


_NOT_MEASURED = {"missing": "no record", "stale": "record stale",
                 "unreadable": "record unreadable"}


def line(summary_):
    """The one readiness line every reader shows."""
    if not isinstance(summary_, dict) or summary_.get("status") != "measured":
        summary_ = summary_ if isinstance(summary_, dict) else {}
        reason = summary_.get("reason")
        label = _NOT_MEASURED.get(reason, "no record")
        detail = summary_.get("detail") or MEASURE
        return f"Repository readiness: not measured ({label}: {detail})"
    floor = "floor met" if summary_.get("floor_met") else "floor not met"
    return (f"Repository readiness: {summary_.get('score')} of {summary_.get('signals')} "
            f"signals, {floor}")


def hook_line(root, autonomy, now=None):
    """The session-start warning, or "" when there is nothing to warn about:
    only an autonomous project that is below the floor or not measured is
    warned."""
    if autonomy != "autonomous":
        return ""
    summary_ = summary(root, now=now)
    if summary_["status"] != "measured":
        shown = line(summary_)
        measure = "" if "compass readiness" in shown else f": {MEASURE}"
        return (f"{shown}. Assess will refuse autonomous work (`approach evaluate --write`) "
                f"until a fresh record meets the readiness floor{measure}.")
    if summary_["floor_met"]:
        return ""
    absent = floor_absent(read(root).record)
    return (f"{line(summary_)}. Below the readiness floor: {', '.join(absent)} absent. "
            f"Assess will refuse autonomous work (`approach evaluate --write`) until each "
            f"is present or `autonomy` is changed to balanced or controlled.")
