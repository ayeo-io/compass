# The release line

The release line is one text, written for a user, that each shipping issue records
for the release notes. This page says where it is kept, which commands write it, what
they refuse and when a landing refuses an issue that has none. The code is
`cli/compass_pkg/release_line.py`. The decision is
`architecture/decisions/ADR-065-regular-issues-owe-an-intent-and-shipping-issues-record-a-release-line.md`.

## Where it is kept

The line is the manifest's `release_note:` key, an optional string. The manifest holds
the only copy. Every document that shows the line renders it from the manifest.

Write one sentence for a small change, or a paragraph for a larger one. No command
checks the length.

## Who writes it

Three commands take `--release-note "<text>"`. Each writes the key only when the flag
is given.

| Command | When it writes |
|---|---|
| `compass acceptance record --release-note "<text>" -- <command>` | After the command passes, with the evidence record. A failed run stores nothing. |
| `compass ship-commit --issue <slug> --release-note "<text>"` | After every landing refusal passes and before the landing commit. When nothing is staged and the issue lands at HEAD, after the stale-green, document and scope refusals. |
| `compass quick-fix finish --release-note "<text>" -- <command>` | It passes the line to `ship-commit`. With `--no-commit`, it stores the line once the three gates pass. |

- The latest write wins. A `ship-commit` with no flag keeps the stored line.
- A write that replaces a different line prints
  `compass ship-commit: release line replaced (was: <old text>)`.
- A write takes `.manifest.lock`, reads the manifest again and changes only
  `release_note`. It keeps a change that another command made after the writer's
  first read.
- Line breaks inside a line are kept in the manifest. Every reader prints the line on
  one line.

## What each writer refuses

A writer strips leading and trailing space from the line. It refuses, before it writes
anything:

| The line or the issue | Refusal |
|---|---|
| a blank line | `release-line-missing` |
| a line that starts with `#` | `release-line-heading`. `compass release notes` prints the line under a heading, where it would read as a heading of its own. |
| a line the scenario title rules refuse | the reason `compass scenario add` gives: a path that does not exist, a duration attached to a user's experience, or an outside user's experience |
| a completed or closed issue | the refusal names the issue as completed or closed |

`ship-commit --release-note` takes the issue from `--issue`, then from `COMPASS_ISSUE`
or the session issue, then from the current-task pointer. With none of these, it is
refused and names `--issue <slug>`.

## When a landing refuses

`compass ship-commit` and `compass quick-fix finish` run the refusal
`release-line-missing` before they stage or write anything. `ship-commit` judges the
manifest with the given `--release-note` applied. `quick-fix finish` judges it before
it runs the test command.

The refusal judges an issue only when all four of these hold:

1. the landing names the issue (`--issue`, `COMPASS_ISSUE` or the current-task pointer);
2. the issue is not completed and not closed;
3. its manifest has a `generation` key;
4. its stored configuration sets `release_line: true` on its approach. An issue on
   the four-stage path (ADR-092) has no approach entry. It owes a line when the
   configuration sets the field on any approach except the spike.

It then refuses an issue whose `release_note` is absent or blank. So:

- a spike lands with no line;
- a commit that names no issue is not judged;
- a completed issue landed again at HEAD after a review fix is not judged, and is not
  rewritten;
- an issue assessed before the field existed owes no line until
  `compass approach evaluate --write` commits a generation that sets it.

The refusal is not a check of `compass check`, so no archived issue is judged by it.

## Where it is shown

- `compass release notes --since <ref>` (`docs/release-notes.md`).

## Refusal codes

`release-line-missing` and `release-line-heading` are in `docs/refusal-codes.md`.
