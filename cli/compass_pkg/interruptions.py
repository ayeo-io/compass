"""Count the interruptions an issue takes, in an append-only log.

An interruption is a pre-tool hook block or a failing `compass check`: a
moment the work stopped and someone had to act. Each one appends a line to
`.compass/interruptions.log`, so `compass retro` can report whether the
framework gets in the way, as numbers rather than impressions.

The log is append-only and lives outside every issue folder. Appending one
short line is safe when another process writes at the same moment, so a
count can never damage a manifest, and `compass check` never writes into
the issue it checks. Counting must never change the outcome it counts:
`record` swallows every error, and a count that cannot be written is lost.

DEPENDENCY: Python 3 standard library only. The pre-tool hook imports this
directly, so it stays Python 3.9-compatible.
"""
from __future__ import annotations

import datetime
import os
import re

KINDS = ("hook_blocks", "check_failures")
LOG_NAME = "interruptions.log"
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def record(compass_dir: str, slug: str, kind: str) -> None:
    """Append one interruption of `kind` for issue `slug` to the log."""
    try:
        if kind not in KINDS or not _SLUG.match(slug or ""):
            return
        if not os.path.isdir(compass_dir):
            return
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        with open(os.path.join(compass_dir, LOG_NAME), "a",
                  encoding="utf-8") as fh:
            fh.write(f"{stamp}\t{slug}\t{kind}\n")
    except Exception:  # noqa: BLE001 - a lost count must not become a failure
        return


def totals(compass_dir: str) -> dict:
    """{slug: {kind: count}} from the log. A line that does not parse is
    skipped, so one bad line cannot stop a report."""
    out: dict = {}
    try:
        with open(os.path.join(compass_dir, LOG_NAME), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return out
    for line in lines:
        parts = line.split("\t")
        if len(parts) != 3 or parts[2] not in KINDS or not _SLUG.match(parts[1]):
            continue
        counts = out.setdefault(parts[1], {})
        counts[parts[2]] = counts.get(parts[2], 0) + 1
    return out
