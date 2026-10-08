# Policy test and init-preset

This page is the owning doc for `compass policy test` and `compass policy
init-preset`. It states the fixture format, what the test checks and in what
order, the exit codes and the exact shape of the JSON each command prints.
From 6.0.0 the fixture format, the keys of both reports, their order and their
values are a public contract: a change to any of them is a breaking change.

A preset is a folder with a `compass.yml` that other projects extend as a git
parent ([git-parents.md](git-parents.md)). The test shows that the preset
computes what its authors say it does, and that it keeps the framework locks.

The code is `cli/compass_pkg/preset_test.py` (the test and its report),
`cli/compass_pkg/preset_init.py` (the scaffold) and
`cli/compass_pkg/policy_cmd.py` (the two verbs). The decisions behind it are
ADR-035 (the merge grammar), ADR-037 (classification) and ADR-039 (waivers
and locks).

## A preset folder

```
my-preset/
  compass.yml
  compass-fixtures/
    small-work.yml
    large-work.yml
```

| Path | Meaning |
|---|---|
| `compass.yml` | The preset. It is read as a parent over the shipped default and over any git parent it extends |
| `compass-fixtures/` | The fixtures, one `.yml` file each, directly in the folder or in a group folder below it |

`compass policy init-preset` writes this layout. The test runs on the folder
given, or on the working folder when none is given.

## Fixture groups

A folder inside `compass-fixtures/` is a group. Its name is the folder's path
below `compass-fixtures/`, written with `/`, so the fixtures in
`compass-fixtures/meets/banking/` are in the group `meets/banking`. A group can
be at any depth, and a folder that holds fixtures and folders is a group of its
own, apart from the groups below it. A fixture directly in `compass-fixtures/`
has no group.

```
my-preset/
  compass.yml
  compass-fixtures/
    small-work.yml            # no group
    meets/
      banking/
        large-work.yml        # group meets/banking
```

Each folder in the path is named with lower-case letters, digits and hyphens,
starting with a letter or digit, and a group is at most 3 folders deep. A folder
that breaks either rule is a problem and is not read.

The fixture groups of a preset change nothing about how a fixture runs: every fixture runs over the
same merged configuration. The group is a label that the report carries, with a
count for each group, so a tool that reads the report can say which named set of
fixtures a preset passes. The test does not follow a link to a folder, so a link
cannot lead the test outside the preset. A folder whose name starts with a dot
is ignored.

## What `compass policy test` does

The test runs in two steps and does the second only when the first passes.

1. **Lint.** It lints the preset as a parent, with the shipped default and
   the preset's pinned git parents beneath it. A parent is data only, so the
   lint refuses what a parent must not carry and what a lock forbids. See
   [policy-lint.md](policy-lint.md) for each code.

   | Code | Meaning in a preset |
   |---|---|
   | `L-UNLOCK-PLACEMENT` | The preset carries `unlock:`. Only a project can lift a lock |
   | `L-SETTINGS-KEY` | The preset carries a settings key such as `autonomy` or `allow_project_commands`. Settings belong to a project |
   | `L-IMPL-UNKNOWN` | A check names an `impl` that the check registry does not hold |
   | `K-LOCK-REFUSED` | The preset changes a locked entry |
   | `C-LOOSENING` | The preset owes less than its parent and carries no valid waiver for it |
   | `W-NO-OWNER` | The preset carries a waiver and declares no `owner` |

   A waiver in a preset is approved by the preset's own `owner`, or by the
   names in the `approvers.project-waiver` of the layer above it, as for any git
   parent. The `owner` of the project that runs the test, and of a project that
   later extends the preset, does not count. Every finding names the layer
   `preset`.

   Any other lint finding fails the test too. The text and JSON reports give
   the finding as `policy lint` does. A preset that extends a pinned git parent
   fetches it when it is not cached, into `.compass/cache/parents/` in the
   preset folder. `--offline`, or `COMPASS_OFFLINE=1`, reads the cache only and
   fails with `L-PARENT-NOT-CACHED` for a parent that is missing.
2. **Fixtures.** It merges the shipped default, the git parents and the preset
   in that order, then evaluates every fixture over the result.

The test never runs anything the preset carries.

## A fixture

A fixture is a mapping with these keys.

