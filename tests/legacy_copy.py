# tests/legacy_copy.py - the 8.x reader of a copied governance folder, for the contracts
"""Read a copy of `routing-policy.yml` and `guardrails.yml`
as 8.x read it.

Compass 9.0.0 does not read copied governance: a project that holds a copy and
no `compass.yml` is refused with `governance-copy-removed` (ADR-098). This
module is the reader 8.x ran, kept for the tests that compare 9.0.0 with what
8.x routed: contracts 1 and 2 (the 8.0.4 copy, and configuration C, the 5.6.0
copy), `test_evidence_required.py` and the route tests that compare with
8.0.4 (VD-043 decision 1). No CLI module imports it.

`adapt` converts the two files into one catalogue-form document. It reads data
and returns data, and copies every value before it renames it. Old key names
are read through the migration map the loaders use, so a policy copied before
the renames converts to the same document as a newer one. Three things change
shape in the catalogue:

- the fallback approach (`default_route`) becomes the last rule of the
  `default_shapes` set, matching every assessment;
- the free-text `biases` become a rule set with no effect;
- a guardrail's `checked_at` keeps its first stage as the gate's `stage`,
  which the design records and does not enforce.

`resolved_from_copy` then reads the adapted document as the whole
configuration, as `effective.resolve_live` read a copy before 9.0.0.
"""
# DEPENDENCY: standard library (copy, os, re, sys); compass_pkg.core, compass_pkg.routing,
# compass_pkg.stable_ids, compass_pkg.artifact_kinds,
# compass_pkg.path_stages, compass_pkg.word_map, compass_pkg.catalogue_spec,
# compass_pkg.check_set, compass_pkg.effective and compass_pkg.removed_parts.
from __future__ import annotations

import copy
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))

from compass_pkg import artifact_kinds, check_set, core, removed_parts
from compass_pkg import stable_ids, word_map
from compass_pkg import catalogue_spec as spec
from compass_pkg.effective import _non_text_keys
from compass_pkg.routing import canonical_routes
from compass_pkg.path_stages import rename_v1_stage_keys
from compass_pkg.stable_ids import (APPROACH_REGULAR, APPROACH_SPIKE, GATE_G5, GATE_SPIKE_CONCLUDE,
                                    PATH_STAGE_IDS, STAGE_ASSESS, STAGE_BUILD, STAGE_IDS,
                                    STAGE_SHIP, STAGE_VERIFY)

# The eight stages in the order they run. A stage an approach names that is
# not here is appended, so an unusual policy still converts.
STAGE_ORDER = STAGE_IDS

# A mode has a rank only when it sits on the depth ladder. Every other mode
# differs in kind, not in depth, so it has no rank and the classifier treats
# it as incomparable. The one mode above `thorough` is "thorough, plus a
# follow-up". The ranks reproduce today's lift, which raises exactly
# `collapsed`, `skipped` and `lightweight` to `thorough` and leaves every other
# mode as it is.
MODE_RANKS = stable_ids.MODE_RANKS

# The dimensions that have an order, and which way is stricter.
ORDERED_DIMENSIONS = ("risk", "size")
REQUIRED_DIMENSIONS = ("risk", "familiarity", "size")

# How two rules that set the same effect combine. A selector is not an
# effect and has no entry: `ceiling` picks which loop ceiling `limit` sets,
# `until` says when a blocked stage opens again, and `seat` picks which seat
# `tier` and `effort` set.
EFFECT_HITS = {
    "force_minimum_approach": "max",
    "lean_toward": "first",
    "max_worktrees": "min",
    "limit": "min",
    "tier": "max",
    "effort": "max",
}
SELECTORS = ("ceiling", "until", "seat")

# Effects the catalogue form names differently (ADR-041).
RENAMED_EFFECTS = {"force_minimum_route": "force_minimum_approach",
                   "forbid_route": "forbid_approach"}
STAGE_EFFECTS = ("require_phase", "block_phase", "never_skip")
ARTIFACT_EFFECTS = ("add_artifact", "require_artifact", "suggest_artifact")

# Locks (ADR-039). The human sign-off guardrail `G5` and its check cannot be
# unlocked by anyone.
# On the four-stage path (ADR-092) the build stage holds the Definition of Done,
# which the `verify` stage held before, so it takes that stage's lock.
LOCKED_STAGES = (STAGE_ASSESS, STAGE_VERIFY, STAGE_BUILD, STAGE_SHIP)
LOCKED_REVIEW_GATES = (GATE_SPIKE_CONCLUDE,)
HARD_GUARDRAILS = (GATE_G5,)

