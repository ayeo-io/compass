# `compass issue configure` and the reassess commit

This page is the owning doc for `compass issue configure`: how a person
proposes a change to one issue's own configuration, previews it, applies it at
reassess, and recovers from an interrupted commit. The store it writes to is
described in [generation-store.md](generation-store.md); the decision behind
both is ADR-036. The code is `cli/compass_pkg/issue_config_cmd.py` (the verb
and the reassess plan), `cli/compass_pkg/config_preview.py` (the preview and
the waiver re-check), `cli/compass_pkg/generation.py` (the proposal file,
discard and adoption) and `cli/compass_pkg/routing.py` (`--reset-config`).

## The commands

| Command | What it does | Touches the manifest |
|---|---|---|
| `compass issue configure --mode STAGE=MODE` (also `--route NAME`, `--autonomy`, `--ceiling NAME=N`, `--from-file PATH`) | Writes the proposed `config:` layer to `generations/<n+1>/proposed.yml` and prints a preview | No |
| `compass issue configure --discard [N]` | Removes the proposal, or a leftover folder, above the generation in force | No |
| `compass issue configure --commit [N]` | Adopts a complete leftover folder, if a fresh resolution gives the same files | Yes: the commit point |
| `compass approach evaluate --write --reason "..."` | Reassess. Applies a pending proposal as the new `config:` and commits the next generation | Yes |
| `compass approach evaluate --write --reset-config` | Reassess, dropping the issue's `config:` | Yes |

`/compass:assess --reassess` runs the reassess. The default for `N` is the
generation after the one in force.

`approach evaluate` computes the approach, stages, gates, checkpoints and
subtask ceiling from the configuration the issue runs against and from the
issue's own layer: the approach it names, the stage modes it sets and the
subtask ceiling it sets. The layer applies before the floors, caps and role
rules, so a floor still raises an approach the issue named too low. A
read-only evaluation uses the stored generation's layer, or the manifest's
`config:` for an issue with no generation. A write commits the layer it
computed from. The lint refuses a layer that loosens a lock when the
generation is committed; a read-only evaluation does not run it.

## Proposing a change

A call needs at least one change. Flags add to the overlay a call starts from:

| Flag | Writes into the overlay |
|---|---|
| `--mode STAGE=MODE` | `stages.<STAGE>.set.mode: MODE` |
| `--route NAME` | `approach: NAME` |
| `--autonomy VALUE` | `autonomy: VALUE` (`controlled`, `balanced` or `autonomous`) |
| `--ceiling NAME=N` | `ceilings.<NAME>: N`, a whole number of at least 1 |
| `--from-file PATH` | The whole overlay, replaced by the file's mapping; any flag is applied on top |

The starting overlay is the pending proposal when there is one, otherwise the
manifest's `config:`. Two calls therefore accumulate: `--mode refine=full`
then `--ceiling subtask_ceiling=2` proposes both. `--discard` starts again.

`proposed.yml` holds, in this order:

| Key | Meaning |
|---|---|
| `schema` | `1` |
| `issue` | The issue's slug |
| `base_generation` | The generation in force when it was written |
| `base_config_digest` | The digest of the manifest's `config:` when it was written (the digest of an empty mapping when there was none) |
| `overlay` | The whole proposed `config:` |

The call refuses, and writes nothing, when:

- the issue has no stored generation (`generation: 0`, or no `generation:` key). The message names `compass approach evaluate --write`;
- the issue is landed;
- `generations/`, the next folder or anything in it is a symbolic link;
- the next folder holds anything but a readable `proposed.yml`. A complete leftover is named with `--commit` and `--discard`; an incomplete one with `--discard`;
- a flag is malformed, `--from-file` is not a mapping, or the project's own layers do not resolve.

## The preview

The preview resolves the issue with the proposed overlay and compares it with
the stored generation. Its parts, in order:

1. `verdict`: `accepted`, or `refused` with the reasons the layered lint gives. A refused proposal is still written, so the person can edit and try again.
2. `proposal`: the path of `proposed.yml`.
3. The resolved fields that change against the generation in force.
4. The classification of the issue layer over the project's configuration (ADR-037), with its first point when it loosens or cannot be compared.
5. What the issue owes at its own assessment, before and after. Before is the issue's current `config:` resolved now; after is the proposal. The comparison is the classifier's single-assessment form, `classify.compare_at`. `compass policy diff` is not in this tree; when it lands it calls the same functions for two configuration references.
6. The records the change invalidates: waivers and the approvals behind them. Their files stay on disk; only their status in `records.yml` changes.
7. The next step.

