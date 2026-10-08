# Policy migrate

This page is the owning doc for `compass policy migrate`. The command turns a
project that runs on copied legacy governance and `.compass/config.yml` into a
`compass.yml` that holds only the project's local edits over the shipped
default preset, plus the project's settings. It finds which shipped release the
copy came from, adopts the defaults that moved since, and proves the local
edits with the classifier, or says exactly what it could not express. From
6.0.0 the JSON shape, the exit codes and the codes below are a public contract:
a change to a key, its order or a code is a breaking change.

The code is `cli/compass_pkg/policy_migrate.py` (the plan, the writes and the
report), `cli/compass_pkg/shipped_releases.py` (the table of releases) and
`cli/compass_pkg/policy_cmd.py` (the command). The decisions behind it are
ADR-037 (classification), ADR-039 (waivers), ADR-042 (the shipped preset and
the legacy views) and ADR-043 (one project file).

## When the overlay takes effect

`compass check`, the evaluator and the other readers resolve each issue's
configuration through the effective view. After `--apply`:

- an issue with no stored generation is judged by `compass.yml` over the
  shipped default at once;
- an issue with a generation keeps it until its next reassess
  (`compass approach evaluate --write`), which commits the overlay.

The classifier proves the two configurations equivalent before anything is
written, so no verdict moves at the switch. The governance copies stay in
place as the record of what the project ran. The report and the `--apply`
output say this in a closing line.

## What it reads

| Source | Used for |
|---|---|
| `governance/routing-policy.yml` and `governance/guardrails.yml` | The overlay. Both must be present: Compass does not read a lone one |
| `.compass/config.yml` | The settings that move into `compass.yml` and the state that moves to the state file in `.compass/` |
| The table of shipped releases | The base release the copy came from (below) |

A project can have either of the first two or both. A project with neither has
nothing to migrate.

## Dry run, apply and the old files

The command is a dry run unless it is given `--apply`. A dry run prints what
it would do and writes nothing.

`--apply` never loses a file. It follows this order, so the project is always in the
whole old state or the whole new state:

1. Copy each source, byte for byte, into the `legacy` folder of `.compass/`.
2. Write `migration.yml` in `.compass/`: the digest of each source, the tool version, and whether this run created the state file.
3. Write `state.yml` in `.compass/`, only when the old file held state and the state file does not exist or an earlier stopped run made it.
4. Write `compass.yml` atomically. This is the commit point.
5. Remove `.compass/config.yml`.

What happens to each old file:

| File | After `--apply` | Why |
|---|---|---|
| `governance/routing-policy.yml`, `governance/guardrails.yml` | Kept in place, and copied | `compass check` and the evaluator still read them, so removing them would change behaviour the overlay does not yet carry |
| `.compass/config.yml` | Copied, then removed | A `compass.yml` that Compass reads, with settings left in the old file, is refused as a settings conflict |

The kept copies and the overlay are two sources that can differ. The digest of
each kept copy is in `migration.yml`. Removing the copies is a follow-up for
when the readers move; the `legacy` folder already holds them, so nothing is
lost. A person restores an old file by copying it back from the `legacy`
folder. There is no `--undo` yet.

If a run stops after step 4 and before step 5, `compass.yml` and the old file
exist together. The next `--apply` sees `migration.yml` and a digest of the old
file that still matches, and removes it. An old file that was edited since does
not match, and the command refuses.

## When it refuses

A refusal exits 2, prints its reason on stderr, prints nothing on stdout and
writes nothing.

| Cause | Reason |
|---|---|
| The project is the Compass framework repository | Its governance files are generated from the shipped preset |
| `compass.yml` exists and `migration.yml` records that this command wrote it | The settings now live in `compass.yml`. The message says how to go back: copy the old files from the `legacy` folder, then remove `compass.yml` and `migration.yml`. It never advises moving `compass.yml` away, which would put the settings back to their defaults |
| `compass.yml` exists, has `schema:`, and no marker | Compass reads it, so there is nothing to migrate into. When `.compass/config.yml` still sets keys, the message names them. This covers both settings files being present, which Compass does not merge |
| `compass.yml` exists and has no `schema:` | Compass does not read it, so it is another tool's file. The message says to move it to another name or add `schema: 1` |
| One of the two governance files is present without the other | A copy needs both |
| A source cannot be parsed or converted | The message names the file |

The one exception to the `compass.yml` refusals is the interrupted run above.

## The base release and the overlay

1. Convert the project's two files to catalogue form with the legacy adapter. Call the result the copy.
2. Find the base release in the table of shipped releases, in this order:
   - the release whose `version:` lines (both files carry one) match the copy's, and the newest when two tags shipped the same files;
   - else the release that gives the fewest overlay entries, and the newest of equals;
   - else, when even the nearest needs more than 40 entries, the files this install ships, reported as `as-built`.
   The `current` release is the pair of files this install ships. The version lines are a hint: the classifier check below runs whichever way the release was found.
