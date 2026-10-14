# compass_pkg.issue_usage - what an issue's sessions cost, recorded when it lands
"""The `usage` block `compass ship-commit` writes for every approach but the
quick fix, from the transcripts of the sessions that worked on the issue. An
issue assessed before checkpoint outcomes were recorded (not judged) gets no
block, so it lands exactly as it did before.

The pre-tool hook lists those sessions in `usage.sessions`
(`session_record`); the session that runs `ship-commit` is added. Each
session's transcript, with its subagents' transcripts, is read in full, line
by line, through `session_usage.requests`, which keeps numbers, model names
and times only. Nothing is sampled: when the files sum to more than
`session_usage.USAGE_READ_LIMIT_BYTES`, none is read and the block records
`too-large`.

The block holds:

- `sessions`, `source` and `skipped_lines`;
- `total`: every request in the issue's span, from each session's start (the
  latest boundary of another issue in the same session before this issue's
  first stage end, else the session's first request) to the landing;
- `stages`: each stage the route ran, with the requests between the end of
  the stage before and its own end, or `measured: false, reason: no-window`
  when no record dates its end (its requests count in the next stage);
- `unattributed`: the requests after the last stage end.

The stages and `unattributed` add up to `total`. A window that another issue
recording the same session overlaps is marked `shared`, and so is `total`.
When nothing can be counted the block is `recorded: false` with a word from
`session_usage.REASONS`, and keeps `sessions`; it never holds a count then.
Usage never stops a landing. Owning decision:
`architecture/decisions/ADR-063-*.md`.
"""
# DEPENDENCY: standard library (datetime, os); compass_pkg.checkpoint_outcomes,
# core, diagnose (its `_records`, read and not changed), project_settings,
# session_usage, stable_ids.
from __future__ import annotations

import os
from datetime import datetime, timezone

from compass_pkg import checkpoint_outcomes, project_settings, session_usage
from compass_pkg.core import load_yaml, manifest_path
from compass_pkg.stable_ids import (APPROACH_QUICK_FIX, STAGE_BREAKDOWN, STAGE_IDS,
                                    STAGE_IMPLEMENT)

#: Each count block holds these keys, as a quick fix's stages do.
_COUNT_KEYS = ("requests", "subagent_requests") + session_usage.COUNTS + ("cost_usd",)


def _time(value):
    return session_usage._parse_time(value)


def stage_ends(task_dir, task) -> dict:
    """`{stage: time or None}` for every stage. A checkpoint stage ends at its
    outcome's `at`; breakdown at the earliest `dispatched_at` of a subtask;
    implement at the latest red, green or acceptance record. The `verify` and
    `ship` stages have no dated end. An end later than a later stage's end is dropped,
    because a person can answer a checkpoint after later work."""
    from compass_pkg.diagnose import _records
    ends = {stage: None for stage in STAGE_IDS}
    for stage, entry in checkpoint_outcomes.outcomes(task).items():
        ends[stage] = _time(entry.get("at"))
    dispatched = [_time(s.get("dispatched_at")) for s in task.get("subtasks") or []
                  if isinstance(s, dict)]
    dispatched = [t for t in dispatched if t]
    ends[STAGE_BREAKDOWN] = min(dispatched) if dispatched else None
    records = [_time(stamp) for _kind, _scenario, stamp, _command, _path in _records(task_dir)]
    records = [t for t in records if t]
    ends[STAGE_IMPLEMENT] = max(records) if records else None
    later = None
    for stage in reversed(STAGE_IDS):
        end = ends[stage]
        if end is None:
            continue
        if later is not None and end > later:
            ends[stage] = None
            continue
        later = end
    return ends


def _sessions_of(manifest):
    usage = manifest.get("usage") if isinstance(manifest.get("usage"), dict) else {}
    found = [s for s in usage.get("sessions") or [] if isinstance(s, str)]
    if isinstance(usage.get("session"), str):
        found.append(usage["session"])
    return found


def _boundaries(task_dir, manifest):
    """Every time another issue records for its own stages."""
    times = [t for t in stage_ends(task_dir, manifest).values() if t]
    times += session_usage._boundaries(manifest)
    return times


def _counts(chosen, prices):
    totals = {"requests": len(chosen),
              "subagent_requests": sum(1 for r in chosen if r["subagent"])}
    for name in session_usage.COUNTS:
        values = [r[name] for r in chosen]
        totals[name] = None if any(v is None for v in values) else sum(values)
    costs = [session_usage._cost(r, prices) for r in chosen]
    totals["cost_usd"] = None if any(c is None for c in costs) else round(sum(costs), 6)
    return totals


def _overlaps(spans, begin, end):
    """True when another issue's span runs into the window [begin, end)."""
    for lo, hi in spans:
        if lo == hi:
            if begin <= lo < end:
                return True
        elif lo < end and hi > begin:
            return True
    return False