Exit codes:

| Exit | Meaning |
|---|---|
| 0 | The proposal is written and would be accepted. `--discard` and `--commit` succeeded |
| 1 | The proposal is written and would be refused at commit. The reasons are printed |
| 2 | An error: nothing was proposed, discarded or adopted |

### `--json`

`--json` prints one document to standard output. The keys, their order and
the shape of each part are a public contract from 6.0.0. `--json` applies to
the preview; `--discard` and `--commit` print text and refuse it.

| Key | Meaning |
|---|---|
| `schema` | `1` |
| `issue` | The slug |
| `generation` | The generation in force |
| `proposed` | The number the proposal would become |
| `verdict` | `accepted` or `refused` |
| `reasons` | Strings: `CODE path: message` for each lint error, or the message of a proposal that does not resolve |
| `proposal` | The path of `proposed.yml`, relative to the project root |
| `base` | What the overlay was built on: `config` (the manifest's `config:`) or `pending proposal` |
| `changes` | A list of `{path, before, after}`, sorted by path; `null` for a field in only one side. For a stage mode the issue's layer sets, `before` is the mode the issue has, not `null` |
| `classification` | `{result, reason, scan, first_point}` |
| `assessment` | `{approach, result, changes, refused}` |
| `invalidates` | A list of `{id, kind, reason}`, sorted by id |
| `next` | The command to run next |

Each nested object, with its keys in this order:

| Object | Key | Meaning |
|---|---|---|
| each `changes` item | `path` | The dotted path of a resolved field |
| | `before` | Its value in the generation in force |
| | `after` | Its value with the proposal |
| `classification` | `result` | `equivalent`, `tightening`, `loosening`, `incomparable` or `not-run` |
| | `reason` | One sentence from the classifier |
| | `scan` | `full`, `early-exit`, `identical`, `cap` or `none` |
| | `first_point` | The first assessment where the layer loosens or cannot be compared, or `null` |
| `first_point` | `assessment` | The assessment the point stands for |
| | `represents` | The values of each dimension the point stands for |
| | `outcome` | `looser`, `mixed` or the other point outcome the classifier names |
| | `summary` | One sentence about the point |
| | `changes` | The differences at the point |
| each `first_point.changes` item | `fact` | The obligation fact that differs |
| | `field` | The configuration field it comes from |
| | `key` | The entry within the fact, or `null` |
| | `outcome` | `tighter`, `looser` or `incomparable` |
| | `parent` | The value before |
| | `child` | The value with the proposal |
| `assessment` | `approach` | `{before, after}`: the delivery approach each side gives, or `null` |
| | `result` | The classification word for the issue's own assessment |
| | `changes` | The differences at that assessment |
| each `assessment.changes` item | `fact`, `field`, `key`, `outcome` | As in `first_point.changes` |
| | `before` | What the issue owes now |
| | `after` | What it would owe |
| | `refused` | In `assessment`: `{before, after}`, the evaluator's message for a side that refuses the assessment, or `null` |
| each `invalidates` item | `id` | `waiver:<scope>:<catalogue>.<entry>` for a waiver, or the approval record's id |
| | `kind` | `waiver` or `approval` |
| | `reason` | Why it is invalid |

Two examples are pinned. `tests/test_issue_configure.py` compares the
command's output with the files in `tests/fixtures/` and checks each block
below against its file.

The first, for `--autonomy controlled` on a regular issue at generation 1,
is `issue-configure-example.json`.

```json
{
  "schema": 1,
  "issue": "feature",
  "generation": 1,
  "proposed": 2,
  "verdict": "accepted",
  "reasons": [],
  "proposal": ".compass/work/feature/generations/2/proposed.yml",
  "base": "config",
  "changes": [
    {
      "path": "autonomy",
      "before": "balanced",
      "after": "controlled"
    }
  ],
  "classification": {
    "result": "equivalent",
    "reason": "every point owes the same",
    "scan": "full",
    "first_point": null
  },
  "assessment": {
    "approach": {
      "before": "regular",
      "after": "regular"
    },
    "result": "equivalent",
    "changes": [],
    "refused": null
  },
  "invalidates": [],
  "next": "/compass:assess --reassess --reason \"...\""
}
```

The second, `issue-configure-refused-example.json`, is a loosening
(`--mode define=collapsed`) on an issue whose waiver went stale because the
project changed its own check from `blocking` to `advisory`. It shows a
refusal with its reasons, a `first_point`, and an invalidated waiver with the
approval record behind it.

```json
{
  "schema": 1,
  "issue": "feature",
  "generation": 1,
  "proposed": 2,
  "verdict": "refused",
  "reasons": [
    "C-INCOMPARABLE approaches.stages: at risk trivial, familiarity greenfield, size atomic, goal delivery, urgency live-defect, role engineer, labels none: approaches.checkpoints (controlled) is [\"assess\", \"define\"] in the parent and [\"assess\"] in the child; a waiver on the entry, approved by the layer above, excuses it"
  ],
  "proposal": ".compass/work/feature/generations/2/proposed.yml",
  "base": "config",
  "changes": [
    {
      "path": "stages.define.mode",
      "before": "full",
      "after": "collapsed"
    }
  ],
  "classification": {
    "result": "incomparable",
    "reason": "at risk trivial, familiarity greenfield, size atomic, goal delivery, urgency live-defect, role engineer, labels none: approaches.checkpoints (controlled) is [\"assess\", \"define\"] in the parent and [\"assess\"] in the child",
    "scan": "full",
    "first_point": {
      "assessment": {
        "risk": "trivial",
        "familiarity": "greenfield",
        "size": "atomic",
        "goal": "delivery",
        "urgency": "live-defect",
        "role": "engineer",
        "labels": []
      },
      "represents": {
        "risk": [
          "trivial",
          "contained"
        ],
        "familiarity": [
          "greenfield",
          "brownfield-mapped"
        ],
        "size": [
          "atomic",
          "small"
        ],
        "goal": [
          "delivery",
          null
        ],
        "urgency": [
          "live-defect"
        ],
        "role": [
          "engineer",
          "qa",
          null
        ]
      },
      "outcome": "mixed",
      "summary": "at risk trivial, familiarity greenfield, size atomic, goal delivery, urgency live-defect, role engineer, labels none: approaches.checkpoints (controlled) is [\"assess\", \"define\"] in the parent and [\"assess\"] in the child",
      "changes": [
        {
          "fact": "stage_mode",
          "field": "approaches.stages",
          "key": "define",
          "outcome": "incomparable",
          "parent": "reproduce-first",
          "child": "collapsed"
        },
        {
          "fact": "checkpoints",
          "field": "approaches.checkpoints",
          "key": "controlled",
          "outcome": "looser",
          "parent": [
            "assess",
            "define"
          ],
          "child": [
            "assess"
          ]
        }
      ]
    }
  },
  "assessment": {
    "approach": {
      "before": "regular",
      "after": "regular"
    },
    "result": "loosening",
    "changes": [
      {
        "fact": "stage_mode",
        "field": "approaches.stages",
        "key": "define",
        "outcome": "looser",
        "before": "full",
        "after": "collapsed"
      },
      {
        "fact": "checkpoints",
        "field": "approaches.checkpoints",
        "key": "balanced",
        "outcome": "looser",
        "before": [
          "define",
          "plan"
        ],
        "after": [
          "plan"
        ]
      },
      {
        "fact": "checkpoints",
        "field": "approaches.checkpoints",
        "key": "controlled",
        "outcome": "looser",
        "before": [
          "assess",
          "define",
          "refine",
          "plan"
        ],
        "after": [
          "assess",
          "refine",
          "plan"
        ]
      }
    ],
    "refused": null
  },
  "invalidates": [
    {
      "id": "EV-1",
      "kind": "approval",
      "reason": "it approved waiver:issue:checks.team-check, which is invalid: checks.team-check.severity: the parent value changed from 'blocking' to 'advisory'; the project value is 'advisory'"
    },
    {
      "id": "waiver:issue:checks.team-check",
      "kind": "waiver",
      "reason": "checks.team-check.severity: the parent value changed from 'blocking' to 'advisory'; the project value is 'advisory'"
    }
  ],
  "next": "/compass:assess --reassess --reason \"...\""
}
```

## Applying it: the reassess commit

`compass approach evaluate --write` settles the following before it prints
anything, so a refusal never follows a printed result: the proposal, the
flags, the project's own layers resolving, the waiver re-check, the layered
lint of a configuration that differs from the generation in force, the
landed check, and the match of a folder to adopt. One case is left to the
commit: a configuration equal to the generation in force is not linted,
because whether it commits depends on the computed outcome, so an adoption of
such a folder can still refuse after the result prints.

1. **The proposal.** A pending proposal becomes the manifest's `config:` in the manifest it writes. It is stale, and the reassess refuses it, when `base_generation` is not the generation in force or `base_config_digest` is not the digest of the manifest's `config:` now. The message names `compass issue configure --discard`.
2. **`--reset-config`.** It removes `config:` from the manifest it writes. It refuses while a proposal is pending, because it cannot be both applied and dropped.
3. **Waivers.** Each issue waiver in the generation in force is re-checked. It is invalidated when the parent value of a waived field changed since the approval was given, or when the overlay now sets a waived field to another value. The waiver's entry is left out of the resolution, so the field reverts to the parent's value, and `records.yml` marks the waiver and the approval record behind it `invalidated` with the reason. The manifest's `config:` still holds the entry. The command prints why (the parent value moved, with the old and new value) and the two ways out: approve it again with a new `human-approval` record that names the new values, or remove the entry from `config:`. A later reassess refuses the entry with the same account until one of those is done, because the approval names the values it saw. The waiver is valid again if the parent value returns to what the approval named: the next reassess stores it as `valid`.

Then the commit writes in the order the store fixes: the four files, the
`complete` marker, the manifest. A consumed proposal is removed after the
manifest replace. If the result equals the generation in force, nothing is
committed, the command says "no change" and a proposal that asked for what is
already held is removed.

`records.yml` keeps each record the generation before it marked `superseded`
or `invalidated`, and any record the new generation does not restate.

### The `reassessments:` entry

A reassess that changes the delivery approach appends an entry to the
manifest's `reassessments:`, as before. It gains `generation: {from, to}`.
`from` is the generation in force; `to` is the generation the commit made, or
the same number when nothing was committed.

A reassess that changes only the issue's `config:` layer (a proposal applied,
`--reset-config`, a hand edit, or a waiver left out) appends an entry of kind
`configuration`, with the `--reason`, `generation: {from, to}` and a `changed`
note holding the digest of the layer before and after. `compass retro` ignores
that kind in its sizing signal, as it ignores `policy-correction`: no one
misread the work. A reassess that commits nothing adds no entry. Without
`--reason` the entry says so and the command warns.

