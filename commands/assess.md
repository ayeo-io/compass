---
description: Assess risk, familiarity and size, re-assess an issue, or start a spike
argument-hint: "<issue description> [--reassess]"
allowed-tools: Read, Write(./.compass/**), Write(./docs/**), Edit(./.compass/**), Edit(./docs/**), Bash(compass *), Glob, Grep
---

# /compass:assess

Assessing never skips. You score risk, familiarity and size, and
`compass approach evaluate` computes the evidence the change owes from the
configuration in force. You do not pick a process.

**Issue:** $ARGUMENTS

## A change you can state

Every delivery change starts with one call, whatever its size. It is also
the start of `/compass:go` and `/compass:quick-fix`.

```
compass quick-fix start <slug> --risk "<VALUE> - <reason>" \
  --familiarity "<VALUE> - <reason>" --size "<VALUE> - <reason>" \
  --intent "<what will be true afterwards>" \
  --scenario "Given ... When ... Then ..." --test <test node id> \
  [--labels <tag,...>] [--urgency "live-defect - <reason>"]
```

`--labels auth`, `payments`, `personal-data` or `migrations` make the
change need a person's sign-off. `--urgency "live-defect - <reason>"` marks
a production defect: its reproduction's red comes first. When unsure of a
value, choose the larger. `start` runs `compass init` first: tell the user
about a `created:` line, and read any listed settled decisions that touch
the change.

Show the three lines of `compass approach show --issue <slug>`. Then:

```
compass tdd-red --scenario TRC-001 -- <test command>
compass quick-fix finish -m "<commit message>" --no-commit -- <test command>
```

While evidence is owed, `finish` refuses and prints one `next:` line per
owed item: run them, as `/compass:go` does. Leave out `--no-commit` only if
the user asked for a commit.

## The spike

If you cannot state what will be true afterwards, run the same `start`
with `--goal "exploration - <the question>"`. It computes a spike and
stops. Follow `${CLAUDE_PLUGIN_ROOT}/approaches/assess-procedure.md` for the
pointer and the `.spike` marker. A spike concludes with a recorded finding
and ships nothing.

## Re-assess

When the ratings were wrong or the change grew, run
`compass approach evaluate --write --reason "..." --justify DIM="..."`
after reading `approaches/assess-procedure.md`. It logs the change in
`reassessments:`; `--reset-config` drops `config:`. A re-assess of an
issue assessed before the path moves it onto the path.
