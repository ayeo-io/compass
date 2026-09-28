---
description: The whole light path for a small, safe change
argument-hint: "<what needs fixing>"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# /compass:quick-fix

The change is small, safe, and in code whose behaviour is already written
down. `compass quick-fix start` opens the issue and records the assessment
in one call; `compass quick-fix finish` checks, traces and ships in another.
Between them you write one failing test and the code that turns it green.
Load `quick-fix` alongside it and read nothing else.

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
choose the larger size: collapsing an easy stage later is cheap, discovering
mid-build that the process was too light is not.

## 1. Start

```
compass quick-fix start <slug> \
  --risk "<VALUE - reason>" --familiarity "<VALUE - reason>" --size "<VALUE - reason>" \
  --goal "delivery" --role "engineer" \
  --intent "<sentence>" \
  --scenario "Given ... When ... Then ..." --scenario-id <id> \
  --test <node-id>
```

`--test` repeats for more than one test; `--goal` and `--role` default to
`delivery` and `engineer`, and can carry a reason.

Before writing anything, the verb refuses a dimension with no reason, or a
value the policy does not know, and names which. It then runs `compass init`,
writes the manifest, and computes the approach through `compass approach
evaluate`. If the result is not a quick fix, it says so, keeps the
assessment, and hands off to `/compass:assess` - exit non-zero, nothing else
written. Re-examine a dimension, not the computed approach.

Otherwise it writes `delivery-approach.md`, registers it with `compass issue
artifact delivery-approach`, sets `.compass/current-task`, and records the
scenario against the intent, all in one call. If it created `.compass/` or
`docs/compass/`, it prints the line - report it, since an unannounced
directory is how it gets deleted by hand or committed by accident.

## 2. Red, green

Write the failing test, then:

```
compass tdd-red --scenario <id> -- <test command>
```

The CLI runs it, asserts it genuinely fails, and drops the marker
`hooks/pre-tool.sh` reads before it lets you edit code. Write the smallest
correct change, then:

```
compass tdd-green --scenario <id> -- <test command>
```

It asserts the test passes and clears the marker. Refactor with the suite
green; never touch the markers by hand.

## 3. Finish

```
compass quick-fix finish -m "<message>"
```

It checks every precondition first: the approach is still `quick-fix`, no
gate is pending beyond the three, the scenario has a green on file, and -
with more than one scenario - every changed path is already traced. Any
unmet condition is named, nothing is committed, exit non-zero.

Once those hold, `finish` does the rest of shipping in one call: traces
each changed path, runs `compass check`, records the output through
`compass evidence`, passes the three gates against that check and the
green, appends the devlog line, and commits through `compass ship-commit`.

## Stop and re-assess when

The change grows - a second file, then a third, then a decision you did not
expect. The assessment was wrong; the move is `compass quick-fix start`
again with the real dimensions, not pushing on with a process you no longer
believe. Three consecutive fixes that did not hold means the same thing.

## Gate

- `quick-fix start` wrote `delivery-approach.md` and the one scenario;
- a red and a green are both on file for it;
- `quick-fix finish` ran to completion: every changed file traced, `compass
  check` passed, the three gates `pass` with evidence, the commit landed and
  the devlog line was written.
