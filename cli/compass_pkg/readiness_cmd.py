# compass_pkg.readiness_cmd - `compass readiness`
"""`compass readiness [--json] [--fix-list]`: measure the repository against
the readiness signals in force and write `.compass/readiness.yml`.

The order of one run:

1. remove the temporary worktrees a killed run left
   (`readiness_run.remove_left_worktrees`);
2. read the catalogue in force (`readiness_catalogue.catalogue`) and refuse,
   before anything runs, a project key that is not a string;
3. plan the project commands the command signals need; a command the project
   does not declare is absent without running;
4. ask `project_commands.command_permission` once: trust first, then the
   opt-in. Refused, or with no commit to check out, every planned command is
   absent and no worktree is made;
5. run the allowed commands (`readiness_run.run_commands`);
6. decide every signal (`readiness_signals`), write the record
   (`readiness_record`) and print one line per signal, the score and the
   floor.

`--fix-list` reads a fresh record instead and writes nothing.

A measured project below the floor is a result, not an error: the verb exits
0. It exits 2 only for a `CompassError`, such as a project key that is not a
string. `docs/readiness.md` owns this behaviour.
"""
# DEPENDENCY: standard library (os, time); compass_pkg.core,
# compass_pkg.project_commands, compass_pkg.project_settings,
# compass_pkg.readiness_catalogue, readiness_record, readiness_registry,
# readiness_run, readiness_signals and compass_pkg.terminal.
from __future__ import annotations

import os
import time

from compass_pkg import (project_commands, project_settings, readiness_catalogue,
                         readiness_record, readiness_registry, readiness_run,
                         readiness_signals)
from compass_pkg.core import CompassError, find_compass_dir
from compass_pkg.terminal import Report


def _implementation(signal_id, entry):
    impl = readiness_registry.READINESS.get((entry or {}).get("impl"))
    if impl is None:
        raise CompassError(f"readiness signal {signal_id} names the implementation "
                           f"{(entry or {}).get('impl')!r}, which this CLI does not ship")
    return impl


def _plan(root, catalogue, ctx):
    """The commands to run, and the not-run reasons of those that will not."""
    planned = []
    for signal_id, entry in catalogue.items():
        impl = _implementation(signal_id, entry)
        if not impl.runs_project_command:
            continue
        key, command, limit = readiness_signals.planned_command(root, entry)
        if command is None:
            ctx.not_run[signal_id] = ("undeclared", f"not declared - set project.{key} "
                                                    f"in {ctx.settings_file}")
            continue
        planned.append(readiness_run.Planned(signal_id, key, command, limit))
    return planned


def _refuse_bad_keys(root, catalogue):
    """Read every project key the catalogue uses, so a value that is not a
    string is refused before any command runs."""
    for entry in catalogue.values():
        params = (entry or {}).get("params") or {}
        for name in ("key", "command"):
            if isinstance(params.get(name), str):
                project_settings.project_text(root, params[name])


def _not_run(ctx, planned, kind, reason):
    for entry in planned:
        ctx.not_run[entry.signal_id] = (kind, reason)
    return []


def _permitted(root, planned, ctx, notes):
    """The planned commands that may run here. Asks for permission once,
    trust first, and marks every command not run when it is refused or when
    there is no commit to check out."""
    if not planned:
        return planned
    permission = project_commands.command_permission(root)
    if permission.kind == "untrusted":
        notes.append(f"project commands not run: {permission.reason}. "
                     f"allow_project_commands was not read.")
        return _not_run(ctx, planned, "untrusted", f"not run: {permission.reason}; "
                                                   f"allow_project_commands was not read")
    if permission.kind == "disabled":
        return _not_run(ctx, planned, "disabled",
                        f"not run: project commands are disabled - set {permission.reason}")
    if readiness_record.head(root) is None:
        return _not_run(ctx, planned, "no-checkout",
                        "not run: the repository has no commit, so there is no clean "
                        "checkout of HEAD to run it in")
    return planned


def _run(root, planned, budget_seconds, started, ctx, notes):
    try:
        outcomes = readiness_run.run_commands(root, planned, budget_seconds, started)
    except OSError as exc:
        _not_run(ctx, planned, "no-checkout",
                 f"not run: the clean checkout of HEAD could not be made: {exc}")
        return
    for outcome in outcomes:
        ctx.outcomes[outcome.signal_id] = outcome
        if outcome.status == "over-budget":
            notes.append(f"stopped at the time limit: {outcome.signal_id}")


