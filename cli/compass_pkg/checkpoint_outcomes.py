# compass_pkg.checkpoint_outcomes - the record of each stage hand-off
"""What happened at each checkpoint stage hand-off of an issue.

A checkpoint stage is one of assess, define, refine and plan
(`core.CHECKPOINT_STAGES`). The manifest's `checkpoint_outcomes` holds one
entry per stage that has an outcome:

    {stage, outcome, by, at}            outcome: skipped
    {stage, outcome, by, at, evidence}  outcome: waited

- `waited` means a person answered the hand-off. Only `compass evidence
  approve --checkpoint` writes it, with a `checkpoint-approval` evidence record
  that `evidence` names (`approve_cmd`).
- `skipped` means the autonomy setting passed the hand-off and an agent went
  on. `compass issue checkpoint add` writes it, and writes no evidence record.

One outcome is kept per stage. A person's later answer replaces `skipped`; a
`skipped` never replaces `waited`.

Only an issue whose manifest holds the `checkpoint_outcomes` key is judged.
The first assessment writes it as an empty list; nothing adds it to an issue
assessed before outcomes were recorded, so both commands refuse such an issue
rather than turn it into a judged one.

Every reader uses the functions here, so they agree on what an outcome is.
Owning decision: `architecture/decisions/ADR-063-*.md`.
"""
# DEPENDENCY: standard library (os); compass_pkg.core, decisions_taken, terminal.
from __future__ import annotations

import os

from compass_pkg.core import (CHECKPOINT_STAGES, CompassError, load_manifest, now_iso,
                              resolve_issue_dir, save_manifest)
from compass_pkg.terminal import say

WAITED, SKIPPED = "waited", "skipped"
OUTCOMES = (WAITED, SKIPPED)
KEY = "checkpoint_outcomes"

#: The stage weights under which a route runs no hand-off for the stage.
_NOT_RUN = ("skipped", "collapsed", "none")

#: How a person records an answer, for the refusals that send them there.
_APPROVE = ("compass evidence approve --checkpoint {stage} --approver <you> "
            "--role <role>")


def judged(task) -> bool:
    """True when the issue takes outcomes: its manifest holds the key, an
    empty list included."""
    return isinstance(task, dict) and KEY in task


def outcomes(task) -> dict:
    """`{stage: entry}` for every well-formed entry; a later entry for the same
    stage wins. An entry of the wrong shape is passed over."""
    found = {}
    value = task.get(KEY) if isinstance(task, dict) else None
    for entry in value if isinstance(value, list) else []:
        if (isinstance(entry, dict) and entry.get("stage") in CHECKPOINT_STAGES
                and entry.get("outcome") in OUTCOMES):
            found[entry["stage"]] = entry
    return found


def listed(task) -> list:
    """The checkpoint stages in the manifest's `checkpoints:` list, when it is
    a list."""
    value = task.get("checkpoints") if isinstance(task, dict) else None
    return [s for s in value if s in CHECKPOINT_STAGES] if isinstance(value, list) else []


def missing(task) -> list:
    """The listed checkpoints with no outcome; none for an issue not judged."""
    if not judged(task):
        return []
    have = outcomes(task)
    return [stage for stage in listed(task) if stage not in have]


def stage_runs(task, stage) -> bool:
    """True when the route runs the stage, so it has a hand-off."""
    stages = task.get("stages") if isinstance(task, dict) else None
    weight = stages.get(stage) if isinstance(stages, dict) else None
    return bool(weight) and weight not in _NOT_RUN


def set_outcome(task, entry):
    """Make `entry` the stage's one outcome, in the place of any earlier one."""
    kept = [e for e in task.get(KEY) or []
            if not (isinstance(e, dict) and e.get("stage") == entry["stage"])]
    task[KEY] = kept + [entry]


def _joined(stages):
    if len(stages) == 1:
        return stages[0]
    return ", ".join(stages[:-1]) + " and " + stages[-1]


def landing_refusal(task, task_dir):
    """The refusal text for a judged issue that lists a checkpoint with no
    outcome, or None. The first entry of `manifest.LANDING_REFUSALS`."""
    stages = missing(task)
    if not stages:
        return None
    from compass_pkg import refusals
    return refusals.render(
        "checkpoint-no-outcome", slug=os.path.basename(os.path.normpath(task_dir)),
        stages=_joined(stages), stage=stages[0],
        **{"is": "is" if len(stages) == 1 else "are",
           "it": "it" if len(stages) == 1 else "them"})


