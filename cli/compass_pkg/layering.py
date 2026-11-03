# compass_pkg.layering - the layering record of the four-layer acceptance strategy
"""`compass layering record` and the check `layering-test-passed` of the
four-layer acceptance strategy (`S17`, ADR-086).

The project owns its layer rules: its layering test checks that each test layer
calls only the layer below it, in whatever language the project uses. Compass
runs that test and records the run; it never reads the test or the code it
checks. The command runs `-- <command>`, or `project.layering_command`, through
`tdd._run_test`, and writes `evidence/layering.json` with the command, the test
path, the exit code, the number of tests that ran, the tree id and the time.
The test count comes from pytest's JUnit report when the runner wrote one, read
by `pytest_report`, and is null otherwise. The command exits 0 when the record
is written, even when the test failed, because the check judges the record.

`layering-test-passed` fails a missing, unreadable or failed record, one that
shows 0 tests ran and one made on an older tree. It does not judge a null
count, so a shell script that exits 0 passes. It needs a record on the routing
`on` only: a quick fix and a hotfix reuse the existing DSL.
"""
# DEPENDENCY: standard library (os, shlex, sys); compass_pkg.core, project_settings
# and strategy_records, and inside functions compass_pkg.binding, pytest_report,
# tdd and terminal. The check registry imports this module, so it imports no
# command module at load time.
from __future__ import annotations

import os
import shlex
import sys

from compass_pkg import project_settings, strategy_records
from compass_pkg.core import CompassError, find_upwards, now_iso, resolve_issue_dir

CHECK = "layering-test-passed"
TYPE = "layering"
NAME = "layering"
EV_ID = "EV-LAYERING"
VERB = "layering record"
SETTING = "project.layering_command"
COMMAND = "compass layering record [--test-path <path>] -- <layering test command>"


def _project(task_dir):
    root = find_upwards(task_dir, ".compass") or task_dir
    project = project_settings.lenient(root).get("project")
    return project if isinstance(project, dict) else {}


def _command(args, project):
    if args.command:
        command = list(args.command)
        return command[1:] if command[:1] == ["--"] else command
    text = project.get("layering_command")
    if not (isinstance(text, str) and text.strip()):
        raise CompassError(
            f"compass {VERB}: no command to run. Give the layering test's command after "
            f"`--`, or set {SETTING} in the project's settings. Nothing was run or "
            f"recorded.")
    try:
        return shlex.split(text)
    except ValueError as exc:
        raise CompassError(f"compass {VERB}: {SETTING} cannot be split into words: "
                           f"{exc}. Nothing was run or recorded.") from exc


def _test_path(args, project):
    if args.test_path:
        return args.test_path
    support = project.get("acceptance_support")
    named = support.get("layering_test") if isinstance(support, dict) else None
    return named if isinstance(named, str) and named.strip() else None


def cmd_layering_record(args):
    """`compass layering record`: run the project's layering test and write
    `evidence/layering.json`. Exit 0 when written."""
    from compass_pkg import pytest_report, tdd
    from compass_pkg.binding import ids_for
    from compass_pkg.terminal import say
    task_dir = resolve_issue_dir(args.task)
    project = _project(task_dir)
    command = _command(args, project)
    env, report, ours, before = pytest_report.with_report(command)
    tree_ids = ids_for(task_dir)     # the tree the test runs on, named before it runs
    code, out, warnings = tdd._run_test(command, env)
    for w in warnings:
        sys.stderr.write(f"compass {VERB}: warning - {w}\n")
    ran = pytest_report.tests_ran(report) if pytest_report.written(report, before) else None
    if ours and os.path.exists(report):
        os.remove(report)
    payload = {"type": TYPE, "command": " ".join(command), "argv": command,
               "test_path": _test_path(args, project), "exit_code": code,
               "passed": code == 0 and ran != 0, "tests_ran": ran,
               "timestamp": now_iso(), "log_excerpt": "\n".join(out.splitlines()[-25:]),
               "_full_log": out}
    tdd._bind_to_tree(payload, tree_ids)
    path = tdd._write_evidence(task_dir, NAME, payload)
    strategy_records.register(task_dir, TYPE, EV_ID, os.path.relpath(path, task_dir),
                              payload["record_id"], payload["content_digest"])
    count = "the runner reported no test count" if ran is None else f"{ran} test(s) ran"
    return say(args, f"compass {VERB}: layering record written (exit {code}; {count}).",
               detail=[f"command  : {payload['command']}",
                       f"evidence : {path}",
                       "           `compass check` judges it with layering-test-passed."],
               evidence=path, passed=payload["passed"])


# --- the check ---------------------------------------------------------------------------

def _faults(path, record):
    """Why the layering record does not show a passing layering test."""
    code = record.get("exit_code")
    if not strategy_records.whole(code):
        return [f"{path}: a field is missing - exit_code, the layering test's result"]
    if record.get("tests_ran") == 0:
        return [f"{path} shows that 0 tests ran, so no test ran; the layering test must "
                f"run at least one test"]
    if code != 0:
        tail = [line for line in str(record.get("log_excerpt") or "").splitlines()
                if line.strip()][-3:]
        return [f"{path}: the layering test failed (exit {code})"
                + (": " + " | ".join(tail) if tail else "")]
    return []


def _check_layering_test_passed(task, task_dir):
    """The layering check: an in-scope issue on the routing `on` has a layering
    record of a passing run on the current tree."""
    decline = strategy_records.declined(task, task_dir, TYPE, _faults)
    if decline is not None:
        return decline
    path, record, faults = strategy_records.outcome(task, task_dir, TYPE, _faults)
    if path is None:
        return False, (f"no layering record is registered; a written note does not count. "
                       f"Record the project's layering test with `{COMMAND}`")
    if record is not None:
        tree = strategy_records.tree_fault(task, task_dir, path, record)
        if tree:
            faults.append(tree)
    if faults:
        return False, "; ".join(faults)
    count = ("the runner reported no test count" if record.get("tests_ran") is None
             else f"{record['tests_ran']} test(s) ran")
    return True, f"{path}: `{record.get('command')}` passed ({count}) on the current tree"


def register(sub):
    """Add `compass layering record` to the parser."""
    import argparse
    from compass_pkg.core import issue_arg
    parser = sub.add_parser("layering", help="the layering record of the four-layer "
                                             "acceptance strategy")
    verbs = parser.add_subparsers(dest="subcmd", required=True)
    rec = verbs.add_parser("record", help="run the project's layering test and record "
                                          "the run")
    issue_arg(rec)
    rec.add_argument("--test-path", dest="test_path", metavar="PATH",
                     help="the layering test's path (default: "
                          "project.acceptance_support.layering_test)")
    rec.add_argument("command", nargs=argparse.REMAINDER,
                     help=f"the command, after -- (default: {SETTING})")
    rec.set_defaults(func=cmd_layering_record, output_kind="hand-off")
