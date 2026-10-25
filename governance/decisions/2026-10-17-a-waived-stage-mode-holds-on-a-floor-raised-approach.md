# a-waived-stage-mode-holds-on-a-floor-raised-approach

## Decided by

jed72

## Date

2026-10-17

## Supersedes

`governance/decisions/2026-10-05-floors-win-over-the-issue-layer.md`, for waived stage modes only. Everything else in that entry stands: a floor still wins over the rest of an issue's own configuration.

## Decision

When a floor replaces an issue's approach with a heavier one, the evaluator keeps a stage mode the issue's `config:` sets if that stage's entry carries an issue waiver. Any stage the floor does not name can be waived this way, not only breakdown. Every other stage mode the issue sets is still reported as ignored.

The route lowers a stage mode only. It never lowers:

- the approach a floor forces;
- a stage a floor names in `never_skip` or `require_phase`, because the floor's lift still runs after the issue layer;
- a gate, a guardrail or its check, including guardrail 5;
- an artifact the approach or a rule earns;
- a lock, because the lint still refuses a layer that loosens a locked entry.

The waiver is the issue waiver of ADR-039: a reason, and `approved_by` naming a `human-approval` record that names the entry (`stages.<id>`) and the mode it approves. When the project has an `approvers.issue-waiver` list, the record must be by a person it lists. When it has none, the record must be by the project's `owner`. The reassess lints the issue's layer at its own assessment when the layer or the assessment changes. A waiver with no record, a record by someone who may not approve it, or a record for other values is then refused, and nothing is written.

## Why

A floor exists for risk a single issue cannot judge away, and what it does about that risk is the gates, the guardrails and the stages it names. Breakdown is a strategy, not a guardrail: whether the work splits into parallel subtasks does not change what is checked before it lands. Before this decision an approved reassess to a solo build was recorded and then ignored without a refusal, and the only way through was a subtask record written after the build. A recorded approval, bound to the entry and the values it approves, keeps the owner's decision and leaves every check of the floor in force.

Rejected: letting floors leave breakdown alone with no approval. The issue layer could then lower the breakdown of any floor-raised issue without anyone signing it off.

## Evidence

The maintainer's reply on 17 October 2026 to the question in GitHub issue ayeo-io/compass-delivery-record#16, "Let an owner-approved reassess override a stage a label floor raised": "Approve the recommended design for #16, any unnamed stage, the solo build, and a follow-up for the null quirk."

The issue was found on the migration review-entries fix, whose manifest set breakdown to skipped, recorded the owner's approval in a reassess reason, and needed a subtask record written after the build to clear `multiagent-run-recorded`.