def landing_issue(args):
    """`(manifest, folder)` of the issue a landing is for - from `--issue`,
    `COMPASS_ISSUE` or the current-task pointer - or None when none is named or
    it cannot be read. The most recently changed issue is never guessed: a
    refusal must not judge an issue the landing is not for."""
    from compass_pkg.core import find_compass_dir, session_issue
    try:
        slug = getattr(args, "task", None) or session_issue()
        if not slug:
            with open(os.path.join(find_compass_dir(), "current-task"),
                      encoding="utf-8") as fh:
                slug = fh.read().strip()
        if not slug:
            return None
        task_dir = resolve_issue_dir(slug)
        task, _ = load_manifest(task_dir)
    except (CompassError, OSError, ValueError):
        return None
    return (task, task_dir) if isinstance(task, dict) else None


def refuse_unjudged(task, task_dir, verb):
    if not judged(task):
        slug = os.path.basename(os.path.normpath(task_dir))
        raise CompassError(
            f"{verb}: '{slug}' was assessed before checkpoint outcomes were recorded, so it "
            f"is not judged and takes no outcome; nothing was written.")


def refuse_stage(task, stage, verb):
    """Refuse a stage that is not a checkpoint stage, or one the route does not run."""
    if stage not in CHECKPOINT_STAGES:
        raise CompassError(
            f"{verb}: '{stage}' is not a checkpoint stage; a checkpoint is one of "
            f"{', '.join(CHECKPOINT_STAGES)}. Nothing was written.")
    if not stage_runs(task, stage):
        weight = ((task.get("stages") or {}).get(stage)
                  if isinstance(task.get("stages"), dict) else None)
        raise CompassError(
            f"{verb}: the approach runs no {stage} hand-off ({stage} is "
            f"{weight or 'not in the approach'}), so it takes no outcome. Nothing was written.")


def cmd_checkpoint_add(args):
    """`compass issue checkpoint add <stage> --outcome skipped --by <agent>`."""
    from compass_pkg.decisions_taken import agent_names
    verb = "compass issue checkpoint add"
    stage, by = args.stage, " ".join(str(args.by or "").split())
    task_dir = resolve_issue_dir(args.task)
    task, path = load_manifest(task_dir)
    refuse_unjudged(task, task_dir, verb)
    if stage not in CHECKPOINT_STAGES:
        refuse_stage(task, stage, verb)
    if args.outcome == WAITED:
        raise CompassError(f"{verb}: only a person's approval records waited; run "
                           + _APPROVE.format(stage=stage) + ".")
    refuse_stage(task, stage, verb)
    current = outcomes(task).get(stage)
    if current and current.get("outcome") == WAITED:
        raise CompassError(
            f"{verb}: {stage} already holds a waited outcome by {current.get('by')}, and a "
            f"skip never replaces a person's answer. Nothing was written.")
    if stage in listed(task):
        raise CompassError(
            f"{verb}: {stage} is a listed checkpoint, so it waits for a person; run "
            + _APPROVE.format(stage=stage) + ".")
    if by not in agent_names():
        raise CompassError(
            f"{verb}: --by must name an agent, such as spec-author or planner, not "
            f"'{by}'. A person answers a hand-off with compass evidence approve "
            f"--checkpoint {stage}. Nothing was written.")
    if current:
        return say(args, f"{verb}: {stage} is already recorded as skipped; nothing was "
                         f"written.", stage=stage, recorded=SKIPPED, written=False)
    set_outcome(task, {"stage": stage, "outcome": SKIPPED, "by": by,
                       "at": now_iso().replace("+00:00", "Z")})
    save_manifest(task, path)
    return say(args, f"{verb}: {stage} recorded as skipped by {by}.",
               stage=stage, recorded=SKIPPED, by=by, written=True)


def register(issue_subs, issue_arg):
    """Add the `checkpoint` group to `compass issue`."""
    group = issue_subs.add_parser(
        "checkpoint", help="the record of a stage hand-off the autonomy setting passed")
    subs = group.add_subparsers(dest="checkpoint_cmd", required=True)
    add = subs.add_parser(
        "add", help="record that a checkpoint hand-off was passed without waiting")
    add.add_argument("stage", help="assess, define, refine or plan")
    add.add_argument("--outcome", required=True, choices=OUTCOMES,
                     help="skipped; a waited outcome is a person's, through "
                          "compass evidence approve --checkpoint")
    add.add_argument("--by", required=True, help="the agent that went on")
    issue_arg(add)
    add.set_defaults(func=cmd_checkpoint_add, output_kind="hand-off")
