# Policy diff

This page is the owning doc for `compass policy diff`. It states what the
command compares, how a reference is read, what each part of the report
means, and the exact shape of the JSON it prints. From 6.0.0 the keys, their
order and their values are a public contract: a change to any of them is a
breaking change.

The code is `cli/compass_pkg/replay.py` (the references, the replay, the open
issues, the document and its text) and `cli/compass_pkg/policy_cmd.py` (the
verb). The decisions behind it are ADR-036 (an issue runs against a stored
generation) and ADR-037 (a change is classified by its effect).

## What it compares

`compass policy diff A B` compares two configurations two ways.

1. **Classification.** The classifier (ADR-037) runs over the whole grid of
   assessments and says whether `B` is `equivalent` to `A`, `tightening`,
   `loosening` or `incomparable`. The document holds the classifier's own
   JSON, unchanged, in `classification`. `governance/routing-policy.md` describes
   that shape.
2. **Replay.** The command runs the evaluator under both configurations at
   many assessments and lists each one whose result differs. A difference is a
   `field`, a `key`, the value `before` (under `A`) and the value `after`
   (under `B`).

Classification says whether `B` owes less. Replay says where. A change to a
check's wording, or to a value no rule reads, is `equivalent` and replays no
change. A change to which approach an assessment routes to can be
`equivalent` by obligations and still replays a change to `approach`.

## References

| Reference | Meaning |
|---|---|
| `default`, `default@6`, `compass:default@6` | The shipped default. Only major 6 ships; `default@6.0.0` is accepted |
| `project` | The root `compass.yml` over the shipped default, or the shipped default alone when there is no file |
| `legacy` | The project's copied `governance/routing-policy.yml` and `governance/guardrails.yml`, through the legacy adapter |
| `git:<revision>` | The project's `compass.yml` at that git revision over the shipped default, or the shipped default alone when the file did not exist then |
| a path | One `compass.yml` over the shipped default, as `compass policy lint --file` reads it |
| `github:<owner>/<repo>@<ref>#<sha>` | A git parent written as in `extends:` ([git-parents.md](git-parents.md)): the shipped default, then the parents it extends from the furthest, then that parent. The project's own `compass.yml` is not part of it |
| `generation:<slug>:<n>` | Refused: `policy diff` does not yet compare against a stored generation. Use `compass policy show --issue <slug>` for what an issue resolves to now |

| Arguments | `A` | `B` |
|---|---|---|
| none | `git:HEAD` | `project` |
| one | `project` | the argument |
| two | the first | the second |

A reference that does not name a keyword is read as a path, relative to the
working folder. A file that does not parse, fails its own layer check or does
not merge is refused with its label and a pointer to `compass policy lint
--file`. The command does not lint: it shows what a change does, including a
change that lint would refuse.

A git parent is data. Each layer of its chain must pass the parent layer check
before it merges, so a settings key or an `unlock:` is refused (exit 2) with the
finding's text. An uncached pin is fetched into the project's
`.compass/cache/parents/`, after one line on stderr (`compass policy diff:
fetching <ref> into .compass/cache/parents/`); `--offline`, or `COMPASS_OFFLINE=1`, reads the cache
only and refuses an uncached pin with `L-PARENT-NOT-CACHED`. A bad spelling is
refused with `L-PARENT-FORM` or `L-PARENT-NO-SHA` before git runs. The
classification is the raw one, with no waiver applied, so a parent that loosens
the default shows `loosening` whether or not its own waiver excuses it.

## The sets that are replayed

| Set | What is replayed |
|---|---|
| `grid` | One assessment for each combination of value classes of the grouped grid (ADR-037), with no labels |
| `labels` | The same combinations with each non-empty subset of the labels the rules name, by size then name |
| `archive` | The recorded `assessment` of each issue under `.compass/work/`, by slug, with no issue layer |

A value class stands for every value of a dimension that no rule tells apart.
The point uses the first value, and `represents` lists the others. A value
that one configuration accepts and the other does not, and that a rule reads,
is a difference of its own (`dimensions.values`, with `before` and `after`
saying whether each side accepts it).

With more than eight named labels the `labels` set is skipped, with the
reason, and the other sets still run. When the two configurations are
identical nothing is evaluated and every set is skipped with the reason.
An issue with no `assessment` mapping is not replayed, and the `archive` set
says so when no issue has one. A manifest that does not parse is listed in
`unreadable`.

### Differences

The facts compared are the classifier's facts plus `approach` and
`rules_fired`: `approach`, `stage_mode`, `entry`, `exit`, `gate_set`,
`gate_checks`, `gate_accepts`, `artifacts_owed`, `required_skills`,
`blocked_stages`, `required_artifacts`, `checkpoints`, `ceilings`, `checks`,
`artifact_depends_on`, `artifact_checks`, `rules_fired`. A fact that maps
names to values gives one difference for each name whose value differs, and
`key` is that name. Otherwise `key` is null.

An assessment one side cannot run is one `evaluation` difference. Its
`before` and `after` are `runs`, `refused: <reason>` (a routing conflict) or
`cannot run: <message>` (such as a value the vocabulary lacks). Two sides
that fail in the same way are no difference.

## `--open`

`--open` runs each issue that is not done (in the backlog, ready, in progress
or in review) over both configurations with its own `config:` layer, at its
recorded assessment. Each issue is listed with the state its records show.
It lists:

- each issue whose obligations differ, with its differences;
- each issue whose layer one side cannot merge, as `unresolved` with the side
  (`a` or `b`) and the message;
- each issue waiver whose waived field has a different parent value under `B`
  than under `A`, as needing re-approval at the next reassess.

