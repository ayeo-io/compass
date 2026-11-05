#!/usr/bin/env python3
# =============================================================================
# compass_pkg.next_cmd - `compass next`
# =============================================================================
#
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/ and pinned in
# THIRD-PARTY-NOTICES.md. cli/compass_pkg/__init__.py resolves it, and it is
# the only third-party code Compass ships; everything else is the Python 3
# standard library.
# =============================================================================

# The pre-tool hook's dependency reader imports this module through
# `lifecycle`, and the hook's readers run under a python3 older than 3.10 too
# (docs/safety-contract.md), where a `str | None` annotation fails at import.
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

# --- dependency check --------------------------------------------------------
# cli/compass_pkg/__init__.py already checked that the bundled copy resolves,
# or exited 3 naming the absolute path it checked, before this module's own
# code runs, so this is never anything but a normal import.
import yaml


import re as _re


import fnmatch
import re as _re
from compass_pkg import status_words
from compass_pkg.stable_ids import (
    APPROACH_QUICK_FIX, REMOVED_GATE_IDS, STAGE_ASSESS, STAGE_BREAKDOWN, STAGE_DEFINE, STAGE_IDS,
    STAGE_IMPLEMENT, STAGE_PLAN, STAGE_REFINE, STAGE_SHIP, STAGE_VERIFY)
from compass_pkg.manifest_store import load_manifest_mapping
from compass_pkg.core import (CompassError, artifact_path, canonical_shape, manifest_path,
                              normalize_spine, resolve_issue_dir)

# --- command: next -----------------------------------------------------------
# `compass next` reads manifest.yml and prints ONE
# line (at a terminal, framed by the rail; see `_emit`): the next stage, the next uncleared gate, and delivery-approach-aware
# collapsed-stage markers. It is strictly READ-ONLY over
# .compass/work/<task>/ - no file is written or created. It derives its
# answer from manifest.yml, and checks evidence/
# and the .red marker for a red the manifest does not list.
#
# The plain line, which is all piped output and the model ever see:
#   "<NextPhase> [gate: <gate-id>][ | <phase> collapsed in this approach]"
# When the issue has landed:
#   "all phases complete"
# When the manifest records no delivery approach:
#   exit non-zero with a message naming assess
# When manifest.yml is missing (assess has not run):
#   exit non-zero with a message naming assess
#
# The canonical stage order Compass follows:
# The current keys. `normalize_spine` maps a retired key forward on load, so a
# list written in the retired spelling would stop matching every manifest it
# reads, and `compass next` would report the wrong stage instead of failing.
_PHASE_ORDER = list(STAGE_IDS)

# Weights that show a stage was deliberately left out of this delivery approach
_SKIPPED_WEIGHTS = {"skipped", "collapsed"}


def _next_active_phase(phases: dict) -> str | None:
    """Return the slug of the next stage that actively runs on this delivery approach.

    Skipped / collapsed stages are bypassed.  Returns None when every stage
    has a skipped weight (degenerate delivery approach) or phases is empty.
    """
    for p in _PHASE_ORDER:
        weight = (phases.get(p) or "").strip().lower()
        if weight not in _SKIPPED_WEIGHTS:
            return p
    return None


def _detect_collapsed_phases(phases: dict) -> list:
    """Return stage names (title-cased) that are collapsed on this delivery approach."""
    out = []
    for p in _PHASE_ORDER:
        weight = (phases.get(p) or "").strip().lower()
        if weight == "collapsed":
            out.append(p.capitalize())
    return out


def _typed(task: dict) -> dict:
    """The manifest with `gates` as a list and `stages` as a mapping of strings.

    A hand-edited manifest can hold anything, and every reader below
    assumes these two shapes. A value of the wrong type is read as empty,
    so `compass next` and the status line still name a stage.
    """
    if not isinstance(task, dict):
        return task
    gates = task.get("gates")
    stages = task.get("stages")
    stages = stages if isinstance(stages, dict) else {}
    return dict(task,
                gates=gates if isinstance(gates, list) else [],
                stages={k: v if isinstance(v, str) else "" for k, v in stages.items()})


def _first_pending_gate(gates: list) -> str | None:
    """Return the id of the first gate whose status is not 'pass'. A gate a release
    removed owes nothing, so it is never the next one to clear."""
    for g in (gates or []):
        if (isinstance(g, dict) and g.get("status") != "pass"
                and g.get("id") not in REMOVED_GATE_IDS):
            return g.get("id")
    return None


