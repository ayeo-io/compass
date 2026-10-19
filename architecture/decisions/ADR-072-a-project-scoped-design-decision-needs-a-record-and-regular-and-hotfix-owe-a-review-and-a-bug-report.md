---
id: ADR-072
title: A project-scoped design decision needs a decision record before it lands, and the regular and hotfix approaches owe a review and a bug report
status: proposed
date: 2026-10-18
supersedes: ''
superseded_by: ''
---

Proposed by the planner for design-scope-review-and-bug-report on 2026-10-18, from ayeo-io/compass-delivery-record#32, "Add design-decision scope, a regular-approach review and a hotfix bug report".

## Context

A technical design records its decisions as `DD-1`, `DD-2` and so on. Some of them settle a question for the whole project, such as which module owns a rule. When the issue closes, the decision stays in that issue's design, and the next issue that meets the question does not find it in `architecture/decisions/`.

Two approaches also lack a document they need:

- The regular approach runs a lightweight refine stage but owes no requirements review, so the review leaves no file. One regular issue in forty had one on 10 October 2026.
- The hotfix approach owes no bug report, so its reproduce-first define stage writes a failing test with nothing to check it against.

Two earlier decisions bound the answer:

- ADR-036: an issue runs against its stored generation, and a CLI upgrade never changes an open issue.
- ADR-037: a configuration change is classified by its effect, and an added obligation is a tightening.

## Decision

1. Each design decision carries a scope line, `Scope: issue` or `Scope: project`. The technical design template asks for it, and the architecture notes propose which decisions are project-scoped.
2. A landing refuses an open issue whose registered technical design holds a decision scoped `project` that no record in `architecture/decisions/` names. The refusal is an entry of the landing refusals that `compass ship-commit` and `compass quick-fix finish` run before they stage anything. Its code is `project-decision-unrecorded`, and it names the path the next `compass adr new` would write.
3. A record names a decision in one of two ways:
   - the decision's block cites an ADR id whose file is in `architecture/decisions/`;
   - a file there holds both the issue's slug and the decision id.
   A citation of a record that does not exist does not count.
4. A decision with no scope line is not refused. No design written before 7.0.0 has one.
5. The shipped default owes `requirements-review` at depth `lightweight` on the regular approach, with three sections: Self-QA of the spec, Ambiguity ledger and Gate, which holds the Definition of Ready. It owes `bug-report` at depth `thorough` on the hotfix approach, and keeps `acceptance-criteria` at `lightweight` there.

## Alternatives considered

- **A check under a gate in `guardrails.yml`.** It needs a check id, a corpus, a version lock and a gate on each approach, for a rule that matters only at landing. Rejected.
- **A lint note for an unrecorded decision.** It does not stop the landing, which is what the requirement asks. Rejected.
- **A stored-configuration field that turns the refusal on, as `release_line` does.** The refusal fires only on a declared `Scope: project`, and no design in the archive declares one, so no open issue meets it unasked. Rejected as a field with nothing to decide.
- **An artifact rule for the two documents.** A rule fits a condition on the assessment. These documents are owed by every issue of the approach. Rejected.
- **Moving `bug-report` to the define stage.** It would change when every project's bug report is due. The report states the defect at intake, and define writes the failing test against it. Rejected.

## Consequences

- A design that declares a project-scoped decision cannot land until its record exists.
- A new regular issue cannot land until its requirements review is approved, and a new hotfix until its bug report is approved. An issue assessed before 7.0.0 keeps its stored generation and owes neither.
- A project with the `entry-exit-evaluation` capability on owes the seven Definition of Ready records at plan entry on each new regular issue, because the regular approach now lists `requirements-review`.
- An author can leave the scope line out and pass. The architect's notes are where a project-wide decision is caught.

## References

- ADR-036, ADR-037.
- `cli/compass_pkg/decision_scope.py`, `cli/compass_pkg/refusals.py`, `governance/presets/default/approaches.yml`, `governance/presets/default/artifacts.yml`.
