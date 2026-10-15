# The artifact catalogue

The artifact catalogue describes each kind of document a process writes. A tool reads the description to print a skeleton, to list the kinds and to check a configuration. This page owns the catalogue's fields, the skeleton that `compass issue template show` prints, the rounds of a kind that repeats, the home of each document and the table of shipped kinds.

The catalogue is the `artifacts:` map in `governance/presets/default/artifacts.yml`. A project or a preset adds a kind in its own `artifacts:` map with the same fields.

## The fields of a kind

| Field | Needed | What it holds |
|---|---|---|
| `file` | yes | The document's filename, with no directory. `<n>` marks a kind that repeats, such as `review-<n>.md` |
| `stage` | yes | The stage that owns the document: a stage id of the stages catalogue |
| `owner` | yes | The role that writes it: an agent id in `agents/`, or a value of the `role` dimension |
| `audience` | yes | One line saying who reads the document and what they decide from it |
| `stands_for` | yes | The name the industry uses for this kind of document, such as `prd` or `hld` |
| `sections` | yes | The headings per depth: a map from `lightweight` or `thorough` to an ordered list of heading texts |
| `depends_on` | no | The kinds this one is checked against for freshness. Empty when absent |
| `required_when` | no | A condition under which the document is owed. Today `subtasks: {min: N}` |
| `every_approach` | no | When true, every approach owes the kind |

`compass policy lint` reports a kind that lacks a needed field, or holds a malformed value, as an error. A list in `sections` can be empty only for a kind whose template holds no `## ` heading and exactly one rendered block. `verification-note` is the one shipped kind like that.

## The skeleton

`compass issue template show <kind> [--depth D]` prints the skeleton of a kind. The catalogue entry gives the header and the headings, and `templates/<kind>.md` gives the prose under each heading.

- The header is a `document-header` block of six lines (see `docs/rendered-blocks.md`): the issue and approach, the stage and owner, the status, the date, what the document reads and the audience line. `template show` prints the kind's real stage, owner and audience, the issue's slug when one is selected, and a `{{...}}` placeholder for the rest. The home path and the traditional name are not in the header; the table below and the glossary hold them.
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

The role guide (`How each role reads the spec`) lives in `docs/roles-guide.md`; no template and no section list holds it. Both checks are blocking, sit in no gate and decline to judge an archived issue: see `governance/guardrails.md`.

`tests/test_artifact_catalogue_fields.py` compares each template's unmarked headings with `sections.thorough`, and checks that `sections.lightweight` is an ordered subset of it. A `{{...}}` token in a template heading and a `<...>` token in the catalogue count as the same placeholder.

## Documents that repeat

A kind repeats when its `file` holds `<n>`, as `review-<n>.md` does. The registry holds one entry per round, each with its own id, status and path, and a `round` read from the filename. Rounds count from 1 and carry no leading zero.

- `compass issue artifact set review --path docs/compass/<created>-<slug>/review-2.md` registers round 2. Registering the same round again updates its entry and adds no new one.
- `--round N` names an existing round when no path is given.
- A path that is not `review-<n>.md` is refused, and the refusal names the pattern.
- `compass issue artifact-path review` prints the latest round. `--round N` prints one.
- `compass check`, the issue page, the board panel and the receipt each list every round. A finding names the round and its entry id.

A kind that no approach, rule or `every_approach` flag names is voluntary: nothing owes it, and a person registers it when it is written. Today `review`, `bug-report`, `architecture-notes`, `product-owner-review` and `positioning` are voluntary. `compass issue artifact set` accepts any kind the issue's catalogue declares, and `compass approach evaluate --write` never marks a voluntary entry `superseded`.

## One home for every kind

`compass issue artifact set --path` accepts only `docs/compass/<created>-<slug>/<file>`, where `<file>` is the kind's `file` (with the round in it for a kind that repeats). The refusal names the kind and its home. The rule reads the catalogue, so a kind a project adds has the same home.

## Files that match no kind

