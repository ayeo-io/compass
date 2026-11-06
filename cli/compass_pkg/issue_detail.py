# compass_pkg.issue_detail - the facts of one issue that the board reads
"""One function that reads an issue's approach, state, stage and gate count.

`compass flow` (the board) calls `detail` through this module, not by name, so a
test can replace it and see the board follow (ADR-051). Before 9.0.0 the header
block of the issue page called it too (ADR-091 removed the page).

The function takes the manifest and the issue's folder and reads nothing else,
unless the caller passes a reader for the issues it depends on (ADR-062), so the
board can read an issue from another worktree (ADR-048).

This module is a leaf: it imports `lifecycle`, `status_words` and `effective`
(inside a function), and none of `flow` or `check_cmd`.
"""
# DEPENDENCY: standard library (dataclasses, os); compass_pkg.lifecycle,
# status_words, effective (imported inside a function).
from __future__ import annotations

import os
from dataclasses import dataclass

from compass_pkg import lifecycle, status_words

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


def _documents(manifest, task_dir=None, other=False):
    """The documents an older release registered, each as the facts a reader shows.
    9.0.0 registers none and judges none owed (ADR-091), so `text` is always None; the
    key stays so a reader of the old shape still parses it."""
    found = []
    for entry in manifest.get("artifacts") or []:
        if isinstance(entry, dict) and entry.get("kind"):
            rnd = entry.get("round")
            text = None
            fact = {"id": str(entry.get("id") or ""), "kind": str(entry["kind"]),
                    "round": rnd if isinstance(rnd, int) else None,
                    "status": str(entry.get("status") or ""),
                    "path": str(entry.get("path") or ""), "text": text}
            # Only a unit's entry carries the key, so the `--json` of every other
            # document reads as it did before units existed.
            if entry.get("unit"):
                fact["unit"] = str(entry["unit"])
            found.append(fact)
    return tuple(found)


def _refuse_another_major(manifest, task_dir, other):
    """Raise the major refusal of an issue whose generation another major built, unless the
    caller views many issues (`other`). Before 9.0.0 the document rows read the issue's
    configuration and raised it on the way; they read none now (ADR-091), so the read is
    made here and its result is not used."""
    if not task_dir or other:
        return
    from compass_pkg import effective
    try:
        effective.view_or_legacy(task_dir, manifest=manifest)
    except effective.MajorRefusal:
        raise
    except Exception:                                       # noqa: BLE001 - no configuration
        return


def _stage(manifest, task_dir, state):
    """`(stage, problem)`, from `lifecycle.stage_of`: the dependency derivation
    compares stages there, so the board and the derivation read one rule."""
    return lifecycle.stage_of(manifest, task_dir, state)


def detail(manifest, task_dir, read=None, other=False):
    """The `IssueDetail` of one issue. `read` is a `lifecycle` reader for the
    issues it depends on; without one, no dependency is judged. `other` is for a
    view of many issues: a generation built by another major is then not refused."""
    _refuse_another_major(manifest, task_dir, other)
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
                       _documents(manifest, task_dir, other), waits, deps)


def state_text(manifest, task_dir):
    """The state as a reader sees it: `done (completed)` for a closed issue, the
    state word for any other. A blocked flag is not named."""
    state = lifecycle.state_of(manifest, task_dir)
    reason = status_words.close_reason(manifest)
    return "%s (%s)" % (state, reason) if state == "done" and reason else state
