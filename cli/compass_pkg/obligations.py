# compass_pkg.obligations - what a resolved configuration owes an assessment
"""The facts a configuration owes an assessment, computed by today's evaluator.

The classifier compares two configurations by what each owes at an
assessment (ADR-037). This module computes those facts for one
configuration and one assessment. It does not route: `evaluate_route` is the
one implementation of routing, and `policy_adapter` turns the merged
catalogues into the input that function already takes, so a replay can show
the two paths agree. When the evaluator takes the catalogue form itself the
adapter becomes the identity.

An assessment the evaluator refuses (an exploration that a floor would turn
into delivery, or a forbidden approach) is an outcome at that point, not a
failure of the comparison, so it comes back as `Refused`. A fault in the
configuration itself (an issue naming a mode its stage does not have) is a
different thing and raises.
"""
# DEPENDENCY: standard library (copy, dataclasses); compass_pkg.catalogue_spec,
# compass_pkg.core (CompassError, reading_matches, canonical_shape,
# _stage_key_renames),
# compass_pkg.loop_ceilings (the ceiling names) and compass_pkg.routing
# (evaluate_route, RoutingConflict, prepare_policy, route_checkpoints), and
# compass_pkg.stable_ids (the approach ids).
# Only compass_pkg.classify, compass_pkg.effective and compass_pkg.replay import this module.
from __future__ import annotations

import copy
from dataclasses import dataclass, fields

from compass_pkg.catalogue_spec import AUTONOMY, CAPABILITIES, ISSUE_KEYS
from compass_pkg.stable_ids import APPROACH_FULL, APPROACH_HOTFIX, APPROACH_QUICK_FIX, APPROACH_REGULAR, APPROACH_SPIKE
from compass_pkg.core import (CompassError, _stage_key_renames, canonical_shape,
                              reading_matches)
from compass_pkg.loop_ceilings import CEILINGS
from compass_pkg.routing import (RoutingConflict, evaluate_route, prepare_policy,
                                 route_checkpoints)

# The effect names the evaluator reads, from the catalogue spelling (ADR-041).
# A test holds this equal to the inverse of the table the legacy adapter
# renames by, so the two cannot drift.
_LEGACY_EFFECT = {"force_minimum_approach": "force_minimum_route",
                  "forbid_approach": "forbid_route"}

# The hit policy the evaluator applies to each effect when several rules set
# it, and for an effect not listed. The evaluator does not read a declared
# policy yet, so a rule set that declares another is refused until it does.
BUILT_IN_HIT = {"force_minimum_approach": "max", "lean_toward": "first",
                "max_worktrees": "min", "limit": "min"}
DEFAULT_HIT = "collect"

# The approaches the evaluator knows, and whether each ships. It names the
# spike as a literal where it adds the gates every shipping approach carries,
# and its checkpoint table accepts only these names, so another approach, or a
# changed `ships`, would be a fact it never reads.
EVALUATOR_APPROACHES = {APPROACH_SPIKE: False, APPROACH_QUICK_FIX: True, APPROACH_REGULAR: True,
                        APPROACH_HOTFIX: True, APPROACH_FULL: True}

# Which legacy block a rule set's `kind` fills.
_GUARDRAIL_BLOCKS = {"floors": "floors", "caps": "caps", "ceilings": "loop_ceilings",
                     "immovable-gates": "immovable_gates", "role-rules": "role_rules"}


def _ordered(rule_set):
    rules = (rule_set or {}).get("rules") or {}
    return sorted(rules.items(), key=lambda item: item[1].get("order", 0))


def _legacy_rule(rule_id, rule):
    """One rule in the shape the evaluator reads: its effects at the top
    level, under the names the evaluator knows."""
    out = {"id": rule_id}
    if "when" in rule:
        out["when"] = rule["when"]
    for effect, value in (rule.get("then") or {}).items():
        out[_LEGACY_EFFECT.get(effect, effect)] = value
    if "rationale" in rule:
        out["rationale"] = rule["rationale"]
    return out


