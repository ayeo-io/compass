# Compass - Releasing

This page is the maintainer's procedure for a Compass release, the record of what
each major release changed, and the description of this repository's CI.
[`scripts/release.sh`](../scripts/release.sh) does the packaging.

---

## The release procedure

**Compass follows semantic versioning.**

- **major** - something a caller could call stops working. Removing a command,
  a verb, a flag spelling or a manifest key is a major, however small the diff.
- **minor** - new capability, nothing removed.
- **patch** - a fix that changes no interface.

Backward compatibility holds within a major (ADR-006). A new mechanism does
nothing on a project that has not adopted it. When a change looks like it forces
a major, you can remove the break, for example by normalizing old manifests on
read. Do not redefine the break.

Before the release notes name a cost or token ratio, `sdd-bench-9-0-0.md` in
`docs/` must record a pass. No test scans the GitHub release body, the
repository description or the ayeo.io page, so check them by hand.

### The steps

1. **Bump the version** in every location that carries it. There are seven:

   | Location | Guarded by |
   |---|---|
   | `VERSION` (root) | `tests/test_version_consistency.py` |
   | `COMPASS_VERSION` in `cli/compass` | `tests/test_version_consistency.py` |
   | `COMPASS_VERSION` in `cli/compass_pkg/core.py` | `tests/test_version_consistency.py`, and `cli/compass` asserts equality with it at import time |
   | `.claude-plugin/plugin.json` `$.version` | `tests/test_version_consistency.py` |
   | `.claude-plugin/marketplace.json` `$.metadata.version` | `tests/test_version_consistency.py` |
   | `.claude-plugin/marketplace.json` `$.plugins[0].version` | `tests/test_version_consistency.py` |
   | The expected `compass --version` output in `docs/install-smoke-test.md` | `tests/test_version_consistency.py` and `tests/test_cli_surface_drift.py` |

   **And one more edit:** `EXPECTED_VERSION` in
   `tests/test_version_consistency.py`. It is hardcoded so that a release
   where nothing was bumped fails. Without this edit the suite is red.
   `tests/test_version_guard_covers_every_location.py` derives the locations
   from the files and fails when the guard has no case for one. Run the suite
   after this step.

2. **`make clean`** - removes `__pycache__`, `*.bak`, `.DS_Store`,
   `.pytest_cache`, `_deltest` and `pytest-cache-files-*`. The release tarball
   must not carry any of these.

3. **`make test`** - must be green. It runs on parallel workers when
   `pytest-xdist` is installed (`pip install pytest-xdist`). If a drift-guard
   test fails, such as `tests/test_cli_surface_drift.py` or
   `tests/test_release_invariants.py`, a public document does not match the
   code. Fix the document, run again, then continue.

4. **`make ci`** - must be green. It runs `compass policy lint`, then `issue
   lint` on every issue under `.compass/work/` and `check` on the issues in
   flight or landed since the last release tag (`compass ci --since <tag>`).
   Once per release, run `COMPASS_FULL_ARCHIVE=1 make ci`, which checks every
   issue, and `COMPASS_FULL_ARCHIVE=1 make test`. The archive tests then read
   every local issue instead of the tracked sample,
   `tests/fixtures/archive-sample.tar.gz`, and the citation tests run.

5. **`make release`** - writes `dist/compass-<version>.tar.gz`. The release
   script:
   - clears `dist/` of any earlier tarball;
   - runs `validate.sh`, `policy lint`, the test suite and the
     examples-present check before it packages;
   - fails with exit 1 when the tarball holds a noise file (`.DS_Store`,
     `__MACOSX`, `__pycache__`, `*.bak`, `.pytest_cache`, `_deltest`,
     `pytest-cache-files-*`);
   - fails when a worked example under `examples/` lacks its
     `.compass/work/<slug>/manifest.yml`.

6. **Inspect the tarball.** Read `tar -tzf dist/compass-<version>.tar.gz | less`,
   even when the script's checks passed.

7. **Publish only the tarball from step 5.** Do not zip the source tree with
   Finder, GitHub's "Download ZIP" or any other tool. Those include local
   noise files.

