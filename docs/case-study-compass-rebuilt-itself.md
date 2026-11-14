# Compass turned its own delivery process on itself - here's what the record shows

In August 2026 the maintainer used Compass to rewrite Compass's own
vocabulary, rename its own commands and migrate its own issue archive to a
new schema, as Compass issues under Compass's own gates. This page says what
the record of that work shows, and what a reader can and cannot check.

The work took nine slices and eleven pull requests, two of them sent back
for more work. The commits, the pull requests and the test suite are public.
The issue-by-issue record is not.

## The rename

Compass 1.x had a private vocabulary - "route" for a delivery approach, "frame" for triage, and so on. <!-- vocabulary-scan: allow - quotes the retired noun this sentence explains -->
The v2 rewrite replaced it with the industry's words, one word per concept,
frozen as `governance/terminology.yml` (commit `681766c`): 49 terms and 16
banned v1 spellings. A test (`tests/test_terminology.py`) scans the
repository's prose and fails on a banned term.

Nine surfaces, such as templates, commands, skills and docs, started on a
`pending_surfaces` list that could only shrink:

- Four of the nine slices struck a surface off the list: slices 3, 5, 6
  and 7.
- The other five were the freeze, the session instructions, the machine
  manifest, the migrator and the release.
- The list reached zero at 7b, merged as `b6017b0` in pull request #33.

The list was not the whole repository. Cutting the 2.1.0 release found a
tenth document that had never been on it: the install smoke test still told
a new user to run a v1 command and expect v1 fields. The scanner had never
read the file, and the version guard for it searched for the retired
spelling. A person reading found both.

Eleven pull requests carried the nine slices, because three slices were
split in two (3a/3b, 5a/5b, 7a/7b). Two splits were decided in advance and
the third, 7a/7b, mid-session. Two of the eleven came back with changes
requested, recorded in this repository's devlogs and evidence files, not in
a GitHub review thread:

- **PR #31** rewrote thirteen skills and ten agent files. The scanner was
  green, but the prose had tautologies like "TDD is the TDD strategy". It
  went back for a hand-polish pass.
- **PR #32**, the docs slice, came back because part of its read-aloud pass
  was half-finished.

The rewrite closed in fifteen sessions of a sixteen-session budget. The
record re-baselined the budget at session twelve, when the original
twelve-session estimate proved wrong. It landed as `7071672` on `main`,
tagged `v2.0.0`, through pull request #35. The release commit inside it,
`5a4da2d`, calls it "the industry's words, the same behaviour."

## The migrator

`compass issue migrate` rewrites another project's 1.x archive to the new
schema. The `migrations` label raised its delivery approach to a full human
sign-off gate. `compass check` on the finished issue reports every check
passing: tested-before-ship, acceptance-before-code, traceability, evidence
over assertion, and the human-approval record.

The maintainer did not approve from the diff. He built a 1.x tree by hand
and ran the migrator on it, a dry run first and then the real apply. That
found a defect no test had checked: the migrator never changed the *shape*
value, so an issue triaged `express` stayed `express` and did not become
`quick-fix`. The fix landed as commit `6b36255`, and only then was the
sign-off recorded. Pull request #34 merged as `01df2f1`.

## The PyYAML trade

Compass never claimed to be stdlib-only in public. In at least half a dozen
places (`README.md`, `docs/quickstart.md`, `docs/five-minutes.md`,
`docs/install-smoke-test.md`, `docs/security.md`) it said that PyYAML was
the CLI's one hard dependency, and told you to `pip install pyyaml` before
your first assessment. "Stdlib-only" was a goal in the planning document.
The project set out to remove the dependency and chose to carry it, because:

- `yaml.safe_dump` appears at four sites, including the issue manifest, so
  Compass needed an emitter as well as a parser.
- A hand-built reader would have needed a parser, an emitter and a 135-file
  conformance proof, not the one-session fix first estimated.
- Without PyYAML, the pre-tool hook's acceptance-before-code check had been
  failing open, silently. Bundling aimed to close that.

The trade is published:

- `THIRD-PARTY-NOTICES.md` records the version, the upstream sha256 and a
  command that downloads the same sdist, hashes it and diffs it against the
  vendored copy. That command was run during review: the hash matched and
  the diff was empty.
- `docs/security.md` used to say: "The CLI itself is one file:
  `cli/compass`. … if something else shows up on your path after a Compass
  install, that is the bug." It now reads "nothing is installed onto your
  Python path," with the audit command named.

The cost stays:

- Compass decides which PyYAML version runs wherever it runs. It shadows an
  adopter's own PyYAML inside Compass's invocations (process-scoped only).
- An adopter gets a PyYAML security fix only when Compass ships a new copy,
  and nobody watches for that. This gap was filed
  (`vendored-dependency-ownership`) and abandoned, not solved.

## The gap the audit found in itself

A full-suite run of 957 tests was recorded as evidence and cited by three
gates. A later command destroyed it. `compass tdd-green --scenario TRC-G3`
re-recorded one scenario's evidence and overwrote the shared file those
gates cited, because that command writes the generic record before the
scenario copy. For a while three green gates cited an eleven-test run of one
file. `compass check` reported PASS throughout: it checks that a cited
record exists and is green, not that it is the run it claims to be.

A reviewer caught it by reading file sizes. Counting characters in the raw
pytest output and re-running the suite confirmed it: 957 characters, 951
dots, 6 skips, 0 failures. The automated check missed it and human review
caught it. It is filed as `tdd-green-unbound-record`: stamp an identity on
an evidence record when it is written, and check it when a gate cites it.

That cycle turned up eight framework and process gaps in total, each filed:

- a schema that rejected the evaluator's own re-assessment records;
- a traceability gap that let two changed test files go untracked through
  two review rounds;
- a missing owner for the vendored copy's currency;
- duplicated YAML logic across five shell scripts;
- a spec-deriver crash on a valid schema shape;
- two SHA-pinned tests that failed only on a shallow CI clone;
- a CI check that skipped, not failed, when a quoted archive passage could
  not be checked;
- the evidence-identity gap above.

As of the 2.1.0 release, four have landed: the deriver crash, the
shallow-clone tests, the evidence-identity gap and the archive-quote check.
The missing owner for the vendored copy was abandoned. The other three stay
queued.

## What a reader can check, and what this proves

**Checkable now:** the commit hashes, the pull request numbers,
`governance/terminology.yml`, `THIRD-PARTY-NOTICES.md`, ADR-013 (vendored
third-party code) and the test suite. Clone the repository and run it.

**Not checkable:** the devlog entries, the file-size catch, the character
counts, who filed what and when, the session-budget figure and the migrated
archive. They come from `.compass/work/` and `docs/proposals/`, which are
gitignored. That detail is the maintainer's own account.
`archive-quote-verification`, landed as of the 2.1.0 release, makes the CI
check fail, not skip, when a quoted archive passage cannot be checked. The
archive itself stays private.

**The suite:** 851 passing (857 total, six skipped) when the rewrite began,
and 951 passing (957 total, six skipped) when the install work closed.

**What this does not prove:** that Compass works for anyone else. Nobody
outside this repository has used it yet. There is no measured install time,
no seeded-user data and no second team's experience.
