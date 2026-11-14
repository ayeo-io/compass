# Judged checks

A check of kind `judged` records a judgment. `compass evidence review`
writes the review record that clears it. The CLI checks that the record
exists, says `pass`, was written by a listed reviewer and covers inputs that
have not changed. It does not check the reasoning.

## Declaring a judged check

```yaml
checks:
  design-review:
    statement: The design holds against every scenario.
    kind: judged
    reviewers: [agent, jed72]
    inputs: [technical-design, acceptance-criteria]
    severity: blocking
    on_skipped: fail
```

| Field | Meaning |
|---|---|
| `statement` | What is judged. |
| `inputs` | The artifact ids or evidence ids the reviewer read. A check with no `inputs` cannot be reviewed and fails in a list. |
| `reviewers` | Who can review: `agent` (any agent session), `agent:<id>` (one session), or a person's id. The default is `[agent]`. |

- An evidence id names the file of that evidence entry. Any other input is
  a document of the issue.
- The digest of an input is the SHA-256 of its file without the lines
  inside [rendered blocks](rendered-blocks.md). A render of a block does not
  re-owe the review.
- The digest of the check's definition covers every field of the check. A
  change to any field re-owes the review.

## The review record

`compass evidence review` writes `evidence/review-<check>-<n>.yml` in the
issue's directory. It registers the file in the manifest as `manual-review`
evidence with `check: <check id>`:

```yaml
schema: 1
check: design-review
issue: my-issue
verdict: pass
reason: Sections 2 to 6 read; it holds.
reviewer: {kind: person, id: jed72}
scope: technical-design.md
inputs:
  technical-design: sha256:...
  acceptance-criteria: sha256:...
generation: 1
definition_digest: sha256:...
at: 2026-10-08T10:00:00Z
content_digest: sha256:...
```

- **Not a record:** one edited after it was written, one with no
  `content_digest` stamp, one with no file, one for another check, and one
  copied from another issue (`issue` holds the slug it was written in).
- **Never overwritten.** A second review is a new record. The newest
  registered record by a listed reviewer decides: a later `fail` overrides a
  `pass`, and a new `pass` clears a `fail`.
- **A reviewer the check does not list:** the record is set aside. It can
  neither clear the check nor block it.
- **Another generation** than the one in force re-owes the review.

## When a judged check passes

The deciding record must meet all four conditions. The first one that fails
starts the detail of the row:

| Condition | Cause when it fails | When |
|---|---|---|
| It is a record | `no review record` | No registered record, or the newest is not usable. The detail names the command to run, or why the record is not usable. |
| Its `verdict` is `pass` | `verdict is fail` | The detail gives the reviewer and the reason. |
| Its reviewer is in `reviewers` | `reviewer not listed` | Every usable record is by a reviewer not listed. The detail names who reviewed the newest and who the check lists. |
| Its `inputs` digests and `definition_digest` equal the digests now | `input changed since review` | An input has other bytes, is missing, or is not in the set the review covered, or the definition or the generation changed. The detail names each. |

A changed input or definition re-owes the review: the check fails until
someone reviews the inputs as they are now.

A judged check follows the rules of each check in a list
([entry and exit evaluation](entry-exit-evaluation.md)):

- It is `pending` until its list is due.
- It gives its `on_skipped` verdict when its stage is skipped or collapsed.
- An advisory one reports a failure with the `advisory` status, which does
  not fail the run.

## `compass evidence review`

```
compass evidence review CHECK --verdict pass|fail --reason TEXT --reviewer ID
                        [--scope TEXT] [--issue SLUG]
```

| Option | Meaning |
|---|---|
| `CHECK` | The id of a judged check in the issue's stored configuration |
| `--verdict` | `pass` or `fail` |
| `--reason` | What was read and why the verdict holds. Not empty. |
| `--reviewer` | `agent`, `agent:<session id>` or a person's id |
| `--scope` | What the judgment covers (optional) |

The command digests the inputs as they are now, writes the record and
registers it. It exits 0 when it wrote the record. It exits 2 and writes
nothing for:

- a check that does not exist, or is not of kind `judged`;
- a check that declares no `inputs`;
- an input that cannot be found;
- an empty reason or reviewer, or a verdict other than `pass` or `fail`;
- an issue with no stored configuration (run `compass approach evaluate
  --write`).

### `--json`

The `--json` document is a public contract, like the exit codes. A change
to a key or its order is a breaking change. This is real output; `at` and
`definition_digest` vary and are shown as `...`. `scope` and `generation`
are absent when the record has none.

```json
{
  "outcome": "compass evidence review: design-review - pass recorded as EV-REVIEW-design-review-1.",
  "check": "design-review",
  "verdict": "pass",
  "evidence_id": "EV-REVIEW-design-review-1",
  "path": "evidence/review-design-review-1.yml",
  "reviewer": {
    "kind": "person",
    "id": "jed72"
  },
  "scope": "technical-design.md",
  "inputs": {
    "technical-design": "sha256:dd7eb5b73000f522b5ab205e8af24a1cd265725066b603b1db475ff92cf51529",
    "acceptance-criteria": "sha256:c2405d27077f12e98622f4489dfa5a10d28834fd85d0c32f5fbf73bf1d3a2955"
  },
  "generation": 1,
  "definition_digest": "sha256:...",
  "at": "...",
  "detail": [
    "record : evidence/review-design-review-1.yml",
    "input  : technical-design sha256:dd7eb5b73000f522b5ab205e8af24a1cd265725066b603b1db475ff92cf51529",
    "input  : acceptance-criteria sha256:c2405d27077f12e98622f4489dfa5a10d28834fd85d0c32f5fbf73bf1d3a2955"
  ]
}
```

## An agent review

No agent review is required (ADR-090). A project turns one on as advisory
evidence with one setting in `compass.yml` (ADR-094):

```yaml
agent_review: on
```

The setting adds the judged check `agent-review` at the `ship` entry:

| Field | Value |
|---|---|
| Statement | "An agent that did not write the change reviewed it against the acceptance criteria." |
| Reviewers | `reviewers: [agent]` |
| Inputs | `inputs: [acceptance-criteria]` |
| Severity | `severity: advisory` |
| On a skipped stage | `on_skipped: not-applicable` |

The reviewing agent runs `compass evidence review agent-review --verdict
pass|fail --reason TEXT --reviewer agent`.

- With no record, a `fail` or a changed input, the check shows as ADVISORY.
  `compass check` does not fail on it.
- A record by a person is set aside, because the check lists only `agent`.
- The check is not in the Definition of Done, so `dod-evidence-typed` does
  not read it.
- A `checks:` or `stages:` block in `compass.yml` is a removed setting and
  is not read.

## Limits

- The shipped default names no judged check. A project with none is
  unchanged.
- A role in `reviewers` is not resolved. It is matched as a person's id.
- Reviewer identity is not authenticated, as with `human-approval`. A name
  in a field is a claim.
- A `human` check still reads a tick.
- A check of kind `evidence` is not evaluated, and a blocking one fails.

## Code

`cli/compass_pkg/review_records.py` reads a record and judges it.
`cli/compass_pkg/review_cmd.py` is the command. `stage_lists.py` calls the
first for each judged check in a stage's entry or exit list. The decisions
are ADR-033 (checks are data) and ADR-037 (what a configuration change
owes).