8. **Check the tarball out of the source tree.** All four commands must
   succeed:

   ```bash
   cp dist/compass-<version>.tar.gz /tmp/
   cd /tmp && tar -xzf compass-<version>.tar.gz
   cd compass-<version>
   bash scripts/validate.sh
   python3 cli/compass policy lint
   python3 cli/compass ci
   ```

9. **Check the queue against this release.** Run `compass flow --digest` and
   read its queue aging line and table. For each backlog issue that touches
   what this release changes, pull it in or say why it waits. Put the answer
   in the release notes under "Queued against this release", or write "None"
   there.

10. **Tag and publish.** `governance/shipped-releases.tar.xz` is frozen. A
   release adds nothing to it, because 9.0.0 removed `compass policy migrate`,
   which read it (ADR-094).

11. **Publish the plugin copy.** Users and the plugin directory install
   Compass from the `plugin` branch, which `.claude-plugin/marketplace.json`
   names. Each commit on that branch holds the files one release ships. After
   the tag, run:

   ```bash
   git fetch origin plugin:plugin
   python3 scripts/build-plugin-copy.py --ref v<version> --commit
   git push origin plugin
   ```

   - Never force-push `plugin`.
   - `--commit` takes only a `vX.Y.Z` tag newer than the release the branch
     holds. It refuses a local branch that is missing or behind
     `origin/plugin`.
   - The script reads the tag's tracked files and keeps only the files
     `scripts/plugin-files.txt` lists. It refuses a copy with more than 512
     files, a non-image file over 256 KiB, a version that differs from the
     tag, or a `${CLAUDE_PLUGIN_ROOT}` path that is not in the copy.
   - `make release` runs the same check against `HEAD` at step [4b].

### Checks for 6.0.0

Run these on top of steps 1 to 9, before step 10.

1. **A full run with the whole archive.** `COMPASS_FULL_ARCHIVE=1 make test`
   and `COMPASS_FULL_ARCHIVE=1 make ci`.
2. **The six compatibility contracts.** Each is compared with a baseline
   captured once from 5.6.0: routing output, what each delivery approach owes,
   `compass check` verdicts on archived issues, CLI exit codes on a recorded
   command corpus, pre-tool hook decisions on a recorded corpus, and old
   manifests, evidence and receipts staying readable. The tests are
   `tests/test_compat_contracts.py` (A), `tests/test_compat_configurations.py`
   (B and C), `tests/test_compat_contract_4.py` and
   `tests/test_compat_contract_5.py`. Each contract must hold under these
   configurations:
   - **A.** No configuration: the shipped default alone. Contracts 1 and 2
     read a copy of the 8.0.4 shipped governance in its place
     (`tests/fixtures/compat/v8.0.4-governance.tgz`), because 9.0.0 replaces
     the approaches they compare (ADR-092).
   - **B.** An empty overlay: a `compass.yml` that holds only `schema: 1` and
     `extends: compass:default@6`. Two corpus entries are left out under B:
     `policy-test-no-preset` and `policy-update-no-project-file`.
   - **C.** A copy of the 5.6.0 shipped governance files
     (`tests/fixtures/compat/v5.6.0-governance.tgz`), run through the legacy
     adapter.
   - **D.** Contracts 4 and 5 only: the same project with a 5.6.0
     `.compass/config.yml`, and again after `compass policy migrate` has moved
     its settings into `compass.yml`.

   Where B and C differ from A:
   - Contract 1 allows three spellings: the layered path prints `intent`,
     `launch-readiness` and `ship` where 5.6.0 printed `intent.md`,
     `launch-readiness.md` and `land`.
   - Contract 4 leaves out an entry whose project state already holds a
     settings file or governance of its own, every `policy migrate` entry, and
     the `terminology` entries under C.
   - Contract 5 runs the hook corpus with the settings in a `compass.yml` (B),
     and with the 5.6.0 governance copy beside `.compass/config.yml` (C).
   - Each parametrization has a partner test that plants a fault and expects a
     difference.
