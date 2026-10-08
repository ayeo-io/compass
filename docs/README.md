# Compass docs

Every doc in this folder, by what you came to do, and which doc owns the
facts about each code area. `tests/test_doc_router.py` fails when a path in
the table does not exist, and when a doc in this folder is not listed.

## Start here

- [index.md](index.md) - the documentation site's home page, at https://docs.ayeo.io/compass/.
- [five-minutes.md](five-minutes.md) - one small change from assessment to a reviewable result.
- [quickstart.md](quickstart.md) - from an empty machine to a finished first issue, and the status line and the rail.
- [roles-guide.md](roles-guide.md) - how product, design, engineering, marketing and QA each use Compass.
- [glossary.md](glossary.md) - every word and id prefix Compass uses.

## How Compass works

- [methodology.md](methodology.md) - the adaptive, spec-driven method and why it is built this way.
- [routing-deep-dive.md](routing-deep-dive.md) - how the assessment becomes a delivery approach.
- [safety-contract.md](safety-contract.md) - what Compass enforces, and what it does not claim.
- [refusal-codes.md](refusal-codes.md) - every reason the pre-tool hook can refuse with, generated.
- [multiagent-protocol.md](multiagent-protocol.md) - how a multiagent issue is run, step by step.
- [headless-runner.md](headless-runner.md) - `compass run`: one stage of one issue with nobody in the session.
- [delivery-record.md](delivery-record.md) - `compass record`: the delivery record kept in its own repository.
- [receipt.md](receipt.md) - the one-screen view of an issue's gates and evidence.
- [writing-specs-and-plans.md](writing-specs-and-plans.md) - a worked example of a spec and a plan.
- [system-spec.md](system-spec.md) - the current behaviour, derived from landed issues.
- [system-spec-archive.md](system-spec-archive.md) - superseded behaviour, derived.

## Running and maintaining Compass

- [install-smoke-test.md](install-smoke-test.md) - the checklist after an install or an install change.
- [releasing.md](releasing.md) - how to cut a release.
- [configuration.md](configuration.md) - every project setting: what it does, its values, its default and which file holds it.
- [policy-lint.md](policy-lint.md) - `compass policy lint` and `compass policy effective` on a layered project: the order of the checks, the finding codes and both JSON shapes.
- [check-implementations.md](check-implementations.md) - the version and fixture corpus of each check implementation, the build rule and what a major difference does.
- [policy-diff.md](policy-diff.md) - `compass policy diff`: the references, the sets it replays, `--open`, the exit codes and the JSON shape.
- [generation-store.md](generation-store.md) - the stored generation of an issue's configuration: its files, the commit order, the states and what reads it.
- [issue-configure.md](issue-configure.md) - `compass issue configure`: propose, preview, discard and recover a change to one issue's configuration, and how a reassess commits it.
- [policy-migrate.md](policy-migrate.md) - `compass policy migrate`: how copied governance and the old settings file become a `compass.yml` overlay over the release the copy came from, what it keeps, when it refuses, its exit codes and its JSON shape.
- [git-parents.md](git-parents.md) - a git parent in `extends:`: the pinned spelling, the fetch and cache, what Compass refuses and what an issue records.
- [policy-update.md](policy-update.md) - `compass policy update`: the major bump, the waiver re-check, the terminal re-approval, the exit codes and the JSON shape.
- [security.md](security.md) - what Compass adds to a repository, and how to review it.
- [portability.md](portability.md) - the adapter boundary, for running Compass outside Claude Code.

## Background

- [desired-state.md](desired-state.md) - where Compass is going.
- [case-study-compass-rebuilt-itself.md](case-study-compass-rebuilt-itself.md) - what Compass's own record shows.
- [launch-article.md](launch-article.md) - the launch article.

## Owning docs

Each area's facts live in one doc. Change the code, change the doc, in the
same commit.

