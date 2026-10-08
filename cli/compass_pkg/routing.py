#!/usr/bin/env python3
# =============================================================================
# compass_pkg.routing - the delivery-approach evaluator and
# `compass approach evaluate`
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
from compass_pkg.core import _stage_key_renames, ASSESSMENT_KEY_MAP, CompassError, canonical_shape, display_shape, display_stage, find_governance, load_manifest, load_yaml, reading_matches, resolve_issue_dir, shape_stages
from compass_pkg.governance import governance_drift
from compass_pkg.stable_ids import APPROACH_FULL, APPROACH_REGULAR, APPROACH_SPIKE
from compass_pkg.render import fired_rule_line
from compass_pkg.manifest import annotate_gate_accepts_text



# The policy states, as a number, how many parallel subtasks each shape
# permits, so a cap can be compared against it directly. A null ceiling
# means UNBOUNDED, not that the number is unknown.
# Nothing in routing-policy.yml or .compass/config.yml states a multiagent width -
# the only cap the policy carries is RP-CAP-001's max_worktrees: 1, and the
# config file says in as many words that the worktree cap is a routing
# concern it does not hold. A ceiling on multiagent work can only come from a
# cap, or from the distribution map at breakdown.
# Route shapes declare `subtask_ceiling` as a number since ADR-023; `core`
# keeps its own copy for reading archived manifests, which still carry the
# words.


# A `block_phase` value comes straight from routing-policy.yml, which still
# spells the ship stage `land` (RP-ROLE-001) - the policy file is not a
# manifest, so `normalize_spine` never touches it. Canonicalise it the same
# way a manifest's stage keys already are on load, then hand it to the
# display layer, so nothing prints the retired name.
def _display_blocked_phase(phase):
    return display_stage(_stage_key_renames().get(phase, phase))


def canonical_routes(policy):
    """`policy` with every route name in its current spelling, and the old
    names it held. A project's policy copied before the routes were renamed
    keys them `express`, `standard` and `expedition`, or names `feature`
    and `initiative`; it computes exactly as the renamed one does. The result
    shares nothing with `policy`, so a caller may change it."""
    import copy
    return canonical_view(copy.deepcopy(policy or {}))


def canonical_view(policy):
    """What `canonical_routes` returns, without copying the policy: the
    containers a rename changes are new, and everything else is the policy's
    own. The result is for reading. The evaluator reads a policy once for each
    assessment, and copying all of it each time was most of the cost of a
    classification (a profile of the classifier benchmark)."""
    out = dict(policy or {})
    old = set()

    def name(value):
        new = canonical_shape(value)
        if new != value:
            old.add(value)
        return new

    def keyed(mapping, where):
        # Two keys that name one route - `standard` beside `regular` - would
        # silently merge, and one of them would be lost; refuse instead.
        merged, seen = {}, {}
        for key, value in mapping.items():
            new = name(key)
            if new in merged:
                raise CompassError(
                    f"`{where}` names route '{new}' twice, as '{seen[new]}' "
                    f"and '{key}'. Keep one of them.")
            merged[new], seen[new] = value, key
        return merged

    out["route_shapes"] = keyed(out.get("route_shapes") or {}, "route_shapes")
    strategies = dict(out.get("routing_strategies") or {})
    if strategies:
        if "default_route" in strategies:
            strategies["default_route"] = name(strategies["default_route"])
        shapes = strategies.get("default_shapes")
        if isinstance(shapes, list):
            strategies["default_shapes"] = [
                dict(shape, lean_toward=name(shape["lean_toward"]))
                if isinstance(shape, dict) and "lean_toward" in shape else shape
                for shape in shapes]
        out["routing_strategies"] = strategies
    guardrails = out.get("routing_guardrails")
    if isinstance(guardrails, dict) and guardrails:
        def renamed(rule):
            if not isinstance(rule, dict):
                return rule
            return dict(rule, **{key: name(rule[key])
                                 for key in ("force_minimum_route", "forbid_route")
                                 if key in rule})
        out["routing_guardrails"] = {
            key: ([renamed(rule) for rule in group] if isinstance(group, list)
                  else group)
            for key, group in guardrails.items()}
    table = out.get("autonomy_checkpoints")
    if isinstance(table, dict):
        out["autonomy_checkpoints"] = {
            level: (keyed(row, f"autonomy_checkpoints.{level}")
                    if isinstance(row, dict) else row)
            for level, row in table.items()}
    return out, sorted(old)


class PreparedPolicy:
    """A policy read once for many assessments: its route names in the current
    spelling, the old names it held, its vocabulary, and the problems of its
    checkpoint table. None of it depends on the assessment, so a caller that
    routes many assessments under one policy (the classifier) prepares it once
    and hands this to `evaluate_route` in place of the policy. The table's
    problems are kept, not raised, so `evaluate_route` raises them at the point
    it always has."""

    def __init__(self, view, renamed, vocab, table_errors):
        self.view = view
        self.renamed = renamed
        self.vocab = vocab
        self.table_errors = table_errors


