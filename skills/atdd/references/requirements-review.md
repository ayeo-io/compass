# The requirements review and the self-review

Read with the sections "Self-review before the requirements review" and "The requirements review" of `skills/atdd/SKILL.md`. This file holds how the two split the work, why there is no subagent critic between them, and the anti-patterns of a spec.

## The split, stated plainly

The two overlap enough that a reader meeting both wonders which is redundant.
Neither is. They differ in *who does them*, *what they cost*, and *what kind of
finding they can produce*.

| | Inline self-review (while writing) | Requirements review (end of specify) |
|---|---|---|
| **Who** | the spec-author, alone | spec-author plus reviewer; the person where `scenario-approval` is owed |
| **Cost** | minutes - four mechanical scans over one file | needs reading, and often a human decision |
| **Finds** | placeholder, orphan-intent, untestable-`Then`, ambiguous-quantifier | contradictions between scenarios, gaps across the whole set, governance conflicts, ambiguities that need someone to *choose* |
| **Output** | edits to `acceptance-criteria.md`, in place | a resolution and an owner per ambiguity, recorded as decisions |
| **When** | every delivery issue | every delivery issue with more than one scenario; a one-scenario change and the hotfix's reproduction need only the self-review; a spike has neither |

The dividing line: **the self-review fixes what one person can see and
settle alone; the requirements review resolves what needs a decision.** An unfilled placeholder has
one correct answer and the author already knows it. "Do these two scenarios
contradict each other, and which one is wrong?" does not - and pretending
otherwise is how a spec ships with an unresolved contradiction.

The review does not re-run the four scans. If it finds one of them still
open, that means the self-review was skipped: worth saying so, not worth
silently absorbing.

*Why there is no subagent critic here.* The R1 project shipped a
subagent review loop between spec and plan and then removed it in their
[v5.0.6 release](R1/releases/tag/v5.0.6).
They reported regression testing across five versions and five
trials that found identical quality scores whether the loop ran or not, at
roughly 25 minutes of overhead per run. Compass has not repeated that
measurement and takes the published result at face value. Compass already has
two review points that earn their cost: **the requirements review**, which
QAs the spec against governance, and the **review** at ship. A
third pass between them would double the time without measurably
improving the spec.

## Anti-patterns

- **The implementation scenario** - `Given the cache is warm, When flushCache()
  is called…`. That tests the code's shape, not its behavior. Scenarios outlive
  implementations.
- **The unfalsifiable Then** - "Then the user has a good experience." If it
  cannot fail, it cannot pass; it is not a scenario.
- **The orphan-creating spec** - leaving real behavior with no scenario.
  The acceptance-before-code guardrail forbids code that no stated acceptance criterion describes; the
  spec is where you prevent the orphan, not the ship stage.
- **The novel** - a scenario with five `Given` lines and three `When` lines.
  Split it.
