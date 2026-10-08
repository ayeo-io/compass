#!/usr/bin/env python3
# =============================================================================
# compass_pkg.analyze - `compass analyze` and `compass ci`
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
from compass_pkg.check_cmd import cmd_check
from compass_pkg.stable_ids import (
    GATE_VERIFY_ANALYZE, STAGE_ASSESS, STAGE_BREAKDOWN, STAGE_DEFINE, STAGE_IDS, STAGE_IMPLEMENT, STAGE_PLAN,
    STAGE_REFINE, STAGE_SHIP, STAGE_VERIFY)
from compass_pkg.core import COMPASS_SCHEMA_VERSION, COMPASS_VERSION, CompassError, artifact_path, exit_for_mode, find_compass_dir, load_mode, load_yaml, manifest_path, mode_banner, normalize_spine, now_iso, resolve_issue_dir, save_manifest
from compass_pkg.governance import cmd_policy_lint
from compass_pkg.policy import cmd_task_lint



# --- command: analyze -------------------------------------------------------
# `compass analyze` - cross-artifact consistency check
#
# Reads an issue's artifacts (intent.md, acceptance-criteria.md,
# delivery-approach.md, manifest.yml, positioning.md if present) and emits a
# structured consistency report.
#
# Finding types (the taxonomy is fixed in code, not read from signals.yml):
#   orphaned-intent  - a scenario in acceptance-criteria.md/manifest.yml links
#                      to an intent id that does not appear in intent.md
#   route-disagreement - delivery-approach.md and manifest.yml describe
#                        different stage weights for the same stage
#   orphan-claim     - positioning.md lists a claim id that no scenario links to
#   missing-artifact - an artifact needed by the delivery approach's
#                      non-collapsed stage is absent (delivery-approach-aware:
#                      legitimately omitted artifacts on collapsed/skipped
#                      stages are not flagged)
#
# Mode selection (ADR-007):
#   Gate-clearing mode  - verify.analyze is in manifest.yml.gates:
#       exits non-zero on any finding; evidence type `consistency-check`;
#       id prefix `EV-ANALYZE-<task>-<ts>`
#   Advisory mode - verify.analyze NOT in gates:
#       exits 0 even on findings; evidence type `command-output`;
#       id prefix `EV-ANALYZE-ADVISORY-<task>-<ts>`
#
# Invariants honoured (defined in architecture/ownership.md):
#   read-only over the manifest, never writing to its `assessment` or
#   `gates` (`Inv-1`, `Inv-4`)
#   the finding taxonomy is structural, not read from signals.yml (`Inv-7`)
#   no intent.md / acceptance-criteria.md exits 0, "no artifacts" (`Inv-8`)
#   never asserts whether gate evidence exists or passes; that is
#   `compass check`'s job


# Check for intent.md only when define runs at full weight. Do not default
# to "full": a defaulted lookup turns a key rename into a false finding
# instead of an error.
_SPECIFY_FULL_WEIGHTS = {"full"}

# The stages this checks for approach-disagreement. Current keys:
# `normalize_spine` maps a retired key forward on load, so a set written in the
# retired spelling matches nothing and every check below falls to its default.
_KNOWN_PHASES = set(STAGE_IDS)