`compass issue lint` reports each top-level `.md` file in the documents folder whose name matches no kind's `file` and is not on the not-an-artifact list. A kind is one the issue's configuration declares or one the shipped default declares: an issue stored on an earlier generation keeps that generation's catalogue, and the migrate names files for the shipped kinds. The report is one line for each file, and it does not change the exit code.

The not-an-artifact list is `NOT_AN_ARTIFACT` in `cli/compass_pkg/stable_ids.py`. It holds the names and patterns that the process writes but that are no kind: `README.md`, `devlog.md`, review briefs, subtask assignments and briefs, a builder's hand-back (`result.md` and `result-subtask-<n>.md`), `architect-ruling.md`, `recommendation.md`, `released-verbs-v5.6.0.md`, `compare.md`, `report.md` and `*.v6.bak`. The migrate reads the same list.

## Documents owed only under a condition

An entry can carry `required_when: {subtasks: {min: 2}}`. The shipped `distribution-map` does. One function, `artifact_owed.owed()`, decides whether the issue owes such a document, and `compass check`, the issue page, the board panel and the receipt all ask it. The subtask count is the length of the manifest's `subtasks:` list, and an absent list counts as zero.

While the condition is false, `artifacts-approved` does not judge the document, and the readers show `not needed: one subtask` or `not needed: no subtasks recorded` where it has no file. A document that a person recorded as `omitted` keeps its reason and never reads "not needed". A document written anyway shows its own status. `compass next` is unchanged: a written or omitted map still marks breakdown done.

## The delivery-approach record on every approach

The `delivery-approach` entry carries `every_approach: true`, so `compass approach evaluate --write` registers it for each approach as a draft with a depth and no path. The depth is the approach's mode for the `assess` stage when that mode is an artifact depth, else `lightweight`. The quick fix and the spike name the kind themselves and keep `lightweight`. The assess stage writes the file at the path `compass issue artifact-path delivery-approach` prints, in the issue's documents folder, then registers it with `compass issue artifact set delivery-approach --status draft --path <that path>`. Until the file exists, that verb prints the home for a registered entry that has no path.

## Justifications

The manifest's `justifications` key holds one line for each assessed dimension of type `enum` or `ordered-enum` (risk, familiarity, size, goal, role, urgency). It sits beside `assessment` and never inside it. `compass approach evaluate --write --justify DIM=TEXT` merges the flags over the stored key. It refuses, naming each dimension, when a value is new or changed since the last evaluation and has no non-blank justification, and it writes nothing. An unchanged value keeps its recorded line, or none on an issue that predates the key. `compass issue configure --commit` takes the same flag. `compass quick-fix start` writes the key from the reasons it is given, and refuses a `--goal` or `--role` without a reason. A `--goal` or `--role` left out records no value and no justification, and the readers show it as `not assessed`. `compass issue receipt` reads the key, and falls back to the assessment table of the record for an issue that has none.

## Closing a spike

`compass issue artifact set spike-conclusion --status draft --path <file> --decision <discard|graduate-to-delivery|defer>` registers the conclusion and writes the one `spike-conclusion` evidence record that the check `spike-conclusion-present` reads, naming the document. `graduate-to-delivery` needs `--next-issue <slug>`, the slug of the delivery issue. A second run with another decision updates the record. `--decision` on any other kind is refused. The check itself is unchanged.

## The rendered blocks of the record

`templates/delivery-approach.md` holds four rendered blocks in place of its tables: `assessment` (under The assessment), `policy-rules` (under Policy rules that fired), `stage-weights` (under Per-stage weight) and `gate-set` (under Gate set). `compass issue render` writes them from the manifest, and `rendered-blocks-current` fails at the verification stage when a reassessment leaves one stale. The four templates with a `## Gate` section hold blocks, not tick boxes: `plan-exit` in `technical-design.md`, `breakdown-exit` in `distribution-map.md`, and the existing `dor` and `dod` blocks. `docs/rendered-blocks.md` describes each kind.

