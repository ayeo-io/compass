# Compass - Routing Deep Dive

This page takes six issues through assess: the scores, the evidence row,
the additions and the record in the manifest. The rubric itself, with the
three scored dimensions and the scoring tables, is `approaches/rubric.md`.

Every delivery issue runs the same four stages: assess, specify, build and
ship (`approaches/path.md`). What changes from one issue to the next is the
evidence the change owes before it ships. Assess computes that list,
`evidence_required`. It does not pick a delivery approach.

---

## The shape of every assessment decision

Assess runs the same four steps for every issue:

1. **Score the three dimensions** - risk, familiarity and size - and read
   the optional switches, goal and urgency. Each gets a one-line written
   justification. `compass quick-fix start` takes each dimension as an
   option. A dimension left out is recorded as `contained` risk,
   `brownfield-mapped` familiarity or `small` size, with the reason "not
   rated at start".
2. **Match the evidence row.** `cli/compass_pkg/evidence_required.py` reads
   the rows in order, and the first that matches wins:
   - `RP-EVID-SPIKE`: goal `exploration`. The issue is a spike, which is not
     on the path and ships nothing.
   - `RP-EVID-COMMON`: every other assessment. Risk, size, familiarity and
     urgency add no review and no record.
3. **Apply the additions and the configuration.** On the delivery row, each
   addition is an approval a person gives:
   - `RP-EVID-SIGNOFF` adds `scenario-approval` for a `G5` label or critical
     risk: a person approves the scenarios before any code edit;
   - `G5` adds `human-approval` for a `G5` label: a person signs the change
     off before it ships.

   The policy in force then adds the evidence of each matching
   `require_evidence` setting of `compass.yml` (`RP-SETTING-<n>`), the gate
   of each matching floor of the project's own (`add_gate`) and the skill a
   floor asks for (`require_skill`). The shipped check set holds no floor
   that adds a gate. Every rule that fires is recorded with its rationale.
4. **Record the evidence.** `compass quick-fix start` does this when it opens
   the issue, and `compass approach evaluate --write` does it on a re-assess.
   Each writes `delivery_approach: delivery`, `evidence_required`, the gates,
   the checkpoints and the rules that fired into `manifest.yml`.
   `compass approach show` prints the result in three lines.

Facts the cases use:

- The `G5` labels are `auth`, `payments`, `personal-data` and `migrations`,
  and any label a project adds with `signoff_labels`.
- Every delivery issue owes `request` (who asked, and a link to the request,
  ADR-096), `scenarios`, `red-before-green`, `suite-green`, three review
  gates and `ship-approval`, a person's approval of the change at ship
  (ADR-095).
- The immovable gates (`verify.correctness`, `verify.governance`,
  `verify.traceability`) are those three review gates. No configuration
  removes them. `compass quick-fix finish` passes them itself, from the test
  records and the output of `compass check` (ADR-099).
- The records of the four-layer acceptance strategy (`S17`), `outer-loop`,
  `isolation` and `layering`, are owed only where a `require_evidence`
  setting adds them.
- Which documents the issue holds is not an input. Compass needs only
  `acceptance-criteria.md` (ADR-091).
- The exact conditions are in `governance/routing-policy.md`, "The evidence
  rows".

The transcripts are real output of `compass approach evaluate --verbose
--assessment ...`, from the `assessment` line to the `gate set` line.

---

## Case 1 - A typo fix in an auth module

> **Request:** "Fix the typo in the JWT refresh error message."

| Dimension | Value | Justification |
|---|---|---|
| Risk | `trivial` | A misspelt word in an error string. No data, money or auth behavior is touched. |
| Familiarity | `brownfield-mapped` | Existing code that is easy to read. |
| Size | `atomic` | One file, one string, no design decision. |
| Goal | `delivery` | A known change to shipped code. |

Assess labels the change `auth`, because the label says where the change
is, not how risky it looks.

Every delivery assessment matches `RP-EVID-COMMON`. The `auth` label fires
two additions: `RP-EVID-SIGNOFF` adds `scenario-approval`, and `G5` adds
`human-approval`.

