# Compass - Routing Deep Dive

`approaches/rubric.md` is the assess stage's rubric: the four dimensions, the
scoring tables, the four-step procedure. This page applies the rubric to six
issues, walking each one through scoring, composition, policy-rule
constraint, and the final `delivery-approach.md` - so that the claim
"Compass computes the process per issue" stops being an assertion and
becomes something you can watch happen.

---

## The shape of every assessment decision

Every issue, every time, the assess stage runs the same four steps:

1. **Score the four dimensions** - risk, familiarity, size, goal and
   role - each with a one-line written justification. If a value cannot be
   justified, the assess stage asks rather than guesses.
2. **Compose the candidate delivery approach** - assemble per-stage weight
   from the dimension contributions, biased by the routing strategies, name
   the reference shape for shared vocabulary, list any deviations.
3. **Constrain with the routing policy rules** - floors raise the candidate,
   caps limit it, immovable gates are always added, blocking role rules add
   artifacts and blocks. Every rule that fires is recorded with its
   rationale.
4. **Write `delivery-approach.md` and confirm** - including the de-scope ledger, where
   every collapsed or skipped stage carries an explicit "safe to skip
   because…" line.

The five reference shapes - quick fix, regular, full, hotfix, spike - are
not a menu. They are the common shapes the composition lands near. A perfectly
normal output is "regular, but verify also runs the `security` dimension" -
that is the framework working, not an exception.

What follows is six cases. Read them in order; they build on each other.

---

## Case 1 - A typo fix in an auth module

> **Request:** "Fix the typo in the JWT refresh error message."

### Score

| Dimension | Value | Justification |
|---|---|---|
| risk | `trivial` | The wrong outcome is a misspelt word in an error string - cosmetic, instantly obvious, instantly reversible. No data, no money, no auth *behaviour* touched. |
| Familiarity | `brownfield-mapped` | Existing code; the error path is trivially readable. |
| Size | `atomic` | One file, one string, no design decision, well under thirty minutes. |
| Goal and role | `engineer` | Feature pipeline ownership; no intent document, no other role. |

Assess also assigns domain tags. The change is *in* the JWT module, so it
tags `labels: [auth]` - honestly, because the tag is about where the change
lives, not how scary it looks.

### Compose

Atomic size, trivial risk, mapped familiarity, engineer role. This is
the textbook quick fix case. The candidate delivery approach is **quick
fix**: one scenario, the requirements review collapsed, plan collapsed to a
one-liner, breakdown skipped, full TDD on a tiny surface, three gates at
verify.

### Constrain

Now the routing policy rules run. The floor `when: { labels: [auth] }` matches
the `labels: [auth]` tag, and its action is `force_minimum_route: full`.
The candidate quick fix is raised to **full**.

This is the single most important thing the routing system does, so it is
worth stating plainly: *a one-character change to an auth error message gets
the full approach.* Not because the change is large - it is
atomic - but because the risk of the auth module is not a function of
line count. A floor is domain knowledge overriding the raw dimension assessment.

### Final `delivery-approach.md`

The delivery approach is the full approach. The policy-rules section of
`delivery-approach.md` records:

> **floor** · `labels: [auth]` · Candidate delivery approach quick fix was
> raised to the full approach · *"Domain risk overrides size. A one-line auth
> change is not small."*

The engineer sees *why* a typo fix got the full approach. Because the
delivery approach is advisory until confirmed, they can discuss it - but they
cannot have it silently routed light. A floor is a rule in
`governance/routing-policy.yml`; overriding it would mean amending that
file, not overriding a delivery approach.

In practice the team might decide the policy is too blunt and narrow the floor
(`labels: [auth]` only when the change is to auth *logic*, not auth-adjacent
strings). That is a legitimate, logged amendment to
`governance/routing-policy.yml` - not a convenience edit mid-issue. Until then,
the typo fix runs the full approach, and that is the system being conservative on
purpose.

---

## Case 2 - A normal-sized new feature

