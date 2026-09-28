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
that fallback. To move the documents, run `compass migrate`. It refuses when
git holds no copy of the work directory, and `--i-have-a-copy` tells it you
have taken one yourself.

New in 5.0.0, and nothing removed by it:

- `/compass:quick-fix` and its `quick-fix` skill: the light path reads one
  command file and one skill.
- `compass issue artifact-path <kind>` prints where one of an issue's
  documents is.
- `compass issue artifact --path` records where a document was written.

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
under an older vocabulary still loads, and `compass migrate` still brings
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

3. **`make test`** - must be green. The full test suite, including:
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

4. **`make ci`** - must be green. Runs `compass policy lint` + `issue
   lint` + `check` across all issues under `.compass/work/`. (`make ci`
   is what CI runs; failing it locally means CI will fail.)

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

9. **Tag and publish.** The release-script run, the out-of-tree smoke
   test, and the seven-locations version bump are the gate; tagging is
   the consequence.

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