# What a check reports when it cannot run, read from each module that
# returns `NOTHING_TO_CHECK` for it: checks.py (scenarios-are-executable,
# claim-traces-to-scenario, command-passes), binding.py (evidence-matches-tree), checks.py
# (dod-evidence-typed), landed_by.py, evidence_identity.py and section_checks.py, and
# multiagent_check.py, borrowed_docs.py, artifact_status.py and design_size.py (removed in
# 9.0.0, still named so an old guardrails copy reads as before).
# The check declared-tests-resolve returns a pass with a note. Every other check
# fails.
DECLINING_CHECKS = (
    "scenarios-are-executable", "claim-traces-to-scenario", "command-passes",
    "borrowed-documents-answered", "evidence-matches-tree",
    "evidence-identity-matches", "dod-evidence-typed", "landed-by-resolves", "multiagent-run-recorded", "artifacts-approved",
    "nfr-rows-resolved", "contracts-declared", "design-within-word-ceiling",
    "acceptance-applicability-agrees", "outer-loop-recorded", "acceptance-support-present", "outer-loop-attempts-recorded",
    "isolation-proven", "layering-test-passed",
)
PASSING_CHECKS = ("declared-tests-resolve",)
# The checks the check set declares `severity: advisory`. The legacy guardrails
# file has no severity field, so the adapter gives them this severity.
ADVISORY_CHECKS = ("acceptance-applicability-agrees", "acceptance-support-present")

# The parameters of each shipped check that takes some (ADR-064). The legacy
# guardrails file has no field for them, so the adapter holds the table the
# preset's checks.yml carries.
CHECK_PARAMS = {
    "design-within-word-ceiling": {"factor": 1.5},
    "contracts-declared": {
        "trigger_paths": ["schemas/*", "governance/presets/*", "*.schema.json"],
        "trigger_contents": [{"path": "*.py", "contains": "add_parser("}],
    },
}

# The order the generator rebuilds a rule or a guardrail in unless the
# sidecar says the legacy file differs.
GUARDRAIL_KEYS = ("id", "name", "statement", "checks", "applies_when", "checked_at")

_FALLBACK_RULE = "RP-SHAPE-FALLBACK"


class _Notes:
    """What the catalogue form cannot hold, collected while converting, for
    the sidecar."""

    def __init__(self):
        self.policy_when = {}
        self.guardrail_when = {}
        self.legacy_values = {}
        self.rule_key_order = {}
        self.guardrail_key_order = {}
        self.checked_at = {}


def _dimension_name(name):
    name = core.ASSESSMENT_KEY_MAP.get(name, name)
    return core.WHEN_KEY_MAP.get(name, name)


def _when(when, seen=None):
    """A `when:` clause with current dimension names, copied. `seen` collects
    each renamed key, current spelling to legacy spelling."""
    if not isinstance(when, dict):
        return copy.deepcopy(when)
    out = {}
    for key, value in when.items():
        new = core.WHEN_KEY_MAP.get(key, key)
        if seen is not None and new != key:
            seen[new] = key
        if new == "any_of" and isinstance(value, list):
            out[new] = [_when(c, seen) for c in value]
        else:
            out[new] = copy.deepcopy(value)
    return out


def _stage(name):
    return core._stage_key_renames().get(name, name)


def _stage_list(names):
    """A list of stage names with the v1 names renamed only when the list is v1:
    `specify` and `build` are path stages too (ADR-092), so a 9.0.0 list keeps them."""
    return rename_v1_stage_keys(list(names), core._stage_key_renames())


def _on_path(policy):
    """True for a policy whose approaches name only the path stages (ADR-092)."""
    shapes = (policy.get("route_shapes") or {}).values()
    used = {s for shape in shapes for s in core.shape_stages(shape)}
    return bool(used) and used <= set(PATH_STAGE_IDS)


def _artifact_id(value):
    value = str(value)
    return value[:-3] if value.endswith(".md") else value


# --- dimensions ----------------------------------------------------------------

def _dimensions(policy):
    vocabulary = {
        _dimension_name(k): v
        for k, v in (policy.get("assessment_vocabulary")
                     or policy.get("reading_vocabulary") or {}).items()}
    out = {}
    for name, values in vocabulary.items():
        if name == "labels_common":
            continue
        entry = {"type": "ordered-enum" if name in ORDERED_DIMENSIONS else "enum",
                 "values": list(values)}
        if name in ORDERED_DIMENSIONS:
            entry["tighter"] = "higher"
        if name in REQUIRED_DIMENSIONS:
            entry["required"] = True
        out[name] = entry
    # Labels are an open set: the common values are suggestions.
    out["labels"] = {"type": "set", "open": True,
                     "common": list(vocabulary.get("labels_common") or [])}
    return out


# --- approaches and stages -------------------------------------------------------