| Key | Required | Meaning |
|---|---|---|
| `name` | no | The name the report shows. It defaults to the file name without `.yml` |
| `assessment` | yes | The assessment to evaluate: a value for each dimension to set, such as `risk`, `familiarity`, `size`, `goal` and `role`, and `labels`, a list of text. Any other key is an error |
| `expect` | yes | What the evaluation must compute. It holds at least one of the four keys below |

| `expect` key | Value | The fixture passes when |
|---|---|---|
| `approach` | an approach name | the computed delivery approach is that name |
| `gates` | a list of gate ids | the gates in force are exactly those ids, in any order |
| `stages` | a mapping from a stage to a mode | each stage named has that mode; a stage not named is not compared. An empty `stages` mapping compares nothing, so it is an error |
| `checks` | a list of check ids | the checks that the gates in force run are exactly those ids, in any order |

```yaml
name: Small contained work also gets the clarity review
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: small
  goal: delivery
  role: engineer
  labels: []
expect:
  approach: quick-fix
  gates: [G1, G2, G3, G4, verify.clarity, verify.correctness, verify.governance,
    verify.traceability]
  stages: {implement: full}
```

Fixtures run in this order: the fixtures with no group, then each group by name,
and within each the fixtures by file name. A fixture has one of three statuses.