## The quick-fix record

`compass quick-fix start` writes the delivery-approach record with its own short headings: Assessment, Policy rules fired, Advice, Intent, Scenario and De-scope ledger. After the title the record holds a `document-header` block. Under Assessment it holds an `assessment` block, and under Policy rules fired a `policy-rules` block, both filled by the render. The record has no `**Approach:**` line, because the header block names the approach. A record written before the blocks existed keeps its tables. They are not an ordered subset of the thorough headings. `sections.lightweight` describes the record a hotfix or a spike writes from the template.

## Measuring the archive

`scripts/measure-artifact-catalogue.py --root <copy>` reads a copy of an archive and prints the figures this catalogue was built to move. It only reads, but run it on a copy.

- With no flag, it gives the figures before the 7.0.0 migrate: the kinds declared, the kinds in use that the catalogue does not declare, the regular issues with the record in the documents folder, the regular issues with a stub distribution map, and the distinct review filenames. `--catalogue` reads the kinds from another `artifacts.yml`, and `--list-kinds FILE` writes the undeclared names.
- With `--after`, it gives the figures after the migrate: files in a documents folder that match no kind, regular issues that held a record before the migrate and lack it registered in the documents folder, other issues holding a record that is not registered there, regular issues with fewer than two subtasks that carry a map registered at lightweight depth, review filenames that are not `review-<n>.md`, and issues with two review files of one round. It names the issues behind each figure that is not zero. It also prints two counts that are not faults: regular issues that never had a record, for which the migrate writes none, and small maps the migrate adopted with no depth, which it keeps.

`--json` prints either set as JSON.

## The kinds

The table below is generated from the catalogue by `compass _derive-glossary`, which also writes the per-kind entries of `docs/glossary.md`. A test compares both files with a fresh generation. Change a kind in `artifacts.yml`, then regenerate.

<!-- compass:catalogue-table -->

| Kind | File | Stage | Owner | Traditional name | Who reads it |
|---|---|---|---|---|---|
| `delivery-approach` | `delivery-approach.md` | `assess` | router | project-plan | Anyone joining the issue reads it to see how much process the work gets and why. |
| `verification-note` | `verification-note.md` | `verify` | verifier | test-summary | The person who ships a quick fix reads it to see the scenario, its test and the gates on one screen. |
| `acceptance-criteria` | `acceptance-criteria.md` | `define` | spec-author | requirements | Every role reads it to agree the behaviour that will be built, and the builder turns each scenario into a test. |
| `technical-design` | `technical-design.md` | `plan` | planner | hld | A reviewer reads it to challenge the design before code is written. |
| `distribution-map` | `distribution-map.md` | `breakdown` | planner | work-breakdown | The orchestrator reads it to decide how many worktrees to start and which scenarios each one owns. |
| `verification-report` | `verification-report.md` | `verify` | verifier | test-report | The person who ships reads it to decide whether the evidence supports landing the change. |
| `intent` | `intent.md` | `assess` | product-owner | prd | The product owner and the spec author read it to agree which problem is solved and which outcome counts as success. |
| `requirements-review` | `requirements-review.md` | `refine` | spec-author | requirements-review | The planner and the person who asked read it to confirm every open question is settled before design starts. |
| `threat-model` | `threat-model.md` | `plan` | planner | threat-model | A security reviewer reads it to judge whether the risks to data and access are handled before the change lands. |
| `rollback-plan` | `rollback-plan.md` | `plan` | planner | rollback-plan | The person who runs a release reads it to know how to undo the change and whether that was rehearsed. |
| `launch-readiness` | `launch-readiness.md` | `verify` | product-marketer | release-readiness-review | The marketer and the person who ships read it to decide whether every public claim is backed by a passing scenario. |
| `ui-contract` | `ui-contract.md` | `define` | designer | ui-specification | The builder and the spec author read it to build the screens and states the designer specified. |
| `bug-report` | `bug-report.md` | `assess` | spec-author | bug-report | The assessor and the builder read it to reproduce the defect and size the fix. |
| `architecture-notes` | `architecture-notes.md` | `define` | architect | architecture-review | The spec author and the planner read it to keep the design inside the system's invariants. |
| `positioning` | `positioning.md` | `define` | product-marketer | positioning-statement | The marketer and the reviewer of claims read it to keep every public message tied to a scenario. |
| `product-owner-review` | `product-owner-review.md` | `plan` | product-owner | stakeholder-review | The planner reads it to confirm the design still delivers the intent before implementation starts. |
| `review` | `review-<n>.md` | `verify` | reviewer | review-record | The builder and the person who ships read each round to decide what must change before the work passes. |
| `spike-conclusion` | `spike-conclusion.md` | `verify` | builder | spike-report | The person who decides reads it to discard, graduate or defer the spike. |

