---
id: ADR-008
title: Cross-task derived artifacts are generated from landed task scenarios at Land time; the derivation is reconstructible, idempotent, and never a source-of-truth
status: accepted
date: 2026-05-25
supersedes: ''
superseded_by: ''
---

> **Vocabulary note (ADR-023, 2026-08-27):** this record's *Land* is now
> **ship**; `route.md` is now `delivery-approach.md`; `spec.feature.md` is
> now `acceptance-criteria.md`; `plan.md` is now `technical-design.md`;
> `task.yml` is now `manifest.yml`; the *lens* is now the **role**. The
> record keeps the words it was decided in; only the names have moved.

> **Amended by ADR-026 (2026-09-25):** the derivation now runs in
> `ship-commit`, after it marks an issue landed, and `integrate.sh` no longer
> derives or marks anything landed. Rules 2 to 4 below stand.

## Context

Every artifact Compass produces today is **per-task**: `route.md`, `spec.feature.md`, `plan.md`, `verification-report.md`, `task.yml`, and so on all live under a single `.compass/work/<task>/` directory and describe one task's slice of work. The framework has no first-class concept of a **cross-task** artifact - a single document derived from many tasks' outputs.

The "living system spec" capability is the first such cross-task artifact. The requirement: the framework leaves behind *a durable, current description of the system derived from scenarios as they land* - not a pile of task directories, and not a document a human maintains by hand.

Two specific risks need to be addressed:

- **Treating the derived artifact as a second canonical spec** - a future agent or human edits `docs/system-spec.md` and the framework now has two competing sources of truth. This is the same risk `architecture-notes.md` files run against `spec.feature.md`, resolved there by the "lens annotates, never forks" pattern (ADR-004).
- **In-memory derivation state that is not reconstructible from disk** - if the derivation accumulates ephemeral state during `scripts/integrate.sh` execution, the artifact can drift from what the landed task.ymls actually contain, and cold reconstruction is impossible. ADR-005 (state lives on disk) applies and must be honoured for the derivation's inputs too.

The framework also needs landed-task state to stay in place (no `.compass/archive/` directory; ADR-006 keeps backward compatibility through optional fields) and needs the derivation invocation not to introduce a new public CLI verb (the public CLI surface stays capped at `analyze` and `next`).

## Decision

Cross-task derived artifacts follow four invariants:

1. **Derived at Land.** Derivation runs as the final step of `scripts/integrate.sh`, after combined-regression green and the worktree merge. It is invoked through a private CLI entry point `compass _derive-system-spec --internal` whose subcommand name begins with `_` and is omitted from `compass --help`. The public CLI verb count is unchanged.

2. **Reconstructible from landed-task state alone.** The derivation reads `.compass/work/<issue>/task.yml` for every task whose `task.yml.status == 'landed'` and that file's linked `spec.feature.md`. No intermediate state, cache, or registry exists outside `.compass/work/`. Deleting `docs/system-spec.md` and re-running the derivation produces a byte-identical file. The `task.yml.status` field is a new schema field added under ADR-006's backward-compat contract: absent or `'1.0'`-schema files default to `active` (not landed), so the derivation excludes them.

3. **Idempotent and deterministically ordered.** Re-running the derivation against unchanged inputs yields a byte-identical artifact. Tasks are processed in Land-timestamp order, with task slug as the tiebreaker for ties. Supersession follows a defined algorithm: scenarios sharing an intent id across tasks → latest-landed wins for the current-behaviour section, earlier moves to an archived-behaviour appendix with task slug and Land date recorded against the entry. Scenarios whose intent ids drift across tasks (a renaming refactor) cannot be auto-reconciled and surface as "potential supersession" advisories - the only human-judgement gap in the algorithm.

