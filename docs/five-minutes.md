# Compass in five minutes

This walkthrough takes one small change through the four stages of the path,
assess, specify, build and ship, to a reviewable, checked result.

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

Open a project you are happy to change. Compass will add a `.compass/`
directory for the issue's manifest and evidence, and a `docs/compass/`
directory for the issue's documents.

## 1. Assess the work

Start with a real, contained change:

```text
/compass:go "Fix the misspelt invalid-token message"
```

`/compass:go` runs all four stages in one session. The steps below show what
it does at each one.

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

Judgment goes into the assessment. Everything after it is deterministic: the
same assessment and configuration produce the same
evidence, every time.

For a contained typo, Compass asks for the evidence every change owes and no
more. It writes the manifest to `.compass/work/<issue>/` and the issue's
documents to `docs/compass/<date>-<issue>/`, and the manifest records the
judgment it was computed from. The part of `manifest.yml` that matters here:

```yaml
schema_version: "3.0"
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: atomic
  goal: delivery
```

Those three dimensions and the switches are the only judgment in the routing. Everything after
them - the evidence the change owes and the gates - is computed. The
`delivery` approach is the path; the only other approach is the spike. Run
`compass approach evaluate --verbose` against that assessment and it prints:

```text
  policy          : this project's effective configuration (compass.yml over the shipped default)
  assessment      : {"risk": "contained", "familiarity": "brownfield-mapped", "size": "atomic", "goal": "delivery"}
  evidence row    : RP-EVID-LIGHT
  FINAL APPROACH  : delivery
  evidence owed   : scenarios, red-before-green, suite-green, correctness, governance, traceability
  policy rules fired:
    A small change with low risk owes the evidence every change owes (RP-EVID-LIGHT, evidence)
        - evidence owed: scenarios, red-before-green, suite-green, correctness, governance, traceability
  gate set        : verify.correctness, verify.governance, verify.traceability
```

The first line shows what the project runs against. The text above is the line
for a project with a `compass.yml`. A project without one has not changed the
shipped default, and the line names the shipped `routing-policy.yml` and its
version instead. Run against an issue that already has a stored generation, the
line reads `generation N of this issue (parent ...)`.

See the decision:

```bash
compass approach show --issue fix-token-message
```

It prints three lines: the approach and whether the session stops for you,
the evidence the change owes, and where the issue's files go.

```text
Approach: delivery (risk contained, familiarity brownfield-mapped, size atomic) - does not stop to wait for you
Evidence: scenarios, red-before-green, suite-green, correctness, governance, traceability, outer-loop
Writes: .compass/work/fix-token-message/ and docs/compass/2026-11-06-fix-token-message/
```

`outer-loop` is there because the four-layer acceptance strategy (`S17`)
applies to a change a real client can observe: the scenario's test runs
against the system from the outside. This project has no `compass.yml`, so
it runs on the live default, which ships the strategy. The `approach
evaluate` transcript above came from a project whose `compass.yml` extends
`compass:default@6`, a major from before the strategy shipped, so it owes no
`outer-loop`. In one project the preview and the write owe the same
evidence.

To see every issue at once, with a lane for each stage, run
`compass board render`. It writes one page and opens it in the browser;
`compass board refresh` rewrites it after an issue moves to another stage. `docs/board.md`
describes the page.

Correct the assessment if it is wrong: the evidence is only as good as the
assessment. The session waits for your approval only at the checkpoints the
project's `autonomy` setting lists, which the first line of `compass approach
show` names.

## 2. Specify the scenario

For this change, one Gherkin scenario is enough. `/compass:go` writes it into
`acceptance-criteria.md` when it records the assessment:

```gherkin
Scenario: TRC-001
  Given a request has an invalid token
  When authentication rejects it
  Then the response says invalid token
```

The scenario is the shared specification. It tells the engineer what to test,
QA what to check, and reviewers what the change is meant to achieve. Larger
work gets more scenarios, added with `compass scenario add`, and each one
names the test that proves it.

## 3. Build with evidence

Every `compass` call that writes a record ends with a `next:` line, and
`compass next` prints it at any time. After the assessment it says:

```text
next: compass tdd-red --loop outer --scenario TRC-001 -- <acceptance test command>
```

Compass uses TDD on every change on the path:

1. record a failing test with `compass tdd-red`;
2. make the smallest useful change; and
3. record the passing test with `compass tdd-green`.

The commands run the test and write evidence beneath the issue directory.
Compass does not treat "the tests pass" in chat as evidence. Until a failing
test is on record, the pre-tool hook refuses an edit to the code.

## 4. Ship

`/compass:ship` reviews the change and passes each gate with recorded
evidence. For a small change, `compass quick-fix finish` does this in one
call: it runs the suite, runs `compass check` and passes the gates.

```text
compass quick-fix finish: 'fix-token-message' checked, not committed.
  gates : verify.correctness, verify.governance, verify.traceability -> pass
  evidence : EV-T-TRC-001-outer, EV-CHECK-1
```

When you ask for a commit, `compass ship-commit` commits the files the issue
recorded as changed, and nothing else. Your normal CI is still responsible for tests, linting,
security scanning, builds and deployment checks.

## What you should now have

A small issue typically leaves:

```text
.compass/work/<issue>/
├── manifest.yml
├── generations/
└── evidence/

docs/compass/<date>-<issue>/
└── acceptance-criteria.md
```

`.compass/work/<issue>/` holds the machine state; `docs/compass/<date>-<issue>/`
holds the acceptance criteria, the one document Compass needs and checks
(ADR-091). A team can keep its own notes beside it. Another person, session or compatible
runtime can resume from these files without the original chat.

## The mental model in five points

1. **Assess the work, do not choose a process.** Three dimensions are judgment;
   the evidence is computed from them.
2. **One path, adaptive evidence.** Every change runs assess, specify, build
   and ship. The assessment decides which evidence each stage judges.
3. **Guardrails are hard; strategies are defaults.** A small change owes less
   evidence but never loses a guardrail.
4. **Evidence, not assertion.** A gate clears with a record a reader can open.
5. **If it is not on disk, it did not happen.** The manifest and its artifacts
   stay after the conversation ends.

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
