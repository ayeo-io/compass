# Compass operating contract

**Start an issue before you change a file.** When someone describes work to
build, change or fix, run `/compass:assess` first, even if they never typed
it. Only conversation is exempt. If `.compass/current-task` names an open
issue, carry on with it. **One request is one issue.** Do not open a second
issue for follow-on work in the same request; add it to this one.

**The path is three commands**, each alone in its Bash call:
`compass quick-fix start`, then `compass quick-fix finish -m "<message>" --
<test command>` once the tests and code are written, then `compass
ship-commit` when the person asks for a commit. Each prints `next:`; do what
it says. Between start and finish, write tests and code and run the tests
directly. Compass writes the record itself: never edit `.compass/`.

**Five guardrails:**
1. Every change lands with a test that fails without it.
2. Acceptance criteria exist before the code.
3. Code traces to a criterion and a reason.
4. Evidence is a recorded command output, never a claim.
5. A person approves anything irreversible.

**Approvals.** For the labels `auth`, `payments`, `personal-data` and
`migrations`, a person approves the scenarios before any code edit. Never
approve for the person: ask them to type `/compass:approve <n>` and stop.
Approve yourself only under a delegation naming you. Never create, extend or
revoke a delegation.

**Commit only what you mean to.** `compass ship-commit` stages the changed
files and the record; do not `git add` anything under `.compass/` yourself.
Check the commit's files and author. A lint fix never weakens an assertion.

**Write for a person in the spirit of ASD-STE100.** Lead with the point. If
they are lost, re-pitch.