3. **The framework's own file.** `tests/test_framework_compass_yml.py` fails
   when this repository's `compass.yml` holds a catalog key, a waiver, an
   unlock or a capability. `tests/test_old_settings_file_sweep.py` and
   `tests/test_settings_prose.py` fail when a source or a document names
   `.compass/config.yml` without `compass.yml` or the state file.
4. **The verbs the notes name exist.** For every command the release notes
   name, check that `compass <verb> --help` runs.
5. **Release notes.** The notes are the body of the GitHub release, which the
   repository does not track. Use the shape of the 5.6.0 notes: what is new,
   the changed behavior, what is fixed, and "Queued against this release"
   (step 9).

### What changes at 9.0.0

9.0.0 ends most 8.x legacy readers and adds `compass migrate`, which moves an
8.x project to 9.0.0 and keeps its evidence (ADR-098). The facts are in
`docs/upgrade-9-0-0.md`.

The 9.0.0 release notes must hold this line, as `SECURITY.md` and the upgrade
guide do:

> Compass 8.x gets security fixes only, for 90 days after 9.0.0 is released.
> After that, only 9.x is supported.

The release commit adds the end date to `SECURITY.md`.
`tests/test_upgrade_9_0_0_guide.py` checks that the three files hold the line.

### What changed at 8.0.0

8.0.0 is a major release because of one change: delegation. It removes no
reader. The facts are in `docs/upgrade-8-0-0.md`.

**What breaks**

- The positional form of `/compass:delegate`, and `--labels`, are refused.
- A delegated approval needs `--issue <slug>`, as a plain command in the
  agent's Bash tool.
- A delegation file in a linked worktree's own folder gives no approval. The
  main checkout's `.compass/delegations/` is the one store.

**What the release adds**

- `/compass:delegate [--agent] [--until] [--on] [--for] [--max]`. With no
  flag, a delegation covers this session's agents on every issue until
  `/compass:revoke`. `/compass:approve` and `/compass:reject` reach a request
  in any worktree.
- A `compass` launcher in the plugin's data folder, for the person's own
  terminal.
- The pre-tool hook catches `perl -pi`, `ruby -pi` and interpreter writes
  through a variable.

**Upgrade.** Update every checkout and every installed plugin together, then
type `/compass:delegate` again for any delegation you rely on. No archive
migration is needed.

### What changed at 7.0.0

7.0.0 removed the released command spellings that 6.0.0 renamed. It added the
document set, rendered blocks, the `default@7` preset, approval inside Claude
Code, delegation and the readiness floor. The facts are in
`docs/upgrade-7-0-0.md`.

**What is removed.** Each spelling exits 2 with the parser's usual error:

| Removed | Use instead |
|---|---|
| `approach summary` | `approach show` |
| `issue set-status` | `issue status set`, or `issue status remove` for `active` |
| `policy review-rules` | `review-rule list` |
| `issue dashboard` | `issue render` |
| `issue artifact` | `issue artifact set` |
| `migrate` | `issue migrate` |
| `issue subtask update` | `issue subtask set` |
| `run --stage build` | `run --stage implement` |
| `issue labels sync` | `issue github sync` |

**What is kept until 9.0.0.** The readers of old words, old approach names,
copied 5.x governance (with the generated views `routing-policy.yml` and
`guardrails.yml`) and `.compass/config.yml` when `compass.yml` is absent
(`governance/decisions/2026-10-25-legacy-readers-readable-until-9-0-0.md`).

**Upgrade and rollback.**

1. Update every checkout and every installed plugin together. Do not run a 6.x
   CLI on a 7.0.0 tree.
2. Copy the two issue folders, `.compass/work` and `docs/compass`, outside the
   project.
3. Run `compass issue migrate`, read the list, then run
   `compass issue migrate --apply --i-have-a-copy`.
4. If the project has a `compass.yml`, run `compass policy migrate --words`
   and `compass policy update`.

There is no supported rollback. The only way back is to restore the copy of
the two issue folders, both together. That discards everything recorded after
the copy was taken.

### What changed at 6.0.0

