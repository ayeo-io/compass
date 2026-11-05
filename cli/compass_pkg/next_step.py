# compass_pkg.next_step - the one command that comes next on an issue
"""Decide the `next:` command from an issue's records (ADR-092).

`compass next` prints the issue's stage and then `next: <command>`. One
function, `next_command`, decides the command, so `compass next` and the verbs
that will print the same part cannot disagree. The rows below are read top to
bottom, and the first that matches gives the command:

| Records show | `next:` |
|---|---|
| no manifest | `/compass:go "<what you want>"` |
| closed | none |
| a spike with no conclusion | `compass evidence add EV-SPIKE --type spike-conclusion ...` |
| assessed, no scenario | `compass scenario add TRC-001 ...` |
| a scenario with no test | `compass scenario tests set <id> --test <path::name>` |
| `scenario-approval` owed, no outcome | `compass evidence request --checkpoint specify` |
| `S17` applies, no outer-loop red | `compass tdd-red --loop outer --scenario <id> -- ...` |
| a scenario with no red | `compass tdd-red --scenario <id> -- <test command>` |
| a red with no green | `compass tdd-green --scenario <id> -- <test command>` |
| `isolation` owed | `compass isolation record --parallel ... --repeat ...` |
| `layering` owed | `compass layering record -- <layering test command>` |
| a Definition of Done item open | `compass evidence add <EV-id> ... --meets <item>` |
| a review gate pending | `compass gate pass <gate> --evidence <EV-id>` |
| `human-approval` owed | `compass evidence request --check human-approval-present` |
| a listed checkpoint with no outcome | `compass evidence request --checkpoint <stage>` |
| every gate passes | `compass check, then compass ship-commit -m "<message>"` |

What is owed comes from `evidence_required` on a path issue. An issue assessed
before the path has no such list, so its owed evidence is read from the records
it has: the `S17` rows from its stored `acceptance_strategy` block and the
Definition of Done from a `thorough` verify stage, as `compass check` judges
them. The rows that only the path adds (`scenario-approval`, `human-approval`)
are not owed on an old issue; `compass check` still judges its own rules.

The words in angle brackets are for the reader to fill in. This module reads
records only and never writes.
"""
# DEPENDENCY: standard library (os); compass_pkg.path_stages, red_first,
# stable_ids and status_words, and inside functions the readers of
# acceptance_strategy, checkpoint_outcomes, checks, effective, gate_status and
# item_records. It must not import next_cmd at load time: next_cmd imports it.
from __future__ import annotations

import os

from compass_pkg import path_stages, red_first, status_words
from compass_pkg.stable_ids import APPROACH_SPIKE, REMOVED_GATE_IDS, STAGE_SPECIFY, STAGE_VERIFY

GO = '/compass:go "<what you want>"'
FIRST_SCENARIO = "TRC-001"
SPIKE_GATE = "spike.conclude"
#: The routings of `S17` that owe each strategy record on an old issue, as the
#: preset routed them (`acceptance_strategy.ROUTINGS`).
_LEGACY_ROUTINGS = {"outer-loop": ("existing-dsl", "existing-dsl-isolation", "on"),
                    "isolation": ("existing-dsl-isolation", "on"),
                    "layering": ("on",)}
#: The record file each strategy command writes.
_ISOLATION_RECORD = "isolation-proof.json"
_LAYERING_RECORD = "layering.json"


def next_command(task, task_dir, done=None):
    """The command that comes next on the issue, or None for a closed issue.

    `task` is the loaded manifest, or None when there is none. `done` is the set
    of stages the records show as done, when the caller already has it; the
    checkpoint row reads it. A fault in a reader gives `compass check`, which
    says what is missing, so `compass next` still prints a line.
    """
    if not isinstance(task, dict):
        return GO
    if status_words.is_closed(task):
        return None
    try:
        return _first_match(task, task_dir, done)
    except Exception:  # noqa: BLE001 - the stage line must still print
        return "compass check"


def _first_match(task, task_dir, done):
    if task.get("delivery_approach") == APPROACH_SPIKE:
        spike = _spike(task)
        if spike:
            return spike
    else:
        for row in (_specify, _build, _ship):
            command = row(task, task_dir)
            if command:
                return command
    gate = _pending_gate(task)
    if gate:
        return f"compass gate pass {gate} --evidence <EV-id>"
    if _owed(task, task_dir, "human-approval") and not _human_approval(task, task_dir):
        return "compass evidence request --check human-approval-present"
    stage = _checkpoint_waiting(task, done)
    if stage:
        return f"compass evidence request --checkpoint {stage}, then stop for /compass:approve"
    return 'compass check, then compass ship-commit -m "<message>"'


# --- the rows of each stage ----------------------------------------------------------------

def _specify(task, task_dir):
    scenarios = needing_tests(task)
    if not _scenarios(task):
        return (f"compass scenario add {FIRST_SCENARIO} --intent <intent id> "
                "--test <path::name>")
    untested = [s["id"] for s in scenarios if not _tests_of(s)]
    if untested:
        return f"compass scenario tests set {untested[0]} --test <path::name>"
    if _owed(task, task_dir, "scenario-approval") and not specify_handed_off(task):
        return ("compass evidence request --checkpoint specify, "
                "then stop for /compass:approve")
    return None