## Recovery

A crash leaves one of the states in [generation-store.md](generation-store.md).
The manifest names the previous generation until its replace, so the issue
keeps running against a whole generation.

| Interrupted after | Manifest names | State | Resolve with |
|---|---|---|---|
| nothing written | n | none | run the reassess again |
| `resolved.yml`, `provenance.yml`, `versions.yml` or `records.yml` | n | `incomplete` | `compass issue configure --discard`, or run the reassess again, which overwrites it. `--commit` refuses it |
| `complete` | n | `complete-unreferenced` | `compass issue configure --commit` or `--discard` |
| the manifest replace | n+1 | `current` | nothing; a `proposed.yml` left in the folder is ignored |
| removing `proposed.yml` | n+1 | `current` | nothing |

`--commit` re-runs the reassess with the folder named. It resolves the four
files afresh and compares their digests with the folder's marker. It adopts
the folder only when the folder is whole, the manifest still names the
generation before it, and every digest matches. It then writes the manifest
and nothing else. When the folder held a `proposed.yml`, the proposal is
applied as the manifest's `config:` first, as the interrupted reassess would
have done. Any other case refuses and writes nothing: the message names the
files that no longer match, and `--discard`.

Give `--commit` the `--reason` the interrupted reassess should have recorded:
`compass issue configure --commit --reason "..."`. The reason of the
interrupted run is not stored in the folder, so without it the entry says the
reason was not given.

A crash that followed `--reset-config` leaves no record of the flag, but the
folder records that the issue had no overlay (`issue_overlay_digest` is
empty). When the manifest still holds a `config:` and the plain reading
refuses, `--commit` tries the reading with `--reset-config`, and adopts the
folder if that reproduces it. If neither reading does, it refuses with the
first reading's message.

## Not built yet

- `compass policy diff`, which will call the preview's comparison for two references.
- `compass issue migrate-config` and the pending-change line in `compass check`.
- Check-result records (`result:<check>`) are not invalidated by a configuration change.