def _all_gates_pass(gates: list) -> bool:
    """True when every gate is marked pass. A gate a release removed owes nothing
    (`gate_status`), so the issue is past the verify stage while only that gate is pending."""
    from compass_pkg import gate_status
    return gate_status.all_gates_passed({"gates": gates})


def _entries(task: dict, key: str) -> list:
    """The dict entries of a manifest list. A hand-edited manifest can hold
    anything, and `compass next` must still name a stage."""
    value = task.get(key)
    return [e for e in value if isinstance(e, dict)] if isinstance(value, list) else []


def _registered(task: dict, kind: str) -> bool:
    """True when the manifest registers the `kind` document: an entry with a
    path at any status but `superseded`, or one recorded as omitted. A stage
    command writes the status (`draft` at registration, `approved` once a later
    stage records its work), but a person can hold a document at `draft` or
    `awaiting-approval` and the stage is still recorded, so the status cannot
    be what counts."""
    for a in _entries(task, "artifacts"):
        if a.get("kind") != kind:
            continue
        if a.get("status") == "omitted" or (a.get("path") and a.get("status") != "superseded"):
            return True
    return False


def _earned(task: dict, kind: str) -> bool:
    """True when the issue's route earns the `kind` document. Before 9.0.0
    `approach evaluate` seeded an entry for every document the route earned;
    9.0.0 writes no `artifacts:` list (ADR-091), so a newer issue earns none."""
    return any(a.get("kind") == kind for a in _entries(task, "artifacts"))


def _review_written(task_dir: str | None) -> bool:
    """True when the issue's requirements review exists on disk, registered
    or not. The resolver finds a registered one, or one beside the manifest
    as issues before 5.0.0 kept it; an unregistered one in the documents
    folder is what refine wrote before 9.0.0 on a route that did not earn it."""
    if not task_dir:
        return False
    from compass_pkg.core import unregistered_document
    name = "requirements-review.md"
    return (os.path.isfile(artifact_path(task_dir, name))
            or unregistered_document(task_dir, name) is not None)


def _handed_off(task: dict, stage: str) -> bool:
    """True when the manifest records the hand-off of `stage`: `skipped`, written
    by `compass issue checkpoint add`, or `waited`, written when a person
    approved it. Every route that runs the stage records one or the other."""
    from compass_pkg import checkpoint_outcomes
    return stage in checkpoint_outcomes.outcomes(task)


def _testing_started(task: dict, task_dir: str | None) -> bool:
    """True once any test result is on record: a test-run in the manifest, or
    a red that `compass tdd-red` wrote, which the manifest does not list. A red
    that ends stage 1 (`before_implement`) is written at refine, so it does not
    count (ADR-081)."""
    if any(e.get("type") == "test-run" for e in _entries(task, "evidence")):
        return True
    if not task_dir:
        return False
    if os.path.isfile(os.path.join(task_dir, ".red")):
        return True
    try:
        names = os.listdir(os.path.join(task_dir, "evidence"))
    except OSError:
        return False
    from compass_pkg.red_first import load_record
    return any(n.startswith("red") and n.endswith(".json") and not load_record(
        os.path.join(task_dir, "evidence", n)).get("before_implement") for n in names)


def _every_scenario_tested(task: dict) -> bool:
    """True when each scenario that needs a test has a test-run bound to it.
    A `verifiable: narrative` scenario is cleared by its written body, so it
    never gets one."""
    ids = [s["id"] for s in _entries(task, "scenarios")
           if isinstance(s.get("id"), str) and s.get("verifiable") != "narrative"]
    tested = {e["scenario"] for e in _entries(task, "evidence")
              if e.get("type") == "test-run" and isinstance(e.get("scenario"), str)}
    return bool(ids) and all(i in tested for i in ids)


