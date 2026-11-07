# Compass in five minutes

This walkthrough takes one small change through the four stages of the path,
assess, specify, build and ship, to a commit that holds the code and its
record. Then it checks that record the way a reviewer does. Every block of
output below is real: it comes from one new project, run from start to end.

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
test. The test fails: the module spells the message `invlaid token`. Its
`compass.yml` names the owner, the project and its test command, and nothing
else.

## 1. Assess the work

Start with a real, contained change:

```text
/compass:go "Fix the misspelled invalid-token message"
```

`/compass:go` runs all four stages in one session. The steps below show the
commands it runs at each one.

Compass scores three dimensions:

| Dimension | What it asks |
|---|---|
| Risk | What happens if this goes wrong? |
| Familiarity | Is the affected code understood? |
| Size | How much delivery work is involved? |

Two optional switches change what the change owes: `goal: exploration`
makes the issue a spike, which explores and ships nothing, and `urgency:
live-defect` is the hotfix setting, which asks for a reproduction first.
Domain labels, such as `auth`, add evidence: a person approves the scenarios
and signs off before the change ships. Neither is scored.

The session records the assessment, the scenario, the test that proves it and
the request in one call:

```bash
compass quick-fix start fix-token-message \
  --risk "contained - one message string in one module" \
  --familiarity "brownfield-mapped - two functions with a test" \
  --size "atomic - one line" \
  --intent "An invalid token gets a correctly spelled message" \
  --scenario "Given a request has an invalid token When authentication rejects it Then the response says invalid token" \
  --test tests/test_auth.py::test_rejects_an_invalid_token \
  --request https://github.com/acme/token-api/issues/42 --requester "Dana Lee"
```

`--request` links what asked for the change and `--requester` names who
asked. Without them the check `request-recorded` fails, but nothing stops;
`compass next` names the command that records them.

The manifest records the judgment. Its first lines:

```yaml
schema_version: '3.0'
issue: fix-token-message
created: '2026-11-07'
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: atomic
```

Those three dimensions and the switches are the only judgment. Everything
after them, the evidence the change owes and the gates, is computed: the same
assessment and configuration produce the same evidence, every time. The
`delivery` approach is the path; the only other approach is the spike.
`compass approach evaluate --verbose` shows the computation:

```text
  policy          : this project's effective configuration (the check set, tightened by compass.yml)
  assessment      : {"risk": "contained", "familiarity": "brownfield-mapped", "size": "atomic"}
  evidence row    : RP-EVID-LIGHT
  FINAL APPROACH  : delivery
  evidence owed   : request, scenarios, red-before-green, suite-green, correctness, governance, traceability, outer-loop, ship-approval
  policy rules fired:
    A small change with low risk owes the evidence every change owes (RP-EVID-LIGHT, evidence)
        - evidence owed: request, scenarios, red-before-green, suite-green, correctness, governance, traceability, ship-approval
  gate set        : verify.correctness, verify.governance, verify.traceability
```

`compass approach show --issue fix-token-message` prints the same decision in
three lines: the approach and whether the session stops for you, the
evidence the change owes, and where the issue's files go.

```text
Approach: delivery (risk contained, familiarity brownfield-mapped, size atomic) - does not stop to wait for you
Evidence: request, scenarios, red-before-green, suite-green, correctness, governance, traceability, outer-loop, ship-approval
Writes: .compass/work/fix-token-message/ and docs/compass/2026-11-07-fix-token-message/
```

`outer-loop` is there because the four-layer acceptance strategy (`S17`)
applies to a change a real client can observe: the scenario's test runs
against the system from the outside, and its red and green are recorded as
outer-loop records.

Correct the assessment if it is wrong: the evidence is only as good as the
assessment. The session waits for your approval only at the checkpoints the
project's `autonomy` setting lists, which the first line of `compass approach
show` names.

## 2. Specify the scenario

The acceptance tests are the specification. `quick-fix start` wrote the one
scenario into `acceptance-criteria.md`, with a traceability id that the
evidence and the trail use from now on:

```text
### Scenario: Given a request has an invalid token When authentication rejects it Then the response says invalid token
<!-- traceability id: TRC-001 · serves: INT-1 -->

Given a request has an invalid token When authentication rejects it Then the response says invalid token
```

The scenario tells the engineer what to test, QA what to check, and the
reviewer what the change is meant to achieve. Larger work gets more
scenarios, added with `compass scenario add`, and each one names the test
that proves it.

## 3. Build with evidence

Every `compass` call that writes a record ends with a `next:` line, and
`compass next` prints it at any time. After the assessment it says:

```text
Build [gate: verify.correctness] | next: compass tdd-red --loop outer --scenario TRC-001 -- <acceptance test command>
```

Build is red, then green:

1. record the failing test with `compass tdd-red`;
2. make the smallest useful change; and
3. record the passing test with `compass tdd-green`.

Until a failing test is on record, the pre-tool hook refuses an edit to the
code. The red runs the test and keeps its output:

```text
compass tdd-red: failing test recorded (exit 1) (bound to TRC-001).
  evidence : .compass/work/fix-token-message/evidence/red-TRC-001.outer.json
  frozen : the scenarios, at this first red (sha256 f0836d6e1023)
  marker   : .compass/work/fix-token-message/.red
  the pre-tool hook will now allow code edits.
