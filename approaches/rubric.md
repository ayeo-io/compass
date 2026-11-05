# Assess - the sizing rubric

Assess is the component that runs at the start of every issue. It reads three
scored dimensions, two switches and any domain labels. It applies the routing
rules in force (`compass policy show`; an unmigrated 5.x project runs on its
own copied `governance/` until `compass policy migrate`), and records the
delivery approach in the manifest. This file is its rubric. The `adaptive-routing`
skill is the procedural companion; this is the reference.

Assess does not pick an approach from a list. Assess scores three dimensions
and reads two switches; `compass approach evaluate` composes and constrains
the approach, and explains the result. The five reference shapes in this directory are common
shapes the composition lands near - not a menu.

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
When unsure, the assess stage estimates *up* - it is cheaper to collapse a
stage that turned out easy than to discover mid-implementation that the
approach was too light.

### The two switches and the domain labels - *what selects a shape, and what raises the floor?*

The two switches are `goal` and `urgency`. Neither is scored, and either can
be left out. One value of each leans the approach towards a reference shape,
and a later routing rule can still raise it:

`goal` is `delivery` or `exploration`. `goal: exploration` leans towards the
spike shape (`RP-SHAPE-001`).

`urgency` is `none` or `live-defect`. `urgency: live-defect` on an atomic or
small change leans towards the hotfix shape (`RP-SHAPE-002`).

The domain labels are an open list of tags, such as `auth`, `payments`,
`personal-data` and `migrations`. They are not scored and need no
justification. Those four raise the approach to at least full
(`RP-FLOOR-003`), add the `verify.architecture` gate
and bring the guardrail 5 sign-off. Critical risk alone does not bring that
sign-off.

Role is not an assessment dimension. The product owner, product marketer,
designer and QA are perspectives a session consults. A document on disk
brings no gate: Compass needs and checks only `acceptance-criteria.md`
(ADR-091).

Intent is *the actual outcome wanted*, not just the literal request. "Add
a CSV export" from a product owner who says "let finance self-serve" may need
more than a button. Assess reads the intent the product owner gave, through
`/compass:intent` or in the issue description.

One goal value is **exploration** - "I cannot frame this well
enough to deliver it yet." An `exploration` goal composes towards the **Spike**
approach (see `approaches/spike.md`), the way live-defect urgency composes towards
Hotfix. Assess still scores all three dimensions; the switch is what selects
the shape.

---

## Steps 2 and 3 - the CLI composes and constrains

You do not compose the approach. Run:

```
compass approach evaluate --issue <slug> --write --justify risk="<why>" --justify size="<why>" ...
```

Each scored dimension, and each switch you set, needs a `--justify` when its
value is new or changed. Domain labels need none.

It applies the routing rules in force (the shipped default preset plus the
project's `compass.yml`) to the assessment you just recorded - composing the
candidate shape, then applying the floors, caps and immovable gates - and
folds the result back into the manifest. Same assessment plus
same configuration gives the same approach, every time.

`approaches/composition-reference.md` has the detail, for tuning the policy
or explaining a result. `--verbose` prints which rules fired.

## Step 4 - Record the decision and confirm

The manifest is the record of the delivery approach: `compass approach
evaluate --write` writes it, and on a quick fix `compass quick-fix start`
does. The pre-tool hook reads the manifest's `delivery_approach:`, and
`compass approach show` prints the decision. The manifest holds:

- the three scored dimensions and any switches, each with its one-line
  justification (`justifications:`);
- every routing rule that fired (`policy_rules_fired:`);
- the final approach: per-stage weight, the gate set, the orchestration.

The opening `devlog.md` entry holds **the de-scope reasons** - every stage or
check that is collapsed or skipped, each with an explicit "safe to skip
because…" line. A stage with no justification cannot be skipped; if the
assess stage cannot justify a skip, the stage runs.

Routing is **advisory until confirmed**. The human can override any dimension or
the final approach - log each override to `devlog.md`, with who and why.
What cannot be overridden: an `immovable_gate`, or a `floor` (a routing
rule is governance speaking; changing it means a reviewed change to the
project's `compass.yml`, not overriding an approach, and a loosening needs a
waiver that the project's owner approves). An issue can keep a lower mode for
a stage a floor did not name, on the approach the floor raised, only with an
issue waiver the project owner approved
(`${CLAUDE_PLUGIN_ROOT}/governance/decisions/2026-10-17-a-waived-stage-mode-holds-on-a-floor-raised-approach.md`).

---

## Reassessing mid-issue

If implementation shows the size was misread - the "small" change is growing
into a multi-module refactor - the correct move is to **stop and re-assess**,
not to push on with an approach you no longer believe. `/compass:assess --reassess`
re-scores the dimensions and records what changed and why in the manifest's
`reassessments:` log. A re-assess is a normal event, not a failure. An approach quietly
outgrown is the failure.
