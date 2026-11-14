# Compass in five minutes

This page takes one small change from the request to a commit that holds the
code and its record, then checks the record as a reviewer does. Each block
of output is real: it comes from one new project, run from start to end.

## Before you start

You need Claude Code and Python 3.10 or later. Install Compass from a shell:

```bash
claude plugin install compass --marketplace ayeo-io/compass
```

Or inside Claude Code:

```text
/plugin marketplace add ayeo-io/compass
/plugin install compass@compass
```

The example project is a git repository with one module and its test. The
module spells a message `invlaid token`, and no test reads the message. Its
`compass.yml` names the owner, the project and its test command.

## 1. Start the issue

```text
/compass:go "Fix the misspelled invalid-token message"
```

`/compass:go` runs the whole change in one session. It opens the issue in
one call:

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

`--intent` says what will be true afterwards. `--request` links the request
and `--requester` names who asked. Each call that writes a record ends with
a `next:` line; `compass next` prints it at any time.

The manifest records the assessment:

```yaml
schema_version: '3.0'
issue: fix-token-message
created: '2026-11-10'
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: small
```

| Dimension | What it asks | Option |
|---|---|---|
| Risk | What happens if this goes wrong? | `--risk` |
| Familiarity | Is the affected code understood? | `--familiarity` |
| Size | How much delivery work is involved? | `--size` |

The values above are the ones `start` records when an option is left out.

Every delivery issue owes the same evidence, whatever its size. Two things
add an approval by a person:

- A domain label: `auth`, `payments`, `personal-data`, `migrations`, or a
  label the project adds. A person approves the scenarios before any code
  edit, and signs the change off before it lands.
- `critical` risk. A person approves the scenarios before any code edit.

`goal: exploration` makes the issue a spike, which explores and ships
nothing.

The same assessment and configuration give the same evidence each time.
`compass approach evaluate --verbose` shows the computation:

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

`compass approach show --issue fix-token-message` prints it in three lines:

```text
Approach: delivery (risk contained, familiarity brownfield-mapped, size small) - does not stop to wait for you
Evidence: request, scenarios, red-before-green, suite-green, correctness, governance, traceability, ship-approval
Writes: .compass/work/fix-token-message/ and docs/compass/2026-11-10-fix-token-message/
```

`start` wrote the scenario into `acceptance-criteria.md`, with the
traceability id that the evidence and the trail use:

```text
### Scenario: An invalid token gets a correctly spelled message
<!-- traceability id: TRC-001 · serves: INT-1 -->

An invalid token gets a correctly spelled message
```

For larger work, the session adds each scenario to this file in the same
form, with the next `TRC-` id.

## 2. Write the test and the code

The session writes a test that reads the message, corrects the spelling and
runs the tests. It needs no `compass` command here:

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

1. reads the scenarios from `acceptance-criteria.md` and the changed files
   from git;
2. runs the test command on a temporary copy of the commit the issue started
   from, with the changed test file laid over it. It must fail: the red;
3. runs the test command on the working tree. It must pass: the green;
4. runs `compass check` and passes the three gates;
5. writes the request for your approval, and stops.

The red record, `evidence/red-TRC-001.json`, says where the red was proved:

```text
  "exit_code": 1,
  "passed": false,
  "red_kind": "failure",
  "proved_on": "base-copy",
  "base_commit": "956a3fbc422b6a72d2dcd3df5b69a42342173315",
```

`proved_on: base-copy` means the tests fail without the change. It does not
show that the test was written before the code (`docs/base-copy.md`).

`compass check` reads the records on disk, not the chat:

```text
PASS - 12 check(s) passed, 13 had nothing to check on 'fix-token-message' (delivery)
[mode: enforced]
  generation 1 (parent 9.0.0)
  Policy: compass-checks@9.0.0 (sha256 446c1cf864df46a525c0e12050681aee9a8799be4db2f4074835d01060b4…
```

`compass check --verbose` prints every check with its reason.

## 4. Approve, then commit

A person gives the ship approval. The agent cannot give it
([safety contract](safety-contract.md)). You read the change and type:

```text
/compass:approve 1
```

The session runs the same `finish` again, and it commits:

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
the issue. You open the pull request and merge it as for any change. Unless
the project keeps the record out, the same commit holds the issue's record:

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

Your CI still does the tests, linting, security scanning, builds and
deployment checks.

In this run the person approved at a terminal, with `compass evidence
approve`. The ship approval can also come from the pull request: after the
merge, `compass issue link set --pr <n>` reads a review that approves it, by
a person who is not its author.

## 5. Change it after the approval

An approval covers the change you saw: the request and the approval record
hold a digest of its code and test files. After feedback, the session edits
the code and the test and runs `finish` once:

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

The change now differs from the one you approved, so `compass check` fails
until you approve the new state:

```text
FAIL - 1 of 12 check(s) failed, 13 had nothing to check on 'fix-token-message' (delivery)
[mode: enforced]
  generation 1 (parent 9.0.0)
  Policy: compass-checks@9.0.0 (sha256 446c1cf864df46a525c0e12050681aee9a8799be4db2f4074835d01060b4…

FAIL ship-approval-present: EV-SHIP-APPROVAL-1 was given for an earlier state of the change (sha256…
     fix: Run `compass issue link set --pr <n>` once merged, or `compass evidence request --ship`.
```

After `/compass:approve 2`, `compass check` passes again. The first approval
stays on record. The next commit that holds the record carries the new one.

## 6. Check the trail

`trail.md` has six sections:

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

The trail names each file it rests on with a `sha256sum` digest: the
manifest, the acceptance criteria, the red and green records, and the code
and test as the green tested them. A reviewer checks them from the
repository root without Compass, at the commit that holds that version of
the trail. With `--quiet`, no output and exit 0 mean every file matches:

```text
$ grep -E '^[0-9a-f]{64}  ' .compass/work/fix-token-message/trail.md | sha256sum -c --quiet -
```

Change one of those files after the commit and the same command names it:

```text
$ grep -E '^[0-9a-f]{64}  ' .compass/work/fix-token-message/trail.md | sha256sum -c --quiet -
sha256sum: WARNING: 1 computed checksum did NOT match
app/auth.py: FAILED
```

The check proves that the files match their digests. It does not prove that
the trail's prose is true.

## What you should now have

```text
.compass/work/<issue>/
├── manifest.yml
├── trail.md
├── generations/     not committed; a fresh clone rebuilds it from the manifest
└── evidence/

docs/compass/<date>-<issue>/
└── acceptance-criteria.md
```

`.compass/work/<issue>/` holds the machine state.
`docs/compass/<date>-<issue>/` holds the acceptance criteria, the one
document Compass needs and checks (ADR-091). Another person or session can
resume from these files without the chat.

## The mental model in five points

1. **Two commands.** `start` opens the issue and `finish` writes the record.
2. **The tests fail without the change.** `finish` runs them on a copy of
   the base commit, where they must fail, and on the working tree, where
   they must pass. This does not show the order of the work.
3. **One path, the same evidence.** A domain label or `critical` risk adds a
   person's approval of the scenarios before any code edit.
4. **One person approves each change, as they saw it.** When the change
   differs from the one approved, Compass asks again.
5. **If it is not on disk, it did not happen.** The record ships with the
   code, and a reviewer checks it with `sha256sum`.

## Next

- [CLI reference](cli.md) - every verb; `compass <verb> --help` explains one.
- [Methodology](methodology.md) - the path, and how assess selects the evidence.
- [Safety contract](safety-contract.md) - read it before you rely on a gate.
- [Install smoke test](install-smoke-test.md) - when a command or a hook fails.
