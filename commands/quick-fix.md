---
description: The whole light path for a small, safe change
argument-hint: "<what needs fixing>"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# /compass:quick-fix

The change is small, safe, and in code whose behaviour is already written
down. Three calls: `compass quick-fix start` records the assessment,
`compass tdd-red` records the failing test, and `compass quick-fix finish`
checks the fix. Read nothing else unless one of them refuses.

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
  --risk "<VALUE> - <reason>" \
  --familiarity "<VALUE> - <reason>" \
  --size "<VALUE> - <reason>" \
  --intent "<what will be true afterwards, one sentence>" \
  --scenario "Given ... When ... Then ..." \
  --test <test node id>
```

The values, and nothing else:

- risk: `trivial`, `contained`, `cross-cutting` or `critical`
- familiarity: `greenfield`, `brownfield-mapped` or `brownfield-unmapped`
- size: `atomic`, `small`, `standard`, `large` or `product`

`--goal` and `--role` default to `delivery` and `engineer`. `--test` can
repeat. The scenario id is `TRC-001` unless you pass `--scenario-id`.

It runs `compass init`, records the assessment, computes the approach
through `compass approach evaluate`, writes `delivery-approach.md`, and
registers it with `compass issue artifact`. If it prints a `created:` line
naming `.compass/` or `docs/compass/`, report it to the user: a directory
that appears unannounced gets deleted by hand or committed by accident.

If the approach is heavier than a quick fix, it stops and says so. Continue
with `/compass:assess`: the manifest holds the values and the approach,
and the reasons go into its approach record.

## 2. Red

Write the failing test, then:

```
compass tdd-red --scenario TRC-001 -- <test command>
```

It asserts the test fails and lets `hooks/pre-tool.sh` allow code edits.
Then write the smallest correct change. Never touch the markers by hand.

## 3. Finish

```
compass quick-fix finish -m "<commit message>" --no-commit -- <test command>
```

It traces the changed files, records the green through `compass tdd-green`
with your test command, runs `compass check`, records its output through
`compass evidence`, passes the three gates and writes the devlog line.

Leave out `--no-commit` only when the user asked for a commit: it then
commits through `compass ship-commit`. With `--no-commit`, say the change
is checked and not committed, and give the commit command it prints.

If it refuses, it names the failed condition and passes no gate. Fix that
and run the same command again.

## Stop and re-assess when

The change grows - a second file, then a third, then a decision you did not
expect. The assessment was wrong. Run `/compass:assess --reassess` with the
real dimensions rather than push on. Three fixes in a row that did not hold
mean the same thing.

## Gate

- `quick-fix start` wrote `delivery-approach.md` and the one scenario;
- a red is on file for it;
- `quick-fix finish` ran to completion: the green recorded, every changed
  file traced, `compass check` passed, the three gates `pass` with
  evidence, and the devlog line written.
