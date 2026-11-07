# Compass docs

Every doc in this folder, by what you came to do, and which doc owns the
facts about each code area. `tests/test_doc_router.py` fails when a path in
the table does not exist, and when a doc in this folder is not listed.

## Start here

- [index.md](index.md) - the documentation site's home page, at https://docs.ayeo.io/compass/.
- [five-minutes.md](five-minutes.md) - one small change from assessment to a reviewable result.
- [quickstart.md](quickstart.md) - from an empty machine to a finished first issue, and the status line and the rail.
- [glossary.md](glossary.md) - every word and id prefix Compass uses.
- [cli.md](cli.md) - the CLI reference: one line per verb, and how the slash commands call them.

## How Compass works

- [methodology.md](methodology.md) - the adaptive, spec-driven method and why it is built this way.
- [routing-deep-dive.md](routing-deep-dive.md) - how the assessment becomes a delivery approach.
- [safety-contract.md](safety-contract.md) - what Compass enforces, and what it does not claim.
- [refusal-codes.md](refusal-codes.md) - every reason the pre-tool hook can refuse with, generated.
- [artifact-catalog.md](artifact-catalog.md) - the artifact catalog: the fields of a kind, the skeleton, the word limits, the documents that repeat, the documents per work unit and the table of shipped kinds.
- `artifact-catalogue.md` - the old name of the artifact catalog page, kept until 9.0.0 so a link to it opens the new page.
- [delivery-record.md](delivery-record.md) - `compass record`: the delivery record kept in its own repository.
- [checkpoints.md](checkpoints.md) - checkpoint outcomes and the `checkpoint-approval` record: their shapes, the two commands that write them, the landing refusal, and where `compass issue diagnose` and the delivery record show them.
- [release-line.md](release-line.md) - the release line each shipping issue records: the `release_note` key, the three commands that write it, the texts they refuse, when a landing refuses an issue with none, and where the line is shown.
- [release-notes.md](release-notes.md) - `compass release notes --since <ref>`: which completed issues it lists against a git reference, the order, the two closing count lines, and what it never writes.
- [github-links.md](github-links.md) - `compass issue link set`: an issue's link to its GitHub issue and its pull request, how `land_commit` follows the merge, how `gh` is run, and the limits.
- [writing-specs-and-plans.md](writing-specs-and-plans.md) - a worked example of a spec and a plan.

## Running and maintaining Compass

