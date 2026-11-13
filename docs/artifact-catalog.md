# The artifact catalogue

**Removed in 9.0.0 (ADR-091).** Compass 9.0.0 needs and checks one document, `acceptance-criteria.md`, so it has no artifact catalogue. The shipped default declares an empty `artifacts:` map, and a project `artifacts:` key is left out of the merge and named by `compass policy lint` (`L-SETTING-REMOVED`). Compass writes, registers and renders no other document; a team can keep its own notes. The commands that printed a skeleton and registered a document are removed.

The rest of this page records the catalogue as 8.x declared it, because archived issues and their stored generations read it. The catalogue 8.0.4 shipped is kept byte for byte as `governance/artifacts-8.0.4.yml`. `artifact_kinds.shipped()` reads it to fill the missing fields of a stored entry, `compass issue migrate` reads it to map file names to kinds, and `nfr-rows-resolved` reads the sections of the acceptance criteria from it when a stored generation declares none.

## The fields of a kind

| Field | Needed | What it holds |
|---|---|---|
| `file` | yes | The document's filename, with no directory. `<n>` marks a kind that repeats, such as `review-<n>.md`. `<unit>` marks a kind written once per work unit, and only such a kind may hold one folder, such as `low-level-design/<unit>.md` |
| `stage` | yes | The stage that owns the document: a stage id of the stages catalogue |
| `owner` | yes | The role that writes it: a role name such as `planner`, or a value of the `role` dimension |
| `audience` | yes | One line saying who reads the document and what they decide from it |
| `stands_for` | yes | The name the industry uses for this kind of document, such as `prd` or `hld` |
| `sections` | yes | The headings per depth: a map from `lightweight` or `thorough` to an ordered list of heading texts |
| `depends_on` | no | The kinds this one depends on. Nothing reads it since 9.0.0 removed artifact freshness (ADR-091). Empty when absent |
| `required_when` | no | A condition under which the document is owed. Today `subtasks: {min: N}` |
| `every_approach` | no | When true, every approach owes the kind |
| `word_ceiling` | no | The word limit per depth: a map from a depth the kind's `sections` lists to a whole number of at least 1. See Word limits below |

`compass policy lint` reports a kind that lacks a needed field, or holds a malformed value, as an error. For `word_ceiling` that is a value that is not a map, a limit that is not a whole number of at least 1, and a depth the kind's `sections` does not list. For `file` it is a name that holds both `<n>` and `<unit>`, a placeholder written twice, and a folder in a name with no `<unit>`. A list in `sections` can be empty only for a kind whose template holds no `## ` heading and exactly one rendered block. `verification-note` is the one shipped kind like that.

## The skeleton

`compass issue template show <kind> [--depth D]` prints the skeleton of a kind. The catalogue entry gives the header and the headings, and `templates/<kind>.md` gives the prose under each heading.

- The header is a `document-header` block of six lines (see `docs/rendered-blocks.md`): the issue and approach, the stage and owner, the status, the date, what the document reads and the audience line. `template show` prints the kind's real stage, owner and audience, the issue's slug when one is selected, and a `{{...}}` placeholder for the rest. The home path and the traditional name are not in the header; `governance/artifacts-8.0.4.yml` holds them.
- The headings are `sections[<depth>]`, in order. A heading carries no number. The reading order is the list order, and a reader finds a section by its name.
- With no `--depth`, the depth is the one the issue registers the kind at, else `thorough`.
- A kind with no template prints its headings with no prose, after a `document-header` block. `verification-note` has no header block.
- A template that is not a catalogue kind (`devlog`, `incident` and `pull-request-body`) prints as the file. `--depth` on one is refused.

A template marks a section the author can leave out with the line `<!-- compass:optional -->` directly under its heading. The skeleton prints an optional section at `thorough`, in its template position, with `(optional)` after the heading. It prints none at `lightweight`. An optional heading is not listed in `sections`.

Four sections are named in the catalogue and read by name, so a checker finds them whatever number an older document gave them:

| Section | Kind | Read by |
|---|---|---|
| Non-functional requirements | `acceptance-criteria` | the check `nfr-rows-resolved` |
| Data and interfaces | `technical-design` | the check `contracts-declared` |
| Verification plan | `technical-design` | the `coverage` block, which adds a Kind column when the heading is present |
| Risks and dependencies | `technical-design` | the `dependencies` block under its risk table |

Both checks are blocking, belong to no gate and decline to judge an archived issue: see `governance/guardrails.md`.

`tests/test_artifact_catalogue_fields.py` compares each template's unmarked headings with `sections.thorough`, and checks that `sections.lightweight` is an ordered subset of it. A `{{...}}` token in a template heading and a `<...>` token in the catalogue count as the same placeholder.

## Word limits

A kind's `word_ceiling` sets the most words its document should hold at each depth. The shipped default sets two, and no other kind has one:

| Kind | `thorough` | `lightweight` |
|---|---|---|
| `technical-design` | 4,000 | 1,200 |
| `acceptance-criteria` | 5,000 | 1,500 |

