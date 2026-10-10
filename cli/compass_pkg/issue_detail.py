# compass_pkg.issue_detail - the facts of one issue that the board and the issue page share
"""One function that reads an issue's approach, state, stage and gate count.

`compass flow` (the board) and the header block of the issue page both call
`detail` through this module, so the two cannot disagree (RS-8, ADR-051). They
call it through the module, not by name, so a test can replace it and see both
surfaces follow.

The function takes the manifest and the issue's folder and reads nothing else.
The board can read an issue from another worktree (ADR-048) while the page reads
this checkout, so the two share the function and not the checkout.

This module is a leaf: it imports `lifecycle`, `next_cmd` and `status_words`, and none
of `flow`, `check_cmd` or `render_cmd`.
"""
# DEPENDENCY: standard library (dataclasses); compass_pkg.lifecycle, next_cmd,
# status_words, stable_ids.
from __future__ import annotations

from dataclasses import dataclass

from compass_pkg import lifecycle, status_words
from compass_pkg.stable_ids import STAGE_ASSESS

NOT_ASSESSED = "not assessed"


@dataclass(frozen=True)
class IssueDetail:
    approach: str
    state: str
    #: The stage `compass next` names, `done` for a closed issue; None when it could not be read.
    stage: object
    gates_passed: int
    gates_total: int
    #: Why the stage could not be read, else None.
    stage_problem: object = None

    @property
    def gates(self):
        return "%d/%d" % (self.gates_passed, self.gates_total)


def _gate_counts(manifest):
    gates = manifest.get("gates")
    entries = [g for g in gates if isinstance(g, dict)] if isinstance(gates, list) else []
    return sum(1 for g in entries if g.get("status") == "pass"), len(entries)


def _stage(manifest, task_dir, state, recorded):
    """`(stage, problem)`. A closed issue is at `done`; an issue with no delivery
    approach is at assess; every other issue is where `compass next` puts it."""
    from compass_pkg import next_cmd
    if state == "done":
        return "done", None
    if state in ("backlog", "ready") and not recorded:
        return STAGE_ASSESS, None
    try:
        return next_cmd._current_phase_from_task(manifest, task_dir) or "done", None
    except Exception as exc:                                # noqa: BLE001
        return None, "the stage could not be read (%s)" % type(exc).__name__


def detail(manifest, task_dir):
    """The `IssueDetail` of one issue."""
    state = lifecycle.state_of(manifest, task_dir)
    recorded = bool(manifest.get("delivery_approach"))
    stage, problem = _stage(manifest, task_dir, state, recorded)
    passed, total = _gate_counts(manifest)
    return IssueDetail(str(manifest.get("delivery_approach") or NOT_ASSESSED), state, stage,
                       passed, total, problem)


def state_text(manifest, task_dir):
    """The state as a reader sees it: `done (completed)` for a closed issue, the
    state word for any other. A blocked flag is not named."""
    state = lifecycle.state_of(manifest, task_dir)
    reason = status_words.close_reason(manifest)
    return "%s (%s)" % (state, reason) if state == "done" and reason else state