> **Request:** "Add a saved-views feature to the dashboard - users can name a
> filter combination and recall it."

### Score

| Dimension | Value | Justification |
|---|---|---|
| risk | `contained` | A broken saved-view is annoying and bounded to the dashboard; recoverable, no data loss, no other surface affected. |
| Familiarity | `brownfield-mapped` | The dashboard's filter behaviour is already captured in scenarios. |
| Size | `medium` | Several files - a persistence layer, the filter serialisation, the UI - and one or two design decisions, 1–3 days. |
| Goal and role | `engineer` | No intent document; an engineer is implementing a well-understood feature. |

Domain tags: `labels: [persistence]` might carry, but nothing on the
policy's floor list (`auth`, `payments`, `personal-data`, `migrations`,
`public-api`).

### Compose

Standard size, contained risk, mapped familiarity. The candidate is
**regular**, plainly: a small feature set of scenarios, a light-to-full
requirements review pass, a real `technical-design.md` with the design decisions recorded, solo or
pair orchestration, six gates at verify. No deviation from the reference shape is
warranted - risk is only `contained`, so `security` stays scaled
rather than full and `clarity` and `regression` are on as the regular approach
always has them.

### Constrain

No floor matches - no domain tag on the floor list, risk is not
`critical`, familiarity is mapped. No cap is relevant. The immovable gates
(`verify.correctness`, `verify.governance`, `verify.traceability`) are
always added. `verify.regression` is in this approach's own gate set rather
than added separately - it is approach-scoped, and a quick fix does not run it, which
is the point of a quick fix. `verify.claims` is role-scoped and does not
appear at all here, because no marketer is involved. No `role_rules` fire -
only an engineer.

### Final `delivery-approach.md`

The policy-rules section reads, in full:

> No routing policy rule fired. Candidate delivery approach stands.

That line is itself the record - silence is not allowed; "nothing fired" is
written down. The delivery approach is regular, unmodified. The de-scope
ledger is short: the dedicated orchestrator agent is skipped (≤3 subtasks,
the lead builder integrates) and the full distribution map is reduced to a
short list. Both carry their standing justifications.

This is the boring case, and the boring case matters: most work is on the regular
approach, and it should feel like the default working shape, not
extra process.

---

## Case 3 - A payments-touching migration

> **Request:** "Migrate the stored card-token format - one column, a follow-up
> script, a read-path change."

### Score

| Dimension | Value | Justification |
|---|---|---|
| risk | `critical` | A wrong migration can corrupt stored payment tokens - data loss, money, and a path that does not cleanly roll back. |
| Familiarity | `brownfield-mapped` | The token storage and read path are mapped. |
| Size | `small` | Honestly: one column, one follow-up script, one read-path change. 1–3 files, a known pattern. |
| Goal and role | `engineer` | An engineer running a contained migration. |

This is the case the methodology opens with: *a migration that touches one
file is small but not safe.* Size and risk are different axes, and
here they point in opposite directions. Assess scores them honestly -
size `small`, risk `critical` - and does not let one hide the
other. Domain tags: `labels: [payments, migrations]` - two tags, both on the
floor list.

### Compose

If size alone drove the delivery approach, this would compose towards quick
fix or a light regular approach - `small` on mapped familiarity. Assess composes the
candidate from *all four* contributions, and `critical` risk dominates: full
test surface including adversarial and boundary inputs, the rollback path
exercised, every review dimension. The candidate already composes heavy -
towards **full** - on risk alone.

### Constrain

Two floors fire, and they reinforce each other:

- `when: { risk: critical }` → `force_minimum_route: full`,
  `never_skip: [refine, verify, ship]`. *"Critical changes coordinate or they
  break things quietly."*
- `when: { labels: [payments, migrations] }` → `force_minimum_route:
  full`. *"Domain risk overrides size."*