- 9.0.0 removed the word count and the design-size check that read it (ADR-091). The field stays valid and nothing reads it.
- The field is an obligation field. An issue stored on a generation from before the field existed has no limit, because the reading of an earlier generation never fills the field from the shipped default. The classifier compares it by identity, as it compares `required_when`: a layer that changes a shipped kind's limit needs a waiver.
- `compass issue lint` prints a note for each registered document over its limit, naming the document, its count, the limit and the depth. The note never changes the exit code. It is silent on an issue with no `generation` key, a closed issue, a document registered with no path and a catalogue with no limit at the registered depth.
- The check `design-within-word-ceiling` refuses a technical design over 1.5 times its limit once plan exit is due. It belongs to no gate: see `governance/guardrails.md`.

## Documents that repeat

A kind repeats when its `file` holds `<n>`, as `review-<n>.md` does. The registry holds one entry per round, each with its own id, status and path, and a `round` read from the filename. Rounds count from 1 and carry no leading zero.

- `compass issue artifact set review --path docs/compass/<created>-<slug>/review-2.md` registers round 2. Registering the same round again updates its entry and adds no new one.
- `--round N` names an existing round when no path is given.
- A path that is not `review-<n>.md` is refused, and the refusal names the pattern.
- `compass issue artifact-path review` prints the latest round. `--round N` prints one.
- `compass check`, the issue page and the board panel each list every round. A finding names the round and its entry id.

## Documents per work unit

A kind is written once per work unit when its `file` holds `<unit>`, as `low-level-design/<unit>.md` does. A unit is `U` followed by a whole number from 1 with no leading zero, such as `U3`. The units are the rows of the technical design's Work units table.

- The registry holds one entry per unit, with a `unit` key and the id `ART-LOW_LEVEL_DESIGN-U<n>`.
- `compass issue artifact set low-level-design --unit U<n> --status draft --path docs/compass/<created>-<slug>/low-level-design/U<n>.md` registers unit `U<n>`. Registering the same unit again updates its entry and adds no new one.
- A unit such as `U0`, `U01` or `core` is refused, and so is a path that is not `low-level-design/<unit>.md` in the documents folder. The refusal names the pattern.
- `compass issue artifact-path low-level-design --unit U3` prints the home of unit 3. With no `--unit` it refuses when two or more units are registered, and names them.
- `compass check`, the issue page and the board panel list one line per unit.
- No approach names the kind, so `compass approach evaluate --write` registers no entry for it. The planner writes one file per unit at the plan stage and registers each one.
- On a full issue, `compass issue lint` prints a note for each Work units row with no registered low-level design. The note never changes the exit code.

The technical design keeps the approach, the decisions, the interfaces, the verification plan, the risks and the Work units table. The signatures, contracts, file plan and tests of each unit go in its low-level design. The template's Work units table has a Low-level design column, which links each unit's file on the full approach and holds a dash elsewhere. Unit stays the first column, so the distribution map reads the table as before.

## Design-decision scope

Each design decision of `technical-design.md` has a `Scope:` line, `issue` or `project`. A project-scoped decision binds later issues too, so `compass ship-commit` and `compass quick-fix finish` refuse an open issue whose registered design holds one that no record in `architecture/decisions/` names (`project-decision-unrecorded`, ADR-072). A record names the decision when the decision's block cites its ADR id and the file exists, or when the file holds both the issue's slug and the decision id. The refusal names the path the next `compass adr new` writes. A decision with no `Scope:` line is not judged. The value is read in any case and may be followed by punctuation or a dash and a reason, so `Scope: Project`, `Scope: project.` and `Scope: project - later issues follow it` all declare the project scope. Plain words after the value make the line prose, as in `Scope: project and more`; the decision then counts as unscoped, and `compass issue lint` prints a note that names the line and the accepted forms. The architect proposes the project-scoped decisions under Candidate decision records in `architecture-notes.md`.

## Owed and voluntary kinds

From 7.0.0 the regular approach owes `requirements-review` at `lightweight`: Self-QA of the spec, Ambiguity ledger and Gate, which holds the Definition of Ready. The hotfix approach owes `bug-report` at `thorough`. An issue assessed earlier keeps its stored generation and owes neither.

A kind that no approach, rule or `every_approach` flag names is voluntary: nothing owes it, and a person registers it when it is written. Today `review`, `architecture-notes`, `product-owner-review`, `positioning` and `low-level-design` are voluntary. `compass issue artifact set` accepts any kind the issue's catalogue declares, and `compass approach evaluate --write` never marks a voluntary entry `superseded`.

## One home for every kind

`compass issue artifact set --path` accepts only `docs/compass/<created>-<slug>/<file>`, where `<file>` is the kind's `file` (with the round in it for a kind that repeats, and the unit for a kind written per unit). The refusal names the kind and its home. The rule reads the catalogue, so a kind a project adds has the same home.

## Files that match no kind

`compass issue lint` reports each top-level `.md` file in the documents folder whose name matches no kind's `file` and is not on the not-an-artifact list. A kind is one the issue's configuration declares or one the shipped default declares: an issue stored on an earlier generation keeps that generation's catalogue, and the migrate names files for the shipped kinds. The report is one line for each file, and it does not change the exit code. Only the top level is read, so the files in `low-level-design/` are never reported.

