# Compass - Routing Deep Dive

`approaches/rubric.md` is the assess stage's rubric: the three scored
dimensions, the scoring tables and the procedure. This page applies the
rubric to six issues. It takes each one through scoring, the evidence row,
the additions and the record in the manifest, so that the claim "Compass
computes what each change owes" is something you can watch happen.

Every delivery issue runs the same four stages: assess, specify, build and
ship (`approaches/path.md`). The stages do not change from one issue to the
next. What changes is the evidence the change owes before it ships, and
assess selects that evidence. From 9.0.0 assess no longer picks a delivery
approach such as quick fix, regular, full or hotfix; it computes the
`evidence_required` list.

---

## The shape of every assessment decision

Every issue, every time, assess runs the same four steps:

1. **Score the three dimensions** - risk, familiarity and size - and read
   the optional switches, goal and urgency, each with a one-line written
   justification. `compass quick-fix start` takes each dimension as an
   option. A dimension left out is recorded as `contained` risk,
   `brownfield-mapped` familiarity or `small` size, with the reason "not
   rated at start".
2. **Match the evidence row.** `cli/compass_pkg/evidence_required.py` reads
   the rows in order, and the first that matches wins:
   - `RP-EVID-SPIKE`: goal `exploration`. The issue is a spike, which is not
     on the path and ships nothing.
   - `RP-EVID-COMMON`: every other assessment. Every delivery issue owes the
     same evidence. Risk, size, familiarity and urgency add no review and no
     record.
3. **Apply the additions and the configuration.** On the delivery row, each
   addition is an approval a person gives:
   - `RP-EVID-SIGNOFF` adds `scenario-approval` for a `G5` label or critical
     risk: a person approves the scenarios before any code edit;
   - `G5` adds `human-approval` for a `G5` label: a person signs the change
     off before it ships.

   The policy in force then adds the gate of each floor of the project's own
   that matches (`add_gate`), the evidence of each `require_evidence` setting
   of `compass.yml` that matches (`RP-SETTING-<n>`), each gate it holds
   immovable, and the skill a floor asks for (`require_skill`). The
   shipped check set holds no floor that adds a gate. The records of the four-layer
   acceptance strategy (`S17`), `outer-loop`, `isolation` and `layering`,
   are owed only where a `require_evidence` setting adds them. Every rule
   that fires is recorded with its rationale. Which documents the issue
   holds is not an input: Compass needs only `acceptance-criteria.md`
   (ADR-091).
4. **Record the evidence.** `compass quick-fix start` does this when it opens
   the issue, and `compass approach evaluate --write` does it again on a
   re-assess. Each writes `delivery_approach: delivery`, `evidence_required`,
   the gates derived from it, the checkpoints and the rules that fired into
   `manifest.yml`. `compass approach show` prints the result in three lines.

The `G5` labels are `auth`, `payments`, `personal-data` and `migrations`,
and any label a project adds with `signoff_labels`.
The every-issue evidence is `request` (who asked, and a link to the
request, ADR-096), `scenarios`, `red-before-green`, `suite-green`, three
review gates and `ship-approval`, a person's approval of the change at ship
(ADR-095). The immovable gates (`verify.correctness`,
`verify.governance`, `verify.traceability`) are those three: no
configuration removes them. `compass quick-fix finish` passes them itself,
from the test records and the output of `compass check` (ADR-099). The
exact conditions are in `governance/routing-policy.md`, "The evidence rows".

The transcripts below are real output of `compass approach evaluate
--verbose --assessment ...`. Each starts at the `assessment` line, because
the `policy` line above it names the configuration on your machine. Each
ends at the `gate set` line: the advisory strategies printed below it are
named in the text instead.

What follows is six cases. Read them in order; they build on each other.

---

## Case 1 - A typo fix in an auth module

> **Request:** "Fix the typo in the JWT refresh error message."

### Score

