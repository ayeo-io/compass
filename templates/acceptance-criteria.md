<!--
TEMPLATE: acceptance-criteria.md
Produced by: the define stage (`/compass:define`); refined
             at requirements review (`/compass:refine`).
Lives at:    docs/compass/<created>-<issue-slug>/acceptance-criteria.md
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

Fill every {{PLACEHOLDER}}. Keep the Gherkin clean: one behaviour per
scenario, concrete Given/When/Then, no implementation detail.
-->
<!-- absorbed: "criteria, read by every role through its own perspective - and it is read" -->
<!-- absorbed: "test & review)." -->
<!-- absorbed: "BDD strategy: no code may exist that no scenario here describes." -->

# Spec - {{ISSUE_SLUG}}

> **Stage:** define · **Last updated:** {{DATE}} · **Owning agent:** spec-author
> **Familiarity:** {{greenfield discovery \| existing behaviour mapped first, then new scenarios}}

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

## How each role reads this file

<!-- Do not edit this block - it is the same on every spec. It is here so
     any role opening the file knows it is theirs too. -->

- **Product owner / manager** - reads for *intent fidelity*: do these scenarios deliver the outcome in `intent.md`?
- **Product marketer** - reads for *claims*: every line of launch copy must point at a scenario id here.
- **Engineer** - reads for *tests*: scenarios are the acceptance suite and seed the TDD red→green cycle.
- **QA** - reads for *coverage*: which scenarios are exercised, which edges are not.
- **Designer** - UI behaviour authored in `ui-contract.md` flows in here as scenarios.

---

## Intent links

<!-- The "→ intent" end of the traceability chain. Each id below is
     referenced by scenarios in the groups that follow. -->

| Intent id | Source | Statement |
|---|---|---|
| INT-1 | {{intent.md desired outcome \| ui-contract.md \| the issue description}} | {{one line}} |
| INT-2 | {{…}} | {{…}} |

---

## Scenario group A - {{NAME, e.g. "Export generation"}}

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

## Coverage ledger

<!-- Maintained continuously, not at the end. QA reads this at Verify. -->

| Traceability id | Serves intent | Has a failing test (implement) | Passes as acceptance (verify) |
|---|---|---|---|
| `TRC-A1` | INT-1 | {{[ ] / [x]}} | {{[ ] / [x]}} |
| `TRC-A2` | INT-1 | {{[ ]}} | {{[ ]}} |
| `TRC-B1` | INT-2 | {{[ ]}} | {{[ ]}} |
| `TRC-F1` | INT-1 | {{[ ]}} | {{[ ]}} |
