# Compass operating contract

**Assess before you change anything.** Run `/compass:assess` before editing
code, specs or artifacts. You read risk, familiarity, size and goal; the CLI
computes the delivery approach.

**Never skip assessment.** Only conversation is exempt: answering,
explaining, reading. Before a tool call changes a file, the issue must be
assessed.

**Trigger on intent, not on the command.** If someone describes work to build,
change or fix, assess first even if they never typed the command.
Explicitly typing any Compass command
always works. If `.compass/current-task` already points at an assessed issue,
carry on with it.

**Guardrails are hard. Strategies are soft.** Five guardrails:

1. Every change lands with a passing test that covers it.
2. Acceptance criteria exist before the code.
3. Code traces to a criterion and a reason.
4. Evidence is a recorded command output, never a claim that something passed.
5. A human approves anything irreversible.

Strategies, such as testing first, can be stepped off with a recorded reason;
guardrails cannot.

**Approvals.** Approve only under a delegation naming you, with `compass
evidence approve --delegated --as <you>`. Otherwise run `compass
evidence request`, ask the person to type `/compass:approve` or
`/compass:reject`, and stop. Never create, extend or revoke a delegation.

**Evidence, not assertion.** Use the CLI: `compass tdd-red -- <cmd>` records a
failing test, `compass tdd-green -- <cmd>` a passing one, and `compass check`
runs the guardrails.

**If it is not on disk, it did not happen.** Documents go to
`docs/compass/<created>-<slug>/`, registered in the manifest. The manifest,
evidence and markers live in `.compass/work/<slug>/`. Another session
resumes from those files.

**Stages, in order**, each with a `/compass:*` command:

1. assess
2. define acceptance criteria
3. refine
4. plan
5. break down
6. implement
7. verify
8. ship

Honour the delivery approach's stage weights.

**Record friction you observe.** If a step costs more than it returns and
will recur, run `compass issue friction` with evidence and a one-line fix.

**Where to look.** `compass <verb> --help` explains a verb; the
`compass-runtime` skill maps the stages.

**Write for someone with no context.** Why before what, no reference a reader
cannot follow, and stop once you have said it.

**A person's approval is theirs to give.** Never record it for them. Print
the exact command for their own terminal, with no `!` prefix, and stop.

**Commit only what you mean to.** Stage each file by its path, never
`.compass/`, and check the staged list and the commit's authors. If
something is staged by mistake, say so and stop; do not retry a refused
unstage. A lint fix never weakens an assertion; re-run the affected tests.

**Settle edge cases before scenarios.** Read
`skills/bdd-specification/SKILL.md`.
