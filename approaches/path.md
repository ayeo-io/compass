# The path

Every delivery issue runs the same four stages, in order: assess, specify,
build and ship (ADR-092). The stages are fixed in code and have no modes.
What changes from one issue to the next is the evidence the change owes
before it ships, and assess selects that evidence from the assessment.

`/compass:go` runs the whole path in one session. `/compass:quick-fix` is
its short form, for a change the person already knows is small. Both start
with `compass quick-fix start`, which serves every size. After each step,
`compass next` and the verb that wrote the record print one `next:` line:
the one command to run next. Follow it until `compass check` passes.

## The four stages

| Stage | What it produces | Judged here |
|---|---|---|
| Assess | The assessment with a reason for each value, the `evidence_required` list, the pending gates, the `S17` block and the checkpoints. | No gate passes here. |
| Specify | The scenarios in `acceptance-criteria.md` or a `.feature` file, the test each one declares, and, where `S17` applies, the specification and its DSL. | `G2` (each scenario has an id and an intent), `G3` (each claim traces to a scenario), the `specify` checkpoint where `scenario-approval` is owed, the `S17` stage 1 review. |
| Build | A red for each scenario, then the code, then a green. Where `S17` applies, the outer-loop records, the isolation proof and the layering record. | `G1` (tested before it lands), the outer-loop checks, the Definition of Done as the Build exit list, the `S17` stage 2 review at the `build` checkpoint. |
| Ship | `compass check` passes, every owed sign-off is on record, and the commit lands. | Every `verify.*` gate with typed evidence (`G4`), `dod-evidence-typed`, `G5` (the human sign-off), the `S17` stage 3 review at the `ship` checkpoint. |

The gate ids keep their `verify.` prefix, because every archived manifest
and evidence record names them. They are passed at Ship.

On brownfield code whose behavior is not written down
(`familiarity: brownfield-unmapped`), specify starts with the
`behavior-mapping` skill: it writes the baseline scenarios before any new
one. A floor asks for it (`RP-FLOOR-002`), or gives it as advice on a small
change (`RP-ADV-002`).

Each stage is done when its records show it:

- Assess, when `delivery_approach` and `evidence_required` are set.
- Specify, when each scenario has an id, an intent and a declared test, and
  the `specify` checkpoint has an outcome where it is listed.
- Build, when each scenario that is not `verifiable: narrative` has a red,
  then a green.
- Ship, when the issue is closed. The ship approval comes after the
  landing: `compass issue link set --pr <n>` reads it from the merged pull
  request's review, or a person types it after `compass evidence request
  --ship`. `compass next` names the step while it is owed.

## The evidence rows

`cli/compass_pkg/evidence_required.py` computes the evidence from the
assessment and the configuration in force. The first row that matches
wins, and the additions apply on top of it:

- **The light row** (`RP-EVID-LIGHT`): an atomic or small change with
  trivial or contained risk, no hotfix setting and no `G5` label. It owes the evidence every delivery issue owes: scenarios,
  a red before each green, a green suite, the three gates that no
  configuration removes (`verify.correctness`, `verify.governance`,
  `verify.traceability`), and `ship-approval`, a person's approval of the
  change at ship (ADR-095).
- **The defect row** (`RP-EVID-DEFECT`): an atomic or small fix under the
  hotfix setting, with risk that is not critical and no `G5` label. It adds `regression`, `security` and the Definition of Done.
- **The standard row** (`RP-EVID-STANDARD`): every other delivery
  assessment. It adds `regression`, `security`, `clarity` and the
  Definition of Done.
- **The additions**: `architecture` for cross-cutting or critical risk or a
  `G5` label; `scenario-approval` for a `G5` label or critical risk;
  `human-approval` for a `G5` label; `reproduce-first` under the hotfix
  setting. The `G5` labels are `auth`, `payments`, `personal-data` and
  `migrations`.
- **The `S17` tokens**: `outer-loop`, `isolation` and `layering`, owed by
  the four-layer acceptance strategy as its routing for the row says.

The exact conditions, the tokens of each row and the records that meet each
token are in `governance/routing-policy.md`, "The evidence rows" and "The
path writer". That file is the authority; this summary follows it.

`compass approach show` prints the issue's evidence on one line.
`compass approach evaluate --verbose` names the row that matched and each
rule that fired.

## The hotfix setting

A hotfix is not an approach. It is the assessment value `urgency:
live-defect`, given as `--urgency "live-defect - <reason>"` on
`compass quick-fix start` or as `--assessment urgency=live-defect` on
`compass approach evaluate`. It does two things:

- It adds `reproduce-first`. The first scenario is the reproduction, and its
  red is recorded before any scenario approval or code. `compass next` sends
  the agent to `compass tdd-red` before anything else.
- On a small fix with no `G5` label and risk that is not critical, it
  selects the defect row.

A fix that is medium or larger takes the standard row and still owes
`reproduce-first`.

The hotfix keeps its follow-up. Before the issue closes:

- The reproduction is a real Given/When/Then scenario in
  `acceptance-criteria.md` that names the defect.
- Each follow-up the fix owes is recorded with `compass follow-up add FU-<id>
  --github owner/repo#N --summary "..."`, linked to the GitHub issue that
  tracks it. A linked follow-up need not be resolved before the issue closes.
  Name the root cause, and file the missing scenario that would have caught
  the defect as a follow-up issue where one is owed.

The stop hook warns on an issue that carries `urgency: live-defect` while the
reproduction scenario is missing.

## The spike

A spike is the one approach that is not on the path. `goal: exploration`
selects it. It runs assess, build (explore) and ship (conclude), owes the
gate `spike.conclude`, and ships nothing. `approaches/spike.md` describes
it.

## What no issue can skip

- The default guardrails in `governance/guardrails.md`. Every row owes
  them.
- A red before each green. Only a spike suspends that strategy (`S2`).
- The three gates no configuration removes.
- Re-assess when the work outgrows its assessment: `/compass:assess
  --reassess --reason "..."`. The re-assessment recomputes the evidence and
  logs the change in the manifest's `reassessments:` list.
