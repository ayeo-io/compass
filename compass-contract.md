# Compass operating contract

**Start an issue before you change a file.** When someone describes work to
build, change or fix, run `/compass:assess` first, even if they never typed
it. Only conversation is exempt. **One request is one issue.** Never start a
second issue for follow-on work or feedback in the same request; add it to
this one.

**The path is two commands**, each alone in its Bash call: `compass quick-fix
start`, then `compass quick-fix finish -m "<message>" -- <test command>` once
tests and code are written. `finish` writes the record and commits. When
it asks for a person's approval, stop. After feedback, edit and run `finish`
again. Each command prints `next:` or `done:`; do what it says, and do not
check its commit again. Never edit `.compass/`.

**Five guardrails:**
1. Every change lands with a test that fails without it.
2. Acceptance criteria exist before the code.
3. Code traces to a criterion and a reason.
4. Evidence is a recorded command output, never a claim.
5. A person approves anything irreversible.

**Approvals.** For the labels `auth`, `payments`, `personal-data` and
`migrations`, a label the project adds, and `critical` risk, a person approves
the scenarios before any code edit. Never approve for the person: ask them to
type `/compass:approve <n>` and stop. Approve yourself only under a
delegation naming you. Never create, extend or revoke a delegation.

**Commits.** `finish` stages the changed files and the record; do not `git
add` anything under `.compass/` yourself, and do not push unless asked. A
lint fix never weakens an assertion.

**Write for a person in the spirit of ASD-STE100.** Lead with the point. If
they are lost, re-pitch.
