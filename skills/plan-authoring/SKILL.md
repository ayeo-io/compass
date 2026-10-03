---
name: plan-authoring
description: Writing a technical design and its self-review. Load at the plan stage.
---

# Plan Authoring

This skill is about *writing* a plan. `governance-check` is about *checking*
one against governance. Keep the two apart: one asks "is this design clear
enough to argue with?", the other asks "does it cross a guardrail?"

A plan has one job that its section list does not make obvious: **let a
reviewer disagree with the design before the code exists.** That is the
cheapest moment to change it. Everything below serves that.

## The six optional sections

`templates/technical-design.md` offers six sections beyond the ones every plan has. They
are optional individually, and the judgement about which to use is the craft
this skill teaches.

| Section | Include when | Omit when |
|---|---|---|
| **0. Summary** | A reader who did not write the plan needs to know what it delivers before judging how. | Section 1 is already short enough to be the summary. |
| **2. Interaction** (sequence diagram) | Two or more components collaborate and the *order* of their exchanges matters. | The change lives inside one component. |
| **3. Structure** (class/module diagram) | New components, changed relationships, or a contract the work units assume. | The change adds no new boundary. |
| **4. Design patterns invoked** | A real named pattern is genuinely being applied *and* you can say what it buys this change. | You cannot name it, or cannot say what it buys. |
| **5. The shape of the change** (code) | The shape of an interface, type, or API is itself a decision worth arguing with. | The shape is obvious from section 1. |
| **5a. Cross-cutting concerns** | The change touches security, privacy, or what you can see in production. *Design Docs at Google* (<https://www.industrialempathy.com/posts/design-docs-at-google/>) names these three as concerns of the design rather than documents of their own. | It touches none of them - or a label earned a full threat-model.md or rollback-plan.md, in which case link that rather than summarising it here. |

Where the route plans in full, section 5a also names the well-architected
pillars the change touches and what the design does about each. That is
the well-architected alignment strategy, `S15`, and the pillars come from
`governance/architecture-sources.yml`. It is advice for the reviewer, not a
gate.

**Delete the sections you do not use.** An empty optional heading is worse
than an absent one: it reads as an omission rather than a decision, and the
next author fills it in to be safe.

## Scaling by delivery approach

- **quick-fix** - none of them. quick-fix writes no `technical-design.md` at all; the plan is
  a one-line edit note in `delivery-approach.md`.
- **feature** - the ones that add clarity. Typically one diagram, and one of
  the other three. Reaching for all six on a feature approach is a sign the
  assessment was too low, not a sign of thoroughness.
- **initiative** - all of them, freely, where the work warrants it. Here the
  plan *is* the design document, and a reviewer is expected to spend real time
  in it.

## Diagrams: Mermaid by default

Mermaid renders natively in GitHub, in every modern IDE viewer, and in the
Compass artifacts themselves. Use it.

**Reach for PlantUML only when Mermaid genuinely cannot express the shape** -
component diagrams with lifelines, state charts with guards, deployment
orchestration. PlantUML needs a rendering path the reader may not have, so the cost
of using it is that some readers see source instead of a picture. Pay that
cost when the diagram is worth it, not by default.

A diagram earns its place by replacing prose, not by accompanying it. If the
paragraph above the diagram already says everything the diagram says, cut one
of them.

## Naming a pattern honestly

This is the section that goes wrong most often, so it has its own rule:

> **A pattern name with no reason is name-dropping.** It makes a plan sound
> considered without making it clearer, and a reviewer cannot disagree with a
> bare name.

Every named pattern needs a concrete reason it earns its place *in this
change* - an existing second variant, a boundary you mock in tests, a change
you already expect. "We use the Strategy pattern" is not a design decision.
"The `TokenValidator` interface lets us swap signature algorithms without
touching `AuthService`; we already ship two and expect a third" is.

If you cannot name a real pattern, omit the section. Two justified patterns
beat five decorative ones, and an omitted section costs a reviewer nothing.
Where you chose between two, name the one you rejected and why: that is the
named-patterns strategy, `S16`.

## Self-review before hand-off

Run these over the finished plan and **fix what you find inline**. Do not
write a review artifact and do not invoke a reviewer agent - this is the cheap
pass the author owes the reviewer, the same shape as the spec-author's
self-review in `bdd-specification`.

1. **Placeholder scan** - any `{{...}}` template placeholder left, including in
   a section you kept but did not fill. Read for those yourself: `compass plan
   lint` does not look for `{{...}}`. What it does catch is the *phrases* that
   mean a decision was deferred - "TBD", "TODO", "implement later", "add
   appropriate error handling" - plus a work unit that promises tests without
   naming any. It is advisory and always exits 0: a hit is a note, not a block.
   Judge each one - a deferred decision with a named owner is a plan; an unowned
   `TBD` is a gap.
2. **Coverage scan** - every scenario group in `acceptance-criteria.md` is covered by
   at least one work unit. An uncovered group means either a missing unit or a
   scenario nobody intends to satisfy, and both are worth knowing now.
3. **Pattern-name check** - every pattern named in section 4 is actually
   applied by a work unit in section 8, and carries its reason.
4. **Magic-number scan** - every threshold, timeout, or budget in the plan has
   a stated source: the spec, an ADR, or a measurement. A number with no
   source is a decision someone will have to re-make during implementation, alone.

## Anti-patterns

- **The padded plan** - all six optional sections filled on a change that
  needed one. Process weight is a cost; a long plan is read less carefully than a
  short one.
- **The decorative diagram** - a diagram that restates the paragraph above it.
  Cut one.
- **The implementation in section 5** - section 5 sketches a contract. If you
  are writing the body, you are doing the implement stage's work in a document nobody will
  run.
- **The undisagreeable plan** - prose that describes what will happen without
  exposing a single choice. If a reviewer cannot find anything to push back
  on, the decisions are hiding in someone's head, not in the plan.
- **Pattern-name-dropping** - see above. It is the most common way a plan
  looks more considered than it is.
