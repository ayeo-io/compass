# Compass - the desired state

**What this is.** The standing description of where Compass is going, written
as observable statements that are true or false on any given day. Not a plan
(plans change), not a vision - a target condition. Each iteration cycle:
score every statement, find the biggest gap, let the gap choose the next
work. When every statement holds, Compass has reached the target.

**How to use it.** Re-read before each release. Score each statement
true / partly / false, with a line of evidence (or the honest absence of
any). Never argue a statement into "true" - if it needs arguing, it is
false. Change a statement only through the same review as an ADR. Do not
change a statement to match the product.

---

## 1. What it feels like to use

**D1.** A developer describes work in their own words - "the search
endpoint 500s on empty filters", "we need CSV export", "rebuild
onboarding" - and Compass responds like a competent delivery manager:
what kind of work this is, how it will run it, and why that level of
process. In plain English, in a few sentences.

**D2.** A colleague with no Compass exposure reads a full session
transcript and never asks "what does that word mean?" Every term is one
they know from ordinary software work.

**D3.** Engineering detail is one request away, and never volunteered
uninvited. "Show me the detail" produces the assessment, the policy
trace, the gate list, the evidence. The default register hides nothing;
it just doesn't lecture.

**D4.** The human can overrule the sizing in one sentence - "this touches
payments, treat it as higher risk" - and Compass adjusts, says what
changed, and remembers why.

**D5.** A first-time user goes from install to their first shipped change
in under fifteen minutes without reading a manual. The five worked
examples are the manual.

**D6.** Nobody bypasses Compass. The moment someone quietly does a
change *outside* the framework because the framework would slow them
down, a statement here has failed - find which one.

## 2. What it produces

**D7.** A bug fix produces exactly: a bug report note, a failing-then-
passing test, a PR. Nothing else exists. A typo fix produces even less.

**D8.** An initiative produces:

- an intent document that was iterated and reviewed before design started,
  with an explicit first slice (the 80/20 cut);
- a design a reviewer can *see* (diagrams, named patterns, illustrative
  code);
- work broken into slices that each leave the system releasable;
- flagged incremental PRs;
- a rollout plan with a way back;
- named SLOs where the ops surface changes.

**D9.** Requirements can change during the work, and each change is
recorded, not treated as a failure. An intent document gets outside
review before it is approved.

**D10.** Acceptance criteria are executable. The scenario a human reviewed
and the test the machine runs are the same artifact, not two artifacts
that claim to agree.

**D11.** Every artifact reads well cold. A stranger opening any intent document,
design, or PR description can follow it without having been in the
conversation.

## 3. The engineering underneath

**D12.** Process is sized per change, deterministically. Same assessment,
same policy, same process - every time, reproducibly. The typo and the
payments rewrite share one framework and nothing else.

**D13.** No argument clears a hard rule; only a check that can fail clears
it. Tested-before-ship, acceptance-before-build, traceability,
evidence-not-assertion, human sign-off on the irreversible - each is
cleared this way.

**D14.** State is earned, not asserted. An issue moves to done because the
evidence exists; a board column always shows the real workflow state; a
drag past a failing gate is refused with the reason in plain English.

**D15.** Every shipped change has a receipt: what was asked, how it was
sized, what was checked, what proved it. One screen, generated from the
mechanism, readable by a non-engineer.

**D16.** Compass is built with Compass, and it shows. The framework's own
repo is the reference implementation: its intent documents, receipts, and
friction log are public and current.

**D17.** The framework watches itself. When its sizing is consistently
wrong, or a gate consistently fails to earn its cost, Compass surfaces
that with data - and a human changes the policy, on evidence.

## 4. Its place in the world

**D18.** Real teams that are not the maintainer use it on real codebases,
and at least one has said in public, in their own words, that it made
their delivery better.

**D19.** The comparison question has a crisp answer. "Why not R1/
R3/R5?" - *because none of them right-size the process, and
none of them can prove what they shipped.* The advantage (deterministic
sizing + evidence you can fail) has not been traded away for any feature,
however tempting.

**D20.** The vocabulary freeze holds. Two years from now the words are
still the industry's words, and `compass terminology` is still the single
source of truth that the build enforces.

**D21.** Someone the maintainer has never met has contributed a fix, a
label rule, or a worked example - and the contribution process made that
routine rather than heroic.

## What we will not do to get there

The constraints that hold *during* iteration, so closing a gap never opens
a worse one:

- No sixth hard rule; new rigour arrives as checks on the existing five,
  or as strategies.
- No judgement moved past the human: assessment and policy changes stay
  human; the mechanism stays deterministic.
- No invented vocabulary, ever again. If the industry has no word for it,
  question the concept before coining the word.
- No feature that makes the small change heavier. The typo fix must stay
  as light as it is now; it is the proof the adaptivity is real.
- No claim without a receipt - in the product, or in how we talk about
  the product.

## The gap review (the loop itself)

At each release, or fortnightly - whichever comes first:

1. Score D1-D21: true / partly / false, one line of evidence each.
2. The statements scored *false* with the cheapest path to *true* and the
   statements blocking others (D2 blocks D5; D16 blocks D18) get the next
   cycle's work. Everything else waits.
3. Friction logged during the cycle counts as evidence - a statement can
   regress, and record the regression.
4. Once a year, challenge the statements themselves. Amending the target
   is allowed; changing it quietly is not.

The test of the whole endeavour is D6. Everything else serves it.