```text
  assessment      : {"risk": "trivial", "familiarity": "brownfield-mapped", "size": "atomic", "goal": "delivery", "labels": ["auth"]}
  evidence row    : RP-EVID-COMMON
  FINAL APPROACH  : delivery
  evidence owed   : request, scenarios, red-before-green, suite-green, correctness, governance, traceability, scenario-approval, human-approval, ship-approval
  policy rules fired:
    Every change owes the same evidence: the request, the scenarios, the red before the green, a green suite and the ship approval (RP-EVID-COMMON, evidence)
        - evidence owed: request, scenarios, red-before-green, suite-green, correctness, governance, traceability, ship-approval
    A change to a `G5` surface, or with critical risk, owes a person's approval of its scenarios (RP-EVID-SIGNOFF, evidence)
        - evidence owed: scenario-approval
    A change to a `G5` surface owes a person's sign-off before it ships (`G5`, guardrail)
        - evidence owed: human-approval
  gate set        : verify.correctness, verify.governance, verify.traceability
```

A one-character change to an auth error message owes every approval there
is. A label overrides the dimension scores.

**Record.** Three gates, all passed at ship, a person's approval of the
scenarios before the first code edit, and a person's sign-off before the
change lands.

- Until the scenarios are approved, the pre-tool hook refuses a code edit
  with the code `code-before-approval`.
- The manifest's `policy_rules_fired` list records the three rules, each
  with its rationale.
- A project cannot remove a rule. Every project runs one fixed check set,
  and a setting in `compass.yml` can only add to it
  (`docs/configuration.md`).
- To excuse one check on one issue, the session asks for a waiver, which a
  person must approve (`docs/waivers.md`).

---

## Case 2 - A normal-sized new feature

> **Request:** "Add a saved-views feature to the dashboard - users can name a
> filter combination and recall it."

| Dimension | Value | Justification |
|---|---|---|
| Risk | `contained` | A broken saved view is bounded to the dashboard and recoverable. |
| Familiarity | `brownfield-mapped` | Scenarios already cover the dashboard's filters. |
| Size | `medium` | Several files and one or two design decisions, 1-3 days. |
| Goal | `delivery` | A well-understood feature. |

A `persistence` label might apply, but it is not a `G5` label (`auth`,
`payments`, `personal-data`, `migrations`). `RP-EVID-COMMON` matches and no
addition fires.

```text
  assessment      : {"risk": "contained", "familiarity": "brownfield-mapped", "size": "medium", "goal": "delivery"}
  evidence row    : RP-EVID-COMMON
  FINAL APPROACH  : delivery
  evidence owed   : request, scenarios, red-before-green, suite-green, correctness, governance, traceability, ship-approval
  policy rules fired:
    Every change owes the same evidence: the request, the scenarios, the red before the green, a green suite and the ship approval (RP-EVID-COMMON, evidence)
        - evidence owed: request, scenarios, red-before-green, suite-green, correctness, governance, traceability, ship-approval
  gate set        : verify.correctness, verify.governance, verify.traceability
```

**Record.** Three gates, all passed at ship, and one person's approval of
the change. The session writes the scenarios, the tests and the code.
`compass quick-fix finish` shows that the tests fail without the change and
pass with it, and passes the gates with typed evidence. One session builds
every part of the change (ADR-090). Most work matches this case.

---

## Case 3 - A payments-touching migration

> **Request:** "Migrate the stored card-token format - one column, a follow-up
> script, a read-path change."

| Dimension | Value | Justification |
|---|---|---|
| Risk | `critical` | A wrong migration can corrupt stored payment tokens, and does not roll back cleanly. |
| Familiarity | `brownfield-mapped` | The token storage and read path are mapped. |
| Size | `small` | One column, one script, one read-path change. |
| Goal | `delivery` | A contained migration. |

Size and risk are different dimensions, and assess scores each as it is.
Labels: `payments` and `migrations`, both `G5` labels.

`RP-EVID-COMMON` matches. The evidence owed, the rules fired and the gate
set are the same as in Case 1:

- **The common row** (`RP-EVID-COMMON`) gives the evidence every delivery
  issue owes.
- **Two approvals by a person.** `RP-EVID-SIGNOFF` (critical risk and the
  labels) adds `scenario-approval`. `G5` (the labels) adds `human-approval`.
- **No review is added.** A project that wants the architecture review on
  such a change adds the token `architecture` with `require_evidence` in
  `compass.yml` (`docs/configuration.md`).
- **One advisory strategy.** Below the gate set the CLI prints `RP-ADV-001`
  (`regression-baseline`): run the existing suite green before and after
  the change. It never blocks.

`governance-check` checks the strategy in `governance/strategies.md` that a
migration is reversible or has a written, tested rollback. A team that makes
it a project check (`project_checks` in `compass.yml`) makes it block.