def _resolved_approach(approaches, name, seen=()):
    """An approach with the fields of the one it extends filled in, nearest
    first. A cycle is a fault in the configuration."""
    if name in seen:
        raise CompassError("approaches extend each other in a cycle: "
                           + " -> ".join((*seen, name)))
    entry = approaches[name]
    parent = entry.get("extends")
    if not parent:
        return dict(entry)
    if parent not in approaches:
        raise CompassError(f"approach '{name}' extends '{parent}', which is not defined")
    merged = _resolved_approach(approaches, parent, (*seen, name))
    merged.update(entry)
    return merged


#: Keys that evaluation derives for a check's `when` (`listing_assessment`).
#: A dimension of the same name would be overwritten by the derived value, so
#: a configuration may not define one.
DERIVED_KEYS = ("ships",)


def assessment_vocabulary(dimensions):
    vocabulary = {}
    for name in DERIVED_KEYS:
        if name in dimensions:
            raise CompassError(
                f"a dimension cannot be named '{name}': evaluation derives that "
                f"key for a check's `when` from the approach")
    for name, dimension in dimensions.items():
        if dimension.get("type") in ("enum", "ordered-enum"):
            vocabulary[name] = list(dimension.get("values") or [])
        elif name == "labels" and dimension.get("common"):
            vocabulary["labels_common"] = list(dimension["common"])
    return vocabulary


def _shapes(approaches):
    shapes = {}
    for name in approaches:
        entry = _resolved_approach(approaches, name)
        if name not in EVALUATOR_APPROACHES:
            raise CompassError(
                f"approach '{name}' is not one the evaluator knows "
                f"({', '.join(EVALUATOR_APPROACHES)}), so it would be routed "
                f"as no approach at all")
        if entry.get("ships", EVALUATOR_APPROACHES[name]) != EVALUATOR_APPROACHES[name]:
            raise CompassError(
                f"approach '{name}' sets ships to {entry['ships']!r}, but the "
                f"evaluator treats it as "
                f"{'shipping' if EVALUATOR_APPROACHES[name] else 'not shipping'}")
        shapes[name] = {
            "weight": entry["weight"],
            "stages": dict(entry.get("stages") or {}),
            "gates": list(entry.get("gates") or []),
            "artifacts": dict(entry.get("artifacts") or {}),
            "subtask_ceiling": entry.get("subtask_ceiling", 1),
        }
    return shapes


def _checkpoints(approaches):
    table = {}
    for name, entry in approaches.items():
        for level, stages in (entry.get("checkpoints") or {}).items():
            table.setdefault(level, {})[name] = list(stages)
    return table


def _ranks(stages):
    ranks = {stage: {mode: body["rank"] for mode, body in (entry.get("modes") or {}).items()
                     if "rank" in (body or {})}
             for stage, entry in stages.items()}
    return ranks if any(ranks.values()) else None


def _strategies(rules):
    """`routing_strategies` from the shape, advisory and bias rule sets. An
    advisory rule that carries a `strategy` is an advisory strategy; the
    others suggest an artifact, which the evaluator does not read."""
    shapes, advisory, defaults, biases = [], [], [], []
    for rule_set in rules.values():
        kind = rule_set.get("kind")
        for rule_id, rule in _ordered(rule_set):
            if kind == "shapes":
                shapes.append(_legacy_rule(rule_id, rule))
            elif kind == "advisory":
                legacy = _legacy_rule(rule_id, rule)
                (advisory if "strategy" in legacy else defaults).append(legacy)
            elif kind == "biases":
                biases.append(rule.get("rationale", ""))
    strategies = {"default_shapes": shapes, "advisory_strategies": advisory,
                  "role_defaults": defaults, "biases": biases}
    # A last shape that matches every assessment is the fallback approach.
    if shapes and not shapes[-1].get("when"):
        strategies["default_route"] = shapes.pop()["lean_toward"]
    return strategies


def _guardrails(rules):
    blocks = {block: [] for block in _GUARDRAIL_BLOCKS.values()}
    for rule_set in rules.values():
        block = _GUARDRAIL_BLOCKS.get(rule_set.get("kind"))
        if block:
            blocks[block] += [_legacy_rule(i, r) for i, r in _ordered(rule_set)]
    return blocks


