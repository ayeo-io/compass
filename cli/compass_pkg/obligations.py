# compass_pkg.obligations - what a resolved configuration owes an assessment
"""The routing policy of a resolved configuration, in the shape the evaluator reads.

`evaluate_route` is the one implementation of routing. `policy_adapter` turns
the catalogues of a resolved configuration (the check set, a stored
generation or a governance copy) into the input that function takes:
the reverse of the legacy adapter's `adapt`. `issue_input` hands the evaluator
an 8.x issue's own layer, which a stored generation keeps (ADR-094).
`dimension_orders` and `listing_assessment` give the order a `when:` compares
by and the assessment a check's `when:` reads.

The classifier that compared two configurations by what each owed (ADR-037)
was removed in 9.0.0 with the configuration layers (ADR-094).
"""
# DEPENDENCY: compass_pkg.catalogue_spec (AUTONOMY, ISSUE_KEYS), compass_pkg.core
# (CompassError, canonical_shape), compass_pkg.loop_ceilings (the ceiling names) and
# compass_pkg.stable_ids (the approach ids).
# Only compass_pkg.effective may import this module.
from __future__ import annotations

from compass_pkg.catalogue_spec import AUTONOMY, ISSUE_KEYS
from compass_pkg.stable_ids import (APPROACH_DELIVERY, APPROACH_FULL, APPROACH_HOTFIX, APPROACH_QUICK_FIX,
                                    APPROACH_REGULAR, APPROACH_SPIKE)
from compass_pkg.core import CompassError, canonical_shape
from compass_pkg.loop_ceilings import CEILINGS

# The effect names the evaluator reads, from the catalogue spelling (ADR-041).
# A test holds this equal to the inverse of the table the legacy adapter
# renames by, so the two cannot drift.
_LEGACY_EFFECT = {"force_minimum_approach": "force_minimum_route",
                  "forbid_approach": "forbid_route"}

# The hit policy the evaluator applies to each effect when several rules set
# it, and for an effect not listed. The evaluator does not read a declared
# policy yet, so a rule set that declares another is refused until it does.
BUILT_IN_HIT = {"force_minimum_approach": "max", "lean_toward": "first",
                "max_worktrees": "min", "limit": "min", "tier": "max",
                "effort": "max"}
DEFAULT_HIT = "collect"

# The approaches the evaluator knows, and whether each ships. It names the
# spike as a literal where it adds the gates every shipping approach carries,
# and its checkpoint table accepts only these names, so another approach, or a
# changed `ships`, would be a fact it never reads.
# `delivery` is the shipped default's fallback (ADR-092); the evaluator routes
# to it only to collect the floors, so it is never written as an approach.
EVALUATOR_APPROACHES = {APPROACH_SPIKE: False, APPROACH_QUICK_FIX: True, APPROACH_REGULAR: True,
                        APPROACH_HOTFIX: True, APPROACH_FULL: True, APPROACH_DELIVERY: True}

# Which legacy block a rule set's `kind` fills (`role-rules`: a 6.x generation).
_GUARDRAIL_BLOCKS = {"floors": "floors", "caps": "caps", "ceilings": "loop_ceilings",
                     "immovable-gates": "immovable_gates", "artifact-rules": "artifact_rules",
                     "role-rules": "role_rules"}


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


#: Keys evaluation derives: `ships` for a check's `when` (`listing_assessment`)
#: and `artifacts`, the documents on disk (ADR-070). A dimension of the same name
#: would be overwritten by the derived value, so a configuration may not define one.
DERIVED_KEYS = ("ships", "artifacts")


def assessment_vocabulary(dimensions):
    vocabulary = {}
    for name in [n for n in DERIVED_KEYS if n in dimensions]:
        raise CompassError(f"a dimension cannot be named '{name}': evaluation derives "
                           f"that key from the approach or the documents on disk")
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
                f"({', '.join(EVALUATOR_APPROACHES)}), so it would get "
                f"no approach at all")
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


# --- the verdict of a check with nothing to check -----------------------------------


# --- the facts -------------------------------------------------------------------

def dimension_orders(dimensions):
    return {name: list(d.get("values") or []) for name, d in dimensions.items()
            if d.get("type") == "ordered-enum"}


def listing_assessment(assessment, approach):
    """The assessment a check's `when` and `blocking_when` read: its values
    and one derived key, `ships`, whether the chosen approach ships. A `when`
    reads the assessment only, and an exploration that is not recorded as
    one cannot be told from a delivery by the goal, so a check that a spike
    does not owe says `when: {ships: true}` (the ruling on the spike's
    Definition of Done). `approach` is the catalogue's entry for the approach
    the route chose."""
    return {**assessment, "ships": bool((approach or {}).get("ships", True))}


def _mapping(value, what):
    if not isinstance(value, dict):
        raise CompassError(f"{what} must be a mapping, found {type(value).__name__}")
    return value


def issue_input(config, issue, waived=None):
    """What an issue's own layer hands the evaluator: the approach it names,
    the stage modes it sets, `waived_stages` (from `waived`, else the entries
    that hold a waiver; kept on a floor-raised approach) and its ceiling. The modes
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
    # Whether a waiver is approved is the lint's question (decision 2026-10-17).
    if waived is None:
        waived = [s for s, b in (issue.get("stages") or {}).items()
                  if isinstance(b, dict) and "waiver" in b]
    if any(s in modes for s in waived):
        out["waived_stages"] = sorted(s for s in waived if s in modes)
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


