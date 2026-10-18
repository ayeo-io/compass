# Spec - design-scope-review-and-bug-report

<!-- compass:render document-header -->
> **Issue:** design-scope-review-and-bug-report · **Approach:** regular
> **Stage:** define · **Owner:** spec-author
> **Status:** approved
> **Date:** 2026-10-18
> **Reads:** [delivery-approach.md](delivery-approach.md), [intent.md](intent.md)
> **Audience:** Every role reads it to agree the behaviour that will be built, and the builder turns each scenario into a test.
<!-- /compass:render -->

## Summary

**Goal:** A decision that applies to the whole project cannot land without a decision record, a regular issue leaves a short requirements review, and a hotfix leaves a bug report.

**Approach:** Each design decision in `technical-design.md` gains a `Scope:` line, `issue` or `project`. A new landing refusal in `compass ship-commit` reads the registered design and refuses a project-scoped decision that no record in `architecture/decisions/` names. The shipped default preset gains `requirements-review: lightweight` on the regular approach, with a lightweight section list, and `bug-report: thorough` on the hotfix approach.

**Why now / what changes:** These are the last three requirements of the 7.0.0 document set, and the release waits for them. Afterwards an author sees a `Scope:` line in each decision block, a landing names the decision record it is missing, a new regular issue owes `requirements-review.md` and a new hotfix owes `bug-report.md`. An issue assessed before the change keeps its stored generation and owes neither document.

---

## Intent links

| Intent id | Source | Statement |
|---|---|---|
| INT-1 | intent.md desired outcome | A project-wide design decision cannot land without a decision record that names it. |
| INT-2 | intent.md desired outcome | A regular issue leaves a short requirements review. |
| INT-3 | intent.md desired outcome | A hotfix leaves a bug report. |

---

## Scenario group A - design-decision scope

**Independence note:** the landing refusal and the two templates; no preset change.

### Scenario: A project-scoped decision with no record is refused at landing
<!-- traceability id: DSR-1 · serves: INT-1 -->

```gherkin
Scenario: A project-scoped decision with no record is refused at landing
  Given a regular issue ready to ship whose registered technical design holds "DD-2" with "Scope: project"
  And no file in architecture/decisions/ names "DD-2" of the issue
  When the author runs compass ship-commit
  Then the command exits 2 with the code "project-decision-unrecorded"
  And the refusal names "DD-2" and the path architecture/decisions/ADR-<next number>-<title>.md to write
  And the manifest, the index and HEAD are as they were
```

### Scenario: A decision record that names the decision lets the issue land
<!-- traceability id: DSR-2 · serves: INT-1 -->

```gherkin
Scenario: A decision record that names the decision lets the issue land
  Given the issue of DSR-1
  When either "DD-2" cites "ADR-001" and architecture/decisions/ADR-001-<title>.md exists, or a file in architecture/decisions/ names both the issue's slug and "DD-2"
  Then compass ship-commit lands the issue with no decision-scope refusal
```

### Scenario: Issue-scoped and unscoped decisions are not refused
<!-- traceability id: DSR-3 · serves: INT-1 -->

```gherkin
Scenario: Issue-scoped and unscoped decisions are not refused
  Given a technical design whose decisions say "Scope: issue" or give no scope line
  When the author runs compass ship-commit
  Then no decision-scope refusal is given
```

### Scenario: The templates ask for the scope
<!-- traceability id: DSR-4 · serves: INT-1 -->

```gherkin
Scenario: The templates ask for the scope
  Given the shipped templates
  When compass issue template show technical-design prints the design decisions
  Then each decision block holds a "Scope:" line naming issue and project
  And the "Candidate decision records" section of architecture-notes.md asks the architect which decisions are project-scoped
```

---

## Scenario group B - the regular requirements review

**Independence note:** the preset and its generated views; shared with group C.

### Scenario: A new regular issue owes a lightweight requirements review
<!-- traceability id: DSR-5 · serves: INT-2 -->

```gherkin
Scenario: A new regular issue owes a lightweight requirements review
  Given a regular issue assessed on the shipped default
  When compass approach evaluate --write runs
  Then the registry holds one requirements-review entry at depth lightweight
  And the full approach still owes it at depth thorough
```

### Scenario: The lightweight review has three sections
<!-- traceability id: DSR-6 · serves: INT-2 -->

```gherkin
Scenario: The lightweight review has three sections
  When compass issue template show requirements-review --depth lightweight runs
  Then its headings are "Self-QA of the spec", "Ambiguity ledger" and "Gate"
  And the Gate section holds the rendered Definition of Ready block
```

---

## Scenario group C - the hotfix bug report

**Independence note:** the preset and its generated views; shared with group B.

### Scenario: A new hotfix owes a thorough bug report
<!-- traceability id: DSR-7 · serves: INT-3 -->

