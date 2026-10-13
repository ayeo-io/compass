---
id: ADR-057
title: Derived views go to GitHub one way, behind a refusal check
status: accepted
date: 2026-10-13
supersedes: ''
superseded_by: ''
---

Accepted by jed72 on 2026-10-13.

## Context

Compass writes an issue's labels to its linked GitHub issue when a project
switches on `github_labels` (`docs/github-labels.md`). Labels are short,
fixed words. The issue page adds a second kind of write: the rendered issue
README posted as one comment on the linked GitHub issue, and the ask written
once into an empty issue body. That text is the issue's own prose, decisions
and file names, and it reaches everyone who can read the GitHub issue. Until
now that text stayed inside the repository.

Three facts shaped the decision:

- After a record-changing command, the entry point ran the label sync first
  and the README render second. A step that copied the README in the label
  sync's place would post the README as it was before the command.
- `github-sync.yml` was rewritten whole by each write, so a second write's
  result would erase the first's.
- No check stood between the repository's text and GitHub.

The board, a project index issue and any later tracker write would reuse
whatever rule this issue sets, so the rule is recorded here rather than only
in the owning doc.

## Decision

1. **Order.** After a command exits 0, three steps run in this order: the
   label sync, the README render, then the page step. The page step reads the
   README file the render wrote and never renders text itself. It syncs only
   the issue the command named. A linked issue whose README the render also
   rewrote waits for its own next sync, and `compass issue lint` reports its
   page as out of date meanwhile.
2. **One way.** Compass writes to GitHub and reads back only what it needs to
   find its own writes: the id of the comment that opens with its marker line,
   and whether the issue body is empty. No text read from GitHub enters the
   manifest, the issue's documents or `github-sync.yml`.
3. **Exit codes.** A sync that runs after another command never changes that
   command's exit code. A failure is one line on standard error and an error
   in `github-sync.yml`. The on-demand `compass issue github sync` is the one
   place a failed or refused write makes the exit code non-zero, because the
   person asked for it.
4. **One record writer.** One function writes `github-sync.yml`. It keeps the
   section of the write that did not run and changes only the section of the
   write that did. Labels and page each keep their own error.
5. **The refusal check is the boundary.** Before any GitHub call for the
   page, two checks read the text as it would be posted, after link
   rewriting and after the size bound:
   - paths to files the project keeps out of git, and any file under
     `.compass/private/`;
   - credential shapes that `redact` would replace.
   A block the size bound leaves out is not checked, because it is not
   posted.
6. **Refused whole.** A hit in the comment or in the body refuses both. No
   partial post is made, and nothing is redacted and posted in its place.
7. **Off by default.** The page is a third switch, `github_labels.page`, off
   by default. With it off, no call is added to what the label sync makes
   (ADR-006).

## Alternatives considered

- **Render the README in memory inside the page step.** It keeps the old
  order but gives the README a second code path, so the comment and the file
  could disagree. Rejected.
- **Redact and post.** Replace a found path or credential and post the rest. It
  keeps the page current, but a redaction rule that misses one form leaks it,
  and the reader cannot tell what was removed. Refusing is safer; the cost is
  a stale page until the text is fixed, which lint reports.
- **Check the README file rather than the posted text.** It would refuse a
  page for a chart the size bound leaves out and pass a link rewriting
  produced. Rejected: the check reads what leaves.
- **Scan the page for rival product names.** The page carries the issue's
  own requirements, which state how things work without naming or comparing
  other products, so a name scan would guard against text the documents do
  not hold. Rejected by jed72 on 2026-10-13. The repository's own
  rival-name gate in `scripts/` is unchanged.
- **One record file per write.** It removes the overwrite but splits one
  issue's GitHub state across files that lint must join. One writer over one
  file is simpler.

## Consequences

- A project that turns on the page widens the audience of its issue
  documents to everyone who can read the GitHub issue. The owning doc,
  `docs/github-labels.md`, says so.
- A refused or failed page stays stale until the next successful sync; lint
  reports it.
- A command that triggers both writes can wait for the `gh` timeout of each
  call it makes. An unchanged page makes no call, because the digest of the
  text to post is computed from local files and git only.

## References

- ADR-005, state lives on disk; ADR-006, a new mechanism does nothing unless
  adopted.
- ADR-014 (superseded by ADR-019 and ADR-020; ADR-024 now carries its
  removal rule) and ADR-044: a released verb is removed at the major
  version, which is how the label sync's on-demand verb becomes
  `compass issue github sync` at 7.0.0.
- ADR-051, rendered blocks are derived in place; the render step imports
  nothing from the label sync, and the page step imports nothing from the
  render.
- `docs/github-labels.md`, the owning doc.
