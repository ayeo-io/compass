---
description: Assess risk, familiarity and size, re-assess an issue, or start a spike
argument-hint: "<issue description> [--reassess]"
allowed-tools: Read, Write(./.compass/**), Write(./docs/**), Edit(./.compass/**), Edit(./docs/**), Bash(compass *), Glob, Grep
---

# /compass:assess

Assessing is the one stage that never skips. You score the three dimensions -
judgment - and `compass approach evaluate` computes the delivery approach and
the evidence the change owes from the configuration in force. You do not pick
a process.

**Issue:** $ARGUMENTS

## A change you can state

Every delivery change starts with one call, whatever its size. This is the
start of `/compass:go` and of `/compass:quick-fix`; you do not need to load
either.

```
compass quick-fix start <slug> --risk "<VALUE> - <reason>" \
  --familiarity "<VALUE> - <reason>" --size "<VALUE> - <reason>" \
  --intent "<what will be true afterwards>" \
  --scenario "Given ... When ... Then ..." --test <test node id> \
  [--labels <tag,...>] [--urgency "live-defect - <reason>"]
```

Pass `--labels` when the change touches `auth`, `payments`,
`personal-data` or `migrations`: those tags make the change need a person's
sign-off. Pass `--urgency "live-defect - <reason>"` for a defect in
production: the first scenario is the reproduction, and its red comes first.

Risk is `trivial`, `contained`, `cross-cutting` or `critical`; familiarity
is `greenfield`, `brownfield-mapped` or `brownfield-unmapped`; size is
`atomic`, `small`, `medium`, `large` or `product`. When unsure, choose
the larger. `start` runs `compass init` first; if it prints a `created:`
line, tell the user. If it lists settled decisions, read any that touch the
change before writing code.

Run `compass approach show --issue <slug>` and show its three lines. Then
write the failing test, record it, and write the fix:

```
compass tdd-red --scenario TRC-001 -- <test command>
compass quick-fix finish -m "<commit message>" --no-commit -- <test command>
```

`finish` records the green, runs the checks and passes the gates. While the
change owes more evidence, it refuses and prints one `next:` line for each
owed item: run them, as `/compass:go` does. Leave out `--no-commit` only if
the user asked for a commit.

## A change you cannot state yet: the spike

If you cannot state what will be true afterwards, that is exploration, and
it is assessed like anything else. Run the same `compass quick-fix start`
with `--goal "exploration - <the question>"`. It records the assessment,
computes a spike and stops. Then read
`${CLAUDE_PLUGIN_ROOT}/approaches/assess-procedure.md` and follow its steps
for the pointer and the `.spike` marker. A spike
explores, concludes with a recorded finding, and ships nothing.

## Re-assess

When the ratings were wrong or the change grew, re-assess the issue rather
than continue on the old ratings. Run
`compass approach evaluate --write --reason "..." --justify DIM="..."`. It
records the change in the manifest's `reassessments:` log and commits the
next generation with any `compass issue configure` proposal;
`--reset-config` drops `config:`. A re-assess of an issue assessed before
the path moves it onto the path. Read
`${CLAUDE_PLUGIN_ROOT}/approaches/assess-procedure.md` first for the full
procedure.
