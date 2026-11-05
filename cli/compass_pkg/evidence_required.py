# compass_pkg.evidence_required - the evidence a change owes before it ships
"""Assess selects the evidence a change owes, not a delivery approach.

`evaluate` is a pure function of the assessment and the configuration in force.
It returns the ordered `evidence_required` list, the gate ids derived from it,
the routing of the four-layer acceptance strategy (`S17`) and the ids of the
rules that fired. The owning doc, `governance/routing-policy.md` ("The evidence
rows"), explains each row and addition.

The rows are fixed in code. A row is picked by the first match; the additions
then apply on top. The configuration adds only what a project can still set
for a new issue: the gates of its floors (`add_gate`) and immovable gates, the
skills its floors ask for (`require_skill`) and its advisory strategies. This
module never reads the configuration's approaches, shapes, stage modes or
caps, so a frozen preset or copied governance that still declares them gives
the same evidence as the live default.

The rows reproduce the gate sets 8.0.4 routed: `tests/test_evidence_required.py`
compares them on every point of the contract 1 grid and every subset of the
`G5` labels.
"""
# DEPENDENCY: compass_pkg.core (CompassError, reading_matches), red_first
# (ACCEPTANCE_KINDS), retired (DIMENSIONS) and routing (RoutingConflict,
# REMOVED_GATES); no standard library module. No module imports this one yet.
from __future__ import annotations

from compass_pkg import retired
from compass_pkg.core import CompassError, reading_matches
from compass_pkg.red_first import ACCEPTANCE_KINDS
from compass_pkg.routing import REMOVED_GATES, RoutingConflict

# The new ids are named here until step 7 of #351 moves this module onto the ids
# of `stable_ids` (`APPROACH_DELIVERY`, `PATH_STAGE_IDS`, `SPIKE_STAGE_IDS`), which
# a parallel change adds. Keep the values equal to those.
APPROACH_DELIVERY = "delivery"
APPROACH_SPIKE = "spike"
PATH_STAGE_IDS = ("assess", "specify", "build", "ship")
SPIKE_STAGE_IDS = ("assess", "build", "ship")

#: The labels of guardrail `G5`, the irreversible surfaces that owe a person's sign-off.
G5_LABELS = ("auth", "payments", "personal-data", "migrations")

#: Every token, in the order the manifest stores them.
TOKENS = ("scenarios", "red-before-green", "suite-green",
          "correctness", "governance", "traceability",
          "regression", "security", "clarity", "architecture",
          "outer-loop", "isolation", "layering",
          "definition-of-done", "reproduce-first", "scenario-approval", "human-approval")

#: The review gate each token is met by. The other tokens are met by records and
#: checks, not by a gate (`governance/routing-policy.md`).
GATE_OF_TOKEN = {"correctness": "verify.correctness", "governance": "verify.governance",
                 "traceability": "verify.traceability", "regression": "verify.regression",
                 "security": "verify.security", "clarity": "verify.clarity",
                 "architecture": "verify.architecture"}
TOKEN_OF_GATE = {gate: token for token, gate in GATE_OF_TOKEN.items()}
SPIKE_GATE = "spike.conclude"

#: What every delivery issue owes.
EVERY_ISSUE = ("scenarios", "red-before-green", "suite-green",
               "correctness", "governance", "traceability")

#: The `S17` tokens, each with the routings that owe it. `outer-loop` is owed
#: wherever the strategy applies.
S17_TOKENS = {"outer-loop": ("existing-dsl", "existing-dsl-isolation", "on"),
              "isolation": ("existing-dsl-isolation", "on"),
              "layering": ("on",)}
STATES = ("on", "off")
EXPECTED = ("none",) + tuple(ACCEPTANCE_KINDS)

_SMALL = {"size": ["atomic", "small"]}
_G5 = {"labels_any": list(G5_LABELS)}

