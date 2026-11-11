# The path

Every delivery issue runs the same four stages, in order: assess, specify,
build and ship (ADR-092). The stages are fixed in code and have no modes.
Every issue owes the same evidence. Only a person's approval is added,
for a `G5` label or critical risk. A project can add more in its
`compass.yml`.

`/compass:go` runs the whole path in one session. `/compass:quick-fix` is
its short form, for a change the person already knows is small. A change takes
two commands. `compass quick-fix start` opens the issue and serves every
size. Between the commands the session writes the tests and the code and
runs the tests. `compass quick-fix finish -m "<message>" -- <test command>`
writes the record (ADR-099). After each step, `compass next` and the verb
that wrote the record print one `next:` line: the one command to run next.
Follow it until `compass check` passes.

## The four stages

| Stage | What it produces | Judged here |
|---|---|---|
| Assess | The assessment with a reason for each value, the `evidence_required` list, the pending gates, the `S17` block and the checkpoints. | No gate passes here. |
| Specify | The scenarios in `acceptance-criteria.md` or a `.feature` file, the test each one declares, and, where `S17` applies, the specification and its DSL. | `G2` (each scenario has an id and an intent), `G3` (each claim traces to a scenario), the `specify` checkpoint where `scenario-approval` is owed, the `S17` stage 1 review where it is owed. |
| Build | The tests, then the code. `finish` proves the red on a copy of the base commit and the green in the working tree. Where `S17` applies, the outer-loop records, the isolation proof and the layering record. | `G1` (tested before it lands), the outer-loop checks where owed, the Definition of Done as the Build exit list where owed, the `S17` stage 2 review at the `build` checkpoint where owed. |
| Ship | `compass check` passes, every owed sign-off is on record, and the commit lands. | Every owed `verify.*` gate with typed evidence (`G4`), `dod-evidence-typed` where a Definition of Done is owed, `G5` (the human sign-off), the `S17` stage 3 review at the `ship` checkpoint where owed. |

The gate ids keep their `verify.` prefix, because every archived manifest
and evidence record names them. `finish` passes the three common gates.

On brownfield code whose behavior is not written down
(`familiarity: brownfield-unmapped`), specify starts with behavior mapping,
from the `atdd` skill: it writes the baseline scenarios before any new
one. A floor asks for it (`RP-FLOOR-002`), or gives it as advice on a small
change (`RP-ADV-002`).

Each stage is done when its records show it:

- Assess, when `delivery_approach` and `evidence_required` are set.
- Specify, when each scenario has an id, an intent and a declared test, and
  the `specify` checkpoint has an outcome where it is listed.
- Build, when each scenario that is not `verifiable: narrative` has a red,
  then a green. `finish` writes both.
- Ship, when the issue is closed. `finish` commits once the first ship
  approval is on record. The ship approval comes after the
  landing: `compass issue link set --pr <n>` reads it from the merged pull
  request's review, or a person types it after `compass evidence request
  --ship`. `compass next` names the step while it is owed.

## The evidence rows

`cli/compass_pkg/evidence_required.py` computes the evidence from the
assessment and the configuration in force. Two rows exist: `RP-EVID-SPIKE`
for a spike and `RP-EVID-COMMON` for every other assessment. The additions
apply on top of the common row:

- **The common row** (`RP-EVID-COMMON`): every delivery issue owes
  `request`, who asked for the change and a link to the request (#356),
  `scenarios`, `red-before-green`, `suite-green`, the three gates that no
  configuration removes (`verify.correctness`, `verify.governance`,
  `verify.traceability`), and `ship-approval`, a person's approval of the
  change at ship (ADR-095). Risk, size, familiarity and urgency add nothing
  to it.
- **The additions**, each a person's approval: `scenario-approval` for a
  `G5` label or critical risk, and `human-approval` for a `G5` label. The
  `G5` labels are `auth`, `payments`, `personal-data` and `migrations`, and
  each label in the project's `signoff_labels`.
- **Tokens a project adds**: the review tokens `regression`, `security`,
  `clarity` and `architecture`, `definition-of-done`, `reproduce-first`, and
  the `S17` tokens `outer-loop`, `isolation` and `layering`. They are owed
  only where the `require_evidence` setting of the project's `compass.yml`
  adds them. With no `S17` token owed, the `S17` routing is `guidance`: the
  `atdd` skill is advice and no check of the strategy runs.

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
`compass approach evaluate`. It records the urgency and adds no evidence: a
hotfix owes what every delivery issue owes. A project that wants the
reproduction recorded first adds `reproduce-first` in `require_evidence`;
the first scenario is then the reproduction, and its red is recorded before
any scenario approval or code.

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
- A red before each green. Only a spike suspends that strategy (`S2`). `finish` proves it on a copy of the base commit.
- The three gates no configuration removes.
- Re-assess when the work outgrows its assessment: `/compass:assess
  --reassess --reason "..."`. The re-assessment recomputes the evidence and
  logs the change in the manifest's `reassessments:` list.
