# Compass in five minutes

This walkthrough takes one small change from the request to a commit that
holds the code and its record. The session runs two `compass` commands:
`compass quick-fix start` opens the issue, and `compass quick-fix finish`
writes the record. Then the walkthrough checks that record the way a
reviewer does. Every block of output below is real: it comes from one new
project, run from start to end.

## Before you start

You need Claude Code and Python 3.10 or later. Compass CI tests Python 3.11.

Install Compass from a shell, in one line:

```bash
claude plugin install compass --marketplace ayeo-io/compass
```

Or type two commands inside Claude Code:

```text
/plugin marketplace add ayeo-io/compass
/plugin install compass@compass
```

Open a project you are happy to change. Compass adds a `.compass/` directory
for the issue's manifest and evidence, and a `docs/compass/` directory for the
issue's documents.

The project in this example is a git repository with one module and its
test. The module spells a message `invlaid token`, and no test reads the
message. Its `compass.yml` names the owner, the project and its test
command, and nothing else.

## 1. Start the issue

Start with a real, contained change:

```text
/compass:go "Fix the misspelled invalid-token message"
```

`/compass:go` runs the whole change in one session. The steps below show the
commands it runs.

The session opens the issue in one call:

```bash
compass quick-fix start fix-token-message \
  --intent "An invalid token gets a correctly spelled message" \
  --request https://github.com/acme/token-api/issues/42 --requester "Dana Lee"
```

```text
compass quick-fix start: 'fix-token-message' started.
  created: .compass/ - tell the user
next: write the tests and the code, then compass quick-fix finish -m "<commit message>" -- <test command>
```

`--intent` says what will be true afterwards. `--request` links what asked
for the change and `--requester` names who asked. Every `compass` call that
writes a record ends with a `next:` line, and `compass next` prints it at
any time.

The manifest records the assessment. Its first lines:

```yaml
schema_version: '3.0'
issue: fix-token-message
created: '2026-11-10'
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: small
```

Compass scores three dimensions:

| Dimension | What it asks |
|---|---|
| Risk | What happens if this goes wrong? |
| Familiarity | Is the affected code understood? |
| Size | How much delivery work is involved? |

`start` takes each as an option (`--risk`, `--familiarity`, `--size`). The
values above are the ones it records when an option is left out. Every
delivery issue owes the same evidence, whatever its size. Two things add an
approval by a person:

- a domain label: `auth`, `payments`, `personal-data`, `migrations`, or a
  label the project adds. A person approves the scenarios before any code
  edit, and signs the change off before it lands;
- `critical` risk. A person approves the scenarios before any code edit.

`goal: exploration` makes the issue a spike, which explores and ships
nothing.

The evidence the change owes and the gates are computed: the same assessment
and configuration produce the same evidence, every time. The `delivery`
approach is the path; the only other approach is the spike.
`compass approach evaluate --verbose` shows the computation for an
assessment:

```text
  policy          : this project's effective configuration (the check set, tightened by compass.yml)
  assessment      : {"risk": "contained", "familiarity": "brownfield-mapped", "size": "small"}
  evidence row    : RP-EVID-COMMON
  FINAL APPROACH  : delivery
  evidence owed   : request, scenarios, red-before-green, suite-green, correctness, governance, traceability, ship-approval
  policy rules fired:
    Every change owes the same evidence: the request, the scenarios, the red before the green, a green suite and the ship approval (RP-EVID-COMMON, evidence)
        - evidence owed: request, scenarios, red-before-green, suite-green, correctness, governance, traceability, ship-approval
  gate set        : verify.correctness, verify.governance, verify.traceability
```

`compass approach show --issue fix-token-message` prints the same decision in
three lines: the approach and whether the session stops for you, the
evidence the change owes, and where the issue's files go.

```text
Approach: delivery (risk contained, familiarity brownfield-mapped, size small) - does not stop to wait for you
Evidence: request, scenarios, red-before-green, suite-green, correctness, governance, traceability, ship-approval
Writes: .compass/work/fix-token-message/ and docs/compass/2026-11-10-fix-token-message/
```

`start` wrote the one scenario into `acceptance-criteria.md`, with a
traceability id that the evidence and the trail use from now on:

```text
### Scenario: An invalid token gets a correctly spelled message
<!-- traceability id: TRC-001 · serves: INT-1 -->

An invalid token gets a correctly spelled message
```

The scenario tells the engineer what to test, QA what to check, and the
reviewer what the change is meant to achieve. Larger work gets more
scenarios: the session writes each one in this file in the same form, with
the next `TRC-` id, and `finish` reads them.

## 2. Write the test and the code

