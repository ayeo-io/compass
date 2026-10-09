# Stage entry and exit lists

This page is the owning doc for the evaluation of a stage's `entry` and `exit`
lists. It states what the capability switches, when a list is due, how each kind of
check is judged, what `on_skipped` does, where the results show, and how the
document templates render the lists. The code is
`cli/compass_pkg/stage_lists.py` and, for the templates,
`cli/compass_pkg/template_lists.py`. `compass check`, `compass next` and
`compass issue receipt` read the first.

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
| `human` | A tick: a checked box (`- [x]`) whose text equals the check's `statement`, under the list's heading in the requirements review (entry lists) or the verification report (exit lists). The headings are in "Where a list sits in a document". With `approvers:` the tick also needs a current approval by a listed approver (see [Approvers on a human check](#approvers-on-a-human-check)). |
| `deterministic` | Its registered implementation runs. The receipt does not run it and shows `pending`. |
| `judged` | A review record: the newest registered `manual-review` record by a listed reviewer must say `pass` and match the check's inputs, definition, issue and generation. The cause of a failure is the first words of the detail. See [judged-checks.md](judged-checks.md). The receipt reads the record and shows the real verdict. |
| `evidence` | Not evaluated by this version. A blocking check of this kind fails, so a list cannot pass by naming a check nothing reads. This holds whatever the capability, for a check a project adds, and `compass policy lint` warns (`M-LIST-KIND-UNEVALUATED`, exit code unchanged). The shipped default names none. |

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

## Approvers on a human check

A `human` check can declare `approvers:`, a list of names. Then a tick or a
deferral tag alone does not clear it. It also needs a `human-approval` entry in
the issue's evidence registry that:

- names the check (`check: <id>`) and holds a decision, `approved` or
  `rejected`;
- holds `approver`, `role`, `scope` and `timestamp`;
- is by a listed approver (below);
- names this issue (`issue: <slug>`);
- names the issue's current generation (`generation: <n>`; both are none when
  the issue has none, and generation 0 is not none).

A record that fails any of these is set aside, so a record by someone else
cannot clear the check or block it. Of the records that remain, the newest
decides: a later rejection by a listed approver withdraws an approval, and a
later approval restores it. The row fails when no record remains. Its detail
starts with the cause (`no approval record`, `approver not listed`, `approval
is for another issue`, `approval is for another generation`, `approval
withdrawn`), shows the values it read and names the approvers who may approve.

A box must still be ticked: an approval does not replace the tick. A box
unticked with a resolving typed tag is a deferral, and a deferral does not
excuse a check that lists approvers, so it also needs a current approval. Both
tag forms (`evidence` and `follow-up`) behave the same. Without `approvers:`,
or with an empty list, a tick is enough and a deferral passes.

Who is listed. `owner` names the project's owner (the `owner:` of
`compass.yml`, the same name waivers use), and names nobody when the project
declares none. Any other entry is read as a person id, a role included, until
roles are resolved. The approver `agent` never matches.

What is not protected. An approver's name is not authenticated, the same limit
as every `human-approval` record. Anyone who can write `manifest.yml`, an
agent included, can add a record that names a listed person. Two guards exist:
`compass evidence approve` needs a terminal and refuses the approver `agent`.
They stop an agent session that calls the verb. They do not stop one that
edits the manifest.

### `compass evidence approve`

```
compass evidence approve --check ID --approver NAME --role ROLE --scope TEXT
                         [--decision approved|rejected] [--issue SLUG]
```

| Option | Meaning |
|---|---|
| `--check` | The id of a human check that lists approvers |
| `--approver` | The person's id. It must be listed by the check |
| `--role` | The role the person acts in |
| `--scope` | What the approval covers |
| `--decision` | `approved` (the default) or `rejected` |

The command stamps the issue, the issue's generation and the time, and
registers the record as `EV-APPROVAL-<check>-<n>`. It exits 0 when it wrote the
record and 2 when it did not. In the second case it writes nothing. It exits 2
for:

- no terminal on standard input, because an approval is a person's act and an
  agent session has no terminal;
