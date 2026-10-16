<!--
TEMPLATE: low-level-design.md
Role in the pipeline: the detail of one work unit, written by the planner at
the plan stage beside the technical design. There is one file per work unit
of the design's Work units table, at low-level-design/U<n>.md, registered
with `compass issue artifact set low-level-design --unit U<n> --path ...`.
The builder of that unit reads this file and its own scenarios, and nothing
of the other units.

The technical design keeps the approach, the decisions, the interfaces, the
verification plan, the risks and the Work units table. The signatures, the
contracts, the file plan and the unit's tests belong here, so the design stays
short enough to review.

Fill every {{PLACEHOLDER}}.
-->

# Low-level design {{UNIT}} - {{ISSUE_SLUG}}

<!-- compass:render document-header -->
<!-- /compass:render -->

## Signatures

{{Each new or changed function, class and constant this unit adds, with its signature.}}

## Contracts

{{What each interface promises: inputs, outputs, errors, and the rules a caller can rely on.}}

## File-level plan

{{Each file this unit changes or adds, and the change, as a table.}}

## Tests this unit writes

{{The test file this unit owns, each test by name, and the scenario id each one proves.}}