def _approaches(policy):
    shapes = policy.get("route_shapes") or {}
    table = policy.get("autonomy_checkpoints") or {}
    out = {}
    for name, shape in shapes.items():
        entry = {"weight": shape["weight"], "ships": name != APPROACH_SPIKE}
        # Every approach that ships owes a release line, as the shipped default says;
        # like `ships`, no legacy file holds the field, so it follows the approach (ADR-065).
        if name != APPROACH_SPIKE:
            entry["release_line"] = True
        entry.update({
            # `shape_stages` also reads the retired `phases:` block.
            "stages": core.shape_stages(shape),
            "gates": list(shape.get("gates") or []),
            # A shape with no ceiling allows one subtask, as the evaluator reads it.
            "subtask_ceiling": shape.get("subtask_ceiling", 1),
        })
        if shape.get("artifacts"):     # a 9.0.0 view has no `artifacts:` map (ADR-091)
            entry["artifacts"] = {_artifact_id(k): v for k, v in shape["artifacts"].items()}
        # An autonomy level or approach the table leaves out waits at every
        # hand-off, so it is left out here too rather than given an empty list.
        checkpoints = {level: _stage_list(row[name])
                       for level, row in table.items()
                       if isinstance(row, dict) and name in row}
        if checkpoints:
            entry["checkpoints"] = checkpoints
        if name == APPROACH_SPIKE:
            entry["locked"] = True
        out[name] = entry
    return out


def _stages(approaches):
    used = {}
    for approach in approaches.values():
        for stage, mode in approach["stages"].items():
            used.setdefault(stage, [])
            if mode not in used[stage]:
                used[stage].append(mode)
    # A policy on the four-stage path lists its stages in path order (ADR-092).
    order = PATH_STAGE_IDS if set(used) <= set(PATH_STAGE_IDS) else STAGE_ORDER
    names = [s for s in order if s in used]
    names += [s for s in used if s not in order]
    out = {}
    for order, stage in enumerate(names, start=1):
        modes = sorted(used[stage], key=lambda m: (m not in MODE_RANKS,
                                                   MODE_RANKS.get(m, 0), m))
        entry = {"order": order,
                 "modes": {m: ({"rank": MODE_RANKS[m]} if m in MODE_RANKS else {})
                           for m in modes}}
        if stage in LOCKED_STAGES:
            entry["locked"] = True
        out[stage] = entry
    return out


# --- rules -------------------------------------------------------------------------

def _effect(key, value):
    """An effect in its catalogue spelling: the key, then the value."""
    key = RENAMED_EFFECTS.get(key, key)
    if key in STAGE_EFFECTS:
        value = [_stage(v) for v in value] if isinstance(value, list) else _stage(value)
    elif key in ARTIFACT_EFFECTS:
        value = _artifact_id(value)
    return key, copy.deepcopy(value)


def _convert_rule(rule, notes):
    """`(id, when, then, extra)` for one legacy rule. Every key but `id`,
    `when` and `rationale` is an effect, so none is lost; what the new
    spelling cannot say goes to the notes."""
    rule_id = rule["id"]
    # The new spelling keys a rule by its id. A malformed id, such as a list,
    # is read as its text, as the 8.x evaluator reads it: the router must not
    # crash on it, and `compass policy lint` reports it (`TRC-D1`).
    if not isinstance(rule_id, str):
        rule_id = str(rule_id)
    when = _when(rule["when"], notes.policy_when) if "when" in rule else None
    then = {}
    for key, value in rule.items():
        if key in ("id", "when", "rationale"):
            continue
        new_key, new_value = _effect(key, value)
        then[new_key] = new_value
        if new_value != value:
            notes.legacy_values.setdefault(rule_id, {})[key] = copy.deepcopy(value)
    default = ["id"] + (["when"] if when is not None else []) \
        + [k for k in rule if k not in ("id", "when", "rationale")] \
        + (["rationale"] if "rationale" in rule else [])
    if list(rule) != default:
        notes.rule_key_order[rule_id] = list(rule)
    extra = {"rationale": rule["rationale"]} if "rationale" in rule else {}
    return rule_id, when, then, extra


def _rule_set(kind, rules, locked=False):
    """A rule set from `(id, when, then, extra)` tuples, with a hit policy
    for each effect any rule sets."""
    hit, body = {}, {}
    for order, (rule_id, when, then, extra) in enumerate(rules, start=1):
        rule = {"order": order}
        if when is not None:
            rule["when"] = when
        if then:
            rule["then"] = then
        rule.update(extra)
        body[rule_id] = rule
        for effect in then:
            if effect not in SELECTORS:
                hit.setdefault(effect, EFFECT_HITS.get(effect, "collect"))
    out = {"kind": kind, "hit": hit, "rules": body}
    if locked:
        out["locked"] = True
    return out