- [install-smoke-test.md](install-smoke-test.md) - the checklist after an install or an install change.
- [adapter-conformance.md](adapter-conformance.md) - local behaviour checks and the separate native and independent acceptance runs.
- [releasing.md](releasing.md) - how to cut a release.
- [upgrade-6-0-0.md](upgrade-6-0-0.md) - the words, keys and commands that 6.0.0 renames, what reads the old form until 9.0.0, and why there is no supported rollback.
- [upgrade-7-0-0.md](upgrade-7-0-0.md) - what 7.0.0 changes and what to do about it, one section per change.
- [upgrade-8-0-0.md](upgrade-8-0-0.md) - what 8.0.0 changes about delegation, and what breaks: the flag form, `--issue` on a delegated approval and the common store.
- [configuration.md](configuration.md) - every project setting: what it does, its values, its default and which file holds it, and the five tighten-only settings that add to the check set.
- [waivers.md](waivers.md) - a waiver of one check on one issue: how to ask for one, how a person approves it and what `compass check` then shows.
- [policy-lint.md](policy-lint.md) - `compass policy lint` and `compass policy show`: the settings lint of `compass.yml`, the legacy lint of a governance copy, the finding codes and both JSON shapes.
- [check-implementations.md](check-implementations.md) - the version and fixture corpus of each check implementation, the build rule and what a major difference does.
- [generation-store.md](generation-store.md) - the stored generation of an issue's policy: its files, the manifest's `policy:` block, the commit order, the states and what reads it.
- [entry-exit-evaluation.md](entry-exit-evaluation.md) - the capability that evaluates each stage's entry and exit lists: when a list is due, how each kind of check is judged, what `on_skipped` does and where results show.
- [judged-checks.md](judged-checks.md) - a check of kind `judged`, its review record and `compass evidence review`: what a judged check needs to pass, the four failure causes, how a changed input re-owes the review and the JSON shape.
- [issue-dependencies.md](issue-dependencies.md) - `depends_on` and `compass issue depends add|remove`: the entry shape, the nine `until` values, when the block counts at implement, what the hook reads and what it costs, the fail-safe cases, the worktree rule and what each reader shows.
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
| `tests/adapter_conformance/`, `tests/test_adapter_behaviour.py` | `docs/adapter-conformance.md` |
| `hooks/`, `compass-contract.md`, `cli/compass_pkg/approval_guard.py`, `cli/compass_pkg/approval_words.py` | `docs/safety-contract.md` |
| `cli/compass_pkg/tip_scope.py` | `docs/safety-contract.md` |
| `cli/compass_pkg/ship_commit_reason.py` | `docs/safety-contract.md` |
| `cli/compass_pkg/manifest_store.py` | `docs/safety-contract.md` |
| `cli/compass_pkg/comment_only_edit.py` | `docs/safety-contract.md` |
| `cli/compass_pkg/refusals.py` | `docs/refusal-codes.md` |
| `cli/compass_pkg/release_line.py` | `docs/release-line.md` |
| `cli/compass_pkg/release_notes.py`, `cli/compass_pkg/shipped_issues.py` | `docs/release-notes.md` |
| `cli/compass_pkg/project_settings.py`, `cli/compass_pkg/tighten.py`, `cli/compass_pkg/settings_lint.py`, `cli/compass_pkg/catalogue_spec.py`, `schemas/compass.schema.json`, `tests/test_tighten.py`, `tests/test_settings_lint.py` | `docs/configuration.md` |
| `cli/compass_pkg/legacy_adapter.py`, `governance/presets/default@6/`, `governance/presets/default@7/`, `tests/fixtures/preset-digests.yml` | `governance/routing-policy.md` |
| `cli/compass_pkg/stable_ids.py`, `cli/compass_pkg/gate_status.py`, `tests/test_stable_ids.py` | `architecture/decisions/ADR-040-stable-ids-live-in-one-module.md` |
| `cli/compass_pkg/path_stages.py`, `cli/compass_pkg/path_readers.py`, `tests/test_path_stages.py`, `tests/test_path_checks.py` | `architecture/decisions/ADR-092-compass-runs-one-path-of-four-stages.md` |
| `cli/compass_pkg/atomic_io.py` | `architecture/decisions/ADR-036-an-issue-runs-against-a-stored-generation.md` |
| `cli/compass_pkg/obligations.py` | `governance/routing-policy.md` |
| `cli/compass_pkg/policy_cmd.py`, `cli/compass_pkg/readiness_registry.py` | `docs/policy-lint.md` |
| `cli/compass_pkg/generation.py`, `cli/compass_pkg/effective.py`, `cli/compass_pkg/impl_versions.py`, `scripts/bench-evaluate.py` | `docs/generation-store.md` |
| `scripts/impl-coverage.py`, `tests/fixtures/impls/versions.lock.yml` | `docs/check-implementations.md` |
| `cli/compass_pkg/issue_depends.py` | `docs/issue-dependencies.md` |
| `cli/compass_pkg/stage_lists.py`, `cli/compass_pkg/item_records.py`, `cli/compass_pkg/follow_up_cmd.py`, `cli/compass_pkg/doc_sections.py`, `cli/compass_pkg/approval_records.py`, `cli/compass_pkg/approvals.py`, `cli/compass_pkg/approval_requests.py`, `cli/compass_pkg/prompt_approval.py`, `cli/compass_pkg/delegations.py`, `cli/compass_pkg/delegation_tickets.py`, `cli/compass_pkg/worktree_lookup.py`, `cli/compass_pkg/approve_cmd.py`, `tests/test_human_checks.py`, `tests/fixtures/evidence-approve-example.json` | `docs/entry-exit-evaluation.md` |
| `cli/compass_pkg/artifact_kinds.py`, `cli/compass_pkg/justifications.py`, `templates/*.md` | `docs/artifact-catalog.md` |
| `cli/compass_pkg/review_records.py`, `cli/compass_pkg/review_cmd.py`, `tests/fixtures/evidence-review-example.json` | `docs/judged-checks.md` |
| `cli/compass_pkg/waiver_records.py`, `cli/compass_pkg/waiver_cmd.py`, `tests/test_waiver_records.py` | `docs/waivers.md` |
| `cli/compass_pkg/check_set.py`, `governance/check-set.yml`, `tests/fixtures/check-set-digests.yml`, `tests/test_check_set_content.py` | `governance/guardrails.md` |
| `cli/compass_pkg/routing.py`, `cli/compass_pkg/g5_label_prompt.py`, `cli/compass_pkg/approach_diagram.py`, `governance/routing-policy.yml`, `approaches/`, `docs/approach-diagram.html` | `governance/routing-policy.md` |
| `cli/compass_pkg/checks.py`, `cli/compass_pkg/dod_due.py`, `cli/compass_pkg/check_cmd.py`, `cli/compass_pkg/check_registry.py`, `cli/compass_pkg/red_first.py`, `governance/guardrails.yml` | `governance/guardrails.md` |
| `governance/strategies.md` | `governance/strategies-rationale.md` |
| `governance/terminology.yml` | `docs/glossary.md` |
| `commands/`, `schemas/` | `skills/compass-runtime/SKILL.md` |
| `cli/compass_pkg/tdd.py`, `cli/compass_pkg/tdd_green.py`, `cli/compass_pkg/green_attempts.py`, `cli/compass_pkg/evidence_identity.py`, `cli/compass_pkg/evidence_sums.py` | `skills/evidence-gates/SKILL.md` |
| `cli/compass_pkg/loop_ceilings.py` | `governance/routing-policy.md` |
| `cli/compass_pkg/evidence_required.py`, `cli/compass_pkg/path_writer.py`, `tests/fixtures/compat/v8.0.4-governance.tgz`, `tests/test_path_writer.py`, `tests/test_quick_fix_path.py` | `governance/routing-policy.md` |
| `cli/compass_pkg/record.py`, `cli/compass_pkg/redact.py` | `docs/delivery-record.md` |
| `cli/compass_pkg/checkpoint_outcomes.py` | `docs/checkpoints.md` |
| `cli/compass_pkg/issue_link.py`, `cli/compass_pkg/github_links.py`, `cli/compass_pkg/pull_request_link.py`, `tests/fake_gh.py` | `docs/github-links.md` |
| `cli/compass_pkg/status_words.py`, `cli/compass_pkg/lifecycle.py`, `cli/compass_pkg/status_cmd.py` | `architecture/decisions/ADR-045-the-issue-lifecycle-is-derived-from-records.md` |
| `cli/compass_pkg/decisions_taken.py` | `architecture/decisions/ADR-050-artifact-status-is-written-by-stage-exits-and-by-a-persons-approval.md` |
| `cli/compass_pkg/rendered_blocks.py`, `cli/compass_pkg/issue_detail.py`, `cli/compass_pkg/project_scan.py`, `cli/compass_pkg/migrate_blocks.py`, `cli/compass_pkg/doc_paths.py` | `docs/rendered-blocks.md` |
| `cli/compass_pkg/record_triggers.py`, `cli/compass_pkg/command_guard.py` | `docs/generation-store.md` |
| `cli/compass_pkg/section_checks.py`, `cli/compass_pkg/outside_gate.py`, `cli/compass_pkg/spec_location.py` | `governance/guardrails.md` |
| `cli/compass_pkg/acceptance_strategy.py`, `cli/compass_pkg/outer_loop.py`, `cli/compass_pkg/candidate_client.py`, `cli/compass_pkg/isolation.py`, `cli/compass_pkg/layering.py`, `cli/compass_pkg/strategy_records.py` | `governance/guardrails.md` |
| `cli/compass_pkg/support_code.py` | `governance/guardrails.md` (the check and the claim limit) |
| `cli/compass_pkg/migrate.py`, `cli/compass_pkg/migrate_kinds.py`, `cli/compass_pkg/migrate_copy_check.py` | `architecture/decisions/ADR-056-the-migrate-maps-documents-by-a-table-and-registers-before-it-moves.md`, `docs/upgrade-7-0-0.md` |
| `cli/compass_pkg/parse_cache.py` | `architecture/decisions/ADR-049-bulk-manifest-reads-use-a-parse-cache-keyed-on-content.md`, widened by `architecture/decisions/ADR-052-the-parse-cache-serves-the-render-as-well-as-flow.md` |
| `cli/compass_pkg/rival_names.py`, `scripts/rival-name-gate.py`, `scripts/rival-name-hashes.txt`, `scripts/rival-name-binary-pins.txt` | `governance/decisions/2026-10-07-checked-binaries-are-pinned-in-the-rival-name-gate.md` |
| `cli/compass_pkg/flow.py` | `docs/cli.md` |
| `cli/compass_pkg/next_cmd.py`, `cli/compass_pkg/render.py`, `cli/compass_pkg/statusline.py`, `bin/compass-statusline` | `docs/quickstart.md` |
| `cli/compass_pkg/next_step.py`, `cli/compass_pkg/next_line.py`, `tests/test_next_step.py` | `docs/quickstart.md` (the table of next commands) |
| `cli/compass`, `cli/compass_pkg/verb_help.py`, `cli/compass_pkg/lineage.py` | `README.md` |
| `scripts/release.sh`, `scripts/build-plugin-copy.py`, `scripts/plugin-files.txt`, `.claude-plugin/marketplace.json`, `Makefile`, `VERSION` | `docs/releasing.md` |
| `.github/workflows/`, `scripts/ci-*.py` | `docs/releasing.md` |
| `examples/atdd-adapters/python/`, `tests/acceptance/atdd_strategy/test_reference_example.py` | `examples/atdd-adapters/python/README.md` |
| `examples/atdd-adapters/typescript/`, `tests/acceptance/atdd_strategy/typescript.py` | `examples/atdd-adapters/typescript/README.md` |
| `cli/compass_pkg/pytest_report.py` | `architecture/decisions/ADR-087-a-runner-that-is-not-pytest-writes-its-junit-report-where-compass-names-it.md` |
| `scripts/render-document-set.py`, `architecture/document-set-7-0-0.svg`, `tests/test_document_set_diagram.py` | `docs/methodology.md` |
| `scripts/install.sh`, `.claude-plugin/` | `docs/install-smoke-test.md` |
| `hooks/hooks.json`, the adapter boundary | `docs/portability.md` |
| `cli/compass_pkg/project_commands.py`, `cli/compass_pkg/trust.py` | `docs/security.md` |
| `ci/` | `ci/README.md` |
| `architecture/` | `architecture/decisions/README.md` |