3. Compare the copy with the base release entry by entry, in catalogue order and then id order. These are the local edits:
   - an id only in the copy is an `add`;
   - an id only in the base release is a `remove`;
   - an entry with a changed field is a `set` of that field. A map field is written as `{set, remove}`, so one changed rule is one entry of the overlay;
   - an entry that lost a field is a `replace` with the whole entry, because a field cannot be unset.
4. A rule set's `order` numbers are compared by sequence. Removing a rule from the middle renumbers the rules after it and changes no relative position, so the overlay lists only the removal. A rule carries `order` only when its relative position changed or when it is added.
5. The `project:` guardrails of the copy become project checks and gates: a `command-passes` guardrail becomes a check named by the guardrail id and a slug of its name, with its parameters, and every guardrail becomes a gate at its first `checked_at` stage.
6. Merge the overlay over the preset. The result is the migrated configuration.
7. Classify the copy against the base release plus the overlay. It must be `equivalent`. That proves the overlay holds the local edits and nothing else.

Defaults that moved since the base release are **adopted** without a waiver.
They are listed in the report and in `adopted`, as entry and operation, from the
base release to the current default. An entry the project also edited keeps its
edit for the fields it edited. The report also gives the `behaviour`: the
classifier's verdict on the copy against the migrated configuration, and how
many grid points differ. Adopting a default can change behaviour; that is
reported, and it does not block.

The copy is compared with a release of the legacy files, not with the preset,
because the preset holds fields the legacy format cannot state: stage entry and
exit lists and three Definition of Done checks. Comparing with the preset would
copy those back as removals.

A value only the legacy views hold, which the catalogue cannot state, blocks by
name as `MIG-UNEXPRESSED`. Two things can differ:

- The list of stages a guardrail is checked at. A gate keeps its first stage,
  so a longer list cannot be written.
- A field of a project guardrail that neither its gate nor its check can hold,
  such as `owner`, or `params` on a check other than `command-passes`.

A project guardrail with only fields a gate and check can hold becomes a
project check and a project gate in the overlay.

## Waiver stubs, lock refusals and the lint

Only a local edit that loosens the base release, or cannot be compared with
it, needs a person's confirmation. The command classifies each overlay entry
alone against the base release. An entry that needs an excuse gets a stub:

```yaml
waiver:
  reason: Migrated from a copy of the governance files whose local edit loosens the shipped release it came from. Confirm the departure, then set approved_by and approved_on.
  approved_by: UNAPPROVED
```

The command does not invent an approval or a date. It then lints the file as
the project layer over the preset, with `policy_lint`. Every lint error is
reported. An edit that loosens an entry the framework locks is a lock refusal
(`K-LOCK-REFUSED`), which no waiver excuses. An unapproved stub (`W-UNAPPROVED`)
and a missing `owner` (`W-NO-OWNER`) block the migration too. `--apply` writes
nothing while anything is blocked. A person puts the printed `compass.yml` in
place by hand, names an `owner`, approves each stub and runs `compass policy
lint`.

An unedited copy of any shipped release migrates with no stub and no lock
refusal. A copy that matches no release (`as-built`) has every difference from
the current files as a local edit, so each removal needs approval; an explicit
`--adopt-defaults` for that case may follow in a later release.

## Settings

The command reads `.compass/config.yml` as the old reader does, and takes each
key in file order. The table says where each key goes in `compass.yml`:

| Key | Goes to |
|---|---|
| A key the catalogue lists as a settings key | `compass.yml`, same name |
| `mode` | `compass.yml` as `adoption` |
| A key `cli/migrate-map.yml` renames under `config_keys` | `compass.yml`, new name |
| `worktree_root`, `max_worktrees` or `test_command` found outside `multiagent` and `project` | `compass.yml` under `multiagent` or `project`, where the scripts read it |
| `initialised`, `records_signed_since` | The state file in `.compass/` |
| `version` | Dropped: `schema: 1` replaces it |
| Anything else | Listed as unread and not copied. It stays in the copy of the old file in the `legacy` folder |

`governance_drift` is copied and listed under `moved`, not dropped: dropping it
would turn `strict` into advisory without a word, and the legacy lint still
reads it. It is dropped in a later migration step when the legacy lint retires.
Comments in the old file are not copied; the copy in the `legacy` folder keeps
them.

The new file starts `schema: 1` and `extends: compass:default@6`, then the
settings, then the overlay. The `extends` string is built by
`layers.default_extends` from the preset's major version, and
`layers.parse_extends` reads it back, so the writer and the reader share one
spelling.