def _rules(policy, notes):
    strategies = policy.get("routing_strategies") or {}
    guard = policy.get("routing_guardrails") or {}

    def converted(items):
        return [_convert_rule(r, notes) for r in items or []]

    out = {}
    shapes = converted(strategies.get("default_shapes"))
    shapes.append((_FALLBACK_RULE, {}, {"lean_toward":
                   strategies.get("default_route", APPROACH_REGULAR)},
                   {"rationale": "No other shape matched, so the working default."}))
    out["default_shapes"] = _rule_set("shapes", shapes)
    out["floors"] = _rule_set("floors", converted(guard.get("floors")))
    # A 9.0.0 view holds no caps (ADR-092), so it makes no rule set.
    if "caps" in guard:
        out["caps"] = _rule_set("caps", converted(guard.get("caps")))
    out["loop_ceilings"] = _rule_set("ceilings", converted(guard.get("loop_ceilings")))
    out["immovable_gates"] = _rule_set(
        "immovable-gates", converted(guard.get("immovable_gates")), locked=True)
    # A 7.0.0 policy holds `artifact_rules`; a 6.x copy holds `role_rules` and
    # `role_defaults`, which convert as they always did (ADR-070). A block the
    # policy does not hold makes no rule set. A 9.0.0 view holds neither block
    # (ADR-091).
    if "artifact_rules" in guard:
        out["artifact_rules"] = _rule_set("artifact-rules",
                                          converted(guard.get("artifact_rules")))
    if "role_rules" in guard:
        out["role_rules"] = _rule_set("role-rules", converted(guard.get("role_rules")))
    out["advisory"] = _rule_set("advisory", converted(strategies.get("advisory_strategies")))
    if "role_defaults" in strategies:
        out["role_defaults"] = _rule_set("advisory", converted(strategies.get("role_defaults")))
    # A copy written before 9.0.0 can hold `model_rules`. 9.0.0 removed model
    # tiers (ADR-090), so the block makes no rule set and is not read.
    out["biases"] = _rule_set("biases", [
        (f"RP-BIAS-{i:03d}", None, {}, {"rationale": str(text)})
        for i, text in enumerate(strategies.get("biases") or [], start=1)])
    return out


# --- checks and gates ------------------------------------------------------------

def _locked_by_gate(guardrails):
    """Each check's lock: `hard` when a hard-locked guardrail holds it,
    `true` when any other guardrail does."""
    locks = {}
    for group in ("defaults", "spike_guardrails"):
        for gate in guardrails.get(group) or []:
            level = "hard" if gate["id"] in HARD_GUARDRAILS else True
            for check in gate.get("checks") or []:
                if locks.get(check) != "hard":
                    locks[check] = level
    return locks


def _project_check_id(guardrail):
    """The id of the check a project guardrail's `command-passes` becomes:
    the guardrail id, then its name as a slug."""
    slug = "".join(c if c.isalnum() else "-" for c in str(guardrail.get("name", "")).lower())
    slug = "-".join(part for part in slug.split("-") if part)
    return f"{guardrail['id']}-{slug}" if slug else str(guardrail["id"])


def _project_guardrails(guardrails):
    return [g for g in guardrails.get("project") or []
            if isinstance(g, dict) and "id" in g]


def _checks(guardrails, notes):
    locks = _locked_by_gate(guardrails)
    out = {}
    for name, body in (guardrails.get("checks") or {}).items():
        entry = {"statement": body["description"], "kind": "deterministic",
                 "impl": name, "severity": "advisory" if name in ADVISORY_CHECKS
                 else "blocking"}
        if "blocking_when" in body:
            entry["blocking_when"] = _when(body["blocking_when"], notes.guardrail_when)
        entry["on_skipped"] = ("not-applicable" if name in DECLINING_CHECKS
                               else "pass" if name in PASSING_CHECKS else "fail")
        if name in locks:
            entry["locked"] = locks[name]
        if name in CHECK_PARAMS:
            entry["params"] = copy.deepcopy(CHECK_PARAMS[name])
        out[name] = entry
    # A project guardrail runs the project's own command through the generic
    # `command-passes` check; its parameters belong to the check it becomes.
    for guardrail in _project_guardrails(guardrails):
        if "command-passes" in (guardrail.get("checks") or []):
            check = {"statement": guardrail.get("statement", ""), "kind": "deterministic",
                     "impl": "command-passes", "severity": "blocking",
                     "on_skipped": "not-applicable"}
            if guardrail.get("params"):
                check["params"] = copy.deepcopy(guardrail["params"])
            out[_project_check_id(guardrail)] = check
    return out


def _first_stage(guardrail):
    for stage in _stage_list(guardrail.get("checked_at") or []):
        return stage
    return None