| Dimension | Value | Justification |
|---|---|---|
| Risk | `trivial` | The wrong outcome is a misspelt word in an error string - cosmetic, instantly obvious, instantly reversible. No data, no money, no auth *behavior* touched. |
| Familiarity | `brownfield-mapped` | Existing code; the error path is easy to read. |
| Size | `atomic` | One file, one string, no design decision, well under thirty minutes. |
| Goal | `delivery` | A known change to shipped code; nothing needs exploring first. |

Assess also assigns labels. The change is *in* the JWT module, so it labels
it `auth`, because the label is about where the change lives, not how risky
it looks.

### The row

Every delivery assessment matches `RP-EVID-COMMON`. Atomic size and trivial
risk change nothing: the row is the same for every size and risk.

### The additions

The `auth` label fires two additions:

- `RP-EVID-SIGNOFF` adds `scenario-approval`: a person approves the
  scenarios before any code edit;
- `G5` adds `human-approval`: a person signs the change off before it ships.

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

This is the most important thing the routing does: *a one-character change
to an auth error message owes the most approvals there are.* Not because the
change is large - it is atomic - but because the risk of the auth module is
not a function of line count. A label is domain knowledge that overrides the
raw dimension scores.

### Record

Three gates, all passed at ship, a person's approval of the scenarios before
the first code edit, and a person's sign-off before the change lands. Until
the scenarios are approved, the pre-tool hook refuses a code edit with the
code `code-before-approval`.
The manifest's `policy_rules_fired` list records the three rules, each with
its rationale. The engineer sees *why* a typo fix owes a person's sign-off.
They can discuss it, but they cannot have the evidence silently reduced. The
rows and additions are fixed in code, and the `G5` sign-off is a guardrail.
A project cannot remove a rule: every project runs one fixed check set, and
a setting in `compass.yml` can only add to it (`docs/configuration.md`). To
excuse one check on one issue, the session asks for a waiver, which a person
must approve (`docs/waivers.md`). That is a recorded and reviewed act, not
an edit mid-issue.

---

## Case 2 - A normal-sized new feature

> **Request:** "Add a saved-views feature to the dashboard - users can name a
> filter combination and recall it."

### Score

| Dimension | Value | Justification |
|---|---|---|
| Risk | `contained` | A broken saved view is annoying and bounded to the dashboard; recoverable, no data loss, no other surface affected. |
| Familiarity | `brownfield-mapped` | The dashboard's filter behavior is already captured in scenarios. |
| Size | `medium` | Several files - a persistence layer, the filter serialization, the UI - and one or two design decisions, 1-3 days. |
| Goal | `delivery` | A well-understood feature is being built. |

Labels: `persistence` might apply, but it is not a `G5` label (`auth`,
`payments`, `personal-data`, `migrations`).

### The row

`RP-EVID-COMMON` matches, as it does for every delivery assessment. No
addition fires: risk is only `contained`, and there is no `G5` label.

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

### Record

Three gates, all passed at ship, and one person's approval of the change.
The session writes the scenarios, the tests and the code, and
`compass quick-fix finish` writes the record: it shows that the tests fail
without the change and pass with it, and passes the gates with typed
evidence. One session builds every part of the change, one after another
(ADR-090).

This is the plain case, and the plain case matters: most work matches the
common row with nothing added, and it should feel like the normal way to
work, not extra process.

---

## Case 3 - A payments-touching migration

> **Request:** "Migrate the stored card-token format - one column, a follow-up
> script, a read-path change."

### Score

| Dimension | Value | Justification |
|---|---|---|
| Risk | `critical` | A wrong migration can corrupt stored payment tokens - data loss, money, and a path that does not cleanly roll back. |
| Familiarity | `brownfield-mapped` | The token storage and read path are mapped. |
| Size | `small` | One column, one follow-up script, one read-path change. 1-3 files, a known pattern. |
| Goal | `delivery` | A contained migration. |

