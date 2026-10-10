---
id: ADR-046
title: The delivery board is one data set with one renderer per output
status: accepted
date: 2026-10-09
supersedes: ''
superseded_by: ''
---

## Context

`compass flow` shows the delivery board as text and as `--json`. A new page, written by `compass board render`, shows the same issues with more fields: the assessment, the policy rules that fired, the depth of each stage and every gate.

Three outputs that each build their own rows would place the same issue in different states. `compass flow --json` is also a public contract: a consumer reads its keys, so removing or retyping one breaks that consumer until the next major version.

## Decision

**`board()` in `cli/compass_pkg/flow.py` builds the board data once. Each output renders that data and reads nothing else.**

- The text board, `--json` and the page all take their rows from `board()`. The state comes from the one lifecycle accessor (ADR-045) and the stage from the function `compass next` uses, called through its module at call time, so the two cannot disagree.
- Each row carries the lane the page puts it in. The page never works out a lane from the section a row sits in.
- Escaping lives in the page renderer only. Every recorded value goes through it, and nothing else writes a value into the markup.
- `compass flow --html` and `compass board render` call one function, `board_cmd.build_page`, so the two pages cannot differ.
- The page is generated output. Nothing reads it back and nothing commits it.
- **`compass flow --json` is additive within a major version.** A new key can appear. No key a release held is removed, renamed or retyped, and the section headings stay the keys of the `sections` object. A test pins the full key set, so a removed key fails.
- A row the page cannot place (a schema major this Compass does not read, a `current_phase` that names no stage, a new field of the wrong type) keeps the section it had in `--json` and carries an `unplaceable` reason. The page lists it in a note.

The rule for every other `--json` command is not decided here. Each of those commands needs its own key pin first.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| One row builder per output | Each output stays simple. | The outputs would drift: the same issue could be in progress in one and ready in another. |
| Render the page from the `--json` text | One source for machine and page. | It adds a process and a text round trip, and the page needs fields `--json` should not have to carry as text. |
| Keep the old table writer beside the page | No change to `--html` output. | Two writers for one board. The page replaces the tables. |
| Store the generated page at ship | A reader could open it without running a command. | A derived view would become state (ADR-005, ADR-008). |
| Write the `--json` rule for every command now | One rule everywhere. | It cannot be pinned without a key list for each command, and those commands are out of scope. |

## Consequences

**Positive:**
- The text board, `--json` and the page place every issue in the same state.
- A new view reads the data function and adds no state logic.
- A removed `--json` key fails a test.

**Negative:**
- `compass flow --html` now writes the board page. The old tables are gone. This is a release-note item.
- Once a release holds the new row keys, a rename waits for 7.0.0.
- The page escapes values in one module, so a fault there affects every value. The page also carries a Content-Security-Policy tag that refuses script and external loads if escaping ever failed.

**Neutral / follow-on:**
- The board's schema-major test sits beside the one in `core.load_manifest`, because this change leaves manifest loading alone. The loaders can share one test later.

## References

- ADR-003: flow advises and never gates.
- ADR-005: state is reconstructible from disk, so a derived view is not stored.
- ADR-008: the living spec is derived and never edited by hand.
- ADR-044: vocabulary and CLI naming, and the `--json` consequence for the board.
- ADR-045: the issue lifecycle is derived from records.
