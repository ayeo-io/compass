---
description: Start any change with one command - assess it, show the plan in three lines, then begin
argument-hint: "<what you want>"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# /compass:go

One command for the ordinary path. It sets Compass up if needed, assesses
the change, shows the person the plan in three lines, and starts the work.
Do not ask the person which Compass command to use: this one decides.

**Change:** $ARGUMENTS

## 1. Set up

Run `compass init`. It is safe every time: it creates `.compass/` only if it
is missing, and says so. Tell the person in one line if it created it.

## 2. Assess

Read the code the change touches, then rate it honestly and record it in one
call:

```
compass quick-fix start <slug> --risk "<VALUE> - <reason>" \
  --familiarity "<VALUE> - <reason>" --size "<VALUE> - <reason>" \
  --intent "<what will be true afterwards>" \
  --scenario "Given ... When ... Then ..." --test <test node id> \
  [--labels <tag,...>]
```

- risk: `trivial`, `contained`, `cross-cutting` or `critical`
- familiarity: `greenfield` (new code), `brownfield-mapped` (existing code
  whose behaviour tests or docs pin) or `brownfield-unmapped`
- size: `atomic`, `small`, `medium`, `large` or `product`
- `--labels auth`, `payments`, `personal-data` or `migrations` when the
  change touches one; those bring the human sign-off

A rating is a judgement with a reason, not a way to reach a lighter process.
When unsure, rate the size up.

## 3. Show the plan

Run `compass approach show --issue <slug>` and show its three lines to
the person, unedited, before you edit any file. They are the only Compass
text the person needs before code: the approach, the gates it must pass,
and where its files go.

## 4. Continue

Do not stop to ask whether to go ahead.

- **Quick fix:** write the failing test and record it against the one
  scenario `quick-fix start` wrote, then make the change and finish:

  ```
  compass tdd-red --scenario TRC-001 -- <test command>
  compass quick-fix finish -m "<commit message>" --no-commit -- <test command>
  ```

  The change is checked and gated but not committed: committing is the
  person's to ask for. Say so when you finish.
- **Anything heavier:** `quick-fix start` has already recorded the
  assessment and computed the approach. Run `/compass:assess` steps 4 to 6,
  from `${CLAUDE_PLUGIN_ROOT}/approaches/assess-procedure.md`
  (write `delivery-approach.md`, the pointer and any spike marker), then
  follow that approach's stages. Do not wait at its step 7: the summary you
  showed is the confirmation, and the person can still override a dimension
  at any point.
- **Not yet clear what it delivers:** if you cannot state what will be true
  afterwards, that is exploration. Run `/compass:assess`; it routes a spike. <!-- vocabulary-scan: allow - route is a verb here -->

If a command refuses, its message says why and how to clear it. Act on it;
ask the person only for a decision that is theirs, such as approving an
irreversible change.
