#!/usr/bin/env python3
# =============================================================================
# compass - run one stage of one issue with nobody in the session
# =============================================================================
# `compass run <slug> --stage <stage> --stop-file PATH` starts one
# `claude -p` session per cycle and, between cycles, decides from the files
# on disk alone whether to go on. A fresh session per cycle is the point: one
# long session runs out of context, while the manifest and the evidence carry
# everything a new session needs.
#
# It is the one verb that starts a model session (ADR-030), and it is
# bounded so that an unattended run cannot run on:
#
# - a cycle ceiling and a minute ceiling, from the `loop_ceilings` rules in
#   routing-policy.yml; a flag can lower them, never raise them;
# - a stop file, checked before every cycle, whose path must be given;
# - a run of cycles that change nothing on disk, at the repeated-error
#   ceiling;
# - a manifest it cannot read, which stops it: nobody is there to ask.
#
# It never lands an issue. The session is told not to, the commands that
# would are denied to it, and a session that lands the issue anyway stops
# the run. Every piece of text it writes or prints is redacted first.
#
# DEPENDENCY: standard library (hashlib, json, os, shutil, signal, sys,
# time) and
# compass_pkg (core, host_launch, loop_ceilings, redact).
# =============================================================================
"""`compass run`: one stage of one issue, one fresh session per cycle."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import sys
import time

from compass_pkg.core import (FRAMEWORK_ROOT, CompassError, docs_dir,
                              find_upwards, load_manifest, load_yaml,
                              manifest_path, now_iso, resolve_issue_dir,
                              save_manifest)
from compass_pkg import host_launch
from compass_pkg.loop_ceilings import loop_ceilings
from compass_pkg.redact import redact

#: The stage a run may take, and the command its session runs. A run never
#: assesses, plans or lands: those need a person.
STAGES = {"build": "/compass:implement", "verify": "/compass:verify"}

#: Commands a session started by the runner may not use.
DENIED = ("Bash(git push:*)", "Bash(gh pr merge:*)",
          "Bash(compass ship-commit:*)")

#: Exit code of a run that stopped short of done. 2 is a refusal and 3 an
#: incomplete install, so a stop has its own code.
STOPPED = 4

#: How much of a session's error output a record keeps.
_ERROR_TAIL = 2000


def _prompt(stage, slug):
    return (f"This session is unattended: nobody will read or answer a "
            f"question, so do not ask one. Run {STAGES[stage]} for the "
            f"Compass issue {slug}, and stop when the stage is done or you "
            f"cannot go on. Do not land, ship, push or merge: an unattended "
            f"run ends at a result, and a person lands it.")


def _session_args():
    return ["--output-format", "stream-json", "--verbose",
            "--permission-mode", "acceptEdits",
            "--plugin-dir", FRAMEWORK_ROOT,
            "--disallowedTools", ",".join(DENIED)]


def _limit(value, ceiling, name, flag, minimum_text):
    """The value a run uses: the flag when given, else the policy limit.
    Refused when the policy sets none, or the flag is out of range."""
    if ceiling is None:
        raise CompassError(
            f"compass run: governance/routing-policy.yml sets no {name} "
            f"ceiling, and an unattended run must have one. Add the "
            f"`loop_ceilings` rules RP-LOOP-006 (run_cycles) and RP-LOOP-007 "
            f"(run_minutes) from the Compass copy of that file.")
    limit, rid = ceiling
    if value is None:
        return limit, rid
    if value <= 0:
        raise CompassError(f"compass run: {flag} must be {minimum_text}.")
    if value > limit:
        raise CompassError(
            f"compass run: {flag} {value:g} is above the ceiling of {limit} "
            f"that {rid} sets. A flag can lower a ceiling, never raise it.")
    return value, rid


def _claude(path):
    found = path or shutil.which("claude")
    if not found or not os.path.isfile(found) or not os.access(found, os.X_OK):
        raise CompassError(
            "compass run: cannot find `claude` to run the session. Install "
            "Claude Code, or name the executable with --claude.")
    return found


def _digest(task, task_dir):
    """What a cycle could change: the manifest without the runner's own
    `runs:` entry, and the content of every evidence file."""
    h = hashlib.sha256()
    body = {k: v for k, v in task.items() if k != "runs"}
    h.update(json.dumps(body, sort_keys=True, default=str).encode("utf-8"))
    evidence = os.path.join(task_dir, "evidence")
    for base, dirs, files in os.walk(evidence):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(base, name)
            h.update(os.path.relpath(path, evidence).encode("utf-8"))
            try:
                with open(path, "rb") as fh:
                    h.update(fh.read())
            except OSError:
                h.update(b"?")
    return h.hexdigest()


def _done(task, stage, task_dir):
    if stage == "verify":
        gates = [g for g in task.get("gates") or [] if isinstance(g, dict)]
        return bool(gates) and all(g.get("status") == "pass" for g in gates)
    scenarios = [s for s in task.get("scenarios") or [] if isinstance(s, dict)]
    return bool(scenarios) and all(
        os.path.isfile(os.path.join(task_dir, "evidence",
                                    f"green-{s.get('id')}.json"))
        for s in scenarios)


def _read(task_dir):
    """The manifest, or None when it cannot be read as a mapping."""
    try:
        task = load_yaml(manifest_path(task_dir))
    except Exception:                                   # noqa: BLE001
        return None
    return task if isinstance(task, dict) else None


def _write_record(root, rel, run, cycles, settings):
    lines = [f"# Run {run['n']} - {settings['slug']}", "",
             f"- **Stage:** {run['stage']} (`{STAGES[run['stage']]}`)",
             f"- **Started:** {run['started']}",
             f"- **Ended:** {run['ended']}",
             f"- **Outcome:** {run['outcome']}"]
    if run.get("stopped_reason"):
        lines.append(f"- **Stopped because:** {run['stopped_reason']['reason']}")
    lines += [f"- **Ceilings:** {settings['cycles']} cycles ({settings['cycles_rule']}), "
              f"{settings['minutes']:g} minutes ({settings['minutes_rule']})",
              f"- **Session executable:** `{settings['claude']}`", "",
              "| Cycle | Exit code | Session | Cost (USD) | Changed the records |",
              "|---|---|---|---|---|"]
    for c in cycles:
        lines.append(f"| {c['cycle']} | {c['exit']} | {c.get('session') or '-'} "
                     f"| {c.get('cost') if c.get('cost') is not None else '-'} "
                     f"| {c.get('progress', '-')} |")
    errors = [c for c in cycles if c.get("error")]
    if errors:
        lines += ["", "## Errors", ""]
        for c in errors:
            lines += [f"Cycle {c['cycle']}:", "", "```", c["error"].rstrip(),
                      "```", ""]
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(redact("\n".join(lines).rstrip() + "\n"))


def cmd_run(args):
    root = find_upwards(os.getcwd(), ".compass")
    if not root:
        raise CompassError("compass run: no .compass/ directory here - run it "
                           "from inside a Compass project.")
    if args.stage not in STAGES:
        raise CompassError(
            f"compass run: the stage '{args.stage}' cannot run unattended. "
            f"Permitted: {', '.join(STAGES)}. Assessing, planning and landing "
            f"need a person.")
    if not args.stop_file:
        raise CompassError(
            "compass run: --stop-file is required. Name the file whose "
            "existence stops the run; an unattended run must have a way to "
            "be stopped.")
    task_dir = resolve_issue_dir(args.slug)
    task, path = load_manifest(task_dir)
    if task.get("runs") is not None and not isinstance(task["runs"], list):
        raise CompassError(
            f"compass run: the manifest's `runs:` is not a list, so a run "
            f"cannot be recorded. Fix {os.path.relpath(path, root)} first.")
    ceilings = loop_ceilings(task)
    max_cycles, cycles_rule = _limit(args.max_cycles, ceilings.get("run_cycles"),
                                     "cycle", "--max-cycles", "at least 1")
    max_minutes, minutes_rule = _limit(args.max_minutes,
                                       ceilings.get("run_minutes"), "minute",
                                       "--max-minutes", "more than 0")
    claude = _claude(args.claude)
    # A relative stop file is read from the project root, wherever the
    # command was started.
    stop = args.stop_file if os.path.isabs(args.stop_file) \
        else os.path.join(root, args.stop_file)

    lock = os.path.join(task_dir, "run.lock")
    try:
        os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        raise CompassError(
            f"compass run: another run of {args.slug} is in progress: "
            f"{os.path.relpath(lock, root)} exists. Two runs of one issue "
            f"would overwrite each other's records. Delete the lock only if "
            f"no run is going.")
    # SIGTERM, as a cancelled CI job sends, ends Python without raising
    # anything, so the launcher could not end the session. As an exit it
    # reaches the launcher, which ends the session first.
    previous = signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    try:
        return _run(args, root, task_dir, task, path, claude, stop, ceilings,
                    max_cycles, cycles_rule, max_minutes, minutes_rule)
    finally:
        signal.signal(signal.SIGTERM, previous)
        try:
            os.remove(lock)
        except FileNotFoundError:
            pass  # the session removed it, or the issue folder


def _reserve_record(root, task_dir, task):
    """The next run number and its record path, with the record created
    empty so no later run takes the same number. The number follows both
    the manifest's `runs:` and the records on disk, because a run that
    stopped on an unreadable manifest leaves a record and no entry."""
    rel_dir = docs_dir(task_dir)
    full_dir = os.path.join(root, rel_dir)
    os.makedirs(full_dir, exist_ok=True)
    runs = task.get("runs")
    taken = [len(runs) if isinstance(runs, list) else 0]
    for name in os.listdir(full_dir):
        stem = name[len("run-"):-len(".md")]
        if name.startswith("run-") and name.endswith(".md") and stem.isdecimal():
            taken.append(int(stem))
    n = max(taken) + 1
    while True:
        rel = os.path.join(rel_dir, f"run-{n}.md")
        try:
            os.close(os.open(os.path.join(root, rel),
                             os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return n, rel
        except FileExistsError:
            n += 1


def _run(args, root, task_dir, task, path, claude, stop, ceilings,
         max_cycles, cycles_rule, max_minutes, minutes_rule):
    repeat_limit, repeat_rule = ceilings.get("repeated_error", (None, None))
    n, record_rel = _reserve_record(root, task_dir, task)
    started = now_iso()
    deadline = time.monotonic() + max_minutes * 60
    prompt, session_args = _prompt(args.stage, args.slug), _session_args()
    cycles, outcome, reason = [], "stopped", None
    previous, stale, readable = _digest(task, task_dir), 0, True

    interrupted = None
    try:
        cycle = 0
        while True:
            cycle += 1
            if os.path.exists(stop):
                reason = f"the stop file {args.stop_file} exists"
                break
            if cycle > max_cycles:
                reason = (f"the cycle ceiling of {max_cycles} is reached "
                          f"({cycles_rule})")
                break
            left = deadline - time.monotonic()
            if left <= 0:
                reason = (f"the minute ceiling of {max_minutes:g} is reached "
                          f"({minutes_rule})")
                break
            launched = host_launch.launch_claude(claude, prompt, session_args,
                                                 root, dict(os.environ),
                                                 timeout=left)
            summary = host_launch.session_summary(launched.stdout)
            entry = {"cycle": cycle, "exit": launched.returncode,
                     "session": summary["session_id"], "cost": summary["cost_usd"]}
            if launched.returncode != 0 and launched.stderr.strip():
                # Redact first, then cut: a cut through a credential would
                # leave a piece no pattern recognises.
                entry["error"] = redact(launched.stderr)[-_ERROR_TAIL:]
            cycles.append(entry)
            # The manifest is read first, even after a timeout: a session that
            # broke it must not have the runner's older copy saved over it.
            current_task = _read(task_dir)
            if current_task is None:
                readable = False
                reason = (f"the manifest cannot be read after cycle {cycle}; an "
                          f"unattended run stops rather than guess")
                break
            task = current_task
            if launched.timed_out:
                reason = (f"the minute ceiling of {max_minutes:g} is reached "
                          f"({minutes_rule}); the session was ended")
                break
            if task.get("status") == "landed":
                reason = ("the session landed the issue, which an unattended run "
                          "must never do; a person must check it")
                break
            if _done(task, args.stage, task_dir):
                outcome, reason = "done", None
                entry["progress"] = "yes"
                break
            current = _digest(task, task_dir)
            entry["progress"] = "no" if current == previous else "yes"
            stale = stale + 1 if current == previous else 0
            previous = current
            if repeat_limit is not None and stale >= repeat_limit:
                reason = (f"no progress: {stale} cycles in a row changed nothing "
                          f"in the manifest or the evidence ({repeat_rule})")
                break
    except (KeyboardInterrupt, SystemExit) as exc:
        # The launcher has ended the session. Record the run before going
        # on, so an interrupted run leaves a record and a `runs:` entry.
        interrupted = exc
        outcome = "stopped"
        reason = ("the run was interrupted by a signal; a session that was "
                  "running was ended")
        current_task = _read(task_dir)
        readable = current_task is not None
        task = current_task or task

    in_manifest = False
    if readable:
        # Read again: the last session may have written the manifest.
        task = _read(task_dir) or task
        runs = task.get("runs")
        if runs is not None and not isinstance(runs, list):
            # A session broke the key. The record keeps the run; the
            # manifest is left for a person rather than overwritten. The
            # outcome is settled here, before the record is written, so
            # the record and the exit code agree.
            outcome = "stopped"
            reason = reason or ("the manifest's `runs:` is not a list, so this "
                                "run is recorded only in its run record")
        else:
            in_manifest = True
    run = {"n": n, "stage": args.stage, "started": started, "ended": now_iso(),
           "cycles": len(cycles), "outcome": outcome}
    if reason:
        run["stopped_reason"] = {"reason": redact(reason),
                                 "evidence": record_rel, "at": run["ended"]}
    _write_record(root, record_rel, run, cycles,
                  {"slug": args.slug, "claude": claude, "cycles": max_cycles,
                   "cycles_rule": cycles_rule, "minutes": max_minutes,
                   "minutes_rule": minutes_rule})
    if in_manifest:
        task["runs"] = list(task.get("runs") or []) + [run]
        save_manifest(task, path)
    if interrupted is not None:
        raise interrupted
    if outcome == "done":
        print(f"compass run: {args.stage} is done after {len(cycles)} cycle(s). "
              f"Record: {record_rel}")
        return 0
    print(redact(f"compass run: stopped after {len(cycles)} cycle(s): {reason}. "
                 f"Record: {record_rel}"))
    return STOPPED


def register(sub):
    """Add `compass run` to the top-level parser."""
    p = sub.add_parser(
        "run", help="run one stage of one issue unattended, one session per cycle",
        description="Run the build or verify stage of one issue through "
                    "`claude -p`, one fresh session per cycle, deciding "
                    "between cycles from the manifest and evidence alone. "
                    "Stops at the cycle and minute ceilings in "
                    "routing-policy.yml, when the stop file exists, or after "
                    "cycles that change nothing, and never lands the issue. "
                    "Exit 0 when the stage is done, 4 when stopped, 2 when "
                    "refused. Each run leaves run-<n>.md in the issue's "
                    "documents and a `runs:` entry in the manifest.")
    p.add_argument("slug", help="the issue to run")
    p.add_argument("--stage", required=True, help=" | ".join(STAGES))
    p.add_argument("--stop-file", dest="stop_file",
                   help="the file whose existence stops the run (required)")
    p.add_argument("--max-cycles", dest="max_cycles", type=int,
                   help="sessions to start at most; at most the policy ceiling")
    p.add_argument("--max-minutes", dest="max_minutes", type=float,
                   help="minutes to run at most; at most the policy ceiling")
    p.add_argument("--claude", help="the claude executable (default: on the path)")
    p.set_defaults(func=cmd_run, output_kind="hand-off")
