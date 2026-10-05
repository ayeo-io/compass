---
description: Assess risk, familiarity, size and goal, and compute the delivery approach
argument-hint: "<issue description> [--reassess]"
allowed-tools: Read, Write, Edit, Glob, Grep
---

# /compass:assess

Assessing is the one stage that never skips. You read the four dimensions -
judgement - and `compass approach evaluate` computes the delivery approach
from `governance/routing-policy.yml`. You do not pick a process.

**Issue:** $ARGUMENTS

## A small change an engineer is making

This is the whole of `/compass:quick-fix`; you do not need to load it.

```
compass quick-fix start <slug> --risk "<VALUE> - <reason>" \
  --familiarity "<VALUE> - <reason>" --size "<VALUE> - <reason>" \
  --intent "<what will be true afterwards>" \
  --scenario "Given ... When ... Then ..." --test <test node id> \
  [--labels <tag,...>]
```

Pass `--labels` when the change touches `auth`, `payments`,
`personal-data` or `migrations`: those tags bring the human sign-off.

Risk is `trivial`, `contained`, `cross-cutting` or `critical`; familiarity
is `greenfield`, `brownfield-mapped` or `brownfield-unmapped`; size is
`atomic`, `small`, `standard`, `large` or `product`. When unsure, choose
the larger. `start` runs `compass init` first; if it prints a `created:`
line, tell the user. If it lists
settled decisions, read any that touch the change before writing code.

Then write the failing test, record it, and write the fix:

```
compass tdd-red --scenario TRC-001 -- <test command>
compass quick-fix finish -m "<commit message>" --no-commit -- <test command>
```

`finish` records the green, runs the checks and passes the gates. Leave out
`--no-commit` only if the user asked for a commit. If `start` says the
approach is heavier than a quick fix, the manifest holds the values and
the approach: read the full procedure named below and continue from its step 4,
giving each value its reason there.

## Anything else: the full procedure

Read `${CLAUDE_PLUGIN_ROOT}/approaches/assess-procedure.md` and follow it
before you write anything when any of these holds:

- the change is not a small one an engineer is making;
- `quick-fix start` said the approach is heavier than a quick fix;
- `--reassess` was passed; it re-runs `compass approach evaluate --write
  --reason "..."`.

It holds the setup, `--reassess`, the full procedure and the gate.