def _guardrail_gate(guardrail, ships, notes):
    notes.checked_at[guardrail["id"]] = list(guardrail.get("checked_at") or [])
    default = [k for k in GUARDRAIL_KEYS if k in guardrail]
    if list(guardrail) != default:
        notes.guardrail_key_order[guardrail["id"]] = list(guardrail)
    entry = {"kind": "guardrail", "name": guardrail["name"],
             "statement": guardrail["statement"]}
    stage = _first_stage(guardrail)
    if stage:
        entry["stage"] = stage
    entry["applies_to"] = {"ships": ships}
    if "applies_when" in guardrail:
        entry["when"] = _when(guardrail["applies_when"], notes.guardrail_when)
    entry["checks"] = list(guardrail.get("checks") or [])
    entry["locked"] = "hard" if guardrail["id"] in HARD_GUARDRAILS else True
    return entry


def _gates(policy, guardrails, approaches, rules, notes):
    out = {}
    for g in guardrails.get("defaults") or []:
        out[g["id"]] = _guardrail_gate(g, True, notes)
    for g in guardrails.get("spike_guardrails") or []:
        out[g["id"]] = _guardrail_gate(g, False, notes)
    for g in _project_guardrails(guardrails):
        gate = _guardrail_gate(g, True, notes)
        # The project's own gate is not one of the framework's locks.
        gate.pop("locked", None)
        gate["checks"] = [_project_check_id(g) if c == "command-passes" else c
                          for c in g.get("checks") or []]
        out[g["id"]] = gate
    immovable = {r["gate"] for r in
                 (policy.get("routing_guardrails") or {}).get("immovable_gates") or []}
    accepted = guardrails.get("gate_evidence_requirements") or {}
    # A gate an approach or a rule names but the requirements do not list
    # accepts any evidence type, which an entry with no `accepts` says.
    review = list(accepted)
    for approach in approaches.values():
        review += [g for g in approach["gates"] if g not in review]
    for rule_set in rules.values():
        for rule in rule_set["rules"].values():
            for key in ("add_gate", "gate"):
                gate = (rule.get("then") or {}).get(key)
                if gate and gate not in review:
                    review.append(gate)
    # A review gate is judged at the `verify` stage, or at ship on the four-stage
    # path (ADR-092).
    review_stage = STAGE_SHIP if _on_path(policy) else STAGE_VERIFY
    for gate in review:
        entry = {"kind": "review", "stage": review_stage}
        if gate in accepted:
            entry["accepts"] = list(accepted[gate])
        if gate in immovable or gate in LOCKED_REVIEW_GATES:
            entry["locked"] = True
        out[gate] = entry
    return out


# --- artifacts and vocabulary ----------------------------------------------------

def _artifacts(approaches, rules):
    names = []

    def note(value):
        value = _artifact_id(value)
        if value not in names:
            names.append(value)

    for approach in approaches.values():
        for artifact in approach.get("artifacts") or {}:
            note(artifact)
    for rule_set in rules.values():
        for rule in rule_set["rules"].values():
            for key in ("add_artifact", "require_artifact", "suggest_artifact"):
                if key in (rule.get("then") or {}):
                    note(rule["then"][key])
    shipped = artifact_kinds.shipped()
    return {name: _artifact_entry(name, shipped) for name in names}


# What the legacy files cannot say about a document: they hold its name and the
# approaches and rules that owe it. For a kind the shipped default declares, the
# description fields and the condition come from the shipped default, so a
# project that still carries copies of the two files resolves the same kinds.
# `every_approach` is not copied: it would make an old policy owe a document it
# never listed. `word_ceiling` is not copied either: a project on copied 5.x
# governance gets no word limit it never had. A name the shipped default does not declare keeps only its file,
# and the merge then asks the layer for the fields it lacks.
SHIPPED_FIELDS = ("stage", "owner", "audience", "stands_for", "sections", "depends_on",
                  "required_when")


def _artifact_entry(name, shipped):
    default = shipped.get(name)
    if not isinstance(default, dict):
        return {"file": f"{name}.md"}
    entry = {"file": default.get("file", f"{name}.md")}
    for field in SHIPPED_FIELDS:
        if field in default:
            entry[field] = copy.deepcopy(default[field])
    return entry


# A display name a person would not guess from the id. The id keeps its
# name; the display name says what the check asks today.
DISPLAY_NAMES = {
    "checks.acceptance-applicability-agrees": "Acceptance strategy applicability agrees",
    "checks.outer-loop-recorded": "Outer-loop red and green recorded",
    "checks.acceptance-support-present": "Acceptance support code present",
    "checks.outer-loop-attempts-recorded": "Outer-loop run count recorded",
    "checks.isolation-proven": "Isolation proven",
    "checks.layering-test-passed": "Layering test passed",
    "checks.artifacts-approved": "Documents approved",
    "checks.backfills-paid": "Follow-ups resolved",
    "checks.dod-evidence-typed": "Definition of Done evidence is typed",
    "checks.landed-by-resolves": "Landed-by resolves",
    "checks.nfr-rows-resolved": "Non-functional rows resolved",
    "checks.spike-no-production-changes": "Spike changes no production code",
}


