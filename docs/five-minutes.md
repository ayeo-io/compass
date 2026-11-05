# Compass in five minutes

This walkthrough takes one small change from assessment to a reviewable,
checked result.

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
/compass:assess "Fix the misspelt invalid-token message"
```

Compass scores three dimensions:

| Dimension | What it asks |
|---|---|
| Risk | What happens if this goes wrong? |
| Familiarity | Is the affected code understood? |
| Size | How much delivery work is involved? |

Two optional switches, `goal` and `urgency`, can move the approach towards a
reference shape (spike or hotfix). Domain labels, such as `auth`, can raise the
floor: the lightest approach the policy allows. Neither is scored.

Judgment goes into the assessment. Everything after it is deterministic: the
same assessment and configuration produce the same
approach, every time.

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
them - the evidence the change owes and the gates - is computed. Run
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
compass approach show --issue <issue>
```

It prints the approach, the gates and where the issue's files go. `compass
check` shows each scenario's red, green and evidence, and `compass next` names
the next action. Compass writes no issue page: the manifest and the evidence
are the record.

To see every issue at once, with a lane for each stage, run
`compass board render`. It writes one page and opens it in the browser;
`compass board refresh` rewrites it after an issue moves to another stage. `docs/board.md`
describes the page.

Correct the assessment if it is wrong: a good delivery approach depends on
a good assessment. The session waits for your approval only at the
checkpoints the project's `autonomy` setting lists, which the first line of
`compass approach show` names. Regenerate the dashboard after a
stage changes the issue.

## 2. Define acceptance

Run:

```text
/compass:define
```

For this change, one Gherkin scenario is enough:

```gherkin
Scenario: The invalid-token message is spelled correctly
  Given a request contains an invalid token
  When authentication rejects the request
  Then the response says "invalid token"
```

The scenario is the shared specification. It tells the engineer what to test,
QA what to check, and reviewers what the change is meant to achieve.

## 3. Plan only what is useful

Run:

```text
/compass:plan
```

On a quick fix, planning can collapse to a short note naming the file and test
surface. Larger or riskier work can produce an intent document, high-level design,
low-level design, ADRs, delivery plan or test strategy.

Compass selects those documents because they help this issue. They are not a
fixed checklist.

## 4. Implement with evidence

Run:

```text
/compass:implement
```

Compass uses TDD by default where it adds value:

1. record a failing test with `compass tdd-red`;
2. make the smallest useful change; and
3. record the passing test with `compass tdd-green`.

The commands run the test and write evidence beneath the issue directory.
Compass does not treat “the tests pass” in chat as evidence.

## 5. Verify and ship

Run:

```text
/compass:verify
```

The verify stage checks the acceptance criteria, test evidence, traceability
and any approach-specific gates. Run `compass check` and resolve anything
still open.

Then run:

```text
/compass:ship
```

Compass checks the issue record again before completing the delivery workflow.
Your normal CI is still responsible for tests, linting, security scanning, builds and
deployment checks.

## What you should now have

A small issue typically leaves:

```text
.compass/work/<issue>/
├── manifest.yml
├── devlog.md
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
   the approach is computed from them.
2. **The approach decides the process weight.** Which stages run at what weight,
   which artifacts are needed, which gates apply.
3. **Guardrails are hard; strategies are defaults.** An approach can reduce
   process weight but never removes a guardrail.
4. **Evidence, not assertion.** A gate clears with a record a reader can open.
5. **If it is not on disk, it did not happen.** The manifest and its artifacts
   stay after the conversation ends.

## The CLI underneath

Everything above runs through slash commands, which call the CLI. The full
verb list is in the [CLI reference](cli.md); every verb describes
itself - `compass <verb> --help` says what it does and what the result
means.

## Next

- Read the [methodology](methodology.md) to understand adaptive routing.
- Read the [roles guide](roles-guide.md) if product, design, marketing or QA
  will contribute.
- Read the [safety contract](safety-contract.md) before relying on Compass
  gates.
- Run the [install smoke test](install-smoke-test.md) if commands or hooks do
  not behave as expected.
