# compass_pkg.path_writer - what `approach evaluate --write` writes on the four-stage path
"""The keys a delivery issue's manifest holds on the four-stage path (ADR-092).

`routing.cmd_route_evaluate` calls this module for every assessment. It
turns the result of `evidence_required.evaluate` into the manifest keys: the
`evidence_required` list, the `gates` derived from it (pending), the
`acceptance_strategy` block in the shape ADR-079 set, the `checkpoints` list
and `policy_rules_fired`. A path manifest holds no `stages:`,
`subtask_ceiling:`, `max_worktrees:` or `orchestration:` key.

A spike is not on the path: `evaluate` returns None for it, and the caller
writes the spike keys as it did before, with no `evidence_required` key, so no
reader takes the spike for a path issue (`path_stages.is_path_issue`).

`criteria_text` is the `acceptance-criteria.md` that `compass quick-fix start`
writes for a path issue in place of the devlog. The owning doc is
`governance/routing-policy.md` ("The path writer").
"""
# DEPENDENCY: standard library (os, re); compass_pkg.stable_ids; and inside
# functions acceptance_strategy, evidence_required, project_settings, routing and
# section_checks, because `routing` imports this module and `evidence_required`
# imports `routing`.
from __future__ import annotations

import os
import re

from compass_pkg.stable_ids import (APPROACH_SPIKE, GATE_G5, STAGE_ASSESS, STAGE_BUILD,
                                    STAGE_SHIP, STAGE_SPECIFY)

#: The keys only an issue assessed before the path holds.
LEGACY_ONLY = ("stages", "subtask_ceiling", "max_worktrees", "orchestration")
#: The keys of `LEGACY_ONLY` that no new assessment writes, the spike's included
#: (ADR-092 decision 11). A spike keeps only its stage map.
NOT_WRITTEN = ("subtask_ceiling", "max_worktrees", "orchestration")
#: The fields of the 8.x evaluator's result that a path issue has no use for: the
#: candidate approach the shapes picked, and the stages a document rule blocked.
#: The path has no candidate approach and no stage a rule can block.
NOT_SHOWN = ("candidate_route", "candidate_via", "blocked_phases")

#: What each rule that `evidence_required` fires means, for the manifest's
#: `policy_rules_fired` list and the screens that print it. A rule of the
#: configuration (a floor) keeps the entry the evaluator wrote for it.
RATIONALE = {
    "RP-EVID-LIGHT": "A small change with low risk owes the evidence every change owes",
    "RP-EVID-DEFECT": ("A small fix to a live defect owes the regression and security "
                       "reviews and the Definition of Done"),
    "RP-EVID-STANDARD": ("A change that is not small, or not low risk, owes the regression, "
                         "security and clarity reviews and the Definition of Done"),
    "RP-REQUIRE-003": "Cross-cutting or critical risk owes the architecture review",
    "RP-REQUIRE-004": "A change to a `G5` surface owes the architecture review",
    "RP-EVID-REPRODUCE": "A live defect is reproduced by a red before anything else",
    "RP-EVID-SIGNOFF": ("A change to a `G5` surface, or with critical risk, owes a "
                        "person's approval of its scenarios"),
    GATE_G5: "A change to a `G5` surface owes a person's sign-off before it ships",
}


def checkpoints_for(evidence, autonomy, applies):
    """The stage hand-offs that wait for a person (ADR-092 open question 7).

    `controlled` waits at assess and specify, and at build and ship where the
    four-layer acceptance strategy (`S17`) applies, because those two end its
    stage 2 and 3 reviews. `balanced` and `autonomous` wait nowhere, except at
    specify when the scenarios owe a person's approval. The list has the shape
    every reader of `checkpoints:` reads: the stage ids, in path order."""
    if autonomy == "controlled":
        return [STAGE_ASSESS, STAGE_SPECIFY] + ([STAGE_BUILD, STAGE_SHIP] if applies else [])
    return [STAGE_SPECIFY] if "scenario-approval" in evidence else []


def live_resolved(task, task_dir):
    """The configuration `approach evaluate --write` would commit now, for a run
    that reads the governance files: a preview of an issue with no generation, or
    an assessment given on the command line, in a project with no `compass.yml`.
    A write commits the live configuration, which declares the `S17` strategy, so
    a preview that read only the governance files would owe less than the write
    stores."""
    from compass_pkg import effective
    from compass_pkg.project_settings import find_project_root
    slug = os.path.basename(os.path.normpath(task_dir)) if task_dir else None
    return effective.resolve_live(find_project_root(task_dir or os.getcwd()),
                                  task, slug, task_dir).resolved


