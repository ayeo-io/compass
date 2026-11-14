# Waivers

A waiver excuses one check on one issue. It needs a reason and a person's
approval (ADR-094).

9.0.0 does not read a waiver in `compass.yml` or in an issue's `config:`,
the 8.x form. `compass policy lint` names the key as a removed setting. A
stored 8.x generation keeps the waivers it recorded.

## Ask for a waiver

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

A change with no request to link, such as a typo, uses a waiver of
`request-recorded`.

`compass waiver add` refuses:

- an empty reason, or one with a control character (an escape sequence, a
  direction override or a line break);
- a check the check set never waives: `human-approval-present`,
  `ship-approval-present` and every check of guardrail `G5` (`never_waived`
  in `governance/check-set.yml`);
- a check Compass deleted (`check_registry.DELETED_CHECKS`);
- a check the issue's policy does not hold;
- a second waiver in force for the same check.

A new waiver excuses nothing. `compass check` names it in a notice, with the
command that asks for its approval.

## Approve it

The agent asks and stops:

```sh
compass evidence request --waiver W-1 --issue refund-flow
```

Compass then shows the person the check, the issue and the reason, with
every control, format and line-separator character removed. The person
approves in one of three ways:

- in Claude Code: `/compass:approve waiver W-1` or
  `/compass:approve <request number>`;
- in a terminal:
  `compass evidence approve --waiver W-1 --approver <name> --role <role>`;
- through an agent delegated with `/compass:delegate --for waivers`. No
  default delegation covers a waiver, and the person must type back the code
  the hook shows, as for `g5`.

**Who may approve:** the names in `approvers.waiver` of `compass.yml`, else
in `approvers.issue-waiver`, else the project's `owner`. With no `owner`,
nobody may approve a waiver.

The approval is one `human-approval` record, such as `EV-WAIVER-W-1-1`. It
holds `waiver`, `waived_check`, `waiver_reason`, `approver`, `role`, `scope`,
`decision`, `timestamp`, `issue`, `generation` and `via`. It names a subject,
so it never clears guardrail `G5`.

## What `compass check` shows

An approved waiver turns its check's row into `WAIVED`, with the waiver, the
reason, the approver and the record id. A waived row is not a failure and
not a pass. The summary counts it apart, and `compass check --json` gives
the row the status `waived` and the run a `waived` count.

```text
WAIVED suite-passed: waived by W-1 (the suite runs only in the nightly CI job), approved by ada in EV-WAIVER-W-1-1 - ...
```

A waiver excuses its check only while all of these hold:

- it has a reason and names a check;
- it is not withdrawn;
- its check is not in `never_waived`;
- a `human-approval` record names it, for this issue at its current
  generation, with the same check and reason, by an allowed approver, with
  `decision: approved` and the fields `approver`, `role`, `scope` and
  `timestamp`;
- no `approval-withdrawal` record withdraws that record.

So a waiver changed after its approval, or copied to another issue, excuses
nothing. After a reassessment moves the issue to a new generation, the
waiver needs a new approval, and `compass check` says so.

## Withdraw it

```sh
compass waiver withdraw W-1 --issue refund-flow
```

- A waiver nobody approved is removed, and its pending request is closed.
- An approved waiver is marked `withdrawn_at`. Its approval stays on record
  and the check runs again.
- An agent may run this command: it only makes the issue owe more.
- A person can overrule an approval an agent made under a delegation.
  `/compass:reject <record id> <reason>` writes an `approval-withdrawal`
  record, and the check runs again.

## A waiver of a deleted check

9.0.0 deleted fifteen checks (`check_registry.DELETED_CHECKS`): the eight in
`check_registry.REMOVED`, such as `contracts-declared`, and the seven
Definition of Ready checks, such as `dor-summary-filled`. `compass check`
refuses with exit 2 (`names-deleted-check`), before it runs any check, and
names each of these with its fix, in this order:

| What names a deleted check | Fix |
|---|---|
| A `project_checks` entry in `compass.yml`, by its `id` | Delete the entry |
| A list of checks in `compass.yml`: `gates.<id>.checks`, or `stages.<id>.entry` or `exit`, written plain, as `{add, remove}` or under `set:` | Delete the check from the list |
| A waiver that is not withdrawn | `compass waiver withdraw <id> --issue <slug>` |

The refusal keeps 16 words of the items and 16 of the fixes. Once those
items are cleared, the next run names the rest.

## Limits

Compass checks the approver's name. It does not authenticate the person, and
anyone who can write `manifest.yml` can write a record by hand. Repository
permissions and review of the change are the control
(`docs/safety-contract.md`).