def _build(task, task_dir):
    ids = [s["id"] for s in needing_tests(task)]
    if ids and _owed(task, task_dir, "outer-loop") and not _outer_red(task_dir):
        return (f"compass tdd-red --loop outer --scenario {ids[0]} "
                "-- <acceptance test command>")
    reds = red_first.scenario_reds(task, task_dir) if task_dir else {"no_red": ids}
    if reds["no_red"]:
        return f"compass tdd-red --scenario {reds['no_red'][0]} -- <test command>"
    greened = greens(task)
    no_green = [i for i in ids if i not in greened]
    if no_green:
        return f"compass tdd-green --scenario {no_green[0]} -- <test command>"
    if _owed(task, task_dir, "isolation") and not _record(task_dir, _ISOLATION_RECORD):
        return ('compass isolation record --parallel "<acceptance suite command>" '
                '--repeat "<scenario test command>"')
    if _owed(task, task_dir, "layering") and not _record(task_dir, _LAYERING_RECORD):
        return "compass layering record -- <layering test command>"
    return None


def _ship(task, task_dir):
    if not _owed(task, task_dir, "definition-of-done"):
        return None
    item = _open_dod_item(task, task_dir)
    if item:
        return f"compass evidence add <EV-id> --type <type> --path <path> --meets {item}"
    return None


def _spike(task):
    concluded = any(e.get("type") == "spike-conclusion" for e in _dicts(task.get("evidence")))
    if not concluded:
        return ("compass evidence add EV-SPIKE --type spike-conclusion --path <file> "
                "--decision <discard|graduate-to-delivery|defer>")
    if _pending_gate(task) == SPIKE_GATE:
        return f"compass gate pass {SPIKE_GATE} --evidence EV-SPIKE"
    return None


# --- the records ---------------------------------------------------------------------------

def _dicts(value):
    return [e for e in value if isinstance(e, dict)] if isinstance(value, list) else []


def _scenarios(task):
    return [s for s in _dicts(task.get("scenarios")) if isinstance(s.get("id"), str) and s["id"]]


def needing_tests(task):
    """The scenarios that need a test, a red and a green: every one but a
    `verifiable: narrative` scenario, which its written body clears."""
    return [s for s in _scenarios(task) if s.get("verifiable") != "narrative"]


def _tests_of(scenario):
    tests = scenario.get("tests")
    return [t for t in tests if isinstance(t, str) and t] if isinstance(tests, list) else []


def scenarios_specified(task):
    """True when the issue has a scenario and each one has an id, an intent and,
    unless it is narrative, a declared test."""
    scenarios = _scenarios(task)
    return bool(scenarios) and all(
        s.get("intent") and (s.get("verifiable") == "narrative" or _tests_of(s))
        for s in scenarios)


def greens(task):
    """The scenario ids with a test-run bound to them, as `compass tdd-green`
    registers one."""
    return {e["scenario"] for e in _dicts(task.get("evidence"))
            if e.get("type") == "test-run" and isinstance(e.get("scenario"), str)}


def specify_listed(task):
    value = task.get("checkpoints")
    return isinstance(value, list) and STAGE_SPECIFY in value


def specify_handed_off(task):
    """True when the `specify` checkpoint has an outcome. Read from the raw
    list, so it does not depend on which stages the checkpoint reader knows."""
    from compass_pkg.checkpoint_outcomes import KEY, OUTCOMES
    return any(e.get("stage") == STAGE_SPECIFY and e.get("outcome") in OUTCOMES
               for e in _dicts(task.get(KEY)))


def _outer_red(task_dir):
    if not task_dir:
        return False
    from compass_pkg import acceptance_strategy
    return any(name.endswith(red_first.OUTER + ".json")
               or acceptance_strategy.loop_of(record) == "outer"
               for name, record in acceptance_strategy.red_records(task_dir))


def _record(task_dir, name):
    return bool(task_dir) and os.path.isfile(os.path.join(task_dir, "evidence", name))


def _pending_gate(task):
    for gate in task.get("gates") or []:
        if not isinstance(gate, dict):
            return None
        if gate.get("status") != "pass" and gate.get("id") not in REMOVED_GATE_IDS:
            return gate.get("id")
    return None


def _owed(task, task_dir, token):
    """True when the issue owes the evidence `token` (an `evidence_required` value)."""
    if path_stages.is_path_issue(task):
        listed = task.get("evidence_required")
        if not isinstance(listed, list) or token not in listed:
            return False
        if token in _LEGACY_ROUTINGS:
            return _strategy_in_scope(task, task_dir, stored_needed=False)
        return True
    if token in _LEGACY_ROUTINGS:
        from compass_pkg import acceptance_strategy
        held = acceptance_strategy.stored(task) or {}
        return (held.get("routing") in _LEGACY_ROUTINGS[token]
                and _strategy_in_scope(task, task_dir, stored_needed=True))
    if token == "definition-of-done":
        stages = task.get("stages")
        weight = stages.get(STAGE_VERIFY) if isinstance(stages, dict) else None
        return isinstance(weight, str) and weight.strip().lower() == "thorough"
    return False


def _strategy_in_scope(task, task_dir, stored_needed):
    """Does `S17` apply now? A path issue with no stored block owes what its
    list says; the records can still take it out of scope (an acceptance of kind
    validation or refactor and no red)."""
    from compass_pkg import acceptance_strategy
    if acceptance_strategy.stored(task) is None and not stored_needed:
        return True
    if not task_dir:
        return False
    return acceptance_strategy.in_scope(task, task_dir)[0]


def _open_dod_item(task, task_dir):
    from compass_pkg import effective, item_records
    view = effective.view_or_legacy(task_dir)
    for item in item_records.items(task, task_dir, view, "dod"):
        if item.state == item_records.OPEN:
            return item.check
    return None


def _human_approval(task, task_dir):
    from compass_pkg.checks import _check_human_approval
    return _check_human_approval(task, task_dir)[0]


def _checkpoint_waiting(task, done):
    """The first listed checkpoint whose stage is done and has no outcome."""
    from compass_pkg import checkpoint_outcomes
    missing = checkpoint_outcomes.missing(task)
    for stage in missing:
        if done is None or stage in done:
            return stage
    return None
