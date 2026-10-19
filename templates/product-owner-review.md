<!--
TEMPLATE: product-owner-review.md
Role in the pipeline: the product owner's check, at the plan stage, that the
design still delivers the intent. It reads intent.md, the acceptance criteria
and the technical design, and either lets the plan go to breakdown or sends
it back with findings.

Fill every {{PLACEHOLDER}}.
-->

# Product-owner review - {{ISSUE_SLUG}}

<!-- compass:render document-header -->
<!-- /compass:render -->

## Verdict

{{Pass or no pass on intent fidelity, and the one reason that decides it.}}

## Success signals and measures

{{Each success signal in intent.md, the scenarios and design elements that deliver it, and any signal nothing delivers.}}

## Scope beyond the intent

{{Anything the design builds that intent.md did not ask for, and whether it should stay.}}

## Findings

{{Each finding: what differs from the intent, where, and what would fix it.}}

## Product strategies

{{How the design meets each product strategy in the shipped strategies or your project's strategies file, if it has one, that applies.}}

## Needs a decision

{{Each question only the product owner or the maintainer can settle.}}

## Hand-back to the plan stage

{{What the planner must change before breakdown, or "nothing".}}
