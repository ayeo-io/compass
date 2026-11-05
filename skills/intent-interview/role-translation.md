# Role Translation

Compass is not an engineering framework with extras for other roles.
The four non-engineering roles take part in every stage. The mechanism that
makes that real - instead of aspirational - is the **shared scenario file**.
`acceptance-criteria.md` is the one artifact every role reads, each through their own
perspective. This skill is how each perspective works and how they stay coherent.

## Why one shared artifact

If every role had its own spec, the specs would drift, and "alignment" would
mean reconciling four documents nobody fully trusts. Compass has one. The product owner,
the marketer, the engineer, QA, and the designer are all looking at the *same*
Given/When/Then scenarios - so when they disagree, they are disagreeing about
one concrete thing, not comparing translations. Every role reads the same
scenario file for its own concern.

## The five roles

### Product owner / manager - the **intent** perspective
Reads each scenario asking: *does this deliver the outcome the intent names?*
- Walks every success signal in the Intent links and finds the scenario that delivers
  it. A signal with no scenario is a gap; a scenario that solves the literal
  request but misses the outcome is drift.
- Enters *upstream* of the spec - the intent is written before the scenarios -
  and the plan stage checks the spec against it (the intent-fidelity check).
  Applied from the `product-owner` perspective.

### Product marketer - the **claims** perspective
Reads each scenario asking: *what can I truthfully say publicly because this
scenario exists and passes?*
- Every line of launch copy in `positioning.md` must point at a backing
  scenario. `launch-readiness.md` is the ledger: claim → scenario → status.
- Works *parallel* to the spec and gates shipping - `verify.claims` is a
  blocking gate, added when `positioning.md` is present; no claim ships on a missing, red, or skipped scenario. Applied from the
  product marketer's perspective.

### Engineer - the **tests** perspective
Reads each scenario asking: *how does this become a test, and what TDD cycle
does it seed?*
- The scenarios *are* the acceptance suite; each also seeds the unit-level
  red→green→refactor cycle. The chain is scenario → test → code.
- Owns the implement stage and the verify stage's mechanical half. The engineer does not get a
  private spec - the scenario file is the spec, and the tests are derived from
  it, not invented alongside it.

### QA - the **coverage** perspective
Reads each scenario asking: *which behaviors are exercised, and which edges are
not described at all?*
- Owns the gate at the verify stage. Checks that the scenario set actually covers the
  behavior space - not just that the listed scenarios pass, but that the
  unlisted edges were a deliberate choice, not an oversight.
- Has a real power: QA **can send an issue back to define** if scenarios are
  uncoverable or the coverage has holes. Coverage gaps are a spec problem, found
  at the verify stage.

### Designer - the **contracts** perspective
Reads - and *writes into* - the spec through UI contracts.
- `ui-contract.md` expresses UI behavior as scenarios, and those scenarios
  *flow into* define. The designer feeds the shared file rather than consuming
  a finished one.
- A UI contract is a Given/When/Then like any other: given this state, when this
  interaction, then this observable interface outcome.

## How the roles stay coherent

The roles are different ways of reading, not different documents - that is the
safeguard. But they still have to be reconciled, and the pipeline has specific
moments for it:

- **At refine**, the non-engineering roles review the spec together. This is
  where intent-role, claims-role, and contracts-role disagreements surface
  while the spec is still cheap to change. An ambiguity one perspective sees is recorded
  as a decision with its resolution.
- **At the gates**, the roles become review dimensions - `claims` is the
  marketer's perspective as a dimension at the verify stage; the intent check is the product owner's perspective as a
  gate before the plan stage.
- **When two roles conflict**, governance arbitrates by the conflict rule. A
  guardrail always beats a strategy - so a perspective whose concern is a guardrail
  (the claims gate, traceability) wins over a perspective leaning on a strategy.
  Strategy-vs-strategy is resolved by the delivery approach (the assess stage's call) or by a
  human, often at `/compass:consult` - each non-engineering role curates its
  own strategies (product, voice & positioning) but none of them outranks a
  guardrail. A conflict that governance does not resolve is a
  recorded decision of the requirements review and, if needed, a re-assess.

## How a non-engineering role enters the pipeline

A role is a perspective a session consults. It is not an assessment dimension.
When `/compass:intent`, `/compass:position`, or `/compass:design` opens a
session - or `/compass:consult` convenes several - the session captures the
role's view: the intent goes into `acceptance-criteria.md`, and the marketer
and the designer can keep `positioning.md` and `ui-contract.md` as their own
notes. A document on disk brings no gate (ADR-091): Compass needs and checks
only `acceptance-criteria.md`.

## Anti-patterns

- **The shadow spec** - a role keeping its own private requirements doc instead
  of reading and contributing to `acceptance-criteria.md`. The moment there are two
  specs, there is no spec.
- **The downstream consultee** - treating the product owner, marketer, or
  designer as a
  reviewer of finished engineering work. They are *in* the pipeline: the product owner
  upstream of the spec, the marketer parallel to it, the designer feeding into
  it.
- **Perspective collapse** - flattening a product owner's intent straight into an
  engineering issue. The intent is upstream of the scenarios and the spec must be
  checked back against it; collapsing the two skips the intent-fidelity check.
- **The unread spec** - a role that has an opinion about the product but has not
  read the scenario file. Every perspective reads the *same* file; an opinion not
  grounded in it is not a perspective, it is a preference.