```gherkin
Scenario: A new hotfix owes a thorough bug report
  Given a hotfix assessed on the shipped default
  When compass approach evaluate --write runs
  Then the registry holds one bug-report entry at depth thorough
  And acceptance-criteria stays at depth lightweight
```

---

## Failure-mode scenarios

### Scenario: A cited record that does not exist does not count
<!-- traceability id: DSR-8 · serves: INT-1 -->

```gherkin
Scenario: A cited record that does not exist does not count
  Given "DD-2" with "Scope: project" cites "ADR-009"
  And architecture/decisions/ holds no ADR-009 file
  When the author runs compass ship-commit
  Then the landing is refused with the code "project-decision-unrecorded"
```

### Scenario: A project with no decisions folder is told the first record to write
<!-- traceability id: DSR-9 · serves: INT-1 -->

```gherkin
Scenario: A project with no decisions folder is told the first record to write
  Given a project with no architecture/decisions/ folder
  And a project-scoped "DD-1"
  When the author runs compass ship-commit
  Then the command exits 2 and the refusal names architecture/decisions/ADR-001-<title>.md
```

### Scenario: An issue assessed before the change owes neither document
<!-- traceability id: DSR-10 · serves: INT-2 -->

```gherkin
Scenario: An issue assessed before the change owes neither document
  Given a regular issue whose stored generation has no requirements-review in its artifacts
  When the author runs compass ship-commit with no requirements review written
  Then the command exits 0, and the registry holds no requirements-review entry
```

---

## Non-functional requirements

| Concern | Scenario | Reason it does not apply |
|---|---|---|
| performance | | The refusal reads one registered file and one folder listing; no new loop over issues. |
| capacity | | No stored data grows. |
| compatibility | DSR-10 | |
| security | | No new input crosses a trust boundary; the design path comes from the registry, which already refuses a path outside the project. |
| privacy | | No personal data is read or written. |
| operability | DSR-1, DSR-9 | |
| accessibility | | No user interface. |

---

## Coverage ledger

<!-- compass:render coverage -->
Coverage: 8 of 10 scenarios passed

| Scenario | Title | Kind | Tests | Red | Green | Acceptance | Result |
|---|---|---|---|---|---|---|---|
| DSR-1 | A project-scoped decision with no record is refused at landing | integration | `tests/test_design_scope_review_and_bug_report.py::test_dsr_1_project_decision_without_record_refused` | `red-DSR-1.json` | `green-DSR-1.json` | - | passed |
| DSR-2 | A decision record that names the decision lets the issue land | integration | `tests/test_design_scope_review_and_bug_report.py::test_dsr_2_record_naming_the_decision_lands` | - | - | - | no test record |
| DSR-3 | Issue-scoped and unscoped decisions are not refused | integration | `tests/test_design_scope_review_and_bug_report.py::test_dsr_3_issue_and_unscoped_decisions_not_refused` | `red-DSR-3.json` | `green-DSR-3.json` | - | passed |
| DSR-4 | The templates ask for the scope | unit | `tests/test_design_scope_review_and_bug_report.py::test_dsr_4_templates_ask_for_the_scope` | `red-DSR-4.json` | `green-DSR-4.json` | - | passed |
| DSR-5 | A new regular issue owes a lightweight requirements review | integration | `tests/test_design_scope_review_and_bug_report.py::test_dsr_5_regular_owes_lightweight_requirements_review` | `red-DSR-5.json` | `green-DSR-5.json` | - | passed |
| DSR-6 | The lightweight review has three sections | unit | `tests/test_design_scope_review_and_bug_report.py::test_dsr_6_lightweight_review_sections` | `red-DSR-6.json` | `green-DSR-6.json` | - | passed |
| DSR-7 | A new hotfix owes a thorough bug report | integration | `tests/test_design_scope_review_and_bug_report.py::test_dsr_7_hotfix_owes_thorough_bug_report` | `red-DSR-7.json` | `green-DSR-7.json` | - | passed |
| DSR-8 | A cited record that does not exist does not count | not planned | `tests/test_design_scope_review_and_bug_report.py::test_dsr_8_missing_cited_record_does_not_count` | `red-DSR-8.json` | `green-DSR-8.json` | - | passed |
| DSR-9 | A project with no decisions folder is told the first record to write | not planned | `tests/test_design_scope_review_and_bug_report.py::test_dsr_9_no_decisions_folder_names_first_record` | `red-DSR-9.json` | `green-DSR-9.json` | - | passed |
| DSR-10 | An issue assessed before the change owes neither document | integration | `tests/test_design_scope_review_and_bug_report.py::test_dsr_10_earlier_generation_owes_neither` | - | - | - | no test record |
<!-- /compass:render -->
