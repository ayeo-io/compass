# Requirements review - design-scope-review-and-bug-report

<!-- compass:render document-header -->
<!-- /compass:render -->

---

## Self-QA of the spec

- The ten scenarios do not contradict each other. DSR-1, DSR-8 and DSR-9 are the refusal's three cases; DSR-2 and DSR-3 are the cases it declines.
- Every outcome of `intent.md` has a scenario: INT-1 has seven, INT-2 three and INT-3 one.
- Every `Then` names an exit code, a refusal code, a heading or a registry entry.

## Governance QA of the spec

- The change adds an owed document to two approaches. Adding an obligation is a tightening, so no waiver is needed (`governance/routing-policy.md`, ADR-037).
- An issue assessed before the change runs against its stored generation and owes neither new document (ADR-036). DSR-10 covers it.
- The landing refusal uses the refusal registry's three-line shape (`cli/compass_pkg/refusals.py`).

---

## Ambiguity ledger

### Q1 - What counts as a record that names a decision

- **Question:** The requirement asks for an `architecture/decisions/ADR-*` file "naming" the decision. Decisions are numbered per issue, so `DD-2` alone is not unique across the project.
- **Resolution:** A project-scoped decision is recorded when its block in the design cites an ADR id whose file exists in `architecture/decisions/`, or when a file there names both the issue's slug and the decision id. A citation of a missing file does not count (DSR-8).
- **Decided by:** spec-author (agent)
- **Governance reference:** n/a
- **Spec change:** DSR-2 and DSR-8 state both forms.
- **Status:** resolved

### Q2 - A decision with no scope line

- **Question:** The requirement says every decision carries a scope. Should a decision with no scope line be refused?
- **Resolution:** No. Only a declared `project` scope is refused. Every design written before 7.0.0 has no scope line, and refusing those would block their landings. The template asks for the line, so new designs carry it.
- **Decided by:** spec-author (agent)
- **Governance reference:** ADR-036 (an issue runs against its stored generation)
- **Spec change:** DSR-3.
- **Status:** resolved

### Q3 - Whether the refusal waits for a stored-configuration field

- **Question:** The release-line refusal fires only when the issue's stored generation sets `release_line: true`. Does this refusal need a field like that?
- **Resolution:** No. It fires only on a decision that declares `Scope: project`, and no design in the archive declares one (checked with a search of `docs/compass/*/technical-design.md` on 18 October 2026). An author who writes the line asks for the check.
- **Decided by:** spec-author (agent)
- **Governance reference:** n/a
- **Spec change:** no spec change, clarification only
- **Status:** resolved

### Q4 - The stage of the bug report

- **Question:** The requirement says the reproduction is the define stage's record. The catalogue lists `bug-report` at stage `assess`.
- **Resolution:** The catalogue keeps `assess`. The report states the defect at intake, and the hotfix's reproduce-first define stage writes the failing test against it. Moving the stage would change when every project's bug report is due.
- **Decided by:** spec-author (agent)
- **Governance reference:** n/a
- **Spec change:** no spec change, clarification only
- **Status:** resolved

---

## Gate

### Definition of Ready

<!-- compass:render dor -->
<!-- /compass:render -->

Next stage: **plan** (`/compass:plan`).
