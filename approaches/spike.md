# The spike

> You do not understand the problem well enough to frame it properly yet.
> Explore freely, learn, then graduate or discard. Nothing ships from here.

Spike is the approach for work you cannot yet state as acceptance criteria.
The four-stage path (`approaches/path.md`) assumes you know enough to state
acceptance criteria and build against them. Sometimes you do not - you are investigating a bug whose
cause is unknown, evaluating whether an approach is even viable, learning an
unfamiliar API, prototyping to feel out a design. A framework that forces
that work through a delivery-shaped pipeline puts more process on it than it
needs. Spike is the approach that does not.

## Assess composes towards Spike when

- goal is **exploration** - "I need to understand this before I can frame it"
  - rather than delivery, **and**
- the work is genuinely a question, not a known change, **and**
- nothing irreversible is in scope (see "Spike may NOT" below).

Typical: root-causing a mysterious defect, a viability prototype, a timeboxed
"is this approach even sane" investigation, learning a dependency well enough
to plan real work against it.

Spike is selected by *goal* (`RP-EVID-SPIKE`) - the assess stage still
scores all three dimensions, but the `exploration` goal is what picks the
spike. It is the one approach that is not on the path.

## What is different about Spike

Spike **suspends the TDD strategy**. The pre-tool hook is approach-aware and
does not block code edits on a Spike - red-before-green is the wrong
discipline for code you are writing precisely to learn something and may throw
away. Exploration is not throttled.

This is safe because of the hard rule below it: **a Spike does not land
production code.** It cannot smuggle untested code onto `main`. The only way
a spike's code reaches production is by *graduating*. Graduating means
re-assessing onto the path, where the tested-before-ship,
acceptance-before-code, and traceability guardrails apply in full.

## The three stages

A spike runs three stages: assess, build and ship. It has no specify stage,
because it has no acceptance criteria to write.

| Stage | On a spike |
|---|---|
| Assess | Lightweight but real. The assessment is recorded in the manifest - even a spike is accountable. Write the **question**, what a useful answer would look like, and the **timebox** at the top of the conclusion file, the file that `compass evidence add EV-SPIKE --path` names at Ship. |
| Build | **Explore.** Write code freely to answer the question. The TDD strategy is suspended; the hook does not block. Code here is assumed throwaway. |
| Ship | **Conclude, then graduate or discard.** Not a test gate - a findings check: *did we answer the question?* The output is a written conclusion, recorded with `compass evidence add EV-SPIKE --type spike-conclusion --path <file> --decision <decision>`, then `compass gate pass spike.conclude`. Never "merge to main." |

## Gate set

One gate, `spike.conclude`, at Ship: the question is answered (or explicitly
answered with "inconclusive - here is why"), and the finding is written down.
That is it. Spike has no test gate because it ships nothing.

## What a spike leaves out, and why it is safe

| Left out | Standing justification |
|---|---|
| The specify stage | A spike has no acceptance criteria - its output is knowledge, not behavior. The question takes the place of the scenarios. |
| The red before each green | Red-before-green is the wrong discipline for throwaway learning code. The tested-before-ship guardrail is not skipped - it is *deferred to graduation*, where it applies in full. |

Every justification rests on the same fact: **nothing lands from a Spike.**
What it leaves out is safe because the spike has no delivery output to
protect.

## Graduation - the only way out that keeps code

When a spike answers its question and the team wants to act on it:

1. **Re-assess.** Run `/compass:assess` afresh for the real delivery work. The
   spike's conclusion and any reference code are inputs to that
   assessment - often very good inputs, because the familiarity is now mapped.
2. **The path owns the code.** Any code carried over from the spike
   is now subject to the path's guardrails - the tested-before-it-lands,
   acceptance-before-code and traceability guardrails. In practice most spike
   code is rewritten under TDD; some is kept and retro-tested. Either way it
   meets the guardrails before it lands.
3. **The spike closes.** Its conclusion record names the new issue
   (`--next-issue <slug>` on `compass evidence add`).

Graduation *is* re-assessment. There is no way from spike code to `main`
that skips the four-stage path - that is the whole safety model.

## Discard - the honorable other ending

A spike that concludes "this approach is not viable" or "the bug is X, fixable
in Y" has succeeded. Discard it: record the finding as the conclusion, note any
follow-up issue, and close. A discarded spike that produced a clear answer was
cheap and worth it. The failure mode is not discarding - it is a spike with no
conclusion, which is just untracked work.

## Spike may NOT

- **Land production code.** <!-- vocabulary-scan: allow - ordinary verb opening a sentence, not the retired stage name; the sentence is about landing code, and rewording it would lose the plain meaning -->
  The only exit that keeps code is graduation, which
  is re-assessing. If you find yourself wanting to merge a spike branch to
  `main`, stop - that is a re-assess, not a merge.
- **Touch anything irreversible.** No auth, payments, personal data, or
  migrations: assess refuses exploration with a `G5` label or critical risk,
  because a spike must not touch a surface that owes a person's sign-off. If
  the question can only be answered by touching irreversible surface, it is
  not a spike; assess it as delivery on the path, and answer the question
  with the scenarios at specify.
- **Run past its timebox silently.** When the clock runs out, either conclude
  or re-assess the spike with a new timebox and a written reason. An open-ended
  spike is how exploration becomes drift.
- **Skip the graduate-or-discard decision.** A spike with no conclusion has
  not used the approach - it has just avoided the framework.
