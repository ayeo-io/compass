"""Tokens spent in each stage of a quick fix, from the session's transcript.

Claude Code writes every session to a transcript under its config folder,
named after the session id it also gives each tool call
(`CLAUDE_CODE_SESSION_ID`). This module is the Claude Code adapter: the one
place that reads that format, which Claude Code does not version. Another
runtime has no adapter yet and records `not-claude-code`.

Only numbers, model names and times leave this module. A transcript holds
the whole conversation; none of its text, paths or error messages is kept,
and a reason for recording nothing is one of `REASONS`.
"""
# DEPENDENCY: standard library (datetime, glob, json, os).
from __future__ import annotations

import glob
import json
import os
import re
from datetime import datetime, timezone

SOURCE = "claude-code"
STAGES = ("assess", "implement", "verify", "ship")
# The `verify` and `ship` stages happen inside one `quick-fix finish` call,
# during which the model makes no requests, so a window there would always
# read zero.
MEASURED = ("assess", "implement")
NOT_MEASURED = {"measured": False,
                "reason": "inside one command, where the model makes no requests"}
COUNTS = ("input", "output", "cache_write", "cache_read")
REASONS = ("not-claude-code", "bad-session-id", "no-transcript",
           "unreadable", "no-start-time")

# A session id goes into a file pattern, so only an id of this shape is
# used: anything else could match other sessions' files or leave the
# transcripts folder.
_SESSION_ID = re.compile(r"[A-Za-z0-9_-]+")

_USAGE_FIELDS = {"input": "input_tokens", "output": "output_tokens",
                 "cache_write": "cache_creation_input_tokens",
                 "cache_read": "cache_read_input_tokens"}