This is the case the methodology opens with: *a migration that touches one
file is small but not safe.* Size and risk are different axes, and here they
point in opposite directions. Assess scores them as they are - size `small`,
risk `critical` - and does not let one hide the other. Labels: `payments`
and `migrations`, both `G5` labels.

### The row

`RP-EVID-COMMON` matches. Neither the size nor the risk changes the row.

### The additions

`compass approach evaluate --verbose` lists the rules that fired, in this
order:

```text
  assessment      : {"risk": "critical", "familiarity": "brownfield-mapped", "size": "small", "goal": "delivery", "urgency": "none", "labels": ["payments", "migrations"]}
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

- **The common row** (`RP-EVID-COMMON`) gives the evidence every delivery
  issue owes.
- **Two approvals by a person.** `RP-EVID-SIGNOFF` (critical risk and the
  labels) adds `scenario-approval`, so a person approves the scenarios
  before any code edit. `G5` (the labels) adds `human-approval`, so a
  person signs the change off before it ships.
- **No review is added.** Critical risk and the labels add no review gate.
  A project that wants the architecture review on such a change adds the
  token `architecture` with `require_evidence` in `compass.yml`
  (`docs/configuration.md`).
- **One advisory strategy.** Below the gate set the CLI prints `RP-ADV-001`
  (`regression-baseline`): run the existing suite green before and after the
  change. It is advice, assessed by the reviewer, and never blocks.

`governance-check` checks an engineering strategy in
`governance/strategies.md` (migrations are reversible or come with a
written, tested rollback) - the evidence row does not waive it. If the team
has made that a project check (`project_checks` in `compass.yml`), it is
checked as a check and blocks.

### Record

The manifest's `policy_rules_fired` list records the row, the two additions
and their rationales. The evidence is the same as in Case 1: a typo with an
`auth` label and a critical migration owe the same gates and the same two
approvals. Critical risk with no `G5` label owes the scenario approval and
not the `G5` sign-off.

---

## Case 4 - A greenfield subsystem

> **Request:** "Build the notifications subsystem - email, in-app, and webhook
> delivery, with user preferences and a delivery log."

### Score

| Dimension | Value | Justification |
|---|---|---|
| Risk | `cross-cutting` | Notifications touch many features; a delivery failure degrades something many users see. Recovery needs coordination, but it is not data loss or money - not `critical`. |
| Familiarity | `greenfield` | Net-new code; no existing behavior to preserve. |
| Size | `product` | A new subsystem - three delivery channels, a preferences model, a delivery log. 2+ weeks. |
| Goal | `delivery` | A subsystem that serves a stated outcome. A designer and a product owner may well be consulted (preferences are a user-facing surface). |

Labels: `personal-data` could apply if the preferences or the delivery log
store anything personal. Assess labels the change as it is, and that label
would add the sign-offs of Case 1; assume here it does not.

### The row and the additions

`RP-EVID-COMMON` matches. Nothing else fires: risk is not `critical` and
there is no `G5` label, so there is no scenario approval and no sign-off.

```text
  assessment      : {"risk": "cross-cutting", "familiarity": "greenfield", "size": "product", "goal": "delivery"}
  evidence row    : RP-EVID-COMMON
  FINAL APPROACH  : delivery
  evidence owed   : request, scenarios, red-before-green, suite-green, correctness, governance, traceability, ship-approval
  policy rules fired:
    Every change owes the same evidence: the request, the scenarios, the red before the green, a green suite and the ship approval (RP-EVID-COMMON, evidence)
        - evidence owed: request, scenarios, red-before-green, suite-green, correctness, governance, traceability, ship-approval
  gate set        : verify.correctness, verify.governance, verify.traceability