6.0.0 makes the project's configuration a file a person edits and a tool can
check. **It removes no command.** 7.0.0 removed the renamed command spellings,
and the readers of old forms stay until 9.0.0
(`governance/decisions/2026-10-25-legacy-readers-readable-until-9-0-0.md`).
It removes one output shape: the `compass flow --json` keys held, next_up,
landed_this_week and abandoned. The new keys are backlog, ready, in_progress,
in_review, done_this_week and closed.

**Renamed words and commands at 6.0.0.** The tables are in
`docs/upgrade-6-0-0.md`. 6.0.0 renames the depth words (`full` becomes
`thorough`), the size `standard`, the run stage `build`, the friction `phase`
key, the stored issue statuses and eight command spellings. A manifest is
written at schema `3.0`.

**Upgrade and rollback.** Update every checkout and every installed plugin
together. Do not run a v5 `ship-commit` on a 6.0.0 tree. 6.0.0 offers no
supported rollback. The first rewrite of each manifest keeps the original as
`manifest.yml.v5.bak`. Restoring it discards everything recorded after that
rewrite. The internal reverse map, used only to rehearse a rollback before the
tag, loses `duplicate_of`, the difference between `not-planned` and
`duplicate`, the `blocked` flag, and the fact that a parked issue had no
reason.

**What the release contains**

- `compass.yml` at the project root is the one file a person edits. A project
  that sets nothing runs on the default.
- The shipped default is a preset directory. `routing-policy.yml` and
  `guardrails.yml` are views generated from it.
- A layer can add, set, replace or remove an entry. A change that loosens the
  parent needs a waiver with an approver.
- `compass policy lint` checks a layered project. `compass policy show` prints
  every resolved field with the layer that set it. `compass policy diff`
  compares two configurations. `compass policy migrate` turns copied
  governance and a `.compass/config.yml` into a `compass.yml`.
- `compass approach evaluate --write` stores the configuration an issue runs
  against as a numbered generation under `.compass/work/<slug>/generations/`.
  A later change to `compass.yml` cannot change an issue that is already
  running.
- `compass policy update` moves a project to a new major of the shipped
  default. The preset verbs run a preset's fixtures and scaffold a team preset
  repository. 9.0.0 removed presets (ADR-094).
- `compass issue migrate --config` pins an issue's configuration to the
  installed versions.
- A project can name git parents. 9.0.0 removed git parents (ADR-094).
- A check can be judged (`docs/judged-checks.md`). `approvers` name who may
  approve a waiver, a human check or an exit.
- `compass issue template show` prints a document template.
- `compass issue link set` links an issue to a GitHub issue, and
  `compass issue labels sync` writes its labels. The label sync is opt-in.
  9.0.0 removed it (ADR-093).
- `/compass:init` writes a minimal `compass.yml` and copies nothing.
  `compass init` writes `.compass/state.yml` and no settings file.

**What a person sees**

| Person | Sees |
|---|---|
| A new user | `compass init` creates `.compass/state.yml` and `.compass/work/`. `/compass:init`, if run, writes `compass.yml` and no `governance/` copy. |
| A 5.x user who does nothing | The CLI reads `.compass/config.yml` and the copied `governance/` files as 5.6.0 read them. Issue manifests are rewritten to schema 3.0 on first save, and a manifest that holds old words is first copied to `manifest.yml.v5.bak`. Output uses the new words, and `compass flow --json` uses the new keys. |
| A 5.x user who migrates | `compass policy migrate` shows a dry run, and `--apply` moves the settings to `compass.yml`, the state to `.compass/state.yml`, and the old files to `.compass/legacy/`. |
| This repository | A settings-only `compass.yml`. |

**Behavior changes**

- A project with a `compass.yml` sees `approach evaluate` print `intent`,
  `launch-readiness` and `ship`, where 5.6.0 printed `intent.md`,
  `launch-readiness.md` and `land`. A project without a `compass.yml` keeps
  the 5.6.0 document names.
- A `compass.yml` that fails `compass policy lint` makes
  `compass approach evaluate --write` refuse to commit.
- A closed issue keeps the configuration it closed under. It cannot store a
  new generation.
- A script that drops a manifest's `generation:` key leaves an unreferenced
  generation folder. The next `compass approach evaluate --write` refuses to
  write over it, and `compass ci` reports it. Restore the key, or delete the
  folder.