Then a **cap** fires - and this is the subtle part. `when: { risk:
critical }` → `max_worktrees: 1`. So this is the full approach
that is *capped to a single worktree*. It is heavy - full BDD discovery, full
requirements review, a full `technical-design.md`, every gate - and
**solo**. That is not a contradiction. The cap encodes a real trade-off:
parallelism is speed, but a multiagent orchestration has coordination risk,
and on a critical change the coordination risk costs more than the speed
saves.

`governance-check` checks an engineering strategy in `governance/strategies.md`
(migrations are reversible or come with a written, tested rollback) during
the plan stage - the delivery approach does not waive it. (If the team has
hardened that into a project guardrail, it is checked as a guardrail and
blocks.)

### Final `delivery-approach.md`

The delivery approach is the full approach, single worktree. The policy-rules
section records both floors and the cap, each with its rationale. The
orchestration section (§4c of the template) records the worktree count as
**cap-driven** - not as a de-scope.
This distinction matters: the de-scope ledger is for things the delivery
approach *chose* to skip; a cap removing a worktree is a routing policy rule,
and rule-driven reductions go in the orchestration section, never the
ledger. The full approach's de-scope ledger is empty by definition, and a
capped full approach is still the full approach.

A `distribution-map.md` is still written, even though the work runs solo. The
map is the record of *what could have been parallel and why it wasn't* - here,
"it wasn't, because the critical-risk cap pinned it to one worktree."

---

## Case 4 - A greenfield subsystem

> **Request:** "Build the notifications subsystem - email, in-app, and webhook
> delivery, with user preferences and a delivery log."

### Score

| Dimension | Value | Justification |
|---|---|---|
| risk | `cross-cutting` | Notifications touch many features; a delivery failure degrades something many users see. Recovery needs coordination, but it is not data-loss or money - not `critical`. |
| Familiarity | `greenfield` | Net-new code; no existing behaviour to preserve. |
| Size | `product` | A new subsystem - three delivery channels, a preferences model, a delivery log. 2+ weeks, many independent work subtasks. |
| Goal and role | `engineer` | An engineering lead, though a designer and a product owner may well join (preferences are a user-facing surface; the subsystem serves a stated outcome). |

Domain tags: `labels: [personal-data]` might carry if the preferences or
delivery log store anything personal - the assess stage tags honestly and
that tag would add a floor; assume here it does not.

### Compose

`product` size with `cross-cutting` risk and `greenfield` familiarity
is the textbook **full** case, and it composes there with no help from
the routing policy rules. Full BDD discovery from the intent document;
scenarios grouped by independence - email delivery, in-app delivery, webhook
delivery, preferences, the delivery log are plausibly disjoint surfaces; a
full `technical-design.md` plus a real `distribution-map.md`; a multiagent
orchestration across git worktrees, one `builder` per subtask, an
`orchestrator` that writes no feature code; all gates, all dimensions, plus
a per-worktree mid-delivery-approach checkpoint.

### Constrain

The `risk: critical` floor does *not* fire - this is `cross-cutting`,
not `critical`. So the critical-risk cap does *not* apply either: the
multiagent orchestration is not pinned to one worktree. Subtask count comes
from the distribution map, bounded by `max_worktrees` in `compass.yml`
(`.compass/config.yml` in a project without one; default 6). If the map identifies five independent
subtasks, the multiagent orchestration runs five worktrees.

This is the key contrast with Case 3: Case 3 was *heavy and
solo* (critical risk, capped); Case 4 is *heavy and parallel*
(cross-cutting risk, uncapped). Same full-approach reference shape,
genuinely different orchestration - because the dimensions read differently.

### Final `delivery-approach.md`

The delivery approach is the full approach at full weight, multiagent orchestration,
empty de-scope ledger (the full approach's
ledger is empty by definition - it is what the other approaches are measured
against). If a designer and product owner did join, their `role_rules` would
fire: `intent.md` required and the intent-fidelity gate before the plan
stage; the designer's `ui-contract.md` flowing into the define stage as
scenarios. Each would be recorded in the policy-rules section.

---

## Case 5 - A production hotfix