```

This is the key contrast with Case 3. Both owe the same three gates. Case 3
also owes two of a person's approvals, because of its risk and labels. Size
adds no evidence: a two-week subsystem and a one-column migration go through
the same four stages, and the large one has more scenarios, not more stages.
Below the gate set the CLI prints the advisory strategy `RP-ADV-001`, as in
Case 3.

### Record

If the product owner stated an intent, specify writes its outcome into the
Summary and Intent links of `acceptance-criteria.md`, and each scenario
names the intent it serves. The designer's `ui-contract.md` would flow into
specify as scenarios. Neither document adds evidence: no document on disk is
a routing input (ADR-091). The session builds the five parts - email,
in-app, webhook, preferences and the delivery log - one after another
(ADR-090).

---

## Case 5 - A production hotfix

> **Request:** "Checkout is returning 500s for any cart with a discount code -
> happening now."

### Score

A hotfix is not a delivery approach. It is the assessment switch `urgency:
live-defect`, given as `--urgency "live-defect - <reason>"` on `compass
quick-fix start` (`approaches/path.md`, "The hotfix setting"). Assess still
scores all three dimensions, because they decide the row.

| Dimension | Value | Justification |
|---|---|---|
| Risk | `cross-cutting` | Checkout is down for every cart with a discount code - many users affected, and recovery needs coordination with the payments team. No data is lost, no money is misrouted, and the deploy can be rolled back cleanly, so it stops short of `critical`. |
| Familiarity | `brownfield-mapped` | The checkout and discount paths are mapped. |
| Size | `small` | The defect is bounded; the fix is expected to be 1-3 files once the cause is found. |
| Goal | `delivery` | Fixing a live defect. |
| Urgency | `live-defect` | User impact, happening now. |

### The row and the additions

`RP-EVID-COMMON` matches, and no addition fires. The hotfix setting adds no
evidence: a live defect owes what every delivery issue owes.

```text
  assessment      : {"risk": "cross-cutting", "familiarity": "brownfield-mapped", "size": "small", "goal": "delivery", "urgency": "live-defect"}
  evidence row    : RP-EVID-COMMON
  FINAL APPROACH  : delivery
  evidence owed   : request, scenarios, red-before-green, suite-green, correctness, governance, traceability, ship-approval
  policy rules fired:
    Every change owes the same evidence: the request, the scenarios, the red before the green, a green suite and the ship approval (RP-EVID-COMMON, evidence)
        - evidence owed: request, scenarios, red-before-green, suite-green, correctness, governance, traceability, ship-approval
  gate set        : verify.correctness, verify.governance, verify.traceability
```

The issue runs the same four stages as any other:

- **Specify** starts with the reproduction. The first scenario describes the
  defect, and its test reproduces the 500.
- **Build** writes that test and the fix. `compass quick-fix finish` runs the
  test on a copy of the commit the issue started from, where it must fail,
  and on the working tree, where it must pass. That shows the test fails
  without the fix (`docs/base-copy.md`).
- **Ship** passes three gates with typed evidence, the same as any other
  issue.

Two changes to the assessment add an approval:

- With `critical` risk - say the discount path also double-charged a card -
  `RP-EVID-SIGNOFF` adds `scenario-approval`.
- With a `G5` label, such as `payments`, the change owes `scenario-approval`
  and `human-approval`, as in Case 1.

A project that wants the reproduction recorded before anything else adds the
token `reproduce-first` for live defects with `require_evidence`.

### Record

The reproduction is a real Given/When/Then scenario in
`acceptance-criteria.md` that names the defect. Each follow-up the fix owes
is recorded with `compass follow-up add`, which links the GitHub issue that
tracks it (`--github`): name the root cause, and file the
missing scenario that would have caught the defect as a follow-up issue
where one is owed.

---

## Case 6 - An issue that cannot be framed yet

> **Request:** "Our background job queue is dropping ~2% of jobs under load and
> nobody knows why. Find out."

### Score

Assess still scores all three dimensions, but this request is not a known
change; it is a *question*. There are no acceptance criteria to state,
because the behavior to fix is the unknown. That is the signal for
**exploration** as the goal.

| Dimension | Value | Justification |
|---|---|---|
| Risk | `contained` | The investigation itself touches nothing irreversible - reading logs, adding instrumentation behind a flag, reproducing in a sandbox. |
| Familiarity | `brownfield-unmapped` | The queue's behavior under load is exactly what is *not* written down. |
| Size | `small` | The investigation is timeboxed; the eventual fix is unknown and not in scope here. |
| Goal | `exploration` | "I need to understand this before I can assess it" - not a delivery request. |

### The row

Goal `exploration` matches `RP-EVID-SPIKE`. A spike is the one issue that is
not on the path: it runs assess, build (explore) and ship (conclude), owes
the one gate `spike.conclude` and ships nothing.

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

A spike keeps its stage map, so the output shows a weight for each of its
three stages. Below the gate set the CLI prints the advisory strategy
`RP-ADV-002` (`atdd`): on unmapped ground, pin what the code
does now before changing it. Assess records the **question** ("what is dropping ~2% of jobs
under load?") and a **timebox**. Build becomes **exploration**: the engineer
instruments and reproduces freely, and the TDD strategy is suspended (`S2`):
red-before-green is the wrong discipline for throwaway diagnostic code.
Assess writes a `.spike` marker in the issue directory.

### The refusal

If the question could only be answered by touching `auth`, `payments`,
`personal-data` or `migrations`, or the risk is `critical`, assess refuses
the spike:

```text
compass: routing conflict - exploration cannot silently become delivery.
  Intent is 'exploration' (a spike), but the assessment names critical risk or a `G5` label, where a change owes a person's sign-off.
  A spike ships nothing and must not touch production-critical surface.
  Re-assess: either scope a narrower discovery issue that does not touch the risky surface, or set intent=delivery and accept the evidence that change owes.
