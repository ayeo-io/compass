# compass_pkg.approach_blocks - the rendered blocks of the delivery-approach record
"""Pure renderers for the four blocks of `delivery-approach.md` (ADR-055, DD-10).

- `assessment`: a row per assessed dimension with its value and the justification the
  manifest records, then the labels;
- `policy-rules`: the policy line, the generation and a row per rule that fired;
- `stage-weights`: a row per stage, in stage order, with the mode the manifest records;
- `gate-set`: the gates in the manifest's order, and beside an added gate the rules that
  added it.

Each takes a `RenderInputs` snapshot and the project-relative path of the document, and
returns a `Part`, as the renderers in `block_renderers` do. `block_renderers` registers
them through `_add_modules`. They read only the manifest and the configuration view.
"""
# DEPENDENCY: compass_pkg.render_inputs, rendered_blocks, stable_ids; compass_pkg.routing and
# compass_pkg.justifications are imported inside the renderers that use them, because routing
# imports modules that import the renderers.
from __future__ import annotations

from compass_pkg import rendered_blocks as rb
from compass_pkg.render_inputs import OWN, Part, code as _code
from compass_pkg.stable_ids import STAGE_IDS

#: Shown for a dimension the manifest holds no justification for: an issue assessed
#: before the manifest kept them.
NO_JUSTIFICATION = "no justification recorded"


def _dimension_order(view, assessed):
    from compass_pkg import justifications
    ordered = [name for name in justifications.justified_dimensions(view) if name in assessed]
    rest = sorted(k for k, v in assessed.items()
                  if k not in ordered and k != "labels" and not isinstance(v, (list, dict)))
    return ordered + rest


def assessment(inputs, doc_rel):
    assessed = inputs.task.get("assessment")
    assessed = assessed if isinstance(assessed, dict) else {}
    if not assessed:
        return Part(OWN, ["No assessment recorded yet."])
    reasons = inputs.task.get("justifications")
    reasons = reasons if isinstance(reasons, dict) else {}
    lines = ["| Dimension | Value | Justification |", "|---|---|---|"]
    for name in _dimension_order(inputs.get_view(), assessed):
        if assessed.get(name) in (None, ""):
            continue
        reason = str(reasons.get(name) or "").strip() or NO_JUSTIFICATION
        lines.append("| %s | %s | %s |" % (rb.cell(name.capitalize()), rb.cell(assessed[name]),
                                           rb.cell(reason)))
    labels = assessed.get("labels")
    labels = [str(x) for x in labels] if isinstance(labels, list) else []
    lines += ["", "Labels: %s" % (rb.field(", ".join(labels)) if labels else "none")]
    return Part(OWN, lines)


def policy_rules(inputs, doc_rel):
    from compass_pkg import routing
    generation = inputs.task.get("generation")
    lines = ["Policy: %s" % rb.field(routing.policy_line(inputs.get_view())),
             "Generation: %s" % (rb.field(generation) if generation
                                 else "0 - not stored yet"), ""]
    fired = [f for f in inputs.list_of("policy_rules_fired")]
    if not fired:
        return Part(OWN, lines + ["No policy rule fired."])
    lines += ["| Type | Rule | What it changed | Rationale |", "|---|---|---|---|"]
    for rule in fired:
        changed = "; ".join(str(c) for c in rule.get("changed") or []) or "nothing recorded"
        lines.append("| %s | %s | %s | %s |" % (
            rb.cell(rule.get("kind") or "rule"), rb.cell(rule.get("id", "?")),
            rb.cell(changed), rb.cell(str(rule.get("rationale") or "").strip()
                                      or "no rationale recorded")))
    return Part(OWN, lines)


def stage_weights(inputs, doc_rel):
    stages = inputs.task.get("stages")
    if not isinstance(stages, dict) or not stages:
        return Part(OWN, ["No stage weights recorded yet."])
    order = [s for s in STAGE_IDS if s in stages] + [s for s in stages if s not in STAGE_IDS]
    lines = ["| Stage | Weight |", "|---|---|"]
    lines += ["| %s | %s |" % (rb.cell(s), rb.cell(stages[s])) for s in order]
    return Part(OWN, lines)


def gate_set(inputs, doc_rel):
    from compass_pkg import routing
    gates = inputs.list_of("gates")
    if not gates:
        return Part(OWN, ["No gates recorded yet."])
    added = routing.gates_added_by(inputs.list_of("policy_rules_fired"))
    lines = ["Gates: %d" % len(gates), ""]
    for gate in gates:
        gate_id = str(gate.get("id", "?"))
        line = "- %s" % _code(gate_id)
        if added.get(gate_id):
            line += " - added by %s" % rb.field(", ".join(added[gate_id]))
        lines.append(line)
    return Part(OWN, lines)


RENDERERS = {
    "assessment": assessment,
    "policy-rules": policy_rules,
    "stage-weights": stage_weights,
    "gate-set": gate_set,
}
