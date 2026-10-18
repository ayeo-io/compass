# Plan - design-scope-review-and-bug-report

<!-- compass:render document-header -->
> **Issue:** design-scope-review-and-bug-report · **Approach:** regular
> **Stage:** plan · **Owner:** planner
> **Status:** approved
> **Date:** 2026-10-18
> **Reads:** [delivery-approach.md](delivery-approach.md), [intent.md](intent.md), [acceptance-criteria.md](acceptance-criteria.md)
> **Audience:** A reviewer reads it to challenge the design before code is written.
<!-- /compass:render -->

---

## Approach

Three changes, built together because they share `docs/artifact-catalogue.md` and `docs/upgrade-7-0-0.md`, and the two preset changes share the generated views and their pins.

1. **Decision scope (group A).** A new module, `cli/compass_pkg/decision_scope.py`, holds one landing refusal. It reads the issue's registered `technical-design.md`, lists its decisions with `issue_page.design_decisions` (which already reads a `Scope:` line), and refuses a `project`-scoped decision that no record in `architecture/decisions/` names. `manifest.LANDING_REFUSALS` gains the entry, so `compass ship-commit` and `compass quick-fix finish` both run it before they stage anything. The refusal text lives in `refusals.py` under `project-decision-unrecorded`. The technical design template gains a `Scope:` line in each decision block, and the architecture notes template asks the architect which decisions are project-scoped.
2. **Regular requirements review (group B).** `governance/presets/default/approaches.yml` gives `regular.artifacts` the entry `requirements-review: lightweight`. `artifacts.yml` gives `requirements-review` a lightweight section list: Self-QA of the spec, Ambiguity ledger and Gate. The Gate section already holds the `dor` rendered block.
3. **Hotfix bug report (group C).** `hotfix.artifacts` gains `bug-report: thorough`. `acceptance-criteria: lightweight` stays.

The generated views (`governance/routing-policy.yml`, `governance/guardrails.yml`) are regenerated with raised versions, and the preset digests and content hashes are pinned again.

---

## Design decisions (ADR-style)

### `DD-1` - A landing refusal reads the decision scope from the registered design

- **Scope:** project
- **Context:** A project-wide decision recorded only in one issue's design is lost when the issue closes. The landing is the last point where Compass can ask for the record.
- **Decision:** A new entry of `manifest.LANDING_REFUSALS`, in its own module, reads the design through the registry and the existing decision parser. It declines on a closed issue, an issue with no registered design and a design with no project-scoped decision. This decision is recorded in ADR-071.
- **Alternatives considered:** A check in `guardrails.yml` under a gate. It would need a new check id, a corpus, a version lock and a gate change on every approach, for a rule that only matters at landing. A lint note. It would not stop the landing, which is the point of the requirement.
- **Consequences:** Every landing reads one more file. A design that declares `Scope: project` cannot land until its record exists.
- **Governance tie:** guardrail `G3` (traceability: a later issue finds the decision through its record).

### `DD-2` - A record names a decision by citation or by slug and id

- **Scope:** project
- **Context:** Decision ids restart at `DD-1` in each issue, so an id alone is not unique.
- **Decision:** A project-scoped decision is recorded when its block cites an ADR id whose file is in `architecture/decisions/`, or when a file there holds both the issue's slug and the decision id as whole words. The refusal names the path the next `compass adr new` would write: `ADR-<count + 1>-<decision title as a slug>.md`. This decision is recorded in ADR-071.
- **Alternatives considered:** Only the citation. A record written first, before the design names it, would then not count. Only the slug and id. Most designs already cite records by id.
- **Consequences:** A citation of a record that does not exist is refused, so a typo in an id does not pass.
- **Governance tie:** n/a

### `DD-3` - The two documents are preset values, and no new field gates them

- **Scope:** project
- **Context:** The release line needed a new approach field because its refusal had to know which issues owe a line. These two documents are ordinary owed artifacts.
- **Decision:** Add `requirements-review: lightweight` to `regular.artifacts` and `bug-report: thorough` to `hotfix.artifacts`. Owed artifacts already flow through the registry, `artifacts-approved` and the classifier, and an issue keeps its stored generation. This decision is recorded in ADR-071.
- **Alternatives considered:** A rule in `routing_guardrails.artifact_rules`. A rule fits a condition on the assessment; these hold for every issue of the approach.
- **Consequences:** A new regular issue cannot land until its requirements review is approved; a new hotfix, until its bug report is approved.
- **Governance tie:** ADR-036 (stored generation), ADR-037 (an added obligation is a tightening).