def _check_hit_policies(rules):
    """The evaluator applies one hit policy to each effect. A rule set that
    declares another would be read as if it had not, so it is refused."""
    for set_name, rule_set in rules.items():
        for effect, declared in ((rule_set or {}).get("hit") or {}).items():
            built_in = BUILT_IN_HIT.get(effect, DEFAULT_HIT)
            if declared != built_in:
                raise CompassError(
                    f"rule set '{set_name}' declares the hit policy '{declared}' "
                    f"for '{effect}', but the evaluator applies '{built_in}' and "
                    f"does not read a declared one yet")


def policy_adapter(config):
    """The routing policy, in the shape `evaluate_route` takes, of a resolved
    configuration: the reverse of the legacy adapter's `adapt`. Hit policies are
    not read, and one that differs from the evaluator's own is refused."""
    _check_hit_policies(config.get("rules") or {})
    policy = {
        "assessment_vocabulary": assessment_vocabulary(config.get("dimensions") or {}),
        "route_shapes": _shapes(config.get("approaches") or {}),
        "routing_strategies": _strategies(config.get("rules") or {}),
        "routing_guardrails": _guardrails(config.get("rules") or {}),
    }
    table = _checkpoints(config.get("approaches") or {})
    if table:
        policy["autonomy_checkpoints"] = table
    ranks = _ranks(config.get("stages") or {})
    if ranks is not None:
        policy["stage_mode_ranks"] = ranks
    orders = dimension_orders(config.get("dimensions") or {})
    if orders:
        policy["dimension_orders"] = orders
    return policy


# --- the result ------------------------------------------------------------------

@dataclass(frozen=True)
class Refused:
    """The evaluator refused this assessment with a routing conflict.
    `reason` is its message. Any other evaluator error is a fault in an
    input and raises."""
    reason: str


@dataclass(frozen=True)
class Obligations:
    """What a configuration owes an assessment. The first fifteen fields are
    the facts the classifier compares; `approach`, `rules_fired` and
    `ignored_overrides` are outcomes, which are not obligations (a different
    approach that owes the same is equivalent)."""
    stage_mode: dict
    entry: dict
    exit: dict
    gate_set: tuple
    gate_checks: dict
    gate_accepts: dict
    artifacts_owed: dict
    required_skills: tuple
    blocked_stages: tuple
    required_artifacts: tuple
    checkpoints: dict
    ceilings: dict
    checks: dict
    artifact_depends_on: dict
    artifact_checks: dict
    approach: str = ""
    rules_fired: tuple = ()
    ignored_overrides: dict = None   # the issue's stage modes a floor replaced

    def compared(self):
        return {f.name: getattr(self, f.name) for f in fields(self)
                if f.name in COMPARED_FACTS}


# Which fact carries each key of `catalogue_spec.OBLIGATION_FIELDS` that an
# evaluation produces. A key that is not here is in FOOTPRINT_ONLY: a lock
# reads it from the configuration, and no assessment changes it.
FACT_FOR_FIELD = {
    "approaches.stages": "stage_mode",
    "stages.mode": "stage_mode",
    "approaches.gates": "gate_set",
    "approaches.artifacts": "artifacts_owed",
    "approaches.artifacts.depth": "artifacts_owed",
    "approaches.checkpoints": "checkpoints",
    "approaches.subtask_ceiling": "ceilings",
    "rules.ceilings": "ceilings",
    "evaluation.max_worktrees": "ceilings",
    "stages.entry": "entry",
    "stages.exit": "exit",
    "gates.checks": "gate_checks",
    "gates.accepts": "gate_accepts",
    "checks.kind": "checks",
    "checks.impl": "checks",
    "checks.params": "checks",
    "checks.accepts": "checks",
    "checks.reviewers": "checks",
    "checks.approvers": "checks",
    "checks.inputs": "checks",
    "checks.severity": "checks",
    "checks.on_skipped": "checks",
    "checks.statement": "checks",
    "artifacts.depends_on": "artifact_depends_on",
    "artifacts.checks": "artifact_checks",
    "evaluation.required_skills": "required_skills",
    "evaluation.blocked_stages": "blocked_stages",
    "evaluation.required_artifacts": "required_artifacts",
}
FOOTPRINT_ONLY = ("approaches.ships", "stages.order", "gates.stage")
COMPARED_FACTS = frozenset(FACT_FOR_FIELD.values())

# `statement` is compared for a check a person or a model judges: its text is
# the instruction. For a deterministic check the implementation is.
STATEMENT_KINDS = ("human", "judged")


