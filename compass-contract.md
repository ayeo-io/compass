# Compass operating contract

This project uses Compass: follow this in every session.

**Assess before you change anything.** Before editing code, specs or product
artifacts, run `/compass:assess`: you read risk, familiarity, size and goal,
and the CLI computes the delivery approach. You do not choose the process.

**Never skip assessment.** The only exempt work is conversation - answering a
question, explaining code, reading to understand. The moment a tool call would
change a file, the current issue must already have been assessed.

**Trigger on intent, not on the command.** If someone describes work to build,
change or fix, assess first even if they never typed the command. This adds to
explicit invocation rather than replacing it: typing any Compass command
always works. If `.compass/current-task` already points at an assessed issue,
carry on with it rather than assessing again.

**Guardrails are hard. Strategies are soft.** Five guardrails:

1. Every change lands with a passing test that covers it.
2. Acceptance criteria exist before the code.
3. Code traces to a criterion and a reason.
4. Evidence is a recorded command output, never a claim that something passed.
5. A human approves anything irreversible.

Strategies, such as testing first, can be stepped off with a recorded reason;
guardrails cannot.

**Evidence, not assertion.** Use the CLI: `compass tdd-red -- <cmd>` records a
failing test, `compass tdd-green -- <cmd>` a passing one, and `compass check`
runs the guardrails against what is on disk.

**If it is not on disk, it did not happen.** Stage documents go to
`docs/compass/<created>-<slug>/`, registered in the manifest. The manifest,
evidence and markers live in `.compass/work/<slug>/`. A later session, or
another agent, picks the work up from those files.

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

**Where to look.** `compass <verb> --help` explains a verb; the
`compass-runtime` skill maps the stages.

**Write for someone with no context.** Why before what, no reference a reader
cannot follow, and stop once you have said it.