Headings of each kind, in order:

- `delivery-approach`, thorough: The assessment; The composed candidate; Policy rules that fired; The final delivery approach; The de-scope ledger; Owed follow-ups; Human overrides; Confirmation
- `delivery-approach`, lightweight: The assessment; Policy rules that fired; The final delivery approach; The de-scope ledger
- `verification-note`, lightweight: no heading (one rendered block)
- `acceptance-criteria`, thorough: Summary; Intent links; Scenario group <letter> - <name>; Failure-mode scenarios; Non-functional requirements; Coverage ledger
- `acceptance-criteria`, lightweight: Summary; Intent links; Scenario group <letter> - <name>; Non-functional requirements; Coverage ledger
- `technical-design`, thorough: Approach; Design decisions (ADR-style); Data and interfaces; Verification plan; Risks and dependencies; Governance check; Work units; Gate
- `technical-design`, lightweight: Approach; Design decisions (ADR-style); Data and interfaces; Verification plan; Risks and dependencies; Governance check; Gate
- `distribution-map`, thorough: Work units; Independence analysis; Scenario-group → subtask mapping; Proposed worktree orchestration; The cap that applies; Gate
- `distribution-map`, lightweight: Work units; Independence analysis; Scenario-group → subtask mapping; Gate
- `verification-report`, thorough: Scenario acceptance results; Test suite evidence; Review dimensions; Gate decision; Failure modes de-scoped at define; Decisions taken for the user; Gate
- `intent`, thorough: Problem; Desired outcome; Success signals; Constraints; Non-goals; Internal FAQ; Affected roles; Intent-fidelity check (filled at the pre-plan gate)
- `requirements-review`, thorough: Self-QA of the spec; Governance QA of the spec; Ambiguity ledger; Gate
- `threat-model`, thorough: What are we working on?; What can go wrong?; What are we going to do about it?; Did we do a good enough job?
- `rollback-plan`, thorough: What breaks; How we go back; When this was last rehearsed
- `launch-readiness`, thorough: Claims-to-scenarios traceability checklist; What is checked vs. not; Voice & positioning check; Go / No-Go
- `ui-contract`, thorough: Surface; States; Interaction scenarios; Accessibility commitments; Handoff to define
- `bug-report`, thorough: Observed behaviour; Expected behaviour; Reproduction steps; Impact
- `architecture-notes`, thorough: System under change; Invariants to preserve; Boundary risks; Candidate decision records; Recommendations; Items for a person to decide; Notes for the planner
- `positioning`, thorough: Audience; Value proposition; Press release (working-backwards); Messaging - claims and their backing scenarios; Customer & internal FAQ; Honesty policy check (voice & positioning strategies); Handoff
- `product-owner-review`, thorough: Verdict; Success signals and measures; Scope beyond the intent; Findings; Product strategies; Needs a decision; Hand-back to the plan stage
- `review`, thorough: Scope; Verdict; Blocking; Not blocking; Security; Probes
- `spike-conclusion`, thorough: Question; What we learned; Decision; What this spike did not decide

<!-- /compass:catalogue-table -->
