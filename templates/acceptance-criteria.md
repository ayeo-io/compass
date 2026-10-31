<!--
TEMPLATE: acceptance-criteria.md
Role in the pipeline: The shared artifact. Every role reads the same
acceptance criteria from its own perspective. It is read twice: as the
specification when defined, and as the acceptance check at verify. It
satisfies the "Acceptance defined before it is built" guardrail (`G2`) via the
BDD strategy: every change to production code must be described by a
scenario here.

Scenarios are grouped by independence - that grouping seeds the
distribution map at the plan stage. Every scenario carries a traceability id
and a link back to the intent it serves - that is the traceability
guardrail at work.

Fill every {{PLACEHOLDER}}. Keep the Gherkin clean: one behavior per
scenario, concrete Given/When/Then, no implementation detail.
-->
<!-- absorbed: "criteria, read by every role through its own perspective - and it is read" -->
<!-- absorbed: "test & review)." -->
<!-- absorbed: "BDD strategy: no code may exist that no scenario here describes." -->

# Spec - {{ISSUE_SLUG}}

<!-- compass:render document-header -->
<!-- /compass:render -->

## Summary

<!-- WRITE THIS FIRST, and write it in prose. A reviewer opening a spec they
     did not write wants to know what is being built and why - not to
     reverse-engineer it from Gherkin. That synthesis is easy for the author
     and progressively harder for everyone else, which is where review quietly
     stops happening. This section is the write-for-a-cold-reader strategy
     applied to the criteria themselves.

     Three fields, in this order. Length scales with the delivery approach:
       quick fix   - one to two sentences per field.
       regular     - ordinary paragraphs.
       full        - up to 200 words per field, where the work warrants it.

     An unfilled field is caught twice: by the author's placeholder scan
     when the criteria are finished, and by the Definition of Ready at the
     foot of requirements-review.md, which will not let an empty Summary
     reach plan. -->

**Goal:** {{One sentence - what this change delivers, in user terms. Not the
implementation, not the ticket title.}}

**Approach:** {{Two to three sentences - the shape of the change, at the level
a role reviewer would want. Enough that a reader can predict roughly what the
scenarios below will cover.}}

**Why now / what changes:** {{One short paragraph - the visible outcome, and
what a user or an adjacent role would notice afterwards that they do not notice
today. If nothing observable changes, say so plainly and explain what does.}}

---

## Intent links

<!-- The "→ intent" end of the traceability chain. Each id below is
     referenced by scenarios in the groups that follow. -->

| Intent id | Source | Statement |
|---|---|---|
| INT-1 | {{intent.md desired outcome \| ui-contract.md \| the issue description}} | {{one line}} |
| INT-2 | {{…}} | {{…}} |

---

## Scenario group {{LETTER}} - {{NAME, e.g. "Export generation"}}

<!-- A group is a set of scenarios that touch disjoint code/surface from the
     other groups. Independent groups can become parallel subtasks in the
     distribution map. If everything is one group, that is fine - say so. -->

**Independence note:** {{what makes this group separable from the others - or "single group, no parallelism expected"}}

### Scenario: {{SCENARIO TITLE}}
<!-- traceability id: TRC-A1 · serves: INT-1 -->

```gherkin
Scenario: {{scenario title}}
  Given {{the starting context}}
  When {{the action or event}}
  Then {{the observable outcome}}
  And {{any further observable outcome}}
```

<!-- For one behavior over several values, open the fence with
     `Scenario Outline:` and end it with an `Examples:` table. A fence with
     no scenario line takes its title from the heading above it. -->

### Scenario: {{SCENARIO TITLE - a realistic edge}}
<!-- traceability id: TRC-A2 · serves: INT-1 -->

```gherkin
Scenario: {{scenario title}}
  Given {{…}}
  When {{…}}
  Then {{…}}
```

---

## Scenario group B - {{NAME}}
<!-- compass:optional -->

**Independence note:** {{…}}

### Scenario: {{SCENARIO TITLE}}
<!-- traceability id: TRC-B1 · serves: INT-2 -->

```gherkin
Scenario: {{scenario title}}
  Given {{…}}
  When {{…}}
  Then {{…}}
```

---

## Failure-mode scenarios

<!-- The failure modes that matter, per the approach's test-surface target.
     Quick fix: the obvious edges only. Regular and up: the failure modes
     that matter. Critical risk: adversarial and boundary inputs too. -->

### Scenario: {{FAILURE MODE TITLE}}
<!-- traceability id: TRC-F1 · serves: INT-1 -->

```gherkin
Scenario: {{scenario title}}
  Given {{…}}
  When {{the thing that goes wrong}}
  Then {{the system's correct, safe response}}
```

---

## Non-functional requirements

<!-- One row for each of the seven concerns, in this order. Resolve a row one of
     two ways:
       - name the scenario ids that cover it in the Scenario column, comma
         separated. At thorough depth the Then line of each scenario states a
         number, such as "within 3 seconds", so the requirement can be tested;
       - or write a reason it does not apply in the last column.
     A row left as a placeholder is open. `compass check` fails a spec with an
     open row. Add a row for a concern of your own below the seven. -->

| Concern | Scenario | Reason it does not apply |
|---|---|---|
| performance | {{scenario ids, e.g. TRC-A1}} | {{or the reason it does not apply}} |
| capacity | {{…}} | {{…}} |
| compatibility | {{…}} | {{…}} |
| security | {{…}} | {{…}} |
| privacy | {{…}} | {{…}} |
| operability | {{…}} | {{…}} |
| accessibility | {{…}} | {{…}} |

---

## Coverage ledger

<!-- Written by `compass issue render` from the scenarios and the red and green records in
     the manifest. Do not edit between the markers: the next render replaces it. -->

<!-- compass:render coverage -->
<!-- /compass:render -->