# Stage name → manifest.yml key (lowercase map)
# The names a human writes in delivery-approach.md, and the manifest key each one
# means. Both the retired and the current spelling map to the current key,
# because a prose record written months ago still says the retired word while
# the manifest it describes has been normalised forward.
_PHASE_NAME_MAP = {
    STAGE_ASSESS: STAGE_ASSESS, "triage": STAGE_ASSESS, "frame": STAGE_ASSESS,
    STAGE_DEFINE: STAGE_DEFINE, "specify": STAGE_DEFINE,
    STAGE_REFINE: STAGE_REFINE, "clarify": STAGE_REFINE,
    STAGE_PLAN: STAGE_PLAN, "design": STAGE_PLAN,
    STAGE_BREAKDOWN: STAGE_BREAKDOWN, "distribute": STAGE_BREAKDOWN,
    STAGE_IMPLEMENT: STAGE_IMPLEMENT, "build": STAGE_IMPLEMENT,
    STAGE_VERIFY: STAGE_VERIFY,
    STAGE_SHIP: STAGE_SHIP, "land": STAGE_SHIP,
    # The prose names, which are what the shipped template actually writes in
    # its stage table and therefore what every real record on disk says.
    # Without the prose names, five of the eight rows in a template-shaped
    # record match nothing, and the check compares three stages while
    # reporting on all eight.
    "define acceptance criteria": STAGE_DEFINE,
    "acceptance criteria": STAGE_DEFINE,
    "requirements review": STAGE_REFINE,
    "technical design": STAGE_PLAN,
    "break down the work": STAGE_BREAKDOWN,
    "test & review": STAGE_VERIFY,
    "test and review": STAGE_VERIFY,
}


