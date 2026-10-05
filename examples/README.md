# Compass - Worked Examples

Five completed Compass issues, one per reference shape. Each is real-shaped
exactly as it would look *after the issue finished* - `.compass/work/<issue-slug>/`
holds the manifest, the devlog and the evidence, and
`docs/compass/<date>-<slug>/` holds the human-facing documents and the gates
they carry.

The framework's docs tell you what Compass *is*. These show you what it *looks
like done*. Read one and you have seen a delivery approach end to end; read
all five and you have seen the whole adaptive range - from a one-string fix
with almost no process, to a multiagent subsystem that runs every gate.

Each example is self-contained and verifiable. From inside any example's issue
directory:

```
compass issue lint --file manifest.yml         # the manifest is well-formed
compass approach evaluate --issue <slug>   # the assessment composes to the claimed shape
compass check --issue <slug>                 # the guardrail checks pass (see the Spike note)
```

---

## The five examples

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

### 2. `feature-api-change/` - the regular approach

**Issue:** add per-client rate limiting to the public `/search` endpoint after
one client's bulk job degraded latency for everyone.

**What it demonstrates:** the default working shape at full artifact weight -
`requirements-review.md` with the Definition of Ready ticked, a real `technical-design.md` with
two ADR-style design decisions, a full `verification-report.md` with the
Definition of Done and pasted test output. It also shows breakdown being
*skipped for a reason* (the work units share code surface, so multiagent
orchestration would create a merge conflict, not parallelism).

**One-line lesson:** the normal case - every stage runs, the two checklist
gates are real, and "solo" is a justified finding, not a default.

### 3. `hotfix-regression/` - the hotfix

**Issue:** `/search` returns a 500 for any request with an empty `filter` object -
a live crash on a new mobile build.

**What it demonstrates:** reproduce-first (the failing regression test *is* the
spec - `evidence/red-TRC-001.json` reproduces the crash before any fix), the compressed
front of the pipeline, the *uncompressed* Verify gate, and the **mandatory
follow-up**. `manifest.yml`'s `follow_ups:` lists three follow-ups, all resolved; `delivery-approach.md` §6 and
the `devlog.md` ship entry show all three **resolved** - which is what makes this a
closed issue and not an open one. `compass check` enforces it.

**One-line lesson:** a hotfix defers work to go faster and must finish it
before it closes - a hotfix with an outstanding follow-up is an open issue.

### 4. `initiative-new-subsystem/` - the initiative

**Issue:** build the in-app notifications subsystem - durable delivery,
per-category preferences, a security category that mute cannot suppress.

**What it demonstrates:** full weight, every gate, multiagent orchestration across worktrees -
and two routing guardrails *firing visibly*. The assessment includes
`labels: [migrations]`, so **RP-FLOOR-003** raises the candidate from feature
to initiative ("domain risk overrides size") - you can see it in
`manifest.yml`'s `policy_rules_fired` and in `delivery-approach.md` §3. A product owner is
involved, so **RP-ROLE-002** needs `intent.md` and blocks Plan until the spec
is checked against it for intent fidelity. The `migrations` tag also makes
guardrail `G5` apply - `manifest.yml`'s `evidence:` registry carries a typed
`human-approval` entry (approver, role, scope, decision, timestamp,
conditions) for the irreversible schema change, and the JSON record it points
at lives under `evidence/approval-migration-0042.json`. Full set: `intent.md`
with an Internal FAQ, `distribution-map.md` with the two-subtask multiagent
orchestration, per-subtask *and* combined verification.

**One-line lesson:** the router is governed too - a domain tag can overrule
the size assessment, and the heaviest delivery approach is heavy on purpose.

### 5. `spike-technical-unknown/` - the spike

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

If you read them in approach-weight order - `quick-fix-typo`, `feature-api-change`,
`hotfix-regression`, `initiative-new-subsystem`, `spike-technical-unknown` -
you watch the same eight-stage pipeline and the same artifact vocabulary
grow and shrink while the manifest keeps the same shape. That constancy is the
point: a person who has read one Compass issue can read any other. The
*weight* changes; the *shape* does not.

## BDD adapters

`bdd-adapters/` holds a worked project per BDD runner - `pytest-bdd`,
`cucumber-js`, `behave` and `godog`. Each takes the same Compass spec through
the same four steps (declare the runner, `compass bdd extract`, bind the steps,
run) and only the binding differs. A CI job runs each one, because an
example no job runs is an example nobody can trust.