_VOCABULARY_KEYS = {"blast_radius": "risk", "terrain": "familiarity",
                    "magnitude": "size", "intent": "goal",
                    "touches_common": "labels_common"}


def prepare_policy(policy):
    """The `PreparedPolicy` of `policy`. A policy that names one route twice
    raises here, as `evaluate_route` has always raised it first."""
    from compass_pkg.policy import checkpoint_table_errors
    view, renamed = canonical_view(policy)
    vocab = {_VOCABULARY_KEYS.get(k, k): v
             for k, v in (view.get("assessment_vocabulary")
                          or view.get("reading_vocabulary") or {}).items()}
    return PreparedPolicy(view, renamed, vocab, checkpoint_table_errors(view))


def route_checkpoints(prepared, stages, approach, autonomy):
    """The hand-offs that wait for a person under `autonomy`, for an approach
    whose stages are `stages`. Only this depends on the autonomy, so a caller
    that needs every autonomy value routes once and asks for the rest here."""
    from compass_pkg.policy import CHECKPOINT_STAGES
    runs = [s for s in CHECKPOINT_STAGES
            if stages.get(s) not in (None, "collapsed", "skipped")]
    table = prepared.view.get("autonomy_checkpoints")
    row = {canonical_shape(k): v
           for k, v in ((table or {}).get(autonomy) or {}).items()}
    listed = row.get(canonical_shape(approach))
    # A missing table, value or route waits at every hand-off the route
    # runs: a gap must not read as "never wait".
    return runs if listed is None else [s for s in runs if s in listed]


class RoutingConflict(CompassError):
    """The assessment and the policy disagree: exploration that a floor would
    turn into delivery, or an approach a cap forbids. These are outcomes of
    an assessment, and the one kind of error a caller that compares policies
    can treat as a result. Every other error is a fault in an input."""


def _below_full(stage, mode, ranks):
    """Does a floor's lift raise this stage's mode to `full`? With ranks
    (the catalogue form's `stages.<id>.modes.<mode>.rank`, handed over as
    `stage_mode_ranks`) it lifts a mode ranked below `full`, and leaves a
    mode with no rank alone. Without them it lifts the three modes that sit
    below `full` on the depth ladder, which is what the ranks reproduce for
    the shipped policy."""
    if ranks is None:
        return mode in ("collapsed", "skipped", "light")
    stage_ranks = ranks.get(stage) or {}
    mode_rank, full_rank = stage_ranks.get(mode), stage_ranks.get("full")
    return mode_rank is not None and full_rank is not None and mode_rank < full_rank


