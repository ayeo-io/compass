# Assess - the sizing rubric

Assess is the component that runs at the start of every issue. It reads four assessment
dimensions, applies `governance/routing-policy.md`, and writes `delivery-approach.md`. This
file is its rubric. The `adaptive-routing` skill is the procedural companion;
this is the reference.

Assess does not pick an approach from a list. Assess scores four dimensions;
`compass approach evaluate` composes and constrains the approach, and
explains the result. The five reference shapes in this directory are common
shapes the composition lands near - not a menu.

---

## Step 1 - Score the four dimensions

For each dimension, the assess stage assigns a value and writes a one-line
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
| `greenfield` | Net-new code with no existing behaviour to preserve. |
| `brownfield-mapped` | Existing code, and its current behaviour is already captured in scenarios (or trivially readable). |
| `brownfield-unmapped` | Existing code whose behaviour is *not* written down. A floor forces `behaviour-mapping` here - you cannot safely change what you have not first described. On an atomic or small change with trivial or contained risk and no domain label it is advice instead (`RP-ADV-002`). |

### Size - *how much work is this, honestly?*

| Value | Test |
|---|---|
| `atomic` | One file, one obvious change, < ~30 min, no design decision. |
| `small` | 1–3 files, a known solution pattern, no new architecture. |
| `standard` | Several files, 1–3 days, one or two design decisions. |
| `large` | Multi-module, 1–2 weeks, real architecture, plausibly parallelisable. |
| `product` | A new system or subsystem, 2+ weeks, many independent work subtasks. |

Size is the only dimension a person reliably over- or under-estimates.
When unsure, the assess stage estimates *up* - it is cheaper to collapse a
stage that turned out easy than to discover mid-implementation that the
approach was too light.

### Goal and role - *who is invoking, and what outcome are they after?*

| Value | Entry point | What it changes |
|---|---|---|
| `engineer` | `/compass:assess` | Standard pipeline ownership. |
| `product-owner` | `/compass:intent` | Adds `intent.md` upstream of the spec; inserts the intent-fidelity gate before Plan. |
| `product-marketer` | `/compass:position` | Adds `positioning.md` / `launch-readiness.md`; blocks shipping on the claims gate. |
| `designer` | `/compass:design` | Adds `ui-contract.md`; UI contracts enter the define stage as scenarios. |
| `qa` | joins at `/compass:verify` | Owns the Verify gate; can send an issue back to define if scenarios are uncoverable. |

Intent is also *the actual outcome wanted*, not just the literal request. "Add
a CSV export" invoked by a product owner whose `intent.md` says "let finance
self-serve" may need more than a button. Assess reads `intent.md` if one
exists.

One goal value is not a role: **exploration** - "I cannot frame this well
enough to deliver it yet." An `exploration` goal composes towards the **Spike**
approach (see `approaches/spike.md`), the way live-defect urgency composes towards
Hotfix. Assess still scores all four dimensions; the goal is what selects
the shape.

---

## Steps 2 and 3 - the CLI composes and constrains

You do not compose the approach. Run:

```
compass approach evaluate --issue <slug> --write
```

It applies `governance/routing-policy.yml` to the assessment you just
recorded - composing the candidate shape, then applying the floors, caps,
immovable gates and blocking role rules - and folds the result back into the
manifest. Same assessment plus same policy gives the same approach, every time.

`approaches/composition-reference.md` has the detail, for tuning the policy
or explaining a result. `--verbose` prints which rules fired.

## Step 4 - Write `delivery-approach.md` and confirm

Assess writes `.compass/work/<issue-slug>/delivery-approach.md` from
`templates/delivery-approach.md`. It contains:

- the four dimension assessment, each with its one-line justification;
- the composed candidate approach;
- every routing rule that fired and what it changed;
- the final approach: per-stage weight, the gate set, the multiagent orchestration;
- **the de-scope ledger** - every stage or check that is collapsed or skipped,
  each with an explicit "safe to skip because…" line. A stage with no
  justification cannot be skipped; if the assess stage cannot justify a skip,
  the stage runs.

Routing is **advisory until confirmed**. The human can override any dimension or
the final approach - overrides are recorded in `delivery-approach.md` too, with who and why.
What cannot be overridden: an `immovable_gate`, or a `floor` (a routing
rule is governance speaking; changing it means amending
`governance/routing-policy.yml`, not overriding an approach).

---

## Reassessing mid-issue

If implementation shows the size was misread - the "small" change is growing
into a multi-module refactor - the correct move is to **stop and re-assess**,
not to push on with an approach you no longer believe. `/compass:assess --reassess`
re-scores the dimensions, writes a new `delivery-approach.md` revision, and records what
changed and why. A re-assess is a normal event, not a failure. An approach quietly
outgrown is the failure.