- A migrated overlay takes effect at once for an issue that has no generation.
  An issue with a generation keeps it until its next reassessment.
- A project with a `compass.yml` and a `.compass/config.yml` that still holds
  settings is refused (`settings-conflict`). Move the keys into `compass.yml`.
- A `compass.yml` with no `schema:` key is not read as Compass's file. The old
  file is read, and a warning says so.
- An old CLI fails `compass issue lint` on a manifest that has `generation:`.
  ADR-006 does not promise that new data reads on an old CLI.

### Keeping the previous default major

9.0.0 replaced the live preset with the fixed check set (ADR-094), so no
release after it keeps a preset folder.

- A stored generation holds its own resolved policy.
- `tests/fixtures/check-set-digests.yml` pins each version of
  `governance/check-set.yml`.
- `default@6` and `default@7` are test fixtures under
  `tests/fixtures/presets/`.
- The artifacts catalog of 8.0.4 stays as `governance/artifacts-8.0.4.yml`,
  because the CLI still reads it.
- `tests/test_frozen_files_unchanged.py` compares all three byte for byte
  with the release that shipped them.

### What changed at 5.0.0

5.0.0 removed two skills by merging each into another. Load the replacement:

| Removed | Use instead |
|---|---|
| `traceability` skill | `evidence-gates` skill, which now holds it as `traceability.md` |
| `role-translation` skill | `intent-interview` skill, which held it as `role-translation.md` until 9.0.0 deleted it (ADR-093) |

Issue documents moved to `docs/compass/<created>-<slug>/`. The manifest,
`evidence/` and `devlog.md` stay in `.compass/work/<slug>/`. A path in the
manifest's `artifacts:` list is measured from the project root.

An issue written under 4.x keeps working: a bare filename still resolves
beside the manifest. To move the documents, run compass migrate (`compass issue migrate` from 6.0.0). It refuses when
git holds no copy of the work directory, unless you pass `--i-have-a-copy`.

New in 5.0.0:

- `/compass:quick-fix` and its `quick-fix` skill.
- `compass issue artifact-path <kind>` prints where one of an issue's
  documents is.
- `compass issue artifact set --path` records where a document was written.

### What changed at 4.0.0

4.0.0 removed three slash commands and one hidden CLI verb (ADR-024):

| Removed | Use instead |
|---|---|
| `/compass:triage` | `/compass:assess` <!-- vocabulary-scan: allow - the upgrade table must name the removed spelling beside its replacement, or a reader whose script broke cannot match the error they got to the row that fixes it --> |
| `/compass:wireframe` | `/compass:design` <!-- vocabulary-scan: allow - the upgrade table names the removed spelling so a broken caller can find it --> |
| `/compass:roundtable` | `/compass:consult` <!-- vocabulary-scan: allow - the upgrade table names the removed spelling so a broken caller can find it --> |
| `compass design lint` | `compass plan lint` <!-- vocabulary-scan: allow - the upgrade table records the removed verb beside its replacement; a reader whose script broke needs the spelling they typed to appear here --> |

A project that copied `governance/` under 3.x also needs the new file
`governance/strategies-rationale.md`, which `strategies.md` links. An issue
directory written under an older vocabulary still loads, and
`compass issue migrate` still brings one forward (ADR-020).

---

## Before changing the words sessions act on

A change to one of these three texts must be measured before it is merged:

- `compass-contract.md`, which the SessionStart hook injects;
- a refusal message in `hooks/pre-tool.sh`;
- `skills/tdd-discipline/SKILL.md`.

Measure it with sdd-bench, the only measurement Compass accepts (ADR-093).
The runner is `harness.py` in the sdd-bench `tools` folder:

1. Commit the change. Run the sdd-bench scenarios under the compass
   condition, with `--plugin-source` naming this checkout, into a directory
   of their own.
2. Score each finished tree with `score.py` in the same `tools` folder.
3. Compare the scores with the latest published sdd-bench result for
   Compass, and put the comparison in the PR.

A change that lowers a behavior's pass rate against that result does not
merge without a written reason. This blocks only when both results have at
least five runs per scenario and condition. With fewer, the comparison goes
in the PR and does not block.

