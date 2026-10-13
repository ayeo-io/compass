<!--
TEMPLATE: ui-contract.md
Role in the pipeline: the designer's artifact, written through `/compass:design`. The designer feeds INTO
Define - UI behaviour here is authored as Given/When/Then scenarios so it
flows directly into acceptance-criteria.md as scenarios, not as a separate track.
That is how the designer is a full participant in the pipeline and not a
downstream consumer. Accessibility commitments here are checked against the
project's accessibility strategy, if governance/strategies.md has one.

Fill every {{PLACEHOLDER}}. Write behaviour as scenarios - the same Gherkin
shape the spec uses - so the handoff into the define stage is mechanical.
-->

# UI Contract - {{ISSUE_SLUG}}

> **Author:** {{DESIGNER NAME}} · **Date:** {{DATE}}
> **Feeds into:** acceptance-criteria.md (the scenarios below become spec scenarios)
> **Governance check:** accessibility commitments honour the project's accessibility strategy, if `governance/strategies.md` has one.

---

## Surface

<!-- What user-facing surface this covers: the screen, component, or flow.
     One contract per coherent surface. -->

{{SURFACE DESCRIPTION}}

## States

<!-- Every distinct state the surface can be in. Each state is something a
     scenario will land in or assert. -->

| State | What the user sees | How it is reached |
|---|---|---|
| {{e.g. empty}} | {{…}} | {{…}} |
| {{e.g. loading}} | {{…}} | {{…}} |
| {{e.g. populated}} | {{…}} | {{…}} |
| {{e.g. error}} | {{…}} | {{…}} |

## Interaction scenarios

<!-- Behaviour as Given/When/Then. These are written to be lifted straight
     into acceptance-criteria.md - give each a traceability id now so the chain is
     unbroken across the handoff. -->

### Scenario: {{INTERACTION TITLE}}
<!-- traceability id: TRC-UI1 · serves: {{INT-id from intent.md, or the issue}} -->

```gherkin
Scenario: {{scenario title}}
  Given {{the surface is in state X}}
  When {{the user does Y}}
  Then {{the surface transitions to / shows Z}}
```

### Scenario: {{INTERACTION TITLE - an edge or error path}}
<!-- traceability id: TRC-UI2 · serves: {{INT-id}} -->

```gherkin
Scenario: {{scenario title}}
  Given {{…}}
  When {{…}}
  Then {{…}}
```

## Accessibility commitments

<!-- Stated as commitments that become scenarios or acceptance checks.
     Must meet or exceed the project's accessibility strategy, if governance/strategies.md has one. -->

| Commitment | How it is checked |
|---|---|
| {{e.g. "Keyboard-operable: every interaction reachable without a pointer"}} | {{scenario id, or the check QA runs}} |
| {{e.g. "Visible focus state on all interactive elements"}} | {{…}} |
| {{e.g. "Contrast meets WCAG 2.2 AA"}} | {{…}} |
| {{e.g. "Error states announced to assistive tech"}} | {{…}} |

---

## Handoff to define

- [ ] Every interaction scenario above has a traceability id and an intent link.
- [ ] Accessibility commitments meet or exceed the project's accessibility strategy, if `governance/strategies.md` has one.
- [ ] These scenarios are copied into `acceptance-criteria.md` under a UI scenario group.

Next: the scenarios flow into the acceptance criteria (`/compass:define`).