### `DD-4` - A decision with no scope line is not refused

- **Scope:** issue
- **Context:** No design written before this change has a scope line.
- **Decision:** Only `Scope: project` is refused. No lint note is added for a missing line, because `obligations.py` and `manifest.py` are at their size limits and the template already asks.
- **Alternatives considered:** A lint note for a decision with no scope. It can follow in a later issue.
- **Consequences:** An author can leave the scope out and pass. The architect's notes are where a project-wide decision is caught.
- **Governance tie:** n/a

---

## Data and interfaces

**Fields.**

| Name | Type | Required | Meaning | Written by | Read by |
|---|---|---|---|---|---|
| `Scope:` line in a `DD-n` block of `technical-design.md` | `issue` or `project` | no | Whether the decision applies to this issue or to the whole project | the planner | `issue_page.design_decisions`, `decision_scope.landing_refusal` |
| `approaches.regular.artifacts.requirements-review` | depth word | no | The regular approach owes a lightweight requirements review | the shipped preset | `routing.evaluate_route`, the classifier |
| `approaches.hotfix.artifacts.bug-report` | depth word | no | The hotfix approach owes a thorough bug report | the shipped preset | `routing.evaluate_route`, the classifier |
| `artifacts.requirements-review.sections.lightweight` | list of headings | no | The headings of a lightweight requirements review | the shipped preset | `compass issue template show`, `policy lint` |

**Contracts.**

| Inputs | Outputs | Exit codes | Errors |
|---|---|---|---|
| `decision_scope.landing_refusal(task, task_dir)` | the refusal text, or `None` | n/a (a function) | none raised: an unreadable design or decisions folder reads as nothing to judge |
| `compass ship-commit` on an issue with an unrecorded project decision | nothing staged or written | 2 | `Blocked: landing of issue '<slug>'`, naming the decisions and the record path, code `[project-decision-unrecorded]` |

---

## Verification plan

Kinds: `unit`, `integration`, `acceptance`, `judged review` and `manual`.

| Group | Kind | Fixture or environment |
|---|---|---|
| A | integration | a temporary git repository driven through `cli/compass`, as in `tests/test_intent_and_release_line.py` |
| DSR-4, DSR-6 | unit | the shipped templates through `compass issue template show` |
| B, C, DSR-10 | integration | a temporary repository assessed on the shipped default |

Not tested:
- The text of the upgrade notes - a reviewer reads it at verify.

---

## Risks and dependencies

| Risk | Likelihood | Effect | Addressed by |
|---|---|---|---|
| Tests that land a regular issue without approving every owed document now fail | high | the suite | DSR-5; those tests register the new document, as the regular intent change did |
| The refusal blocks this issue's own landing | low | this landing | ADR-071 is written and cited under DD-1 to DD-3 |
| An open issue's stored generation changes | low | open issues | DSR-10; ADR-036 |

Dependencies on other issues:

<!-- compass:render dependencies -->
None
<!-- /compass:render -->

---

## Governance check

| Area | Result | Evidence / note |
|---|---|---|
| Guardrails (the five defaults + project) | pass | Ten scenarios precede the code; each names its test; the refusal leaves the index as it was. |
| Method strategies (defaults + project) | followed | BDD and TDD apply; each scenario gets a red before its code. |
| Product strategies | followed | Delivers INT-1 to INT-3 of `intent.md`. |
| Voice & positioning strategies | n/a | No positioning document. |
| Routing policy | pass | The approach is built as computed except the breakdown, recorded in the de-scope ledger for a person to decide. |

---

## Work units

| Unit | Scenario group(s) it satisfies | Code surface it touches | Independent of | Low-level design |
|---|---|---|---|---|
| U1 | group A - DSR-1 to DSR-4, DSR-8, DSR-9 | `decision_scope.py`, `manifest.py`, `refusals.py`, two templates | shares two docs with U2 | - |
| U2 | groups B and C - DSR-5 to DSR-7, DSR-10 | the default preset, the generated views, their pins, `commands/refine.md` | shares two docs with U1 | - |

**Parallelism assessment:** the units share `docs/artifact-catalogue.md` and `docs/upgrade-7-0-0.md`, so the work is built solo.

---

## Gate

<!-- compass:render plan-exit -->
No exit checks are configured for the plan stage.
<!-- /compass:render -->

Next stage: **implement** on solo work.
