# Stage entry and exit lists

This page is the owning doc for the evaluation of a stage's `entry` and `exit`
lists. It states when evaluation is on, when a list is due, how each kind of
check is judged, what `on_skipped` does, and where the results show. The code
is `cli/compass_pkg/stage_lists.py`. `compass check`, `compass next` and
`compass issue receipt` read it.

## Switching it on

The capability `entry-exit-evaluation` is off in the shipped default. A
project turns it on in `compass.yml`:

```yaml
capabilities:
  entry-exit-evaluation: true
```

With it off, no command shows or runs a list, and the output is the same as
before the capability existed. A check in a list that says
`requires: [entry-exit-evaluation]` is inactive until the capability is on.
The shipped default lists the seven Definition of Ready checks as the `plan`
entry and the seven Definition of Done checks as the `verify` exit, and each
needs the capability.

An issue reads the capability from its stored generation (see
`docs/generation-store.md`). Turning it on changes nothing for an issue until
the next `compass approach evaluate --write`.

## When a list is due

`compass next` names the current stage. A list is due by its position:

| List | Due when |
|---|---|
| entry of a stage | the stage is the current stage, or the issue is past it |
| exit of a stage | the issue is past the stage |

A landed issue has every list due. `compass check` counts only due checks. The
receipt shows every list, and says which are not yet due.

## How a check is judged

| Kind | Judged by |
|---|---|
| `human` | A tick: a checked box (`- [x]`) whose text equals the check's `statement`, under the heading `Definition of Ready` in the requirements review (entry lists) or `Definition of Done` in the verification report (exit lists). |
| `deterministic` | Its registered implementation runs. The receipt does not run it and shows `pending`. |
| `judged`, `evidence` | Not evaluated by this version. A blocking check of these kinds fails, so a list cannot pass by naming a check nothing reads. |

An unchecked box that carries a typed tag (`(evidence: ...)` or
`(follow-up: ...)`) is not a tick for a `human` check. The existing check
`dod-evidence-typed` still reads those tags and runs as before.

A check with `severity: advisory`, or a `blocking_when` that does not match the
issue's assessment, reports a failure as a pass that says it is advisory.

## When a list is skipped, and `on_skipped`

A skipped check does not run. It gives the verdict its `on_skipped` names:

| `on_skipped` | Verdict |
|---|---|
| `fail` | fail |
| `not-applicable` | nothing to check |
| `pass` | pass |

A check is skipped in two cases:

- For a `human` check, the stage that produces its document is `skipped` or
  `collapsed`, or the document is recorded as deliberately omitted. That stage
  is the one before the listed stage for an entry list (refine, for the
  `plan` entry) and the listed stage for an exit list. This is why a collapsed
  refine makes the Definition of Ready not applicable.
- For any other kind, the listed stage is `skipped` or `collapsed`.

`on_skipped` answers "the stage was skipped". It does not say that a list does
not apply to an approach. A list does not depend on the stage's mode.

## A check that an approach does not owe

A `when` on a check reads the assessment. Evaluation adds one derived key,
`ships`, whether the approach the issue was routed to ships. Each Definition of
Done check in the shipped default says `when: {ships: true}`, so a spike, which
does not ship, owes none of them and a delivery owes all seven. A project can
use `ships` in the `when` of its own checks. The key adds no field to the
configuration, so the classifier compares it as it compares any `when`.

## Where results show

`compass check` adds one result for each due check, under a guardrail labelled
`stage:<stage>:<entry|exit>`. The results count in `ran`, `failed` and
`nothing_to_check` like any other, and a failure fails the run. In `--json`, a
row of `checks` has the same four keys as every other row: `guardrail`,
`name`, `status` (`pass`, `fail` or `nothing-to-check`) and `detail`. No key
is added to the output.

`compass next` appends `entry not met: <check ids>` to its line when the
current stage has failing entry checks.

`compass issue receipt` adds a "Stage lists" section before the verdict. Each
list is headed with its stage, its side and whether it is due. Each check shows
its id, its state (`pass`, `fail`, `nothing-to-check` or `pending`) and its
detail.

## Limits

- The templates do not render from the lists, and the typed tag does not apply
  to every exit list yet.
- A `human` check is a tick. `approvers:` are not read.
- `judged` and `evidence` checks are not evaluated.
- A tick is found by the text of the statement. A statement that differs from
  the box fails with "no checklist item".
