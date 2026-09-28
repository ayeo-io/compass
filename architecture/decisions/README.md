# Architecture Decision Records - Compass Framework

This directory contains Compass's own Architecture Decision Records (ADRs).
These are the founding decisions that define how the framework itself works and
why. Every framework-touching issue should read these before proposing changes
to the pipeline, routing, guardrails, strategies, or role model.

## Why ADRs matter here

Compass is a framework that recommends ADRs for adopting projects. These ADRs
are Compass using ADRs for its own decisions: the framework's own structural
decisions are recorded here as first-class artifacts, not buried in git history
or living only in conversation.

The architect agent reads these ADRs when consulting on a framework-touching
issue. When it cites "ADR-001" or "ADR-003", it is citing a decision
recorded in this directory.

## Numbering convention

ADRs are numbered sequentially: `ADR-001`, `ADR-002`, `ADR-003`, …

Rules:
- Numbers are **never reused**. If an ADR is superseded, the old number and
  file remain (with `status: superseded`). The new ADR gets the next available
  number.
- Numbers are **per-tree**. Compass's `architecture/decisions/` numbering
  starts at ADR-001. An adopting project's `architecture/decisions/` also
  starts at ADR-001 - these are different trees, different sequences.
- **Supersession** is via the `superseded_by` field, not by renumbering. If
  ADR-003 is replaced by a new decision, ADR-003 gains `superseded_by: ADR-007`
  and ADR-007 gains `supersedes: ADR-003`. The chain is navigable in both
  directions.
- The `compass adr new <slug>` subcommand assigns the next sequential number
  and registers the file here. In a multiagent orchestration with concurrent
  worktrees, two subtasks may produce the same number - the orchestrator
  resolves the conflict at integration by renumbering one side.

## Index

