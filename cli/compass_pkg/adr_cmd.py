# compass_pkg.adr_cmd - `compass adr new`, a numbered decision record
"""`compass adr new`: create the next numbered ADR and register it in the index.

It moved out of `receipt.py` when 9.0.0 removed `compass issue receipt` (ADR-091).
"""
# DEPENDENCY: standard library; compass_pkg.core and compass_pkg.terminal.
from __future__ import annotations

import datetime
import os
import re

from compass_pkg.core import CompassError, find_upwards

__all__ = ["cmd_adr_new"]


# --- command: adr new ---------------------------------------------------------
# `compass adr new <slug>` creates a sequentially-numbered ADR file under
# architecture/decisions/ and registers it in the README.md index.
#
# Sequential within a tree at invocation time; concurrent worktrees may
# collide and surface the conflict as a normal git merge conflict. The
# directory is created if absent.

_ADR_TEMPLATE = """\
---
id: {id}
title: {title}
status: proposed
date: {date}
supersedes: ''
superseded_by: ''
---

## Context

<!-- Describe the situation that necessitated this decision. -->

## Decision

<!-- State the decision clearly and concisely. -->

## Alternatives considered

<!-- List alternatives that were evaluated and why they were not chosen. -->

## Consequences

<!-- Describe the positive and negative consequences of this decision. -->

## References

<!-- Link to ADRs, issues, or documents that influenced this decision. -->
"""

_ADR_README_HEADER = """\
# Architecture Decision Records

This directory contains the project's Architecture Decision Records (ADRs).

Each ADR captures one significant architectural decision: its context, the
choice made, the alternatives considered, and the consequences.

## Numbering

ADRs are numbered sequentially.  `compass adr new <slug>` assigns the next
available number so the index is always in creation order.  When two worktrees
create ADRs concurrently, a git merge conflict on this README signals the
collision; resolve by renumbering one side.

## Index

| ID | Title | Status |
|---|---|---|
"""


def _adr_readme_row(adr_id: str, title: str, status: str, path: str) -> str:
    return f"| [{adr_id}]({path}) | {title} | {status} |\n"


def _with_adr_row(readme_text: str, row: str) -> str:
    """The README with `row` placed in the ADR table.

    After the last existing ADR row; failing that, under the separator of the
    first table whose header starts with ID; failing that, at the end. A README
    with sections after its table must keep them after it, so appending to the
    file is only the last resort.
    """
    lines = readme_text.splitlines(keepends=True)
    adr_row = re.compile(r"^\|\s*\[?ADR-\d+")
    at = max((i for i, line in enumerate(lines) if adr_row.match(line)), default=None)
    if at is None:
        for i, line in enumerate(lines[:-1]):
            if re.match(r"^\|\s*ID\s*\|", line) and re.match(r"^\|[-\s|:]+\|\s*$", lines[i + 1]):
                at = i + 1
                break
    if at is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        return "".join(lines) + row
    if not lines[at].endswith("\n"):
        lines[at] += "\n"
    lines.insert(at + 1, row)
    return "".join(lines)


def cmd_adr_new(args):
    """Create a new numbered ADR file and register it in the decisions README."""
    slug = args.slug
    if not slug:
        raise CompassError("compass adr new requires a slug argument")
    # Sanitise slug: lowercase, replace spaces/underscores with hyphens
    slug = slug.strip().lower().replace(" ", "-").replace("_", "-")

    # Find the architecture/decisions directory
    proj = find_upwards(os.getcwd(), os.path.join("architecture", "decisions"))
    if proj:
        decisions_dir = os.path.join(proj, "architecture", "decisions")
    else:
        # Not found walking up - create relative to cwd
        decisions_dir = os.path.join(os.getcwd(), "architecture", "decisions")

    os.makedirs(decisions_dir, exist_ok=True)

    # Count existing ADR-*.md files to determine the next number
    existing = sorted(
        f for f in os.listdir(decisions_dir)
        if f.startswith("ADR-") and f.endswith(".md")
           and f != "ADR-template.md"
    )
    next_num = len(existing) + 1
    num_str = f"{next_num:03d}"
    adr_id = f"ADR-{num_str}"
    filename = f"ADR-{num_str}-{slug}.md"
    full_path = os.path.join(decisions_dir, filename)

    if os.path.exists(full_path):
        raise CompassError(
            f"{full_path} already exists. If you are in a concurrent worktree, "
            f"this is expected - rename one side when the subtasks integrate."
        )

    title_words = slug.replace("-", " ").title()
    content = _ADR_TEMPLATE.format(
        id=adr_id,
        title=title_words,
        date=datetime.date.today().isoformat(),
    )
    with open(full_path, "w", encoding="utf-8") as fh:
        fh.write(content)

    # Update README.md index
    readme_path = os.path.join(decisions_dir, "README.md")
    if os.path.exists(readme_path):
        readme_text = open(readme_path, encoding="utf-8").read()
    else:
        readme_text = _ADR_README_HEADER

    row = _adr_readme_row(adr_id, title_words, "proposed", filename)
    if adr_id not in readme_text:
        with open(readme_path, "w", encoding="utf-8") as fh:
            fh.write(_with_adr_row(readme_text, row))

    # The caveat is split across two lines: one 129-character line is not a
    # line a person reads, and this one is worth reading.
    from compass_pkg.terminal import say

    return say(args, f"compass adr new: created {full_path}",
               detail=[f"registered in {readme_path}",
                       "NOTE: if another worktree creates ADRs at the same "
                       "time, the",
                       "      numbers will collide - renumber when the "
                       "subtasks integrate."],
               path=full_path, index=readme_path)
