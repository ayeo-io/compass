---
id: ADR-041
title: The configuration vocabulary, amending ADR-012
status: proposed
date: 2026-10-06
supersedes: ''
superseded_by: ''
---

## Context

This record amends ADR-012 (the v2 vocabulary is frozen - industry words only, enforced by the build). ADR-012 asks for a decision record for a new term, a change of meaning or a new ban; its rule 4 also lets a recorded maintainer instruction fill a gap additively. This record is the decision for the configurable-framework design, because it adds terms and resolves two clashes.

The configurable-framework design turns delivery approaches, stages, checks and gates into data that a project extends. It needs words for the parts of that data, and it hits two clashes with the frozen vocabulary.

- **The catalogue of delivery approaches.** It needs a name. `governance/terminology.yml` bans "route" as the computed process shape and gives "delivery approach" as the replacement (the `banned:` block starts at line 673; the entry is at lines 692-694). A catalogue called `routes` would teach the banned word in every project file.
- **The word `mode`.** Today `mode` is the adoption setting, `advisory` or `enforced`, in `.compass/config.yml`. `load_mode` reads it (`cli/compass_pkg/core.py:173-186`) and `mode_banner` prints `[mode: advisory]` (`core.py:218-224`). The design gives each stage a `mode` too, such as `collapsed`. The design also folds `.compass/config.yml` into `compass.yml` (ADR-043), so both meanings would sit in one file.

## Decision

**The catalogue of delivery approaches is `approaches`** (decided by jed72 on 6 October 2026). The names that follow from it are:

- the catalogue key `approaches` in the preset and in a project file;
- the issue-layer key `approach`, which picks a delivery approach for one issue;
- the floor effect `force_minimum_approach`, which replaces today's `force_minimum_route` (`governance/routing-policy.yml:124`) in the new format;
- the vocabulary prefix `approaches.`, as in `approaches.quick-fix`.

**`routing-policy.yml` and the `router` agent keep their names.** The ban covers "route" as the computed shape. It does not cover routing as an activity. `terminology.yml` already defines `router` (line 245) as the agent named for the file it runs.

**The adoption setting is `adoption`** (decided by jed72 on 6 October 2026). It takes `advisory` or `enforced` and lives in `compass.yml`. `mode` keeps one meaning in the new format: the stage mode. A project that has not migrated keeps `mode:` in `.compass/config.yml`, which the CLI reads as today. The banner and the advice that names the file change with the key.

**These terms join the vocabulary:**

- **catalogue**: one of the eight maps of configuration entries keyed by id: `dimensions`, `stages`, `approaches`, `rules`, `checks`, `gates`, `artifacts` and `vocabulary`.
- **layer**: one source of configuration: the shipped preset, a team parent, the project file or the issue.
- **overlay**: a layer file that states only its differences from its parent.
- **preset**: a named, versioned parent. `default` is the only preset Compass ships.
- **generation**: a stored, numbered copy of the resolved configuration that an issue runs against.
- **waiver**: a recorded departure from a parent's value, with a reason and an approver.
- **lock**: a mark on an entry that refuses a change from a lower layer that would loosen it or that the classifier cannot compare. Tightening stays allowed.
- **capability**: a named switch for new blocking behaviour, off in the shipped default.
- **stage mode**: how a stage runs for an issue, such as `collapsed`; the `mode` field of a stage.
- **project file**: `compass.yml` at the project root, the one file a person edits.
- **settings key**: a top-level key of `compass.yml` that configures the CLI instead of the process.
- **pin**: the `#<sha>` suffix on a git `extends:`, which names the parent commit a project runs against.
- **obligation**: anything the configuration asks for at an assessment: a stage mode, a check on an entry or exit list, a gate, an artifact, a checkpoint or a ceiling.
- **classifier**: the component that compares two configurations by their obligations.

The terms join `governance/terminology.yml` when this record is accepted, in the increment that builds the vocabulary catalogue. That diff must bump the file's version, as ADR-012 rule 4 says it must.

**Display names live in the `vocabulary` catalogue, and ids stay stable.** The catalogue maps `<catalogue>.<id>` to a display name and aliases, for example `approaches.quick-fix: { name: "quick fix" }`. Code, manifests and generations use the id. A display name or alias must not match a pattern in the `banned:` block, and lint runs the same ban patterns over them. `terminology.yml` stays the glossary and the ban list. The `vocabulary` catalogue does not replace it.

## Alternatives considered

- **`routes:` as the catalogue name.** Rejected: "route" is banned as the computed process shape (`terminology.yml:692-694`). Every project file, preset and display id such as `routes.quick-fix` would teach the banned word, and the scan would need an exemption for each.
- **`delivery_approaches:` as the catalogue name.** Rejected: it is long, and it repeats in every nested id and reference, such as `delivery_approaches.quick-fix` and `delivery_approaches.full.stages`. `approaches` keeps the frozen word and drops the repeated qualifier, because the file already says what kind of approach it means.
- **Keep `mode` for both the adoption setting and the stage mode.** Rejected: one file would hold a top-level `mode: advisory` and `stages.<id>.set.mode: collapsed`, two unrelated meanings. A published preset is also a `compass.yml`, so a copied `mode: advisory` could read as a harmless stage line. Lint would reject it in a parent, but the name would stay easy to confuse.
- **Rename `routing-policy.yml` and the `router` agent as well.** Rejected: the ban is about the shape, not the activity. Renaming both would break every project that copied the file and every reference to the agent, for no gain in meaning.

## Consequences

- No project file, preset or display name carries "route" for the computed shape. The legacy views in `governance/` keep their present keys, including `force_minimum_route`, until they are removed at 7.0.0 (ADR-042).
- The migration renames `mode` to `adoption` when it writes `compass.yml`. A project moves its settings file anyway when it migrates, so the rename costs nothing extra.
- Tests that pin the banner text or the advice naming `.compass/config.yml` change with the key. `tests/test_modes.py` covers the banner.
- The catalogue `approaches` shares its name with the prose directory `approaches/`, which describes the same delivery approaches. The two hold the same subject in two forms: the catalogue is data, the directory explains it.
- The `project_additions` block in `terminology.yml` (lines 989-992) says project vocabulary additions are not supported. It changes in the increment that builds the `vocabulary` catalogue, because a project can then give its own entries display names.

## References

- ADR-012: the v2 vocabulary is frozen; this record amends it.
- ADR-042: shipped defaults live in a preset directory.
- ADR-043: a project has one configuration file, `compass.yml`.
- `governance/terminology.yml`: the `banned:` block (line 673), the `router` term (line 245) and `project_additions` (lines 989-992).
- `cli/compass_pkg/core.py`: `load_mode` (lines 173-186) and `mode_banner` (lines 218-224).
- `governance/decisions/2026-10-06-the-approach-catalogue-is-approaches.md` and `governance/decisions/2026-10-06-the-adoption-setting-is-adoption.md`: the ledger entries for the two naming decisions.
