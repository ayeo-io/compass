---
description: Assess an issue, re-assess it, or start a spike
argument-hint: "<issue description> [--reassess]"
allowed-tools: Read, Write(./.compass/**), Write(./docs/**), Edit(./.compass/**), Edit(./docs/**), Bash(compass *), Glob, Grep
---

# /compass:assess

Assessing never skips. You score risk, familiarity and size; `compass
approach evaluate` computes the evidence the change owes. You do not pick a
process.

**Issue:** $ARGUMENTS

## A change you can state

Every delivery change starts with this call, as `/compass:go` and
`/compass:quick-fix` do.

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
reproduction's red comes first. `--request` links what asked for the
change (an `https://` URL or `owner/repo#N`), and `--requester` names who
asked. Pass both when the request is known. Without them the check
`request-recorded` fails, but nothing stops: `compass issue link set
--request <url> --requester <name>` records them later. `start` runs
`compass init`: tell the user about a `created:` line, and read any listed
settled decisions that touch the change.

Show the three lines of `compass approach show --issue <slug>`. Then:

```
compass tdd-red --scenario TRC-001 -- <test command>
compass quick-fix finish -m "<commit message>" --no-commit -- <test command>
```

While evidence is owed, `finish` refuses and prints one `next:` line per
owed item: run them, as `/compass:go` does. Drop `--no-commit` only if the
user asked for a commit.

## The spike

If you cannot state what will be true afterwards, run `start` with
`--goal "exploration - <the question>"`. It computes a spike and stops.
Follow `${CLAUDE_PLUGIN_ROOT}/approaches/assess-procedure.md` for the
pointer and the `.spike` marker. A spike records a finding and ships
nothing.

## Re-assess

When the ratings were wrong or the change grew, read that procedure, then
run `compass approach evaluate --write --reason "..." --justify DIM="..."`.
It logs the change in
`reassessments:` and commits the next generation. The manifest's `config:`
is not read (ADR-094). It moves an issue assessed before the path onto the
path.