---

## Continuous integration

`.github/workflows/compass.yml` runs this repository's checks and tests on
every pull request, in the merge queue and on every push to main. A script in
`scripts/ci-*.py` makes each decision a job takes.
`tests/test_ci_workflow_shape.py`, `tests/test_ci_shards.py`,
`tests/test_ci_fast_tests.py` and `tests/test_ci_already_tested.py` test the
workflows and the scripts.

The whole test suite runs once for each pull request, in the merge queue, on
the exact commit that then lands on main
(`governance/decisions/2026-11-01-the-full-suite-runs-in-the-merge-queue.md`).

| Kind of run | Jobs that run | Job minutes, about |
|---|---|---|
| A push to a pull request | `checks`, `count`, `fast-tests`, `self-check` here; `build` and `pr-text` in their own workflows | 5 to 10, more when the pull request changes slow test files |
| A merge group (the `merge_group` event) | every job but `already-tested` and `fast-tests` | 100 to 160, most of it in the shards |
| A push to main | nothing but `already-tested` when a merge group tested the same commit green; otherwise what a merge group runs | 1, or as a merge group |

A draft pull request runs no test: `checks`, `count` and `fast-tests` skip,
and `self-check` passes. Marking it ready for review (`ready_for_review`) runs
them.

### The jobs

| Job | What it does |
|---|---|
| `already-tested` | Runs on a push to main only. Decides whether the push can skip every other job. |
| `checks` | The rival-name scan of commit messages, `scripts/validate.sh`, the CLI syntax check and `compass ci`. |
| `count` | Counts the tests outside the serial pass, with `pytest --collect-only -q -m "not serial" tests/`. |
| `fast-tests` | Runs on a pull request only. Runs the test files the pull request changes and a fixed set of house-rule test files. |
| `shard` | A matrix of shard jobs. Each runs its share of the test files on parallel workers, prints every test's duration and ends at 45 minutes. |
| `serial` | Runs the tests marked `serial` alone, and prints its 20 slowest tests. |
| `self-check` | The aggregator. It needs every job above, the four `bdd-adapter` jobs, `atdd-adapter-python`, `atdd-adapter-typescript` and `check-mutation`. |
| `bdd-adapter`, `bdd-adapter-behave`, `bdd-adapter-cucumber-js`, `bdd-adapter-godog` | Run each BDD reference adapter. |
| `atdd-adapter-python` | Runs the Python example of four-layer acceptance tests (`examples/atdd-adapters/python/`) through its API driver and its CLI driver, then its layering test. |
| `atdd-adapter-typescript` | Does the same for the TypeScript example (`examples/atdd-adapters/typescript/`) on Node 22.13.0, after `npm ci` and a type check. Then it runs the Compass tests that need Node (`TRC-C5`, `TRC-J6`, `TRC-X3`) with `COMPASS_REQUIRE_TYPESCRIPT=1`, so a missing Node fails them. It is not a ruleset-required check, but `self-check` needs it. |
| `check-mutation` | Breaks each shipped check and confirms its register tests go red. |

The suite jobs are the shards, `serial`, `check-mutation` and the adapter
jobs. They run in a merge group and on a push to main only.

`self-check` passes:

- in a merge group, and on a push to main that runs the suite, when every
  suite job succeeded, `fast-tests` skipped and the shard counts add up to the
  `count` total;
- on a pull request, when `checks`, `count` and `fast-tests` succeeded and
  every suite job skipped.

A new push to a pull request, or a change of its base branch, cancels the run
it replaces. This workflow never cancels a merge group or a push to main.

### The fast tests

On a pull request, `fast-tests` runs the files that
`scripts/ci-fast-tests.py --base <base sha> --head <head sha>` lists:

- the house-rule test files: `tests/test_house_style.py`,
  `tests/test_terminology.py`, `tests/test_rival_names_never_committed.py`,
  `tests/test_us_english_guard.py`, `tests/test_contract_claude_md_drift.py`
  and `tests/test_workflow_pins.py`. `tests/test_writing_style.py` takes
  about 500 seconds, so it runs in the merge queue only;
