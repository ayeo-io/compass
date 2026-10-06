---
id: ADR-035
title: Delivery approaches, stages and modes are configuration data
status: proposed
date: 2026-10-06
supersedes: ''
superseded_by: ''
---

## Context

The routing policy is one file, and a project changes it only by owning a full copy. `/compass:init` copies `governance/routing-policy.yml` (368 lines, `version: 2.19.0` at line 20) into the project, and the CLI reads that copy instead of the shipped file. A project that changes one stage of one delivery approach owns every other line from then on, and the drift report compares rule ids, not content.

The format cannot describe what a project would change:

- A delivery approach has no id the drift report can see. A copy that drops `verify.security` from an approach, or sets the `verify` stage to `skipped`, is not reported.
- Stage values are free text. `schemas/routing-policy.schema.json:370-372` types an approach's `stages` as any object, so a typo such as `lite` passes lint.
- The set of approaches is fixed. The schema needs the five `route_shapes` keys by name (`schemas/routing-policy.schema.json:337-356`), and `cli/compass_pkg/policy.py:206-211` checks them by name.
- The code names approaches in string literals: `ROUTE_NAMES` (`cli/compass_pkg/core.py:607`), `CHECKPOINT_ROUTES` (`cli/compass_pkg/policy.py:76`), and the two spike tests in the evaluator (`cli/compass_pkg/routing.py:238` and `:309`).
- "Raise to full" is a fixed list. `cli/compass_pkg/routing.py:302-304` lifts `collapsed`, `skipped` and `light` to `full`; any other value is left alone.
- A floor names a minimum approach by key (`force_minimum_route: full`, `governance/routing-policy.yml:124`), compared by `weight` (`cli/compass_pkg/routing.py:165-166` and `:180-184`). If a project could add approaches, a lighter approach under a new name would sit below every floor.

ADR-033 (projects add checks, gates and dimension values as data) decided that projects add process as data and the framework locks its core. ADR-010 (project governance layers over framework defaults) decided that a project states its differences, not a copy. This record sets the format for the routing half of that configuration.

## Decision

**The eight stages are fixed. Each declares named modes with a numeric `rank`.** The stages are assess, define, refine, plan, breakdown, implement, `verify` and ship, in that order. A project cannot add, remove or reorder a stage. Each stage declares its modes, and each mode names the skill it loads, the artifacts it produces, the checks it runs and its `rank`. A higher rank means more process. The shipped modes cover every value in use today: `full`, `light`, `collapsed`, `skipped`, `multiagent`, `explore`, `conclude`, `graduate-or-discard`, `reproduce-first`, `expedited` and `full-plus-backfill`. "At least mode M" is a comparison against M's rank, which replaces the fixed list at `routing.py:302-304`.

**A delivery approach picks a mode per stage.** The catalogue is named `approaches` (`governance/decisions/2026-10-06-the-approach-catalogue-is-approaches.md`). An approach declares:

- a `weight`, distinct across approaches, which orders them for a floor; lint fails on a tie;
- a mode for each stage;
- its gates and its artifacts with their depth;
- its `subtask_ceiling`;
- its checkpoints for each autonomy setting (`controlled`, `balanced`, `autonomous`), which today sit apart in `autonomy_checkpoints` (`routing-policy.yml:296-314`);
- `ships:`, true unless the approach delivers nothing;
- optionally `extends:` another approach, stating only what differs.

An issue picks an approach with `approach:`, and a floor raises the minimum approach with `force_minimum_approach`. The legacy keys `route_shapes` and `force_minimum_route` are read through the legacy adapter until 7.0.0 (`governance/decisions/2026-10-06-legacy-governance-readable-until-7-0-0.md`).

**A project extends the shipped default and states only its differences.** The project file declares `extends: compass:default@<major>`. Every layer uses the one merge grammar the configurable framework uses (`governance/decisions/2026-10-05-one-merge-grammar.md`):

- `set:` updates named fields of an entry;
- `replace: true` with a full entry replaces it;
- `remove: true` removes it, and fails while anything still refers to it;
- a list field inside `set:` takes `add:` and `remove:`;
- a map field inside `set:` is changed key by key, with its own `set` and `remove` (`governance/decisions/2026-10-06-set-on-a-map-is-key-by-key.md`).

**Lighter needs an approved waiver; heavier needs none.** A change that makes a stage lighter, removes a gate, or both lightens and tightens, fails lint unless the entry carries an approved waiver. ADR-039 (waivers, locks and unlocks) says who may approve one. A change that only adds process passes. ADR-037 (a configuration change is classified by its effect over the assessment grid) defines lighter and heavier.