# --- the verdict of a check with nothing to check -----------------------------------

# What `compass check` reports for a check, from what the preset's
# `on_skipped` says of one that cannot run. `not-applicable` is today's
# `nothing-to-check`: the check inspected nothing, so it neither passed nor
# failed anything.
SKIPPED_STATUS = {"pass": "pass", "not-applicable": "nothing-to-check", "fail": "fail"}


def skipped_verdict(check):
    """The verdict, as `compass check --json` spells it, that the obligation
    path gives a check with nothing to check."""
    value = check.get("on_skipped")
    if value not in SKIPPED_STATUS:
        raise CompassError(f"on_skipped is '{value}'; it must be one of "
                           f"{', '.join(SKIPPED_STATUS)}")
    return SKIPPED_STATUS[value]


# --- the facts -------------------------------------------------------------------

def dimension_orders(dimensions):
    return {name: list(d.get("values") or []) for name, d in dimensions.items()
            if d.get("type") == "ordered-enum"}


def _known_capabilities(names, who):
    """A misspelt switch would turn nothing on and nobody would be told."""
    for name in names:
        if name not in CAPABILITIES:
            raise CompassError(f"{who} the capability '{name}', which is not one of "
                               f"{', '.join(CAPABILITIES)}")


def listing_assessment(assessment, approach):
    """The assessment a check's `when` and `blocking_when` read: its values
    and one derived key, `ships`, whether the chosen approach ships. A `when`
    reads the assessment only, and an exploration that is not recorded as
    one cannot be told from a delivery by the goal, so a check that a spike
    does not owe says `when: {ships: true}` (the ruling on the spike's
    Definition of Done). `approach` is the catalogue's entry for the approach
    the route chose."""
    return {**assessment, "ships": bool((approach or {}).get("ships", True))}


def _active(check, assessment, orders, capabilities):
    """A check is active when its `when` matches and every capability it
    needs is on."""
    _known_capabilities(check.get("requires") or (), "a check requires")
    return (reading_matches(check.get("when"), assessment, orders)
            and set(check.get("requires") or ()) <= set(capabilities))


def _active_ids(ids, checks, assessment, orders, capabilities):
    out = []
    for check_id in ids:
        if check_id not in checks:
            raise CompassError(f"a list names the check '{check_id}', which the "
                               f"configuration does not define")
        if _active(checks[check_id], assessment, orders, capabilities):
            out.append(check_id)
    return tuple(sorted(out))


def _check_facts(check, assessment, orders):
    """The fields of an active check that two configurations are compared on.
    The severity is the one in force at this assessment: a `blocking_when`
    that does not match makes a finding advisory, as `compass check` reads
    it. It reads the configured orders, as every other clause does."""
    severity = check.get("severity", "blocking")
    blocking_when = check.get("blocking_when")
    if blocking_when and not reading_matches(blocking_when, assessment, orders):
        severity = "advisory"
    facts = {
        "kind": check.get("kind"), "impl": check.get("impl"),
        "params": copy.deepcopy(check.get("params") or {}),
        "accepts": sorted(check.get("accepts") or []),
        "reviewers": sorted(check.get("reviewers") or []),
        "approvers": sorted(check.get("approvers") or []),
        "inputs": sorted(check.get("inputs") or []),
        "severity": severity, "on_skipped": check.get("on_skipped"),
    }
    if check.get("kind") in STATEMENT_KINDS:
        facts["statement"] = check.get("statement")
    return facts


def _guardrail_gates(gates, ships, assessment, orders):
    """The guardrail gates in force: those that apply to an approach that
    ships (or not), and whose own condition matches."""
    out = []
    for gate_id, gate in gates.items():
        if gate.get("kind") != "guardrail":
            continue
        applies = gate.get("applies_to") or {}
        if "ships" in applies and applies["ships"] != ships:
            continue
        if reading_matches(gate.get("when"), assessment, orders):
            out.append(gate_id)
    return out


