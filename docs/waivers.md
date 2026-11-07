# Waivers

A waiver excuses one check on one issue. It needs a reason and a person's approval. This page shows how to ask for one, how a person approves it, and what `compass check` then shows. The decision behind it is ADR-094, the architecture decision record that makes every project run one fixed check set.

A waiver in a project's `compass.yml` or in an issue's `config:` layer is the 8.x form. 9.0.0 removed the layers that held it (ADR-094): such a waiver is not read, and `compass policy lint` names the key that holds it as a removed setting. A stored 8.x generation keeps the waivers it recorded.

## Ask for a waiver

The agent, or a person, writes the waiver with a reason:

```sh
compass waiver add --issue refund-flow --check suite-passed \
  --reason "the suite runs only in the nightly CI job"
```

The waiver goes into the issue's `manifest.yml`:

```yaml
waivers:
  - id: W-1
    check: suite-passed
    reason: the suite runs only in the nightly CI job
    requested_at: "2026-11-06T10:00:00Z"
    requested_by: agent
```

`compass waiver add` refuses:

- an empty reason;
- a reason that holds a control character: an escape sequence, a direction override or a line break. The person is shown the reason, so it must be plain text on one line;
- a check the check set never waives: `human-approval-present`, `ship-approval-present` and every check of guardrail `G5`, from `never_waived` in `governance/check-set.yml`;
- a check the issue's policy does not hold;
- a second waiver in force for the same check.

A new waiver excuses nothing. `compass check` names it in a notice, with the command that asks for its approval.

## Approve it

The agent asks and stops:

```sh
compass evidence request --waiver W-1 --issue refund-flow
```

At the end of the agent's turn Compass shows the person the request: the check, the issue and the reason. The person approves in one of three ways:

- in Claude Code, by typing `/compass:approve waiver W-1` or `/compass:approve <request number>`;
- in a terminal, with `compass evidence approve --waiver W-1 --approver <name> --role <role>`;
- through an agent the person delegated waivers to, with `/compass:delegate --for waivers`. No default delegation covers a waiver, and a delegation that covers waivers takes effect only after the person types back the code the hook shows, as for `g5`.

The approval is one `human-approval` record:

```yaml
- id: EV-WAIVER-W-1-1
  type: human-approval
  waiver: W-1
  waived_check: suite-passed
  waiver_reason: the suite runs only in the nightly CI job
  approver: ada
  role: owner
  scope: waiver W-1 of suite-passed
  decision: approved
  timestamp: "2026-11-06T10:05:00Z"
  issue: refund-flow
  generation: 1
  via: prompt
```

The record names a subject, so it never clears guardrail `G5`.

Who may approve: the names in `approvers.waiver` of `compass.yml`, else in `approvers.issue-waiver`, else the project's `owner`. A project with no `owner` has nobody who may approve a waiver. Both are read from `compass.yml` as settings (`project_settings.project_file`), so a removed catalog key in the same file does not stop them being read.

## What `compass check` shows

An approved waiver turns its check's row into `WAIVED`, with the waiver, the reason, the approver and the record id. A waived row is not a failure and not a pass: it is counted apart.

```text
FAIL - 2 of 13 check(s) failed, 11 had nothing to check, 1 waived (an approved waiver excuses it) on 'refund-flow' (delivery)
WAIVED suite-passed: waived by W-1 (the suite runs only in the nightly CI job), approved by ada in EV-WAIVER-W-1-1 - ...
```

`compass check --json` gives the row the status `waived` and the run a `waived` count.

A waiver excuses its check only while all of these hold:

- it has a reason and names a check;
- it is not withdrawn;
- its check is not in `never_waived`;
- a `human-approval` record names it, for this issue at its current generation, with the same check and reason, by an allowed approver, with `decision: approved` and the four fields `approver`, `role`, `scope` and `timestamp`;
- no `approval-withdrawal` record withdraws that record.

A waiver changed after its approval, or copied to another issue, excuses nothing. A reassessment that moves the issue to a new generation, for example because its risk rose, sets the approval aside: `compass check` names the waiver as not approved and says it needs a new approval at this generation.

The request Compass shows the person holds the reason with every control, format and line-separator character removed, so a reason written by hand into the manifest cannot hide the line that names the check.

## Withdraw it

```sh
compass waiver withdraw W-1 --issue refund-flow
```

A waiver nobody approved is removed, and its pending request is closed. An approved waiver is marked `withdrawn_at`, so its approval stays on record and the check runs again. Withdrawing only makes the issue owe more, so an agent may run it.

A person can also overrule an approval an agent made under a delegation: `/compass:reject <record id> <reason>` writes an `approval-withdrawal` record, and the check runs again.

## Limits

Compass checks the approver's name. It does not authenticate the person, and anyone who can write `manifest.yml` can write a record by hand. Repository permissions and review of the change are the control, as for every approval (`docs/safety-contract.md`).
