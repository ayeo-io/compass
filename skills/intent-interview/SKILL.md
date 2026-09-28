---
name: intent-interview
description: Drawing `intent.md` out of a conversation. Load before acceptance criteria exist.
---

# Intent interview

There are two ways an issue gets an `intent.md`, and this skill covers both.

**Someone arrives with a document.** It is in Notion, or Jira, or a file called
something nobody would guess. `compass intent ingest` has read it and left a
snapshot at `intent-source.md`. Your job is to turn it into `intent.md`.

**Someone arrives with an idea.** No document at all. Same discipline, longer
conversation, nothing to reshape.

The rule that makes both safe is the same one, and it is worth stating before
anything else.

## Nothing is invented

**Every statement in `intent.md` traces to the source or to a recorded answer.
There is no third origin.**

You can move material, split it, merge it under a template heading, and
reformat it. You must not change what it means, and you must not add to it.

That last part is the one that will tempt you. A source document with no non-goals is a
source document that feels unfinished, and you will be able to think of a perfectly
sensible non-goal. **Write it and you have put a product decision into the
record that no person made** - and it will read exactly like one they did make,
because there is nothing on the page to distinguish them.

So: where the source is silent, you ask. Where you ask and nobody answers, the
document says so, in words.

`compass check` holds this mechanically through
`validate_intent_origins` - every section with content must name where it came
from. The check is not the reason to do it; it is what stops the reason being
forgotten.

## Step aside when there is nothing to ask

**Read the source first, and count what it already answers.** If it carries the
problem, the outcome, the non-goals, the success signals and a first slice,
then there is nothing to draw out. Reshape it into the template's sections,
record every section as `from: source`, and hand it over.

A person who arrives with a complete source document and gets interrogated about it
learns that Compass wastes their time. That is a worse outcome than a thin
`intent.md`, because they do not come back.

**Say what you are doing:** "Your source document covers everything the
template asks for, so I have reshaped it and asked nothing." That sentence is
the whole hand-off when the source is good.

## When there is something to ask

**One question at a time.** A list of six questions gets one answer to the
first and silence for the rest. Ask, wait, use the answer, then ask the next.

**Offer choices where the choices are real.** "Is the ranking change in scope,
or is this only about latency?" is answerable in a second. "What are your
non-goals?" is a blank page with a question mark. Only offer options you would
be content with - a menu with one plausible item is a leading question.

**Draft the section only after its content is agreed.** Writing first and
asking for corrections puts the person in the position of editing your words
instead of saying theirs, and most people will accept what is written rather
than push back.

**Ask about the first slice before you close.** "If only part of this shipped
first, which part delivers most of the value?" is the question people are most
grateful to have been asked and least likely to volunteer.

## Declining is a complete answer

**A person can decline every question and must still get an `intent.md`.**
Someone in a hurry, or without the answers to hand, needs to start now and
come back later. A loop that blocks them is worse than no interview.

When a question is declined:

- record it in `interview` with `answer: null` - the question was asked, and
  that is worth knowing
- record the section as `from: unanswered`
- write, in the section itself, that it was asked and not answered

**Never write `TBD`.** `TBD` means "someone will get to this", and
`compass plan lint` scans for it as an unfinished placeholder. A section that
was asked about and deliberately left open is *finished*. Two different states,
and only one of them is true:

> No non-goals were stated in the source, and none were supplied when asked.

That sentence is a complete section. `TBD` is not.

## What you write

| Where | What |
|---|---|
| `intent.md` | the reshaped document, following `templates/intent.md`'s sections |
| `manifest.yml` → `intent_source.sections` | one entry per section: `name`, `from` (`source` \| `answer` \| `unanswered`), and `answer_id` where it cites one |
| `manifest.yml` → `intent_source.interview` | every question asked, with its answer or `null` |

`intent-source.md` is never edited. It is the record `intent.md` is checked
against, and a reviewer who wants to know whether you invented something reads
the two side by side.

## Hand-off

> I have written `intent.md` from the source document at `<origin>`.
>
> N sections came from the source, M from questions I asked, K were asked
> about and left open. The questions and answers are recorded in the manifest.
>
> Worth a read before the acceptance criteria are written. Specifically:
> - **Anything I have put in your words that is not what you meant** - I
>   reorganised the source, and reorganising can change emphasis.
> - **The sections marked as left open** - they are deliberate, not missing,
>   and if that is wrong now is the cheap moment.
> - **The first slice**, if one was agreed. Everything downstream follows it.

Fill in the real origin and counts. A hand-off that still says `<origin>` has
not been read by the person sending it.

## Voice

You are asking someone about their own product. Ask short questions and let
them talk. Do not explain the framework, do not narrate which section you are
on, and do not thank them for each answer. See
`skills/compass-runtime/writing-voice.md`.

## Speaking to a role that is not yours

In `skills/intent-interview/role-translation.md`. Read it when the person you
are interviewing works in a different discipline from the artifact you are
about to write - it is how one role's words become another's without either
losing what they meant.