4. **Never a source-of-truth.** The derived artifact carries a header on its first line: `DERIVED FILE - do not hand-edit; edit .compass/work/<task>/spec.feature.md`. Hand-edits to the derived file are silently overwritten by the next Land. The source-of-truth is, and remains, the per-task `spec.feature.md` files plus their `task.yml.scenarios` index. This is the same relationship `architecture-notes.md` has to `spec.feature.md` (ADR-004 - lens annotates, never forks) extended one level up: a derived cross-task artifact annotates the corpus of per-task specs, but does not replace them.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Make `docs/system-spec.md` an editable canonical spec maintained alongside the per-task specs | Familiar pattern; humans can refine the language | Re-introduces hand-maintenance, and the file goes out of date, and it violates the "derived not hand-maintained" requirement. Creates two competing sources of truth for the same behaviour, exactly the failure mode ADR-004 was written to prevent |
| Derive at every gate, not only at Land | The artifact is always current, not stale between Lands | Adds derivation overhead to every gate transition; the artifact's job is to describe what is *in production*, which by definition is only updated by Land. Pre-Land derivation describes work-in-progress, which is precisely what `spec.feature.md` is for |
| Cache derived state in `.compass/cache/system-spec.json` and reconstruct only on cache miss | Faster derivation; explicit reconstruction trigger | Adds a new on-disk concept (cache directory); creates a second source of truth (the cache); breaks "reconstructible from landed-task state alone." The simplest-thing strategy (`S3`) rules against caching until proven necessary |
| Maintain a `.compass/landed/<task>.json` summary file at Land instead of a `status` field on `task.yml` | Compact derivation input; separates landed from active state cleanly | Adds a new on-disk artifact type (one more file every issue must write); duplicates information already in `task.yml`; breaks the "no second source of truth" rule that `task.yml.scenarios` is canonical |

## Consequences

**Positive:**
- The framework can now produce cross-task artifacts using a documented pattern. Future capabilities (e.g. a cross-task review of which guardrails fire most often, a digest of recent behaviour changes for changelog purposes) can follow the same pattern.
- The derived artifact is always current relative to the latest Land and always reconstructible cold from `.compass/work/`. Deletion is recoverable; corruption is rederivable.
- The public CLI surface is unchanged. The private-entry-point convention (`_<name>`) establishes a pattern for future internal-only CLI calls.
- The backward-compat story is clean: old `task.yml` files without `status` are treated as not-landed, so adopter projects upgrading do not see their old work suddenly appear in the system spec.

**Negative:**
- The `task.yml` schema gains a field (`status`), and `schema_version` bumps to `'1.1'`. Adopters who check task.ymls in their own tooling against the published schema will need to update.
- The supersession algorithm cannot auto-reconcile cases where intent ids drift across tasks; those cases surface as "potential supersession" advisories that a human must inspect. The framework accepts this gap deliberately - automated intent-id reconciliation would risk silently merging genuinely-different behaviours.
- The private-entry-point convention (`_<name>`) is invisible to `compass --help` users but visible to anyone reading `cli/compass`. It must be clearly documented in the file's header comment.

**Neutral / follow-on:**
- The `archive/<behaviour-id>.md` appendix structure of `docs/system-spec.md` may need its own structural conventions as the spec grows. The first task to land >100 archived behaviours will reveal whether a flat appendix scales, or whether per-intent grouping is needed.
- `compass retro` (which already walks all `task.yml` files) shares infrastructure with the derivation walker. If a future change generalises the "walk all task.yml" operation, both should adopt it.

## References

- `ADR-004` (one spec, many lenses; the lens annotates, never forks - the analogous pattern at the per-task level)
- `ADR-005` (state lives on disk; conversation reconstructs from artifacts - the reconstructibility invariant)
- `ADR-006` (backward compat is non-negotiable; every new mechanism no-ops cleanly - the schema migration discipline)
- `scripts/integrate.sh` - the Land integration script the derivation hooks into
- `schemas/manifest.schema.json` - the schema gaining the `status` field
