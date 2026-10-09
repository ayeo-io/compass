#!/usr/bin/env python3
# =============================================================================
# bench-evaluate - how long `compass approach evaluate` takes, with and without --write
# =============================================================================
# `approach evaluate --write` commits a generation of the issue's configuration
# (ADR-036): it resolves and lints the layers, writes four files, a marker and
# the manifest. This times that against a plain evaluate, so the cost the
# store adds to the one command that pays it is a number, not a guess. Run it
# against another checkout with --cli to compare before and after.
#
# DEPENDENCY: standard library (argparse, os, shutil, statistics, subprocess,
# sys, tempfile, time) and the compass entry point it times.
# =============================================================================
"""Time `compass approach evaluate` in a scratch project.

    scripts/bench-evaluate.py                  5 runs of each case
    scripts/bench-evaluate.py --runs 20        more runs
    scripts/bench-evaluate.py --cli PATH       time another checkout's cli/compass

Cases, each timed as one whole process, start-up included:

- `process start`: `compass --version`, the cost every case carries;
- `evaluate`: no --write;
- `evaluate --write (first commit)`: an issue with no generation;
- `evaluate --write (no change)`: the same issue again.

Each is run with no `compass.yml` and with a project layer that adds one check.
A checkout from before the store prints the first-commit and no-change cases
as plain `--write`; the rows still compare.
"""
from __future__ import annotations

import argparse
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = "bench"

MANIFEST = """schema_version: '3.0'
issue: bench
created: '2026-10-07'
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: medium
  goal: delivery
  role: engineer
  labels: []
evidence: []
"""

PROJECT = """schema: 1
checks:
  bench-extra:
    statement: A check the project adds.
    kind: deterministic
    impl: suite-passed
    severity: advisory
    on_skipped: fail
"""


def _env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home, "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "PYTHONDONTWRITEBYTECODE": "1"}


def _timed(cli, cwd, *argv):
    """The wall time of one `compass` process, in milliseconds. A command that
    fails stops the run: a time for a failure would be a wrong number."""
    start = time.perf_counter()
    done = subprocess.run([sys.executable, cli, *argv], cwd=cwd, env=_env(cwd),
                          capture_output=True, text=True, timeout=600)
    elapsed = (time.perf_counter() - start) * 1000
    if done.returncode != 0:
        raise SystemExit(f"bench-evaluate: `compass {' '.join(argv)}` exited "
                         f"{done.returncode}\n{done.stdout}{done.stderr}")
    return elapsed


def _project(root, with_layer):
    os.makedirs(os.path.join(root, ".compass", "work"), exist_ok=True)
    if with_layer:
        with open(os.path.join(root, "compass.yml"), "w", encoding="utf-8") as fh:
            fh.write(PROJECT)


def _issue(root, name):
    folder = os.path.join(root, ".compass", "work", name)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "manifest.yml"), "w", encoding="utf-8") as fh:
        fh.write(MANIFEST.replace("issue: bench", f"issue: {name}"))


def measure(cli, runs, with_layer):
    """`{case: [ms, ...]}` for one project shape."""
    root = tempfile.mkdtemp(prefix="bench-evaluate-")
    try:
        _project(root, with_layer)
        out = {"process start": [], "evaluate": [], "evaluate --write (first commit)": [],
               "evaluate --write (no change)": []}
        for n in range(runs):
            out["process start"].append(_timed(cli, root, "--version"))
            _issue(root, SLUG)
            out["evaluate"].append(_timed(cli, root, "approach", "evaluate", "--issue", SLUG))
            fresh = f"{SLUG}-{n}"
            _issue(root, fresh)
            out["evaluate --write (first commit)"].append(
                _timed(cli, root, "approach", "evaluate", "--issue", fresh, "--write"))
            out["evaluate --write (no change)"].append(
                _timed(cli, root, "approach", "evaluate", "--issue", fresh, "--write"))
        return out
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--runs", type=int, default=5, help="runs of each case (default 5)")
    parser.add_argument("--cli", default=os.path.join(ROOT, "cli", "compass"),
                        help="the compass entry point to time (default: this checkout's)")
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    print(f"bench-evaluate: {args.runs} run(s) per case, {args.cli}")
    print(f"{'case':<52}{'median ms':>10}{'min':>8}{'max':>8}")
    for with_layer in (False, True):
        print(f"\n{'with a project layer' if with_layer else 'no compass.yml'}")
        for case, times in measure(args.cli, args.runs, with_layer).items():
            print(f"  {case:<50}{statistics.median(times):>10.0f}"
                  f"{min(times):>8.0f}{max(times):>8.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