def _loop_ceilings(rules, assessment, orders):
    """For each loop ceiling the lowest limit among the matching rules, so a
    rule can only lower one (the reading `loop_ceilings.loop_ceilings` gives
    the policy file)."""
    found = {}
    for rule_set in rules.values():
        if rule_set.get("kind") != "ceilings":
            continue
        for _, rule in _ordered(rule_set):
            then = rule.get("then") or {}
            name, limit = then.get("ceiling"), then.get("limit")
            if (name not in CEILINGS or not isinstance(limit, int)
                    or isinstance(limit, bool) or limit < 1):
                continue
            if reading_matches(rule.get("when"), assessment, orders):
                found[name] = min(limit, found.get(name, limit))
    return found


def _artifact_id(value):
    value = str(value)
    return value[:-3] if value.endswith(".md") else value


def _mapping(value, what):
    if not isinstance(value, dict):
        raise CompassError(f"{what} must be a mapping, found {type(value).__name__}")
    return value


def issue_input(config, issue):
    """What an issue's own layer hands the evaluator: the approach it names,
    the stage modes it sets and the subtask ceiling it sets. The stage modes
    are read from the resolved `config` (the merge writes an issue's `mode`
    into its stage); the approach and the ceilings are not catalogue entries,
    so they come from `issue`, the layer's own document. A key the issue layer
    does not allow, a mode, approach or ceiling that does not exist, and a
    layer of the wrong shape are faults in the layer and raise.

    The issue's `autonomy` is allowed and changes no fact: the caller picks
    its row of `checkpoints`."""
    issue = _mapping({} if issue is None else issue, "the issue's layer")
    for key in issue:
        if key not in ISSUE_KEYS:
            raise CompassError(f"the issue's layer holds the key '{key}', which is "
                               f"not one of {', '.join(ISSUE_KEYS)}")
    for key in ("stages", "checks", "gates", "rules"):
        if key in issue:
            _mapping(issue[key], f"the issue's {key}")
    if "autonomy" in issue and issue["autonomy"] not in AUTONOMY:
        raise CompassError(f"the issue's autonomy is '{issue['autonomy']}'; it must "
                           f"be one of {', '.join(AUTONOMY)}")
    out = {}
    approach = issue.get("approach")
    if approach:
        if not isinstance(approach, str):
            raise CompassError("the issue's approach must be a name, found "
                               f"{type(approach).__name__}")
        # An older name is read as the current one, as the evaluator does.
        current = canonical_shape(approach)
        if current not in (config.get("approaches") or {}):
            raise CompassError(f"the issue names the approach '{approach}', which "
                               f"the configuration does not define")
        out["approach"] = current
    modes = {}
    for stage, body in (config.get("stages") or {}).items():
        if "mode" in body:
            if body["mode"] not in (body.get("modes") or {}):
                raise CompassError(f"the issue sets stage '{stage}' to mode "
                                   f"'{body['mode']}', which the stage does not have")
            modes[stage] = body["mode"]
    if modes:
        out["stage_modes"] = modes
    ceilings = _mapping(issue.get("ceilings") or {}, "the issue's ceilings")
    for name, limit in ceilings.items():
        if name not in (*CEILINGS, "subtask_ceiling"):
            raise CompassError(f"the issue sets the ceiling '{name}', which is not one "
                               f"of {', '.join((*CEILINGS, 'subtask_ceiling'))}")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise CompassError(f"the issue sets the ceiling '{name}' to {limit!r}; "
                               f"a ceiling is a whole number of at least 1")
    if "subtask_ceiling" in ceilings:
        out["subtask_ceiling"] = ceilings["subtask_ceiling"]
    return out


class Preparation:
    """What `obligations` builds from a configuration and an issue layer and
    would otherwise build again for every assessment: the adapted policy,
    prepared for the evaluator, and the issue's input. A caller that asks about
    one configuration at many assessments passes one `Preparation` for it. It
    fills itself on the first call, so a fault in the configuration surfaces at
    the same point as without one, and it is built again for a configuration or
    an issue it was not made from."""

    def __init__(self):
        self._made_from = None
        self._built = None

    def get(self, config, issue):
        if self._made_from is None or (self._made_from[0] is not config
                                       or self._made_from[1] is not issue):
            built = (prepare_policy(policy_adapter(config)), issue_input(config, issue))
            self._made_from, self._built = (config, issue), built
        return self._built