def measure(root, notes):
    """Measure the project at `root`. Returns the record written; `notes`
    collects lines for the person (a refusal, a stopped command)."""
    started = time.monotonic()
    readiness_run.remove_left_worktrees(root)
    catalogue = readiness_catalogue.catalogue(root)
    _refuse_bad_keys(root, catalogue)
    ctx = readiness_signals.Context(root)
    planned = _permitted(root, _plan(root, catalogue, ctx), ctx, notes)
    budget_seconds = readiness_run.command_budget()
    if planned:
        _run(root, planned, budget_seconds, started, ctx, notes)
    signals = []
    for signal_id, entry in catalogue.items():
        impl = _implementation(signal_id, entry)
        decided = getattr(readiness_signals, impl.function)(ctx, signal_id, entry)
        signals.append({"id": signal_id, "impl": impl.name, "version": impl.version,
                        "weight": entry.get("weight", 1),
                        "required_for_autonomous": entry.get("required_for_autonomous") is True,
                        **decided})
    budget = {"commands_seconds": budget_seconds,
              "used_seconds": round(time.monotonic() - started, 1)}
    record = readiness_record.new_record(root, signals, budget)
    readiness_record.write(root, record)
    return record


def _score_line(record):
    signals = record["signals"]
    score = sum(1 for s in signals if s["result"] == "present")
    below = readiness_record.floor_absent(record)
    floor = ("readiness floor met" if not below
             else "readiness floor not met: " + ", ".join(below))
    return f"{score} of {len(signals)} signals - {floor}", score, below


def fix_order(signals):
    """The absent signals in the order a person should fix them: those on
    the floor first, then the heavier weight first, then catalogue order."""
    absent = [(i, s) for i, s in enumerate(signals) if s.get("result") == "absent"]
    absent.sort(key=lambda item: (not item[1].get("required_for_autonomous"),
                                  -int(item[1].get("weight") or 0), item[0]))
    return [s for _, s in absent]


def _fix_list(args, root):
    """Print the checklist from a fresh record. Writes nothing."""
    rep = Report(args, title="compass readiness --fix-list")
    reading = readiness_record.read(root)
    verdict = readiness_record.fresh(root, reading.record) if reading.status == "ok" else None
    if verdict is None or not verdict.fresh:
        summary = readiness_record.summary(root)
        rep.summary(readiness_record.line(summary),
                    "No fresh readiness record to list fixes from: run `compass readiness` "
                    "first.")
        rep.data(fixes=[], readiness=summary)
        return rep.emit()
    fixes = fix_order(reading.record["signals"])
    items = []
    for entry in fixes:
        fix = entry.get("fix") or {}
        items.append(f"- [ ] {entry['id']}: {fix.get('change', entry['reason'])} "
                     f"({fix.get('file', readiness_record.RECORD)})")
    rep.summary(readiness_record.line(readiness_record.summary(root)))
    rep.body("\n".join(items) if items else "Every readiness signal is present.")
    rep.data(fixes=[{"id": e["id"], "required_for_autonomous": e["required_for_autonomous"],
                     "weight": e.get("weight"), **(e.get("fix") or {})} for e in fixes])
    return rep.emit()


def cmd_readiness(args):
    root = os.path.dirname(find_compass_dir())
    if args.fix_list:
        return _fix_list(args, root)
    notes = []
    record = measure(root, notes)
    width = max([len(s["id"]) for s in record["signals"]] + [10])
    lines = [f"  {s['id']:<{width}}  {s['result']:<8}  {s['reason']}" for s in record["signals"]]
    score_line, score, below = _score_line(record)
    rep = Report(args, title="compass readiness")
    rep.summary(readiness_record.line(readiness_record.summary(root)))
    rep.body("\n".join([*lines, *(f"  {note}" for note in notes), "",
                        f"  {score_line}", f"  wrote {readiness_record.RECORD}"]))
    rep.data(**record, score=score, of=len(record["signals"]), floor_met=not below,
             below_floor=below, path=readiness_record.RECORD)
    return rep.emit()


def register(sub):
    """Add `compass readiness` to the top-level parser."""
    parser = sub.add_parser(
        "readiness", help="measure whether this repository is fit for unattended agent "
                          "work and write .compass/readiness.yml")
    parser.add_argument(
        "--fix-list", action="store_true", dest="fix_list",
        help="print a checklist of the absent signals from a fresh record, the floor's "
             "first; runs nothing and writes nothing")
    parser.set_defaults(func=cmd_readiness, output_kind="report")