def _parse_time(value):
    """A timestamp as an aware datetime, or None."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if not parsed.tzinfo:
        parsed = parsed.replace(tzinfo=timezone.utc)
    # UTC, so times written with different offsets sort and compare as times.
    return parsed.astimezone(timezone.utc)


def _config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or \
        os.path.join(os.path.expanduser("~"), ".claude")


def transcript_paths(session_id):
    """The session's transcript and its subagents' transcripts; none for an
    id that is not a plain session id."""
    if not isinstance(session_id, str) or not _SESSION_ID.fullmatch(session_id):
        return []
    projects = glob.escape(os.path.join(_config_dir(), "projects"))
    main = glob.glob(os.path.join(projects, "*", f"{session_id}.jsonl"))
    subagents = glob.glob(os.path.join(projects, "*", session_id,
                                       "subagents", "*.jsonl"))
    return sorted(main) + sorted(subagents)


def requests(paths, skipped=None):
    """One entry per model request: `{at, model, subagent, input, output,
    cache_write, cache_read}`. A request written over several lines is
    counted once, at its first line's time, with the highest value of each
    count. `skipped`, a list, gains one entry per line that is not JSON."""
    found = {}
    for path in paths:
        subagent = os.path.basename(os.path.dirname(path)) == "subagents"
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                try:
                    line = json.loads(raw)
                except ValueError:
                    if skipped is not None and raw.strip():
                        skipped.append(1)
                    continue
                if not isinstance(line, dict) or line.get("type") != "assistant":
                    continue
                message = line.get("message") or {}
                usage = message.get("usage") if isinstance(message, dict) else None
                at = _parse_time(line.get("timestamp"))
                if not isinstance(usage, dict) or at is None:
                    continue
                key = line.get("requestId") or message.get("id")
                if not key:
                    continue
                counts = {name: usage.get(field)
                          for name, field in _USAGE_FIELDS.items()}
                counts = {name: value if isinstance(value, int) else None
                          for name, value in counts.items()}
                model = message.get("model")
                entry = found.get(key)
                if entry is None:
                    found[key] = {"at": at.isoformat(),
                                  "model": model if isinstance(model, str) else None,
                                  "subagent": subagent, **counts}
                    continue
                for name, value in counts.items():
                    if value is not None and (entry[name] is None
                                              or value > entry[name]):
                        entry[name] = value
    return sorted(found.values(), key=lambda r: r["at"])


def _cost(request, prices):
    price = prices.get(request["model"]) if request["model"] else None
    if not isinstance(price, dict):
        return None
    total = 0.0
    for name in COUNTS:
        if request[name] is None or price.get(name) is None:
            return None
        total += request[name] * float(price[name]) / 1_000_000
    return total


def _boundaries(manifest):
    """Every time an issue records for its own stages. A quick fix finished
    with `--no-commit` has no `land_timestamp`, so its finish times count."""
    return [t for t in (_parse_time(manifest.get(key)) for key in
                        ("started_at", "finish_started_at", "committed_at",
                         "land_timestamp")) if t]


def _windows(manifest, others, session, first, now):
    """Each stage's half-open window, and whether another issue in the same
    session overlaps it."""
    started = _parse_time(manifest.get("started_at"))
    finish = _parse_time(manifest.get("finish_started_at")) or now
    committed = _parse_time(manifest.get("committed_at")) or now
    mine = [o for o in others
            if ((o.get("usage") or {}).get("session") == session)]
    earlier = [t for o in mine for t in _boundaries(o) if t < started]
    assess_from = max(earlier) if earlier else first
    windows = {"assess": (assess_from, started),
               "implement": (started, finish),
               "verify": (finish, committed),
               "ship": (committed, now)}
    spans = []
    for o in mine:
        times = _boundaries(o)
        if times:
            spans.append((min(times), max(times)))
    def overlaps(lo, hi, begin, end):
        # An issue with only a start time is a point; one with a span shares
        # a window only when it runs into it, not when it ends where the
        # window begins.
        if lo == hi:
            return begin <= lo < end
        return lo < end and hi > begin
    shared = {stage: any(overlaps(lo, hi, begin, end) for lo, hi in spans)
              for stage, (begin, end) in windows.items()}
    return windows, shared


def stage_usage(issue_dir, manifest, other_manifests, now=None, prices=None):
    """The manifest's `usage` block for a quick fix. `other_manifests` are
    this project's other issues, read to place the assess window; `prices`
    maps a model to dollars per million tokens of each kind."""
    usage = manifest.get("usage") if isinstance(manifest.get("usage"), dict) else {}
    session = usage.get("session") or os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session:
        return {"recorded": False, "reason": "not-claude-code"}
    if not isinstance(session, str) or not _SESSION_ID.fullmatch(session):
        return {"recorded": False, "reason": "bad-session-id",
                "source": SOURCE}
    base = {"session": session, "source": SOURCE}
    if not _parse_time(manifest.get("started_at")):
        return {"recorded": False, "reason": "no-start-time", **base}
    paths = transcript_paths(session)
    if not paths:
        return {"recorded": False, "reason": "no-transcript", **base}
    skipped = []
    try:
        found = requests(paths, skipped)
    except OSError:
        return {"recorded": False, "reason": "unreadable", **base}
    now_at = _parse_time(now) or datetime.now(timezone.utc)
    first = _parse_time(found[0]["at"]) if found else now_at
    windows, shared = _windows(manifest, other_manifests, session, first, now_at)
    stages = {}
    for stage in STAGES:
        if stage not in MEASURED:
            stages[stage] = dict(NOT_MEASURED)
            continue
        begin, end = windows[stage]
        inside = [r for r in found if begin <= _parse_time(r["at"]) < end]
        totals = {"requests": len(inside),
                  "subagent_requests": sum(1 for r in inside if r["subagent"])}
        for name in COUNTS:
            values = [r[name] for r in inside]
            totals[name] = None if any(v is None for v in values) else sum(values)
        costs = [_cost(r, prices or {}) for r in inside]
        totals["cost_usd"] = (None if any(c is None for c in costs)
                              else round(sum(costs), 6))
        if shared[stage]:
            totals["shared"] = True
        stages[stage] = totals
    return {**base, "skipped_lines": len(skipped), "stages": stages}
