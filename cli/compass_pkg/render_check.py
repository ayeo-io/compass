# compass_pkg.render_check - the check `rendered-blocks-current`
"""The check `rendered-blocks-current` (implementation 1.0.0, ADR-051).

It runs the render of `render_cmd.plan_issue` without writing and compares. A
block is current when the render would not change a byte of it, so the check has
no second definition of "current" (DD-2).

Each block has a scope (`block_renderers.Part`):

- an **own** block draws only on this issue's records. A stale one fails the
  check at verify, ship and done, and is an advisory failure before;
- a **cross** block draws on other issues or on the project (`related`, the
  governance lines of `decisions`, the issue's row of the project index). A stale
  one is always an advisory failure, because a checkout that holds one issue
  cannot judge it (DCJ-79).

The issue's own manifest is read with `load_manifest`, never through the parse
cache, so a planted cache entry cannot clear or fail the check (DCJ-77).
"""
# DEPENDENCY: standard library (os); compass_pkg.render_cmd, block_renderers,
# next_cmd, status_words, stable_ids. check_cmd is imported inside `check`
# because check_cmd imports the registry that imports this module.
from __future__ import annotations

import os

from compass_pkg import block_renderers, status_words
from compass_pkg.core import CompassError

CHECK_ID = "rendered-blocks-current"
FIX = "run `compass issue render`"


def _blocking(task, task_dir):
    """True once the issue has reached verify, or is done: a stale own block
    then fails the check. Before verify it is an advisory failure."""
    from compass_pkg import next_cmd
    from compass_pkg.stable_ids import STAGE_IDS, STAGE_VERIFY
    if status_words.is_closed(task):
        return True
    phase = next_cmd._current_phase_from_task(task, task_dir)
    if phase is None:
        return True
    order = list(STAGE_IDS)
    return phase in order and order.index(phase) >= order.index(STAGE_VERIFY)


def stale_parts(plan):
    """`(own, cross)`: the lines that name each stale block, as
    `<path>: block <kind> ...`, or the missing issue page."""
    own, cross = [], []
    for item in plan.files:
        if item.is_new:
            own.append("%s: the issue page is missing - %s" % (item.rel, FIX))
            continue
        for kind in item.changed_kinds:
            line = "%s: block %s no longer matches the records - %s" % (item.rel, kind, FIX)
            (cross if item.scopes.get(kind) == block_renderers.CROSS else own).append(line)
    return own, cross


def check(task, task_dir):
    """`(passed, detail)` for `compass check`. `task` is not read: the render
    reads the manifest from `task_dir` itself."""
    from compass_pkg import render_cmd
    from compass_pkg.check_cmd import ADVISORY_FAILURE
    task_dir = os.path.abspath(task_dir)
    try:
        plan = render_cmd.plan_issue(task_dir)
    except CompassError as exc:
        # A marker that does not parse is the issue's own document.
        detail = "%s - fix the marker, then %s" % (str(exc).replace("\n", " "), FIX)
        return (False if _blocking(task, task_dir) else ADVISORY_FAILURE), detail
    own, cross = stale_parts(plan)
    if own:
        detail = "; ".join(own + cross)
        return (False if _blocking(task, task_dir) else ADVISORY_FAILURE), detail
    if cross:
        return ADVISORY_FAILURE, "; ".join(cross)
    shown = sum(len(f.kinds) for f in plan.files)
    return True, "every rendered block matches the records (%d block kind(s) in %d document(s))" % (
        shown, len(plan.files))