The session writes a test that reads the message, corrects the spelling and
runs the tests directly. No `compass` command is needed here:

```text
$ python3 -m pytest -q
..                                                                       [100%]
2 passed in 0.09s
```

## 3. Finish

One command writes the whole record:

```bash
compass quick-fix finish -m "Fix the misspelled invalid-token message (#42)" -- python3 -m pytest -q
```

```text
compass quick-fix finish: 'fix-token-message' checked. Nothing is committed.
  red      : the tests fail on the base commit 956a3fbc (exit 1), with 1 test file(s) of the change
  green    : the tests pass on the working tree
  scenarios: TRC-001
  files    : 3 traced from git
next: stop and ask the person to type /compass:approve 1 (the ship approval). Nothing else to run until then. After the approval, run the same finish again: it commits.
```

In that one call `finish`:

1. reads the scenarios from `acceptance-criteria.md`;
2. reads the changed files from git;
3. copies the commit the issue started from to a temporary directory, lays
   the changed test file over it and runs the test command there. The
   command must fail. This is the red;
4. runs the test command on the working tree. It must pass. This is the
   green;
5. runs `compass check` and passes the three gates;
6. writes the request for your approval, and stops.

The red record says where the red was proved. These lines are from
`evidence/red-TRC-001.json`:

```text
  "exit_code": 1,
  "passed": false,
  "red_kind": "failure",
  "proved_on": "base-copy",
  "base_commit": "956a3fbc422b6a72d2dcd3df5b69a42342173315",
```

`proved_on: base-copy` means the tests fail without the change. It does not
show that the test was written before the code.
`docs/base-copy.md` says what the copy holds and where it has limits.

Compass does not treat "the tests pass" in chat as evidence. `compass check`
reads the records on disk and runs the checks the change owes:

```text
PASS - 12 check(s) passed, 13 had nothing to check on 'fix-token-message' (delivery)
[mode: enforced]
  generation 1 (parent 9.0.0)
  Policy: compass-checks@9.0.0 (sha256 446c1cf864df46a525c0e12050681aee9a8799be4db2f4074835d01060b4…
```

`compass check --verbose` prints every check with its reason.

## 4. Approve, then commit

The ship approval is one person's approval of the change. Compass does not
let the agent give it. You read the change and type:

```text
/compass:approve 1
```

The session then runs the same `finish` again, and it commits:

```text
compass quick-fix finish: 'fix-token-message' checked and committed.
  records  : the red and the green already cover these files
  scenarios: TRC-001
  commit   : 789b981 "Fix the misspelled invalid-token message (#42)" by Dana Lee, on branch fix-token-message (new)
  committed: 13 file(s): 2 of the change, 11 of the record (.compass/ and docs/compass/, as intended)
  tree     : working tree clean
done: nothing more to run for this issue, before or after the merge. Do not re-check the commit or push it unless the person asks.
```

The session was on the default branch, so `finish` made a branch named after
the issue and committed there. A commit on a branch is not a merge: you open
the pull request and merge it as you do for any change. Unless the project
keeps the record out, the same commit holds the issue's record: the
manifest, the evidence, the acceptance criteria and `trail.md`.

```text
$ git show --stat --format=%s HEAD
Fix the misspelled invalid-token message (#42)

 .compass/.gitignore                                |   9 ++
 .compass/work/.gitignore                           |   9 ++
 .../work/fix-token-message/evidence/SHA256SUMS     |   4 +
 .../fix-token-message/evidence/check-output.txt    |  52 +++++++++
 .../fix-token-message/evidence/green-TRC-001.json  |  34 ++++++
 .../fix-token-message/evidence/green-TRC-001.log   |   2 +
 .../fix-token-message/evidence/red-TRC-001.json    |  29 +++++
 .../fix-token-message/evidence/red-TRC-001.log     |  17 +++
 .compass/work/fix-token-message/manifest.yml       | 126 +++++++++++++++++++++
 .compass/work/fix-token-message/trail.md           |  72 ++++++++++++
 app/auth.py                                        |   2 +-
 .../acceptance-criteria.md                         |  32 ++++++
 tests/test_auth.py                                 |   4 +
 13 files changed, 391 insertions(+), 1 deletion(-)
```

Your normal CI is still responsible for tests, linting, security scanning,
builds and deployment checks.

In this run the person gave the approval at a terminal, with `compass
evidence approve`. The ship
approval can also come from the pull request: after the merge, `compass
issue link set --pr <n>` reads a review that approves it, by a person who is
not its author.

## 5. Change it after the approval

