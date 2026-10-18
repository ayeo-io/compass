# Intent - design-scope-review-and-bug-report

<!-- compass:render document-header -->
> **Issue:** design-scope-review-and-bug-report · **Approach:** regular
> **Stage:** assess · **Owner:** product-owner
> **Status:** approved
> **Date:** 2026-10-18
> **Reads:** none
> **Audience:** The product owner and the spec author read it to agree which problem is solved and which outcome counts as success.
<!-- /compass:render -->

---

## Problem

A design decision that applies to the whole project can ship with no decision record. The technical design holds it, the issue closes, and the next issue that meets the same question cannot find it in `architecture/decisions/`.

Two approaches also lack a record they need. The regular approach runs a lightweight refine stage, but owes no requirements review, so the review leaves no file. The hotfix approach owes no bug report, so the reproduction its define stage writes has nothing to be checked against.

## Desired outcome

- INT-1: A design decision states whether it applies to the issue or to the project, and a project-wide decision cannot land without a decision record that names it.
- INT-2: A regular issue leaves a short requirements review: the self-QA, the ambiguity ledger and the Definition of Ready.
- INT-3: A hotfix leaves a bug report that its reproduction is checked against.

## Success signals

- `compass ship-commit` refuses an issue whose design holds a project-scoped decision with no decision record, and names the record to write.
- A new regular issue owes `requirements-review` at lightweight depth, and `compass issue template show requirements-review --depth lightweight` prints three sections.
- A new hotfix owes `bug-report` at thorough depth.

## Non-goals

- Deciding for the author which decisions are project-scoped. The architect proposes that in `architecture-notes.md`; a person decides.
- Changing an issue already assessed: it keeps its stored generation.
- Changing the stage modes of either approach.
