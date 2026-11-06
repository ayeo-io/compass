---
description: Run a change from assessment to a checked result in one session
argument-hint: "<what you want>"
allowed-tools: Read, Write, Edit, Bash(compass *), Glob, Grep
---

# /compass:go

One command for every change. It runs the four stages of the path - assess,
specify, build and ship - in this session. Do not ask the person which Compass
command to use.

**Change:** $ARGUMENTS

## 1. Set up

Run `compass init`. If it creates `.compass/`, tell the person in one line.

## 2. Assess

Read the code the change touches, then record the ratings in one call:

```
compass quick-fix start <slug> --risk "<VALUE> - <reason>" \
  --familiarity "<VALUE> - <reason>" --size "<VALUE> - <reason>" \
  --intent "<what will be true afterwards>" \
  --scenario "Given ... When ... Then ..." --test <test node id> \
  [--labels <tag,...>] [--urgency "live-defect - <reason>"]
```

- risk: `trivial`, `contained`, `cross-cutting` or `critical`
- familiarity: `greenfield`, `brownfield-mapped` or `brownfield-unmapped`
- size: `atomic`, `small`, `medium`, `large` or `product`
- `--labels auth`, `payments`, `personal-data` or `migrations` when the
  change touches one; those make the change need a person's sign-off
- `--urgency "live-defect - <reason>"` for a defect in production: the first
  scenario is the reproduction, and its red comes first

When unsure, rate the size up. If you cannot state what will be true
afterwards, that is exploration: run `/compass:assess`, which starts a spike.

## 3. Show the plan

Run `compass approach show --issue <slug>` and show its three lines to
the person, unedited, before you edit any file. Do not wait for a confirmation: the
lines are the confirmation.

## 4. Follow the `next:` lines

Each `compass` call that writes a record of the issue ends with a
`next: <command>` line, and `compass next` prints it at any time. Run it,
then the next one. Do not stop between steps.

Stop only where a `next:` line says to wait for a person: an approval
(`compass evidence request`, then the person types `/compass:approve` or
`/compass:reject`) or a checkpoint. If a command refuses, its message says
why and how to clear it.

### Specify

- Load `bdd-specification`. On `brownfield-unmapped` code, load
  `behavior-mapping` and pin what the code does now before the change.
- When the labels include `public-api`, or the change touches a service in
  `architecture/relations.md` or a `lens_trigger_tag` in the
  `invariants.yml` of `architecture/`, take the architect's perspective first, and
  write `architecture-notes.md` beside the acceptance criteria before you
  write the scenarios.
- Ask which input classes and failure modes the intent implies that no
  scenario covers. Each becomes a scenario or is recorded with
  `compass scenario descope "<mode>" --reason "<why>"`.
- Scan the criteria for placeholders, orphan intents, untestable Thens and
  ambiguous quantifiers, and fix each in place. This self-review is not
  repeated later.
- For behavior a real client can observe, load `atdd` (`S17`).

### Build

- Load `tdd-discipline`. Each scenario goes red, then green. The binding
  decides the record: `--scenario <id>` writes `evidence/green-<id>.json`,
  and an unbound run writes `evidence/green.json`.
- On `cross-cutting` or `critical` risk, or when the assessment advises
  `regression-baseline`, run the existing suite green before you edit shared
  code, record it as `test-run` evidence on `verify.regression`, and run it
  again after the change.
- When a failure is unexpected, load `systematic-debugging`. After three
  fixes in a row that did not hold, stop and re-assess.
- Where `S17` applies, build ends with the stage 2 review (`/compass:ship`).

### Ship

When `compass next` shows the Ship stage, follow `/compass:ship`: it holds
the review that passes the gates, and the commit. Commit only when the
person asks. Until then pass `--no-commit` to `compass quick-fix finish`, and
say the change is checked, not committed.

If the change grows past its rating - more files, an unexpected design
decision, a scenario that needs a new DSL method - stop and run
`/compass:assess --reassess` with the real ratings.

## Hand-off

At the end of specify, hand `acceptance-criteria.md` to the person for a
cold read. Ask them to look for intent fidelity, untestable Thens, a missing
failure mode and ambiguous quantifiers. Where the `specify` checkpoint is
listed, wait for approval; build starts after it. Otherwise say you are going
on, and name the autonomy setting.