def _stages_on_record(task: dict, task_dir: str | None) -> set:
    """The stages the records on disk show as done.

    A stage is done when its own record exists, or when a later stage's
    does. The second rule covers a record that was never written, such as
    a hand-off nobody recorded before the builder started. `compass next` cannot
    run without the approach record, so assess is always done. Ship's
    record, a closed issue, is handled by the callers before they ask for
    a stage.
    """
    own = {
        STAGE_ASSESS: True,
        # A quick fix earns no criteria document; its scenarios are define's
        # record.
        STAGE_DEFINE: (_registered(task, "acceptance-criteria")
                   or bool(_entries(task, "scenarios"))),
        # 9.0.0 writes no requirements review and no technical design
        # (ADR-091), so refine and plan are done when their hand-off is on
        # record. An issue made before 9.0.0 can hold the document instead:
        # refine's review, registered where the route earned it and otherwise
        # read from the file, and plan's registered design.
        STAGE_REFINE: (_handed_off(task, STAGE_REFINE)
                   or _registered(task, "requirements-review")
                   or (not _earned(task, "requirements-review")
                       and _review_written(task_dir))),
        STAGE_PLAN: _handed_off(task, STAGE_PLAN) or _registered(task, "technical-design"),
        # Breakdown records nothing of its own: one session builds the units
        # (ADR-090), and 9.0.0 writes no distribution map (ADR-091). It is done
        # once plan is handed off, unless the route earned a map before 9.0.0.
        STAGE_BREAKDOWN: (bool(_entries(task, "subtasks"))
                          or _registered(task, "distribution-map")
                          or (_handed_off(task, STAGE_PLAN)
                              and not _earned(task, "distribution-map"))),
        STAGE_IMPLEMENT: _every_scenario_tested(task),
        STAGE_VERIFY: _all_gates_pass(task.get("gates") or []),
        STAGE_SHIP: False,
    }
    reached = max(i for i, p in enumerate(_PHASE_ORDER) if own[p])
    if _testing_started(task, task_dir):
        # A test on record means the builder is at work, so every stage
        # before implement is behind it.
        reached = max(reached, _PHASE_ORDER.index("implement") - 1)
    return set(_PHASE_ORDER[:reached + 1])


def _current_phase_from_task(task: dict, task_dir: str | None = None) -> str | None:
    """The stage the issue has reached, or None when every stage that runs
    on its delivery approach is done.

    A top-level `current_phase` key wins when present. Nothing in Compass
    writes it, but test fixtures and hand-edited manifests use it.
    Otherwise the stage is the first one that runs on the approach and is
    not done on the records (`_stages_on_record`).
    """
    cp = task.get("current_phase")
    if cp and isinstance(cp, str):
        return cp.strip().lower()
    phases = task.get("stages") or {}
    done = _stages_on_record(task, task_dir)
    for p in _PHASE_ORDER:
        weight = (phases.get(p) or "").strip().lower()
        if weight not in _SKIPPED_WEIGHTS and p not in done:
            return p
    return None


def _unmet_entry(task: dict, task_dir: str, stage: str) -> list:
    """The ids of the active entry checks of `stage` that fail (the shipped
    checks only where `entry-exit-evaluation` is on). `compass next` must
    still name a stage when the configuration cannot be read, so any fault
    gives none."""
    try:
        from compass_pkg import effective, stage_lists
        view = effective.view_or_legacy(task_dir)
        return stage_lists.unmet_entry(stage_lists.evaluate(view, task, task_dir), stage)
    except Exception:  # noqa: BLE001 - the stage line is the answer; this is extra
        return []


def _emit(args, task, task_dir, line, current_phase, finished, hint=True):
    """Write `line`, today's output, opened by the rail when a person is
    reading. compass_pkg.render decides that; piped output, `CLAUDECODE`,
    `--json`, `--quiet` and `--evidence-out` all get `line` unchanged."""
    from compass_pkg.core import display_shape, display_stage
    from compass_pkg.render import header, rail, rail_style, stage_states, wrap
    from compass_pkg.terminal import resolve_mode

    style = None if getattr(args, "evidence_out", None) else rail_style(
        sys.stdout, resolve_mode(args))
    if not style:
        sys.stdout.write(line)
        return
    try:
        approach = task.get("delivery_approach") or ""
        slug = task.get("issue") or os.path.basename(task_dir.rstrip(os.sep))
        states = stage_states(_PHASE_ORDER, task.get("stages") or {}, current_phase,
                             finished, _SKIPPED_WEIGHTS)
        out = [header([display_shape(approach), slug], style)]
        out += rail([(display_stage(k).capitalize(), st) for k, st in states], style)
        # The plain line is wrapped here only; piped output keeps it whole.
        out += [""] + wrap(line.rstrip("\n"))
        if hint and not finished and current_phase in _PHASE_ORDER:
            quick = canonical_shape(approach) == APPROACH_QUICK_FIX
            out += wrap("Next: /compass:" + ("quick-fix" if quick else display_stage(current_phase)))
        text = "\n".join(out) + "\n"
        # Checked before writing, so a terminal that cannot show the glyphs
        # gets today's line rather than half a rail and a traceback.
        text.encode(sys.stdout.encoding or "utf-8")
    except Exception:  # noqa: BLE001 - the rail is decoration; the line must still print
        text = line
    sys.stdout.write(text)


