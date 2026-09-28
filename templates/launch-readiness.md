<!--
TEMPLATE: launch-readiness.md
Produced by: the product marketer via `/compass:position`; completed at ship time.
Lives at:    docs/compass/<created>-<issue-slug>/launch-readiness.md
Role in the pipeline: the marketer's GATE artifact. The routing-policy
role_rule for `product-marketer` needs this file and blocks shipping until
every claim in positioning.md traces to a PASSING scenario. This is where
the claims→scenario chain is proven before anything ships publicly. The
`claims` review dimension and the `verify.claims` gate, which the role rule
adds while a marketer is in play, both read this file.

Fill every {{PLACEHOLDER}}. A claim with no passing scenario is a no-go -
ship refuses to close on it.
-->

# Launch Readiness - {{ISSUE_SLUG}}

> **Author:** {{PRODUCT MARKETER NAME}} · **Date:** {{DATE}} · **Owning agent:** `product-marketer`
> **Reads from:** positioning.md (the claims), verification-report.md (the scenario results)
> **Gates:** ship - the routing-policy.md role rule adds the blocking `verify.claims` gate.

---

## Claims-to-scenarios traceability checklist

<!-- One row per claim from positioning.md. The scenario must not just
     EXIST - it must PASS at Verify. Pull the pass/fail from
     verification-report.md. -->

| Claim # | Claim | Backing scenario id | Scenario passed at Verify? | Cleared to ship? |
|---|---|---|---|---|
| CLM-001 | {{from positioning.md}} | {{`TRC-id`}} | {{[ ] / [x] - from verification-report.md}} | {{[ ] / [x]}} |
| CLM-002 | {{…}} | {{`TRC-id`}} | {{[ ]}} | {{[ ]}} |
| CLM-003 | {{…}} | {{`TRC-id`}} | {{[ ]}} | {{[ ]}} |

## What is checked vs. not

### Checked - cleared to ship
- {{claim id - backed by a passing scenario}}

### Not checked - may NOT ship
<!-- A claim lands here if: it has no backing scenario, or its scenario
     failed/was not run. Each one is either cut from the launch copy, or
     the issue does not ship. -->
- {{claim id - reason: no backing scenario / scenario `TRC-id` failed at Verify}}

## Voice & positioning check

- [ ] Every shipping claim respects the project's voice and positioning strategies in `governance/strategies.md`, if it has any.
- [ ] No claim overstates what the product can do.

---

## Go / No-Go

<!-- The marketer's gate decision. NO-GO if any claim in the "not checked"
     list is still in the launch copy. -->

**Decision:** {{GO \| NO-GO}}

**Rationale:** {{e.g. "All three claims trace to passing scenarios; cleared." - or "CLM-002 has no backing scenario; either cut CLM-002 from launch copy or the issue does not ship."}}

**Decided by:** {{NAME}} on {{DATE}}.

<!-- If NO-GO, the issue stays open. `/compass:status` keeps flagging the
     unbacked claim; the ship command (`/compass:ship`) refuses to close. -->