**Record.** The manifest's `policy_rules_fired` list records the row, the
two additions and their rationales. Critical risk with no `G5` label owes
the scenario approval and not the `G5` sign-off.

---

## Case 4 - A greenfield subsystem

> **Request:** "Build the notifications subsystem - email, in-app, and webhook
> delivery, with user preferences and a delivery log."

| Dimension | Value | Justification |
|---|---|---|
| Risk | `cross-cutting` | A delivery failure degrades many features. No data or money is lost, so not `critical`. |
| Familiarity | `greenfield` | Net-new code. |
| Size | `product` | Three channels, a preferences model and a delivery log. 2+ weeks. |
| Goal | `delivery` | A subsystem that serves a stated outcome. |

A `personal-data` label would add the sign-offs of Case 1. Assume here it
does not apply.

`RP-EVID-COMMON` matches and nothing else fires. The output is the same as
in Case 2, with the advisory strategy `RP-ADV-001` below the gate set. Size
adds no evidence: a two-week subsystem has more scenarios, not more stages.

**Record.**

- If the product owner stated an intent, specify writes its outcome into
  the Summary and Intent links of `acceptance-criteria.md`, and each
  scenario names the intent it serves.
- A designer's `ui-contract.md` becomes scenarios at specify.
- Neither document adds evidence (ADR-091).
- The session builds the five parts one after another (ADR-090).

---

## Case 5 - A production hotfix

> **Request:** "Checkout is returning 500s for any cart with a discount code -
> happening now."

A hotfix is not a delivery approach. It is the assessment switch `urgency:
live-defect`, given as `--urgency "live-defect - <reason>"` on `compass
quick-fix start` (`approaches/path.md`, "The hotfix setting").

| Dimension | Value | Justification |
|---|---|---|
| Risk | `cross-cutting` | Checkout is down for many users. No data is lost and the deploy rolls back cleanly, so not `critical`. |
| Familiarity | `brownfield-mapped` | The checkout and discount paths are mapped. |
| Size | `small` | The fix is expected to be 1-3 files. |
| Goal | `delivery` | Fixing a live defect. |
| Urgency | `live-defect` | User impact, happening now. |

`RP-EVID-COMMON` matches and no addition fires. The hotfix setting adds no
evidence, so the output is the same as in Case 2. The issue runs the same
four stages:

- **Specify** starts with the reproduction. The first scenario describes the
  defect, and its test reproduces the 500.
- **Build** writes that test and the fix. `compass quick-fix finish` runs the
  test on a copy of the commit the issue started from, where it must fail,
  and on the working tree, where it must pass (`docs/base-copy.md`).
- **Ship** passes three gates with typed evidence.

What adds an approval or a record:

- `critical` risk: `RP-EVID-SIGNOFF` adds `scenario-approval`.
- A `G5` label, such as `payments`: `scenario-approval` and
  `human-approval`, as in Case 1.
- A `require_evidence` setting that adds the token `reproduce-first` for
  live defects.

**Record.** The reproduction is a Given/When/Then scenario in
`acceptance-criteria.md` that names the defect. Record each follow-up the
fix owes with `compass follow-up add`, which links the GitHub issue that
tracks it (`--github`).

---

## Case 6 - An issue that cannot be framed yet

> **Request:** "Our background job queue is dropping ~2% of jobs under load and
> nobody knows why. Find out."

The request is a question, not a known change. There are no acceptance
criteria to state. That is the sign of the goal `exploration`.

| Dimension | Value | Justification |
|---|---|---|
| Risk | `contained` | The investigation touches nothing irreversible. |
| Familiarity | `brownfield-unmapped` | The queue's behavior under load is not written down. |
| Size | `small` | The investigation is timeboxed. The fix is not in scope. |
| Goal | `exploration` | The issue cannot be assessed for delivery yet. |

Goal `exploration` matches `RP-EVID-SPIKE`. A spike is not on the path: it
runs assess, build (explore) and ship (conclude), owes the one gate
`spike.conclude` and ships nothing.

```text
  assessment      : {"risk": "contained", "familiarity": "brownfield-unmapped", "size": "small", "goal": "exploration"}
  first approach  : spike  <- RP-SHAPE-001 (Exploration intent - cannot frame for delivery yet.)
  FINAL APPROACH  : spike
  policy rules fired: none
  per-stage weight:
    assess     : lightweight
    build      : explore
    ship       : graduate-or-discard
  gate set        : spike.conclude
```

- Below the gate set the CLI prints the advisory strategy `RP-ADV-002`
  (`atdd`): on unmapped ground, pin what the code does now before changing
  it.
