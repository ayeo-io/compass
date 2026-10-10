# Compass - Releasing

The procedure for cutting a Compass release. The mechanics live in
[`scripts/release.sh`](../scripts/release.sh); this file is the
human-readable guidance for invoking it and the lessons that pin a
release to a clean, reproducible artifact.

> **What this file is.** Generic operational guidance - apply it for
> every release. Frozen rc.1-era status tables and per-release "owed
> items" no longer live here; that history lives in git.

---

## The release procedure

**Compass follows semantic versioning.** The number describes the
compatibility promise, not the size of the change:

- **major** - something a caller could call stops working. Removing a command,
  a verb, a flag spelling or a manifest key is a major bump however small the
  diff, and however few people it affects. 3.0.0 removed the retired command
  and flag spellings; "no adopters yet" was the reason it was cheap, not a
  reason to call it minor.
- **minor** - new capability, nothing removed.
- **patch** - a fix that changes no interface.

ADR-006 is the other half of this: backward compatibility is non-negotiable
*within* a major, so a new mechanism no-ops on projects that have not adopted
it, and a breaking change happens once, at a major version, with the reason
recorded.

### What changed at 6.0.0

6.0.0 makes the project's configuration a file a person edits and a tool can
check. It is a major release because it changes the shipped default's format
and ships together with the delivery approaches as data (the decision record
"routing policy as configuration goes ahead", in `governance/decisions/`),
not because it removes a command. **It removes no command.** Every file and
name that 5.x read is still read, and every released command spelling that 6.0.0
renames still runs, until 7.0.0 removes them
(`governance/decisions/2026-10-06-legacy-governance-readable-until-7-0-0.md`
and `governance/decisions/2026-10-06-old-route-names-readable-until-7-0-0.md`).
It does remove one output shape: the `compass flow --json` keys held, next_up,
landed_this_week and abandoned, replaced by backlog, ready, in_progress,
in_review, done_this_week and closed.

**Renamed words and commands at 6.0.0.** 6.0.0 renames the depth words (`full`
becomes `thorough`, and the other two follow), the size `standard`, the run
stage `build`, the friction `phase` key, the stored issue statuses and eight
released command spellings. A manifest is written at schema `3.0`. The old words
and the eight command spellings work until 7.0.0. The full tables, the notice a
first save prints and the `manifest.yml.v5.bak` backup are in
`docs/upgrade-6-0-0.md`. `issue status remove` also reopens a closed issue, so
a released script that reopened one keeps working.

**Upgrade and rollback.** Update every checkout and every installed plugin
together. Do not run a v5 `ship-commit` on a 6.0.0 tree: it does not read the
new words and drops the issue from the living spec. 6.0.0 offers no
supported rollback: a problem is fixed forward in a 6.0.x release. The first
rewrite of each manifest keeps the original as `manifest.yml.v5.bak`;
restoring it discards everything recorded after that rewrite. The internal
reverse map, used only to rehearse a rollback before the tag, loses
`duplicate_of`, the difference between `not-planned` and `duplicate`, the
`blocked` flag, and the fact that a parked issue had no reason (it returns as
a plain queued hold). The configuration files of a project (`compass.yml`,
copied governance and `.compass/config.yml`) are read in their old words until
7.0.0. A tool to rewrite them is owed before 7.0.0.

**What the release contains**

- `compass.yml` at the project root is the one file a person edits. It holds the
  project's settings and, optionally, its edits to the shipped default. It
  extends `compass:default@6`, and a project that sets nothing runs on the
  default. A 6.x release of the default never changes a value that 6.0.0 defines.
- The shipped default is a preset directory, `governance/presets/default/`.
  `governance/routing-policy.yml` and `governance/guardrails.yml` are views
  generated from it, and they stay through 6.x for the projects, the drift
  report and the tests that read them.
- A layer can add, set, replace or remove an entry. The classifier compares a
  layer with its parent. A change that loosens the parent needs a waiver with an
  approver, a framework lock cannot be removed by a lower layer, and a project
  that unlocks a framework entry is reported non-conformant.
