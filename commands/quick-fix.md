---
description: The whole light path for a small, safe change
argument-hint: "<what needs fixing>"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# /compass:quick-fix

The change is small, safe, and in code whose behaviour is already written
down. This one
file is the whole path - assess, state the criterion, build it test-first,
check the result, ship. Load `quick-fix` alongside it and read nothing else.

**Issue:** $ARGUMENTS

## When this command is the wrong one

Stop and run the full pipeline if any of these is true:

- the failure would spread past one feature, lose data, lose money, or touch
  auth (that is not a quick fix, whatever the diff size);
- the existing behaviour you are changing is not written down anywhere;
- it is more than about three files, or there is a design decision in it;
- you cannot state in one sentence what will be true afterwards;
- someone other than an engineer is driving - a product owner, a marketer or
  a designer brings artifacts this path does not write.

Guessing low here is the failure this path is most prone to. When unsure,
choose the larger size: collapsing a stage that turned out easy is cheap, discovering
mid-build that the process was too light is not.

## 1. Assess

Run `compass init`. It creates `.compass/` if it is absent and says so;
if the project is already there it changes nothing. Tell the user in one line
when it created something - a directory appearing unannounced is how it gets
deleted by hand or committed by accident.

Pick a slug. Make `.compass/work/<slug>/` and write `manifest.yml` into it
from `${CLAUDE_PLUGIN_ROOT}/templates/manifest.yml`.

Read the four dimensions into the manifest's `assessment:` block - risk,
familiarity, size, goal and role - each with a one-line justification. The
skill has the scoring tests. If you cannot justify a value, ask rather than
guess.

Then compute the approach:

```
compass approach evaluate --issue <slug> --write
```

You do not pick the approach and you do not apply a policy rule by hand. The
CLI reads `governance/routing-policy.yml` against the assessment you just
recorded and folds the result - `delivery_approach`, `stages`, `gates`,
`orchestration` - back into the manifest. **If it comes back as anything
other than a quick fix, this command is over**: the work is heavier than it
looked. Say so, keep the assessment you just recorded, and continue from
`/compass:assess`, which hands off to the full pipeline. Do not argue with the
result - the CLI applied the policy to the four values you recorded, so the
thing to re-examine is a dimension, not the approach.

Write the record itself to `docs/compass/<created>-<slug>/delivery-approach.md`,
where the date is the manifest's `created:` field, and register it with
`compass issue artifact delivery-approach --status draft --path <that path>`.
If you created `docs/compass/`, say so in one line - a directory appearing with
nothing said is how it gets deleted by hand or committed by accident.

Its content comes from `${CLAUDE_PLUGIN_ROOT}/templates/delivery-approach.md`: the four dimensions
with their justifications, the computed approach, any policy rule the CLI
reported, and the de-scope ledger - each collapsed stage with its "safe to
skip because..." line. Write the slug into `.compass/current-task` so later
`compass` calls resolve without a flag.

This is the only document a quick fix owes. Everything else it records is a
machine-readable entry the CLI reads back.

## 2. State the one criterion

One Given/When/Then scenario, and it is the spec. It must be genuinely
unambiguous - the requirements review is collapsed only because the scenario
is unambiguous, so if the scenario needs a conversation to interpret, the
approach was wrong.

Write it into the manifest's `scenarios:` block: a stable id, a title, the
`intent` it serves, and the `tests` that will exercise it. That block is what
`compass check` reads for the acceptance-before-code guardrail. Put the same
scenario in `delivery-approach.md` so a person can read it without opening
the manifest.

Zero scenarios is never valid; one is the minimum.

## 3. Build it test-first

Write the failing test, then:

```
compass tdd-red --scenario <id> -- <test command>
```

The CLI runs it, asserts it genuinely fails, records the failure and drops the
marker `hooks/pre-tool.sh` reads before it will let you edit code. If the test
passes, the CLI refuses and says so - you skipped red. Never touch the markers
by hand; the CLI owns them.

Then write the smallest correct change and:

```
compass tdd-green --scenario <id> -- <test command>
```

It asserts the test passes, records the green under the scenario id, and
clears the marker. Refactor with the suite green.

For each production file you touched, add an entry to the manifest's
`changed_files:` - the path and the scenario id it traces to. That is the
code-to-criterion half of traceability, and `compass check` checks it.

## 4. Verify

Run the new test and the existing suite. Then:

```
compass check --issue <slug>
```

This is the mechanical gate: every scenario has a test, a green is on file,
every changed file traces to a scenario, every gate marked pass has evidence
that resolves. It exits non-zero on any failure.

Read what it says rather than the exit code alone. A line like "no
changed_files recorded yet" or "0/3 pass gates" is green and asserts nothing;
counting it as progress is how an untraced change ships.

Record the check's own output and clear the three gates against it:

```
compass check --issue <slug> --evidence-out evidence/check-output.txt
compass evidence add --issue <slug> --type command-output --path evidence/check-output.txt
compass gate pass verify.governance --issue <slug> --evidence EV-<id>
```

`verify.correctness` points at the scenario-bound green record,
`verify.traceability` and `verify.governance` at the check output. "It passed"
is not a gate-clearing statement; the recorded output is.

A quick fix writes no verification report. The gates and their evidence
pointers are the record.

## 5. Ship

```
compass ship-commit --issue <slug> -m "<message>"
```

It commits on the current branch and errors if HEAD did not move, so a commit
that did not happen cannot count as shipped. Write the message for someone who was not
in the conversation: what changed and why, no agent attribution trailer and no
"generated with" footer.

Add one line to `devlog.md`: what changed, and what proved it.

## Stop and re-assess when

The change grows - a second file, then a third, then a decision you did not
expect. The assessment was wrong, and the move is
`compass approach evaluate` again with the real dimensions, not pushing on
with a process you no longer believe. Three consecutive fixes that did not
hold means the same thing: stop.

## Gate

- `delivery-approach.md` exists with justified dimensions and a de-scope ledger;
- the manifest carries one scenario with an id, an intent and a test;
- a red record and a green record are both on file for it;
- every changed file traces to it;
- `compass check` passes;
- the three gates are `pass` with evidence that resolves;
- the commit is made and the devlog line written.
