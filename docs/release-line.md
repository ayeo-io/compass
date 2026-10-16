# The release line

This page is the owning doc for the release line: one text, written for a user, that
each shipping issue records for the release notes. It states where the line is kept,
which commands write it, which texts are refused, when a landing refuses an issue that
has none, and where the line is shown. The code is `cli/compass_pkg/release_line.py`.
The decision is
`architecture/decisions/ADR-065-regular-issues-owe-an-intent-and-shipping-issues-record-a-release-line.md`.

## Where it is kept

The line is the manifest's `release_note:` key, an optional string. The manifest is
the only copy. Every document that shows the line renders it from the manifest, so no
document holds a second copy that could drift.

Write it for a user: one sentence for a quick fix or a hotfix, a paragraph for regular
or full. No command checks the length.

## Who writes it

Three commands take `--release-note "<text>"`, and each writes the key only when the
flag is given:

| Command | When it writes |
|---|---|
| `compass acceptance record --release-note "<text>" -- <command>` | After the command passes, with the evidence record. A failed run stores nothing. |
| `compass ship-commit --issue <slug> --release-note "<text>"` | After every landing refusal passes and before the landing render, so the landing commit's documents show the line. When nothing is staged and the issue lands at HEAD, after the stale-green, document and scope refusals. |
| `compass quick-fix finish --release-note "<text>" -- <command>` | It passes the line to `ship-commit`. With `--no-commit`, it stores the line once the three gates pass. |

The latest write wins. A `ship-commit` with no flag keeps the stored line. A write that
replaces a different line prints one line with the old text:
`compass ship-commit: release line replaced (was: <old text>)`.

A write takes `.manifest.lock`, reads the manifest again and changes only
`release_note`, so a change another command made to the manifest after the writer's
first read is kept. Two other commands that each write the whole manifest can still
lose one another's change; the release line does not change that.

## What each writer refuses

Before anything is written, a given line is stripped of leading and trailing space and
refused when:

- it is blank: the `release-line-missing` refusal, the same text a landing gives;
- it starts with `#`: the `release-line-heading` refusal, because the living spec reads
  a line such as `### <slug> (completed <date>)` as one of its issue headings;
- the living spec's title rules refuse it as a scenario title, with the reason
  `compass scenario add` gives: a path that does not exist, an eval scenario id, a
  duration attached to a user's experience, or an outside user's experience.

Each writer also refuses a completed or closed issue, naming it as completed or closed,
so a landed record is never rewritten. `ship-commit --release-note` with no issue named
is refused and names `--issue <slug>`. Line breaks inside a line are kept in the
manifest; every reader prints the line on one line.

## When a landing refuses

`manifest.LANDING_REFUSALS` holds the release-line refusal, `release-line-missing`. It
runs at every landing, `compass ship-commit` and `compass quick-fix finish`, before
anything is staged or written. `ship-commit` judges a copy of the manifest with the
given `--release-note` applied, and `quick-fix finish` judges it before it runs the test
command.

The refusal judges an issue only when all four of these hold, and declines otherwise:

1. the landing names the issue (`--issue`, `COMPASS_ISSUE` or the current-task pointer);
2. the issue is not completed and not closed;
3. its manifest has a `generation` key;
4. its stored configuration sets `release_line: true` on its approach.

When it judges, it refuses an issue whose `release_note` is absent or blank. So:

- a spike lands with no line, because the shipped spike has no `release_line` field;
- a commit with no issue named is not judged;
- a completed issue landed again at HEAD after a review fix is not judged, and is not
  rewritten;
- an issue assessed before the field existed owes no line until
  `compass approach evaluate --write` commits a generation that sets it;
- a project on the 5.x governance files has no generation and owes no line.

The refusal is not a check of `compass check`, so no archived issue is judged by it.

## Where it is shown

- The verification report's `## Release line` section, through the `release-line`
  rendered block (`docs/rendered-blocks.md`).
- The verification note of a quick fix, as `Release: <text>`.
- The project index, in the Release column.
- The living spec, under the issue's heading.
- `compass release notes --since <ref>` (`docs/release-notes.md`).

## Refusal codes

`release-line-missing` and `release-line-heading` are in `docs/refusal-codes.md`.