> **Request:** "Checkout is returning 500s for any cart with a discount code -
> happening now."

### Score

Assess still scores all four dimensions - they shape the mandatory
follow-up - but hotfix is the one delivery approach selected by *urgency*
rather than by the size / risk / familiarity composition.

| Dimension | Value | Justification |
|---|---|---|
| risk | `cross-cutting` | Checkout is down for every cart with a discount code - many users affected, and recovery needs coordination with the payments team. No data is lost, no money is misrouted, and the deploy can be rolled back cleanly, so it stops short of `critical`. |
| Familiarity | `brownfield-mapped` | The checkout and discount paths are mapped. |
| Size | `small` | The defect is bounded; the fix is expected to be 1–3 files once the cause is found. |
| Goal and role | `engineer`, often paired with `qa` | An engineer fixing a live defect, QA checking. |

### Compose

A live defect with user impact happening *now*, small size, cross-cutting
risk - the assess stage composes towards a **hotfix**. The shape, stage by
stage:

- **Assess** is fast but real - `delivery-approach.md` is written even
  under time pressure, and the audit trail starts here.
- **Define** is **reproduce-first**: the spec *is* a failing regression
  test that reproduces the 500, simultaneously the BDD scenario and the
  TDD red.
- **Requirements review** collapses - the reproduction *is* the
  clarification.
- **Plan** collapses to a one-line root-cause note.
- **Breakdown** is skipped.
- **Implement** is expedited.
- **Verify** runs **at full weight, not compressed**.
- **Ship** ships the fix and then needs the mandatory follow-up.

### Constrain

Risk here is `cross-cutting`, not `critical`. `RP-FLOOR-001` floors a
`critical` risk value to the full approach, and no delivery approach composes it as a
hotfix, however urgent the defect (`approaches/hotfix.md`). Had the discount
path also double-charged a card, risk would score `critical` and assess would
raise the approach to the full approach, under incident command, instead.

The architecture-check requirement fires on the `cross-cutting` value and adds
`verify.architecture` to hotfix's gate set, so this hotfix runs six gates, not
the base five. `never_skip: [refine, verify, ship]` is honoured by hotfix's
structure regardless of risk (the review is collapsed *into* the
reproduction, not skipped; verify and ship run full). hotfix is the delivery
approach that compresses the stages *before* verify and never verify itself.
Hotfix has no worktree to cap - breakdown is skipped and the fix runs solo.

The methodology's own guard applies here: a fix that turns out to be
`medium`+ in size is *not* a hotfix - it is an incident. Assess it on the
full approach, put someone in incident command, use the multiagent
orchestration if it helps. Assess scores size precisely so that distinction
holds.

### Final `delivery-approach.md`

The delivery approach is hotfix. The §6 "Owed follow-ups" section of `delivery-approach.md` carries an unchecked
item - the mandatory follow-up - and the issue is not closeable until it is
resolved: `delivery-approach.md` completed properly (not just the urgent stub), the
reproduction test promoted into a real Given/When/Then scenario in
`acceptance-criteria.md` traceable to the defect, and a root-cause line in the
`devlog.md`. `/compass:status` flags the outstanding follow-up; `/compass:ship`
refuses to close the issue; the `stop.sh` hook warns at session end.
The outstanding process weight has a due date: "before the issue closes."

---

## Case 6 - An issue that cannot be framed yet

> **Request:** "Our background job queue is dropping ~2% of jobs under load and
> nobody knows why. Find out."

### Score

Assess still scores all four dimensions - but this request is not a known
change, it is a *question*. There are no acceptance criteria to state because
the behaviour to fix is the unknown. That is the signal for **exploration**
as the goal.

| Dimension | Value | Justification |
|---|---|---|
| risk | `contained` | The investigation itself touches nothing irreversible - reading logs, adding instrumentation behind a flag, reproducing in a sandbox. |
| Familiarity | `brownfield-unmapped` | The queue's behaviour under load is exactly what is *not* written down. |
| Size | `small` | The investigation is timeboxed; the eventual fix is unknown and not in scope here. |
| Goal and role | `exploration` (engineer) | "I need to understand this before I can assess it" - not a delivery request. |

