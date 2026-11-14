# The artifact catalog

**Removed in 9.0.0 (ADR-091).** Compass 9.0.0 needs and checks one document,
`acceptance-criteria.md`, so it has no artifact catalog. This page records
the catalog of 8.x, because archived issues and their stored generations
read it.

## What 9.0.0 does

- The shipped default declares an empty `artifacts:` map.
- A project `artifacts:` key is left out of the merge. `compass policy lint`
  names it (`L-SETTING-REMOVED`).
- Compass writes, registers and renders no other document. A team can keep
  its own notes.
- These commands are removed and refuse with a line that names ADR-091:
  `compass issue template show`, `compass issue artifact set` and `compass
  issue artifact-path`.
- The checks `contracts-declared`, `artifacts-approved` and
  `design-within-word-ceiling` are removed.

`governance/artifacts-8.0.4.yml` keeps the catalog 8.0.4 shipped, byte for
byte. Three readers use it:

| Reader | Use |
|---|---|
| `artifact_kinds.shipped()` | Fills the missing fields of a stored entry |
| `compass issue migrate` | Maps file names to kinds |
| `nfr-rows-resolved` | Reads the sections of the acceptance criteria when a stored generation declares none |

## The fields of a kind

| Field | Needed | What it holds |
|---|---|---|
| `file` | yes | The document's filename, with no directory. `<n>` marks a kind that repeats, such as `review-<n>.md`. `<unit>` marks a kind written once for each work unit; only such a kind can hold one folder, such as `low-level-design/<unit>.md` |
| `stage` | yes | The stage that owns the document |
| `owner` | yes | The role that writes it, such as `planner` |
| `audience` | yes | One line: who reads the document and what they decide from it |
| `stands_for` | yes | The name the industry uses for this kind of document, such as `prd` or `hld` |
| `sections` | yes | The headings for each depth: a map from `lightweight` or `thorough` to an ordered list of heading texts |
| `depends_on` | no | The kinds this one depends on. Nothing reads it |
| `required_when` | no | A condition under which the document is owed: `subtasks: {min: N}` |
| `every_approach` | no | When true, every approach owes the kind |
| `word_ceiling` | no | The word limit for each depth: a whole number of at least 1. Nothing reads it |

In 8.x, `compass policy lint` reported as an error:

- a kind that lacks a needed field;
- a `word_ceiling` that is not a map, a limit that is not a whole number of
  at least 1, or a depth the kind's `sections` does not list;
- a `file` that holds both `<n>` and `<unit>`, a placeholder written twice,
  or a folder in a name with no `<unit>`;
- an empty `sections` list, except for a kind whose template holds no `## `
  heading and exactly one rendered block (`verification-note`).

## Sections read by name

Four sections were read by name, so a checker found them whatever number an
older document gave them:

| Section | Kind | Read by |
|---|---|---|
| Non-functional requirements | `acceptance-criteria` | The check `nfr-rows-resolved` (still live) |
| Data and interfaces | `technical-design` | The check `contracts-declared` |
| Verification plan | `technical-design` | The `coverage` block, which added a Kind column when the heading was present |
| Risks and dependencies | `technical-design` | The `dependencies` block under its risk table |

Other facts about the 8.x skeleton:

- Each document opened with a `document-header` block of six lines
  ([rendered blocks](https://github.com/ayeo-io/compass/blob/main/docs/rendered-blocks.md)). `verification-note` had none.
- The headings were `sections[<depth>]`, in order, with no numbers.
- A template marked a section the author could leave out with
  `<!-- compass:optional -->` under its heading. An optional heading was not
  listed in `sections`.

## Word limits

| Kind | `thorough` | `lightweight` |
|---|---|---|
| `technical-design` | 4,000 | 1,200 |
| `acceptance-criteria` | 5,000 | 1,500 |

No other kind had a limit. In 8.x, `compass issue lint` printed a note for a
document over its limit, and `design-within-word-ceiling` refused a
technical design over 1.5 times its limit once plan exit was due.

## What an archived issue's registry can hold

| Shape | Rule in 8.x |
|---|---|
| A kind that repeats (`review-<n>.md`) | One entry for each round, each with its own id, status and path, and a `round` read from the filename. Rounds count from 1 with no leading zero. |
| A kind for each work unit (`low-level-design/<unit>.md`) | One entry for each unit, with a `unit` key and the id `ART-LOW_LEVEL_DESIGN-U<n>`. A unit is `U` and a whole number from 1 with no leading zero. The units are the rows of the technical design's Work units table. |
| The home of a document | `docs/compass/<created>-<slug>/<file>` and no other path |
| A voluntary kind | No approach owed it: `review`, `architecture-notes`, `product-owner-review`, `positioning` and `low-level-design` |
| An owed kind | From 7.0.0 the regular approach owed `requirements-review` at `lightweight`, and the hotfix approach owed `bug-report` at `thorough`. An issue assessed earlier owes neither. |
| `delivery-approach` | `every_approach: true`: registered for each approach as a draft with a depth and no path |
| `distribution-map` | `required_when: {subtasks: {min: 2}}`. The count is the length of the manifest's `subtasks:` list, else the units on the map's `units:` line (`units: 2` or `units: [U1, U2]`). While the condition was false, readers showed `not needed: one subtask`, `not needed: one unit` or `not needed: no subtasks recorded`. |
| A design decision | A `Scope:` line, `issue` or `project`. In 8.x, ship refused a project-scoped decision that no record in `architecture/decisions/` named (ADR-072). |
| A spike conclusion | A `spike-conclusion` evidence record with a decision: `discard`, `graduate-to-delivery` or `defer`. In 9.0.0, `compass evidence add --type spike-conclusion --decision <d> --next-issue <slug>` writes it. |
| The quick-fix record | A delivery-approach record with the headings Assessment, Policy rules fired, Acceptance strategy, Advice, Intent, Scenario and De-scope ledger, and no `**Approach:**` line |

`compass issue migrate` keeps a distribution map that says `units: 1`.

## Files that match no kind

`NOT_AN_ARTIFACT` in `cli/compass_pkg/stable_ids.py` lists the names the
process wrote that are no kind. `compass issue migrate` reads it:

`README.md`, `devlog.md`, review briefs, subtask assignments and briefs, a
builder's hand-back (`result.md` and `result-subtask-<n>.md`),
`architect-ruling.md`, `recommendation.md`, `released-verbs-v5.6.0.md`,
`compare.md`, `report.md` and `*.v6.bak`.

## Justifications

This part is live in 9.0.0 (`cli/compass_pkg/justifications.py`).

The manifest's `justifications` key holds one line for each assessed
dimension of type `enum` or `ordered-enum`: risk, familiarity, size, goal
and urgency. It sits beside `assessment`, never inside it.

- `compass approach evaluate --write --justify DIM=TEXT` merges the flags
  over the stored key.
- It refuses, names each dimension and writes nothing when a value is new or
  changed since the last evaluation and has no justification.
- An unchanged value keeps its recorded line.
- `compass quick-fix start` writes the key from the reasons it is given. It
  refuses a `--goal` without a reason. A `--goal` left out records no value,
  and readers show `not assessed`.
- Role is not an assessment dimension (ADR-070). `quick-fix start --role` is
  refused as an unknown flag, and `--justify role=` as a dimension that
  needs no justification (ADR-098).