- every test file under `tests/` that the pull request changes and that still
  exists.

The job runs those files on parallel workers, then their tests marked
`serial` alone. It fails when it cannot compute the change. The merge queue
finds a test that other code broke, and removes the pull request from the
queue.

To list the files for a branch locally:

```bash
python3 scripts/ci-fast-tests.py --base origin/main --head HEAD
```

### Edits and base changes

`compass.yml` runs on the pull request types `opened`, `synchronize`,
`reopened`, `edited` and `ready_for_review`. GitHub sends `edited` for a
change of title, body or base branch. A base change runs the fast jobs again.
A title or body edit does not:

- `checks`, `count` and `fast-tests` skip, on the condition
  `github.event.action != 'edited' || github.event.changes.base != null`.
- `self-check` still runs, because a skipped required check counts as passed
  and would hide an earlier failure. It runs
  `scripts/ci-already-tested.py --pull-request N --head H --this-run RUN_ID --wait-minutes 55`.
- That script reads the pull request's earlier runs of `compass.yml` on the
  head. It counts only runs that ran `checks`. It passes only when the latest
  counted run's `self-check` succeeded and the pull request's timeline shows
  no base change since that run was created.
- An edit made while the earlier run is still running waits for it. It checks
  every 60 seconds for up to 55 minutes. A wait that runs out fails the check.
- A text-only edit has a concurrency group of its own, so it never cancels a
  run of the fast jobs. A second edit cancels the first edit's run.
- GitHub lists no pull request on the runs of a pull request from a fork, so
  a text edit on one fails `self-check`. Push to the branch again.

### The required checks

The protected-main ruleset needs `self-check`, `check-mutation`, `build`,
`pr-text`, `atdd-adapter-python` and the four `bdd-adapter` jobs. Each must
report on a pull request and in a merge group. A skipped required check
counts as passed, so `self-check` carries the real result:

- Every job in `compass.yml` but `already-tested` runs on the condition
  `!cancelled() && needs.already-tested.outputs.skip != 'true'`. The suite
  jobs add `github.event_name != 'pull_request'`.
- `scripts/ci-self-check.py aggregate` fails `self-check` when a job it needs
  (`--needed`) did not succeed, when a job that this kind of run must not run
  (`--skipped`) did not skip, or when a job has no result. In a merge group
  `--skipped` names `fast-tests`. On a pull request it names every suite job.
- `docs.yml`'s `build` runs on every pull request and in every merge group.
  When the change touches none of `docs/`, `mkdocs.yml` and
  `.github/workflows/docs.yml`, it skips its steps and succeeds
  (`scripts/ci-changed.py`).
- `pr-text.yml` runs in a merge group too, where it passes without a scan.

### The count check

Each shard counts the tests it collects and publishes the count as an
artifact. `self-check` fails when a count is missing or not a whole number, or
when the sum differs from the `count` job's total. This finds a test file that
no shard ran.

The number of shards is set in one place, the `shard` job's matrix. To run one
shard locally, as CI does:

```bash
python3 scripts/ci-shard.py 2 4 > /tmp/shard.txt
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 xargs python3 -m pytest -p xdist.plugin -n auto -m "not serial" --durations=0 < /tmp/shard.txt
```

The shard command splits the test files by weight:

- a file's weight is its entry in `tests/ci-durations.json`, the seconds its
  tests took in a recorded CI run;
- a file the table does not hold weighs the median of the table's entries;
- files go heaviest first, each to the shard with the least weight so far.

To see each shard's predicted load, add `--loads`:

```bash
for i in 0 1 2 3; do python3 scripts/ci-shard.py "$i" 4 --loads; done
```

Refresh the table when the shards drift apart in time. Take the id of a run
whose four shard jobs all succeeded, then rebuild the table and commit it:

```bash
python3 scripts/ci-durations.py RUN_ID
```

The command reads each shard job's log with `gh`. It refuses a run with a
shard job that did not succeed.

### The push skip

A push to main skips every job when the merge queue already tested the pushed
commit green with the whole suite.
`scripts/ci-already-tested.py --commit M --this-run RUN_ID` writes `skip=true`
only when all of these hold. On anything else, including an error reading the
GitHub API, the suite runs:

