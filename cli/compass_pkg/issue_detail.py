# compass_pkg.issue_detail - the facts of one issue that the board and the issue page share
"""One function that reads an issue's approach, state, stage and gate count.

`compass flow` (the board) and the header block of the issue page both call
`detail` through this module, so the two cannot disagree (ADR-051). They
call it through the module, not by name, so a test can replace it and see both
surfaces follow.

The function takes the manifest and the issue's folder and reads nothing else,
unless the caller passes a reader for the issues it depends on (ADR-062). The
board can read an issue from another worktree (ADR-048) while the page reads
this checkout, so the two share the function and not the checkout.

This module is a leaf: it imports `lifecycle`, `next_cmd` and `status_words`, and none
of `flow`, `check_cmd` or `render_cmd`.
"""
# DEPENDENCY: standard library (dataclasses, os); compass_pkg.lifecycle, next_cmd,
# readiness_record, status_words, stable_ids.
from __future__ import annotations

import os
from dataclasses import dataclass

from compass_pkg import artifact_owed, lifecycle, readiness_record, status_words

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
    #: The reason of the blocked flag while it counts (an issue in progress or in review), else None.
    blocked: object = None
    #: The repository readiness line, from the manifest's `readiness:` summary.
    readiness: str = ""
    #: One `{id, kind, round, status, path}` for each registered document, in registry order. A
    #: kind that repeats has one for each round, so no reader shows only the first, and a
    #: kind with a document per work unit has one for each `unit`.
    documents: tuple = ()
    #: The dependency block (`lifecycle.dependency_block`) while it counts, else None. Read
    #: only when the caller passes a reader; `blocked` stays the stored flag's reason.
    waits: object = None
    #: Each `depends_on` entry judged (`lifecycle.Dependency`), when the caller passes a reader.
    dependencies: tuple = ()

    @property
    def gates(self):
        return "%d/%d" % (self.gates_passed, self.gates_total)


def _gate_counts(manifest):
    gates = manifest.get("gates")
    entries = [g for g in gates if isinstance(g, dict)] if isinstance(gates, list) else []
    return sum(1 for g in entries if g.get("status") == "pass"), len(entries)


def _view(task_dir, manifest=None):
    from compass_pkg import effective
    try:
        return effective.view_or_legacy(task_dir, manifest=manifest)
    except Exception:                                       # noqa: BLE001 - nothing declares a condition
        return None


def _documents(manifest, task_dir=None):
    """The registered documents, each as the facts a reader shows. `text` is the
    "not needed: ..." line of a document whose condition is false and that has no
    file. It comes from `artifact_owed`, the function the issue page uses."""
    found = []
    view, read = None, False
    for entry in manifest.get("artifacts") or []:
        if isinstance(entry, dict) and entry.get("kind"):
            rnd = entry.get("round")
            text = None
            if task_dir and not entry.get("path") and entry.get("status") != "omitted":
                if not read:
                    view, read = _view(task_dir, manifest), True
                text = artifact_owed.not_needed(manifest, view, entry)
            found.append({"id": str(entry.get("id") or ""), "kind": str(entry["kind"]),
                          "round": rnd if isinstance(rnd, int) else None,
                          "unit": str(entry["unit"]) if entry.get("unit") else None,
                          "status": str(entry.get("status") or ""),
                          "path": str(entry.get("path") or ""), "text": text})
    return tuple(found)


def _stage(manifest, task_dir, state):
    """`(stage, problem)`, from `lifecycle.stage_of`: the dependency derivation
    compares stages there, so the board and the derivation read one rule."""
    return lifecycle.stage_of(manifest, task_dir, state)


def detail(manifest, task_dir, read=None):
    """The `IssueDetail` of one issue. `read` is a `lifecycle` reader for the
    issues it depends on; without one, no dependency is judged."""
    state = lifecycle.state_of(manifest, task_dir)
    stage, problem = _stage(manifest, task_dir, state)
    passed, total = _gate_counts(manifest)
    flag = lifecycle.blocked_flag(manifest, task_dir)
    deps, waits = (), None
    if read is not None:
        deps = lifecycle.judge(manifest, os.path.basename(os.path.normpath(task_dir)), read)
        waits = lifecycle.dependency_block(manifest, task_dir, deps, stage=stage)
    return IssueDetail(str(manifest.get("delivery_approach") or NOT_ASSESSED), state, stage,
                       passed, total, problem,
                       str(flag.get("reason") or "no reason recorded") if flag else None,
                       readiness_record.line(manifest.get("readiness")),
                       _documents(manifest, task_dir), waits, deps)


def state_text(manifest, task_dir):
    """The state as a reader sees it: `done (completed)` for a closed issue, the
    state word for any other. A blocked flag is not named."""
    state = lifecycle.state_of(manifest, task_dir)
    reason = status_words.close_reason(manifest)
    return "%s (%s)" % (state, reason) if state == "done" and reason else state
