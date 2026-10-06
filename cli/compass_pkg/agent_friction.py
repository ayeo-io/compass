# compass_pkg.agent_friction - `compass issue friction`
"""The agent records friction it observed during the run.

Ship captures friction from signals the CLI computed and one optional line
from the person. The agent meets the process most often, so this verb lets
it file a note where a step cost more than it returned, under a bar that
keeps the channel useful:

- the note cites evidence it observed: a file in the issue folder other
  than the manifest, or a devlog line as `devlog.md:<line>`;
- it names a fix in one line of at most 160 characters;
- at most three notes per issue, and never the same category and phase
  twice.

A note about a step a guardrail backs is accepted but marked, because
friction can change a strategy or an approach's weight, never a guardrail.
Agent notes are counted apart from person notes and never make a lesson on
their own (`calibration._aggregate_friction`, `lessons.propose_from_friction`).
Advisory: no check or gate reads them.
"""
# DEPENDENCY: standard library (os, re); compass_pkg.core.
from __future__ import annotations

import os
import re

from compass_pkg.core import CompassError, load_manifest, resolve_issue_dir, save_manifest

MAX_NOTES = 3
MAX_FIX = 160
CATEGORIES = ("over-weight", "under-weight", "mis-route", "missing-strategy",
              "tooling", "docs", "other")
PHASES = ("assess", "define", "refine", "plan", "breakdown", "implement",
          "verify", "ship")
GUARDRAIL_NOTICE = "guardrail, not changeable by friction"

# A fix asks to change a guardrail-backed step when it both names such a step
# and asks to remove, skip or delay it. A step named alone is not enough:
# "record the evidence path automatically" or "a shorter stack trace" names a
# guardrail word but changes no guardrail. The steps are the five guardrails:
# a failing test first, acceptance criteria before code, traceability,
# recorded evidence and a person's approval or review.
_GUARDRAIL_STEP = re.compile(
    r"\b(?:tdd|red|failing[- ]tests?|tests?|acceptance(?: criteria)?|"
    r"trac(?:e|ed|ing|eability)|evidence|approv\w*|sign[- ]?off|review\w*)\b"
    r"|(?-i:\bACs?\b)", re.I)
_REMOVAL = re.compile(
    r"\b(?:skip\w*|drop\w*|remove\w*|waive\w*|bypass\w*|without|no longer|"
    r"need no|needs no|do not require|does not require|not require|auto-\w+|"
    r"after the code)\b", re.I)


def names_a_guardrail_step(fix):
    """True when `fix` asks to remove, skip or delay a step a guardrail
    backs. A false match only keeps a note out of lessons; a miss would let
    friction count towards changing a guardrail, so --guardrail exists for
    the agent to say so itself."""
    return bool(_GUARDRAIL_STEP.search(fix) and _REMOVAL.search(fix))


def is_guardrail_note(entry):
    return entry.get("source") == "agent" and bool(entry.get("guardrail"))


def _check_observed(task_dir, observed):
    """The cited evidence exists inside the issue folder: a file, or a
    devlog line as `devlog.md:<line>`."""
    root = os.path.realpath(task_dir)
    path, colon, line = observed.partition(":")
    full = os.path.realpath(os.path.join(task_dir, path))
    # The manifest is what this verb writes, so it is never evidence.
    if (os.path.commonpath([root, full]) != root or not os.path.isfile(full)
            or os.path.basename(full) == "manifest.yml"):
        raise CompassError(
            f"compass issue friction: --observed {observed} is not a file in the "
            f"issue folder. Cite evidence you observed: a path such as "
            f"evidence/red.log, or a devlog line as devlog.md:<line>.")
    if colon:
        with open(full, "rb") as fh:
            count = sum(1 for _ in fh)
        if not line.isdigit() or not 1 <= int(line) <= count:
            raise CompassError(
                f"compass issue friction: --observed {observed} names no line in "
                f"{path}, which has {count} line(s).")


def cmd_issue_friction(args):
    task_dir = resolve_issue_dir(getattr(args, "issue_slug", None))
    task, path = load_manifest(task_dir)
    fix = (args.fix or "").strip()
    if "\n" in fix:
        raise CompassError("compass issue friction: --fix must be one line.")
    if not fix:
        raise CompassError("compass issue friction: --fix is required: name the "
                           "change that would have avoided this, in one line.")
    if len(fix) > MAX_FIX:
        raise CompassError(f"compass issue friction: --fix is {len(fix)} characters; "
                           f"keep it to one line of at most {MAX_FIX}.")
    _check_observed(task_dir, args.observed)
    existing = task.get("friction") or []
    mine = [e for e in existing if isinstance(e, dict) and e.get("source") == "agent"]
    if len(mine) >= MAX_NOTES:
        raise CompassError(f"compass issue friction: this issue already has three "
                           f"agent notes, the most it takes. Keep the ones that "
                           f"matter most.")
    if any(e.get("category") == args.category and e.get("phase") == args.phase
           for e in mine):
        raise CompassError(f"compass issue friction: a note for {args.category} in "
                           f"{args.phase} is already recorded; one root cause gets "
                           f"one note.")
    guardrail = bool(args.guardrail or names_a_guardrail_step(fix))
    entry = {"phase": args.phase, "category": args.category, "source": "agent",
             "evidence": args.observed, "proposed_change": fix}
    if guardrail:
        entry["guardrail"] = True
    task["friction"] = existing + [entry]
    save_manifest(task, path)
    print(f"compass issue friction: recorded agent note {len(mine) + 1} of "
          f"{MAX_NOTES} ({args.category}, {args.phase}).")
    if guardrail:
        print(f"  {GUARDRAIL_NOTICE}: it names a step a guardrail backs, so it is "
              f"reported but never counts towards a lesson.")
    return 0


def register(issue_subs):
    """Add `compass issue friction` to the `issue` group. Not a top-level
    verb: Compass grows by groups, and a note belongs to one issue."""
    p = issue_subs.add_parser(
        "friction", help="record friction the agent observed in this issue",
        description="Record where the process cost more than it returned, with "
                    "the evidence you observed and a one-line fix. At most three "
                    "per issue; advisory, never a gate.")
    p.add_argument("--issue", dest="issue_slug", metavar="SLUG",
                   help="issue slug (default: the current-task pointer)")
    p.add_argument("--category", required=True, choices=CATEGORIES)
    p.add_argument("--phase", required=True, choices=PHASES)
    p.add_argument("--observed", required=True,
                   help="evidence in the issue folder, or devlog.md:<line>")
    p.add_argument("--fix", help=f"the change that would have avoided it, at most "
                                 f"{MAX_FIX} characters")
    p.add_argument("--guardrail", action="store_true",
                   help="the note is about a step a guardrail backs")
    p.set_defaults(func=cmd_issue_friction, output_kind="hand-off")