| ID | Title | Status | Principles covered |
|---|---|---|---|
| [ADR-001](ADR-001-judgement-and-mechanism-are-separated.md) | Judgement and mechanism are separated | accepted | Inv-1 (readings are sole judgement field), Inv-7 (mechanism is deterministic) |
| [ADR-002](ADR-002-framework-grows-by-adding-artifacts-not-rules.md) | The framework grows by adding artifacts and lenses, not by adding guardrails or routing dimensions | accepted | Inv-2 (five guardrails), Inv-3 (adaptive routing untouched) |
| [ADR-003](ADR-003-flow-advises-but-never-gates.md) | Flow advises but never gates | accepted | Inv-4 (Flow advises, never gates) |
| [ADR-004](ADR-004-one-spec-many-lenses.md) | One spec, many lenses; the lens annotates, never forks | accepted | Inv-5 (one spec, many lenses) |
| [ADR-005](ADR-005-state-lives-on-disk.md) | State lives on disk; conversation reconstructs from artifacts | accepted | Inv-6 (persistence over conversation) |
| [ADR-006](ADR-006-backward-compat-is-non-negotiable.md) | Backward compat is non-negotiable | accepted | Inv-8 (backward compat for projects without new surfaces) |
| [ADR-007](ADR-007-conditional-gate-promotion-via-floors.md) | Gates may be conditionally promoted from advisory to blocking via routing-policy floors; advisory gates write evidence but do not block Land | accepted | RP-REQUIRE-001/002, verify.analyze (advisory-by-default lifecycle) |
| [ADR-008](ADR-008-cross-task-derived-artifacts.md) | Cross-task derived artifacts are generated from landed task scenarios at Land time; the derivation is reconstructible, idempotent, and never a source-of-truth | accepted | Inv-5, Inv-6, Inv-8 (living spec, derived at Land, silent overwrite contract) |
| [ADR-009](ADR-009-fitness-functions-are-project-guardrails.md) | Architectural fitness functions are project guardrails, not framework guardrails | accepted | Inv-2 (five guardrails), Inv-8 (backward compat; nothing-to-check pass on zero declarations), ADR-007 reuse (verify.architecture floor promotion) |
| [ADR-010](ADR-010-governance-layers-rather-than-copies.md) | Project governance should layer over framework defaults rather than copy them | proposed | Inv-8 (backward compat - a file with no `extends:` must keep working); supersedes nothing, complements the drift-detection work |
| [ADR-011](ADR-011-enforced-file-types-are-project-configurable.md) | Which file types need a red should be project-configurable, not a fixed list | accepted | Inv-8 (backward compat - a project that configures nothing keeps today's behaviour); same floor-plus-opt-in shape as ADR-010 |
| [ADR-012](ADR-012-the-v2-vocabulary-freeze.md) | The v2 vocabulary is frozen - industry words only, enforced by the build; post-freeze changes need a decision record | accepted | governance/terminology.yml + tests/test_terminology.py (the ratchet); ADR-006 (break paid once behind a major version) |
| [ADR-013](ADR-013-vendored-third-party-code.md) | Compass may redistribute third-party code inside the plugin, and a bundled copy takes precedence over any system copy | accepted | Inv-8 (backward compat - TRC-F4/TRC-F5 hold no behaviour change); ADR-002 (no new guardrail or routing dimension added) |
| [ADR-014](ADR-014-retired-names-are-removed-at-the-major-version.md) | Retired names are removed at the major version rather than carried as redirects | superseded by ADR-019, ADR-020 | Inv-8 (backward compat - the break is paid once, behind a major version, per ADR-006); enables ADR-015 |
| [ADR-015](ADR-015-the-vocabulary-scan-covers-code-positions.md) | The vocabulary scan covers code positions, not only prose | superseded by ADR-018 | ADR-012 (the v2 vocabulary freeze - the scan is its enforcement); depends on ADR-014 |
| [ADR-016](ADR-016-id-codes-are-part-of-the-frozen-vocabulary.md) | Id prefixes are part of the frozen vocabulary, and routing rule ids say routing policy rather than guardrail | accepted | ADR-012 (extends the freeze from terms to codes); ADR-006 (the read side stays tolerant) |
| [ADR-017](ADR-017-an-identifier-is-a-key-not-jargon.md) | An identifier is a key, not jargon - attach its meaning, never delete the id | accepted | ADR-012 (amends a frozen `banned:` entry); ADR-016 (states the rule for using the prefixes it defines) |
| [ADR-018](ADR-018-the-scan-reads-every-position-by-default.md) | The vocabulary scan reads every position by default; an exclusion must be declared and reasoned | accepted | supersedes ADR-015; ADR-012 (the freeze this enforces); ADR-014 (removing retired names made it possible) |
| [ADR-019](ADR-019-retired-names-carry-redirects-once-there-are-adopters.md) | Retired names carry redirects once there are adopters | superseded by ADR-024 | supersedes ADR-014's redirect rule; ADR-006 (backward compat within a major version); ADR-015 (a retired name must not be a live teaching surface) |
| [ADR-020](ADR-020-the-archive-is-migrated-not-frozen.md) | The archive is migrated, not frozen | accepted | supersedes ADR-014's "archive as written" clause; ADR-006 (read-side compatibility) |
| [ADR-021](ADR-021-a-release-narrative-guard-retires-with-its-release.md) | A release narrative guard retires with its release | accepted | governance/strategies.md S10 (a guard is accepted on a demonstrated failure) |
| [ADR-022](ADR-022-the-issue-record-is-a-manifest.md) | The issue record is a manifest | accepted | amends ADR-012 (the freeze); ADR-006 (backward compat); ADR-020 (the archive is migrated on read) |
| [ADR-023](ADR-023-the-vocabulary-is-measured-against-anthropics-docs.md) | Where a term has a counterpart in Anthropic's platform docs, Compass uses their word with their meaning; otherwise plain English with no competing meaning | accepted | amends ADR-012 (the freeze, which had no reference text); ADR-015 (a retired name in printed output survives a green scan); ADR-019 (redirect stubs); ADR-020 (archive migrated on read); ADR-022 (a decision record keeps the words it was decided in) |
| [ADR-024](ADR-024-what-compass-owes-an-unobserved-adopter.md) | What Compass owes an unobserved adopter: a migration path, not a redirect - retired names are removed at the major version and redirects are not carried on an inferred adopter population | accepted | supersedes ADR-019 (which inferred a non-empty population from publication); ADR-006 (the principle, untouched - the break is paid at a major version); ADR-020 (the read-side rename tables stay because the archive needs them); Inv-8 (the no-op promise is carried forward and separated from migration compatibility) |
| [ADR-025](ADR-025-the-printed-plan-and-the-recorded-run-are-the-multiagent-interface.md) | The printed plan and the recorded run are the multiagent interface: Compass provisions, prints and records, the host launches the agents, and `multiagent-run-recorded` reads the record | accepted | answers `swarm-dispatch-is-a-protocol-not-a-script`; builds on the subtask record of `orchestrator-loop-hardening` |
| [ADR-026](ADR-026-ship-commit-lands-and-derives-the-living-spec.md) | `ship-commit` lands every issue and derives the living spec; `integrate.sh` only merges and runs the combined regression | accepted | amends ADR-008's first rule (where the derivation runs); needed by ADR-025's staged waves |

## Principle → ADR mapping

Compass holds eight architectural invariants. The table below is where they are
defined; everything else in `architecture/` cites them by id. Six ADRs cover
them:

| Invariant | Principle statement | ADR |
|---|---|---|
| Inv-1 | Assess is mandatory; the manifest's `assessment:` is the only judgement field | ADR-001 |
| Inv-2 | Five guardrails (G1–G5), not more | ADR-002 |
| Inv-3 | Adaptive routing is untouched; no new delivery approaches or dimensions added | ADR-002 |
| Inv-4 | Flow (cross-task signals) advises; it never gates or mutates | ADR-003 |
| Inv-5 | One spec (`acceptance-criteria.md`), many roles; roles annotate, never fork | ADR-004 |
| Inv-6 | Every mechanism output is a named file on disk (persistence over conversation) | ADR-005 |
| Inv-7 | The mechanism is deterministic; given the same inputs, the same outputs | ADR-001 |
| Inv-8 | Backward compat: every new mechanism no-ops on projects that haven't adopted it | ADR-006 |

## Authoring a new ADR

Use `compass adr new <slug>` or copy `templates/architecture/decisions/ADR-template.md`.
Required frontmatter fields: `id`, `title`, `status`, `date`, `supersedes`,
`superseded_by`. Required sections: Context, Decision, Alternatives considered,
Consequences, References.

A decision without alternatives is an assertion, not a record. Every ADR must
enumerate at least one alternative that was genuinely considered and rejected.
