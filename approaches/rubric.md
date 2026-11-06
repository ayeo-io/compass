# Assess - the sizing rubric

Assess runs at the start of every issue. It reads three scored dimensions,
two switches and any domain labels. `compass approach evaluate` then applies
the configuration in force (`compass policy show`; an unmigrated 5.x project
runs on its own copied `governance/` until `compass policy migrate`) and
records the evidence the change owes in the manifest. This file is the
rubric. The `adaptive-routing` skill is the procedural companion; this is
the reference.

Assess does not pick a process. Every delivery issue runs the same four
stages (`approaches/path.md`). Assess scores the three dimensions and reads
the two switches, and the CLI selects the evidence row, adds what the
labels and the configuration add, and explains the result.

---

## Step 1 - Score the three dimensions and read the switches

The three scored dimensions are `risk`, `familiarity` and `size`. The
evaluator refuses an assessment without any one of them. For each dimension,
and for each switch it sets, the assess stage assigns a value and writes a one-line
justification. If it cannot justify a value, it asks the human rather than
guessing - an unjustified value is worse than a question.

### risk - *if this goes wrong, how bad and how wide?*

| Value | Test |
|---|---|
| `trivial` | Wrong outcome is cosmetic or instantly obvious and instantly reversible. No data, no money, no auth, no other team. |
| `contained` | Failure is annoying but bounded to one feature/surface, recoverable without incident, no data loss. |
| `cross-cutting` | Failure spreads across features or services, or degrades something many users touch. Recovery needs coordination. |
| `critical` | Failure can lose data, lose money, breach auth/privacy, or cannot be cleanly rolled back. |

risk is about *consequence*, never *effort*. A one-character change can
be `critical`.

### Familiarity - *new code or existing code, and how well mapped?*

| Value | Test |
|---|---|
| `greenfield` | Net-new code with no existing behavior to preserve. |
| `brownfield-mapped` | Existing code, and its current behavior is already captured in scenarios (or trivially readable). |
| `brownfield-unmapped` | Existing code whose behavior is *not* written down. A floor forces `behavior-mapping` here - you cannot safely change what you have not first described. On an atomic or small change with trivial or contained risk and no domain label it is advice instead (`RP-ADV-002`). |

### Size - *how much work is this, honestly?*

| Value | Test |
|---|---|
| `atomic` | One file, one obvious change, < ~30 min, no design decision. |
| `small` | 1–3 files, a known solution pattern, no new architecture. |
| `medium` | Several files, 1–3 days, one or two design decisions. |
| `large` | Multi-module, 1–2 weeks, real architecture, plausibly parallelisable. |
| `product` | A new system or subsystem, 2+ weeks, many independent work subtasks. |

Size is the only dimension a person reliably over- or under-estimates.
When unsure, the assess stage estimates *up* - it is cheaper to give
evidence that turned out easy to give than to discover mid-build that the
evidence selected was too light.

### The two switches and the domain labels - *what selects a shape, and what adds evidence?*

The two switches are `goal` and `urgency`. Neither is scored, and either can
be left out.

`goal` is `delivery` or `exploration`. `goal: exploration` selects the spike
(`RP-EVID-SPIKE`, `approaches/spike.md`), the one approach that is not on the
path. Assess still scores all three dimensions; the switch is what selects
the spike.

`urgency` is `none` or `live-defect`. `urgency: live-defect` is the hotfix
setting. It adds `reproduce-first` at any size, and on an atomic or small fix
it selects the defect row (`RP-EVID-DEFECT`).

The domain labels are an open list of tags, such as `auth`, `payments`,
`personal-data` and `migrations`. They are not scored and need no
justification. Those four add the `verify.architecture` gate, the scenario
approval at specify (`scenario-approval`) and the guardrail 5 sign-off
(`G5`, `human-approval`). Critical risk alone adds the architecture gate and
the scenario approval, but not that sign-off.

Role is not an assessment dimension. The product owner, product marketer,
designer and QA are perspectives a session consults. A document on disk
brings no gate: Compass needs and checks only `acceptance-criteria.md`
(ADR-091).

Intent is *the actual outcome wanted*, not just the literal request. "Add
a CSV export" from a product owner who says "let finance self-serve" may need
more than a button. Assess reads the intent the product owner gave, in the
issue description or a brief.

---

## Steps 2 and 3 - the CLI selects the evidence

You do not select the evidence. Run:

```
compass approach evaluate --issue <slug> --write --justify risk="<why>" --justify size="<why>" ...
```

Each scored dimension, and each switch you set, needs a `--justify` when its
value is new or changed. Domain labels need none. `compass quick-fix start`
does the same in one call, with each value and its reason as one flag
(`--risk "contained - <why>"`).

It applies the configuration in force (the shipped default preset plus the
project's `compass.yml`) to the assessment: it matches one evidence row,
adds what the labels and the risk add, adds each `add_gate` floor and
project guardrail, and writes the result to the manifest. Same assessment
plus same configuration gives the same evidence, every time. Familiarity
does not change the evidence: `brownfield-unmapped` asks for the
`behavior-mapping` skill instead (`RP-FLOOR-002`, or `RP-ADV-002` as advice
on a small change).

`approaches/composition-reference.md` has the detail, for tuning the
configuration or explaining a result. `--verbose` names the row that matched
and each rule that fired.

## Step 4 - Record the decision and confirm

The manifest is the record: `compass approach evaluate --write` or
`compass quick-fix start` writes it, and `compass approach show` prints it.
The manifest holds:

- the three scored dimensions and any switches, each with its one-line
  justification (`justifications:`);
- every rule that fired (`policy_rules_fired:`);
- the `evidence_required` list, and the gates, the `S17` block and the
  checkpoints derived from it.

The assessment is **advisory until confirmed**. The person can override any
dimension: re-run the evaluation with the new value and its reason, and the
evidence follows. What cannot be overridden is an `immovable_gate` or a
floor of the configuration. Changing one is a reviewed change to the
project's `compass.yml`, not an override for one issue, and a loosening
needs a waiver that the project's owner approves. An issue assessed before
the path keeps its stage modes: it can keep a lower mode for a stage a floor
did not name, on the approach the floor raised, only with an issue waiver
the project owner approved
(`${CLAUDE_PLUGIN_ROOT}/governance/decisions/2026-10-17-a-waived-stage-mode-holds-on-a-floor-raised-approach.md`).

---

## Reassessing mid-issue

If the build shows the size was misread - the "small" change is growing
into a multi-module refactor - the correct move is to **stop and re-assess**,
not to push on with evidence you no longer believe is enough.
`/compass:assess --reassess` re-scores the dimensions, recomputes the
evidence and records what changed and why in the manifest's
`reassessments:` log. A re-assess is a normal event, not a failure. An
assessment quietly outgrown is the failure.