def strategy_inputs(task, task_dir, resolved, expected):
    """`(state, reason, expected)` of the `S17` strategy for this write, or None
    when the write stores no block. As for an 8.x issue (`routing._acceptance_block`),
    no block is stored for a project pinned before the strategy, for a
    configuration that does not declare it, or on a re-assess of an issue assessed
    before it shipped (ADR-006). Then the strategy owes nothing on the issue.
    With no manifest (an assessment given on the command line) it is what a new
    issue in the working directory's project would get."""
    from compass_pkg import acceptance_strategy
    from compass_pkg.project_settings import find_project_root
    task = task or {}
    held = acceptance_strategy.stored(task)
    before = bool(task.get("delivery_approach")) or bool(task.get("evaluated_assessment"))
    project = find_project_root(task_dir or os.getcwd())
    if ((before and held is None) or acceptance_strategy.pinned_below(project)
            or not acceptance_strategy.declared(resolved)):
        return None
    state, reason = acceptance_strategy.setting(project)
    return state, reason, expected or (held or {}).get("expected_acceptance") or "none"


def _block(out, state, reason, expected):
    """The stored `acceptance_strategy` block, in the shape `acceptance_strategy.block`
    writes, with the routing of the evidence row."""
    from compass_pkg import acceptance_strategy as strategy
    if state == "off":
        why = reason
    elif expected in strategy.ACCEPTANCE_KINDS:
        why = f"acceptance of kind {expected}"
    else:
        why = strategy.BEHAVIOR
    block = {"state": state}
    if reason:
        block["reason"] = reason
    block.update({"routing": out["acceptance_routing"], "expected_acceptance": expected,
                  "applies": out["acceptance_applies"], "why": why})
    return block


#: The effects of a rule of the configuration that hold on the path: a required
#: skill, an added gate (read back by `routing.gates_added_by`) and a required
#: document. A floor's other effects raise an approach, force a stage mode or cap
#: the subtasks, and the path has none of those to change.
_PATH_EFFECT = re.compile(r"^(skill|gate|artifact) '")


def row_of(path):
    """The id of the evidence row that fired for `path`, as `--verbose` names it."""
    from compass_pkg import evidence_required as er
    rows = {rule for rule, *_ in er.ROWS}
    return next((f["id"] for f in path["policy_rules_fired"] if f["id"] in rows), None)


def _fired(out, legacy_fired):
    """`policy_rules_fired`: one mapping per rule that fired, in order. A rule of
    the configuration keeps its entry, with only the effects the path has."""
    from compass_pkg import evidence_required as er
    kept = {f.get("id"): dict(f, changed=[c for c in f.get("changed") or []
                                         if _PATH_EFFECT.match(str(c))])
            for f in legacy_fired or [] if isinstance(f, dict)}
    added = dict(((rule, (token,)) for rule, _, token in er.ADDITIONS))
    added.update((rule, tokens) for rule, _, tokens, _ in er.ROWS)
    fired = []
    for rule in out["rules_fired"]:
        if rule in RATIONALE:
            tokens = [t for t in added.get(rule, ()) if t in out["evidence_required"]]
            fired.append({"id": rule, "kind": "guardrail" if rule == GATE_G5 else "evidence",
                          "rationale": RATIONALE[rule],
                          "changed": ["evidence owed: " + ", ".join(tokens)] if tokens else []})
        elif rule in kept:
            fired.append(kept[rule])
        else:
            fired.append({"id": rule, "kind": "requirement", "rationale": "", "changed": []})
    return fired