An issue that is done, whatever its close reason, is never examined. The diff does not read a
stored generation, so `A` stands for what the issue
runs against and `B` for what it meets at its next reassess. The command
writes no file of the project, with two exceptions. When a reference is a git
parent that is not cached and the run may fetch, it fills the git parent cache
in `.compass/cache/parents/`, and it adds `cache/` to `.compass/.gitignore` if
that file does not list it.

## Options and exit codes

| Option | Meaning |
|---|---|
| `--open` | Add the open-issue comparison above |
| `--exit-code` | Exit 1 when anything differs, as `git diff --exit-code` does |
| `--offline` | Read a git parent from the cache only and fetch nothing |
| `--json` | Print the document below |

| Exit | Meaning |
|---|---|
| 0 | The report was printed, whether or not anything differs. Also exit 0 with `--exit-code` when nothing differs |
| 1 | With `--exit-code` only: the classification is not `equivalent`, a replayed assessment changes, or `--open` lists an issue or a waiver |
| 2 | A reference cannot be read or resolved, or a configuration cannot be evaluated |

The text output shows the two references, the classification, one line for
each set, the first five changes of each set (`TEXT_LIMIT`) and a count of
the rest, any unreadable manifests, and with `--open` the issues and waivers.
A list that differs prints what was removed and what was added. The full list is in
`--json`. Identical configurations print the heading and one line that says
there is no difference.

## `compass policy diff --json`

```json
{
  "schema": 1,
  "differs": true,
  "a": {"ref": "default@6", "kind": "default", "default_version": "6.0.0",
        "digest": "sha256:...", "capabilities": []},
  "b": {"ref": "project", "kind": "project", "default_version": "6.0.0",
        "digest": "sha256:...", "capabilities": []},
  "classification": {"schema": 1, "result": "loosening", "...": "the classifier's own JSON"},
  "replay": {
    "sets": [{"name": "grid", "replayed": 288, "changed": 144, "skipped": null}],
    "changes": [
      {"set": "grid", "issue": null,
       "assessment": {"familiarity": "greenfield", "labels": [], "risk": "trivial"},
       "represents": {"risk": ["trivial", "contained"]},
       "differences": [{"field": "approach", "key": null, "before": "quick-fix",
                        "after": "regular"}]}
    ],
    "unreadable": []
  },
  "open": null
}
```

The pinned example is `tests/fixtures/policy-diff-json-example.json`. It
holds every part of the document, including an open issue that cannot merge
and a waiver that needs re-approval. `tests/test_policy_diff.py` checks the
example against `replay.DIFF_JSON_SHAPE`, and `replay.diff_shape_errors`
checks any document against it.

| Key | Type | Meaning |
|---|---|---|
| `schema` | integer | The version of this shape. It is 1 |
| `differs` | boolean | True when the classification is not `equivalent`, any replayed assessment changes, or `--open` lists an issue or a waiver |
| `a`, `b` | object | The two sides, below |
| `classification` | object | The classifier's `to_json()` with the two references as `parent` and `child` |
| `replay` | object | `sets`, `changes` and `unreadable`, below |
| `open` | object or null | Null without `--open` |

Each side has these keys, in this order:

| Key | Type | Meaning |
|---|---|---|
| `ref` | string | The label: `default@6`, `project`, `legacy`, `git:<revision>`, `file:<name>` or a git parent as it was written. A file's name is relative to the project root, or its own name when it is outside the root, so the document holds no machine path |
| `kind` | string | `default`, `project`, `legacy`, `git`, `file` or `parent` (a git parent) |
| `default_version` | string or null | The version of the shipped default beneath it, null for `legacy` |
| `digest` | string | `sha256:` and a digest of the resolved configuration and its capabilities |
| `capabilities` | list | The capability switches that are on, sorted |

`replay.sets` lists `grid`, `labels` and `archive`, in that order, each with
`name`, `replayed` (how many assessments ran), `changed` (how many differ) and
`skipped` (null, or the reason the set did not run).

`replay.changes` lists every assessment whose result differs: all of `grid`,
then `labels`, then `archive`. Within a set the order is the order of the
scan: each combination of value classes in the order of the configuration's
dimensions, then each label subset; the archive is by slug. Each change has
these keys, in this order:

| Key | Type | Meaning |
|---|---|---|
| `set` | string | `grid`, `labels` or `archive` |
| `issue` | string or null | The slug, for `archive` only |
| `assessment` | object | The assessment, with its keys sorted |
| `represents` | object or null | For each dimension, the values the point stands for; null for `archive` |
| `differences` | list | Each difference, below |

A difference has these keys, in this order: `field`, `key` (a string or
null), `before` and `after` (any JSON value).

`replay.unreadable` lists, by slug, each manifest under `.compass/work/` that
does not parse as a mapping. Such a manifest is not replayed, and it is listed
here instead of being dropped. It does not make `differs` true.

`open` has `examined` (the number of open issues run), `issues`, `waivers` and
`unreadable`, in that order. `open.unreadable` is the same list: a manifest that
does not parse has no readable status, so it may be an open issue that was not
examined.

Each entry of `open.issues`, by slug, has these keys, in this order: `issue`,
`status`, `assessment`, `differences` and `unresolved` (null, or an object
with `side` and `message`).

Each entry of `open.waivers` has these keys, in this order: `issue`,
`waiver` (the id, such as `issue:checks.suite-passed`), `entry`, `field`,
`before` (the parent value when the waiver was approved), `after` (the value
now), and `message`.

The document holds no time and no path outside the project, so the same input
gives the same bytes.

## What this page does not cover

- A stored generation (`generation:<slug>:<n>`) and the git parent form. Both wait for the pieces they need.
- `compass policy update`, which `docs/policy-update.md` covers, and `compass policy migrate`. Both call the same replay.
- The classifier's own shape, which `governance/routing-policy.md` describes.
