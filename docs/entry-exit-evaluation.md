# Stage entry and exit lists

This page is the owning doc for the evaluation of a stage's `entry` and `exit`
lists. It states what the capability switches, when a list is due, how each kind of
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

The capability switches the shipped checks. The shipped default lists the seven
Definition of Ready checks as the `plan` entry and the seven Definition of Done
checks as the `verify` exit, and each says `requires: [entry-exit-evaluation]`.
With the capability off those fourteen are inactive, and the output of a
project that has added nothing is the same as before the capability existed.

A check a project adds to a list runs whatever the capability. A project that
wants its own check to wait for the capability writes
`requires: [entry-exit-evaluation]` on it. A list that names a check the
configuration does not define fails with "the check is not defined".

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
| `judged`, `evidence` | Not evaluated by this version. A blocking check of these kinds fails, so a list cannot pass by naming a check nothing reads. This holds whatever the capability, for a check a project adds, and `compass policy lint` warns (`M-LIST-KIND-UNEVALUATED`, exit code unchanged). The shipped default names none. |

An unchecked box that carries a typed tag (`(evidence: ...)` or
`(follow-up: ...)`) counts when the tag resolves, and the detail says
"deferred with" and the tag. A tag that does not resolve fails with the reason
`dod-evidence-typed` gives. Both checks call one function,
`checks.dod_tag_problems`, so a tag means one thing. An unchecked box with no
tag fails as "not ticked".

Each result goes through the judgement `compass check` gives a gate check, so
one check id has one verdict. A deterministic check that has nothing to inspect
follows its `on_skipped`. A check with `severity: advisory`, or a
`blocking_when` that does not match the issue's assessment, that fails is shown
as ADVISORY (status `advisory` in `--json`, counted in `advisory`, recorded as
`advisory` in `results.yml`) and does not fail the run.

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

A third case is not a skip. When a `human` check's document is missing and the
approach the issue was routed to does not list that document kind among its
artifacts, the route owes no such document, and the row is nothing to check,
for example "quick-fix owes no verification-report". The artifact set is read
from the configuration, so a project that adds `verification-report` to an
approach makes the Definition of Done owed there. A document the approach lists
and that is missing still fails with "not found". Note that the shipped regular
approach does not list `requirements-review`, so a regular issue with no
requirements review has nothing to check for the Definition of Ready.

## A check that an approach does not owe

A `when` on a check reads the assessment. Evaluation adds one derived key,
`ships`, whether the approach the issue was routed to ships. Each Definition of
Done check in the shipped default says `when: {ships: true}`, so a spike, which
does not ship, owes none of them and a delivery owes all seven. A project can
use `ships` in the `when` or `blocking_when` of its own checks and in the
`when` of a guardrail gate. The key adds no field to the
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

- The templates do not render from the lists, and the tag rule reads only the
  `Definition of Done` section of the verification report.
- A `human` check is a tick. `approvers:` are not read.
- `judged` and `evidence` checks are not evaluated.
- A tick is found by the text of the statement. A statement that differs from
  the box fails with "no checklist item".