## The table of shipped releases

`governance/shipped-releases.yml` holds, for each tagged release, the version
and the content digest of its two governance files. The digest is the one
`tests/test_governance_drift.py` computes: the parsed file without `version:`.
`governance/shipped-releases.tar.xz` holds the files. An installed plugin has
no git tags, so nothing reads a tag at run time.
`scripts/generate-shipped-releases.py` writes both from the tags, and
`tests/test_shipped_releases.py` fails when the table lacks a tag or an entry no
longer matches its tag. Run the script after cutting a release tag.

## Exit codes

| Exit | Meaning |
|---|---|
| 0 | A dry run that is ready, an applied migration, or nothing to migrate |
| 1 | Blocked: the base release plus the overlay is not shown equivalent to the copy, a value cannot be written, a merge or lint error stands, or a waiver stub is unapproved. Nothing is written |
| 2 | A refusal, or a source that cannot be read |

## Output

The text output opens with `compass policy migrate: dry run - nothing was
written`, `BLOCKED - nothing was written`, `applied`, or `nothing to migrate`.
It then lists what it read, the base release, what the default adopts, the
overlay, the settings it moved, dropped and did not copy, the equivalence, each
blocked item, the files, a closing line that edits to `compass.yml` change
nothing in `compass check` or the evaluator yet, and the `compass.yml` it would
write.

## `compass policy migrate --json`

```json
{
  "schema": 1,
  "mode": "dry-run",
  "result": "ready",
  "base_release": {
    "release": "v5.3.0",
    "chosen_by": "version"
  },
  "sources": [
    {
      "path": "governance/routing-policy.yml",
      "digest": "sha256:2b2bba57040057442ad879e15aa5db381d03bba8d57d4a93f8b831be6b54ddd5"
    },
    {
      "path": "governance/guardrails.yml",
      "digest": "sha256:58bf8365ff3e3fc786771387bbf196bcb3725c7b49bb7b027d0572570d5b6f3c"
    },
    {
      "path": ".compass/config.yml",
      "digest": "sha256:5092212503c46d8d7fe6778a24a8f3cfe625ad76817ca036eb3a87f2c0e9b1a6"
    }
  ],
  "adopted": [
    {
      "catalogue": "approaches",
      "id": "full",
      "operation": "set"
    },
    {
      "catalogue": "approaches",
      "id": "hotfix",
      "operation": "set"
    },
    {
      "catalogue": "approaches",
      "id": "quick-fix",
      "operation": "set"
    },
    {
      "catalogue": "approaches",
      "id": "regular",
      "operation": "set"
    },
    {
      "catalogue": "approaches",
      "id": "spike",
      "operation": "set"
    },
    {
      "catalogue": "rules",
      "id": "advisory",
      "operation": "set"
    },
    {
      "catalogue": "rules",
      "id": "default_shapes",
      "operation": "set"
    },
    {
      "catalogue": "rules",
      "id": "floors",
      "operation": "set"
    },
    {
      "catalogue": "rules",
      "id": "loop_ceilings",
      "operation": "set"
    },
    {
      "catalogue": "checks",
      "id": "dod-evidence-typed",
      "operation": "set"
    },
    {
      "catalogue": "checks",
      "id": "multiagent-run-recorded",
      "operation": "set"
    }
  ],
  "overlay": {
    "counts": {
      "add": 0,
      "set": 1,
      "replace": 0,
      "remove": 0
    },
    "entries": [
      {
        "catalogue": "rules",
        "id": "floors",
        "operation": "set",
        "waiver": null
      }
    ]
  },
  "settings": {
    "moved": [
      {
        "key": "mode",
        "to": "adoption"
      }
    ],
    "state": [],
    "dropped": [
      {
        "key": "version",
        "reason": "schema: 1 replaces it"
      }
    ],
    "unread": [
      "roles"
    ]
  },
  "equivalence": {
    "result": "equivalent",
    "reason": "the configurations are identical",
    "points": 0,
    "scan": "identical"
  },
  "behaviour": {
    "result": "incomparable",
    "reason": "at risk trivial, familiarity greenfield, size atomic, goal delivery, urgency none, role engineer, labels none: approaches.checkpoints (autonomous) is [\"assess\", \"define\"] in the parent and [] in the child",
    "points": 4608,
    "changed": 2400
  },
  "blocked_by": [],
  "files": [
    {
      "action": "copy",
      "path": "governance/routing-policy.yml",
      "to": ".compass/legacy/routing-policy.yml"
    },
    {
      "action": "copy",
      "path": "governance/guardrails.yml",
      "to": ".compass/legacy/guardrails.yml"
    },
    {
      "action": "copy",
      "path": ".compass/config.yml",
      "to": ".compass/legacy/config.yml"
    },
    {
      "action": "write",
      "path": ".compass/migration.yml",
      "to": null
    },
    {
      "action": "write",
      "path": "compass.yml",
      "to": null
    },
    {
      "action": "remove",
      "path": ".compass/config.yml",
      "to": null
    },
    {
      "action": "keep",
      "path": "governance/routing-policy.yml",
      "to": null
    },
    {
      "action": "keep",
      "path": "governance/guardrails.yml",
      "to": null
    }
  ],
  "compass_yml": "# Written by compass policy migrate. This file holds only what differs from\n# the shipped default preset named in extends, and the project's settings.\nschema: 1\nextends: compass:default@6\nadoption: advisory\nrules:\n  floors:\n    set:\n      rules:\n        set:\n          RP-FLOOR-001:\n            order: 1\n            when:\n              risk: critical\n            then:\n              force_minimum_approach: full\n              never_skip:\n              - define\n              - refine\n              - verify\n              - ship\n            rationale: Critical changes coordinate, or they break things quietly.\n"
}
```