1. the pushed commit is 40 hex characters and the run id a whole number;
2. this workflow has at least one `merge_group` run on the pushed commit;
3. the latest of those runs has one `self-check` job, completed with
   conclusion success;
4. that run has `shard` jobs, and every one succeeded.

A pull-request run never lets a push skip. A merge made without the queue,
such as an administrator's, runs the suite on main.

### The merge queue

The `protected-main` ruleset (id 16658263) must have a `merge_queue` rule.
Without it, nothing runs the whole suite before a merge. To add the rule:

```bash
gh api repos/ayeo-io/compass/rulesets/16658263 \
  --jq '{name, target, enforcement, conditions, bypass_actors,
         rules: (.rules + [{type: "merge_queue", parameters: {
           merge_method: "SQUASH", grouping_strategy: "ALLGREEN",
           max_entries_to_build: 3, min_entries_to_merge: 1,
           max_entries_to_merge: 5, min_entries_to_merge_wait_minutes: 5,
           check_response_timeout_minutes: 60}}])}' \
  | gh api -X PUT repos/ayeo-io/compass/rulesets/16658263 --input -
```

`check_response_timeout_minutes` is 60 because a shard can take 45 minutes.
`max_entries_to_build` sets how many suite runs can go at once. Merge a pull
request with "Merge when ready", which adds it to the queue.

### The pull request text

`.github/workflows/pr-text.yml` scans the pull request's title and body for
rival product names. It runs on `edited` too. The ruleset lists `pr-text` as a
required check, so it also runs in a merge group, where it passes without a
scan.

### The automatic review

`.github/workflows/claude-review.yml` reviews a pull request with Claude
against `CLAUDE.md` and the review rules that match the changed files. It is
turned off: no pull request starts it, and a run started by hand skips
(`governance/decisions/2026-10-03-ci-review-manual-only.md`). Its `rules`
step checks out the base branch and runs that branch's
`compass review-rule list --rules <base>/governance/review-rules.yml
--changed-files <files>`, so a pull request cannot change the rules it is
reviewed against.

### Timeouts

Every job in every workflow has `timeout-minutes`: about twice the job's p90
run time, rounded up to a multiple of 5 minutes, at least 5 and at most 45.

| Job | Minutes |
|---|---|
| `serial` | 20 |
| `fast-tests` | 15 |
| `self-check` | 60, because on a title or body edit it waits up to 55 minutes. Each of its steps has a 5-minute limit of its own. |

### Measuring a run

`scripts/ci-run-minutes.py` reads the JSON that `gh run view RUN --json jobs`
prints. It prints each job's minutes, the run's wall time and the sum of job
minutes:

```bash
gh run view 1234567890 --json jobs | python3 scripts/ci-run-minutes.py
```

---

## Supply-chain stance

[`docs/security.md`](security.md) is the reference. At each release, check
that downstream use still follows these rules:

- **Pin to a commit SHA, not a branch**, wherever Compass is used downstream:
  in CI workflows, in vendored copies and in plugin installations.
- **Mirror to a trusted location** for use in an organization, such as a
  private fork, and pin to that mirror.
- **Review the diff between SHAs** before you move the pin.

---

## What defends each invariant

| Invariant | Defender |
|---|---|
| All seven version locations agree | `tests/test_release_invariants.py` (partial-bump guard) |
| Pre-v1.1.0 manifest.yml shapes still lint clean | `tests/test_release_invariants.py` (ADR-006 backward-compat, via the `tests/fixtures/comparison-requirements/` fixture) |
| Every CLI subcommand appears in the public CLI blocks | `tests/test_cli_surface_drift.py` (parses `compass --help`) |
| `docs/install-smoke-test.md` shows the current version | `tests/test_cli_surface_drift.py` (reads `VERSION`, asserts the smoke-test matches) |
| `install.sh` does not double-register hooks in a plugin-source repo | `tests/test_install_plugin_detection.py` |
| The release tarball contains no noise files | `scripts/release.sh` (built into `make release`) |