def obligations(config, assessment, autonomy_values=AUTONOMY, capabilities=(),
                issue=None, preparation=None):
    """`Obligations`, or `Refused` when the evaluator refuses the assessment.
    `capabilities` names the switches that are on, and `issue` is the issue's
    own layer, applied before the floors, caps and role rules (`issue_input`).
    The evaluator runs once, because only the checkpoints depend on the
    autonomy value, and the rest are read from the same route."""
    _known_capabilities(capabilities, "obligations were asked for")
    policy, evaluator_issue = (preparation or Preparation()).get(config, issue)
    values = tuple(autonomy_values) or ("balanced",)
    try:
        result = evaluate_route(copy.deepcopy(assessment), policy,
                                autonomy=values[0], issue=evaluator_issue)
    except RoutingConflict as exc:
        return Refused(str(exc))
    results = {values[0]: result}
    for value in values[1:]:
        results[value] = {"checkpoints": route_checkpoints(
            policy, result["stages"], result["delivery_approach"], value)}
    dimensions = config.get("dimensions") or {}
    orders = dimension_orders(dimensions)
    checks, gates = config.get("checks") or {}, config.get("gates") or {}
    approach = (config.get("approaches") or {}).get(result["delivery_approach"]) or {}
    review = list(result["gates"])
    in_force = sorted(set(review) | set(_guardrail_gates(
        gates, approach.get("ships", True), assessment, orders)))
    # What a check's `when` reads: the assessment and whether the route ships.
    reading = listing_assessment(assessment, approach)

    entry, exit_ = {}, {}
    for stage, body in (config.get("stages") or {}).items():
        entry[stage] = _active_ids(body.get("entry") or [], checks, reading,
                                   orders, capabilities)
        exit_[stage] = _active_ids(body.get("exit") or [], checks, reading,
                                   orders, capabilities)
    gate_checks = {g: _active_ids((gates.get(g) or {}).get("checks") or [], checks,
                                  reading, orders, capabilities)
                   for g in in_force}
    gate_accepts = {g: tuple(sorted((gates.get(g) or {}).get("accepts") or []))
                    for g in in_force}
    artifacts = {a["kind"]: a["depth"] for a in result["artifacts"]}
    listed = set()
    for ids in (*entry.values(), *exit_.values(), *gate_checks.values()):
        listed.update(ids)
    catalogue = config.get("artifacts") or {}
    artifact_checks = {kind: _active_ids((catalogue.get(kind) or {}).get("checks") or [],
                                         checks, reading, orders, capabilities)
                       for kind in artifacts}
    artifact_depends_on = {kind: tuple(sorted((catalogue.get(kind) or {})
                                              .get("depends_on") or []))
                           for kind in artifacts}
    for ids in artifact_checks.values():
        listed.update(ids)
    renames = _stage_key_renames()
    ceilings = {"subtask_ceiling": result["subtask_ceiling"],
                "max_worktrees": result["max_worktrees"],
                **_loop_ceilings(config.get("rules") or {}, assessment, orders)}
    # An issue can lower a loop ceiling and never raise it: the rules that
    # set one are caps, and caps apply after the issue layer.
    for name, limit in (issue or {}).get("ceilings", {}).items():
        if name != "subtask_ceiling":
            ceilings[name] = min(limit, ceilings.get(name, limit))
    return Obligations(
        stage_mode=dict(result["stages"]),
        entry=entry, exit=exit_,
        gate_set=tuple(in_force),
        gate_checks=gate_checks, gate_accepts=gate_accepts,
        artifacts_owed=artifacts,
        required_skills=tuple(sorted(result["required_skills"])),
        blocked_stages=tuple(sorted({renames.get(b["phase"], b["phase"])
                                     for b in result["blocked_phases"]})),
        required_artifacts=tuple(sorted(_artifact_id(a)
                                        for a in result["required_artifacts"])),
        checkpoints={v: tuple(r["checkpoints"]) for v, r in results.items()},
        ceilings=ceilings,
        checks={c: _check_facts(checks[c], reading, orders) for c in sorted(listed)},
        artifact_depends_on=artifact_depends_on, artifact_checks=artifact_checks,
        approach=result["delivery_approach"],
        rules_fired=tuple(f["id"] for f in result["policy_rules_fired"]),
        ignored_overrides=dict((result.get("issue_overrides") or {}).get("ignored")
                               or {}),
    )
