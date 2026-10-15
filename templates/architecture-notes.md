<!--
TEMPLATE: architecture-notes.md
Role in the pipeline: advice to the spec author and the planner, written from
the architect's perspective at the define stage. It writes no scenario and
changes no other file. The planner answers each recommendation in the
technical design.

Cite the file, line or decision record behind every claim. Say what was
checked and what was not.

Fill every {{PLACEHOLDER}}.
-->

# Architecture notes - {{ISSUE_SLUG}}

<!-- compass:render document-header -->
<!-- /compass:render -->

## System under change

{{The modules, files and boundaries this issue touches, and what changes in each.}}

## Invariants to preserve

{{Each rule of the system the change must keep, with the decision record or file that states it.}}

## Boundary risks

{{Each place where the change crosses a boundary and could break a reader or writer on the other side.}}

## Candidate decision records

{{Each decision the plan should record as a decision record: its title and the question it settles.}}

## Recommendations

{{What the spec author and the planner should do, in order of importance.}}

## Items for a person to decide

{{Each question the architect cannot settle, with the options and the architect's recommendation.}}

## Notes for the planner

{{What the planner needs to know before writing the technical design.}}
