---
description: State the technical approach and check it against governance
allowed-tools: Read, Write(./.compass/**), Write(./docs/**), Edit(./.compass/**), Edit(./docs/**), Bash(compass *), Glob, Grep
---

# /compass:plan

Plan turns the spec into a technical approach, checks it against
governance, and - on larger work - decides the parallel orchestration.
Parallelism is *decided here* and *carried out at breakdown*.

(The designer's entry point is `/compass:design`. This command is the
engineering plan stage.)

## Setup

- Run `compass approach show`. The plan stage's weight tells you the shape:
  a one-line "edit which file(s)" note (quick fix), a short design (regular),
  or a full design with its work units (the full approach).
- Read `acceptance-criteria.md` - the design uses the spec as the
  requirements review left it. It is the one document Compass needs and
  checks; a team can keep its own design notes, and Compass does not read them.
- Load the `plan-authoring` skill - how to write the design itself: what a
  work unit is, what makes one independent of another, and the
  self-review the author owes the reviewer before the design is handed over.
- Load the `governance-check` skill.
- Run this stage in this session; Compass starts no agent for it (ADR-090).
- Check the spec against the outcome the product owner asked for (the
  **intent-fidelity** check): the Summary and the Intent links of
  `acceptance-criteria.md` name it. Run it from the product owner's perspective.

## Procedure

1. **Technical approach.** State the design. For each design decision, say
   what was chosen, what was rejected and why. Record a decision that binds
   the project as a decision record (`compass adr new`), and a decision you
   took for the person with `compass issue decision add`. Read
   `architecture-notes.md` in the issue's documents if it exists: each design
   decision then cites an existing ADR (`architecture/decisions/ADR-N-*`),
   names a candidate ADR to write during implementation, or justifies its
   divergence from the notes. When the notes are absent, say in the plan that
   no architect notes were available for this issue.
2. **Governance check.** Run `governance-check` against the governance in
   force - the guardrails (hard, blocking) and the applicable engineering
   strategies (soft, assessed). `compass policy show` prints the rules the CLI
   runs against, and the reasons are in
   `${CLAUDE_PLUGIN_ROOT}/governance/strategies.md` and `guardrails.md`. An
   unmigrated 5.x project runs on its own copied `governance/` until
   `compass policy migrate`. `compass policy lint` checks the structure of the project's `compass.yml` -
   run it if the project has changed the rules. A design that breaks a guardrail
   does not pass - revise the design, never waive the guardrail. A design
   that departs from a strategy can pass, but the departure is recorded.
3. **Work units** (when the work splits into independent units). Read
   the scenario groups from `acceptance-criteria.md`; units that touch
   disjoint code and satisfy disjoint scenarios can run in parallel.
   - On the regular approach: a short list of 2-3 units is enough.
   - On the full approach: list each unit, the files it touches and the
     scenarios it owns.
   - This session builds the units one after another (ADR-090); the list
     records the order and which scenarios each unit owns.

   A policy cap can bound the unit count.
4. **Show the design in the hand-off.** Compass writes no design document and
   registers nothing at this stage. Log the design to `devlog.md`.

## Hand-off

Close the design by handing the technical approach to a human. This is the
last review before code is written, and the cheapest point at which to change
the design.

> The design is below, and in `devlog.md`.
>
> It records N design decisions, the governance check against all of the
> governance in force, and M work units.
>
> Worth a read before implementation. Specifically, look for:
> - **Design decisions you would make differently** - each records what was
>   chosen and what was rejected, so the disagreement should be easy to
>   locate.
> - **A decision with no alternative considered** - that is usually not a
>   decision yet.
> - **Work units that are not as independent as claimed** - optimistic
>   decomposition surfaces as a collision at integration, not here.
> - **Anything still unfinished** - a placeholder such as `TBD`, or a design
>   that is vague without using one.
>
> On approval this goes to breakdown, or straight to implementation on solo
> work.

Wait for approval only if `plan` is in the manifest's `checkpoints:`.
The project's `autonomy` setting, read from `compass.yml` (or from
`.compass/config.yml` in a project without one), decides that list,
and `compass approach show` shows it. If `plan` is not listed, still
state the design and show this hand-off, then say you are going on without
waiting and name the setting, with "Next" in place of "On approval". Record
the passed hand-off with `compass issue checkpoint add plan --outcome skipped
--by planner`, so the person can review it later and send the issue back. If
`plan` is listed, ask with `compass evidence request --checkpoint plan` and
wait: the person types `/compass:approve` in Claude Code, or runs `compass
evidence approve --checkpoint plan --approver <name> --role <role>` at a
terminal, which records the answer. An issue assessed before outcomes were recorded is not judged: both
commands refuse it and write nothing, so say so and go on.

If you resolved a requirement question
yourself instead of asking, record it:
`compass issue decision add <id> --question "<q>" --resolution "<r>" --by <your agent> --stage plan`.
Before you hand off, run `compass next`. When its first line reads
`Waiting at the plan checkpoint`, the issue holds decisions that no person has
confirmed. Show the listed decisions in the hand-off and wait: the person
confirms them all by typing `/compass:approve` after you run `compass evidence
request --decisions` (or `compass evidence approve --decisions` at a terminal), or
reopens one with
`compass issue decision set`. Do not name the next stage while it waits. On
`autonomous` autonomy `compass next` lists the decisions and does not wait; show
the list in the hand-off.

## Gate

The design is stated; the governance check passed (record its result with
`compass evidence add`); the spec meets the outcome the product owner asked for; if the
work is parallelisable, the work units are listed. Log to `devlog.md`. Next: `/compass:breakdown` (or
straight to `/compass:implement` on solo work).