| `status` | Meaning |
|---|---|
| `pass` | Every expectation matches |
| `fail` | At least one expectation differs. Each difference is in `mismatches` |
| `error` | The fixture cannot be run: the file cannot be read or does not parse, a key is unknown or missing, a list or mapping has the wrong shape, or the evaluator rejects the assessment (for example a value that the configuration's vocabulary does not hold). The reason is in `message` |

A mismatch names its `field` as `approach`, `gates`, `checks` or
`stages.<stage>`, with the `expected` and `actual` values. A list is shown
sorted. For a stage that the computed result does not hold, `actual` is `null`.
An empty `gates` or `checks` list is an expectation that none are owed, and it
compares. In the text report, a message that runs over several lines stays
indented under its fixture.

## What fails the run

| Cause | Where it shows |
|---|---|
| A lint error | `lint.ok` is `false`, the fixtures are not run and `fixtures_run` is `false` |
| A fixture with status `fail` or `error` | `fixtures` and `totals` |
| No fixture files | `problems` holds `no fixtures` |
| A group folder with no fixture file and no folder in it | `problems` names it, so a group that was meant to hold fixtures cannot pass with none |
| A group folder whose name is not lower-case letters, digits and hyphens starting with a letter or digit, or that is more than 3 folders deep | `problems` names it. The folder is not read |
| A link of any kind inside `compass-fixtures/` or a group (to a file, to a folder or to nothing) | `problems` names the link. The test does not follow it, so it reads and prints nothing outside the preset |
| A file in `compass-fixtures/` or in a group that ends in `.yaml`, or in `.yml` with any capital letter | `problems` names it. Fixture files end in lower-case `.yml` |
| A `.yml` file that is not a regular file | `problems` names it |

A file that starts with a dot, and a file with any other ending, are ignored.

## Exit codes

| Code | Meaning |
|---|---|
| Exit 0 | The lint passed, there is at least one fixture, every fixture passed and `problems` is empty |
| Exit 1 | A lint error, a fixture that failed or errored, or a problem |
| Exit 2 | The folder or its `compass.yml` is missing, cannot be read or is not UTF-8 text |

A `compass.yml` that can be read but is malformed YAML is a lint error
(`L-LOAD`), so it exits 1 and the report shows the finding. A fixture file that
cannot be read is an error on that fixture, not exit 2.

## The `--json` report of `compass policy test`

`--json` prints one document. Keys appear in this order, and these are all of
them.

| Key | Value |
|---|---|
| `schema` | `1` |
| `preset` | The folder as a person typed it when it is below the working folder, otherwise the folder's own name. It is never an absolute path |
| `result` | `pass` or `fail` |
| `lint` | An object, below |
| `fixtures_run` | `true` when the fixtures were run, `false` when the lint failed first |
| `totals` | An object, below |
| `fixtures` | A list with one object for each fixture, below |
| `problems` | A list of texts, each one a cause from "What fails the run" |
| `groups` | A list with one object for each group that holds a fixture, by group name, below. It is empty when no fixture has a group, and when the lint failed before the fixtures ran |

| `lint` key | Value |
|---|---|
| `ok` | `true` when the lint found no error |
| `stopped_after` | The lint group that had an error, or `null` |
| `findings` | The findings in the shape `policy lint --json` gives: `code`, `level`, `layer`, `path`, `group`, `message` and `detail` |

| `totals` key | Value |
|---|---|
| `fixtures` | The number of fixtures run |
| `passed` | How many have status `pass` |
| `failed` | How many have status `fail` or `error` |

| `fixtures` key | Value |
|---|---|
| `file` | The name of the fixture file, such as `small-work.yml`. The folder it is in is `group`, so `group` and `file` together make the path below `compass-fixtures/` |
| `name` | The fixture's name |
| `status` | `pass`, `fail` or `error` |
| `mismatches` | A list of objects with `field`, `expected` and `actual`; empty unless the status is `fail` |
| `message` | The reason when the status is `error`, otherwise `null` |
| `group` | The group of the fixture, such as `meets/banking`, or `null` when the file is directly in `compass-fixtures/` |

| `groups` key | Value |
|---|---|
| `group` | The group name |
| `fixtures` | The number of fixtures in that group, not counting the groups below it |
| `passed` | How many have status `pass` |
| `failed` | How many have status `fail` or `error` |
| `result` | `pass` when `failed` is 0, otherwise `fail` |

```json
{
  "schema": 1,
  "preset": "my-preset",
  "result": "fail",
  "lint": {"ok": true, "stopped_after": null, "findings": []},
  "fixtures_run": true,
  "totals": {"fixtures": 1, "passed": 0, "failed": 1},
  "fixtures": [
    {
      "file": "example.yml",
      "name": "Small contained work also gets the clarity review",
      "status": "fail",
      "mismatches": [{"field": "stages.implement", "expected": "light", "actual": "full"}],
      "message": null,
      "group": "meets/banking"
    }
  ],
  "problems": [],
  "groups": [{"group": "meets/banking", "fixtures": 1, "passed": 0, "failed": 1, "result": "fail"}]
}
```

The text report adds one line for each group after the fixture totals, such as
`group meets/banking: 2 run, 1 passed, 1 failed`.

The key order of a report with groups is pinned by
`tests/fixtures/preset-interfaces/policy-test-groups.json`, and
`tests/test_preset_interfaces.py` compares a real report with it key for key.
`groups` and `group` are the last keys of their objects, so a reader written for
the earlier report still finds every key it knew in the same place.

### What the report does not have yet

There is no `--group` selector to run one group. The report holds every group,
and a tool that wants one reads it from `groups`. A later release can add the
selector without changing the report.

## `compass policy init-preset DIR --owner NAME`

The command writes a working preset into `DIR`, creating the folder when it is
missing.

| File | Content |
|---|---|
| `compass.yml` | `schema: 1`, the `owner` given, and one change to the shipped default: the quick fix approach also runs the clarity review |
| `example.yml` in `compass-fixtures/` | A fixture that expects that change, and shows the four `expect` keys. Its gates are computed when the file is written, so they match the shipped default of that release |
| `README.md` | How to test the preset, how to write a fixture and how a project extends the preset |
| `.gitignore` | Ignores `.compass/`, where a fetched git parent is cached |

The scaffold passes `compass policy test` where it stands. The command never
overwrites a file: when `DIR` holds any of the four files it names them and
writes nothing. It writes no CI workflow, because a workflow must say how to
install Compass.

| Code | Meaning |
|---|---|
| Exit 0 | The files are written |
| Exit 1 | A file exists; nothing is written |
| Exit 2 | `DIR` is a file, `--owner` is missing, empty or holds a control character (so it is one line of text), or a file cannot be written |

A failed write can leave some files in `DIR`. The message names the files
already written, and a re-run is then refused until they are removed. A link
that points nowhere counts as an existing file.

### The `--json` report of `compass policy init-preset`

| Key | Value |
|---|---|
| `schema` | `1` |
| `dir` | `DIR`, shown as `preset` is above |
| `result` | `written` or `refused` |
| `files` | The files written, or on a refusal the files that already exist; paths from `DIR`, in the order of their bytes (`README.md` comes before `compass.yml`) |

```json
{"schema": 1, "dir": "my-preset", "result": "written",
 "files": [".gitignore", "README.md", "compass-fixtures/example.yml", "compass.yml"]}
```
