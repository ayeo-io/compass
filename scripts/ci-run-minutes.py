#!/usr/bin/env python3
"""Report the time a CI run took, from the JSON `gh run view RUN --json jobs` prints.

Usage:
    gh run view RUN --json jobs | python3 scripts/ci-run-minutes.py
    python3 scripts/ci-run-minutes.py jobs.json

Prints one line per job (its name and its minutes from start to end, to one
decimal place, or "skipped" when it never started), then two totals:

- the wall time, from the earliest job start to the latest job end. This is
  how long a person waits for the run.
- the sum of the job minutes. This is what the run costs in runner time, and
  it is larger than the wall time because jobs run side by side.

Standard library only, so a runner needs nothing installed to use it.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime


def _moment(text):
    """The time `text` names, or None when the job has none.

    GitHub gives a job that never ran the year-1 date 0001-01-01, not null, so
    that date counts as no time.
    """
    if not text or not isinstance(text, str):
        return None
    when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return None if when.year < 2000 else when


def measure(document):
    """(lines, wall minutes, summed minutes) for a parsed `gh run view` answer."""
    lines, starts, ends, total = [], [], [], 0.0
    for job in document["jobs"]:
        name = job.get("name", "(unnamed)")
        start, end = _moment(job.get("startedAt")), _moment(job.get("completedAt"))
        if start is None:
            lines.append("%s: skipped" % name)
            continue
        starts.append(start)
        if end is None:
            lines.append("%s: not finished" % name)
            continue
        minutes = (end - start).total_seconds() / 60
        lines.append("%s: %.1f minutes" % (name, minutes))
        ends.append(end)
        total += minutes
    wall = (max(ends) - min(starts)).total_seconds() / 60 if starts and ends else 0.0
    return lines, wall, total


def main(argv):
    if len(argv) > 2 or (len(argv) == 2 and argv[1] in ("-h", "--help")):
        print(__doc__)
        return 0 if len(argv) == 2 else 2
    try:
        text = open(argv[1], encoding="utf-8").read() if len(argv) == 2 else sys.stdin.read()
        lines, wall, total = measure(json.loads(text))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("cannot read the run's jobs: %s" % exc, file=sys.stderr)
        return 1
    print("\n".join(lines))
    print("Wall time: %.1f minutes" % wall)
    print("Sum of job minutes: %.1f" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
