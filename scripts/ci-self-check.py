#!/usr/bin/env python3
"""The test counts and the pass rule of the `self-check` job.

The parallel test pass runs as a matrix of shard jobs, and `self-check` in
.github/workflows/compass.yml is the one check the protected-main ruleset
requires. A skipped required check counts as passed, and a matrix job
reaches `needs` as one combined result, so this rule checks two things: the
result of every job self-check needs, and that the shards' test counts add
up to the count of the whole suite, so no test file was dropped or run
twice.

Usage:
  ci-self-check.py count FILE
      FILE holds what `pytest --collect-only -q` prints under this
      project's pytest.ini, which adds its own -q, so pytest prints one
      "<path>: <n>" line per file. Prints the sum. Exit 1 when FILE holds
      no such line.

  ci-self-check.py aggregate --needs-env NAME --needed JOBS --exempt JOB
                             --counts DIR [--shards N]
      Reads the needs record (`toJSON(needs)`) from environment variable
      NAME. Passes (exit 0) only when:
        - every job in JOBS (comma-separated) has result "success";
        - every other job in the record, except JOB, has result "success";
        - DIR holds one count file per shard, named shard-<i>-of-<n>, for
          every i from 0 to n-1, with one n across all files (and equal to
          N when --shards is given), each holding a whole number;
        - their sum equals needs.count.outputs.total.
      Each shard names the shard count in its file, so the count is set in
      one place, the shard job's matrix. A shard that failed, was cancelled
      or was skipped publishes no file, so it fails the rule here as well
      as through the matrix job's result.
      Always prints each job and its result, the shard counts, their sum and
      the total. Each failure is a line starting "FAIL:".
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

PER_FILE = re.compile(r"^(\S.*\.py): (\d+)$")
COUNT_NAME = re.compile(r"^shard-(\d+)-of-(\d+)$")
WHOLE = re.compile(r"^\d+$")


def count(path: str) -> int:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"ci-self-check.py count: cannot read {path}: {exc}\n")
        return 1
    numbers = [int(m.group(2)) for line in text.splitlines()
               if (m := PER_FILE.match(line.strip()))]
    if not numbers:
        sys.stderr.write(f"ci-self-check.py count: {path} holds no "
                         "'<path>: <n>' line, so pytest collected no file.\n")
        return 1
    print(sum(numbers))
    return 0


def _shard_counts(folder: Path, expected: int | None, fails: list[str]):
    """The counts by shard index, and the shard count they agree on."""
    files = {}
    if folder.is_dir():
        for entry in sorted(folder.iterdir()):
            m = COUNT_NAME.match(entry.name)
            if m:
                files[(int(m.group(1)), int(m.group(2)))] = entry
    totals = {of for _, of in files}
    if expected is not None:
        totals.add(expected)
    if not files:
        fails.append(f"no shard published a count in {folder}.")
    if len(totals) > 1:
        fails.append("the shard counts disagree on the number of shards: "
                     + ", ".join(sorted(f"shard-{i}-of-{of}" for i, of in files))
                     + (f" (expected {expected})" if expected is not None else ""))
        return {}, None
    if not totals:
        return {}, None
    shards = totals.pop()
    values = {}
    for (index, _), entry in files.items():
        if index >= shards:
            fails.append(f"{entry.name} names shard {index}, beyond {shards} shards.")
    for index in range(shards):
        entry = files.get((index, shards))
        if entry is None:
            fails.append(f"shard {index} published no count.")
            values[index] = None
            continue
        text = entry.read_text(encoding="utf-8", errors="replace").strip()
        if not WHOLE.match(text):
            fails.append(f"shard {index}'s count is not a whole number: {text!r}.")
            values[index] = text
            continue
        values[index] = int(text)
    return values, shards


def aggregate(args) -> int:
    fails: list[str] = []
    raw = os.environ.get(args.needs_env)
    try:
        record = json.loads(raw) if raw is not None else None
        if not isinstance(record, dict):
            raise ValueError("not a JSON object")
    except ValueError as exc:
        print(f"FAIL: environment variable {args.needs_env} does not hold the "
              f"needs record: {exc}.")
        return 1

    needed = [j for j in args.needed.split(",") if j]
    print("Needed jobs:")
    for job in sorted(set(record) | set(needed)):
        entry = record.get(job)
        result = entry.get("result") if isinstance(entry, dict) else None
        note = " (exempt)" if job == args.exempt else ""
        print(f"  {job}: {result if result is not None else 'no result'}{note}")
        if job == args.exempt:
            continue
        if result is None:
            fails.append(f"the job {job} has no result in the needs record.")
        elif result != "success":
            fails.append(f"the job {job} has result {result}, not success.")

    values, shards = _shard_counts(Path(args.counts), args.shards, fails)
    shown = ", ".join("missing" if v is None else str(v) for _, v in sorted(values.items()))
    readable = sum(v for v in values.values() if isinstance(v, int))
    print(f"Number of shards: {shards if shards is not None else 'unknown'}")
    print(f"Shard counts: {shown or 'none'}")
    print(f"Sum of shard counts: {readable}")

    entry = record.get("count")
    outputs = entry.get("outputs") if isinstance(entry, dict) else None
    total = outputs.get("total") if isinstance(outputs, dict) else None
    print(f"Total from the count job: {total if total not in (None, '') else 'missing'}")
    if total in (None, ""):
        fails.append("the count job published no total.")
    elif not WHOLE.match(str(total).strip()):
        fails.append(f"the count job's total is not a whole number: {total!r}.")
    elif values and all(isinstance(v, int) for v in values.values()) \
            and readable != int(str(total).strip()):
        fails.append(f"the shards collected {readable} tests, but the whole "
                     f"suite collects {int(str(total).strip())}.")

    for line in fails:
        print(f"FAIL: {line}")
    if fails:
        return 1
    print("self-check passes: every needed job succeeded and the shard "
          "counts add up to the total.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="ci-self-check.py")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("count")
    c.add_argument("file")
    a = sub.add_parser("aggregate")
    a.add_argument("--needs-env", required=True)
    a.add_argument("--needed", required=True)
    a.add_argument("--exempt", default="")
    a.add_argument("--counts", required=True)
    a.add_argument("--shards", type=int)
    args = parser.parse_args(argv)
    if args.command == "count":
        return count(args.file)
    return aggregate(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
