# Writing the design down

The governance-check skill sends you here at specify. This file says what a
design holds, how many optional sections to use, and the self-review to do
before the governance check.

A design has one job: **let a reviewer disagree with it before the code
exists.** That is the cheapest moment to change it. Write one at specify
when the change has a design decision worth arguing with; a change with no
design decision needs none. Compass writes no design document (ADR-091): the
design goes in the report to the person, or in a design note the team keeps
beside `acceptance-criteria.md`.

Every design states the approach, the design decisions and the work units.
Six sections are optional, and choosing which to use is the craft:

| Section | Include when | Omit when |
|---|---|---|
| **Summary** | A reader who did not write the design needs to know what it delivers before judging how. | The approach is already short enough to be the summary. |
| **Interaction** (sequence diagram) | Two or more components collaborate and the *order* of their exchanges matters. | The change lives inside one component. |
| **Structure** (class or module diagram) | New components, changed relationships, or a contract the work units assume. | The change adds no new boundary. |
| **Design patterns invoked** | A real named pattern is genuinely being applied *and* you can say what it buys this change. | You cannot name it, or cannot say what it buys. |
| **The shape of the change** (code) | The shape of an interface, type, or API is itself a decision worth arguing with. | The shape is obvious from the approach. |
| **Cross-cutting concerns** | The change touches security, privacy, or what you can see in production. | It touches none of them, or the team keeps a threat model or rollback plan of its own; link that instead. |

How many to use scales with the evidence the issue owes:

- **The light row** - none of them. There is no design to write.
- **The standard row** - the ones that add clarity: typically one diagram
  and one other section. Reaching for all six is a sign the assessment was
  too low, not a sign of thoroughness.
- **A change that owes `architecture`** - all of them, freely, where the
  work warrants it. A reviewer is expected to spend real time in it. The
  cross-cutting section also names the well-architected pillars the change
  touches and what the design does about each: that is the well-architected
  alignment strategy, `S15`, and the pillars come from
  `${CLAUDE_PLUGIN_ROOT}/governance/architecture-sources.yml` (an
  unmigrated 5.x project is refused until it migrates). It is advice
  for the reviewer, not a gate.

**Delete the sections you do not use.** An empty optional heading reads as
an omission rather than a decision.

**Diagrams are Mermaid by default.** Mermaid renders in GitHub and in every
modern IDE viewer. Reach for PlantUML only when Mermaid cannot express the
shape, because some readers then see source instead of a picture. A diagram
earns its place by replacing prose: if the paragraph above it already says
everything the diagram says, cut one of them.

**Name a pattern only with a reason.** A pattern name with no reason is
name-dropping: it makes a design sound considered without making it
clearer, and a reviewer cannot disagree with a bare name. Every named
pattern needs a concrete reason it earns its place *in this change* - an
existing second variant, a boundary you mock in tests, a change you already
expect. Where you chose between two, name the one you rejected and why:
that is the named-patterns strategy, `S16`. If you cannot name a real
pattern, omit the section.

**Review the design yourself before the check.** Fix what you find inline;
write no review artifact and start no reviewer agent.

1. **Placeholder scan** - any `{{...}}` left, and any phrase that defers a
   decision ("TBD", "TODO", "implement later", "add appropriate error
   handling"). A deferred decision with a named owner is a design; an
   unowned `TBD` is a gap.
2. **Coverage scan** - every scenario group in `acceptance-criteria.md` is
   covered by at least one work unit.
3. **Pattern-name check** - every named pattern is applied by a work unit
   and carries its reason.
4. **Magic-number scan** - every threshold, timeout or budget has a stated
   source: the spec, an ADR or a measurement.