def usage_block(task_dir, task, others, now, prices) -> dict:
    """The `usage` block of a landed issue. `others` holds `(folder, manifest)`
    for the project's other issues; `now` is the landing time."""
    previous = task.get("usage") if isinstance(task.get("usage"), dict) else {}
    sessions = []
    shipping = os.environ.get("CLAUDE_CODE_SESSION_ID")
    for one in list(previous.get("sessions") or []) + ([shipping] if shipping else []):
        if one not in sessions:
            sessions.append(one)
    if not sessions:
        return {"recorded": False, "reason": "not-claude-code"}
    good = [s for s in sessions if isinstance(s, str) and session_usage._SESSION_ID.fullmatch(s)]
    if len(good) != len(sessions):
        return {"recorded": False, "reason": "bad-session-id", "sessions": good,
                "source": session_usage.SOURCE}
    base = {"sessions": sessions, "source": session_usage.SOURCE}
    paths = {s: session_usage.transcript_paths(s) for s in sessions}
    for found in paths.values():
        if not [p for p in found if os.path.basename(os.path.dirname(p)) != "subagents"]:
            return {"recorded": False, "reason": "no-transcript", **base}
    try:
        size = sum(os.stat(p).st_size for found in paths.values() for p in found)
    except OSError:
        return {"recorded": False, "reason": "unreadable", **base}
    if size > session_usage.USAGE_READ_LIMIT_BYTES:
        return {"recorded": False, "reason": "too-large", **base}
    skipped, per_session = [], {}
    try:
        for session in sessions:
            per_session[session] = session_usage.requests(paths[session], skipped)
    except OSError:
        return {"recorded": False, "reason": "unreadable", **base}

    ends = stage_ends(task_dir, task)
    own_ends = [t for t in ends.values() if t]
    first_end = min(own_ends) if own_ends else now
    found, spans, starts = [], [], []
    for session in sessions:
        sharing = [(d, m) for d, m in others if session in _sessions_of(m)]
        earlier = [t for d, m in sharing for t in _boundaries(d, m) if t < first_end]
        requests = per_session[session]
        start = max(earlier) if earlier else (_time(requests[0]["at"]) if requests else now)
        starts.append(start)
        found += [r for r in requests if start <= _time(r["at"]) < now]
        for d, m in sharing:
            times = _boundaries(d, m)
            if times:
                spans.append((min(times), max(times)))
    found.sort(key=lambda r: _time(r["at"]))
    # The first window starts where counting starts. Another issue's work that
    # ended before then was never counted here, so it overlaps no window.
    counted_from = min(starts)

    stages, cursor = {}, None
    for stage in STAGE_IDS:
        if not checkpoint_outcomes.stage_runs(task, stage):
            continue
        end = ends.get(stage)
        if end is None or (cursor is not None and end <= cursor):
            stages[stage] = {"measured": False, "reason": "no-window"}
            continue
        inside = [r for r in found if (cursor is None or _time(r["at"]) >= cursor)
                  and _time(r["at"]) < end]
        counts = _counts(inside, prices)
        if _overlaps(spans, cursor or counted_from, end):
            counts["shared"] = True
        stages[stage] = counts
        cursor = end
    after = [r for r in found if cursor is None or _time(r["at"]) >= cursor]
    unattributed = _counts(after, prices)
    if _overlaps(spans, cursor or counted_from, now):
        unattributed["shared"] = True
    total = _counts(found, prices)
    if any(b.get("shared") for b in list(stages.values()) + [unattributed]):
        total["shared"] = True
    return {**base, "skipped_lines": len(skipped), "total": total,
            "unattributed": unattributed, "stages": stages}


def _others(task_dir):
    """`(folder, manifest)` for every other issue of this checkout."""
    work = os.path.dirname(os.path.normpath(task_dir))
    found = []
    for name in sorted(os.listdir(work)):
        folder = os.path.join(work, name)
        path = manifest_path(folder)
        if folder == os.path.normpath(task_dir) or not os.path.isfile(path):
            continue
        try:
            manifest = load_yaml(path)
        except Exception:                              # noqa: BLE001 - another issue's fault
            continue
        if isinstance(manifest, dict):
            found.append((folder, manifest))
    return found


def record_at_ship(task, task_dir, now) -> str | None:
    """Set the landed issue's `usage` block. Returns the one line to print when
    usage is not recorded, else None. Never raises.

    A quick fix keeps the block its finish wrote. An issue assessed before
    checkpoint outcomes were recorded (not judged) lands exactly as it did
    before this block existed: nothing is read or written for it."""
    if task.get("delivery_approach") == APPROACH_QUICK_FIX:
        return None
    if not checkpoint_outcomes.judged(task):
        return None
    previous = task.get("usage") if isinstance(task.get("usage"), dict) else {}
    try:
        project = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.normpath(task_dir))))
        prices = project_settings.settings(project).get("prices") or {}
        block = usage_block(task_dir, task, _others(task_dir),
                            _time(now) or datetime.now(timezone.utc),
                            prices if isinstance(prices, dict) else {})
    except Exception:                                  # noqa: BLE001 - never stop a landing
        kept = [s for s in previous.get("sessions") or [] if isinstance(s, str)
                and session_usage._SESSION_ID.fullmatch(s)]
        block = {"recorded": False, "reason": "unreadable",
                 **({"sessions": kept} if kept else {})}
    task["usage"] = block
    if block.get("recorded") is False:
        return f"compass ship-commit: usage not recorded ({block['reason']})."
    return None


def save_landed(task, task_dir, path):
    """Record the landed issue's usage, save its manifest, and print the one
    line that says usage was not recorded. `ship-commit` calls it in both of
    its landing saves, after `land_timestamp` is set."""
    from compass_pkg.core import save_manifest
    line = record_at_ship(task, task_dir, task.get("land_timestamp"))
    save_manifest(task, path)
    if line:
        print(line)
