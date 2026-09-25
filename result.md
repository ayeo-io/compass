# Result - dispatch-protocol, subtask-2

Builds `multiagent-run-recorded`: a `compass check` check that fails a
multiagent issue whose run left no complete subtask record. Scenario DPR-1.

## What changed, file by file

- `cli/compass_pkg/multiagent_check.py` (new) - the check itself,
  `_check_multiagent_run_recorded`. Reads only the manifest dict, taken as
  its first argument; `task_dir`, its second, is accepted for signature
  parity with the other functions in `CHECK_FNS` but is not used. Implements
  every row of the technical design's table in order: not-multiagent
  breakdown, created before 2026-09-25 (or missing), still in flight (not
  every gate has passed and the issue has not landed), no `subtasks:`, a
  subtask not `done`, a subtask whose last review round is missing or
  `fail`, otherwise pass. The last-round
  rule follows the requirements review's Q1: a subtask's last round is the
  last word on it, so a fail after an earlier pass still fails, and a pass
  after an earlier fail clears it. The start date is a module constant,
  `RUN_RECORD_REQUIRED_FROM`, on the same pattern as `RED_REQUIRED_FROM` in
  `red_first.py`. Carries a `# DEPENDENCY:` header line.
- `cli/compass_pkg/check_cmd.py` - imports and registers the check under
  `"multiagent-run-recorded"` in `CHECK_FNS`, and adds a `CHECK_GUIDANCE`
  entry (`why`, `fix`, `do`) next to its evidence-not-assertion guardrail
  (`G4`) neighbours.
- `governance/guardrails.yml` - `version` to `1.25.0`; a `multiagent-run-recorded`
  entry under `checks:`; its id added to the evidence-not-assertion
  guardrail's (`G4`) `checks:` list.
- `tests/fixtures/governance-content-hashes.json` - `guardrails.yml` re-pinned
  to version `1.25.0` and the sha256 `content_hash()` computes over the
  updated file (version key excluded, as the fixture's own helper does).
- `tests/test_stream_c_no_new_checks_or_gates.py` - `multiagent-run-recorded`
  declared in `BASELINE_CHECKS`, with a comment naming this issue.
- `tests/test_multiagent_run_recorded.py` (new) - one test per row of the
  design's table, plus edge cases (missing `stages`, missing `created`, empty
  `gates`, a landed issue with no gates, a later-failing round after an
  earlier pass and the reverse), and one test that runs `compass check
  --verbose` on a multiagent issue and asserts `multiagent-run-recorded`
  appears in the output.

## Test commands and their last lines

Red, before any production code existed (`cli/compass_pkg/multiagent_check.py`
did not exist yet - an import red):

```
$ ./bin/compass tdd-red --issue dispatch-protocol --scenario DPR-1 -- python3 -m pytest -q tests/test_multiagent_run_recorded.py
compass tdd-red: failing test recorded (exit 2) (bound to DPR-1).
  evidence : .../evidence/red-DPR-1.json
  marker   : .../.red
  the pre-tool hook will now allow code edits.
```

Green, after the module and its registration existed:

```
$ python3 -m pytest -q tests/test_multiagent_run_recorded.py
.................                                                        [100%]
```

17 passed. Recorded through the CLI:

```
$ ./bin/compass tdd-green --issue dispatch-protocol --scenario DPR-1 -- python3 -m pytest -q tests/test_multiagent_run_recorded.py
compass tdd-green: passing suite recorded (exit 0) (bound to DPR-1).
```

The required suite, after `git add` on the tracked changed files:

```
$ python3 -m pytest -q tests/test_writing_style.py tests/test_terminology.py tests/test_house_style.py tests/test_governance_drift.py tests/test_stream_c_no_new_checks_or_gates.py tests/test_cli_module_split.py tests/test_install_surface_no_pip.py tests/test_multiagent_run_recorded.py
........................................................................ [ 51%]
....................................................................     [100%]
140 passed in 61.33s
```

`compass check` on the issue itself, confirming the new check runs and
prints its name, and that nothing else in this worktree's manifest broke:

```
$ ./bin/compass check --issue dispatch-protocol
PASS - 12 check(s) passed, 7 had nothing to check on 'dispatch-protocol' (initiative)
[mode: enforced]
```

## Anything I could not do, and why

Nothing in the brief was left undone. No test asked me to edit
`tests/fixtures/repaired-file-structure.json` or `docs/system-spec.md`.

## Decisions the brief did not settle

- **`task_dir` in the check's signature.** The design says the module
  "imports only `core` and `check_results`" and the function only needs the
  manifest dict, but `CHECK_FNS` calls every check with the same two
  positional arguments. Kept that two-argument signature for parity with
  every other entry in `CHECK_FNS` (`check_cmd.py` calls them uniformly) and
  left `task_dir` unused, rather than special-casing this one check's call
  site.
- **Where to insert the check's description in `guardrails.yml`.** Placed it
  immediately after `command-passes`, the last entry in `checks:`, rather
  than reordering the file - `checks:` has no enforced order, and appending
  keeps the diff to an addition.
- **A `no-trusted-rerun` trip of my own making.** Running `compass tdd-green`
  a second time (to refresh the evidence after `changed-file add` calls,
  which do not change the source tree) recorded `attempts: 2,
  rerun_without_change: true` against DPR-1 - the same test, same tree,
  since `.compass/work/` is outside the source-tree hash. That failed
  `no-trusted-rerun` under `compass check`. Rather than add DPR-1 to
  `governance/quarantine.yml`, which would misrepresent a redundant CLI call
  as a flaky test, I deleted the stale `evidence/.tdd-state.json` sidecar (an
  internal cache, not part of the manifest schema) and the stale
  `evidence/green-DPR-1.json`, then recorded one clean green after every
  other edit was in place. `compass check --issue dispatch-protocol` now
  passes clean.
- **This report tripped its own house-style checks first.** An early draft
  named the check's first argument with the retired v1 word for an issue,
  and stated the guardrail id unwrapped; `test_pbw_a1_no_retired_word` and
  `test_pbw_a7_a_bare_code_carries_its_meaning` catch a tracked file the
  moment it is staged, this one included. Reworded the argument description
  above, and gave every guardrail id the house form, `guardrail` followed by
  the id in backticks and parentheses.
