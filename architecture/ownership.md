---
STATUS: ACCEPTED
date: 2026-05-24
---

# Compass - Service Ownership

<!-- the assess stage reads this file and includes it in architecture-loaded.yml as a
     narrative artifact. The architect uses ownership information to
     flag when a proposed change crosses component boundaries - a common source
     of undetected coupling and rework.

     Keep this file current. Stale ownership is worse than no ownership file:
     the role will flag risks against the wrong surface. -->

## Component ownership

Compass is a single-maintainer framework. All components are owned by the
framework maintainer. The table below names the component, what it owns
exclusively, and what it must not do.

| Component | Owns | Must own exclusively |
|---|---|---|
| `cli/compass` | Approach evaluation, gate checking, tdd-red/green evidence, rework-scan, retro, ADR helpers | All mechanism-produced writes to issue manifests and evidence directories |
| `hooks/pre-tool.sh` | `.red` marker gate enforcement | The decision of whether to block a tool call |
| `hooks/stop.sh` | Session-end signal scanning, rework prompt | Detection of scope-bloat and rework signals |
| `commands/*.md` | Phase slash-command definitions | The user-facing pipeline protocol |
| `agents/*.md` | Role agent definitions | Agent instructions and hard boundary statements |
| `governance/` | Routing policy, guardrails, strategies, signals | The machine-readable governance files that the CLI runs |
| `architecture/` (this tree) | Compass's own architectural record | The ADRs and narrative files that describe the framework itself |
| `templates/` | Worked examples for adopters | The template shapes adopters copy. The CLI reads `templates/<kind>.md` in two places: `compass issue template show` (`cli/compass_pkg/template_lists.py`) and `compass policy lint` (`cli/compass_pkg/policy_lint.py`). A template change can break either command |

---

## Must own - per component

### Pipeline (commands/ + stages)

**Must own:**
- The authoritative definition of what each stage produces (the stage-artifact
  contract).
- The gate set for each delivery approach (as computed by the router and encoded in
  `manifest.yml.gates`).
- The Definition of Ready (requirements review → plan gate) and Definition of Done
  (verify → ship gate).

### Router (governance/routing-policy.yml + `compass approach evaluate`)

**Must own:**
- The deterministic computation of the delivery approach, stage weights, and gate set from
  the four context-dimension assessment.
- The routing rule logic (floors, caps, immovable gates).
- The `routing-policy.yml` schema and its validation.

### Guardrails (governance/guardrails.yml + `compass check`)

**Must own:**
- The five hard guardrail definitions (`G1`–`G5`) and their check logic.
- The typed gate evidence schema (`{type, path}` - not bare paths).
- The mechanical pass/fail determination for each gate.

### Strategies (governance/strategies.md + hooks/pre-tool.sh)

**Must own:**
- The BDD strategy (G/W/T as spec and acceptance check).
- The TDD strategy (red → green → refactor cycle and `.red` marker protocol).
- The approach-awareness of strategy enforcement (the spike approach suspends TDD;
  other delivery approaches do not).

### Role Pipeline (agents/*.md + commands/consult.md)

**Must own:**
- Each role's entry-point command and the artifact it produces.
- The `architect` agent's annotation protocol (`architecture-notes.md`
  with five headed sections, no Given/When/Then).
- The role-first / planner-second order of operations.

---

## Must not do - boundary rules

Each rule below names an invariant from the table in
`architecture/decisions/README.md` and the specific way a future change is
most likely to break it. These are the places where a plausible, well-meant
change would quietly cross a line.

### `compass retro` must not mutate manifest.yml

`compass retro` is read-only over all issue manifests. It aggregates
reassessment data to produce a retrospective report but never writes back to
any `.compass/work/<issue>/manifest.yml`. Mutation would violate `Inv-4`
(Flow advises, never gates). The likely way in is a future pass that reads
every issue's reassessment log: writing a summary marker back into
`manifest.yml` looks harmless.

### rework-scan must not exit non-zero on detection

`compass rework-scan` exits 0 whether or not rework signals are detected.
Detection is advisory - it writes a report to `.compass/flow/rework-<date>.md`
and continues. Exiting non-zero would make rework-scan a blocking gate,
violating `Inv-4`. Detection is not the same as a verdict, and a scan that
can fail a build will be tuned until it stops detecting anything.

### architect must not emit Gherkin scenarios

`architecture-notes.md` contains annotations, candidate ADR titles, and
boundary-risk flags. It never contains Given/When/Then scenarios. Scenarios live
in `acceptance-criteria.md` exclusively. Emitting scenarios from the role would violate
`Inv-5` (one spec, many roles). A role that emits scenarios has forked the
spec, which is exactly what the one-spec rule exists to prevent.

### No mechanism may write into manifest.yml.assessment

`manifest.yml.assessment` is the sole field the human fills with judgement (risk,
familiarity, size, goal, role, labels). Every mechanism-produced
load record (`architecture-loaded.yml`, `architecture-notes.md`, `evidence/`,
etc.) lives in its own named file outside `manifest.yml.assessment`. Violating this
would cross `Inv-1`. The tempting mistake is folding loaded architecture
content into `assessment` because it informed the judgement; it did not make it.

### The guardrail count stays at five (`G1`–`G5`)

No new guardrail may be added without a deliberate framework change. Mechanisms
that extend gate checks (typed DoD, architectural-integrity checks) register as
CHECK\_FN entries under an existing guardrail (typically `G4`), not as new G-N
entries. This protects `Inv-2` (five guardrails). Register each check under
the guardrail it actually serves: a Definition-of-Done check is about evidence
(`G4`), not about having a test (`G1`), and filing it under `G1` misreports what
cleared the gate.

### No mechanism may hard-code governance/signals.yml content

`hooks/stop.sh` and `compass rework-scan` must read `governance/signals.yml` at
runtime, not replicate its patterns in Python or shell code. `signals.yml`
exists so a project can extend the patterns without touching the CLI;
hard-coding them takes that away and violates `Inv-7` (deterministic
mechanism - the CLI must read the file).

---

## Cross-component dependency rules

A change that affects any of the following cross-component pairs must trigger
an architect consultation (via `/compass:consult architect`) or
explicitly note why the consultation is not needed:

| Caller component | Callee component | Risk |
|---|---|---|
| Any agent (`agents/*.md`) | `acceptance-criteria.md` | Agents must not write scenarios; annotation only |
| `compass approach evaluate` | `governance/routing-policy.yml` | Schema changes need a routing-policy ADR |
| `compass check` | `governance/guardrails.yml` | Adding a check needs a guardrail-count check |
| `hooks/pre-tool.sh` | `.compass/work/<issue>/.red` | Any change to the marker protocol needs updating both sides |
| `frame_load_architecture` | `architecture/decisions/ADR-*.md` | ADR parsing logic change needs `tests/test_frame_loads_architecture.py` (`TRC-X1`) to stay green |
