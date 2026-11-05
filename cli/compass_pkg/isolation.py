# compass_pkg.isolation - the isolation proof of the four-layer acceptance strategy
"""`compass isolation record` and the check `isolation-proven` of strategy `S17`,
the four-layer acceptance strategy (ADR-086).

Isolation is proven by a record the project's own commands write, never by a
written note. The command runs the parallel command once, then, for each
scenario the manifest declares tests for, runs the repeat command twice with
`{tests}` replaced by those test ids. Each command string is split with
`shlex.split` and run with no shell, through `tdd._run_test`, the path `compass
tdd-red` uses. The record holds the exit codes only: Compass reads no report
and no test code. The command exits 0 when the record is written, even when a
run failed, because the check judges the record.

`isolation-proven` passes when the parallel run passed, every test the issue
declares was in a repeat entry, both runs of each entry passed, the record is on
the tree as it is now, and its candidate is the outer-loop green's. It needs a
record on the routings `on` and `existing-dsl-isolation` (the hotfix).
"""
# DEPENDENCY: standard library (os, shlex, sys); compass_pkg.candidate_client,
# check_results, core, strategy_records and terminal, and inside functions
# compass_pkg.binding and tdd. The check registry imports this module, so it
# imports no command module at load time.
from __future__ import annotations

import os
import shlex
import sys

from compass_pkg import candidate_client, strategy_records
from compass_pkg.core import CompassError, load_manifest, now_iso, resolve_issue_dir

CHECK = "isolation-proven"
TYPE = "isolation-proof"
NAME = "isolation-proof"
EV_ID = "EV-ISOLATION"
TESTS = "{tests}"
VERB = "isolation record"
COMMAND = (f"compass isolation record --candidate <build id>|local --client "
           f"{'|'.join(candidate_client.CLIENTS)} --parallel \"<command>\" "
           f"--repeat \"<command> {TESTS}\"")


def declared(task):
    """`[(scenario, [test id, ...])]` of each scenario that declares a test."""
    out = []
    for entry in (task or {}).get("scenarios") or []:
        if not isinstance(entry, dict):
            continue
        tests = [t for t in entry.get("tests") or [] if isinstance(t, str) and t.strip()]
        if entry.get("id") and tests:
            out.append((entry["id"], tests))
    return out


def _with_tests(argv, tests):
    """`argv` with the word `{tests}` replaced by the test ids, one word each; inside a
    longer word they are joined by spaces."""
    out = []
    for word in argv:
        if word == TESTS:
            out.extend(tests)
        else:
            out.append(word.replace(TESTS, " ".join(tests)))
    return out


def _split(flag, text):
    try:
        argv = shlex.split(text or "")
    except ValueError as exc:
        raise CompassError(f"compass {VERB}: {flag} cannot be split into words: {exc}. "
                           f"Nothing was run or recorded.") from exc
    if not argv:
        raise CompassError(f"compass {VERB}: {flag} needs a command. Nothing was run or "
                           f"recorded.")
    return argv


def cmd_isolation_record(args):
    """`compass isolation record`: run the parallel command once and each scenario's
    tests twice, and write `evidence/isolation-proof.json`. Exit 0 when written."""
    from compass_pkg import tdd
    from compass_pkg.binding import ids_for
    from compass_pkg.terminal import say
    task_dir = resolve_issue_dir(args.task)
    task, _ = load_manifest(task_dir)
    parallel = _split("--parallel", args.parallel)
    repeat = _split("--repeat", args.repeat)
    if not any(TESTS in word for word in repeat):
        raise CompassError(
            f"compass {VERB}: --repeat must hold {TESTS}, which each scenario's declared "
            f"test ids replace, so each scenario runs twice on its own. Nothing was run or "
            f"recorded.")
    scenarios = declared(task)
    if not scenarios:
        raise CompassError(
            f"compass {VERB}: the issue declares no test for any scenario, so there is "
            f"nothing to run twice. Declare each scenario's tests with `compass scenario "
            f"add <id> --test <path>::<name>`. Nothing was run or recorded.")
    tree_ids = ids_for(task_dir)    # the tree the runs test, named before they run
    named = candidate_client.named(VERB, "outer", args.candidate, args.client, True, tree_ids)
    log = []

    def run(argv):
        code, out, warnings = tdd._run_test(argv)
        for w in warnings:
            sys.stderr.write(f"compass {VERB}: warning - {w}\n")
        log.append(f"$ {' '.join(argv)}\n{out}")
        return code

    payload = {"type": TYPE, "parallel": {"command": " ".join(parallel),
                                          "argv": parallel, "exit_code": run(parallel)}}
    payload["repeat"] = []
    for scenario, tests in scenarios:
        argv = _with_tests(repeat, tests)
        runs = [run(argv), run(argv)]
        payload["repeat"].append({"scenario": scenario, "tests": tests,
                                  "command": " ".join(argv), "argv": argv, "runs": runs,
                                  "same": runs[0] == runs[1]})
    payload.update(named)
    payload["passed"] = not _run_faults(payload)
    payload["timestamp"] = now_iso()
    full_log = "\n".join(log)
    payload["log_excerpt"] = "\n".join(full_log.splitlines()[-25:])
    payload["_full_log"] = full_log
    tdd._bind_to_tree(payload, tree_ids)
    path = tdd._write_evidence(task_dir, NAME, payload)
    rel = os.path.relpath(path, task_dir)
    strategy_records.register(task_dir, TYPE, EV_ID, rel, payload["record_id"],
                              payload["content_digest"])
    lines = [f"parallel : exit {payload['parallel']['exit_code']}  "
             f"{payload['parallel']['command']}"]
    lines += [f"repeat   : {r['scenario']} exit {r['runs'][0]}, then exit {r['runs'][1]}"
              for r in payload["repeat"]]
    lines += [f"evidence : {path}",
              "           `compass check` judges it with isolation-proven."]
    verdict = "every run passed" if payload["passed"] else "a run failed"
    from compass_pkg.next_line import announce
    said = say(args, f"compass {VERB}: isolation-proof recorded ({verdict}).",
               detail=lines, evidence=path, passed=payload["passed"])
    return announce(args, task_dir, said)