def _parse_intent_ids_from_brief(brief_path: str) -> set:
    """Extract intent ids from intent.md.

    Scans for lines matching:
      <!-- intent: INT-xxx --> (explicit traceability comment)
      - INT-xxx: ...            (bullet-list intent declaration)
    Returns a set of intent id strings.
    """
    intent_ids = set()
    if not os.path.isfile(brief_path):
        return intent_ids
    with open(brief_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            # comment form: <!-- intent: INT-xxx -->
            m = _re.match(r'<!--\s*intent:\s*(\S+)\s*-->', line)
            if m:
                intent_ids.add(m.group(1))
                continue
            # bullet form: - INT-xxx: ...  or  * INT-xxx: ...
            m = _re.match(r'^[-*]\s+(INT-\S+?):\s+', line)
            if m:
                intent_ids.add(m.group(1))
    return intent_ids


def _parse_scenario_intents_from_spec(spec_path: str) -> dict:
    """Extract {scenario_id: intent_id} from acceptance-criteria.md traceability comments.

    Looks for lines like:
      <!-- traceability id: TRC-A1 · serves: INT-1 -->
    """
    scenario_intents = {}
    if not os.path.isfile(spec_path):
        return scenario_intents
    with open(spec_path, "r", encoding="utf-8") as fh:
        for line in fh:
            m = _re.search(
                r'<!--\s*traceability\s+id:\s*(\S+).*?serves:\s*(\S+)',
                line
            )
            if m:
                scn_id = m.group(1).rstrip(" ·,")
                intent_id = m.group(2).rstrip(" ·,*/-->")
                scenario_intents[scn_id] = intent_id
    return scenario_intents


def _parse_claim_ids_from_positioning(positioning_path: str) -> set:
    """Extract claim ids from positioning.md.

    Scans for:
      <!-- claim: CLM-1 -->
      - CLM-1: ...
    """
    claim_ids = set()
    if not os.path.isfile(positioning_path):
        return claim_ids
    with open(positioning_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            m = _re.match(r'<!--\s*claim:\s*(\S+)\s*-->', line)
            if m:
                claim_ids.add(m.group(1))
                continue
            m = _re.match(r'^[-*]\s+(CLM-\S+?):\s+', line)
            if m:
                claim_ids.add(m.group(1))
    return claim_ids


def _parse_claimed_scenario_ids_from_spec(spec_path: str) -> set:
    """Return every scenario id in the acceptance criteria. It does not read
    claim links.
    """
    return set(_parse_scenario_intents_from_spec(spec_path).keys())


def _parse_phase_weights_from_route_md(route_md_path: str) -> dict:
    """Extract {phase_name_lower: weight} from a delivery-approach.md file.

    Looks for a Markdown table with a Stage (or Phase) column and a Weight
    column.
    """
    weights = {}
    if not os.path.isfile(route_md_path):
        return weights
    with open(route_md_path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    in_phase_table = False
    for line in lines:
        stripped = line.strip()
        # Match both header words: the template writes `| Stage | Weight |
        # Notes |` and older records write `Phase`. An empty weight map
        # would read downstream as "nothing disagreed" instead of "nothing
        # was read".
        if _re.match(r'\|\s*(?:Phase|Stage)\s*\|\s*Weight', stripped,
                     _re.IGNORECASE):
            in_phase_table = True
            continue
        if in_phase_table:
            # separator row
            if _re.match(r'\|[-| ]+\|', stripped):
                continue
            # Data row: `| Requirements review | collapsed | ... |`. The name
            # cell takes anything but a pipe, because the real names are
            # phrases and one of them ("Test & review") carries an ampersand.
            # The weight cell is read whole and then cut at the first comma or
            # space, because records write "full, streams unbounded by policy"
            # vocabulary-scan: allow - quotes what archived records say
            # and the weight is the first word of it.
            m = _re.match(r'\|\s*([A-Za-z][^|]*?)\s*\|\s*([^|]+?)\s*\|',
                          stripped)
            if m:
                phase = m.group(1).strip().lower()
                weight = _re.split(r'[,\s]', m.group(2).strip().lower(), 1)[0]
                # Through the name map, so a prose record written months ago
                # meets the manifest it describes. Without this the parser returns
                # `distribute` while the normalised manifest holds `breakdown`,
                # the comparison finds no key in common, and every
                # disagreement is silently skipped - the check reports clean
                # because the two sides use different keys.
                weights[_PHASE_NAME_MAP.get(phase, phase)] = weight
            elif stripped.startswith("#") or not stripped.startswith("|"):
                in_phase_table = False
    return weights


def _parse_route_from_route_md(route_md_path: str) -> str | None:
    """Extract the reference route name from delivery-approach.md.

    Looks for: **Reference route:** Express  (or similar)
    Returns the route string (lowercase) or None.
    """
    if not os.path.isfile(route_md_path):
        return None
    with open(route_md_path, "r", encoding="utf-8") as fh:
        for line in fh:
            m = _re.search(r'[Rr]eference\s+route[:\s]*[*]*\s*(\w+)', line)
            if m:
                return m.group(1).strip().lower()
    return None


def _analyze_task(task_dir: str, project_root: str | None = None) -> dict:
    """Analyse an issue's artifacts for consistency and return a report dict.

    The report dict has:
      findings: list of {type, subject, detail} dicts
      task_slug: str
      mode: 'gate' | 'advisory'
      has_verify_analyze_gate: bool

    Read-only over all issue artifacts (`Inv-1`, `Inv-4`). It never writes to
    manifest.yml or any other file; the caller (cmd_analyze) writes the
    evidence record.

    Finding types (the taxonomy is structural, not read from signals.yml -
    `Inv-7`):
      orphaned-intent    - scenario links to an intent not in intent.md
      route-disagreement - delivery-approach.md stage weight differs from manifest.yml stages
      orphan-claim       - positioning.md claim has no backing scenario
      missing-artifact   - a needed artifact is absent (delivery-approach-aware)
    """
    task_path = manifest_path(task_dir)
    if not os.path.isfile(task_path):
        raise CompassError(
            f"no manifest.yml in {task_dir} - has assess run? "
            f"compass analyze cannot run before it."
        )
    try:
        task = normalize_spine(load_yaml(task_path))
    except CompassError:
        raise  # re-raise: parse error propagates to cmd_analyze

    task_slug = task.get("task") or os.path.basename(task_dir)
    findings = []

    # Determine mode from gate set (ADR-007)
    gate_ids = [g.get("id") for g in (task.get("gates") or []) if isinstance(g, dict)]
    has_analyze_gate = GATE_VERIFY_ANALYZE in gate_ids

    # --- No artifacts to analyse: exits 0, "no artifacts" (`Inv-8`) --------
    brief_path = artifact_path(task_dir, "intent.md")
    spec_path = artifact_path(task_dir, "acceptance-criteria.md")
    route_md_path = artifact_path(task_dir, "delivery-approach.md")
    positioning_path = artifact_path(task_dir, "positioning.md")

    has_brief = os.path.isfile(brief_path)
    has_spec = os.path.isfile(spec_path)
    has_positioning = os.path.isfile(positioning_path)

    if not has_brief and not has_spec:
        # Bare-repo path: no artifacts to analyse
        return {
            "findings": [],
            "task_slug": task_slug,
            "mode": "gate" if has_analyze_gate else "advisory",
            "has_verify_analyze_gate": has_analyze_gate,
            "no_artifacts": True,
        }

    # --- 1. Delivery-approach-aware missing-artifact check -------------------
    # Check for intent.md only when define runs at full weight.
    phases = task.get("stages") or {}
    # Do not default to "full": a defaulted lookup turns a key rename into a
    # false finding instead of an error.
    specify_weight = str(phases.get(STAGE_DEFINE, phases.get("specify", ""))).lower()
    if specify_weight in _SPECIFY_FULL_WEIGHTS and not has_brief:
        findings.append({
            "type": "missing-artifact",
            "subject": "intent.md",
            "detail": (
                f"intent.md is absent but the define stage is '{specify_weight}' - "
                f"a full-weight define stage requires a brief."
            ),
        })

    # --- 2. Orphaned-intent check -------------------------------------------
    # Scenarios in manifest.yml with an intent that is not in intent.md.
    # Only when intent.md exists (no intent.md means no intents to check
    # against, but missing-artifact above may already have flagged that).
    if has_brief:
        declared_intents = _parse_intent_ids_from_brief(brief_path)
        task_scenarios = [
            s for s in (task.get("scenarios") or []) if isinstance(s, dict)
        ]
        for scn in task_scenarios:
            scn_id = scn.get("id", "?")
            intent_id = scn.get("intent")
            if intent_id and declared_intents and intent_id not in declared_intents:
                findings.append({
                    "type": "orphaned-intent",
                    "subject": scn_id,
                    "detail": (
                        f"scenario '{scn_id}' links to intent '{intent_id}' which "
                        f"does not appear in intent.md (declared intents: "
                        f"{sorted(declared_intents)})"
                    ),
                })
        # Also check acceptance-criteria.md's scenario-intent links
        if has_spec:
            spec_scenario_intents = _parse_scenario_intents_from_spec(spec_path)
            for scn_id, intent_id in spec_scenario_intents.items():
                if intent_id and declared_intents and intent_id not in declared_intents:
                    # Deduplicate: only report if not already caught from manifest.yml
                    already = any(
                        f["type"] == "orphaned-intent" and f["subject"] == scn_id
                        for f in findings
                    )
                    if not already:
                        findings.append({
                            "type": "orphaned-intent",
                            "subject": scn_id,
                            "detail": (
                                f"acceptance-criteria.md: scenario '{scn_id}' links to "
                                f"intent '{intent_id}' which does not appear in "
                                f"intent.md (declared intents: {sorted(declared_intents)})"
                            ),
                        })

    # --- 3. Route-disagreement check ----------------------------------------
    # Compare delivery-approach.md stage weights against the manifest's stages.
    if os.path.isfile(route_md_path):
        route_md_phases = _parse_phase_weights_from_route_md(route_md_path)
        task_phases = {k.lower(): str(v).lower() for k, v in phases.items()}
        for phase in _KNOWN_PHASES:
            md_weight = route_md_phases.get(phase)
            task_weight = task_phases.get(phase)
            if md_weight is not None and task_weight is not None:
                if md_weight != task_weight:
                    findings.append({
                        "type": "route-disagreement",
                        "subject": phase.title(),
                        "detail": (
                            f"delivery-approach.md says '{phase}' is '{md_weight}' but "
                            f"manifest.yml says '{task_weight}'"
                        ),
                    })

    # --- 4. Orphan-claim check -----------------------------------------------
    # Claims in positioning.md that have no scenario backing them.
    # Checks whether a claim names a scenario id, not whether the scenario
    # passes - that is compass check / verify.claims's job.
    if has_positioning:
        claim_ids = _parse_claim_ids_from_positioning(positioning_path)
        # Collect all scenario ids from manifest.yml and spec
        task_scn_ids = {
            s.get("id") for s in (task.get("scenarios") or [])
            if isinstance(s, dict) and s.get("id")
        }
        spec_scn_ids = set()
        if has_spec:
            spec_scn_ids = set(_parse_scenario_intents_from_spec(spec_path).keys())
        all_scn_ids = task_scn_ids | spec_scn_ids

        # Check manifest.yml claims as well
        task_claims = {
            c.get("id"): c.get("scenario")
            for c in (task.get("claims") or [])
            if isinstance(c, dict) and c.get("id")
        }

        for claim_id in claim_ids:
            # An orphan claim is one with no backing scenario id
            if claim_id in task_claims:
                # claim is in manifest.yml - check it has a scenario
                backing = task_claims[claim_id]
                if not backing:
                    findings.append({
                        "type": "orphan-claim",
                        "subject": claim_id,
                        "detail": (
                            f"claim '{claim_id}' is in manifest.yml claims but has "
                            f"no backing scenario"
                        ),
                    })
            else:
                # Claim is only in positioning.md - it must name a scenario
                # We can't check the link without manifest.yml.claims, so flag it
                findings.append({
                    "type": "orphan-claim",
                    "subject": claim_id,
                    "detail": (
                        f"claim '{claim_id}' in positioning.md has no backing "
                        f"scenario in manifest.yml claims"
                    ),
                })

    return {
        "findings": findings,
        "task_slug": task_slug,
        "mode": "gate" if has_analyze_gate else "advisory",
        "has_verify_analyze_gate": has_analyze_gate,
        "no_artifacts": False,
    }


def _write_analyze_evidence(task_dir: str, task_slug: str, report: dict,
                             is_gate_mode: bool) -> str:
    """Write the analyse evidence file and return the file path (relative to task_dir).

    Gate-clearing: type=consistency-check, prefix EV-ANALYZE-<task>-<ts>
    Advisory:      type=command-output,  prefix EV-ANALYZE-ADVISORY-<task>-<ts>

    The file is JSON; the manifest.yml evidence registry is NOT written here -
    analyse is read-only over the manifest (`Inv-1`, `Inv-4`).
    cmd_analyze calls this and then upserts into the registry separately only
    in gate-clearing mode (to let compass check clear verify.analyze).
    """
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if is_gate_mode:
        ev_id = f"EV-ANALYZE-{task_slug}-{ts}"
        ev_type = "consistency-check"
    else:
        ev_id = f"EV-ANALYZE-ADVISORY-{task_slug}-{ts}"
        ev_type = "command-output"

    payload = {
        "id": ev_id,
        "type": ev_type,
        "task": task_slug,
        "timestamp": now_iso(),
        "mode": "gate" if is_gate_mode else "advisory",
        "finding_count": len(report.get("findings", [])),
        "findings": report.get("findings", []),
    }

    ev_dir = os.path.join(task_dir, "evidence")
    os.makedirs(ev_dir, exist_ok=True)
    filename = f"{ev_id}.json"
    full_path = os.path.join(ev_dir, filename)
    with open(full_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    return f"evidence/{filename}", ev_id, ev_type


def _upsert_analyze_evidence_registry(task_dir: str, ev_id: str,
                                       ev_type: str, rel_path: str) -> None:
    """Upsert the analyse evidence entry into manifest.yml's evidence registry.

    Only called in gate-clearing mode so compass check can locate the
    consistency-check evidence when clearing verify.analyze.

    This is the ONE write to manifest.yml that analyse is permitted: adding an
    entry to the top-level `evidence:` list. It does not write to the
    manifest's `assessment` or `gates` (`Inv-1`, `Inv-4`).
    """
    task_path = manifest_path(task_dir)
    if not os.path.isfile(task_path):
        return
    try:
        task = normalize_spine(load_yaml(task_path))
    except CompassError:
        return
    if not isinstance(task, dict):
        return
    reg = task.get("evidence") or []
    if not isinstance(reg, list):
        return
    # Remove any previous consistency-check entry (replace with fresh run)
    reg = [e for e in reg if not (isinstance(e, dict) and
                                   e.get("type") == "consistency-check")]
    reg.append({"id": ev_id, "type": ev_type, "path": rel_path})
    task["evidence"] = reg
    save_manifest(task, task_path)


def cmd_analyze(args):
    """compass analyze - cross-artifact consistency check.

    Read-only over the manifest (`Inv-1`, `Inv-4`). Writes one evidence file
    (consistency-check or command-output type) to evidence/.

    Exit codes:
      0 - zero consistency findings (or advisory mode regardless of findings,
          or the no-artifacts path - `Inv-8`)
      1 - one or more consistency findings AND verify.analyze gate is present
      2 - input error (malformed manifest.yml, issue not assessed, etc.)
    """
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    project_root = os.path.dirname(os.path.dirname(task_dir))  # .compass/work/<slug>/../../

    # A malformed manifest.yml exits non-zero, stderr naming the file and error.
    try:
        report = _analyze_task(task_dir, project_root)
    except CompassError as exc:
        # Re-raise so main() prints it to stderr with exit 2
        raise

    task_slug = report["task_slug"]
    is_gate_mode = report["has_verify_analyze_gate"]
    findings = report.get("findings", [])
    no_artifacts = report.get("no_artifacts", False)

    # No artifacts (`Inv-8`): exit 0 with an informational message.
    if no_artifacts:
        print(f"compass analyze: no artifacts to analyze for issue '{task_slug}'.")
        print("  (no intent.md and no acceptance-criteria.md found - bare-repo path)")
        return 0

    # A REPORT: every finding is listed, and the summary says how many there
    # are and whether they block, which is what a reader is here to learn.
    from compass_pkg.terminal import Report

    mode_str = "gate-clearing" if is_gate_mode else "advisory"
    rel_path, ev_id, ev_type = _write_analyze_evidence(
        task_dir, task_slug, report, is_gate_mode
    )
    if is_gate_mode:
        _upsert_analyze_evidence_registry(task_dir, ev_id, ev_type, rel_path)

    blocks = bool(findings) and is_gate_mode
    # Not "PASS - 1 finding(s)". The verdict word is the one that gets read,
    # and "PASS" with a count after it reads as a clean result. A run that
    # found something says so; only a run that found nothing says PASS.
    if blocks:
        verdict = "FAIL - %d coherence finding(s), and they block shipping" % len(findings)
    elif findings:
        verdict = ("%d coherence finding(s) - advisory on this approach, so "
                   "they do not block shipping" % len(findings))
    else:
        verdict = "PASS - no coherence findings"
    rep = Report(args, title="compass analyze")
    rep.summary(
        "compass analyze - issue '%s' (%s): %s." % (task_slug, mode_str, verdict),
        ("The verify.analyze gate is in this approach's gate set."
         if is_gate_mode else
         "The verify.analyze gate is NOT in this approach's gate set, so these "
         "findings do not block shipping."),
        # Path only. The type and the id are in --json; what a reader needs
        # from a summary line is the file they can open.
        "Evidence: %s" % rel_path)
    rep.section("findings", list(findings),
                lambda f: "%-20s %-28s %s" % (f["type"], f["subject"],
                                              f["detail"]))
    rep.data(issue=task_slug, gate_mode=is_gate_mode, blocks=blocks,
             finding_count=len(findings), evidence={"path": rel_path,
                                                    "id": ev_id, "type": ev_type},
             registry_updated=bool(is_gate_mode))
    rep.emit()
    return 1 if blocks else 0


# --- command: ci ------------------------------------------------------------
# The full mechanical gate suite, for CI / pre-merge. It is a convenience: it
# just runs the checks that already exist - `policy lint`, then `issue lint`
# and `check` for every issue under .compass/work/ - and aggregates the exit
# codes. CI integration is genuinely this small: run `compass ci`, honour the
# exit code. See ci/README.md.

# Lifecycle states meaning "not active". An issue in one of these has no
# acceptance criteria yet, by design, so the gate checks have nothing to read.
_NOT_IN_FLIGHT = ("queued", "parked", "abandoned")


def _issue_status(slug):
    """The issue's lifecycle status, or '' if it cannot be read.

    An unreadable manifest is not treated as not active: it falls through to
    the checks, which report the problem properly rather than skipping it.
    """
    try:
        manifest = load_yaml(os.path.join(resolve_issue_dir(slug), "manifest.yml"))
    except Exception:
        return ""
    if not isinstance(manifest, dict):
        return ""
    return (manifest.get("status") or "").strip()


def _git_out(cwd, *args):
    """The output of a git command, or None when it fails."""
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    except OSError:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _landed_before(slug, cwd, ref, ref_time):
    """True only when the issue's landing is known to be before `ref`.

    `land_commit` is placed by git ancestry. An issue without it, such as
    one landed before `ship-commit` wrote the field, is placed by
    `land_timestamp` against the ref's commit time. Anything that cannot be
    placed counts as after, so it is checked:
    checking too much costs time, and checking too little hides a failure.
    """
    try:
        manifest = load_yaml(os.path.join(resolve_issue_dir(slug), "manifest.yml"))
    except Exception:
        return False
    if not isinstance(manifest, dict):
        return False
    commit = manifest.get("land_commit")
    if isinstance(commit, str) and commit:
        r = subprocess.run(["git", "merge-base", "--is-ancestor", commit, ref],
                           cwd=cwd, capture_output=True, text=True)
        return r.returncode == 0
    stamp = manifest.get("land_timestamp")
    try:
        landed = datetime.datetime.fromisoformat(str(stamp))
        return landed < ref_time
    except (TypeError, ValueError):
        return False


def cmd_ci(args):
    import types
    mode = load_mode()
    print(f"compass ci - the full mechanical gate suite "
          f"(compass {COMPASS_VERSION}, schema {COMPASS_SCHEMA_VERSION})")
    print(f"{mode_banner(mode)}\n")
    failures = 0
    checked = 0
    skipped = 0

    since = getattr(args, "since", None)
    project = os.getcwd()
    ref_time = None
    if since:
        # A ref git cannot resolve must stop the run: carrying on would
        # check less than the caller asked for and still report a pass.
        try:
            project = os.path.dirname(find_compass_dir())
        except CompassError:
            pass
        commit = _git_out(project, "rev-parse", "--verify", "--quiet", f"{since}^{{commit}}")
        stamp = commit and _git_out(project, "log", "-1", "--format=%cI", commit)
        if not stamp:
            print(f"compass ci: --since {since} does not name a commit in this "
                  f"repository, so nothing was checked.")
            return 2
        ref_time = datetime.datetime.fromisoformat(stamp)
        print(f"Issues landed before {since} are linted only.\n")

    print("[1] governance policy")
    if cmd_policy_lint(types.SimpleNamespace()):
        failures += 1

    # The decisions ledger's history check needs a base ref to compare with
    # (ADR-027). Without --since it says so, rather than passing silently.
    from compass_pkg.decisions import LEDGER, history_problems
    ledger_root = project
    try:
        ledger_root = os.path.dirname(find_compass_dir())
    except CompassError:
        pass
    if os.path.isdir(os.path.join(ledger_root, LEDGER)):
        if since:
            problems = history_problems(ledger_root, commit)
            if problems:
                failures += 1
                print("\n[ledger] FAIL - an entry never changes:")
                for p in problems:
                    print(f"  {p}")
            else:
                print(f"\n[ledger] PASS - every entry at {since} is unchanged.")
        else:
            print("\n[ledger] history check skipped - pass --since <ref> to "
                  "compare governance/decisions/ with a base ref.")

    slugs = []
    try:
        work = os.path.join(find_compass_dir(), "work")
        if os.path.isdir(work):
            slugs = sorted(d for d in os.listdir(work)
                           if os.path.isfile(manifest_path(os.path.join(work, d))))
    except CompassError:
        pass

    if not slugs:
        print("\n  no issues under .compass/work/ - governance policy only.")
    for slug in slugs:
        print(f"\n[issue] {slug}")
        # The lint runs for every issue, whatever its stage. It checks the
        # manifest's own structure - schema version, required keys, vocabulary -
        # and a malformed manifest is malformed whether or not the work has
        # started. Skipping it would let a manifest the linter rejects pass
        # while the sweep reports clean.
        if cmd_task_lint(types.SimpleNamespace(task=slug, file=None)):
            failures += 1

        # The generation the manifest names is the issue's configuration. A
        # broken one fails the sweep and its gate checks are not run, because
        # `compass check` refuses it; a leftover folder is only reported.
        from compass_pkg import effective
        gen_lines, gen_broken = effective.generation_report(resolve_issue_dir(slug))
        for gen_line in gen_lines:
            print(gen_line)
        if gen_broken:
            print("  gate checks skipped - the stored configuration is broken. "
                  "The manifest itself was still linted.")
            failures += 1
            skipped += 1
            continue

        # The gate checks are different. An issue that has not started has no
        # acceptance criteria and no evidence, correctly so - the framework
        # asks for work to be assessed early, and failing the sweep for
        # complying teaches people to stop. Skip those, name the issue, and
        # say why: an issue that vanished from the output would be worse than
        # one that failed, because nobody would know it was there.
        status = _issue_status(slug)
        if status in _NOT_IN_FLIGHT:
            print(f"  gate checks skipped - status is '{status}', so the "
                  f"acceptance criteria and evidence a check looks for do "
                  f"not exist yet. The manifest itself was still linted.")
            skipped += 1
            continue
        # The resolved commit id, not the caller's string, reaches git.
        if since and status == "landed" and _landed_before(slug, project, commit, ref_time):
            print(f"  gate checks skipped - landed before {since}. Run "
                  f"compass ci without --since to check it. The manifest "
                  f"itself was still linted.")
            skipped += 1
            continue
        print()
        # cmd_check applies the output mode itself. Call it and keep its exit
        # code, so ci can report which groups failed.
        checked += 1
        # Forward the caller's output mode, so `compass ci --verbose` gives
        # verbose check output. A CI log is the one place a reader cannot
        # re-run a command.
        # An issue whose configuration cannot be read (generation 0, say) is a
        # failure of that issue, reported, and the sweep goes on to the next.
        try:
            check_failed = cmd_check(types.SimpleNamespace(
                task=slug, _mode=getattr(args, "_mode", None),
                evidence_out=getattr(args, "evidence_out", None),
                no_count=True))
        except CompassError as exc:
            print(f"  gate checks refused - {exc}")
            check_failed = 1
        if check_failed:
            failures += 1

    print("\n" + "=" * 60)
    if failures:
        print(f"compass ci: FAIL - {failures} check group(s) failed.")
    else:
        # The summary must say what ran and what was skipped: a CI reader
        # reads the summary line, not the skip lines above it.
        counted = f"{checked} issue(s) fully checked"
        if skipped:
            why = f"not in flight, or landed before {since}" if since else "not in flight"
            counted += f", {skipped} lint-only ({why})"
        print(f"compass ci: PASS - governance valid; every manifest lints clean; "
              f"{counted}.")
    return exit_for_mode(failures, mode)
