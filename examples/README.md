# Compass - Worked Examples

Two completed Compass issues: a quick fix and a spike. Each is real-shaped
exactly as it would look *after the issue finished* - `.compass/work/<issue-slug>/`
holds the manifest, the devlog and the evidence, and
`docs/compass/<date>-<slug>/` holds the human-facing documents and the gates
they carry.

The framework's docs tell you what Compass *is*. These show you what it *looks
like done*. Read the quick fix and you have seen a delivery approach end to
end. Read the spike and you have seen the way out of the delivery pipeline.

The examples were assessed under 6.x, when role was an assessment dimension. Their records keep it.

Each example is self-contained and verifiable. From inside any example's issue
directory:

```
compass issue lint --file manifest.yml         # the manifest is well-formed
compass approach evaluate --issue <slug>   # the assessment composes to the claimed shape
compass check --issue <slug>                 # the guardrail checks pass (see the Spike note)
```

---

## The two examples

### 1. `quick-fix-typo/` - the quick fix

**Issue:** the upload timeout error says "try again later" when it should name
the file-size limit that is the actual cause.

**What it demonstrates:** the *lightness*. The requirements review, design, and breakdown all
collapse - and `delivery-approach.md` §5 carries an explicit "safe to skip because…" line
for each. One scenario is the whole spec. Verify is a short note, not a full
report. The artifact set is four files and an `evidence/` pair, and that is
*correct* - quick fix adapts test surface, never test existence, so the red and
green records are still there. Their filenames follow the binding: a run
recorded `--scenario TRC-001` writes `evidence/green-TRC-001.json`, and a run
with no binding writes `evidence/green.json`. The `manifest.yml` carries a
top-level `evidence:` registry of two typed entries (a `test-run` and an
`artifact`), and each `pass` gate references them by id - `verify.correctness`
points at the `test-run`, governance and traceability at the `artifact`.

**One-line lesson:** when the change is small on every axis, the quick fix
skips most stages, and records why - but the de-scopes are written down, not
assumed.

### 2. `spike-technical-unknown/` - the spike

**Issue:** is `weasyprint` a viable PDF engine for our report layouts, or do we
need a heavier tool? A timeboxed investigation.

**What it demonstrates:** the way out of the delivery pipeline. `goal: exploration` selects
Spike; `scenarios:` and `changed_files:` are empty *on purpose* - a spike has
no acceptance criteria and lands no production code. The `.spike` marker file
suspends the TDD strategy (the hook does not block edits). There is no
`technical-design.md` and no `verification-report.md`; the `devlog.md` ends in a written
**conclusion** ("viable with caveats") and a **graduate-or-discard decision**
(graduate - re-assess into a real delivery issue; the scratch branch is *not*
merged). `manifest.yml`'s `evidence:` registry carries a single
`spike-conclusion` entry with `decision: graduate-to-delivery` and a
`next_task:` link to the fresh delivery issue.

**Note on `compass check` for the Spike:** `compass check` reads the delivery
approach. On a spike it skips the delivery defaults (`G1`-`G5`) and runs the
spike-only guardrails instead - `S1` (a `spike-conclusion` is recorded with a
valid decision; if `graduate-to-delivery`, `next_task` is set) and `S2`
(`changed_files` is empty - a spike ships nothing). Both *run and pass* for
this example; the run reports `PASS - 3 check(s) passed on
'pdf-export-library-viability' (spike)`. The delivery guardrails are not
bypassed, they are *deferred to graduation*: if the finding is acted on, a
fresh assessment puts it on a delivery approach where the delivery checks
apply in full to any code that is kept.

**One-line lesson:** exploration is not forced through a delivery-shaped
pipeline - and it is safe because nothing lands from a spike.

---

## Reading order

Read `quick-fix-typo` first, then `spike-technical-unknown`. The manifest
keeps the same shape in both, and only the stages that run change. A person
who has read one Compass issue can read any other.

## BDD adapters and acceptance test examples

`bdd-adapters/` holds a worked project per BDD runner - `pytest-bdd`,
`cucumber-js`, `behave` and `godog`. Each takes the same Compass spec through
the same four steps (declare the runner, `compass bdd extract`, bind the steps,
run) and only the binding differs. A CI job runs each one, because an
example no job runs is an example nobody can trust.

`atdd-adapters/` holds a reference example per language of the four-layer
acceptance test model: executable specifications, a domain-specific language
(DSL), protocol drivers and the system under test. `atdd-adapters/python/` is
a small todo service with an HTTP API and a CLI. It gives the support code a
project needs before its first specification: an alias helper, a driver
factory that picks the API driver or the CLI driver at start-up, a DSL root,
and a layering test that fails, naming the file, the line and the rule, when
a layer breaks its shape. The CI job `atdd-adapter-python` runs it through
both drivers and runs its layering test. `atdd-adapters/typescript/` is the
same service and the same layers in TypeScript, run by `node:test`, with its
packages pinned by a lock file. Its runner adapter writes the JUnit report
`compass tdd-red` reads the stage 1 red from. The CI job
`atdd-adapter-typescript` runs it through both drivers and runs its layering
test.