# --- the check ---------------------------------------------------------------------------

def _runs_ok(runs):
    return (isinstance(runs, list) and len(runs) == 2
            and all(strategy_records.whole(c) for c in runs))


def _run_faults(record, path="the record"):
    """Why the runs the record holds do not prove isolation: a missing field, a
    failed parallel run or a scenario that did not pass twice."""
    parallel = record.get("parallel")
    if not isinstance(parallel, dict) or not strategy_records.whole(parallel.get("exit_code")):
        return [f"{path}: a field is missing - parallel.exit_code, the parallel run's result"]
    repeat = record.get("repeat")
    if not isinstance(repeat, list) or not repeat:
        return [f"{path}: a field is missing - repeat, the result of the repeat runs"]
    faults = []
    if parallel["exit_code"] != 0:
        faults.append(f"{path}: the parallel run failed (exit {parallel['exit_code']}), "
                      f"so the suite does not pass when its tests run at the same time")
    for n, entry in enumerate(repeat):
        if not isinstance(entry, dict) or not _runs_ok(entry.get("runs")):
            faults.append(f"{path}: a field is missing - repeat[{n}].runs, the exit codes "
                          f"of the repeat run's two runs")
            continue
        first, second = entry["runs"]
        if first == second == 0:
            continue
        words = ["passed" if c == 0 else "failed" for c in (first, second)]
        faults.append(f"{path}: scenario {entry.get('scenario')} - the first run {words[0]} "
                      f"(exit {first}) and the second run {words[1]} (exit {second})")
    return faults


def _covered(record):
    tests = set()
    for entry in record.get("repeat") or []:
        if isinstance(entry, dict) and _runs_ok(entry.get("runs")):
            tests.update(t for t in entry.get("tests") or [] if isinstance(t, str))
    return tests


def _green_candidate(task, task_dir):
    """The candidate of the newest registered outer-loop green that names one."""
    greens = [r for _, r in candidate_client.green_records(task, task_dir)
              if r.get("loop") == "outer" and isinstance(r.get("candidate"), str)
              and r["candidate"]]
    if not greens:
        return None
    return max(greens, key=lambda r: str(r.get("timestamp") or ""))["candidate"]


def _check_isolation_proven(task, task_dir):
    """The isolation check: an in-scope issue on a routing that needs it has an
    isolation proof that passed on the current tree and on the outer-loop green's
    candidate, with every declared test run twice."""
    decline = strategy_records.declined(task, task_dir, TYPE, lambda p, r: _run_faults(r, p))
    if decline is not None:
        return decline
    path, record, faults = strategy_records.outcome(task, task_dir, TYPE,
                                                    lambda p, r: _run_faults(r, p))
    if path is None:
        return False, (f"no isolation-proof record is registered; a written note does not "
                       f"count. Record one with `{COMMAND}`")
    if record is None:
        return False, "; ".join(faults)
    covered = _covered(record)
    faults += [f"{path}: {test} was not run twice; the repeat run leaves out this declared "
               f"test of scenario {scenario}"
               for scenario, tests in declared(task) for test in tests if test not in covered]
    lacks = candidate_client.missing(record)
    if lacks:
        faults.append(f"{path} names no {' and '.join(lacks)}")
    green = _green_candidate(task, task_dir)
    if green and record.get("candidate") and record["candidate"] != green:
        faults.append(f"{path} was made on candidate {record['candidate']}, and the "
                      f"outer-loop green names candidate {green}; record the proof on "
                      f"the green's candidate")
    tree = strategy_records.tree_fault(task, task_dir, path, record)
    if tree:
        faults.append(tree)
    if faults:
        return False, "; ".join(faults)
    return True, (f"{path}: the parallel run passed and each of "
                  f"{len(record['repeat'])} scenario(s) passed twice, on candidate "
                  f"{record.get('candidate')}")


def register(sub):
    """Add `compass isolation record` to the parser."""
    from compass_pkg.core import issue_arg
    parser = sub.add_parser("isolation", help="the isolation proof of the four-layer "
                                              "acceptance strategy")
    verbs = parser.add_subparsers(dest="subcmd", required=True)
    rec = verbs.add_parser("record", help="run the suite in parallel and each scenario's "
                                          "tests twice, and record the exit codes")
    issue_arg(rec)
    rec.add_argument("--candidate", metavar="ID|local", help="the build the suite ran against")
    rec.add_argument("--client", metavar="api|web|cli", help="the interface the suite drove")
    rec.add_argument("--parallel", metavar="COMMAND", required=True,
                     help="the command that runs the suite in parallel")
    rec.add_argument("--repeat", metavar="COMMAND", required=True,
                     help=f"the command that runs the tests {TESTS} names")
    rec.set_defaults(func=cmd_isolation_record, output_kind="hand-off")
