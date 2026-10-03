---
name: behaviour-mapping
description: Capturing existing behaviour as scenarios before changing it. Load on brownfield work with no written behaviour.
---

# Behaviour mapping

The rule behind this skill is simple: **you cannot safely change behaviour you
have not first written down.** On `brownfield-unmapped` familiarity the routing
policy makes this a routing guardrail floor - behaviour mapping runs before any new
scenario, before any change. On an atomic or small change with trivial or
contained risk and no domain label it is advice (`RP-ADV-002`): pin what the code does now where
the change touches it with a test. This skill is how you do it well.

## What behaviour mapping produces

A set of Given/When/Then scenarios that describe what the code **does
now** - not what it should do, not what the ticket wants, what it *does today*.
These go into `acceptance-criteria.md` marked as baseline scenarios. They become:

- the regression baseline - the thing the Verifier runs to prove you did not
  break what was working;
- the starting point the new scenarios are written against;
- the first time this corner of the system has been described in the shared
  vocabulary every role reads.

## The procedure

1. **Bound the surface.** You are not behaviour mapping the whole system - only the
   behaviour the upcoming change will touch, plus its immediate risk.
   Use the manifest's `labels:` and the plan's intended change site to draw
   the boundary. Behaviour mapping too wide wastes the time the delivery
   approach allowed; too narrow misses the regression you are about to cause.
2. **Find the interfaces.** Identify the inputs and outputs of the bounded surface -
   the function signatures, the endpoints, the events, the stored state. These
   are where your `When` and `Then` will attach.
3. **Read behaviour, not intent.** Trace what the code actually does for each
   input class. Resist writing what you think it *should* do - that is the new
   spec's job, and conflating them is the central behaviour mapping mistake.
4. **Characterise with tests where the code is opaque.** When you cannot read
   the behaviour confidently, write a *characterisation test*: assert whatever
   the code returns now, even if it looks wrong, and let the green tell
   you the truth. A characterisation test that documents a bug is still
   correct behaviour mapping - it captures reality.
5. **Write the baseline scenarios.** One behaviour per scenario, same quality
   bar as any BDD scenario (see `bdd-specification`). Name them as the current
   outcome. Mark them baseline.
6. **Flag the surprises.** Behaviour mapping almost always uncovers behaviour nobody
   knew about - undocumented edge cases, latent bugs, dead branches. Record each
   in `requirements-review.md`: is it behaviour other code depends on and
   must preserve, or a bug to
   fix as part of this change? That decision is made deliberately, not by
   accident of what the new code happens to do.

## Behaviour-mapped vs. desired - keep them separate

The most important discipline here. `acceptance-criteria.md` will end up holding two
kinds of scenario:

- **Baseline** - what the code does now. The regression baseline.
- **Target** - what the change will make it do. The new acceptance criteria.

Keep them labelled and distinct. When the change ships, some baseline scenarios
are *intentionally* superseded by target scenarios - that is a recorded
decision, not a silent overwrite. The baseline you are *not* changing must still
pass at the verify stage; that is the proof you preserved what you meant to.

## When the behaviour is genuinely a mess

Sometimes the current behaviour is inconsistent - the same input class does
different things depending on undocumented state. Map it honestly anyway:
write the scenarios that capture the inconsistency. The mess, written down, is
something you can decide about. The mess, undescribed, is something that will
surprise you at the verify stage or in production.

## Anti-patterns

- **Behaviour mapping the ideal.** Writing scenarios for what the code should do and
  calling it behaviour mapping. Now you have no regression baseline and a spec that lies
  about the present.
- **Mapping too much.** Behaviour mapping far beyond the change's risk. The
  delivery approach did not allow for it and it delays the actual work.
- **Skipping it because "I understand this code."** Understanding it is not the
  bar - *it being written down* is the bar. The floor is about the artifact, not
  your confidence.
- **Silent supersession.** Letting a target scenario quietly replace a baseline
  one with no recorded decision about whether that behaviour change was
  intended.
