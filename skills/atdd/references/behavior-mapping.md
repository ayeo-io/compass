# Behavior mapping in full

The procedure behind the section "Behavior mapping" of `skills/atdd/SKILL.md`. That section holds the rule, the two rules of the check set that fire it (`RP-FLOOR-002` and `RP-ADV-002`), and how baseline and target scenarios stay apart.

## What behavior mapping produces

A set of Given/When/Then scenarios that describe what the code **does
now** - not what it should do, not what the ticket wants, what it *does today*.
These go into `acceptance-criteria.md` marked as baseline scenarios. They become:

- the regression baseline - the thing the Verifier runs to prove you did not
  break what was working;
- the starting point the new scenarios are written against;
- the first time this corner of the system has been described in the shared
  vocabulary every role reads.

## The procedure

1. **Bound the surface.** You are not behavior mapping the whole system - only the
   behavior the upcoming change will touch, plus its immediate risk.
   Use the manifest's `labels:` and the change site the intent names to draw
   the boundary. Behavior mapping too wide wastes the time the assessment
   allowed; too narrow misses the regression you are about to cause.
2. **Find the interfaces.** Identify the inputs and outputs of the bounded surface -
   the function signatures, the endpoints, the events, the stored state. These
   are where your `When` and `Then` will attach.
   A new user-facing surface usually wants scenarios for its states and
   interactions in the acceptance criteria.
3. **Read behavior, not intent.** Trace what the code actually does for each
   input class. Resist writing what you think it *should* do - that is the new
   spec's job, and conflating them is the central behavior mapping mistake.
4. **Characterize with tests where the code is opaque.** When you cannot read
   the behavior confidently, write a *characterization test*: assert whatever
   the code returns now, even if it looks wrong, and let the green tell
   you the truth. A characterization test that documents a bug is still
   correct behavior mapping - it captures reality.
5. **Write the baseline scenarios.** One behavior per scenario, same quality
   bar as any BDD scenario (see `skills/atdd/SKILL.md`). Name them as the current
   outcome. Mark them baseline.
6. **Flag the surprises.** Behavior mapping almost always uncovers behavior nobody
   knew about - undocumented edge cases, latent bugs, dead branches. Record each
   as a decision of the requirements review: is it behavior other code depends on and
   must preserve, or a bug to
   fix as part of this change? That decision is made deliberately, not by
   accident of what the new code happens to do.

## When the behavior is genuinely a mess

Sometimes the current behavior is inconsistent - the same input class does
different things depending on undocumented state. Map it honestly anyway:
write the scenarios that capture the inconsistency. The mess, written down, is
something you can decide about. The mess, undescribed, is something that will
surprise you at ship or in production.

## Anti-patterns

- **Behavior mapping the ideal.** Writing scenarios for what the code should do and
  calling it behavior mapping. Now you have no regression baseline and a spec that lies
  about the present.
- **Mapping too much.** Behavior mapping far beyond the change's risk. The
  assessment did not allow for it and it delays the actual work.
- **Skipping it because "I understand this code."** Understanding it is not the
  bar - *it being written down* is the bar. The floor is about the artifact, not
  your confidence.
- **Silent supersession.** Letting a target scenario quietly replace a baseline
  one with no recorded decision about whether that behavior change was
  intended.