#: The rows, first match wins: `(rule id, when, tokens, routing)`, the routing of `S17`. A row's
#: `when` is read with the extra keys `not` (none of these clauses holds) as well
#: as the keys `reading_matches` reads.
ROWS = (
    ("RP-EVID-SPIKE", {"goal": "exploration"}, (), "suspended"),
    ("RP-EVID-LIGHT",
     dict(_SMALL, risk=["trivial", "contained"], **{"not": [{"urgency": "live-defect"}, _G5]}),
     EVERY_ISSUE, "existing-dsl"),
    ("RP-EVID-DEFECT",
     dict(_SMALL, urgency="live-defect", **{"not": [{"risk": "critical"}, _G5]}),
     EVERY_ISSUE + ("regression", "security", "definition-of-done"),
     "existing-dsl-isolation"),
    ("RP-EVID-STANDARD", {},
     EVERY_ISSUE + ("regression", "security", "clarity", "definition-of-done"), "on"),
)

#: The additions to a delivery row, in order: `(rule id, when, token)`.
#: `RP-REQUIRE-003` and `RP-REQUIRE-004` keep the ids of the 8.x floors that added
#: the architecture review.
ADDITIONS = (
    ("RP-REQUIRE-003", {"risk": ["cross-cutting", "critical"]}, "architecture"),
    ("RP-REQUIRE-004", _G5, "architecture"),
    ("RP-EVID-REPRODUCE", {"urgency": "live-defect"}, "reproduce-first"),
    ("RP-EVID-SIGNOFF", {"any_of": [_G5, {"risk": "critical"}]}, "scenario-approval"),
    ("G5", _G5, "human-approval"),
)

_REQUIRED = ("risk", "familiarity", "size")
_OPTIONAL = ("goal", "urgency")
_VOCABULARY_KEYS = {"blast_radius": "risk", "terrain": "familiarity",
                    "magnitude": "size", "intent": "goal"}


def _matches(when, readings, orders):
    when = dict(when)
    unless = when.pop("not", ())
    return reading_matches(when, readings, orders) and not any(
        reading_matches(clause, readings, orders) for clause in unless)


def _checked(assessment, policy):
    """The assessment with the retired dimensions taken out, or `CompassError`
    naming each reading that is missing or outside the configuration's vocabulary."""
    vocab = {_VOCABULARY_KEYS.get(k, k): v for k, v in (
        policy.get("assessment_vocabulary") or policy.get("reading_vocabulary") or {}).items()}
    readings = {k: v for k, v in (assessment or {}).items() if k not in retired.DIMENSIONS}
    errors = [f"missing required reading: {dim}" for dim in _REQUIRED if dim not in readings]
    for dim in _REQUIRED + _OPTIONAL:
        if dim in readings and dim in vocab and readings[dim] not in vocab[dim]:
            errors.append(f"reading {dim}={readings[dim]!r} is not in the vocabulary "
                          f"{vocab[dim]}")
    if errors:
        raise CompassError("invalid assessment:\n  - " + "\n  - ".join(errors))
    return readings


def _refuse_exploration(readings, orders):
    """A spike ships nothing, so it must not touch a surface that owes a person's
    sign-off. 8.x refused the same assessments, where its floors would have raised
    the spike to a delivery approach; turning one into the other is a choice a
    person makes by re-assessing (`approaches/spike.md`)."""
    if _matches({"any_of": [_G5, {"risk": "critical"}]}, readings, orders):
        raise RoutingConflict(
            "routing conflict - exploration cannot silently become delivery.\n"
            "  Intent is 'exploration' (a spike), but the assessment names critical "
            "risk or a G5 label, where a change owes a person's sign-off.\n"
            "  A spike ships nothing and must not touch production-critical surface.\n"
            "  Re-assess: either scope a narrower discovery issue that does not touch "
            "the risky surface, or set intent=delivery and accept the evidence that "
            "change owes.")