def evaluate(readings, policy, autonomy, legacy, strategy):
    """The path keys for an assessment, or None for a spike.

    `policy` is the configuration in force, as `routing.evaluate_route` reads it;
    `legacy` is that function's result, whose fired floors are kept as they are;
    `strategy` is what `strategy_inputs` returned. Raises `RoutingConflict` for
    exploration on a surface that owes a sign-off, as the evaluator does."""
    from compass_pkg import evidence_required as er
    state, reason, expected = strategy if strategy is not None else ("off", None, "none")
    out = er.evaluate(readings, policy, state, expected)
    if out["delivery_approach"] == APPROACH_SPIKE:
        return None
    return {
        "delivery_approach": out["delivery_approach"],
        "evidence_required": out["evidence_required"],
        "gates": out["gates"],
        "acceptance_strategy": (_block(out, state, reason, expected)
                                if strategy is not None else None),
        "checkpoints": checkpoints_for(out["evidence_required"], autonomy,
                                       out["acceptance_applies"]),
        "policy_rules_fired": _fired(out, legacy.get("policy_rules_fired")),
        "required_skills": out["required_skills"],
        "applicable_strategies": out["applicable_strategies"],
    }


def shown(legacy, path):
    """The result `approach evaluate` prints, on the path: the legacy result with
    the path keys in place of the approach's and no key the path does not write."""
    out = {k: v for k, v in legacy.items() if k not in LEGACY_ONLY + NOT_SHOWN}
    out.update({k: v for k, v in path.items() if v is not None})
    return out


def write(task, path):
    """Put the path keys in the manifest and take out the keys of the legacy
    stages. The gates keep the state of any gate the issue already held."""
    for key in ("delivery_approach", "evidence_required", "checkpoints",
                "policy_rules_fired"):
        task[key] = path[key]
    if path["acceptance_strategy"] is not None:
        task["acceptance_strategy"] = path["acceptance_strategy"]
    existing = {g.get("id"): g for g in task.get("gates") or [] if isinstance(g, dict)}
    task["gates"] = [existing.get(gid, {"id": gid, "status": "pending", "evidence": []})
                     for gid in path["gates"]]
    for key in LEGACY_ONLY:
        task.pop(key, None)


def evidence_line(task):
    """The middle line of `compass approach show` on a path issue."""
    owed = [t for t in task.get("evidence_required") or [] if isinstance(t, str)]
    return "Evidence: " + (", ".join(owed) if owed else "none")


# --- the acceptance criteria `compass quick-fix start` writes ------------------------------

_STEPS = re.compile(r"^\s*given\s+(?P<given>.+?),\s*when\s+(?P<when>.+?),\s*then\s+(?P<then>.+?)"
                    r"\.?\s*$", re.IGNORECASE | re.DOTALL)
#: The reason each concern row of the Non-functional requirements table holds on a
#: change that owes no Definition of Done (the light row). It says what is true:
#: start was given one scenario and no requirement. A person replaces it with the
#: scenario ids that cover the concern, where one applies.
NFR_REASON = "quick-fix start was given one scenario and no requirement for this concern"


def criteria_text(slug, intent, scenario_id, scenario, resolve_rows=True):
    """`acceptance-criteria.md` for an issue `compass quick-fix start` opens on
    the path: the sections of `templates/acceptance-criteria.md` that hold what
    start was given, the intent as INT-1 and the one scenario, with no
    placeholder left. 9.0.0 writes no devlog (ADR-092 decision 12), so this file
    holds what the manifest has no key for.

    With `resolve_rows` the concern rows hold `NFR_REASON`. Without it, for a
    change that owes the Definition of Done, they are left empty, so
    `nfr-rows-resolved` names each concern until someone resolves it."""
    from compass_pkg.section_checks import CONCERNS, NFR_HEADING
    steps = _STEPS.match(scenario or "")
    if steps:
        gherkin = ["```gherkin", f"Scenario: {scenario_id}",
                   f"  Given {steps['given'].strip()}", f"  When {steps['when'].strip()}",
                   f"  Then {steps['then'].strip()}", "```"]
    else:
        gherkin = [scenario]
    lines = [f"# Spec - {slug}", "", "## Summary", "", f"**Goal:** {intent}", "",
             "## Intent links", "", "| Intent id | Source | Statement |", "|---|---|---|",
             f"| INT-1 | quick-fix start | {intent} |", "",
             "## Scenario group A - the change", "",
             "**Independence note:** single group, no parallelism expected", "",
             f"### Scenario: {scenario}",
             f"<!-- traceability id: {scenario_id} · serves: INT-1 -->", ""]
    lines += gherkin + ["", f"## {NFR_HEADING}", "",
                        "| Concern | Scenario | Reason it does not apply |", "|---|---|---|"]
    cells = f" {NFR_REASON} " if resolve_rows else " "
    lines += [f"| {concern} | |{cells}|" for concern in CONCERNS]
    return "\n".join(lines) + "\n"