| Key | Type | Meaning |
|---|---|---|
| `schema` | integer | The version of this shape. It is 1 |
| `mode` | `dry-run` or `apply` | Whether `--apply` was given |
| `result` | string | `ready`, `blocked`, `applied` or `nothing-to-migrate` |
| `base_release` | object or null | `release` (a tag, `current`, or null for `as-built`) and `chosen_by` (`version`, `fewest-entries` or `as-built`). Null when there is no copy of the governance files, and on a resumed run |
| `sources` | list | Each file read, as `path` and `digest` (SHA-256 of its bytes), in this order: the routing policy, the guardrails, the old settings file. A resumed run lists the old settings file only |
| `adopted` | list | Each default that moved from the base release to the current default, as `catalogue`, `id` and `operation` |
| `overlay` | object | `counts` (`add`, `set`, `replace`, `remove`) and `entries`, each with `catalogue`, `id`, `operation` and `waiver` (`UNAPPROVED` for a stub, else null) |
| `settings` | object | `moved` (each with `key` and `to`), `state` (the keys that go to `state.yml`), `dropped` (each with `key` and `reason`) and `unread` |
| `equivalence` | object or null | The classifier's verdict on the copy against the base release plus the overlay: `result`, `reason`, `points` (grid points evaluated) and `scan`. Null when there is no copy of the governance files, or the overlay did not merge |
| `behaviour` | object or null | The classifier's verdict on the copy against the migrated configuration: `result`, `reason`, `points` and `changed` (points that differ). Null in the same cases |
| `blocked_by` | list | Each item has `code`, `path` and `message` |
| `files` | list | Each item has `action` (`copy`, `write`, `remove` or `keep`), `path` and `to` (the copy's destination, else null), in the order the command acts |
| `compass_yml` | string or null | The text of the file. Null when there is nothing to write: nothing to migrate, or a resumed run |

Entries are in catalogue order, then id order. The document holds no time and
no path outside the project, so the same input gives the same bytes.
`tests/test_policy_migrate.py` pins each key list, and pins this example with
each `digest`, `points` and `changed` replaced, because a digest follows the
bytes of the files and the other two follow the shipped preset.

A refusal prints no document: the reason is on stderr and the exit is 2.

### Codes in `blocked_by`

| Code | Meaning |
|---|---|
| `MIG-NOT-EQUIVALENT` | The classifier does not find the base release plus the overlay equivalent to the copy. The message gives its reason |
| `MIG-UNEXPRESSED` | The copy changed a value only the legacy views hold, which the catalogue cannot state. The path names it |
| `MIG-UNCLASSIFIABLE` | The classifier cannot read one of the configurations |
| An `M-*` code | The overlay does not merge, such as `M-MAP-REMOVE-ABSENT` or `M-REF-REMOVED` |
| Any other lint code | A finding of `compass policy lint` on the file the command would write: `K-LOCK-REFUSED`, `C-LOOSENING`, `C-INCOMPARABLE`, `W-UNAPPROVED`, `W-NO-OWNER` and the rest of [the lint codes](policy-lint.md) |

## What it does not do

- It has no `--undo` and no `--adopt-defaults`.
- It does not turn a copied `waived:` entry into a `LEGACY` waiver. The removal gets an `UNAPPROVED` stub like any other.
- It does not remove the governance copies.
- It does not run the six compatibility contracts. The classifier is the proof it gives.
- It does not call `compass policy diff`. When that command lands, the behaviour section can show its per-assessment list for the copy and the migrated project. The dry run classifies directly with `classify.classify`.