def evaluate_route(readings, policy, autonomy="balanced", issue=None):
    """Pure function: assessment + policy -> the delivery approach and
    everything that shaped it. This is the deterministic core of Compass.
    `autonomy` changes only `checkpoints` in the result. Old route names in
    the policy are read as the current ones (`canonical_routes`).

    `issue` is an issue's own layer, applied in the order
    `governance/decisions/2026-10-05-floors-win-over-the-issue-layer.md`
    fixes: it names the candidate (`approach`), replaces the candidate's
    base stage modes (`stage_modes`) and can lower the approach's subtask
    ceiling (`subtask_ceiling`), and then the floors, caps and role rules
    apply, so they win over it. A floor that replaces the candidate brings
    the new approach's own modes, so the issue's modes are reported as
    ignored. With no `issue` the result is what it was before the argument
    existed."""
    prepared = (policy if isinstance(policy, PreparedPolicy)
                else prepare_policy(policy))
    policy, renamed, vocab = prepared.view, prepared.renamed, prepared.vocab
    # The dimension orders a `when:` clause reads `at_least` against. Absent,
    # the shipped orders of risk and size apply, as before.
    orders = policy.get("dimension_orders")

    def matches(when):
        return reading_matches(when, readings, orders)

    shapes = policy.get("route_shapes", {})
    strategies = policy.get("routing_strategies", {})
    guardrails = policy.get("routing_guardrails", {})

    # --- check the assessment: a misclassification fails loudly -------------
    errors = []
    for dim in ("risk", "familiarity", "size"):
        if dim not in readings:
            errors.append(f"missing required reading: {dim}")
        elif dim in vocab and readings[dim] not in vocab[dim]:
            errors.append(
                f"reading {dim}={readings[dim]!r} is not in the vocabulary "
                f"{vocab[dim]}"
            )
    for dim in ("goal", "urgency", "role"):
        if dim in readings and dim in vocab and readings[dim] not in vocab[dim]:
            errors.append(
                f"reading {dim}={readings[dim]!r} is not in the vocabulary "
                f"{vocab[dim]}"
            )
    if errors:
        raise CompassError("invalid assessment:\n  - " + "\n  - ".join(errors))

    # --- 1. compose the candidate (routing strategies bias this) -------------
    candidate = strategies.get("default_route", APPROACH_REGULAR)
    candidate_via = "the policy default (no shape matched)"
    for shape in strategies.get("default_shapes", []):
        if matches(shape.get("when")):
            candidate = shape["lean_toward"]
            candidate_via = f"{shape.get('id', '?')} ({shape.get('rationale', '')})"
            break
    issue = issue or {}
    if issue.get("approach"):
        candidate = canonical_shape(issue["approach"])
        candidate_via = "the issue's own choice"

    final = candidate
    fired = []
    never_skip, required_phases, required_skills = set(), set(), set()
    required_artifacts, blocked_phases, role_gates = [], [], []
    max_worktrees, forbidden = None, set()

    def weight(route):
        return shapes.get(route, {}).get("weight", 0)

    # --- 2. floors raise the delivery approach / force stages (routing guardrails) -------
    floor_gates = []  # gates added by floors via add_gate (ADR-007)
    # Artifacts a rule earns, beside the gates a rule earns. What an issue
    # documents is a routed output like its stages and its gate set: judgement
    # produces the assessment, and the mechanism produces everything downstream.
    # A hand-assembled artifact list is a form, which is the thing this
    # framework exists to remove.
    rule_artifacts = []
    for fl in guardrails.get("floors", []):
        if not matches(fl.get("when")):
            continue
        changed = []
        forced = fl.get("force_minimum_route")
        if forced and weight(forced) > weight(final):
            changed.append(f"approach raised {display_shape(final)} -> "
                           f"{display_shape(forced)}")
            final = forced
        if fl.get("require_phase"):
            # Canonicalise these names: they are looked up in a stage map
            # `shape_stages` has already canonicalised, so a retired key
            # would find nothing and raise nothing while the floor still
            # reports as fired.
            required = _stage_key_renames().get(fl["require_phase"],
                                                fl["require_phase"])
            required_phases.add(required)
            changed.append(f"stage '{display_stage(required)}' "
                           f"forced full-weight")
        if fl.get("require_skill"):
            required_skills.add(fl["require_skill"])
            changed.append(f"skill '{fl['require_skill']}' required")
        if fl.get("never_skip"):
            # Canonicalise the stage names a floor rule lists, the same way
            # `shape_stages` canonicalises the keys a shape declares. A policy
            # written before this rename says `clarify` here, and this list is
            # printed - so without it the evaluator names a retired stage in
            # the sentence explaining why a stage cannot be skipped.
            _renames = _stage_key_renames()
            fl = dict(fl, never_skip=[_renames.get(x, x) for x in fl["never_skip"]])
            never_skip.update(fl["never_skip"])
            changed.append("never-skip: " + ", ".join(
                display_stage(s) for s in fl["never_skip"]))
        if fl.get("add_gate"):
            floor_gates.append(fl["add_gate"])
            changed.append(f"gate '{fl['add_gate']}' added to the "
                           f"approach's gate set")
        if fl.get("add_artifact"):
            rule_artifacts.append((fl["add_artifact"], fl.get("rationale", "")))
            changed.append(f"artifact '{fl['add_artifact']}' added to the "
                           f"approach's artifact set")
        if changed:
            # The kind follows what the entry actually did, not which block it
            # sits in. An entry that only attaches a gate raises no minimum, so
            # calling it a floor is the same conflation the RP-REQUIRE ids were
            # introduced to end - and it would print "[RP-REQUIRE-003] floor:"
            # on screen, which reads as a contradiction.
            raises_minimum = any(
                k in fl for k in ("force_minimum_route", "require_phase",
                                  "require_skill", "never_skip"))
            fired.append({"id": fl.get("id", "?"),
                          "kind": "floor" if raises_minimum else "requirement",
                          "rationale": fl.get("rationale", ""), "changed": changed})

    # --- 2b. routing conflict: exploration must not silently become delivery -
    # If the candidate was a Spike and a routing floor would force it onto a
    # delivery approach, that is NOT "Spike raised to initiative" - it is
    # "this is not a Spike." A Spike ships nothing and must not touch
    # production-critical surface (approaches/spike.md). Auto-promoting it
    # would quietly change the *meaning* of the work from "explore" to
    # "deliver." The honest answer is a re-assessment, so the evaluator stops
    # and says so.
    if candidate == APPROACH_SPIKE and final != APPROACH_SPIKE:
        floor_ids = [f["id"] for f in fired if f["kind"] == "floor"]
        raise RoutingConflict(
            "routing conflict - exploration cannot silently become delivery.\n"
            f"  Intent is 'exploration' (a Spike candidate), but routing "
            f"guardrail(s) {floor_ids} would force at least '{final}'.\n"
            f"  A Spike ships nothing and must not touch production-critical "
            f"surface - that is its whole safety model (see the spike "
            f"reference doc).\n"
            f"  Re-assess: either scope a narrower discovery issue that does not "
            f"touch the risky surface, or set intent=delivery and accept the "
            f"'{final}' approach deliberately. The point is that this is a choice "
            f"a human makes, not one the router makes silently."
        )

    # --- 3. caps limit scale-up ---------------------------------------------
    for cap in guardrails.get("caps", []):
        if not matches(cap.get("when")):
            continue
        changed = []
        if "max_worktrees" in cap:
            max_worktrees = cap["max_worktrees"]
            changed.append(f"max_worktrees capped at {cap['max_worktrees']}")
        if cap.get("forbid_route"):
            forbidden.add(cap["forbid_route"])
            changed.append(
                f"approach '{display_shape(cap['forbid_route'])}' forbidden")
        if changed:
            fired.append({"id": cap.get("id", "?"), "kind": "cap",
                          "rationale": cap.get("rationale", ""), "changed": changed})

    # --- 4. role rules add enforced artifacts / blocks ----------------------
    for rr in guardrails.get("role_rules", []):
        if not matches(rr.get("when")):
            continue
        changed = []
        if rr.get("require_artifact"):
            required_artifacts.append(rr["require_artifact"])
            changed.append(f"artifact '{rr['require_artifact']}' required")
        if rr.get("block_phase"):
            blocked_phases.append({"phase": rr["block_phase"],
                                   "until": rr.get("until", "")})
            changed.append(f"stage '{_display_blocked_phase(rr['block_phase'])}' "
                           f"blocked until: {rr.get('until', '')}")
        if rr.get("gate"):
            role_gates.append(rr["gate"])
            changed.append(f"gate '{rr['gate']}' added to the "
                           f"approach's gate set")
        if changed:
            fired.append({"id": rr.get("id", "?"), "kind": "role_rule",
                          "rationale": rr.get("rationale", ""), "changed": changed})

    if final in forbidden:
        raise RoutingConflict(
            f"routing conflict: the composed approach '{final}' is forbidden by "
            f"a cap for this assessment. Re-assess - the assessment and the "
            f"policy disagree, and that needs a human."
        )

    # --- 5. assemble the final shape ----------------------------------------
    shape = shapes.get(final)
    if not shape:
        raise CompassError(f"delivery approach '{final}' has no entry in route_shapes")
    phases = shape_stages(shape)
    applied, ignored = {}, {}
    for stage, mode in (issue.get("stage_modes") or {}).items():
        stage = _stage_key_renames().get(stage, stage)
        # Only the candidate's own stages take an override: the approach a
        # floor chose instead has modes of its own.
        if final == candidate and stage in phases:
            phases[stage] = applied[stage] = mode
        else:
            ignored[stage] = mode
    for p in (never_skip | required_phases):
        if _below_full(p, phases.get(p), policy.get("stage_mode_ranks")):
            phases[p] = "full"
    gates = list(shape.get("gates", []))
    # Immovable gates and role-added gates apply to delivery approaches only. Spike
    # ships nothing - it carries only its own Conclude gate, by design. (A
    # spike that needs a delivery gate is not a spike; it graduates.)
    if final != APPROACH_SPIKE:
        for ig in guardrails.get("immovable_gates", []):
            if ig.get("gate") and ig["gate"] not in gates:
                gates.append(ig["gate"])
        for rg_gate in role_gates:  # gates added by a role rule (e.g. verify.claims)
            if rg_gate not in gates:
                gates.append(rg_gate)
        for fl_gate in floor_gates:  # gates added by a floor's add_gate (ADR-007)
            if fl_gate not in gates:
                gates.append(fl_gate)
    # A CEILING, not a decision. Assess cannot know the orchestration: the
    # evaluator has no concept of a work unit, `routing-policy.yml` says
    # nothing about independence or subtasks, and the distribution map that
    # decides parallelism is written at plan - three stages later. So the
    # evaluator reports how many parallel subtasks this approach PERMITS, and
    # breakdown sets the actual orchestration once the map exists.
    #
    # It stays a number so a cap can be compared against it.
    # --- the artifact set --------------------------------------------------
    # The shape says what this size and risk of work ordinarily documents; a
    # rule adds what a dimension the shape cannot see has earned. Nothing is
    # recorded as "omitted" here: a document the assessment never earned was
    # never a candidate, and writing a reason for it would be the bookkeeping
    # this is meant to remove. `omitted` is for a human deliberately dropping
    # something that WAS earned.
    artifacts = []
    for kind, depth in (shape.get("artifacts") or {}).items():
        artifacts.append({
            "id": "ART-" + str(kind).upper().replace("-", "_"),
            "kind": kind, "status": "draft", "depth": depth,
            # The reason names the rule that earned it, in the reader's words.
            # It deliberately does not repeat the kind - the row already says
            # which document this is.
            # "regular" and "full" are adjectives, so they take a noun.
            "reason": "every %s carries %s" % (
                display_shape(final) + (" approach" if final in (APPROACH_REGULAR, APPROACH_FULL) else ""),
                "one" if depth == "full" else "a light one"),
        })
    # A role rule already demands documents via `require_artifact` - a marketer
    # needs launch-readiness, a product owner an intent document. That is the same idea
    # from the role's side, so it joins the same set rather than living in a
    # second list nothing renders.
    for req in required_artifacts:
        kind = req[:-3] if str(req).endswith(".md") else str(req)
        rule_artifacts.append((kind, "a role in play requires it"))

    for kind, why in rule_artifacts:
        if any(a["kind"] == kind for a in artifacts):
            continue
        artifacts.append({
            "id": "ART-" + str(kind).upper().replace("-", "_"),
            "kind": kind, "status": "draft", "depth": "full",
            "reason": why or "added by a policy rule",
        })

    subtask_ceiling = shape.get("subtask_ceiling", 1)
    if "subtask_ceiling" in issue:
        # A minimum, as for a cap: the issue layer lowers a ceiling and never
        # raises it. An approach with no ceiling takes the issue's.
        asked = issue["subtask_ceiling"]
        subtask_ceiling = asked if subtask_ceiling is None else min(subtask_ceiling, asked)
    if max_worktrees is not None:
        subtask_ceiling = (max_worktrees if subtask_ceiling is None
                           else min(subtask_ceiling, max_worktrees))

    # --- soft advisory strategies --------------------------------------------
    # These BIAS/ASSESS only - they never change the delivery approach, gates,
    # weight, or subtask ceiling. Surfaced for the router and the reviewer
    # (e.g. regression-baseline on shared/critical surface). A strategy, not
    # a guardrail.
    applicable_strategies = []
    for adv in strategies.get("advisory_strategies", []):
        if matches(adv.get("when")):
            applicable_strategies.append({
                "id": adv.get("id", "?"),
                "strategy": adv.get("strategy", ""),
                "rationale": adv.get("rationale", ""),
            })

    # --- checkpoints: which hand-offs wait for a person ----------------------
    # Looked up after everything else, from the final route, so the setting
    # cannot change the route, the stages or the gates.
    if prepared.table_errors:
        raise CompassError("governance/routing-policy.yml: " + prepared.table_errors[0])
    checkpoints = route_checkpoints(prepared, phases, final, autonomy)

    result = {
        # Old route names the policy used, read as the current ones; the
        # caller warns about them.
        "renamed_routes": renamed,
        "candidate_route": canonical_shape(candidate),
        "candidate_via": candidate_via,
        "delivery_approach": canonical_shape(final),
        "policy_rules_fired": fired,
        "stages": phases,
        "gates": gates,
        "artifacts": artifacts,
        "subtask_ceiling": subtask_ceiling,
        "required_artifacts": required_artifacts,
        "required_skills": sorted(required_skills),
        "blocked_phases": blocked_phases,
        "max_worktrees": max_worktrees,
        "applicable_strategies": applicable_strategies,
        "checkpoints": checkpoints,
    }
    if issue:
        result["issue_overrides"] = {"applied": applied, "ignored": ignored}
    return result


