# compass_pkg.record_triggers - which commands change an issue's records
"""The commands whose success changes what an issue's records say, in one place.

`command_guard.before_command` refuses such a command on an issue whose
generation was built by another resolver or schema major, before it writes
(`RECORD_TRIGGERS`).

Before 9.0.0 the same table also chose the commands after which the issue's
documents were rendered and its page posted (ADR-091 removed both), and after
which its labels were written to GitHub (ADR-093 removed the label sync).

A command is a function name, the `func` of its parser. The value names an
argument that must be set for the command to count (`approach evaluate` writes
only with `--write`), or None.

`EXEMPT` names the commands that save a manifest and are not in the table, each
with its reason. A test walks the call graph of the CLI from every command to
`save_manifest` and fails, naming the command, when one is in neither.
"""
# DEPENDENCY: standard library only (annotations). It imports no other module, so the
# major refusal can read it.
from __future__ import annotations

#: Commands that change an issue's records.
RECORD_TRIGGERS = {
    "cmd_route_evaluate": "write",
    "cmd_task_set_status": None,
    "cmd_task_status_remove": None,
    "cmd_issue_link": None,
    "cmd_land_commit": None,
    "cmd_quick_fix_finish": None,
    "cmd_evidence_request": None,
    "cmd_scenario_add": None,
    "cmd_gate_pass": None,
    "cmd_tdd_red": None,
    "cmd_tdd_green": None,
    "cmd_evidence_add": None,
    "cmd_acceptance_record": None,
    "cmd_scenario_descope": None,
    "cmd_evidence_approve": None,
    "cmd_follow_up_add": None,
    "cmd_backfill_pay": None,
    "cmd_decision_add": None,
    "cmd_decision_set": None,
    "cmd_issue_raised_by": None,
    "cmd_scenario_tests": None,
    "cmd_evidence_review": None,
    "cmd_issue_blocked_set": None,
    "cmd_issue_blocked_remove": None,
    "cmd_depends_add": None,
    "cmd_depends_remove": None,
    "cmd_changed_file_add": None,
    "cmd_quick_fix_start": None,
    "cmd_waiver_add": None,
    "cmd_waiver_withdraw": None,
}

#: The argument that names the issue each command in `RECORD_TRIGGERS` changes, so the
#: refusal of a generation built by another major (`command_guard.before_command`)
#: asks about that issue and no other. The default is the `--issue` argument, which falls
#: back to the pointer to the current issue. `quick-fix start` names its issue as a positional `slug`, often a
#: new one, so the current issue is not the one it changes.
ISSUE_FROM = {**{name: "task" for name in RECORD_TRIGGERS}, "cmd_quick_fix_start": "slug"}

#: Commands that save a manifest and are not in `RECORD_TRIGGERS`, each with its reason.
EXEMPT = {
    "cmd_checkpoint_add": ("records that a hand-off was passed without waiting, in "
                           "checkpoint_outcomes; the major refusal has never covered it"),
}
