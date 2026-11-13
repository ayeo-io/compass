# Compass operating contract

**Start an issue before you change a file.** When someone describes work to
build, change or fix, run `/compass:assess` first, even if they never typed
it. Only conversation is exempt. **One request is one issue.** Add follow-on
work or feedback in the same request to this issue; never start a second.

**The path is two commands**, each alone in its Bash call: `compass quick-fix
start`, then `compass quick-fix finish -m "<message>" -- <test command>` once
tests and code exist. `finish` writes the record and commits. When it asks for
a person's approval, stop. After feedback, edit and run `finish` again. Each
command prints `next:` or `done:`; do what it says; do not check its commit
again. Never edit `.compass/`. Help: `compass <verb> --help`.

**Guardrails are hard. Strategies are soft.** **Five guardrails:**
1. Every change lands with a test that fails without it.
2. Acceptance criteria exist before the code.
3. Code traces to a criterion and a reason.
4. Evidence is a recorded command output.
5. A person approves anything irreversible.

**Evidence, not assertion.** **If it is not on disk, it did not happen.**
Scenarios: `docs/compass/<created>-<slug>/`. Manifest and evidence:
`.compass/work/<slug>/`. **Settle edge cases before scenarios** (`atdd` skill).

**Approvals.** For the labels `auth`, `payments`, `personal-data` and
`migrations`, a label the project adds, and `critical` risk, a person approves
the scenarios before any code edit. Never approve for the person: ask them to
type `/compass:approve <n>` and stop. Approve yourself only under a
delegation naming you, with `compass evidence approve --delegated --as <you>`.
Never create, extend or revoke a delegation.

**Commits.** `finish` stages the changed files and the record; do not `git
add` anything under `.compass/` yourself. Push only when asked. For any other
commit, check the staged list and commit authors. If something is staged by
mistake, say so and stop; do not retry a refused unstage. A lint fix never
weakens an assertion; re-run affected tests.

**Write for a person in the spirit of ASD-STE100.** Lead with the point. Use
`compass terminology` terms. If they are lost, re-pitch.