# --- command: approach summary ------------------------------------------------

def cmd_approach_summary(args):
    """`compass approach summary`: the three lines a person reads before
    any code - the approach and the assessment behind it, the gates it must
    pass, and where the issue's files go. `/compass:go` prints this as its
    decision view, so it stays exactly three lines."""
    from compass_pkg.core import docs_dir

    task_dir = resolve_issue_dir(args.task)
    task, _ = load_manifest(task_dir)
    slug = os.path.basename(os.path.normpath(task_dir))
    a = task.get("assessment") or {}
    readings = ", ".join(f"{k} {a[k]}" for k in ("risk", "familiarity", "size")
                         if a.get(k))
    gates = [g.get("id") for g in task.get("gates") or [] if g.get("id")]
    checkpoints = task.get("checkpoints")
    if checkpoints is None:
        waits = ""
    elif checkpoints:
        waits = " - waits for you at: " + ", ".join(checkpoints)
    else:
        waits = " - does not stop to wait for you"
    print(f"Approach: {display_shape(task.get('delivery_approach'))}"
          + (f" ({readings})" if readings else "") + waits)
    print("Gates: " + (", ".join(gates) if gates else "none"))
    print(f"Writes: .compass/work/{slug}/ and {docs_dir(task_dir)}/")
    # The three lines stay three for a project that departs from nothing. One
    # that unlocks a framework entry is reported on every run (ADR-039).
    # A git parent adds one line with its state, read from the cache alone.
    from compass_pkg import locks, parent_states
    from compass_pkg.layers import find_project_root
    project = find_project_root(task_dir)
    for line in locks.conformance_lines(project) + parent_states.summary_lines(project):
        print(line)
    return 0


