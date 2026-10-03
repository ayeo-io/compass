# Compass in five minutes

This walkthrough takes one small change from assessment to a reviewable,
checked result.

## Before you start

You need Claude Code and Python 3.10 or later. Compass CI tests Python 3.11.

Install Compass inside Claude Code:

```text
/plugin marketplace add jed72/compass
/plugin install compass@compass
```

Open a project you are happy to change. Compass will add a `.compass/`
directory containing the issue record and review artifacts.

## 1. Assess the work

Start with a real, contained change:

```text
/compass:assess "Fix the misspelt invalid-token message"
```

Compass assesses four dimensions:

| Dimension | What it asks |
|---|---|
| Risk | What happens if this goes wrong? |
| Familiarity | Is the affected code understood? |
| Size | How much delivery work is involved? |
| Goal and role | What outcome is wanted, and who is asking? |

Judgement goes into the assessment. Everything after it is deterministic: the
same assessment plus the same policy produces the same approach, every time.

For a contained typo, Compass will normally choose a quick-fix-shaped approach.
It writes the result under `.compass/work/<issue>/`, and the manifest records the
judgement it was computed from. The part of `manifest.yml` that matters here:

```yaml
schema_version: "2.0"
status: active
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: atomic
  goal: delivery
  role: engineer
```

Those four dimensions are the only judgement in the routing. Everything after
them - the stages, the gates, the orchestration - is computed. Run
`compass approach evaluate --verbose` against that assessment and it prints:

```text
  policy          : <your project>/governance/routing-policy.yml (v<the version that file declares>)
  assessment      : {"risk": "contained", "familiarity": "brownfield-mapped", "size": "atomic", "goal": "delivery", "role": "engineer"}
  candidate shape : quick fix  <- RP-SHAPE-003 (Small on every axis.)
  FINAL APPROACH  : quick fix
  policy rules fired: none
  parallel subtasks: up to 1 (a ceiling - breakdown sets the orchestration once the distribution map exists)
  per-stage weight:
    assess     : full
    define     : light
    refine     : collapsed
    plan       : collapsed
    breakdown  : skipped
    implement  : full
    verify     : light
    ship       : light
  gate set        : verify.correctness, verify.governance, verify.traceability
```

Generate the issue dashboard:

```bash
compass issue dashboard --issue <issue>
```

Then open `.compass/work/<issue>/README.md`. It tells you:

- the proposed approach;
- what needs human approval;
- which artifacts will be produced;
- what Compass deliberately omitted, and why;
- each scenario's red, green and evidence, with a diagram from intent to
  scenario to test to evidence that renders in a Markdown preview; and
- the next action.

Approve or correct the assessment before continuing. A good delivery
approach depends on a good assessment. Regenerate the dashboard after a
stage changes the issue.

## 2. Define acceptance

Run:

```text
/compass:define
```

For this change, one Gherkin scenario is enough:

```gherkin
Scenario: The invalid-token message is spelt correctly
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
and any approach-specific gates. Read `verification-report.md` and resolve
anything still open.

Then run:

```text
/compass:ship
```

Compass checks the issue record again before completing the delivery workflow.
Your normal CI still owns tests, linting, security scanning, builds and
deployment checks.

## What you should now have

A small issue typically leaves:

```text
.compass/work/<issue>/
├── README.md
├── manifest.yml
├── delivery-approach.md
├── acceptance-criteria.md
├── verification-report.md
├── devlog.md
└── evidence/
```

The exact pack varies with the work. Another person, session or compatible
runtime can resume from these files without the original chat.

## The mental model in five points

1. **Assess the work, do not choose a process.** Four dimensions are judgement;
   the approach is computed from them.
2. **The approach decides the process weight.** Which stages run at what weight,
   which artifacts are earned, which gates apply.
3. **Guardrails are hard; strategies are defaults.** An approach can reduce
   process weight but never removes a guardrail.
4. **Evidence, not assertion.** A gate clears with a record a reader can open.
5. **If it is not on disk, it did not happen.** The manifest and its artifacts
   outlive the conversation.

## The CLI underneath

Everything above runs through slash commands, which call the CLI. The full
verb list is in the [README](../README.md#the-cli); every verb describes
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
