# Compass turned its own delivery process on itself - here's what the record shows

Compass is an open-source framework that right-sizes software process: it
looks at a change, decides how much process weight it needs, and proves what
shipped with an audit trail instead of a promise. In August 2026 its
maintainer used it to rewrite Compass's own vocabulary, rename its own
commands, and migrate its own issue archive to a new schema - as
Compass issues, under Compass's own gates.

Nine slices, eleven pull requests, two sent back for more work, a
migration tool whose human sign-off came only after the maintainer,
running it himself, caught a defect the tests had missed, a dependency
trade-off taken in the open, and an audit process that found a gap in
its own audit trail. The commits, the PRs, and the test suite behind all
of it are public; the issue-by-issue record giving the finer detail
below is not - more on what that means at the end.

## The rename, and the ratchet that drove it

Compass 1.x had grown its own private vocabulary - "route" for what
everyone else calls a delivery approach, "frame" for triage, and so on.
The v2 rewrite replaced it with the industry's words, one word per
concept, frozen as `governance/terminology.yml` (commit `681766c`): 49
terms, 16 banned v1 spellings, and a test (`tests/test_terminology.py`)
that scans the repository's prose and fails on a banned term.

What made the rename honest rather than aspirational was a ratchet.
Nine surfaces - templates, commands, skills, docs, and more - started
listed as `pending_surfaces`, carrying v1 words only because nobody had
got to them yet, under one rule: shrink-only, never grow back. Of
the nine numbered slices, four actually struck a surface off it -
slices 3, 5, 6, and 7; the other five (the freeze, the session
instructions, the machine manifest, the migrator, and the release itself)
did work the ratchet doesn't see but the rewrite needed anyway. The
list reached zero at 7b, the last of the four slices that touched it, merged
as `b6017b0` in pull request #33.

The nine were the surfaces on the list, and the list was not the whole
repository. Cutting the 2.1.0 release turned up a tenth document that
had never been on it: the install smoke test, still telling a new user
to run a v1 command and expect v1 fields, a full major version after
the rename. The scanner had reported clean because it had never been
pointed at the file. It is on the list now, and the version guard that
should have caught the same document's stale output was searching for
the retired spelling, so it had been checking the wrong line all
along. Both were found by a person reading, not by the mechanism.

Eleven pull requests carried the nine slices to the tag - three were
split into two sessions each (3a/3b, 5a/5b, 7a/7b). Two were decided in
advance, on foresight; the third, 7a/7b, was decided mid-session, at a
green boundary reached partway through the work. Two of the eleven PRs
came back changes-requested, on record in this repository's own
devlogs and evidence files rather than a GitHub review thread. PR #31
rewrote thirteen skills and ten agent files; review found the scanner green while the
prose still read stiff - tautologies like "TDD is the TDD strategy" -
and it went back for a hand-polish pass. PR #32, the docs slice, came
back a second time because part of its read-aloud pass had been left
half-finished. Both are what "changes requested" should look like: a
scanner that can only catch banned words, and a human catching what it
can't.

The rewrite closed in fifteen of a sixteen-session budget, re-baselined
in the record at session twelve when the original twelve-session estimate
proved wrong, rather than quietly pushed through. It landed as
`7071672` on `main`, tagged `v2.0.0`, via pull request #35. The release
commit inside it, `5a4da2d`, calls the whole thing "the industry's
words, the same behaviour."

## The migrator: every check passed, and the sign-off took real work to earn

The last piece was `compass issue migrate` - the tool that rewrites someone
else's 1.x archive to the new schema. It edits a tree it doesn't own,
the riskiest thing in the cycle, and the `migrations` label floored its
delivery approach to a full human sign-off gate. `compass check` on the finished issue
reports every check passing: tested-before-ship, acceptance-before-code,
traceability, evidence over assertion, and the human-approval record,
together.

The sign-off is worth reading closely. The maintainer didn't approve
from the diff - he built a constructed 1.x tree by hand and ran the
migrator against it: dry run first, checked it wrote nothing and
reported accurately, then the real apply. It found a real defect: the
migrator renamed artifacts and rewrote schema keys but never touched
the *shape* value inside them, so an issue triaged `express` under the
old names stayed `express` instead of becoming `quick-fix` - no test
had checked that field on a real migrated manifest. The fix landed as
commit `6b36255`, and only then was the sign-off recorded. Pull request
#34 merged as `01df2f1`.

## The PyYAML trade, made in the open

Here's the part where the decision cost something. Compass never claimed to be
stdlib-only in public. What it actually said, in at least half a dozen
places (`README.md`, `docs/quickstart.md`, `docs/five-minutes.md`,
`docs/install-smoke-test.md`, `docs/security.md`), was that PyYAML was
the CLI's one hard dependency, and it told you to `pip install pyyaml`
before your first assessment. "Stdlib-only" was a goal in the planning
document, not a claim already made - it was literally the plan's own item
for removing the dependency. The project set out to remove the dependency
and chose instead to carry it, in the open, with a reason.

