<!--
TEMPLATE: positioning.md
Role in the pipeline: the marketer's artifact. The marketer works PARALLEL
to the spec, not downstream of it. Every claim must point at the scenario id
in acceptance-criteria.md that backs it - that is the claim→scenario
half of the traceability guardrail. The voice & positioning
strategies in governance/strategies.md govern how it is said. Unbacked
claims are resolved at ship time via launch-readiness.md; the marketer role_rule
blocks shipping until they are.

Fill every {{PLACEHOLDER}}. Leave the "backing scenario" slot blank if no
scenario backs the claim yet - an empty slot is a visible gap, which is
the point.
-->

# Positioning - {{ISSUE_SLUG}}

> **Author:** {{PRODUCT MARKETER NAME}} · **Date:** {{DATE}}
> **Governance owner check:** consistent with the voice & positioning strategies in `governance/strategies.md`.

---

## Audience

<!-- Who is this for? Be specific - the segment, their context, what they
     are trying to do. Cross-check against intent.md's primary user. -->

{{AUDIENCE}}

## Value proposition

<!-- The core promise, in one or two sentences, in the product's voice.
     This is itself a claim - it needs a backing scenario. -->

{{VALUE PROP}}

- **Backing scenario:** {{`TRC-id` from acceptance-criteria.md - or BLANK (debt)}}

## Press release (working-backwards)

<!-- The Amazon-style PRFAQ press release: write the launch as if it has
     already shipped. This is the working-backwards forcing function - if you
     cannot write a compelling, honest press release, the thing is not worth
     building yet, or it is not yet understood. EVERY factual sentence below
     is a public claim: if it asserts something the product does, it must
     appear in the Messaging table with a backing scenario. -->

### {{HEADLINE - benefit-focused, under 10 words}}

<!-- Good: "Finance closes the month without filing a data request"
     Bad:  "Introducing the new CSV Export Module v2" -->

**{{LOCATION}}, {{DATE}}** - {{ONE SENTENCE: who can now do what, and the
headline benefit}}.

{{PROBLEM PARAGRAPH - the pain this removes, in the user's terms. Cross-check
against intent.md's Problem.}}

{{SOLUTION PARAGRAPH - how it works, at the altitude a user cares about. Not
the implementation.}}

> "{{CUSTOMER QUOTE - a realistic, specific, un-corporate expression of relief
> or delight. Good: 'I used to wait two days for finance data. Now I just
> pull it.' Bad: 'This has improved my productivity metrics.'}}"
> - {{NAME, ROLE - fictional but plausible}}

{{HOW TO GET STARTED - the one action a reader takes next.}}

## Messaging - claims and their backing scenarios

<!-- Each message is a public claim. Each claim gets a backing scenario
     slot. The launch-readiness.md gate at ship time checks this whole table. -->

| # | Claim (as it would appear publicly) | Backing scenario id | Checked? |
|---|---|---|---|
| CLM-001 | {{"…"}} | {{`TRC-id` - or BLANK}} | {{[ ] - filled at ship time}} |
| CLM-002 | {{"…"}} | {{`TRC-id` - or BLANK}} | {{[ ]}} |
| CLM-003 | {{"…"}} | {{`TRC-id` - or BLANK}} | {{[ ]}} |

## Customer & internal FAQ

<!-- The PRFAQ's second half. Customer FAQs answer what a real user would ask;
     internal FAQs are where the team is honest with itself. Customer-facing
     answers are claims and follow the same scenario-backing rule. -->

**Customer FAQs**

- **Q: {{primary use case question}}** - A: {{clear, simple answer}}
- **Q: {{does it work with …}}** - A: {{answer}}
- **Q: {{the obvious edge case}}** - A: {{answer}}

**Internal FAQs** (these mirror intent.md's Internal FAQ - keep them consistent)

- **Q: Why ship this now?** - A: {{strategic / timing rationale}}
- **Q: What is in v1 vs later?** - A: {{the cut}}
- **Q: How will we measure success?** - A: {{the deciding signal}}
- **Q: What are the risks?** - A: {{honest assessment}}

## Honesty policy check (voice & positioning strategies)

<!-- How this positioning describes what the product cannot yet do. No claim
     may overstate. Checked against the voice & positioning strategies in
     governance/strategies.md. -->

- {{e.g. "We say 'CSV export for finance', not 'full reporting suite' - a voice strategy; the suite is a non-goal in intent.md."}}

---

## Handoff

This file feeds `launch-readiness.md` at ship time. No claim above ships until
its backing-scenario slot is filled and that scenario passes at Verify.
