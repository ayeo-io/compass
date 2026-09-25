# Result - dispatch-protocol, subtask-1

## What changed

- **`scripts/lib/issue-docs.sh`** (new). `issue_doc_path <slug> <kind>`
  prints where one of an issue's documents is: it runs `compass issue
  artifact-path <kind> --issue <slug>` through `compass_python` (the
  worktree's own `cli/compass`, never a bare `compass`), and falls back to
  `.compass/work/<slug>/<kind>.md` for an issue that predates the artifact
  registry. Sourcing it has no side effect - it only defines the function.

- **`scripts/multiagent.sh`**.
  - `MAP` and `ROUTE` are now resolved through `issue_doc_path` instead of a
    hard-coded flat path, so an issue whose documents are registered under
    `docs/compass/<created>-<slug>/` is found there. `delivery-approach`'s
    pre-rename filename is kept as a local second-chance check, because the
    artifact resolver does not know that old name (out of scope to change -
    it lives in `cli/compass_pkg/`, a file this subtask does not own).
  - Seeding now also reads every kind the manifest's `artifacts:` list
    names, resolves each through `issue_doc_path`, and copies any that
    resolve outside `.compass/work/<slug>/` into the worktree at the same
    path relative to the project root - non-destructive, same as the
    existing issue-directory copy.
  - A `Wave` column in the map's header row is detected by exact cell match.
    `--wave N` provisions that wave's rows only; without it, wave 1 runs and
    the output names the next wave. The cap is measured against the chosen
    wave's row count, not the map's total. A wave number above the map's
    highest staged wave is refused. A map with no `Wave` column is
    unaffected; `--wave` given against one is refused rather than silently
    ignored.

- **`templates/distribution-map.md`**. Documents the optional `Wave`
  column in a comment under §3's table, with an example row shape and one
  sentence on what `scripts/multiagent.sh --wave N` does with it. The
  table itself is unchanged, since the column is optional.

- **`tests/test_multiagent_docs_and_waves.py`** (new). Six tests: two for
  DPR-2's provisioning half (a registered map and its sibling documents are
  read and seeded at their registered path; a legacy flat-layout issue is
  unaffected), four for DPR-3 (`--wave` scopes both provisioning and the
  cap; the default is wave 1 with the next wave named; a wave above the
  map's highest is refused; a map with no `Wave` column is unaffected).

## Test commands and output

Full run of the new file, plus the pre-existing multiagent regression
suites (unchanged behaviour):

```
$ python3 -m pytest -q tests/test_multiagent_docs_and_waves.py tests/test_swarm_seeding.py tests/test_swarm_cap.py tests/test_swarm_script_parser.py
.............................
29 passed in 7.94s
```

The three required house checks, plus the new file again:

```
$ python3 -m pytest -q tests/test_writing_style.py tests/test_terminology.py tests/test_house_style.py tests/test_multiagent_docs_and_waves.py
..........................................................................
..............
110 passed in 4.61s
```

`bash -n` on both scripts, clean; `shellcheck` reports only pre-existing
classes of warning (an unused `COMPASS_HOME` that was already unused before
this change, and `SC1091` info notices that a sourced file cannot be
followed at lint time), nothing new.

Red-green evidence recorded through this worktree's own CLI
(`/Users/jed/dev/.compass-worktrees/dispatch-protocol-subtask-1/bin/compass`),
one red before each scenario's code changed:

- `evidence/red-DPR-2.json`, `evidence/green-DPR-2.json` (two rounds - the
  registry lookup and seeding loop, then a `PBW-A8` fix found while running
  the required house checks; a real, observed failure both times, not a
  reworded one).
- `evidence/red-DPR-3.json`, `evidence/green-DPR-3.json`.
- `changed-file add` recorded for `scripts/multiagent.sh`,
  `scripts/lib/issue-docs.sh` (DPR-2 and DPR-3) and
  `templates/distribution-map.md` (DPR-3).

## What I could not do

- DPR-2's integration half - `integrate.sh` reading the map from the
  registered path - is subtask-3's, per the brief. Not touched.
- `tests/fixtures/repaired-file-structure.json` and `docs/system-spec.md`
  were not asked for by any test I wrote or ran; nothing in this subtask
  touched them.

## Decisions the brief did not settle

- **"A wave above the ceiling is refused"** (DPR-3) reads as the map's own
  highest staged wave, not the worktree cap - the scenario's own numbers (3
  waves, each of at most 3, against a ceiling of 4) mean the cap can never
  be the thing that refuses a wave in that scenario, so "ceiling" has to
  mean the map's highest wave number. `--wave 4` against a 3-wave map is
  refused with that reading; the cap still applies separately, to whichever
  wave is actually chosen.
- **`--wave` against a map with no `Wave` column** is refused
  (`"multiagent.sh: --wave given but the map has no Wave column."`) rather
  than silently ignored - not specified by DPR-3, but a wave number a map
  cannot honour is a real mistake, not a no-op.
- **`delivery-approach`'s pre-rename filename** stays as a literal
  flat-path check in `multiagent.sh` itself, because the artifact
  resolver's rename table (`cli/compass_pkg/core.py`) does not carry that
  pairing and is outside this subtask's files.
- **Dropped the `# shellcheck source=scripts/lib/issue-docs.sh` directive**
  rather than adding a named exemption to `tests/test_writing_style.py`'s
  `PBW-A8` rule (which flags the directive's repo-root-relative path
  resolution, same as the existing `compass-python.sh` directive already
  has an exemption for) - that test file is not one this subtask owns. The
  `source` line works identically without the hint; shellcheck simply
  cannot follow it at lint time, same as it already cannot follow
  `compass-python.sh`.
- **Fixed a bug found while implementing**: `issue_doc_path` first computed
  `compass_home` one directory too shallow, and Bash 3.2 (macOS's
  `/bin/bash`) raises "unbound variable" on `"${arr[@]}"` over a
  zero-element array under `set -u` - both are described in this
  worktree's local devlog, not committed with the code.
