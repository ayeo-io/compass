---
name: receiving-code-review
description: "Answering review comments: check each against the code, push back with reasons, record the outcome."
---

# Receiving Code Review

There are two ways to answer a reviewer badly, and agreeing too readily is the
more common one.

**Check each suggestion against the code before you implement it.** Every
comment is a hypothesis about code the reviewer read faster than you wrote it.
A suggestion right about the symptom and wrong about the cause is the normal
case - implementing it verbatim leaves the symptom and adds a change nobody
needed.

**"You're absolutely right", before checking, is the failure this prevents.**
It converts the reviewer's guess into your commit, removing the second opinion
review existed to give.

**Push back with technical reasoning when the reviewer is wrong.** Show the case
their suggestion breaks, the constraint it misses, or the measurement that
contradicts it - not preference, not seniority, not how long the version
took. If you
cannot produce a technical reason, they are probably right.

**Treat "implement this properly" as a question about scope.** Ask what breaks
today without it. If the answer is nothing, it is a separate issue, not a
review thread.

**Read the label first** (`${CLAUDE_PLUGIN_ROOT}/governance/strategies.md` `S12`; an unmigrated 5.x
project runs on its own copied `governance/`). Issue, suggestion, nitpick, question or
praise tells you what blocks the merge before you read the argument. If it is
missing, ask rather than guess.

**Say what you did.** Per comment: changed it, or did not and why. A resolved
thread with no reply is a decision nobody can audit, and a change with no
recorded reason is an assertion. Keep the reply short: *"Checked -
`validate()` runs before the cache write, so that race cannot happen here. It
can on the batch path; fixed there."*

## Anti-patterns

- **Reflexive agreement** - implementing without checking.
- **Reflexive defence** - explaining why the code is fine before reading properly.
- **Silent compliance** - changing it with no reply, so the reasoning is lost.
- **Deferring on authority** - the code does not know who filed the comment.