- the approver `agent` (or `agent:<id>`), or an empty approver, role or scope;
- a check that does not exist, is not `human`, or lists no approvers;
- an approver the check does not list, because the record would not count;
- a decision other than `approved` or `rejected`.

The `--json` document is a public contract. A change to a key or its order is
a breaking change. This is the real output for the example above; `at` varies
and is shown as `...`. The key `answer` holds the decision.

```json
{
  "outcome": "compass evidence approve: sign-off - approved by jed72 recorded as EV-APPROVAL-sign-off-1.",
  "check": "sign-off",
  "answer": "approved",
  "evidence_id": "EV-APPROVAL-sign-off-1",
  "approver": "jed72",
  "role": "owner",
  "scope": "the plan",
  "issue": "feature",
  "generation": 1,
  "at": "...",
  "detail": [
    "record     : EV-APPROVAL-sign-off-1 in manifest.yml evidence",
    "issue      : feature",
    "generation : 1"
  ]
}
```

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

## Where a list sits in a document

A list sits under a heading in the document that holds its ticks: the
requirements review for an entry list and the verification report for an exit
list.

| List | Heading |
|---|---|
| `plan` entry | `Definition of Ready` |
| `verify` exit | `Definition of Done` |
| any other stage | `<Stage> <side> list`, for example `Implement exit list` or `Define entry list` |

The typed tag rule of `dod-evidence-typed` reads every exit list's section,
not only the Definition of Done. An unticked box under an exit heading needs a
typed tag that resolves, whichever stage the list belongs to. Entry lists have
no tag rule.

## Rendering the templates

The checklists of `templates/requirements-review.md` and
`templates/verification-report.md` render from the stage's lists in the issue's
effective view. `compass issue template show <kind> [--issue SLUG] [--json]` prints
the template of that kind (`requirements-review`, `verification-report` or any
other template) with its checklists rendered. `/compass:refine` and
`/compass:verify` write their documents from this output, not from the template
file. `--json` prints one object with the keys `kind`, `issue`, `source` and
`text`. `source` is `generation` (the issue's stored configuration), `live` (the
project's configuration now) or `none` (no configuration is read, so `text` is
the template file).

For each list, the rendered section holds one box for each `human` check the
list names, in the listed order:

- A check whose statement the template already words keeps the template's own
  text, bold label and tag included. A project with the shipped default
  therefore renders each template file byte for byte.
- A check the template does not word gets a generated line,
  `- [ ] <statement>`. In an exit list the line starts
  `(evidence: {{EV-id}})`, so the box can be deferred with a typed tag.
- A template box that no list names is left out.
- A list on a stage other than the two named ones renders as its own section
  under its heading, before the `Next stage:` line. A list with no `human`
  check adds no section.
- A check the list names more than once gives one box.

An exit list on `plan` or on any stage other than `verify` is always in the
verification report, and an entry list on any stage other than `plan` is always
in the requirements review. An exit list on `plan` renders into the
verification report as `Plan exit list`, although the report is written at
`verify`: the side of a list picks the document, not the stage.

A check of another kind has no box to tick and does not render. The render
reads neither `requires` nor `when`: the document shows what the configuration
lists, and evaluation decides what is owed. Any other template, and an issue
read without a configuration, render as the file. Rendering adds no line to a
default template. The line cap in `tests/test_borrowed_document_shapes.py`
covers the threat model and the rollback plan only, and rendering does not
change them.

The tick, the tag rule and the renderer read a section the same way
(`cli/compass_pkg/doc_sections.py`): it starts at a heading and ends at the next
heading or at a line that starts `Next stage:`, and a line inside an HTML
comment is not in any section. Only the text from `<!--` to `-->` is hidden,
so a box with a trailing comment is still a box. A stage id can hold a dot, so `Code.review exit
list` is an exit heading.

## Limits

- A role in `approvers:` other than `owner` is read as a person id. An
  approval record is not authenticated (see [Approvers on a human
  check](#approvers-on-a-human-check)).
- `evidence` checks are not evaluated.
- A tick is found by the text of the statement. A statement that differs from
  the box fails with "no checklist item".
