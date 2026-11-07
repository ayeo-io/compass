---
description: Assess an issue, re-assess it, or start a spike
argument-hint: "<issue description> [--reassess]"
allowed-tools: Read, Write(./.compass/**), Write(./docs/**), Edit(./.compass/**), Edit(./docs/**), Bash(compass *), Glob, Grep
---

# /compass:assess

You score risk, familiarity and size; `compass approach evaluate`
computes the evidence the change owes. You do not pick a process.

**Issue:** $ARGUMENTS

## A change you can state

Every change starts here, as in `/compass:go` and `/compass:quick-fix`.

```
compass quick-fix start <slug> --risk "<VALUE> - <reason>" \
  --familiarity "<VALUE> - <reason>" --size "<VALUE> - <reason>" \
  --intent "<what will be true afterwards>" \
  --scenario "Given ... When ... Then ..." --test <test node id> \
  --request <url> --requester "<name>" \
  [--labels <tag,...>] [--urgency "live-defect - <reason>"]
```

Risk is `trivial`, `contained`, `cross-cutting` or `critical`; familiarity
`greenfield`, `brownfield-mapped` or `brownfield-unmapped`; size `atomic`,
`small`, `medium`, `large` or `product`. When unsure, choose the larger.
`--labels auth`, `payments`, `personal-data` or `migrations` need a
person's sign-off. `--urgency` marks a production defect: its
reproduction's red comes first. `--request` (an `https://` URL or
`owner/repo#N`) and `--requester` record what asked and who. Without them
`request-recorded` fails but nothing stops; `compass issue link set` adds
them later. `start` runs `compass init`: tell the user about a `created:`
line, and read any listed settled decisions that touch the change.

Show the three lines of `compass approach show --issue <slug>`. Then:

```
compass tdd-red --scenario TRC-001 -- <test command>
compass quick-fix finish -m "<commit message>" --no-commit -- <test command>
```

While evidence is owed, `finish` prints one `next:` line per owed item:
run each. Drop `--no-commit` only if the user asked for a commit.

## The spike

If you cannot state what will be true afterwards, run `start` with
`--goal "exploration - <the question>"`. It stops there.
Follow `${CLAUDE_PLUGIN_ROOT}/approaches/assess-procedure.md` for the
pointer and the `.spike` marker. A spike records a finding and ships
nothing.

## Re-assess

When a rating was wrong or the change grew, read that procedure, then
run `compass approach evaluate --write --reason "..." --justify DIM="..."`.
It logs the change in `reassessments:`, commits the next generation, and
moves an issue assessed before the path onto it.