An approval covers the change you saw. `finish` records a digest of the code
and test files of the change, and the request and the approval record hold
it. After feedback, the session edits the code and the test and runs
`finish` once:

```text
compass quick-fix finish: 'fix-token-message' checked and committed.
  red      : the tests fail on the base commit 956a3fbc (exit 1), with 1 test file(s) of the change
  green    : the tests pass on the working tree
  scenarios: TRC-001
  commit   : 38b13f0 "Add a hint to the invalid-token response (#42)" by Dana Lee, on branch fix-token-message
  committed: 11 file(s): 2 of the change, 9 of the record (.compass/ and docs/compass/, as intended)
  tree     : working tree clean
next: stop: the change differs from the one approved. Ask the person to type /compass:approve 2 (the ship approval). Nothing else to run now.
```

It proved the red and the green again and committed on the branch. The
change now differs from the one you approved, so `compass check` fails until
you approve the new state:

```text
FAIL - 1 of 12 check(s) failed, 13 had nothing to check on 'fix-token-message' (delivery)
[mode: enforced]
  generation 1 (parent 9.0.0)
  Policy: compass-checks@9.0.0 (sha256 446c1cf864df46a525c0e12050681aee9a8799be4db2f4074835d01060b4…

FAIL ship-approval-present: EV-SHIP-APPROVAL-1 was given for an earlier state of the change (sha256…
     fix: Run `compass issue link set --pr <n>` once merged, or `compass evidence request --ship`.
```

After `/compass:approve 2`, `compass check` passes again. The first approval
stays on record. The new approval is written to the manifest in the working
tree, so the next commit that holds the record carries it.

## 6. Check the trail

`trail.md` says, in order, who asked, what was agreed, the red, the green,
who approved and what shipped:

```text
## 1. Who asked
## 2. What was agreed
## 3. Red, for each scenario
## 4. Green
## 5. Who approved, and by what authority
## 6. What shipped
```

`compass trail --check` writes nothing and exits 1 when the file is out of
date. At the first commit above it says:

```text
compass trail: trail.md of fix-token-message is up to date.
```

Under each statement the trail names its files with their `sha256sum`
digests: the manifest, the acceptance criteria, the red and green records,
and the code and test as the green tested them. A reviewer checks them from
the repository root without Compass, at the commit that holds that version
of the trail. `--quiet` prints only the files that do not match, so no
output and exit 0 means every file matches:

```text
$ grep -E '^[0-9a-f]{64}  ' .compass/work/fix-token-message/trail.md | sha256sum -c --quiet -
```

Change one of those files after the commit and the same command names it:

```text
$ grep -E '^[0-9a-f]{64}  ' .compass/work/fix-token-message/trail.md | sha256sum -c --quiet -
sha256sum: WARNING: 1 computed checksum did NOT match
app/auth.py: FAILED
```

Leave out `--quiet` to see an `OK` line for each file. The check proves that
the files match their digests. It does not prove that the trail's prose is
true.

## What you should now have

A small issue typically leaves:

```text
.compass/work/<issue>/
├── manifest.yml
├── trail.md
├── generations/     not committed; a fresh clone rebuilds it from the manifest
└── evidence/

docs/compass/<date>-<issue>/
└── acceptance-criteria.md
```

`.compass/work/<issue>/` holds the machine state; `docs/compass/<date>-<issue>/`
holds the acceptance criteria, the one document Compass needs and checks
(ADR-091). A team can keep its own notes beside it. Another person or session
can resume from these files without the original chat.

## The mental model in five points

1. **Two commands.** `start` opens the issue and `finish` writes the record.
   Between them the session writes tests and code and runs the tests
   directly.
2. **The tests fail without the change.** `finish` runs them on a copy of
   the commit the issue started from, where they must fail, and on the
   working tree, where they must pass. This does not show the order of the
   work.
3. **One path, the same evidence.** Every delivery issue owes the same
   evidence. A domain label or `critical` risk adds a person's approval of
   the scenarios before any code edit.
4. **One person approves each change, as they saw it.** The agent cannot
   give the approval. When the change differs from the one approved,
   Compass asks again.
5. **If it is not on disk, it did not happen.** The record ships with the
   code, and a reviewer checks it with `sha256sum`.

## The CLI underneath

Everything above runs through slash commands, which call the CLI. The full
verb list is in the [CLI reference](cli.md); every verb describes
itself - `compass <verb> --help` says what it does and what the result
means.

## Next

- Read the [methodology](methodology.md) to understand the path and how
  assess selects the evidence.
- Read the [safety contract](safety-contract.md) before relying on Compass
  gates.
- Run the [install smoke test](install-smoke-test.md) if commands or hooks do
  not behave as expected.
