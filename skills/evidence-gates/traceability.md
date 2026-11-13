# Traceability

**The traceability guardrail** keeps two chains, on every delivery issue:

```
code → scenario → intent
claim → scenario
```

The chain is not paperwork. It *is* the audit trail. When it is intact, anyone
can pick any line of code and walk it up to the reason it exists; anyone can
pick any public claim and walk it down to the proof it is true. When it is
broken, you have code nobody can explain or claims nobody can stand behind -
and that is a no-pass at ship.

## The two chains, link by link

### code → scenario → intent

- **code → scenario.** Every unit of production code traces up to a scenario in
  `acceptance-criteria.md` that motivates it. Not one-to-one - a scenario may need
  several units, a unit may serve several scenarios - but *onto*: no code
  without at least one scenario above it. The acceptance-before-code guardrail forbids code no stated
  acceptance criterion describes; this link is how that is observable.
- **scenario → intent.** Every scenario traces up to an intent - a success signal
  in the Intent links, the ticket, the product outcome it serves. A scenario with no
  intent above it is a scenario nobody asked for.

### claim → scenario

- Every public claim - launch copy, docs, marketing, a sentence in the
  changelog - traces down to a scenario that, when it passes, makes the claim
  true. The manifest's `claims:` is the ledger, and the
  `claim-traces-to-scenario` check reads it.

## How it is kept

- **code → scenario.** `compass quick-fix finish` reads the changed files
  from git and traces each one to the scenarios of the issue.
- **scenario → intent.** Write each scenario for the intent the issue was
  started with. Give it the next `TRC-` id.
- **claim → scenario.** The Marketing Perspective adds a `claim → scenario`
  entry to the manifest's `claims:` as each claim is drafted. A claim with no
  entry is not yet a shippable claim.

## What a break looks like - and what to do

- **Orphan code** - a unit with no scenario above it. Either it implements
  behavior that needs a scenario (file it with the Spec Author), or it is dead
  code (delete it). Code does not get to exist unexplained.
- **Orphan scenario** - a scenario with no intent above it. Either find the
  intent it serves, or question whether the scenario should exist. Scenarios
  nobody asked for are scope creep with a Given/When/Then on it.
- **Orphan claim** - a public claim with no scenario below it. The marketer's
  three moves: file the missing scenario, soften the claim until a real
  scenario backs it, or cut the claim. It never ships orphaned - `verify.claims`
  blocks it.
- **Stale link** - a scenario was rewritten and the code above it now traces to
  a scenario that no longer says what the code does. Re-point the link; a link
  to the wrong place is worse than a missing one because it lies.

## How the chain becomes the audit trail

Run end to end, the chains answer the questions an audit asks without anyone
reconstructing anything:

- *Why does this code exist?* - walk up: scenario, then intent.
- *Is this feature actually built?* - walk down from the intent: scenarios,
  then code, then the passing tests.
- *Can we say this publicly?* - walk down from the claim to the scenario and
  check its status at ship.
- *What breaks if we change this scenario?* - walk down to every unit of code
  and every claim that traces to it.

That is why it is kept on every delivery issue, including the lightest
change and the hotfix.

## Anti-patterns

- **The decorative reference** - a scenario tag that points vaguely at a feature
  rather than precisely at a scenario. Precision is what makes the walk work.
- **Letting a hotfix skip it** - "we were in a hurry." The reproduction test
  traces to the defect; the promoted scenario traces to an intent. The chain
  holds under time pressure too.
- **Claims that outrun scenarios** - drafting launch copy for behavior the spec
  does not yet describe and intending to write the scenario later. The scenario
  comes first, or the claim is not real.