next: compass tdd-green --loop outer --scenario TRC-001 --candidate <build id>|local --client api|web|cli -- <acceptance test command>
```

The scenarios are now frozen: a later change to them shows in the trail.
After the one-line fix, the green runs the same test against the local build
(`--candidate local`) through its programming interface (`--client api`):

```text
compass tdd-green: passing suite recorded (exit 0) (bound to TRC-001).
  evidence : .compass/work/fix-token-message/evidence/green-TRC-001.outer.json
  registry : manifest.yml `evidence:` updated with the test-run entry
  marker : .red cleared - red -> green is on record.
next: compass quick-fix finish -m "<commit message>" --no-commit --candidate <build id>|local --client api|web|cli -- <test command>
```

Compass does not treat "the tests pass" in chat as evidence. `compass check`
reads the records on disk and runs the checks the change owes:

```text
PASS - 15 check(s) passed, 9 had nothing to check, 1 failed as advisory (does not block) on 'fix-to…
[mode: enforced]
  generation 1 (parent 9.0.0)
  Policy: compass-checks@9.0.0 (sha256 59a833c6efcf00adfc00ce6ae50803ab271da6ea103f7fd5c48fdd84da00…

ADVISORY acceptance-support-present: advisory (this check declares severity: advisory) - missing su…
```

The advisory says the project has not yet named the support code of the
four-layer strategy. It does not block. `compass check --verbose` prints
every check with its reason.

## 4. Ship

`compass quick-fix finish` runs the suite, runs `compass check` and passes the
gates in one call:

```text
compass quick-fix finish: 'fix-token-message' checked, not committed.
  gates : verify.correctness, verify.governance, verify.traceability -> pass
  evidence : EV-T-TRC-001-outer, EV-CHECK-1
  commit : when asked, stage the traced files, then run
  `compass ship-commit --issue fix-token-message -m "<message>" --release-note "<release line>"`
```

When you ask for a commit, stage the changed file and run `compass
ship-commit --issue fix-token-message` with a message and a release line.
It commits the files the issue recorded as changed, and nothing else. Unless
the project keeps the record out, the same commit holds the issue's record:
the manifest, the evidence, the acceptance criteria and `trail.md`.

```text
$ git show --stat --format=%s HEAD
Fix the misspelled invalid-token message

 .compass/.gitignore                                |   9 ++
 .compass/work/.gitignore                           |   9 ++
 .../work/fix-token-message/evidence/SHA256SUMS     |   4 +
 .../fix-token-message/evidence/check-output.txt    |  52 ++++++++++
 .../evidence/green-TRC-001.outer.json              |  39 ++++++++
 .../evidence/green-TRC-001.outer.log               |   2 +
 .../evidence/red-TRC-001.outer.json                |  33 +++++++
 .../evidence/red-TRC-001.outer.log                 |  17 ++++
 .compass/work/fix-token-message/manifest.yml       | 108 +++++++++++++++++++++
 .compass/work/fix-token-message/trail.md           |  72 ++++++++++++++
 app/auth.py                                        |   2 +-
 .../acceptance-criteria.md                         |  32 ++++++
 12 files changed, 378 insertions(+), 1 deletion(-)
```

Your normal CI is still responsible for tests, linting, security scanning,
builds and deployment checks.

### Where the ship approval comes from

`ship-approval` is one person's approval of the change. Compass does not let
the agent give it. After the merge, `compass issue link set --pr <n>` reads
it from the pull request: a review that approves it, by a person who is not
its author. With no such review, a person types `/compass:approve` after
`compass evidence request --ship`. No landing waits for it, and `compass
next` names both ways while it is owed:

```text
all phases complete | next: compass issue link set --pr <n> --issue fix-token-message after the merge, or compass evidence request --ship, then stop for /compass:approve
```

When the record ships with the code, the fields the merge adds come after
that commit: `compass record commit` commits them alone, and the `next:` line
names it.

## 5. Check the trail

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

Until the approval is read, section 5 says "Ship approval: not on record
yet" and names the two ways to give it.

`compass trail --check` writes nothing and exits 1 when the file is out of
date:

```text
compass trail: trail.md of fix-token-message is up to date.
```

Under each statement the trail names its files with their `sha256sum`
digests: the manifest, the acceptance criteria, the red and green records,
and the code and test as the green tested them. A reviewer checks them from
the repository root without Compass. `--quiet` prints only the files that do
not match, so no output and exit 0 means every file matches:

```text
$ grep -E '^[0-9a-f]{64}  ' .compass/work/fix-token-message/trail.md | sha256sum -c --quiet -
```

Change one of those files after the commit and the same command names it:

```text
$ grep -E '^[0-9a-f]{64}  ' .compass/work/fix-token-message/trail.md | sha256sum -c --quiet -
app/auth.py: FAILED
sha256sum: WARNING: 1 computed checksum did NOT match
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

1. **The acceptance tests are the specification.** Each scenario names the
   test that proves it, and the trail names both.
2. **Red before green, enforced by the hook.** The agent cannot edit the code
   until a failing test is on record.
3. **One path, adaptive evidence.** Every change runs assess, specify, build
   and ship. The assessment decides which evidence each stage judges.
4. **One person approves each change.** Compass reads the approval from the
   merged pull request, or a person types it; the agent cannot give it.
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