### Compose

Exploration goal composes towards **spike**, the way live-defect urgency
composes towards hotfix - the routing strategy
`when: { goal: exploration } → lean_toward: spike` is the bias. Assess is
light but real: `delivery-approach.md` records the **question** ("what is
dropping ~2% of jobs under load?") and a **timebox**. The define stage
collapses to that question. The requirements review is skipped - there is
nothing to QA against, the behaviour is the unknown. The plan stage
collapses to a timebox and an approach sketch. Implementation becomes
**exploration**: the engineer instruments and reproduces freely, and the
**TDD strategy is suspended** - the pre-tool hook is approach-aware and does
not block, because red-before-green is the wrong discipline for throwaway
diagnostic code. Assess also writes a `.spike` marker file in the issue
directory so the hook knows.

### Constrain

The routing policy rules still apply - and one matters here. If the question
could only be answered by touching `auth`, `payments`, `personal-data`, or
`migrations`, the floor would fire and this would *not* be a spike; it would be
the full approach with discovery-heavy acceptance criteria. Here the investigation stays
clear of irreversible surface, so spike stands. Nothing is floored.

### Final `delivery-approach.md` - and the exit

The delivery approach is spike. The verify stage becomes **conclude**: not a test gate, a findings check - *was
the question answered?* The one gate is "the question is answered (or
explicitly answered with 'inconclusive - here is why'), and the finding is
written down." ship becomes **graduate or discard**:

- **Graduate** - the spike found the cause (say, a connection-pool exhaustion
  under a specific retry storm). The finding feeds a fresh `/compass:assess` for
  the real fix. That re-assess is a normal delivery approach - regular,
  probably - and the tested-before-ship, acceptance-before-code, and
  traceability guardrails apply to the fix in full. Any diagnostic code
  carried over is now subject to that delivery approach's guardrails; in
  practice most is rewritten under TDD. The spike's `delivery-approach.md`
  records "graduated → issue `<slug>`".
- **Discard** - the spike concluded "this is environmental, not our code" or
  "inconclusive within the timebox." The finding goes in `devlog.md`, any
  follow-up is filed, and the spike closes. A discarded spike with a clear
  answer succeeded.

Nothing landed from the spike itself. That is the whole safety model: the
de-scopes (the review skipped, the TDD strategy suspended) are safe *because* there is
no delivery output to protect - the only path from spike code to `main` runs
through a real delivery approach. See `approaches/spike.md`.

---

## The same request, four delivery approaches

The cases above are six different requests. Here is one *literal* request -
**"add a CSV export"** - taken four ways, because who asks and what it touches
changes everything. This is the clearest demonstration that Compass computes
the delivery approach from the *assessment*, not the words.

### "Add a CSV export" - engineer, internal admin tool