- `compass policy lint` checks a layered project. `compass policy show`
  prints every resolved field with the layer that set it. `compass policy diff`
  compares two configurations by classification and by replaying assessments.
  `compass policy migrate` turns copied governance and a `.compass/config.yml`
  into a `compass.yml`.
- `compass approach evaluate --write` stores the configuration an issue runs
  against as a numbered generation under `.compass/work/<slug>/generations/`.
  The commands that read configuration read that generation, so a later change
  to `compass.yml` cannot change an issue that is already running.
- `compass policy update` moves a project to a new major of the shipped default
  and asks again for approval of each waiver the move affects. `compass preset
  test` runs a preset's fixtures and checks its locks, and `compass preset
  init` scaffolds a team preset repository.
- `compass issue configure` proposes, previews, discards or recovers a change to
  an issue's own configuration. `compass issue migrate --config` pins an issue's
  configuration to the installed versions. An implementation major that differs
  from the one a generation recorded is refused, and a check can be advisory.
- A project can name git parents, singly or in a chain, and each is pinned by
  sha and judged against the default like any other layer
  (`docs/git-parents.md`).
- A check can be judged: it passes on a recorded review (`docs/judged-checks.md`).
  `approvers` name who may approve a waiver, a human check or an exit, and an
  evidence approval is recorded with its approver.
- `compass issue template show` prints a document template with its checklists
  rendered from the issue's stage lists. The receipt shows where each rule,
  waiver, lock and check came from.
- Compass can write an issue's domain labels and workflow state to its linked
  GitHub issue (`docs/github-labels.md`). It is opt-in: the `github_labels` key
  in `compass.yml` has two switches, both off by default, and with both off no
  command calls GitHub. `compass issue link set` links an issue and
  `compass issue labels sync` writes its labels. The manifest schema gains an
  optional `github` field (`repo`, `number`). Compass never reads a label back
  into the manifest.
- The dashboard, `compass policy show` and `compass issue migrate --help` now
  describe what the code does, and the release documents state which commands
  fetch a git parent and which v5.6.0 commands refuse a schema 3.0 manifest.
- `/compass:init` writes a minimal `compass.yml` for a new project and copies
  nothing. It runs `compass policy migrate` when it finds a
  `.compass/config.yml` or copied governance. `compass init`, which every entry
  point runs, writes `.compass/state.yml` and no settings file.

**What a person sees**

| Person | Sees |
|---|---|
| A new user | `compass init` creates `.compass/state.yml` and `.compass/work/`. `/compass:init`, if run, writes `compass.yml` and no `governance/` copy. |
| A 5.x user who does nothing | Settings and copied governance are read as 5.6.0 read them: the CLI reads `.compass/config.yml` and the copied `governance/` files. Issue manifests are rewritten to schema 3.0 on first save, and a manifest that holds old words is first copied to `manifest.yml.v5.bak`. Output uses the new words, and `compass flow --json` uses the new keys. |
| A 5.x user who migrates | `compass policy migrate` shows a dry run, and `--apply` moves the settings to `compass.yml`, the state to `.compass/state.yml`, and the old files to `.compass/legacy/`. |
| This repository | A settings-only `compass.yml`. It keeps its generated governance files and the legacy lint. |

**Behaviour changes**

- A project with a `compass.yml` sees `approach evaluate` name the intent
  document `intent`, the launch document `launch-readiness` and the last stage
  `ship`, where 5.6.0 printed `intent.md`, `launch-readiness.md` and `land`. A
  project without a `compass.yml` keeps the 5.6.0 document names; its approach
  and depth words follow the 6.0.0 renames in `docs/upgrade-6-0-0.md`.
- A `compass.yml` that fails `compass policy lint` makes
  `compass approach evaluate --write` refuse to commit. Without `--write` the
  command still works.
- A closed issue keeps the configuration it closed under, whatever its close
  reason. It cannot store a new generation.
- A script that rewrites a manifest wholesale and drops its `generation:` key
  leaves a complete but unreferenced generation folder. The next
  `compass approach evaluate --write` refuses to write over it, and `compass ci`
  reports it. Restore the key, or delete the folder.
- A migrated overlay takes effect at once for an issue that has no generation.
  An issue with a generation keeps it until its next reassessment.
- A project with a `compass.yml` and a `.compass/config.yml` that still holds
  settings is refused (`settings-conflict`). Move the keys into `compass.yml` and
  delete them from the old file.
- A `compass.yml` that has no `schema:` key is not taken for Compass's file. The
  old file is read, and a warning says so.
- An old CLI reading a manifest that has `generation:` fails `compass issue lint`,
  because the old manifest schema forbids unknown keys. The backward-compatibility
  rule (ADR-006) protects projects that have not adopted a mechanism. It does not promise that new data reads on an
  old CLI.

### Keeping the previous default major

A release that moves the shipped default to a new major (`default@7` after
`default@6`) must keep the previous major's preset files in
`governance/presets/default@<major>`, a copy of the last preset that major
shipped. `compass policy update` reads both folders to tell which waived
fields moved, and exits 2 for a project on a major that is not kept. Pin the
new preset with `python3 scripts/generate-legacy-views.py --pin`; the old
pins stay. `tests/test_policy_update.py` fails when a kept folder does not
match its pinned digest or when an earlier pinned major is not kept.

### What changed at 5.0.0

5.0.0 removed two skills by merging each into another. A session, an agent
file or a project instruction that loads a removed skill by name must load
its replacement:

| Removed | Use instead |
|---|---|
| `traceability` skill | `evidence-gates` skill, which now holds it as `traceability.md` |
| `role-translation` skill | `intent-interview` skill, which now holds it as `role-translation.md` |

Issue documents moved too. The acceptance criteria, technical design,
delivery approach and the other prose documents now live in
`docs/compass/<created>-<slug>/`. The manifest, `evidence/` and `devlog.md`
stay in `.compass/work/<slug>/`. A path in the manifest's `artifacts:` list
is now measured from the project root.

An issue written under 4.x keeps working without any change: a bare
filename still resolves beside the manifest, and the CLI says when it used
that fallback. To move the documents, run compass migrate (`compass issue migrate` from 6.0.0). It refuses when
git holds no copy of the work directory, and `--i-have-a-copy` tells it you
have taken one yourself.

New in 5.0.0, and nothing removed by it:

- `/compass:quick-fix` and its `quick-fix` skill: the light path reads one
  command file and one skill.
- `compass issue artifact-path <kind>` prints where one of an issue's
  documents is.
- `compass issue artifact set --path` records where a document was written.

### What changed at 4.0.0

4.0.0 removed three slash commands that had been redirect stubs since 3.x,
and one hidden CLI verb. If a script or a session calls any of these,
change it:

| Removed | Use instead |
|---|---|
| `/compass:triage` | `/compass:assess` <!-- vocabulary-scan: allow - the upgrade table must name the removed spelling beside its replacement, or a reader whose script broke cannot match the error they got to the row that fixes it --> |
| `/compass:wireframe` | `/compass:design` <!-- vocabulary-scan: allow - the upgrade table names the removed spelling so a broken caller can find it --> |
| `/compass:roundtable` | `/compass:consult` <!-- vocabulary-scan: allow - the upgrade table names the removed spelling so a broken caller can find it --> |
| `compass design lint` | `compass plan lint` <!-- vocabulary-scan: allow - the upgrade table records the removed verb beside its replacement; a reader whose script broke needs the spelling they typed to appear here --> |

Also new: `governance/strategies-rationale.md`. `strategies.md` links to
it, so a project that copied `governance/` under 3.x needs this file too -
otherwise that link resolves to nothing.

The read-side rename tables are unaffected: an issue directory written
under an older vocabulary still loads, and `compass issue migrate` still brings
one forward (ADR-020). ADR-024 records why the redirects were not carried
past this boundary.

**When a change looks like it forces a major, removing the break is a
legitimate response; redefining the break is not.** In 3.1.0, the assess
stage started recording a subtask ceiling where it had recorded an
orchestration, and nothing normalised the old field - so every manifest
written earlier read as `None`. That was a major. Normalising old manifests
on read made it a minor, and normalising was owed under ADR-006 regardless
of what it did to the number. The test is whether you would make the change
with the version hidden.

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

   **And one more thing to edit, which is not a published location.**
   `EXPECTED_VERSION` in `tests/test_version_consistency.py` is hardcoded on
   purpose - reading it from `VERSION` would make the test self-maintaining
   and blind to the case it exists for, a release where nothing was bumped.
   Editing it is the deliberate act that says a release is intended, so it
   is part of the procedure even though it ships nowhere. Bumping the seven
   without it leaves the suite red.

   Do not trust the count in this table alone:
   `tests/test_version_guard_covers_every_location.py` derives the set
   from the files themselves and fails if the guard has no case for one
   of them, precisely so a stale table cannot let a partial bump through.

   A partial bump ships a plugin whose manifest disagrees with the CLI it
   installs, so do not skip running the suite after this step. The last
   row is the one that gets forgotten, because it lives in prose rather
   than in a manifest.

2. **`make clean`** - clears local noise (`__pycache__`, `*.bak`,
   `.DS_Store`, `.pytest_cache`, `_deltest`, `pytest-cache-files-*`).
   The release tarball must not carry any of these.

3. **`make test`** - must be green. It runs on parallel workers when
   `pytest-xdist` is installed (`pip install pytest-xdist`), which takes a
   few minutes instead of half an hour. The full test suite, including:
   - `tests/test_cli_surface_drift.py` (every CLI subcommand documented
     in the public CLI surface blocks)
   - `tests/test_release_invariants.py` (the partial-version-bump guard
     + the `comparison-requirements` ADR-006 backward-compat fixture +
     `signals.yml` shape invariants)
   - All other existing tests (delivery-approach selection, guardrail
     checks, evidence handling, Spike safety, CI exit codes, the
     retrospective signal, architecture consistency, etc.)

   If any of the drift-guard tests fail, **do not bump VERSION further.**
   A failed drift-guard means a public-facing artifact has not been
   updated for a behaviour change - the framework's own traceability guardrail (`G3`)
   is at risk. Fix the docs to catch up, re-run, then bump.

4. **`make ci`** - must be green. Runs `compass policy lint`, then `issue
   lint` on every issue under `.compass/work/` and `check` on the issues in
   flight or landed since the last release tag (`compass ci --since <tag>`).
   Once per release, run `COMPASS_FULL_ARCHIVE=1 make ci`, which checks
   every issue. (`compass ci` is what CI runs; failing it locally means CI
   will fail.) Run `COMPASS_FULL_ARCHIVE=1 make test` too: the archive
   tests then read every local issue instead of the tracked sample,
   `tests/fixtures/archive-sample.tar.gz`, and the living-spec and citation
   tests, which skip without it, run.

5. **`make release`** - produces `dist/compass-<version>.tar.gz`.

   The release script:
   - Clears `dist/` of any prior tarball so you publish one artifact,
     not two.
   - Runs `validate.sh` + `policy lint` + the test suite + the
     examples-present check *before* packaging.
   - **Hard-fails (exit 1)** if the tarball contains any noise file
     (`.DS_Store`, `__MACOSX`, `__pycache__`, `*.bak`, `.pytest_cache`,
     `_deltest`, `pytest-cache-files-*`).
   - **Hard-fails** if any of the worked examples under `examples/` is
     missing its `.compass/work/<slug>/manifest.yml`. An exclude that is
     not root-anchored strips the example issue files.

6. **Inspect the tarball.** `tar -tzf dist/compass-<version>.tar.gz | less`
   - read the list even when the script's checks have passed.

7. **Distribute ONLY the tarball from step 5.** <!-- vocabulary-scan: allow - ordinary verb, and the sentence is an instruction about distribution rather than the retired stage --> Do not zip the source
   tree from Finder, GitHub's "Download ZIP," or any other tool. Those
   zip the live working tree, including `__MACOSX`, `.DS_Store`,
   `.pytest_cache`, any `.bak` file, and any other dev noise. The
   release script is the one place the artifact is guaranteed clean -
   every other path includes local noise files.

   A zip built any other way can carry local noise into a release; the fix
   is operational, not in code: ship `dist/compass-<version>.tar.gz` and
   only that.

8. **Check the tarball OUT OF THE SOURCE TREE.** The final smoke test:

   ```bash
   cp dist/compass-<version>.tar.gz /tmp/
   cd /tmp && tar -xzf compass-<version>.tar.gz
   cd compass-<version>
   bash scripts/validate.sh
   python3 cli/compass policy lint
   python3 cli/compass ci
   ```

   All four commands must succeed against the extracted release. Running
   them against the source tree instead would miss a packaging bug that
   only shows up once the tarball is unpacked somewhere else.

9. **Check the queue against this release.** Run `compass flow --digest`
   and read its queue ageing line and table. For each queued issue that
   touches what this release changes, either pull it in or say why it
   waits. Put the answer in the release notes under
   "Queued against this release", or write "None" there. A queued fix
   with its recommendation already written is the case this step exists
   for.

10. **Tag and publish.** The release-script run, the out-of-tree smoke
   test, and the seven-locations version bump are the gate; tagging is
   the consequence. After pushing the tag, run
   `python3 scripts/generate-shipped-releases.py` and land the updated
   `governance/shipped-releases.yml` and `governance/shipped-releases.tar.xz`
   through a pull request. `compass policy migrate` reads this table to
   recognise a project's copied governance, and `test_PM_12` fails wherever
   tags are fetched until the table lists the new tag.
   `python3 scripts/generate-shipped-releases.py --check` exits 0 once it
   does.

### Checks for 6.0.0

Run these on top of steps 1 to 9, before step 10.

1. **A full run with the whole archive.** `COMPASS_FULL_ARCHIVE=1 make test`
   and `COMPASS_FULL_ARCHIVE=1 make ci`. The compatibility contract for check
   verdicts and for old manifests reads every archived issue only with the
   variable set.
2. **The six compatibility contracts.** "A project with no configuration
   behaves as 5.6.0" is six promises, each compared with a baseline captured
   once from 5.6.0 and never regenerated from newer code: routing output, what
   each delivery approach owes, `compass check` verdicts on archived issues, CLI
   exit codes on a recorded command corpus, pre-tool hook decisions on a
   recorded corpus, and old manifests, evidence and receipts staying readable.
   The tests are `tests/test_compat_contracts.py` (A),
   `tests/test_compat_configurations.py` (B and C),
   `tests/test_compat_contract_4.py` and `tests/test_compat_contract_5.py`.
   Each contract must hold under these configurations:
   - **A.** No configuration: the shipped default alone.
   - **B.** An empty overlay: a `compass.yml` holding `schema: 1` and
     `extends: compass:default@6` and nothing else.
   - Under B, two corpus entries are left out because their answer is about
     the configuration found: `policy-test-no-preset` (exit 1, a project preset
     with no fixtures) and `policy-update-no-project-file` (exit 0, already on
     the default). They are still compared under A and C.
   - **C.** A copy of the 5.6.0 shipped governance files, run through the
     legacy adapter. The copy is in `tests/fixtures/compat/v5.6.0-governance.tgz`,
     taken from the `v5.6.0` tag.
   - **D.** Contracts 4 and 5 only, because the settings move files: the same
     project with a 5.6.0 `.compass/config.yml`, and again after
     `compass policy migrate` has moved its settings into `compass.yml`. Both
     states must give the recorded exit codes and hook decisions.

   What B and C check exactly, and where they differ from A:
   - Contracts 1 to 3 and 6 run in full under B and C. Contract 1 compares a
     layered result with the baseline after a table of three spellings: the
     layered path names a required document by its id (`intent`,
     `launch-readiness`) and a blocked stage by its current name (`ship`),
     where 5.6.0 printed `intent.md`, `launch-readiness.md` and `land`. Any
     other name, and every other field, is compared as recorded.
   - Contract 4 runs the corpus under B and C, with the configuration in the
     project's base commit. It leaves out an entry whose project state already
     holds a settings file or governance of its own, every `policy migrate`
     entry (it migrates the files B and C add), and the `terminology` entries
     under C (5.6.0 refuses them in a project with a two-file governance copy).
   - Contract 5 runs the hook corpus with the settings in a `compass.yml` that
     extends the default (B), and with the 5.6.0 governance copy added beside
     `.compass/config.yml` (C).
   - Each parametrisation has a partner test that plants a fault in the
     configuration builder and expects a difference.
3. **The framework's own file.** `tests/test_framework_compass_yml.py` fails when
   this repository's `compass.yml` holds a catalogue key, a waiver, an unlock or
   a capability, because this repository's issues must run the shipped default
   unchanged. `tests/test_old_settings_file_sweep.py` and
   `tests/test_settings_prose.py` fail when a source or a document names
   `.compass/config.yml` without `compass.yml` or the state file.
4. **The verbs the notes name exist.** For every command the release notes
   name, check that `compass <verb> --help` runs. A note must not describe a
   command the tarball lacks.
5. **Release notes.** The notes are the body of the GitHub release, which the
   repository does not track. Use the shape of the 5.6.0 notes: what is new, the
   changed behaviour, what is fixed, and "Queued against this release" (step 9).
   Say plainly that nothing is removed, and name the behaviour changes listed
   above.

---

## Before changing the words sessions act on

Three texts decide most of what a session does under Compass. A change to
any of them must be measured, not judged:

- `compass-contract.md`, which the SessionStart hook injects;
- a refusal message in `hooks/pre-tool.sh`;
- `skills/tdd-discipline/SKILL.md`.

Before the change is merged:

1. Commit the change: the harness loads the checkout's `HEAD`. Then run
   the scenarios the text serves under the compass condition, into a
   directory of their own:
   `python3 evals/harness.py --scenario <id> --condition compass --runs 5 --out <dir>`.
2. Score them with the model judge, which the baseline used:
   `python3 evals/judge.py <dir>/*.json --report <file> --llm`. Each
   result the rules leave undecided costs one more call, capped at $0.50.
3. Compare the report with the baseline and put the comparison in the PR.
   The baseline is the latest eval report in `docs/compass/`, named
   `<date>-eval-*.md`; the first is `2026-09-26-eval-pilot.md`.

A change that lowers a behaviour's pass rate against the baseline does not
merge without a written reason. This blocks only when both reports have at
least five runs per scenario and condition: with fewer, one flipped result
can be chance, so the comparison goes in the PR and does not block. The
published baseline has one run per scenario and condition, so no
comparison blocks until a five-run baseline is published.
`evals/README.md` says which scenarios each text serves, and what a run
costs.

---

## Supply-chain stance

[`docs/security.md`](security.md) is the canonical reference. The
release-time touchpoints:

- **Pin to a commit SHA, not a branch**, wherever Compass is consumed
  downstream (in CI workflows, in vendored copies, in plugin
  installations). A branch can be rewritten; a SHA cannot.
- **Mirror to a trusted location** for organisational use - a private
  fork or an internal package mirror - and pin to that mirror.
- **Review the diff between SHAs** before bumping the pin. Compass is
  small enough that this is realistic.

A release does not loosen these rules; if anything, a new release is
the moment to re-check them.

---

## What defends each invariant

When a release commit touches code or docs, the suite has guards that
catch common drift:

| Invariant | Defender |
|---|---|
| All seven version locations agree | `tests/test_release_invariants.py` (partial-bump guard) |
| Pre-v1.1.0 manifest.yml shapes still lint clean | `tests/test_release_invariants.py` (ADR-006 backward-compat, via the `tests/fixtures/comparison-requirements/` fixture) |
| `signals.yml` shape stays valid | `tests/test_release_invariants.py` (`design_smell` category, etc.) |
| Every CLI subcommand appears in the public CLI blocks | `tests/test_cli_surface_drift.py` (parses `compass --help`) |
| `docs/install-smoke-test.md` shows the current version | `tests/test_cli_surface_drift.py` (reads `VERSION`, asserts the smoke-test matches) |
| `install.sh` does not double-register hooks in a plugin-source repo | `tests/test_install_plugin_detection.py` |
| The release tarball contains no noise files | `scripts/release.sh` (built into `make release`) |

These tests are not formalities - they are what makes a Compass
release credibly reproducible. Run them; honour them.