def _humanise(identifier):
    text = identifier.replace("-", " ")
    return text[:1].upper() + text[1:]


def _vocabulary(approaches, stages, checks, gates):
    out = {}
    for name in approaches:
        out[f"approaches.{name}"] = {"name": core.display_shape(name), "aliases": []}
    for name in stages:
        out[f"stages.{name}"] = {"name": core.display_stage(name), "aliases": []}
    for name, gate in gates.items():
        if "name" in gate:
            out[f"gates.{name}"] = {"name": gate["name"], "aliases": []}
    for name in checks:
        out[f"checks.{name}"] = {
            "name": DISPLAY_NAMES.get(f"checks.{name}", _humanise(name)),
            "aliases": []}
    return out


# --- the public surface -----------------------------------------------------------

def _convert(policy, guardrails):
    # A policy copied before the depth words and the size were renamed is
    # converted as the new words.
    policy, _renamed = canonical_routes(word_map.map_policy(policy or {}))
    guardrails = copy.deepcopy(guardrails or {})
    notes = _Notes()
    approaches = _approaches(policy)
    stages = _stages(approaches)
    rules = _rules(policy, notes)
    checks = _checks(guardrails, notes)
    gates = _gates(policy, guardrails, approaches, rules, notes)
    document = {
        "schema": 1,
        "dimensions": _dimensions(policy),
        "stages": stages,
        "approaches": approaches,
        "rules": rules,
        "checks": checks,
        "gates": gates,
        "artifacts": _artifacts(approaches, rules),
        # The two legacy files have no readiness entry, and 9.0.0 declares no
        # readiness signal (ADR-093), so a copy's catalogue is empty.
        "readiness": {},
        "vocabulary": _vocabulary(approaches, stages, checks, gates),
    }
    return document


def adapt(policy, guardrails):
    """One layer document in catalogue form from a routing policy and a
    guardrails file: `schema: 1` and the nine catalogues."""
    return _convert(policy, guardrails)


def adapt_evidence_types(guardrails):
    """The evidence types as the preset's ninth data set. A project cannot
    add, change or remove one, so it is not a catalogue."""
    types = (guardrails or {}).get("evidence_types") or {}
    return {"schema": 1,
            "evidence_types": {name: {"description": body["description"]}
                               for name, body in types.items()}}


# --- the copy as the whole configuration ---------------------------------------
# What `effective.resolve_live` did for a project with a copy and no `compass.yml`
# before 9.0.0. The value and entry checks are those the 8.x layer check ran on a
# copy before anything merged, so a planted fault is refused as 8.x refused it.

COPIED_FILES = ("routing-policy.yml", "guardrails.yml")


def _legacy_parent(root):
    """`(doc, meta)` for a project that keeps its own copies of the two
    governance files, or None. `doc` is the copy in catalogue form (`adapt`),
    with the check set's capabilities."""
    folder = os.path.join(root, "governance")
    if not all(os.path.isfile(os.path.join(folder, name)) for name in COPIED_FILES):
        return None
    policy = core.load_yaml(os.path.join(folder, "routing-policy.yml"))
    guardrails = core.load_yaml(os.path.join(folder, "guardrails.yml"))
    doc = adapt(policy, guardrails)
    doc["capabilities"] = dict(check_set.load()["capabilities"])
    return doc, {"id": "legacy", "version": str(policy.get("version", "")),
                 "source": "legacy", "guardrails": guardrails}


_ID = re.compile(spec.ID_PATTERN)
#: The entry operations of the 8.x merge that change an entry below the layer. A
#: copy is the whole configuration, so there is none for them to change.
_CHANGES = ("set", "replace", "remove", "unlock")
#: The operations that ride on an entry and are not read here: no lock or waiver
#: exists in 9.0.0 (ADR-094). `locked` is kept where it is a field, as 8.x kept it.
_IGNORED = ("locked", "waiver")


def _legacy_enums():
    """The closed set of each enumerated field, by catalogue and field."""
    from compass_pkg import acceptance_strategy
    return {
        ("checks", "kind"): spec.CHECK_KINDS, ("checks", "severity"): spec.SEVERITIES,
        ("checks", "on_skipped"): spec.ON_SKIPPED, ("checks", "locked"): spec.LOCKS,
        ("gates", "kind"): spec.GATE_KINDS, ("gates", "locked"): spec.LOCKS,
        ("dimensions", "type"): spec.DIMENSION_TYPES, ("dimensions", "tighter"): spec.TIGHTER,
        ("approaches", "acceptance_strategy"): tuple(acceptance_strategy.ROUTINGS),
    }


def _is_type(value, expected):
    if expected == "string":
        return isinstance(value, str)
    if expected == "list":
        return isinstance(value, list)
    if expected == "map":
        return isinstance(value, dict)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer-or-null":
        return value is None or (isinstance(value, int) and not isinstance(value, bool))
    if expected == "boolean-or-hard":
        return value is True or value == "hard"
    return True


