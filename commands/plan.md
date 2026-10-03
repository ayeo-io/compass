---
description: Write the technical design and check it against governance
allowed-tools: Read, Write, Edit, Glob, Grep
---

# /compass:plan

Plan turns the spec into a technical approach, checks it against
governance, and - on larger work - decides the parallel orchestration.
Parallelism is *decided here* and *carried out at breakdown*.

(The designer's entry point is `/compass:design`. This command is the
engineering plan stage.)

## Setup

- Read `delivery-approach.md`. Its weight for this stage tells you the
  shape: a one-line "edit which file(s)" note (quick fix - no `technical-design.md`), a
  real `technical-design.md` (feature), or a full `technical-design.md` plus
  `distribution-map.md` (initiative).
- Read `acceptance-criteria.md` and `requirements-review.md` - the design is
  built on the hardened spec.
- Load the `plan-authoring` skill - how to write the design itself: what a
  work unit is, what makes one genuinely independent of another, and the
  self-review the author owes the reviewer before the design is handed over.
- Load the `governance-check` skill.
- Invoke the `planner` agent - it owns this stage.
- If an `intent.md` exists, this is where the **intent-fidelity gate** lands: the
  spec must be checked against `intent.md` before the design completes. Invoke
  `product-owner` to run it.

## Procedure

1. **Technical approach.** State the design. Record each design decision as
   an ADR-style note - what was chosen, what was rejected, why.
2. **Governance check.** Run `governance-check` against `governance/` - the
   guardrails (hard, blocking) and the applicable engineering strategies
   (soft, assessed). Read the machine-readable governance the CLI runs
   against: `guardrails.yml`, `strategies.md`, `routing-policy.yml`.
   `compass policy lint` checks the structure of the governance YAML - run it
   if the project has tuned `governance/`. A design that crosses a guardrail
   does not pass - revise the design, never waive the guardrail. A design
   that departs from a strategy can pass, but the departure is recorded.
3. **Distribution map** (when the work splits into independent units). Read
   the scenario groups from `acceptance-criteria.md`; units that touch
   disjoint code and satisfy disjoint scenarios can run in parallel.
   - On a feature: a short list of 2-3 units is enough.
   - On an initiative: write the full `distribution-map.md` from its
     template.
   - On an initiative capped solo: still write the full map - it records
     what *could* have been parallel and why it wasn't.

   Subtask count comes from the map; orchestration thresholds from
   `.compass/config.yml`; a policy cap can bound the count.
4. **Write `technical-design.md`** from `${CLAUDE_PLUGIN_ROOT}/templates/technical-design.md`,
   and `distribution-map.md` from its template when applicable.

   **Where it goes.** `docs/compass/<created>-<issue-slug>/technical-design.md`, where the
   date is the manifest's `created:` field - not today's. Then register it:
   `compass issue artifact technical-design --status draft --path <that path>`. The CLI
   refuses a path that climbs out of the project, so the record is checked
   rather than claimed. If you had to create `docs/compass/`, **say so in one
   line** - a directory appearing with nothing said is how it gets deleted by
   hand or committed by accident.

## Hand-off

Close the design by handing the technical approach to a human. This is the
last review before code is written, and the cheapest point at which to change
the design.

> I have written the design to
> `docs/compass/<created>-<issue-slug>/technical-design.md`
> (and the distribution map to `distribution-map.md`).
>
> It records N design decisions, the governance check against all of
> `governance/`, and M work units.
>
> Worth a read before implementation. Specifically, look for:
> - **Design decisions you would make differently** - each records what was
>   chosen and what was rejected, so the disagreement should be easy to
>   locate.
> - **A decision with no alternative considered** - that is usually not a
>   decision yet.
> - **Work units that are not as independent as claimed** - optimistic
>   decomposition surfaces as a collision at integration, not here.
> - **Anything still unfinished** - `compass plan lint` reports placeholder
>   phrases, but a design can be vague without using one.
>
> On approval this goes to breakdown, or straight to implementation on solo
> work.

Wait for approval only if `plan` is in the manifest's `checkpoints:`.
The project's `autonomy` setting in `.compass/config.yml` decides that list,
and `compass approach summary` shows it. If `plan` is not listed, still
write the technical design and show this hand-off, then say you are going on without
waiting and name the setting, with "Next" in place of "On approval". Log
the skipped checkpoint to `devlog.md`, so the person can review it later and
send the issue back.

## Gate

`technical-design.md` exists; the governance check passed (record its result and link
the record); if an `intent.md` exists, the intent-fidelity gate passed; if the work is parallelisable, a
distribution map exists. Log to `devlog.md`. Next: `/compass:breakdown` (or
straight to `/compass:implement` on solo work).
