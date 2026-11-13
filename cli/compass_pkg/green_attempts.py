# compass_pkg.green_attempts - the run count `compass tdd-green` writes
"""The `attempts` and `rerun_without_change` fields of a green record, and the
`test` field of an outer-loop green.

`compass tdd-green` keeps a count per scenario in the sidecar
`evidence/.tdd-state.json`, beside the tree and the command of the last run.
`no-trusted-rerun` (strategy `S5`) reads the two fields: a pass on the same tree
with the same command is a rerun without change.

Each loop keeps its own count (ADR-084). The inner loop keeps the key it always
had, the scenario id (`""` unbound), so a count written before ADR-084 stays the
inner loop's. The outer loop keys the scenario id with `.outer` after it, as its
record's file name does (ADR-082). An outer-loop run that fails is counted too:
the acceptance suite is the outer loop's one assertion, so a fail and then a pass
on the same tree is a rerun, which strategy `S5` calls a failure. The inner loop
counts passes only, as before.
"""
# DEPENDENCY: standard library (json, os); compass_pkg.core and red_first. It
# imports no command module.
from __future__ import annotations

import json
import os

from compass_pkg.core import CompassError, load_manifest
from compass_pkg.red_first import OUTER


def _tdd_state_path(task_dir):
    """Path to the CLI-internal sidecar that tracks the source-tree hash and
    `attempts` counter between tdd-green invocations. Not part of manifest.yml schema.
    """
    return os.path.join(task_dir, "evidence", ".tdd-state.json")


def state_key(scenario, loop=None):
    """The sidecar key of one binding and loop: the scenario id for the inner loop,
    and the id with `.outer` after it for the outer loop (ADR-084)."""
    return (scenario or "") + (OUTER if loop == "outer" else "")


def _read(task_dir):
    path = _tdd_state_path(task_dir)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_tdd_state(task_dir, scenario, loop=None):
    """The state of one binding and loop: `tree_hash`, `attempts` and `command`.
    Empty when the sidecar is absent or unreadable."""
    held = _read(task_dir).get(state_key(scenario, loop))
    return held if isinstance(held, dict) else {}


def _save_tdd_state(task_dir, scenario, tree_hash, attempts, command=None, loop=None):
    """Persist the state of one binding and loop in the sidecar file."""
    path = _tdd_state_path(task_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing = _read(task_dir)
    existing[state_key(scenario, loop)] = {"tree_hash": tree_hash, "attempts": attempts,
                                           "command": command}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=2)


def count(task_dir, scenario, loop, tree_hash, command):
    """`(`attempts`, `rerun_without_change`)` for a passing run, saved for the next run.

    The command matters as much as the tree. Running the same assertion again
    with nothing changed hides a flaky test by re-running it, which the flag
    exists to catch. Running a different one - the narrow suite, then the full
    suite, which the verify stage asks for - is a new assertion, not a retry.
    """
    prior = _load_tdd_state(task_dir, scenario, loop)
    if prior.get("tree_hash") is None:
        attempts, rerun = 1, False      # the first run of this binding and loop
    else:
        attempts = (prior.get("attempts") or 0) + 1
        rerun = prior["tree_hash"] == tree_hash and prior.get("command") == command
    _save_tdd_state(task_dir, scenario, tree_hash, attempts, command, loop)
    return attempts, rerun


def failed(task_dir, scenario, loop, tree_hash, command):
    """Count a run that failed, so a pass on the same tree that follows it is
    recorded as a rerun. No record is written for the failed run. `tdd-green`
    calls it for the outer loop only (ADR-084)."""
    prior = _load_tdd_state(task_dir, scenario, loop)
    _save_tdd_state(task_dir, scenario, tree_hash, (prior.get("attempts") or 0) + 1,
                    command, loop)


def declared_test(task_dir, scenario):
    """The first test the scenario declares in the manifest, or None.

    `no-trusted-rerun` looks one test id up in `governance/quarantine.yml`. A green
    records one exit code for the suite and does not say which test was flaky, so
    a scenario that declares several tests is named by its first; a quarantine
    entry must name that test (ADR-084)."""
    if not scenario:
        return None
    try:
        task, _ = load_manifest(task_dir)
    except (CompassError, OSError, ValueError):
        return None
    for entry in (task or {}).get("scenarios") or []:
        if isinstance(entry, dict) and entry.get("id") == scenario:
            tests = [t for t in entry.get("tests") or [] if isinstance(t, str) and t]
            return tests[0] if tests else None
    return None