**Floors set a minimum and win over the issue layer.** A floor sets a minimum mode for named stages and can add required gates, as well as a minimum approach. The evaluator applies the issue layer's approach and mode choices first, then floors, caps and role rules (`governance/decisions/2026-10-05-floors-win-over-the-issue-layer.md`). A floor therefore lifts a mode an issue lowered.

**Some guarantees are locked.** The shipped default locks each of these (ADR-039 lists the entries). Lint refuses a layer that removes one. Only the project layer can lift such a lock, with an `unlock:` its owner approves, and the project is then reported as not conforming to Compass on every run (ADR-033):

- assess runs, and runs first;
- the `verify` stage comes before ship;
- the immovable gates `verify.correctness`, `verify.governance` and `verify.traceability` (`routing-policy.yml:241-251`) apply to every approach that ships;
- gate evidence is typed. Evidence types are fixed data, not a catalogue entry, so no unlock reaches them.

**An unknown mode fails lint.** A mode named by an approach, a floor or an issue layer must be one the stage declares.

**No approach name appears as a literal in code.** Code that must name an approach, such as the default loader and the migration map, uses the constants in one module (ADR-040, stable ids live in one registered constants module). The spike special case becomes the attribute `ships: false`. The immovable gates apply to an approach that ships. An approach with `ships: false` that a floor would raise to one that ships refuses, as `routing.py:238` does for a spike today.

**A copied policy keeps working.** A project that copied today's full policy, and has no project file, runs through the legacy adapter with no change in behaviour. `compass policy migrate` converts the copy to an overlay. It is a dry run by default, and prints every difference from the shipped default.

## Alternatives considered

- **Keep the copied policy and improve the drift report.** Rejected: a report relies on someone reading it, and a project still owns 368 lines to change one value.
- **Free-text stage values with a fixed "raise to full" list.** Rejected: an unknown value passes lint, and a new mode would need a code change to take part in a floor.
- **Let projects add or reorder stages.** Rejected: the checkpoint stages (`CHECKPOINT_STAGES`, `core.py:192`), the pre-tool hook's stage reads and the guarantees above are written against the eight stages. Custom stages need their own decision.
- **A per-field merge rule declared in the schema, where a value replaces and a list takes `add:` and `remove:`.** Rejected: it is a second grammar beside the configurable framework's, and adopters would see two ways to write one change.
- **Name the catalogue after the legacy key, or `delivery_approaches`.** Rejected: the vocabulary bans the legacy word for this concept (ADR-012, the v2 vocabulary freeze), and the long form repeats in every nested id.

## Consequences

- A project that changes one mode writes one `set:` line, and the drift it carries is visible as an overlay.
- A project can add an approach without falling below a floor, because floors compare by weight and by mode rank, not by name.
- The shipped default, rewritten in this format, must give identical `compass approach evaluate` output for all 1,200 assessments in `assessment_vocabulary` without labels (4 risk, 3 familiarity, 5 size, 2 goal, 2 urgency, 5 role; `routing-policy.yml:273-281`), and for every label combination that recorded issues used, because floors fire on labels. A test runs all of them.
- The default ranks must reproduce today's lift at `routing.py:302-304`. A stage whose modes cannot be ranked one above another makes every change to it incomparable, which needs a waiver.
- The word `mode` now names a stage attribute. The adoption setting takes the key `adoption` in the project file (`governance/decisions/2026-10-06-the-adoption-setting-is-adoption.md`). ADR-041 records the vocabulary amendment.
- Removing the approach-name literals touches `core`, the evaluator, lint, `check_cmd`, `quick_fix_cmd`, `calibration`, `diagnose` and `next_cmd` (for example `check_cmd.py:449` and `quick_fix_cmd.py:346`). Each moves to a catalogue attribute or to the constants module.

## References

- ADR-006: backward compatibility is non-negotiable; the legacy adapter keeps copied policies working through 6.x.
- ADR-010 and ADR-033: layering over the shipped default, and the framework locks.
- ADR-036 (an issue runs against a stored generation of its configuration), ADR-037 (classification by effect) and ADR-039 (waivers, locks and unlocks).
- `governance/routing-policy.yml`, `schemas/routing-policy.schema.json`, `cli/compass_pkg/routing.py` (`evaluate_route`), `cli/compass_pkg/policy.py`.
