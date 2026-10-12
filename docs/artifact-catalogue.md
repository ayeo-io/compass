# The artifact catalogue

The artifact catalogue describes each kind of document a process writes. A tool reads the description to print a skeleton, to list the kinds and to check a configuration. This page owns the catalogue's fields, the skeleton that `compass issue template show` prints and the table of shipped kinds.

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

- The header holds the audience line, the stage, the owner, the home path and the traditional name.
- The headings are `sections[<depth>]`, in order.
- With no `--depth`, the depth is the one the issue registers the kind at, else `thorough`.
- A kind with no template prints its headings with no prose.
- A template that is not a catalogue kind (`devlog`, `incident` and `pull-request-body`) prints as the file. `--depth` on one is refused.

A template marks a section the author can leave out with the line `<!-- compass:optional -->` directly under its heading. The skeleton prints an optional section at `thorough`, in its template position, with `(optional)` after the heading. It prints none at `lightweight`. An optional heading is not listed in `sections`.

`tests/test_artifact_catalogue_fields.py` compares each template's unmarked headings with `sections.thorough`, and checks that `sections.lightweight` is an ordered subset of it. A `{{...}}` token in a template heading and a `<...>` token in the catalogue count as the same placeholder.

## The quick-fix record

`compass quick-fix start` writes the delivery-approach record with its own short headings: Assessment, Policy rules fired, Advice, Intent, Scenario and De-scope ledger. They are not an ordered subset of the thorough headings. `sections.lightweight` describes the record a hotfix or a spike writes from the template.

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

- `delivery-approach`, thorough: 1. The assessment; 2. The composed candidate; 3. Policy rules that fired; 4. The final delivery approach; 5. The de-scope ledger; 6. Owed follow-ups; 7. Human overrides; 8. Confirmation
- `delivery-approach`, lightweight: 1. The assessment; 3. Policy rules that fired; 4. The final delivery approach; 5. The de-scope ledger
- `verification-note`, lightweight: no heading (one rendered block)
- `acceptance-criteria`, thorough: Summary; How each role reads this file; Intent links; Scenario group <letter> - <name>; Failure-mode scenarios; Coverage ledger
- `acceptance-criteria`, lightweight: Summary; Intent links; Scenario group <letter> - <name>; Coverage ledger
- `technical-design`, thorough: 1. Approach; 6. Design decisions (ADR-style); 7. Governance check; 8. Work units; Gate
- `technical-design`, lightweight: 1. Approach; 6. Design decisions (ADR-style); 7. Governance check; Gate
- `distribution-map`, thorough: 1. Work units; 2. Independence analysis; 3. Scenario-group → subtask mapping; 4. Proposed worktree orchestration; 5. The cap that applies; Gate
- `distribution-map`, lightweight: 1. Work units; 2. Independence analysis; 3. Scenario-group → subtask mapping; Gate
- `verification-report`, thorough: 1. Scenario acceptance results; 2. Test suite evidence; 3. Review dimensions; 4. Gate decision; 5. Failure modes de-scoped at define; 6. Decisions taken for the user; Gate
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