```

Here the investigation stays clear of those surfaces, so the spike stands.

### Record - and the exit

Ship becomes **conclude**: not a test gate, a findings check - *was the
question answered?* The one gate is "the question is answered (or answered
with 'inconclusive - here is why'), and the finding is written down." Then
**graduate or discard**:

- **Graduate** - the spike found the cause (say, a connection-pool
  exhaustion under a specific retry storm). The finding feeds a fresh
  `/compass:assess` for the real fix. That assessment is a normal delivery
  issue on the path, and the tested-before-ship, acceptance-before-code and
  traceability guardrails apply to the fix in full. Any diagnostic code
  carried over now owes that issue's evidence; in practice most is rewritten
  under TDD.
- **Discard** - the spike concluded "this is environmental, not our code"
  or "inconclusive within the timebox." The finding is recorded, any
  follow-up is filed, and the spike closes. A discarded spike with a clear
  answer succeeded.

Nothing lands from the spike itself. That is the whole safety model: the
TDD strategy is suspended *because* there is no delivery output to protect.
The only way from spike code to `main` is a delivery issue on the path. See
`approaches/spike.md`.

---

## The same request, four outcomes

The cases above are six different requests. Here is one *literal* request -
**"add a CSV export"** - taken four ways, because who asks and what it
touches changes what the change owes. This shows that Compass computes the
evidence from the *assessment*, not the words.

### "Add a CSV export" - engineer, internal admin tool

Size `small`, risk `contained` (an admin tool, bounded), familiarity
`brownfield-mapped`, goal `delivery`, no labels. This matches the common row
(`RP-EVID-COMMON`) with nothing added: one scenario ("given a filtered
table, when the user exports, then a CSV with those rows downloads"), a test
that fails without the change and passes with it, a green suite, three gates
and one person's approval of the change. Done in an afternoon. Assess stays
out of the way, as it should.

### "Add a CSV export" - product owner, "let finance self-serve"

Same three words, but a product owner's intent sits behind them, and its
outcome is "let finance self-serve their month-end numbers." Assess reads
the goal as the *actual outcome wanted*, not the literal request, and
"self-serve" implies filters that match what finance actually needs,
perhaps scheduling, perhaps permissions. Size is no longer `small`; it is
`medium` or larger. The evidence row is the same, and so are the gates.
What grows is the set of scenarios. Specify writes the outcome
into the Intent links of `acceptance-criteria.md`, and each scenario names
the intent it serves, so the person reading the scenarios can check they
deliver "self-serve" and not just "a button that produces a file". Same
words, more scenarios, because the goal under them is bigger.

### "Add a CSV export" - engineer, export of the payments ledger

Same three words again, but the table is the payments ledger. Assess labels
it `payments` and `personal-data`. Size might still be `small`. It does not
matter: the `G5` labels fire the additions of Case 1, `scenario-approval`
and `human-approval`. Specify
asks what exactly is in this export and what must *not* be, a person
approves the scenarios before any code edit, and a person signs the change
off before it ships. A small feature that owes the most approvals there
are, because of what it touches.

### "Add a CSV export" - product marketer, a launch feature

A marketer works with the team on an export feature being
launched. The engineering work matches the common row, and the evidence
is computed from the assessment alone: `positioning.md` adds no gate
(ADR-091). What the marketer adds is claims ("export your data in one
click", "works with spreadsheets you already use"). Each claim the
manifest's `claims:` list holds is checked by `claim-traces-to-scenario`,
and **shipping is blocked** until every one traces to a passing scenario.
Same three words; a check that had nothing to read in the other three
cases.

Four outcomes, one request. The request did not change. The assessment did,
and Compass computes the evidence from the assessment.

---

## Reassessment - when the assessment was misread

The evidence is computed at assess, but a value can turn out wrong. The
right response is not to push on with evidence you no longer believe fits.

A re-assess scores the dimensions again and runs
`compass approach evaluate --write --reason "..."`. That recomputes
`evidence_required`, the gates and the checkpoints, keeps the state of any
gate the issue already held, and appends an entry to the manifest's
`reassessments` log: what changed (the assessment, the evidence owed, the
gates, the rules that fired), the date and the `--reason`. A reassess that
changes nothing records its `--reason` too, as an entry of kind `unchanged`.
A re-assess is a normal event, not a failure. *Evidence that the work has
quietly outgrown is the failure.*

Two values change the evidence of a delivery issue: a `G5` label and
`critical` risk. A new size, familiarity or urgency corrects the record of
the assessment and changes no evidence. The triggers are concrete:

- **Build shows the risk was read too low.** A "contained" change turns out
  to be able to lose data. The session stops and says so, and assess scores
  it again: `critical` risk owes a person's approval of the scenarios.
- **Build shows the size was read too low.** A "small" change is turning
  into a multi-module refactor. The session says so and the assessment is
  corrected, so the record states the work as it was.
- **A label surfaces late.** Mid-build you find the change reaches auth
  after all. Re-assess: the `G5` additions fire, the change owes a person's
  approval of its scenarios and a person's sign-off, and that is recorded,
  not silent.
- **A decision changes scope.** The team decides to cut or expand scope; if
  the decision touches the assessment, follow it with a re-assess.

An issue assessed before 9.0.0 moves onto the path the same way:
`compass approach evaluate --write --reason "..."` writes the path keys and
logs the old approach in `reassessments` (`from_route: regular`,
`to_route: delivery`).

The reassessed evidence in the manifest is the contract again: the next
session runs `compass approach show` and `compass next` and knows exactly
where the issue stands.

---

## What the routing system is really for

Every case above ends in an evidence list recorded in the manifest, with
the rule behind each item, that a person can read and a later session can
resume from. That is the deliverable. Assess does not just classify the
issue: it explains the classification and records every rule that fired.
The adaptivity is real, and it is *bounded*: by the three-dimension rubric,
by the evidence rows fixed in code, and by the policy in force (the fixed
check set with the tighten-only settings of the project's `compass.yml`,
which `compass policy show` prints with its digest). A project that owes
more changes `compass.yml` (`docs/configuration.md`), reviewed like any other
change. That is what
keeps "adaptive" from becoming arbitrary.