# --- command: approach evaluate -----------------------------------------------

def cmd_route_evaluate(args):
    task = None
    task_path = None
    task_dir = None
    if args.reading and getattr(args, "write", False):
        # Refused before anything prints: a refusal that follows a printed
        # result reads as a result that was written.
        raise CompassError("--write needs an issue (use --issue, or run it in an "
                           "issue); it cannot write an ad-hoc --assessment")
    if args.reading:
        readings = {}
        for pair in args.reading:
            if "=" not in pair:
                raise CompassError(f"--assessment expects key=value, got: {pair}")
            k, v = pair.split("=", 1)
            k = ASSESSMENT_KEY_MAP.get(k, k)
            if k == "labels":
                readings[k] = [t.strip() for t in v.split(",") if t.strip()]
            else:
                readings[k] = v.strip()
    else:
        task_dir = resolve_issue_dir(args.task)
        task, task_path = load_manifest(task_dir)
        if getattr(args, "write", False):
            # The slug reaches the living spec at ship, as a title does.
            from compass_pkg.manifest import slug_problem
            slug = os.path.basename(os.path.normpath(task_dir))
            root = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.normpath(task_dir))))
            problem = slug_problem(root, slug)
            if problem:
                raise CompassError(
                    f"compass approach evaluate: issue slug '{slug}' refused: "
                    f"{problem}")
        readings = task.get("assessment")
        if not readings:
            raise CompassError(
                f"{task_path} has no assessment block - the assess stage "
                f"records the four dimensions there before the approach is "
                f"evaluated."
            )
        from compass_pkg.core import assessment_key_errors
        key_errors = assessment_key_errors(readings)
        if key_errors:
            raise CompassError(f"{task_path}: " + "; ".join(key_errors))

    # The configuration the approach is computed from. An issue with a
    # generation is judged by it. `--write` commits the configuration as it is
    # now, so it computes from that. Only an issue with no generation, in a
    # project with no `compass.yml`, reads the governance files.
    from compass_pkg import effective
    view = effective.view_or_legacy(task_dir, live=bool(args.write))
    if view is None:
        gov = find_governance()
        policy = load_yaml(os.path.join(gov, "routing-policy.yml"))
        from compass_pkg.core import load_autonomy
        autonomy = load_autonomy()
    else:
        gov = None
        policy = view.evaluator_policy()
        autonomy = view.autonomy
    # The drift report compares a project's copy of the policy with the
    # framework's. A configuration resolved over such a copy still gets it.
    drift_gov = gov
    if view is not None and view.from_governance_copy():
        drift_gov = find_governance()
    result = evaluate_route(readings, policy, autonomy)
    if result.get("renamed_routes"):
        sys.stderr.write(
            "compass: governance/routing-policy.yml uses old route names ("
            + ", ".join(f"{old} -> {canonical_shape(old)}"
                        for old in result["renamed_routes"])
            + "); they are read as the new names. Rename them in the file; "
            "the old names stop working at the next major version.\n")

    from compass_pkg.terminal import Emitter, mark_handled, resolve_mode

    # This verb renders all three modes itself, including the JSON document it
    # shipped with. Saying so keeps the generic fallback in main() out of the
    # way - without it, the fallback would wrap this verb's JSON in its
    # "unconverted verb" envelope.
    mark_handled()
    _mode = resolve_mode(args)
    if _mode == "json":
        print(json.dumps(result, indent=2))
    elif _mode != "verbose":
        # The default view. Everything below this branch is what --verbose
        # still prints, unchanged: the provenance line, the raw assessment,
        # the per-stage weights and the full gate list. That detail is real,
        # and a person deciding whether the approach looks right does not need
        # all of it on the first screen - they need the approach, the rules
        # that produced it, and where it was written.
        _fired = [fired_rule_line(f) for f in result["policy_rules_fired"]]
        _ceiling = result["subtask_ceiling"]
        _concerns = []
        # Policy drift is a CONCERN, not provenance. The plain "which policy
        # file did I read" line is detail and lives under --verbose, but a
        # project running a policy that is missing rules the framework ships
        # gets a lighter approach than it should - and a reader has no way to
        # tell that from a genuinely light one. It belongs on the first screen.
        _drift = governance_drift(drift_gov) if drift_gov else None
        if _drift is not None and _drift.drifted:
            _fw = _drift.framework_versions.get("routing-policy.yml", "unknown")
            _concerns.append(
                "this project's policy is missing %d rule(s) or check(s) that "
                "framework v%s ships - run `compass policy lint`"
                % (_drift.count, _fw))
        if result["blocked_phases"]:
            _concerns += ["%s is blocked until %s" % (
                              _display_blocked_phase(b["phase"]), b["until"])
                          for b in result["blocked_phases"]]
        if result["required_artifacts"]:
            _concerns.append("documents required: "
                             + ", ".join(result["required_artifacts"]))
        _e = Emitter(mode=_mode,
                     evidence_out=getattr(args, "evidence_out", None))
        _e.hand_off(
            outcome="%s - %d gate(s), %s"
                    % (display_shape(result["delivery_approach"]),
                       len(result["gates"]),
                       "unbounded parallel subtasks" if _ceiling is None
                       else "up to %d parallel subtask(s)" % _ceiling),
            # Only if it is actually there. `delivery-approach.md` is written
            # by the assess command, not the evaluator, so do not point the
            # reader at it before it exists.
            read=(_approach_doc if task is not None
                  and os.path.isfile(_approach_doc := os.path.join(
                      task_dir, "delivery-approach.md")) else None),
            items=_fired or ["no policy rule fired - the shape is the "
                             "assessment's default"],
            concerns=_concerns,
            next_step=None if args.write else
            "nothing recorded - re-run with --write to fold this into the manifest")
        _e.flush()
    else:
        # Provenance first. delivery-approach.md records which rules fired
        # but not which policy file produced them, so print the policy
        # first, so a reader can tell a genuinely light route from a
        # stale-governance one.
        if gov:
            print(f"  policy          : {os.path.join(gov, 'routing-policy.yml')} "
                  f"(v{policy.get('version', 'unknown')})")
        elif view.source == "generation":
            print(f"  policy          : generation {view.generation} of this issue "
                  f"(parent {view.parent_version() or 'unknown'})")
        else:
            print("  policy          : this project's effective configuration "
                  "(compass.yml over the shipped default)")
        drift = governance_drift(drift_gov) if drift_gov else None
        if drift is None:
            pass
        elif drift.drifted:
            fw = drift.framework_versions.get("routing-policy.yml", "unknown")
            print(f"  POLICY DRIFT    : this policy is missing {drift.count} "
                  f"rule(s)/check(s) that framework v{fw} ships - "
                  f"run `compass policy lint` for the list")
        elif not drift.comparable:
            print(f"  policy drift    : not compared ({drift.reason})")
        print(f"  assessment      : {json.dumps(readings)}")
        print(f"  first approach  : {display_shape(result['candidate_route'])}  "
              f"<- {result['candidate_via']}")
        print(f"  FINAL APPROACH  : {display_shape(result['delivery_approach'])}")
        if result["policy_rules_fired"]:
            print("  policy rules fired:")
            seen_effects = set()
            for f in result["policy_rules_fired"]:
                # Meaning first, code in brackets: a bare id must not open
                # the first screen a new user sees. Keep the kind: it says
                # whether the rule raised the whole approach or only
                # attached one gate.
                print(f"    {fired_rule_line(f)}")
                for c in f["changed"]:
                    if c in seen_effects:
                        continue
                    seen_effects.add(c)
                    print(f"        - {c}")
        else:
            print("  policy rules fired: none")
        ceiling = result["subtask_ceiling"]
        permits = ("unbounded by policy" if ceiling is None
                   else f"up to {ceiling}")
        print(f"  parallel subtasks: {permits} (a ceiling - breakdown sets "
              f"the orchestration once the distribution map exists)")
        print("  per-stage weight:")
        for p, w in result["stages"].items():
            print(f"    {display_stage(p):<11}: {w}")
        print(f"  gate set        : {', '.join(result['gates'])}")
        if result["required_artifacts"]:
            print(f"  required artifacts: {', '.join(result['required_artifacts'])}")
        if result["required_skills"]:
            print(f"  required skills : {', '.join(result['required_skills'])}")
        if result["blocked_phases"]:
            for b in result["blocked_phases"]:
                print(f"  BLOCKED phase   : {_display_blocked_phase(b['phase'])} "
                      f"until {b['until']}")
        if result.get("applicable_strategies"):
            print("  advisory strategies (soft - assessed, never gating):")
            for s in result["applicable_strategies"]:
                print(f"    [{s['id']}] {s['strategy']}: {s['rationale']}")

    # --write: fold the result back into manifest.yml
    if args.write:
        if task is None:
            raise CompassError("--write needs an issue (use --issue, or run it in an "
                               "issue); it cannot write an ad-hoc --assessment")
        # Detect a re-assessment from the approach's content, not its name: a
        # governance update can add gates without changing the approach name.
        # The four assessment dimensions, compared against what the LAST
        # `--write` computed from. They cannot be read out of the manifest:
        # by the time this runs the manifest already holds the corrected
        # assessment, so there would be nothing to differ from.
        # `evaluated_assessment` is what closes that - each write records
        # the assessment it evaluated, and the next write compares against
        # it.
        #
        # Without this, a corrected assessment that leaves the approach
        # unchanged would not be logged, and that correction is the cheapest
        # evidence there is that sizing was wrong, which is exactly what
        # `compass retro` aggregates.
        prior = {
            "assessment": task.get("evaluated_assessment"),
            "delivery_approach": task.get("delivery_approach"),
            "stages": task.get("stages"),
            "subtask_ceiling": task.get("subtask_ceiling"),
            "gates": sorted(g.get("id") for g in (task.get("gates") or [])
                            if isinstance(g, dict)),
            "policy_rules_fired": sorted(
                f.get("id") for f in (task.get("policy_rules_fired") or [])
                if isinstance(f, dict)),
        }
        now = {
            "assessment": task.get("assessment"),
            "delivery_approach": result["delivery_approach"],
            "stages": result["stages"],
            "subtask_ceiling": result.get("subtask_ceiling"),
            "gates": sorted(result.get("gates") or []),
            "policy_rules_fired": sorted(
                f.get("id") for f in (result["policy_rules_fired"] or [])
                if isinstance(f, dict)),
        }
        # Only fields that were ALREADY recorded can have changed. An issue
        # whose stages or gates were never written is being filled in for the
        # first time - `--write` after a bare `delivery_approach:` is
        # materialisation, not a re-assessment, and logging it would put
        # noise into the signal this exists to sharpen. A previous write is
        # still needed: materialising an approach that was never computed is
        # not a re-assessment either.
        changed = {k: {"from": prior[k], "to": now[k]}
                   for k in prior if prior[k] and prior[k] != now[k]}
        evaluated_before = bool(prior["delivery_approach"]) or bool(prior["assessment"])
        reframed = evaluated_before and bool(changed)
        if reframed:
            reason = args.reason or "(reason not given - fill this in)"
            # The kind keeps `compass retro` accurate. Logging a
            # governance-driven weight-up as a plain re-assessment would read
            # as assessment under-sizing the work - and it is not: the
            # assessment was right, the policy under it moved. Only
            # `judgement` feeds the re-sizing aggregate.
            kind = getattr(args, "kind", None) or "judgement"
            task.setdefault("reassessments", []).append({
                "from_route": prior["delivery_approach"],
                "to_route": result["delivery_approach"],
                "kind": kind,
                "changed": changed,
                "reason": reason,
                "date": datetime.date.today().isoformat(),
            })
        task["schema_version"] = "2.0"
        # What this write computed from. Read by the NEXT write to notice a
        # corrected assessment; never read by anything else.
        # A COPY, not the same object. Assigning the reference makes PyYAML
        # emit an anchor alias (`evaluated_assessment: *id001`), so both keys
        # load as one dict and the comparison above can never see a
        # difference - the field would be written and be useless.
        task["evaluated_assessment"] = dict(task.get("assessment") or {})
        task["delivery_approach"] = result["delivery_approach"]
        task["policy_rules_fired"] = result["policy_rules_fired"]
        task["stages"] = result["stages"]
        task["checkpoints"] = result["checkpoints"]
        # seed the gate list (status pending) without clobbering existing state
        existing = {g.get("id"): g for g in task.get("gates", []) if isinstance(g, dict)}
        task["gates"] = [
            existing.get(gid, {"id": gid, "status": "pending", "evidence": []})
            for gid in result["gates"]
        ]
        # Seed the artifact registry the same way the gate list is seeded:
        # what routing computed, without clobbering a status or path a stage
        # has already recorded against an entry.
        recorded = {a.get("kind"): a for a in task.get("artifacts", [])
                    if isinstance(a, dict)}
        merged = []
        for a in result["artifacts"]:
            keep = recorded.get(a["kind"])
            if keep:
                keep = dict(keep)
                keep["reason"] = a["reason"]      # the rule that earned it
                merged.append(keep)
            else:
                merged.append(a)
        # A human-recorded omission of something routing no longer earns is
        # kept: it is a decision someone took, not stale computed output.
        for kind, a in recorded.items():
            if a.get("status") == "omitted" and not any(m["kind"] == kind for m in merged):
                merged.append(a)
        task["artifacts"] = merged
        # make sure the evidence registry exists at the top level
        task.setdefault("evidence", [])
        task["subtask_ceiling"] = result["subtask_ceiling"]
        # Assess never records an orchestration: breakdown owns it, once the
        # distribution map says whether independent subtasks exist.
        task.pop("orchestration", None)
        # The manifest is replaced inside the commit, after the generation's
        # files are whole (ADR-036). A configuration that does not resolve
        # raises here, before any file is written.
        from compass_pkg import effective
        # The accepted-type comments are written in the same replace, under the lock.
        committed = effective.commit_generation(task_dir, task,
                                                render=annotate_gate_accepts_text)
        print(f"\n  wrote the delivery approach, stages and gates -> {task_path}")
        print(f"  {committed.message}")
        from compass_pkg.dashboard import stale_page_reminder
        reminder = stale_page_reminder(task_dir)
        if reminder:
            print(f"  {reminder}")
        if not reframed and getattr(args, "reason", None):
            print("  the delivery approach did not change - the --reason was NOT "
                  "recorded. The approach, stages, gates, ceiling and policy "
                  "rules fired are all identical to what was already on record.")
        if reframed:
            print(f"  RE-ASSESSMENT recorded ({task['reassessments'][-1]['kind']}): "
                  f"{prior['delivery_approach']} -> {result['delivery_approach']}"
                  + (f"  [changed: {', '.join(sorted(changed))}]" if changed else ""))
            if not args.reason:
                sys.stderr.write(
                    "compass: re-assessment recorded with no reason. Re-run with "
                    "--reason \"...\" or edit manifest.yml's last `reassessments` "
                    "entry - the reason is the calibration signal.\n"
                )
    return 0