The reason: Compass's own YAML files needed a real emitter as well as a
parser. `yaml.safe_dump` appears at four sites, including the issue
manifest, so a hand-built "minimal subset" reader would have needed a real
parser, a real emitter, and a 135-file conformance proof - not the
one-session fix originally estimated. Bundling made that
unnecessary. This was one person's call, made solo, aimed at closing
the one quickstart step that could fail - and could fail silently:
without PyYAML, the
pre-tool hook's acceptance-before-code check had been failing open
instead of enforcing anything.

What keeps the trade from being a retreat nobody mentioned: it's published, not
just made. `THIRD-PARTY-NOTICES.md` records the version, the upstream
sha256, and a runnable command that downloads the same sdist, hashes
it, and diffs it against the vendored copy - checkable, not taken on
trust. That command was run for real during review: hash matched, diff
empty. `docs/security.md` used to say, verbatim: "The CLI itself is one
file: `cli/compass`. … if something else shows up on your path after a
Compass install, that is the bug." That went false the moment the
vendoring landed and was rewritten, not deleted: the guarantee now
reads "nothing is installed onto your Python path," still true, with
the audit command named directly.

It's still a cost, not a solved problem. Compass now decides which
PyYAML version runs everywhere it runs - an adopter's own pinned or
patched system PyYAML is shadowed inside Compass's invocations
(process-scoped only). And carrying someone else's code means carrying
their security fixes: an adopter gets a PyYAML fix only when Compass
ships a new copy, and nobody watches for that - a filed gap
(`vendored-dependency-ownership`), abandoned rather than solved.

## The gap the audit found in itself

While that install work was being checked, the review process caught
its own review process failing - stated here rather than smoothed
over. A full-suite run of 957 tests was recorded as evidence,
cited by three gates. A later command silently destroyed it:
re-recording one scenario's evidence through `compass tdd-green
--scenario TRC-G3` overwrote the shared file those gates pointed at,
because that command writes the generic record unconditionally before
the scenario copy. For a while three green gates cited an eleven-test
run of one file - `compass check` reported PASS throughout, because it
only checks that a cited record exists and is green, never whether it's
the run it claims to be.

A reviewer caught it by reading file sizes, confirmed by counting
characters in the raw pytest output and re-running the suite
independently: 957 characters, 951 dots, 6 skips, 0 failures, matching
exactly. That's "evidence, not assertion" - one of Compass's five hard
guardrails - failing on its own terms. The automated half missed it
entirely; the human review dimension the same guardrail prescribes is
what caught it. It's filed as `tdd-green-unbound-record`, promoted by the
maintainer to head the next cycle: stamp identity on an evidence record
when it's written, check that identity when a gate cites it, instead of
trusting a shared file path to mean what it says.

That same cycle of self-use turned up eight framework and process gaps
in total, filed rather than folded into whatever work found them: a
schema rejecting the evaluator's own re-assessment records, a
traceability gap that let two changed test files go untracked through
two review rounds, a missing owner for the vendored copy's currency,
duplicated YAML logic across five shell scripts, a spec-deriver crash on
a valid schema shape nobody had exercised, two SHA-pinned tests failing
only on a shallow CI clone, and a CI check that skips instead of
failing when a quoted archive passage can't be checked. As of the
2.1.0 release, four have landed: the deriver crash, the shallow-clone
tests, the evidence-identity gap above, and the archive-quote check -
the one filed with its own due date, before a public document cites
an archive quote. This one does. The missing owner for the
vendored copy's currency was abandoned rather than fixed. The other
three stay queued.

## What this proves, what's checkable, and what does not

Some of this is independently checkable right now: the commit hashes,
the PR numbers, `governance/terminology.yml`, `THIRD-PARTY-NOTICES.md`,
ADR-013 (vendored third-party code), and the test suite - clone the
repository and run it. The rest
- devlog entries, the file-size catch, character counts, who filed what
and when, and the planning documents this piece draws on for things
like the session-budget figure - comes from `.compass/work/` and
`docs/proposals/`, both kept out of this repository's public history by
its own `.gitignore`. That's a real gap, not a reluctant disclosure.
`archive-quote-verification`, landed as of the 2.1.0 release, closes a
narrower one: it makes the CI check fail rather than silently skip
when a quoted archive passage cannot be checked. The narrative
detail here remains the maintainer's own account. A reader cannot
check this yet, although the opening suggests they can.

What's true regardless: a real framework rewrote its own vocabulary,
renamed its own commands, and migrated its own archive under its own
guardrails. The vocabulary and the commands are on the public record
above; the migrated archive itself is not - it lives in the same
gitignored `.compass/work/` named above. The suite that stood at 851
passing (857 total, six skipped) when this rewrite began had grown to
951 passing (957 total, six skipped) by the time the install work
closed out.

What's not true, and won't be claimed here: that this proves Compass
works for anyone else. Nobody outside this repository has used it yet.
There is no measured install time, no seeded-user data, no second
team's experience to point to - only one project, its maintainer, and a
framework tested, so far, against exactly one thing: itself. That's a
real result and a narrow one, and the honesty about which is which is
the only thing worth asking a reader to trust.

So the useful thing now is people running it on something real and
saying where it gets in their way - that is the one result this repository
cannot produce on its own, and it is worth more than another clean
internal run. The gap named above is filed too: as of the 2.1.0
release, the check now fails rather than silently skips when a quoted
archive passage cannot be checked, and the archive itself still
stays private.