def _dependency_block(task, task_dir, stage):
    """The waits of the issues this one depends on, while it is at implement,
    else None. Read uncached from this checkout, as the pre-tool hook reads
    them, so the two cannot disagree. An issue without `depends_on` reads
    nothing."""
    if not task.get("depends_on"):
        return None
    # Imported here: lifecycle imports this module at its top.
    from compass_pkg import lifecycle
    # Out of scope (not at implement, held or closed): no dependency is read.
    if not lifecycle.in_scope(task, task_dir, stage):
        return None
    folder = os.path.normpath(task_dir)
    deps = lifecycle.judge(task, os.path.basename(folder),
                           lifecycle.checkout_reader(os.path.dirname(folder)))
    return lifecycle.dependency_block(task, task_dir, deps, stage=stage)


def cmd_next(args):
    """compass next - what comes next on this issue's delivery approach?

    Reads manifest.yml and prints ONE line, framed
    by the rail when a person reads it at a terminal.
    Strictly read-only.
    """
    task_dir = resolve_issue_dir(getattr(args, "task", None))

    # --- manifest.yml: must exist (assess check) ---
    task_path = manifest_path(task_dir)
    # Each refusal goes to stderr with paths from the project root, as every
    # other verb's refusal does.
    if not os.path.isfile(task_path):
        raise CompassError(
            "assess has not run for this issue - manifest.yml is missing.\n"
            f"  Run /compass:assess to start the issue at: {task_dir}")

    task = _typed(normalize_spine(load_manifest_mapping(task_path)))

    # --- the delivery approach: must be decided ---
    # The manifest holds the decision; 9.0.0 writes no delivery-approach.md (ADR-091).
    if not task.get("delivery_approach"):
        raise CompassError(
            f"assess has not chosen a delivery approach for {task_dir}\n"
            "  Run /compass:assess to record one before using compass next.")

    # --- completed issue ---
    # Passed gates alone do not finish it: ship still runs, and a closed
    # issue is ship's record.
    gates = task.get("gates") or []
    if status_words.is_closed(task):
        _emit(args, task, task_dir, "all phases complete\n", None, True)
        return 0

    # --- determine next stage and collapsed siblings ---
    phases = task.get("stages") or {}
    current_phase = _current_phase_from_task(task, task_dir)

    # The "next stage" is the current_phase: the first stage that runs on
    # this approach and is not done on the records.
    next_phase = current_phase
    if not next_phase:
        # No current stage derivable - delivery approach is complete or degenerate
        _emit(args, task, task_dir, "all phases complete\n", None, True)
        return 0

    # The stage 2 and 3 reviews of strategy `S17`: a rejected one sends the
    # issue back to its stage, and a listed one with no outcome waits.
    from compass_pkg import checkpoint_outcomes
    done = _stages_on_record(task, task_dir)
    back, review_wait, review_note = checkpoint_outcomes.next_review(task, task_dir, done)
    next_phase = back or next_phase

    # Find the first pending gate for the "next gate" display
    pending_gate = _first_pending_gate(gates)

    # Collapsed stages on this delivery approach
    collapsed = _detect_collapsed_phases(phases)

    # --- compose the one-line output ---
    parts = [next_phase.capitalize()]
    if pending_gate:
        parts[0] += f" [gate: {pending_gate}]"
    unmet = _unmet_entry(task, task_dir, next_phase)
    if unmet:
        parts.append("entry not met: " + ", ".join(unmet))
    if collapsed:
        parts.append(f"{', '.join(collapsed)} collapsed in this approach")
    if review_note:
        parts.append(review_note)
    # The issues this one waits for (ADR-062). Faults in `depends_on` are not
    # named here: the line stays one line, and `compass issue lint` names them.
    blocked = _dependency_block(task, task_dir, next_phase)
    if blocked:
        parts.append("blocked: " + blocked)

    # A decision an agent took for the person: the issue waits at a checkpoint
    # for its confirmation, or lists the decisions and goes on (autonomous).
    from compass_pkg import decisions_taken
    wait, more = decisions_taken.next_lines(task, done)
    wait = wait or review_wait
    if wait and blocked:
        wait += " | blocked: " + blocked
    line = (wait if wait else " | ".join(parts)) + "\n"
    _emit(args, task, task_dir, line, next_phase, False, hint=not wait)
    for extra in more:
        print(extra)
    return 0
