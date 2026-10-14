#!/usr/bin/env python3
"""Rebuild tests/ci-durations.json from one CI run's shard logs.

Usage: ci-durations.py RUN_ID [--out PATH]

scripts/ci-shard.py splits the test files by the seconds this table gives
each file, so the shards take about the same time. This command reads run RUN_ID of
.github/workflows/compass.yml with the gh command, takes the log of every
job named "shard (N)", and sums, per test file, every setup, call and
teardown duration listed under pytest's "slowest durations" heading. It
writes {"run": RUN_ID, "seconds": {file: seconds}} to PATH
(tests/ci-durations.json by default), files sorted, seconds rounded to
hundredths.

A file the logs do not list is left out of the table, and ci-shard.py
weighs it at the table's median.

Exit 1, writing nothing, when the run has no shard job, when a shard job
did not succeed, when a log has no durations section, or when gh fails.
Exit 2 on a bad argument.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

USAGE = "usage: ci-durations.py RUN_ID [--out PATH]\n"
SHARD_JOB = re.compile(r"shard \(\d+\)")
# pytest prints "slowest 25 durations" with --durations=25 and "slowest
# durations" with --durations=0.
HEADING = re.compile(r"=+ slowest (\d+ )?durations =+")
ENTRY = re.compile(r"(\d+(?:\.\d+)?)s (setup|call|teardown)\s+(\S[^:]*?)::")
# The runner puts the job name, step name and a timestamp before each line.
STAMP = re.compile(r"^.*?\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z ")


class Failure(Exception):
    pass


def _gh(*args: str) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise Failure(f"gh {' '.join(args)} exited {r.returncode}: "
                      f"{r.stderr.strip()}")
    return r.stdout


def sum_log(text: str, name: str, seconds: dict[str, float]) -> None:
    """Add the durations section of one shard log to seconds."""
    inside = found = False
    for raw in text.splitlines():
        line = STAMP.sub("", raw, count=1).strip()
        if HEADING.fullmatch(line):
            inside = found = True
            continue
        if not inside:
            continue
        entry = ENTRY.match(line)
        if entry:
            seconds[entry.group(3)] += float(entry.group(1))
        elif not line.startswith("("):
            # The pass/fail summary, or the next section, ends the list.
            inside = False
    if not found:
        raise Failure(f"the log of {name} has no slowest-durations section")


def build(run_id: int) -> dict:
    jobs = json.loads(_gh("run", "view", str(run_id), "--json", "jobs"))["jobs"]
    shards = sorted((j for j in jobs if SHARD_JOB.fullmatch(j["name"])),
                    key=lambda j: j["name"])
    if not shards:
        raise Failure(f"run {run_id} has no shard job")
    failed = [f"{j['name']} ({j['conclusion'] or 'not finished'})"
              for j in shards if j["conclusion"] != "success"]
    if failed:
        raise Failure(f"run {run_id} has shard jobs that did not succeed: "
                      + ", ".join(failed))
    seconds: dict[str, float] = defaultdict(float)
    for job in shards:
        log = _gh("run", "view", "--job", str(job["databaseId"]), "--log")
        sum_log(log, job["name"], seconds)
    return {"run": run_id,
            "seconds": {f: round(s, 2) for f, s in sorted(seconds.items())}}


def main(argv: list[str]) -> int:
    args = list(argv)
    out = Path("tests/ci-durations.json")
    if "--out" in args:
        at = args.index("--out")
        if at + 1 >= len(args):
            sys.stderr.write(f"ci-durations.py: --out needs a path\n{USAGE}")
            return 2
        out = Path(args[at + 1])
        del args[at:at + 2]
    if len(args) != 1 or not args[0].isdigit():
        sys.stderr.write(f"ci-durations.py: give one run id\n{USAGE}")
        return 2
    try:
        table = build(int(args[0]))
    except (Failure, ValueError, KeyError) as exc:
        sys.stderr.write(f"ci-durations.py: {exc}\n")
        return 1
    out.write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8")
    sys.stdout.write(f"Wrote {len(table['seconds'])} files from run "
                     f"{table['run']} to {out}.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
