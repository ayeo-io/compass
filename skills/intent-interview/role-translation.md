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
Reads each scenario asking: *does this deliver the outcome in `intent.md`?*
- Walks every success signal in `intent.md` and finds the scenario that delivers
  it. A signal with no scenario is a gap; a scenario that solves the literal
  request but misses the outcome is drift.
- Enters *upstream* of the spec - `intent.md` exists before the scenarios - and
  gates the plan stage: per the routing policy's blocking `role_rules`, the spec must be
  checked against `intent.md` before the plan stage starts. Applied by the `product-owner`
  agent.

### Product marketer - the **claims** perspective
Reads each scenario asking: *what can I truthfully say publicly because this
scenario exists and passes?*
- Every line of launch copy in `positioning.md` must point at a backing
  scenario. `launch-readiness.md` is the ledger: claim → scenario → status.
- Works *parallel* to the spec and gates shipping - `verify.claims` is a
  blocking role gate; no claim ships on a missing, red, or skipped scenario. Applied by the
  `product-marketer` agent.

### Engineer - the **tests** perspective
Reads each scenario asking: *how does this become a test, and what TDD cycle
does it seed?*
- The scenarios *are* the acceptance suite; each also seeds the unit-level
  red→green→refactor cycle. The chain is scenario → test → code.
- Owns the implement stage and the verify stage's mechanical half. The engineer does not get a
  private spec - the scenario file is the spec, and the tests are derived from
  it, not invented alongside it.

### QA - the **coverage** perspective
Reads each scenario asking: *which behaviours are exercised, and which edges are
not described at all?*
- Owns the gate at the verify stage. Checks that the scenario set actually covers the
  behaviour space - not just that the listed scenarios pass, but that the
  unlisted edges were a deliberate choice, not an oversight.
- Has a real power: QA **can send an issue back to define** if scenarios are
  uncoverable or the coverage has holes. Coverage gaps are a spec problem, found
  at the verify stage.

### Designer - the **contracts** perspective
Reads - and *writes into* - the spec through UI contracts.
- `ui-contract.md` expresses UI behaviour as scenarios, and those scenarios
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
  while the spec is still cheap to change. An ambiguity one perspective sees is logged
  in `requirements-review.md` with its resolution.
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
  `requirements-review.md` entry and, if needed, a re-assess.

## How a non-engineering role enters the pipeline

A role is not a consultation; it is an entry point that *changes the delivery
approach*.
When `/compass:intent`, `/compass:position`, or `/compass:design` opens a
session - or `/compass:consult` convenes several - the assess stage reads the role
as the fourth dimension. A non-engineering role almost always pulls the delivery approach
heavier: it adds artifacts (`intent.md`, `positioning.md`, `ui-contract.md`) and
gates (the intent check, the claims gate). That weight is the framework working
as designed, not overhead to trim.

## Anti-patterns

- **The shadow spec** - a role keeping its own private requirements doc instead
  of reading and contributing to `acceptance-criteria.md`. The moment there are two
  specs, there is no spec.
- **The downstream consultee** - treating the product owner, marketer, or
  designer as a
  reviewer of finished engineering work. They are *in* the pipeline: the product owner
  upstream of the spec, the marketer parallel to it, the designer feeding into
  it.
- **Perspective collapse** - flattening a product owner's `intent.md` straight into an
  engineering issue. `intent.md` is upstream of the spec and the spec must be
  checked back against it; collapsing the two skips the intent-fidelity gate.
- **The unread spec** - a role that has an opinion about the product but has not
  read the scenario file. Every perspective reads the *same* file; an opinion not
  grounded in it is not a perspective, it is a preference.
