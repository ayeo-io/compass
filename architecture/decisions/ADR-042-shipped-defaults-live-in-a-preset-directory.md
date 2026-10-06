---
id: ADR-042
title: Shipped defaults live in a preset directory
status: accepted
date: 2026-10-06
supersedes: ''
superseded_by: ''
---

## Context

The maintainer accepted this record on 2026-10-06.

Today the shipped defaults are two files: `governance/routing-policy.yml`, which `compass approach evaluate` runs, and `governance/guardrails.yml`, which `compass check` runs. A project that wants to change anything copies both into its own `governance/`. `find_governance()` returns that copy when both files are present (`cli/compass_pkg/core.py:135`) and the shipped directory otherwise (`core.py:154-156`).

ADR-010 (project governance should layer over framework defaults rather than copy them) and ADR-033 (projects add checks, gates and assessment-dimension values as data) decided that a project states only its differences, over a shipped parent. The configurable-framework design splits the defaults into eight catalogues and names the parent `compass:default@<major>`. Three questions follow:

- where the shipped defaults live, and which copy is the source;
- what happens to projects that already copied the two files, and to the readers of `.compass/config.yml`;
- how this repository, which is both the framework and a Compass project, avoids reading its own shipped files as a project's copy.

On the third, `find_governance()` cannot tell the two cases apart. Run in this repository, it finds both files in `governance/` and returns that directory as the project's own (`core.py:135`). That directory is also the shipped one, because `FRAMEWORK_ROOT` is the repository root (`core.py:39`).

## Decision

**The single source of the shipped defaults is `governance/presets/default/`.** It holds `preset.yml` (id, version, schema and capabilities, all off), one file per catalogue, and the fixed evidence types. A project never edits it. The CLI loads it only as a parent, for `extends: compass:default@<major>`, from `FRAMEWORK_ROOT/governance/presets/<name>/`.

**`governance/routing-policy.yml` and `governance/guardrails.yml` become generated, read-only views of the preset through 6.x.** They keep the legacy format. Projects that copied them, the drift report and the existing tests keep working. Both views are removed at 7.0.0, together with the reads of the old `.compass/config.yml` (decided by jed72 on 6 October 2026).

**A project with copied governance and no `compass.yml` runs through a legacy adapter, unchanged.** A project with a `.compass/config.yml` and no `compass.yml` keeps reading its settings from that file. Both hold until 7.0.0. `compass policy migrate` moves a project to `compass.yml` when the project chooses.

**`default@6.x` never changes the value of a field that `default@6.0.0` defines** (decided by jed72 on 6 October 2026). A change to an existing value is a new major version. A minor version may only add capabilities and checks, inactive until a project turns them on. A CLI upgrade within 6.x therefore changes no project's behaviour and invalidates no waiver on the shipped default.

**Self-application: this repository runs the shipped default unchanged.**

1. This repository's root `compass.yml` holds settings keys only, such as `autonomy`, `enforcement`, `record` and `project`. It extends `compass:default@6` and declares no catalogue key, waiver, unlock or capability. A test fails when a catalogue key appears in it, and a planted key must prove that the test can fail.
2. The loader never reads a project file from the framework's location. It reads the project file from the project root only. The plugin ships the whole repository (`.claude-plugin/marketplace.json:14` has `"source": "./"`), so an adopter's plugin directory holds this repository's `compass.yml`. Nothing reads it there.
3. The loader tells the framework repository from a project that copied governance by comparing the project root with `FRAMEWORK_ROOT`. When `os.path.realpath` of the project root equals `FRAMEWORK_ROOT`, the two files in `governance/` are the generated views, not a copy. The loader skips legacy detection, prints no "this project copies governance" advisory, and `compass policy migrate` refuses to run.

## Alternatives considered

- **Keep `routing-policy.yml` and `guardrails.yml` as the source and derive the catalogues from them.** Rejected: the legacy format has no place for the new catalogues, such as `artifacts` and `vocabulary`, or for locks and capabilities. The source would be the less expressive of the two.
- **Remove the legacy files at 6.0.0 and rewrite their consumers in the same release.** Rejected: ADR-006 (backward compatibility is non-negotiable) says that a project which has not adopted the new mechanism keeps working. Projects with copied governance would break on upgrade with no migration window.
- **Allow `default@6.x` to change existing values in a minor release.** Rejected: every such change would silently move projects that extend the default, and would invalidate waivers approved against the old value on a routine upgrade.
- **Let this repository carry an overlay for its own issues.** Rejected: its delivery record would then be evidence for a configuration adopters do not get. The ledger entry `2026-10-06-this-repository-may-hold-a-settings-only-compass-yml` keeps the stricter rule.
- **Detect the framework repository by a marker file instead of comparing paths.** Rejected: a marker can be copied into a project along with `governance/`. `FRAMEWORK_ROOT` is computed from the CLI's own location (`core.py:38-39`) and cannot be copied.

## Consequences

- Every change to the shipped defaults is made in `governance/presets/default/`. A test must check that the two generated views match the preset, so a hand edit to a view fails the build.
- The drift report keeps comparing a project's copy with the shipped views until 7.0.0.
- 7.0.0 removes the views, the legacy adapter and the reads of `.compass/config.yml`. A project that has not migrated by then must run `compass policy migrate` first.
- A minor release that needs to change an existing default value must wait for the next major, or add a capability that a project turns on.
- A test fixture under `tests/` must hold its own `.compass` or `.git`. The project root is the first directory, walking up, that holds either (`core.py:87`), so a fixture with neither would read this repository's `compass.yml`. This exposure exists today for `.compass/config.yml`.

## References

- ADR-006: backward compatibility is non-negotiable.
- ADR-010: project governance should layer over framework defaults rather than copy them.
- ADR-033: projects add checks, gates and assessment-dimension values as data.
- ADR-041: the configuration vocabulary, amending ADR-012.
- ADR-043: a project has one configuration file, `compass.yml`.
- `cli/compass_pkg/core.py`: `FRAMEWORK_ROOT` (line 39), `BOUNDARY_MARKERS` (line 87), `find_governance()` (lines 112-160).
- `governance/decisions/2026-10-06-this-repository-may-hold-a-settings-only-compass-yml.md`: the ledger entry for the self-application rule.
- `governance/decisions/2026-10-06-default-6-x-never-changes-a-6-0-value.md` and `governance/decisions/2026-10-06-legacy-governance-readable-until-7-0-0.md`: the ledger entries for the version rule and the 7.0.0 removal.
