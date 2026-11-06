---
name: flow-management
description: Priorities across issues, blockers and the digest. Load when a question spans issues.
---

# Flow Management

Compass is issue-centric: every issue carries its own assessment, evidence and
gates, and the path guarantees a single issue is well-run. Flow management
is the layer *above* that - the cross-issue view. It is the delivery-management
function expressed as a **capability**, not a persona. There is no
"delivery manager" role in Compass; there is `/compass:flow`, which anyone can
run.

This skill is the craft behind that command: how to triage a board of issues,
how to handle a blocker, and how to write the digest.

## Why this is a capability, not a role

A delivery-manager agent would own the board and move issues; Compass has none.
Issue state is not a label someone sets; it is *inferred
from the records on disk*. An issue is in the build stage because its
scenarios are declared and their reds and greens are not all on record - not
because someone moved a card. `compass next` prints the stage each issue's
records show. So flow
management has nothing to *own* and nothing to *move*. Its entire job is to
read the artifacts, notice what the per-issue pipeline structurally cannot
(because each issue only sees itself), and put the right thing in front of a
human first.

## The flow toolkit

Flow management reads artifacts; it also has one CLI command of its own.
`compass retro` aggregates the `reassessments` log across every issue and
reports whether the assess stage is systematically over- or under-sizing
the work - the framework's own feedback loop. It is read-only and never gates. Run it as part
of triage and fold its signal into the digest: "are we right-sizing process?"
is a cross-issue question, and this is the command that answers it.

## Board heuristics

Run these against every issue directory under `.compass/work/`. Order of
severity, worst first:

1. **No `delivery_approach:` in the manifest** - a guardrail violation. Work was started without an assessment.
   This outranks everything; an issue with no computed approach is unaccountable.
   The fix is to run `/compass:assess` now and reconcile.

2. **Assessment outgrown** - the records show the issue outgrowing its assessment
   (a small change whose scenarios keep growing; a change on the light
   evidence row still open after days). The fix is `/compass:assess --reassess`, not
   pushing on. An assessment quietly outgrown is the failure mode Compass exists to
   prevent - flow management is where it gets caught when the issue itself
   missed it.

3. **Stalled** - an in-progress issue with no new record (a scenario, a red,
   a green, a gate pass, evidence) for longer than its size suggests (atomic
   or small: hours; medium: a day or two; large or product: longer, but each
   unit should still show movement). On an archived issue that keeps a
   `devlog.md`, read its movement too. A stall is almost always a hidden
   blocker. Name the likely cause from the artifacts.

4. **Owed follow-up sitting** - an issue at ship or closed with an owed
   follow-up or an unbacked marketing claim. The per-issue `/compass:status`
   flags this; flow's job is to make sure it does not sit ignored across the
   whole board.

5. **Healthy** - progressing in line with its assessment. Report it briefly; spend
   the attention on 1–4.

## Blocker protocol

When an issue is blocked or stalled:

1. **Locate the blocker precisely.** Run `compass next` for the issue and
   read its latest records, and on an archived issue its `devlog.md`.
   "Blocked" is not a state - "blocked on a governance amendment decision",
   "blocked on a flaky integration test", "blocked waiting on a human to
   confirm the assessment override" are states.
2. **Name who or what unblocks it.** A human decision, another issue landing
   first, an external dependency, a re-assess.
3. **Record it where the issue lives** - ask the person working the issue
   to flag it with `compass issue blocked set --reason "<the blocker>"` (an
   in-progress or in-review issue), and the board then shows the reason. On
   an archived issue that keeps a `devlog.md`, append a dated line there
   too. Flow management does not keep a separate blocker list beyond the
   digest's Blocked section: the blocker belongs with the issue.
4. **Escalate by surfacing, not by routing.** Flow management has no authority
   to reassign or reprioritize - it makes the blocker *visible* at the top of
   the flow report and, if a human decision is needed, says so plainly.

## The digest format

`/compass:flow --digest` writes `.compass/flow/digest-<date>.md`. It is
append-only history - a team reads it on a cadence (a weekly scheduled run is
the natural fit). Keep it short enough to read in two minutes.

```markdown
# Flow digest - {{DATE}}

## Needs a human
- {{decision or guardrail violation - or "nothing"}}

## Landed since last digest
- {{issue-slug}} ({{delivery or spike}}) - {{one line: what shipped}}

## In flight
- {{issue-slug}} ({{delivery or spike}}) - {{stage}} - {{health: healthy | stalled | off-track}}

## Blocked
- {{issue-slug}} - blocked on {{precise blocker}}; needs {{who/what}}

## Outstanding follow-ups
- {{issue-slug}} - {{outstanding hotfix follow-up | unbacked claim | de-scoped artifact}}

## Calibration
- {{`compass retro` signal - re-assessment rate, lean toward over- or
  under-sizing, or "balanced" - or "not enough history yet"}}

## Next up
- {{issues triaged but not started, in priority order}}
```

## What flow management must not do

- **It does not gate.** The gates live on each issue's path, next to the
  evidence. Flow adds visibility, never another gate.
- **It does not set issue state.** State is inferred from artifacts. If the
  board looks wrong, the artifacts are wrong - fix those, not a label.
- **It does not own issues.** No assignment, no turf. It reads, triages, and
  surfaces. The moment flow management starts "managing people" instead of
  "surfacing reality", it has become a manager, which Compass does not have.