- Assess records the question and a timebox, and writes a `.spike` marker in
  the issue directory.
- In build the engineer instruments and reproduces freely. The TDD strategy
  is suspended (`S2`).

### The refusal

Assess refuses a spike that touches `auth`, `payments`, `personal-data` or
`migrations`, or whose risk is `critical`:

```text
compass: routing conflict - exploration cannot silently become delivery.
  Intent is 'exploration' (a spike), but the assessment names critical risk or a `G5` label, where a change owes a person's sign-off.
  A spike ships nothing and must not touch production-critical surface.
  Re-assess: either scope a narrower discovery issue that does not touch the risky surface, or set intent=delivery and accept the evidence that change owes.
```

### Record - and the exit

Ship becomes conclude. The one gate is "the question is answered (or
answered with 'inconclusive - here is why'), and the finding is written
down." Then:

- **Graduate.** The spike found the cause. The finding feeds a new
  `/compass:assess` for the fix, a normal delivery issue on the path. Any
  diagnostic code carried over owes that issue's evidence.
- **Discard.** The spike concluded "not our code" or "inconclusive within
  the timebox". The finding is recorded, any follow-up is filed, and the
  spike closes.

Nothing lands from the spike itself. The only way from spike code to `main`
is a delivery issue on the path. See `approaches/spike.md`.

---

## The same request, four outcomes

One request, "add a CSV export", assessed four ways. Compass computes the
evidence from the assessment, not from the words.

### "Add a CSV export" - engineer, internal admin tool

Size `small`, risk `contained`, familiarity `brownfield-mapped`, goal
`delivery`, no labels. The common row (`RP-EVID-COMMON`) matches with
nothing added: one scenario, a test that fails without the change and
passes with it, a green suite, three gates and one person's approval of the
change.

### "Add a CSV export" - product owner, "let finance self-serve"

The product owner's intent is "let finance self-serve their month-end
numbers". Assess reads the goal as the outcome wanted, so size is `medium`
or larger. The evidence row and the gates are the same. The set of
scenarios grows. Specify writes the outcome into the Intent links of
`acceptance-criteria.md`, and each scenario names the intent it serves.

### "Add a CSV export" - engineer, export of the payments ledger

Assess labels it `payments` and `personal-data`. Whatever the size, the
`G5` labels fire the additions of Case 1: a person approves the scenarios
before any code edit, and a person signs the change off before it ships.

### "Add a CSV export" - product marketer, a launch feature

The engineering work matches the common row, and `positioning.md` adds no
gate (ADR-091). The marketer adds claims, such as "export your data in one
click". `claim-traces-to-scenario` checks each claim in the manifest's
`claims:` list, and shipping is blocked until every one traces to a passing
scenario.

---

## Reassessment - when the assessment was misread

When a scored value turns out wrong, re-assess: score the dimensions again
and run `compass approach evaluate --write --reason "..."`. It:

- recomputes `evidence_required`, the gates and the checkpoints;
- keeps the state of any gate the issue already held;
- appends an entry to the manifest's `reassessments` log: what changed (the
  assessment, the evidence owed, the gates, the rules that fired), the date
  and the `--reason`. A reassess that changes nothing records an entry of
  kind `unchanged`.

Two values change the evidence of a delivery issue: a `G5` label and
`critical` risk. A new size, familiarity or urgency corrects the record and
changes no evidence. The triggers:

- **Build shows the risk was read too low.** The session stops and says so.
  `critical` risk owes a person's approval of the scenarios.
- **Build shows the size was read too low.** The session says so, and the
  assessment is corrected.
- **A label surfaces late.** The change reaches auth after all. The `G5`
  additions fire, and that is recorded.
- **A decision changes scope.** If the decision touches the assessment,
  re-assess.

An issue assessed before 9.0.0 moves onto the path the same way. The command
writes the path keys and logs the old approach in `reassessments`
(`from_route: regular`, `to_route: delivery`).

After a re-assess, the next session runs `compass approach show` and
`compass next` to see where the issue stands.

---

## What the routing system is really for

Every case ends in an evidence list in the manifest, with the rule behind
each item, that a person can read and a later session can resume from.
Three things bound what assess can decide:

- the three-dimension rubric;
- the evidence rows fixed in code;
- the policy in force: the fixed check set with the tighten-only settings of
  the project's `compass.yml`, which `compass policy show` prints with its
  digest.

A project that owes more changes `compass.yml` (`docs/configuration.md`),
reviewed like any other change.
