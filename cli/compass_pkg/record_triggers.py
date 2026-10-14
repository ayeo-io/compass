# compass_pkg.record_triggers - which commands change an issue's records
"""The commands whose success changes what an issue's records say, in one place.

Three steps run after such a command exits 0, in this order, and all read this
table:

1. `github_labels.after_command` brings the issue's labels on GitHub up to date
   (`LABEL_TRIGGERS`);
2. `render_after.after_command` renders the issue's documents and the issues the
   manifest links to (`RENDER_TRIGGERS`, which is `LABEL_TRIGGERS` plus
   `RENDER_FURTHER`);
3. `github_page.after_command` posts the README the render has just written to
   the linked GitHub issue (`PAGE_TRIGGERS`, the render's table, because any
   command that can change the README can change the page).

No step imports another, so each can fail without hiding the others, and a
command cannot be in the label table and missing from the render table.

A command is a function name, the `func` of its parser. The value names an
argument that must be set for the command to count (`approach evaluate` writes
only with `--write`), or None.

`EXEMPT` names the commands that save a manifest and are in neither table, each
with the reason no block or label shows what they save. A test walks the call
graph of the CLI from every command to `save_manifest` and fails, naming the
command, when one is in none of the three tables.
"""
# DEPENDENCY: standard library only (annotations). It imports no other module, so the
# label step, the render step and the page step can all read it.
from __future__ import annotations

#: Commands after which the issue's labels are brought up to date.
LABEL_TRIGGERS = {
    "cmd_route_evaluate": "write",
    "cmd_task_set_status": None,
    "cmd_task_status_remove": None,
    "cmd_issue_link": None,
    "cmd_land_commit": None,
    "cmd_quick_fix_finish": None,
    "cmd_scenario_add": None,
    "cmd_gate_pass": None,
    "cmd_issue_artifact": None,
    "cmd_subtask_add": None,
    "cmd_subtask_replan": None,
    # A test on record moves an issue from ready to in-progress.
    "cmd_tdd_red": None,
    "cmd_tdd_green": None,
    "cmd_evidence_add": None,
    "cmd_acceptance_record": None,
    "cmd_scenario_descope": None,
}

#: Commands that change a record a rendered block shows and move no label.
RENDER_FURTHER = {
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
    # The waiting issue's page shows the wait, and the other issue's page
    # lists who waits for it, so both render. After a remove the manifest no
    # longer names the other issue, so `cmd_depends_remove` names it in
    # `args.unlinked` for `render_after` to render.
    "cmd_depends_add": None,
    "cmd_depends_remove": None,
    "cmd_subtask_update": None,
    # The traceability chart of the issue page draws the files each scenario changed.
    "cmd_changed_file_add": None,
    # The quick fix's record holds the header, assessment and policy-rules blocks.
    "cmd_quick_fix_start": None,
}

RENDER_TRIGGERS = {**LABEL_TRIGGERS, **RENDER_FURTHER}

#: Commands after which the issue page on GitHub is brought up to date: every command
#: that can change the README, since the page is the README.
PAGE_TRIGGERS = RENDER_TRIGGERS

#: Commands that save a manifest and render nothing, each with its reason.
EXEMPT = {
    "cmd_analyze": ("in gate-clearing mode it adds one consistency-check evidence entry, and "
                    "the gate pass that must follow it renders; in advisory mode it saves "
                    "nothing, so a render here would make a reading command write"),
    "cmd_intent_ingest": ("saves the intent record the issue was written from, which no "
                          "rendered block shows"),
    "cmd_friction_capture": ("records a friction note in the manifest, which no rendered "
                             "block shows"),
    "cmd_issue_friction": ("records a friction note in the manifest, which no rendered "
                           "block shows"),
    "cmd_subtask_package": ("writes the subtask brief files; the key it saves names their "
                            "paths and no rendered block shows it"),
}