def _when_problems(path, when, ordered):
    """`at_least:` compares by order, so it needs an ordered dimension and a
    threshold among its values; a misspelt threshold would match nothing."""
    out = []
    for key, value in when.items():
        if key == "any_of" and isinstance(value, list):
            for i, clause in enumerate(value):
                if isinstance(clause, dict):
                    out += _when_problems(f"{path}.any_of[{i}]", clause, ordered)
        elif isinstance(value, dict) and "at_least" in value:
            if key not in ordered:
                out.append(f"{path}.{key}: at_least needs an ordered dimension, "
                           f"and {key} is not one")
            elif value["at_least"] not in ordered[key]:
                out.append(f"{path}.{key}: at_least '{value['at_least']}' is not a "
                           f"value of {key} ({', '.join(ordered[key])})")
    return out


def _legacy_value_problems(doc):
    """Every malformed field value in an adapted copy, as text naming its key
    path: a value of the wrong type, a value outside the closed set of its field,
    an incomplete dimension, and an `at_least:` that cannot match. These are the
    value checks the 8.x layer check ran on a copy before anything merged; the
    entry checks are `_legacy_entry_problems`."""
    enums = _legacy_enums()
    ordered = {name: list(values) for name, values in spec.SHIPPED_ORDERS.items()}
    for name, entry in ((doc.get("dimensions") or {}).items()
                        if isinstance(doc.get("dimensions"), dict) else ()):
        if isinstance(entry, dict) and entry.get("type") == "ordered-enum" \
                and isinstance(entry.get("values"), list):
            ordered[name] = list(entry["values"])
    out = []
    for catalogue in spec.CATALOGUES:
        entries = doc.get(catalogue)
        if not isinstance(entries, dict):
            continue
        fields = spec.FIELDS[catalogue]
        for entry_id, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            path = f"{catalogue}.{entry_id}"
            values = {k: v for k, v in entry.items() if k in fields}
            for key, value in values.items():
                expected = fields[key]["type"]
                list_op = expected == "list" and isinstance(value, dict) \
                    and set(value) <= {"add", "remove"}
                map_op = expected == "map" and isinstance(value, dict)
                if not (list_op or map_op or _is_type(value, expected)):
                    out.append(f"{path}.{key}: expected {expected.replace('-', ' ')}, "
                               f"found {value!r}")
                    continue
                allowed = enums.get((catalogue, key))
                if allowed is not None and value not in allowed:
                    out.append(f"{path}.{key}: '{value}' is not one of "
                               f"{', '.join(str(a) for a in allowed)}")
            if catalogue == "dimensions" and values.get("type") in spec.DIMENSION_TYPES:
                kind = values["type"]
                if kind in ("ordered-enum", "enum") and not isinstance(values.get("values"), list):
                    out.append(f"{path}.values: an {kind} lists its values")
                if kind == "ordered-enum" and values.get("tighter") not in spec.TIGHTER:
                    out.append(f"{path}.tighter: an ordered-enum says which way is "
                               f"stricter: {', '.join(spec.TIGHTER)}")
                if kind == "set" and not isinstance(values.get("open"), bool):
                    out.append(f"{path}.open: a set says whether it is open (true or false)")
            elif catalogue == "dimensions" and any(k in values
                                                   for k in ("values", "tighter", "open")):
                out.append(f"{path}.type: a dimension names its type: "
                           f"{', '.join(spec.DIMENSION_TYPES)}")
            for key in ("when", "blocking_when"):
                if isinstance(values.get(key), dict):
                    out += _when_problems(f"{path}.{key}", values[key], ordered)
            if catalogue == "rules" and isinstance(values.get("rules"), dict):
                for rule_id, rule in values["rules"].items():
                    if isinstance(rule, dict) and isinstance(rule.get("when"), dict):
                        out += _when_problems(f"{path}.rules.{rule_id}.when",
                                              rule["when"], ordered)
    return out


def _legacy_entry_problems(catalogue, entry_id, entry):
    """What stops one adapted entry being added as it stands, as text that
    names its key path. These are the faults the 8.x merge refused in a full
    entry added to an empty configuration."""
    path = f"{catalogue}.{entry_id}"
    if not isinstance(entry_id, str) or not _ID.match(entry_id):
        return [f"{path}: '{entry_id}' is not a valid id "
                f"(a letter, then letters, digits, '.', '_' or '-')"]
    if not isinstance(entry, dict):
        return [f"{path}: expected a mapping"]
    fields = spec.FIELDS[catalogue]
    out = [f"{path}.{key}: a copy cannot use {key}" for key in entry if key in _CHANGES]
    out += [f"{path}.{key}: not a field of {catalogue}" for key in entry
            if key not in _CHANGES and key not in _IGNORED and key not in fields]
    out += [f"{path}: a full entry is needed; missing {name}"
            for name, field_spec in fields.items()
            if field_spec["required"] and name not in entry]
    for key, value in entry.items():
        kind = fields.get(key, {}).get("merge")
        if (catalogue, key) == ("stages", "mode"):
            out.append(f"{path}.mode: mode is the issue layer's choice; a copy cannot set it")
        elif isinstance(value, dict) and (
                kind == "list" or (kind == "map" and value and set(value) <= {"set", "remove"})):
            out.append(f"{path}.{key}: a copy writes the value itself, not an operation on it")
    return out


