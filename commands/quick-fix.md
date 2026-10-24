---
description: Run the whole quick-fix approach for a small, safe change
argument-hint: "<what needs fixing>"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# /compass:quick-fix

The change is small, safe, and in code whose behavior is already written
down. Three calls: `compass quick-fix start` records the assessment,
`compass tdd-red` records the failing test, and `compass quick-fix finish`
checks the fix. Read nothing else unless one of them refuses.

**Issue:** $ARGUMENTS

## When this command is the wrong one

Stop and run the full pipeline if any of these is true:

- the failure would spread past one feature, lose data, lose money, or touch
  auth (that is not a quick fix, whatever the diff size);
- the existing behavior you are changing is not written down anywhere, and
  the change is more than small and contained (a small, contained one pins it
  first, below);
- it is more than about three files, or there is a design decision in it;
- you cannot state in one sentence what will be true afterwards;
- someone other than an engineer is leading the work - a product owner, a marketer or
  a designer brings artifacts this path does not write.

The most common mistake here is to rate the work too low. When unsure,
choose the larger size: it is cheap to collapse an easy stage later, but it
is expensive to find during the build that the process was too light.

## 1. Start

```
compass quick-fix start <slug> \
  --risk "<VALUE> - <reason>" \
  --familiarity "<VALUE> - <reason>" \
  --size "<VALUE> - <reason>" \
  --intent "<what will be true afterwards, one sentence>" \
  --scenario "Given ... When ... Then ..." \
  --test <test node id> \
  [--labels <tag,...>]
```

Give each dimension a value and a one-line reason. If you cannot justify a
value, ask: an unjustified value is worse than a question. `start` refuses a
missing reason or an unknown value before it writes anything. The values, and
nothing else:

- risk is consequence, never effort: a one-character change can be critical.
  - `trivial`: cosmetic or instantly obvious, and instantly reversible. No
    data, money, auth or other team.
  - `contained`: bounded to one feature, recoverable without an incident, no
    data lost.
  - `cross-cutting`: spreads across features or services, or makes
    something that many people use worse. Recovery needs coordination.
  - `critical`: can lose data or money, breach auth or privacy, or cannot be
    rolled back.
- familiarity:
  - `greenfield`: net-new, with no existing behavior to preserve.
  - `brownfield-mapped`: existing code whose behavior is already in
    scenarios, or is trivially readable.
  - `brownfield-unmapped`: existing code whose behavior is written down
    nowhere. On a small, contained change it does not stop a quick fix:
    before editing, pin with a test what the code does now where the change
    touches it (`RP-ADV-002`).
- size is the dimension most misread. When unsure, estimate up.
  - `atomic`: one file, one obvious change, under about half an hour, no
    design decision.
  - `small`: one to three files, a solution pattern that already exists here,
    no new structure.
  - `medium`, `large` or `product`: several files, a day or more, one or more
    design decisions. This is heavier than a quick fix.

`--goal` takes `VALUE - reason`; the goal is `delivery` on this path. An
`intent.md` or `positioning.md` on disk adds a check to the quick fix, not
weight. A goal of `exploration` changes the approach ("I cannot state this well enough to
deliver it yet"): that is a spike, not a small change. `--role` is ignored. `--test` can repeat. The scenario id is `TRC-001` unless you pass `--scenario-id`.

Pass `--labels` with the domains touched, comma-separated. Only `auth`,
`payments`, `personal-data` and `migrations` make the change need the
heavier process and a person's sign-off; a synonym such as `pii` does not.

It runs `compass init`, records the assessment, computes the approach
through `compass approach evaluate`, writes `delivery-approach.md`, and
registers it with `compass issue artifact set`. If it prints a `created:` line
naming `.compass/` or `docs/compass/`, report it to the user: if a directory
appears and nobody says so, someone can delete it by hand or commit it by
mistake.

If the approach is heavier than a quick fix, it stops and says so. Continue
with `/compass:assess`: the manifest holds the values and the approach,
and reasons go into its approach record.

## 2. Red

The guardrail is that a change is tested before it lands: no code
reaches main without a passing automated test it traces to. A light approach
changes how much of the code the tests cover - the one scenario and its
obvious edge cases - never whether a test exists.

Write the failing test. It must fail for the right reason: a test that fails
on a typo or a missing import has not described the behavior yet. Then:

```
compass tdd-red --scenario TRC-001 -- <test command>
```

It asserts the test fails and lets `hooks/pre-tool.sh` allow code edits. The
hook blocks a code edit that has no failing test behind it. The answer is to
write the failing test: never disable the hook, work around it, or touch the
markers by hand.

Then write the smallest correct change. Do not make it the most general:
make it more general only in refactor, with the suite green. Refactor names and
duplication with the suite green. If the test has to change, you were
changing behavior: go back to red.

### When the change has no natural failing test

A config value, a documentation string or a dependency bump has no unit that
can fail first. Use a guard that can fail: a regression run, a type check or
an end-to-end check. Run it, watch it fail, then fix.
`compass tdd-red --verified-by regression|e2e|typecheck|live` records which
kind of guard took the place of a unit test. The guard must still fail first: a sanctioned red is
not an exemption from red.

## 3. Finish

```
compass quick-fix finish -m "<commit message>" --release-note "<line>" --no-commit -- <test command>
```

It traces the changed files, records the green through `compass tdd-green`
with your test command, or the declared acceptance, runs `compass check`, records its output through
`compass evidence`, passes the three gates and writes the devlog line.

Leave out `--no-commit` only when the user asked for a commit: it
commits through `compass ship-commit`. With `--no-commit`, say the change
is checked, not committed, and give the commit command it prints.

It lists the files it commits. It refuses a file that was already changed
or untracked when `start` ran, or that sits in a directory with no tracked
file then, unless you trace it with `compass changed-file add`.

If it refuses, it names the failed condition. Fix that
and run the same command again.

## Stop and re-assess when

The change grows - a second file, then a third, then a decision you did not
expect. The assessment was wrong. Run `/compass:assess --reassess` with the
real dimensions rather than continue. Three fixes in a row that did not hold
mean the same thing.

## Gate

- `quick-fix start` wrote `delivery-approach.md` and the one scenario;
- a red (or acceptance) is on file for it;
- `quick-fix finish` ran to completion: the green recorded, every changed
  file traced, `compass check` passed, the three gates `pass` with
  evidence, and the devlog line written.