def evaluate(assessment, policy, acceptance_state="on", expected_acceptance="none"):
    """The evidence an assessment owes under `policy`, the configuration in force
    in the shape `routing.evaluate_route` takes.

    `acceptance_state` is the project's `acceptance_strategy` setting and
    `expected_acceptance` what assess was told (`--expected-acceptance`); either
    can leave out the `S17` tokens, as `acceptance_strategy.block` decides.

    Returns a mapping with `delivery_approach`, `stages`, `evidence_required`,
    `gates`, `acceptance_routing`, `acceptance_applies`, `rules_fired`,
    `required_skills` and `applicable_strategies`. Raises `RoutingConflict` for
    exploration on a surface that owes a sign-off, and `CompassError` for an
    assessment or setting it cannot read."""
    if acceptance_state not in STATES:
        raise CompassError(f"acceptance_state {acceptance_state!r} is not one of {STATES}")
    if expected_acceptance not in EXPECTED:
        raise CompassError(f"expected_acceptance {expected_acceptance!r} is not one of "
                           f"{EXPECTED}")
    readings = _checked(assessment, policy)
    orders = policy.get("dimension_orders")
    guard = policy.get("routing_guardrails") or {}

    rule, _, row_tokens, routing = next(
        r for r in ROWS if _matches(r[1], readings, orders))
    spike = rule == "RP-EVID-SPIKE"
    if spike:
        _refuse_exploration(readings, orders)
    fired = [rule]
    owed = set(row_tokens)
    extra_gates = []

    if not spike:
        for rule_id, when, token in ADDITIONS:
            if _matches(when, readings, orders):
                owed.add(token)
                fired.append(rule_id)
        # A gate the configuration names that a token stands for joins as that
        # token, so `gates` stays derived from `evidence_required`. Any other gate
        # is kept as it is. A removed gate is owed by nothing (`routing.REMOVED_GATES`).
        # The immovable gates are recorded as no rule that fired, as in 8.x;
        # a floor that adds a gate is.
        named = [(None, ig.get("gate")) for ig in guard.get("immovable_gates") or []]
        named += [(fl.get("id"), fl.get("add_gate")) for fl in guard.get("floors") or []
                  if fl.get("add_gate") and reading_matches(fl.get("when"), readings, orders)]
        for rule_id, gate in named:
            if not gate or gate in REMOVED_GATES:
                continue
            if gate in TOKEN_OF_GATE:
                owed.add(TOKEN_OF_GATE[gate])
            elif gate not in extra_gates:
                extra_gates.append(gate)
            if rule_id and rule_id not in fired:
                fired.append(rule_id)

    applies = (not spike and acceptance_state == "on"
               and expected_acceptance not in ACCEPTANCE_KINDS)
    if applies:
        owed.update(t for t, routings in S17_TOKENS.items() if routing in routings)

    skills = []
    for fl in guard.get("floors") or []:
        if fl.get("require_skill") and reading_matches(fl.get("when"), readings, orders):
            if fl["require_skill"] not in skills:
                skills.append(fl["require_skill"])
            if fl.get("id") and fl["id"] not in fired:
                fired.append(fl["id"])
    strategies = [{"id": adv.get("id", "?"), "strategy": adv.get("strategy", ""),
                   "rationale": adv.get("rationale", "")}
                  for adv in (policy.get("routing_strategies") or {}).get(
                      "advisory_strategies") or []
                  if reading_matches(adv.get("when"), readings, orders)]

    evidence = [t for t in TOKENS if t in owed]
    gates = ([SPIKE_GATE] if spike
             else [GATE_OF_TOKEN[t] for t in evidence if t in GATE_OF_TOKEN] + extra_gates)
    return {
        "delivery_approach": APPROACH_SPIKE if spike else APPROACH_DELIVERY,
        "stages": SPIKE_STAGE_IDS if spike else PATH_STAGE_IDS,
        "evidence_required": evidence,
        "gates": gates,
        "acceptance_routing": routing,
        "acceptance_applies": applies,
        "rules_fired": fired,
        "required_skills": sorted(skills),
        "applicable_strategies": strategies,
    }