The not-an-artifact list is `NOT_AN_ARTIFACT` in `cli/compass_pkg/stable_ids.py`. It holds the names and patterns that the process writes but that are no kind: `README.md`, `devlog.md`, review briefs, subtask assignments and briefs, a builder's hand-back (`result.md` and `result-subtask-<n>.md`), `architect-ruling.md`, `recommendation.md`, `released-verbs-v5.6.0.md`, `compare.md`, `report.md` and `*.v6.bak`. The migrate reads the same list.

## Documents owed only under a condition

An entry can carry `required_when: {subtasks: {min: 2}}`. The shipped `distribution-map` does. One function, `artifact_owed.owed()`, decides whether the issue owes such a document, and `compass check`, the issue page and the board panel all ask it. The count is the length of the manifest's `subtasks:` list when the manifest has that key, as a record written before 9.0.0 does. 9.0.0 records no subtasks (ADR-090), so with no such key the count is the units the registered distribution map declares on its `units:` line, `units: 2` or `units: [U1, U2]`: a map that declares two or more units is owed. No map, or a map with no `units:` line, counts as zero.

While the condition is false, `artifacts-approved` does not judge the document, and the readers show `not needed: one subtask`, `not needed: one unit` or `not needed: no subtasks recorded`. A document that a person recorded as `omitted` keeps its reason and never reads "not needed". A document written anyway shows its own status. `compass next` is unchanged: a written or omitted map still marks breakdown done.

## The delivery-approach record on every approach

The `delivery-approach` entry carries `every_approach: true`, so `compass approach evaluate --write` registers it for each approach as a draft with a depth and no path. The depth is the approach's mode for the `assess` stage when that mode is an artifact depth, else `lightweight`. The quick fix and the spike name the kind themselves and keep `lightweight`. The assess stage writes the file at the path `compass issue artifact-path delivery-approach` prints, in the issue's documents folder, then registers it with `compass issue artifact set delivery-approach --status draft --path <that path>`. Until the file exists, that verb prints the home for a registered entry that has no path.

## Justifications

The manifest's `justifications` key holds one line for each assessed dimension of type `enum` or `ordered-enum` (risk, familiarity, size, goal, urgency), as the configuration in force declares them, or the check set (`governance/check-set.yml`) when there is none. It sits beside `assessment` and never inside it. `compass approach evaluate --write --justify DIM=TEXT` merges the flags over the stored key. It refuses, naming each dimension, when a value is new or changed since the last evaluation and has no non-blank justification, and it writes nothing. An unchanged value keeps its recorded line, or none on an issue that predates the key. `compass quick-fix start` writes the key from the reasons it is given, and refuses a `--goal` without a reason. A `--goal` left out records no value and no justification, and the readers show it as `not assessed`. Role is not an assessment dimension from 7.0.0 (ADR-070). From 9.0.0, `quick-fix start --role` is refused as an unknown flag and `--justify role=` as a dimension that needs no justification (ADR-098).

## Closing a spike

`compass issue artifact set spike-conclusion --status draft --path <file> --decision <discard|graduate-to-delivery|defer>` registers the conclusion and writes the one `spike-conclusion` evidence record that the check `spike-conclusion-present` reads, naming the document. `graduate-to-delivery` needs `--next-issue <slug>`, the slug of the delivery issue. A second run with another decision updates the record. `--decision` on any other kind is refused. The check itself is unchanged.

## The distribution map's units line

A map can carry a `units:` line, `units: 1` or a list such as `units: [U1, U2]`. Before 9.0.0 registering a map on a multiagent breakdown read it, refused a map without it, and with `units: 1` recorded the breakdown as one subtask. 9.0.0 runs each issue in one session (ADR-090), so registering a map reads no `units:` line and records no subtask. `compass issue migrate` still keeps a map that says `units: 1`, as it did.

## The rendered blocks of the record

Before 9.0.0 the delivery-approach template held four rendered blocks in place of its tables: `assessment` (under The assessment), `policy-rules` (under Policy rules that fired), `stage-weights` (under Per-stage weight) and `gate-set` (under Gate set). `compass issue render` writes them from the manifest, and `rendered-blocks-current` fails at the verification stage when a reassessment leaves one stale. The four templates with a `## Gate` section hold blocks, not tick boxes: `plan-exit` in `technical-design.md`, `breakdown-exit` in `distribution-map.md`, and the existing `dor` and `dod` blocks. `docs/rendered-blocks.md` describes each kind.

## The quick-fix record

`compass quick-fix start` writes the delivery-approach record with its own short headings: Assessment, Policy rules fired, Acceptance strategy, Advice, Intent, Scenario and De-scope ledger. After the title the record holds a `document-header` block. Under Assessment it holds an `assessment` block, under Policy rules fired a `policy-rules` block and under Acceptance strategy an `acceptance-strategy` block, all filled by the render. The record has no `**Approach:**` line, because the header block names the approach. A record written before the blocks existed keeps its tables. They are not an ordered subset of the thorough headings. `sections.lightweight` describes the record a hotfix or a spike writes from the template.