def _legacy_config(doc):
    """`(config, provenance)` of an adapted copy. The copy is the whole
    configuration, so each entry is added as it stands and nothing merges
    (ADR-094). A gate placed at a legacy stage the copy does not declare is read
    at the path stage that shows it (`removed_parts.with_mapped_stages`).
    The provenance names the layer `legacy` and the operation
    `add` for each entry and field, as the 8.x merge stored them, so a
    generation committed from a copy keeps its stored shape. It moved here from
    `effective` when 9.0.0 stopped reading a copy."""
    mapped, _ = word_map.map_layer(doc)
    for key in mapped:
        if key in spec.SETTINGS_KEYS:
            raise core.CompassError(f"legacy: {key} is a settings key and belongs in the "
                               f"project's own compass.yml, never in a parent (ADR-043)")
    for where, key in _non_text_keys(mapped):
        raise core.CompassError(f"legacy: {where}: {_non_text_key_message(key)} (L-KEY-NOT-TEXT)")
    # A malformed value is refused before anything is added, as 8.x refused it.
    problems = _legacy_value_problems(mapped)
    if problems:
        raise core.CompassError("legacy: " + "; ".join(problems))
    # Two spellings of one check that disagree are refused, as the merge refused them.
    errors = [f"{code} {path}: {message}"
              for code, path, message in word_map.one_check_conflicts(mapped)]
    mapped = removed_parts.with_mapped_stages(mapped, {})
    config, prov = {}, {}
    for catalogue in spec.CATALOGUES:
        if catalogue not in mapped:
            continue
        entries = mapped[catalogue]
        if not isinstance(entries, dict):
            errors.append(f"{catalogue}: expected a mapping keyed by id")
            continue
        table = {}
        for entry_id, entry in entries.items():
            problems = _legacy_entry_problems(catalogue, entry_id, entry)
            if problems:
                errors += problems
                continue
            path = f"{catalogue}.{entry_id}"
            fields = spec.FIELDS[catalogue]
            table[entry_id] = {key: copy.deepcopy(value) for key, value in entry.items()
                               if key in fields}
            prov[path] = {"layer": "legacy", "operation": "add"}
            for key in table[entry_id]:
                prov[f"{path}.{key}"] = {"layer": "legacy", "operation": "add"}
        if table:
            config[catalogue] = table
    if errors:
        raise core.CompassError("legacy: " + "; ".join(errors))
    return config, prov


def _non_text_key_message(key):
    """What YAML read a non-text key as, and how to write it as text."""
    if key is None or isinstance(key, bool):
        kind = "nothing (null)" if key is None else "a boolean"
        example = {True: "on", False: "off", None: "null"}[key]
    else:
        kind = "a number" if isinstance(key, (int, float)) else f"a {type(key).__name__}"
        example = str(key)
    return (f"the key {key!r} is not text: YAML read it as {kind}. "
            f"Quote it, for example \"{example}\":")


def resolved_from_copy(root):
    """The resolved mapping of the project's own copy of the governance files
    at `root`, whatever its `compass.yml` says, with the autonomy `balanced`."""
    legacy = _legacy_parent(os.path.abspath(root))
    if legacy is None:
        raise core.CompassError(f"{root} holds no copy of the governance files")
    doc, meta = legacy
    config, _ = _legacy_config(doc)
    return _resolved(config, dict(doc.get("capabilities") or {}), "balanced",
                     adapt_evidence_types(meta["guardrails"])["evidence_types"])


def _resolved(config, capabilities, autonomy, evidence_types):
    """The mapping a generation's `resolved.yml` holds, from resolved catalogues."""
    return {
        "capabilities": capabilities,
        # An 8.x issue layer could pick an approach and set ceilings, and its
        # stored generation keeps them. With no issue layer the key is always
        # empty; it stays so that a generation committed without a layer keeps
        # the same resolved document, and a reassess commits no new one for it.
        "approach": None,
        "autonomy": autonomy,
        # No lock exists to unlock (ADR-094); the key keeps the stored shape.
        "conformance": {"status": "conformant", "unlocked": []},
        **{name: config[name] for name in spec.CATALOGUES if name in config},
        "evidence_types": evidence_types,
    }