| Area | Owning doc |
|---|---|
| `hooks/`, `compass-contract.md` | `docs/safety-contract.md` |
| `cli/compass_pkg/refusals.py` | `docs/refusal-codes.md` |
| `cli/compass_pkg/project_settings.py` | `docs/configuration.md` |
| `cli/compass_pkg/catalogue_spec.py`, `cli/compass_pkg/catalogue_check.py`, `schemas/compass.schema.json` | `architecture/decisions/ADR-035-delivery-approaches-stages-and-modes-are-configuration.md` |
| `cli/compass_pkg/legacy_adapter.py`, `cli/compass_pkg/legacy_views.py`, `cli/compass_pkg/legacy_views_template.py`, `scripts/generate-legacy-views.py`, `governance/presets/default/`, `tests/fixtures/preset-digests.yml` | `governance/routing-policy.md` |
| `cli/compass_pkg/vocabulary.py` | `architecture/decisions/ADR-035-delivery-approaches-stages-and-modes-are-configuration.md` |
| `cli/compass_pkg/stable_ids.py`, `tests/test_stable_ids.py` | `architecture/decisions/ADR-040-stable-ids-live-in-one-module.md` |
| `cli/compass_pkg/atomic_io.py` | `architecture/decisions/ADR-036-an-issue-runs-against-a-stored-generation.md` |
| `cli/compass_pkg/obligations.py` | `architecture/decisions/ADR-037-configuration-changes-are-classified-by-effect.md` |
| `cli/compass_pkg/classify.py`, `scripts/bench-classifier.py` | `governance/routing-policy.md` |
| `cli/compass_pkg/policy_lint.py`, `cli/compass_pkg/policy_cmd.py` | `docs/policy-lint.md` |
| `cli/compass_pkg/generation.py`, `cli/compass_pkg/effective.py`, `cli/compass_pkg/impl_versions.py`, `scripts/bench-evaluate.py` | `docs/generation-store.md` |
| `scripts/impl-coverage.py`, `tests/fixtures/impls/versions.lock.yml` | `docs/check-implementations.md` |
| `cli/compass_pkg/issue_config_cmd.py`, `cli/compass_pkg/config_preview.py` | `docs/issue-configure.md` |
| `cli/compass_pkg/replay.py` | `docs/policy-diff.md` |
| `cli/compass_pkg/policy_migrate.py`, `cli/compass_pkg/shipped_releases.py`, `scripts/generate-shipped-releases.py`, `governance/shipped-releases.yml`, `governance/shipped-releases.tar.xz` | `docs/policy-migrate.md` |
| `cli/compass_pkg/parents.py`, `cli/compass_pkg/parent_states.py` | `docs/git-parents.md` |
| `cli/compass_pkg/policy_update.py` | `docs/policy-update.md` |
| `cli/compass_pkg/waivers.py` | `architecture/decisions/ADR-039-waivers-locks-and-unlocks.md` |
| `cli/compass_pkg/layers.py`, `cli/compass_pkg/merge.py` | `architecture/decisions/ADR-035-delivery-approaches-stages-and-modes-are-configuration.md` |
| `cli/compass_pkg/locks.py` | `governance/guardrails.md` |
| `cli/compass_pkg/routing.py`, `cli/compass_pkg/approach_diagram.py`, `governance/routing-policy.yml`, `approaches/`, `docs/approach-diagram.html` | `governance/routing-policy.md` |
| `cli/compass_pkg/checks.py`, `cli/compass_pkg/check_cmd.py`, `cli/compass_pkg/check_registry.py`, `governance/guardrails.yml` | `governance/guardrails.md` |
| `governance/strategies.md` | `governance/strategies-rationale.md` |
| `governance/terminology.yml` | `docs/glossary.md` |
| `commands/`, `agents/`, `schemas/` | `skills/compass-runtime/SKILL.md` |
| `cli/compass_pkg/tdd.py`, `cli/compass_pkg/evidence_identity.py` | `skills/evidence-gates/SKILL.md` |
| `cli/compass_pkg/subtasks.py`, `cli/compass_pkg/loop_ceilings.py`, `cli/compass_pkg/multiagent_check.py`, `scripts/multiagent.sh`, `scripts/integrate.sh` | `docs/multiagent-protocol.md` |
| `cli/compass_pkg/run_cmd.py`, `cli/compass_pkg/host_launch.py`, `cli/compass_pkg/redact.py`, `cli/compass_pkg/compliance.py`, `ci/headless-verify.yml` | `docs/headless-runner.md` |
| `cli/compass_pkg/record.py` | `docs/delivery-record.md` |
| `cli/compass_pkg/rival_names.py`, `scripts/rival-name-gate.py`, `scripts/rival-name-hashes.txt`, `scripts/rival-name-binary-pins.txt` | `governance/decisions/2026-10-07-checked-binaries-are-pinned-in-the-rival-name-gate.md` |
| `cli/compass_pkg/flow.py`, `cli/compass_pkg/spec_refresh.py`, `docs/system-spec.md`, `docs/system-spec-archive.md` | `architecture/decisions/ADR-026-ship-commit-lands-and-derives-the-living-spec.md` |
| `cli/compass_pkg/next_cmd.py`, `cli/compass_pkg/render.py`, `cli/compass_pkg/statusline.py`, `bin/compass-statusline` | `docs/quickstart.md` |
| `cli/compass_pkg/receipt.py` | `docs/receipt.md` |
| `cli/compass`, `cli/compass_pkg/verb_help.py`, `cli/compass_pkg/lineage.py` | `README.md` |
| `scripts/release.sh`, `Makefile`, `VERSION` | `docs/releasing.md` |
| `scripts/install.sh`, `.claude-plugin/` | `docs/install-smoke-test.md` |
| `hooks/hooks.json`, the adapter boundary | `docs/portability.md` |
| `cli/compass_pkg/project_commands.py`, `cli/compass_pkg/trust.py` | `docs/security.md` |
| `evals/` | `evals/README.md` |
| `ci/` | `ci/README.md` |
| `architecture/` | `architecture/decisions/README.md` |
