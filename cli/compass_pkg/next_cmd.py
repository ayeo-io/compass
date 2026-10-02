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
from compass_pkg.core import artifact_path, load_yaml, manifest_path, normalize_spine, resolve_issue_dir

# --- command: next -----------------------------------------------------------
# `compass next` reads manifest.yml + delivery-approach.md and prints ONE
# line (at a terminal, framed by the rail; see `_emit`): the next stage, the next uncleared gate, and delivery-approach-aware
# collapsed-stage markers. It is strictly READ-ONLY over
# .compass/work/<task>/ - no file is written or created. It derives its
# answer from manifest.yml and delivery-approach.md, and checks evidence/
# and the .red marker for a red the manifest does not list.
#
# The plain line, which is all piped output and the model ever see:
#   "<NextPhase> [gate: <gate-id>][ | <phase> collapsed on this route]"
# When the issue has landed:
#   "all phases complete"
# When delivery-approach.md is missing:
#   exit non-zero with a message naming delivery-approach.md
# When manifest.yml is missing (assess has not run):
#   exit non-zero with a message naming assess
#
# The canonical stage order Compass follows:
# The current keys. `normalize_spine` maps a retired key forward on load, so a
# list written in the retired spelling would stop matching every manifest it
# reads, and `compass next` would report the wrong stage instead of failing.
_PHASE_ORDER = [
    "assess",
    "define",
    "refine",
    "plan",
    "breakdown",
    "implement",
    "verify",
    "ship",
]

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


def _first_pending_gate(gates: list) -> str | None:
    """Return the id of the first gate whose status is not 'pass'."""
    for g in (gates or []):
        if isinstance(g, dict) and g.get("status") != "pass":
            return g.get("id")
    return None


def _all_gates_pass(gates: list) -> bool:
    """True when every gate is marked pass."""
    if not gates:
        return False
    return all(
        isinstance(g, dict) and g.get("status") == "pass"
        for g in gates
    )


def _entries(task: dict, key: str) -> list:
    """The dict entries of a manifest list. A hand-edited manifest can hold
    anything, and `compass next` must still name a stage."""
    value = task.get(key)
    return [e for e in value if isinstance(e, dict)] if isinstance(value, list) else []


def _registered(task: dict, kind: str) -> bool:
    """True when the manifest registers the `kind` document: an entry with a
    path at any status but `superseded`, or one recorded as omitted. The
    stage commands register their documents as `draft`, and nothing marks
    them approved, so the status cannot be what counts."""
    for a in _entries(task, "artifacts"):
        if a.get("kind") != kind:
            continue
        if a.get("status") == "omitted" or (a.get("path") and a.get("status") != "superseded"):
            return True
    return False


def _testing_started(task: dict, task_dir: str | None) -> bool:
    """True once any test result is on record: a test-run in the manifest, or
    a red that `compass tdd-red` wrote, which the manifest does not list."""
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
    return any(n.startswith("red") and n.endswith(".json") for n in names)


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
    a builder starting without a design registered. `compass next` cannot
    run without the approach record, so assess is always done. Ship's
    record, `status: landed`, is handled by the callers before they ask for
    a stage.
    """
    own = {
        "assess": True,
        # A quick fix earns no criteria document; its scenarios are define's
        # record.
        "define": (_registered(task, "acceptance-criteria")
                   or bool(_entries(task, "scenarios"))),
        # Wherever refine runs, light included, it registers the review
        # (commands/refine.md). Where it is collapsed or skipped it is not
        # a current stage at all.
        "refine": _registered(task, "requirements-review"),
        "plan": _registered(task, "technical-design"),
        "breakdown": bool(_entries(task, "subtasks")) or _registered(task, "distribution-map"),
        "implement": _every_scenario_tested(task),
        "verify": _all_gates_pass(task.get("gates") or []),
        "ship": False,
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


def _emit(args, task, task_dir, line, current_phase, finished):
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
        if not finished and current_phase in _PHASE_ORDER:
            quick = approach in ("quick-fix", "express")
            out += wrap("Next: /compass:" + ("quick-fix" if quick else display_stage(current_phase)))
        text = "\n".join(out) + "\n"
        # Checked before writing, so a terminal that cannot show the glyphs
        # gets today's line rather than half a rail and a traceback.
        text.encode(sys.stdout.encoding or "utf-8")
    except Exception:  # noqa: BLE001 - the rail is decoration; the line must still print
        text = line
    sys.stdout.write(text)


def cmd_next(args):
    """compass next - what comes next on this issue's delivery approach?

    Reads manifest.yml + delivery-approach.md and prints ONE line, framed
    by the rail when a person reads it at a terminal.
    Strictly read-only.
    """
    task_dir = resolve_issue_dir(getattr(args, "task", None))

    # --- manifest.yml: must exist (assess check) ---
    task_path = manifest_path(task_dir)
    if not os.path.isfile(task_path):
        sys.stdout.write(
            "Assess has not run for this issue - manifest.yml is missing.\n"
            f"  Run /compass:assess to start the issue at: {task_dir}\n"
        )
        return 2

    task = normalize_spine(load_yaml(task_path))

    # --- delivery-approach.md: must exist ---
    route_md_path = artifact_path(task_dir, "delivery-approach.md")
    if not os.path.isfile(route_md_path):
        sys.stdout.write(
            f"delivery-approach.md is missing from {task_dir}\n"
            "  Run /compass:assess to produce delivery-approach.md before using compass next.\n"
        )
        return 2

    # --- completed issue ---
    # Passed gates alone do not finish it: ship still runs, and a landed
    # status is ship's record.
    status = task.get("status", "")
    gates = task.get("gates") or []
    if status == "landed":
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

    # Find the first pending gate for the "next gate" display
    pending_gate = _first_pending_gate(gates)

    # Collapsed stages on this delivery approach
    collapsed = _detect_collapsed_phases(phases)

    # --- compose the one-line output ---
    parts = [next_phase.capitalize()]
    if pending_gate:
        parts[0] += f" [gate: {pending_gate}]"
    if collapsed:
        parts.append(f"{', '.join(collapsed)} collapsed on this route")

    _emit(args, task, task_dir, " | ".join(parts) + "\n", next_phase, False)
    return 0