Size `small`, risk `contained` (an admin tool, bounded), familiarity
`brownfield-mapped`, role `engineer`, no domain tags. Composes to **quick fix**:
one scenario ("given a filtered table, when the user exports, then a CSV with
those rows downloads"), the review collapsed, plan a one-liner, full TDD on a
small surface, one gate. Done in an afternoon. Assess stays out of the way -
correctly.

### "Add a CSV export" - product owner, "let finance self-serve"

Same three words, but an `intent.md` sits behind them, and the intent
document's outcome is "let finance self-serve their month-end numbers."
Assess reads the goal as the *actual outcome wanted*, not the literal
request - and "self-serve" implies filters that match what finance actually
needs, perhaps scheduling, perhaps permissions. Size is no longer `small`;
it is `medium` or larger. The `product-owner` role rule fires: `intent.md`
required, the intent-fidelity gate before the plan stage. Composes to
**the regular approach or heavier**, with a gate that checks the export scenarios
actually deliver "self-serve" and not just "a button that produces a file."
Same words, a genuinely bigger delivery approach - because the goal under
them is bigger.

### "Add a CSV export" - engineer, export of the payments ledger

Same three words again, but the table is the payments ledger. Assess tags
`labels: [payments, personal-data]`. Size might still be `small`. It does
not matter: the policy floor `when: { labels: [payments,
personal-data] }` fires and forces the full approach. Composes to
**full** - full
discovery (what exactly is in this export? what must *not* be?), full requirements review,
a `technical-design.md` with the data-handling decisions recorded, every gate, `security`
full. A "small" feature, the full approach, because of what it touches.

### "Add a CSV export" - product marketer, a launch feature

A marketer invokes `/compass:position` for an export feature being launched.
The `product-marketer` role rule fires: `positioning.md` and
`launch-readiness.md` required, the `claims` review dimension on, and **shipping
blocked** until every claim ("export your data in one click", "works with
spreadsheets you already use") traces to a passing scenario. The engineering
work might be quick fix-sized, but the delivery approach carries the claims
gate to ship regardless - `verify.claims` blocks shipping whenever a marketer
is in play. Same three words; an extra gate that did not exist in the other
three cases.

Four delivery approaches, one request. The request did not change. The
assessment did - and Compass computes the delivery approach from the
assessment.

---

## Reassessment - when the assessment was misread

The delivery approach is computed at the assess stage, but a value can turn
out wrong, and the honest response is not to push on with a delivery
approach you no longer believe.

`/compass:assess --reassess` re-scores the four dimensions mid-issue, writes a
**new revision** of `delivery-approach.md` (the prior revision is kept visible under a
"Superseded" heading), and records what changed and why. A re-assess is a
normal event, not a failure. *A delivery approach quietly outgrown is the
failure.*

A re-assess is also *recorded as data*. `/compass:assess --reassess` re-runs
`compass approach evaluate --write`, which detects that the delivery
approach changed and appends an entry to `manifest.yml`'s `reassessments`
log - `from_route`, `to_route`, the date, and the `--reason`. One entry is
an anecdote; the log across every issue is the framework's feedback signal.
`compass retro` reads it and reports the pattern: are reassessments mostly
*up* (assessment is under-sizing) or *down* (over-sizing)? The triggers
below are the individual events; the retrospective signal is how the
framework notices when they add up to a systematic mis-read of the
assessment - see `docs/methodology.md` §10.

The triggers are concrete:

- **Implementation reveals under-read size.** A "small" change is turning into a
  multi-module refactor. The `builder` agent stops and flags it; the assess
  stage re-scores. This is why the adaptive-routing skill says, when size is
  genuinely unclear, estimate *up* - collapsing a stage that turned out easy
  is cheap; discovering mid-implementation that the approach was too light
  is expensive.
- **The requirements review finds the spec is bigger than the approach assumed.** More scenarios,
  more ambiguity than the regular approach's review pass can absorb. Do not push the
  regular approach through a problem shaped for the full approach.
- **A label surfaces late.** You discover mid-implement that the change
  reaches auth after all. Re-assess, the floor fires, the delivery approach
  is raised - and it is recorded, not silent.
- **A consult changes scope.** `/compass:consult` decides to cut or
  expand scope; if the decision touches the delivery approach, the consult's
  own gate says to follow it with a re-assess.

The reassessed `delivery-approach.md` is the contract again - the next session reads the
latest revision and knows exactly where the issue stands.

---

## What the routing system is really for

Every case above ends in a `delivery-approach.md` that a human can read and a later
session can resume from. That is the deliverable. Assess does not just
classify the issue - it explains the classification, records every policy
rule that fired, and writes down every skip with the reason it is safe. The
adaptivity is real, and it is *bounded*: bounded by the four-dimension rubric,
bounded by the routing policy rules in `governance/routing-policy.yml`, bounded by
the rule that an unjustified skip is not a skip. That is what keeps "adaptive"
from becoming arbitrary.
