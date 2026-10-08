# Judged checks

This page is the owning doc for judged checks: a check of kind `judged`, the
review record that clears it, and `compass evidence review`, the command that
writes the record. A judged check records a judgement. The CLI checks that the
record exists, that it says `pass`, that a listed reviewer wrote it and that
the things it judged have not changed. It does not check the reasoning.

The code is `cli/compass_pkg/review_records.py` (reading a record and judging
it) and `cli/compass_pkg/review_cmd.py` (the command).
`cli/compass_pkg/stage_lists.py` calls the first for each judged check in a
stage's entry or exit list (see `docs/entry-exit-evaluation.md`). The
decisions behind it are ADR-035 (checks are data) and ADR-037 (what a
configuration change owes).

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
| `statement` | What is judged. Changing it changes the definition, so an earlier review no longer counts |
| `inputs` | The artifact ids or evidence ids the reviewer read. A check with no `inputs` cannot be reviewed and fails in a list |
| `reviewers` | Who may review. `agent` is any agent session, any other entry is a person's id. The default is `[agent]`. A role matches nobody, because no role to person mapping exists yet |

An input that is an evidence id names the file of that evidence entry. Any
other input is a document of the issue, found as every document is. The digest
of an input is the SHA-256 of its file.

## The review record

`compass evidence review` writes `evidence/review-<check>-<n>.yml` in the
issue's directory and registers it in the manifest as `manual-review` evidence
with `check: <check id>`:

```yaml
schema: 1
check: design-review
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

`content_digest` is the stamp that other evidence carries. A record edited
after it was written, one with no stamp, one with no file and one for another
check is not a record.

A record is never overwritten. A second review of the same check is a new
record, and the newest registered record decides. A later `fail` therefore
overrides an earlier `pass`, and a new `pass` clears a `fail`.

## When a judged check passes

It passes only when the newest record meets all four conditions:

1. the record is a record, as above;
2. its `verdict` is `pass`;
3. its reviewer is in the check's `reviewers`;
4. its `inputs` digests equal the digests of the inputs now, and its
   `definition_digest` equals the digest of the check's definition now.

The first condition that fails names the cause. The detail of the row starts
with it:

| Cause | When |
|---|---|
| `no review record` | The check has no registered record, or its newest record is not usable. The detail names the command to run, or says why the record is unusable |
| `verdict is fail` | The newest record says `fail`. The detail gives the reviewer and the reason |
| `reviewer not listed` | The reviewer is not in `reviewers`. The detail names who reviewed and who the check lists |
| `input changed since review` | An input has other bytes, is missing, or is not the set the review covered, or the definition of the check changed. The detail names each |

A changed input or definition re-owes the review: the same check fails
again until someone reviews the current inputs. The change of the definition
is reported under the fourth cause with its own phrase, because it re-owes the
review for the same reason an input does.

A judged check follows the rules of every check in a list. It is `pending`
until its list is due, it gives its `on_skipped` verdict when its stage is
skipped or collapsed, and an advisory one reports a failure as a pass that
says so. `compass issue receipt` reads the records and shows the real verdict.

Reviewer identity is not authenticated. This is the same limit as
`human-approval`: a name in a field is a claim, not a proof.

## `compass evidence review`

```
compass evidence review CHECK --verdict pass|fail --reason TEXT --reviewer ID
                        [--scope TEXT] [--issue SLUG]
```

| Option | Meaning |
|---|---|
| `CHECK` | The id of a judged check in the issue's stored configuration |
| `--verdict` | `pass` or `fail` |
| `--reason` | What was read and why the verdict holds. It must not be empty |
| `--reviewer` | `agent`, `agent:<session id>` or a person's id |
| `--scope` | What the judgement covers (optional) |

The command digests the check's inputs as they are now, writes the record and
registers it. It exits 0 when it wrote the record and 2 when it did not. In
the second case it writes nothing. It exits 2 for:

- a check that does not exist, or is not of kind `judged`;
- a check that declares no `inputs`;
- an input that cannot be found;
- an empty reason or reviewer, or a verdict other than `pass` or `fail`;
- an issue with no stored configuration (run `compass approach evaluate
  --write`).

### `--json`

The `--json` document is a public contract, like the exit codes. A change to
a key or its order is a breaking change. This is the real output for the
example above; `at` and `definition_digest` vary and are shown as `...`.

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

`scope` and `generation` are absent when the record has none.

## A project with no judged check

Nothing changes. No record is read, the manifest is not touched and the output
of `compass check`, `compass next` and the receipt is the same. The shipped
default names no judged check in any list.

## Limits

- Roles in `reviewers` are not resolved.
- Reviewer identity is not authenticated.
- A `human` check still reads a tick. `approvers:` and the human-approval
  lookup are a later increment.
- A check of kind `evidence` is not evaluated, and a blocking one fails.
