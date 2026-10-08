# Policy lint and the effective view

This page is the owning doc for `compass policy lint` and `compass policy
effective` on a project that has a `compass.yml`. It states what each
command checks or shows, in what order, and the exact shape of the JSON each
one prints. From 6.0.0 the finding codes and both JSON shapes are a public
contract: a change to a key, its order or a code is a breaking change.

The code is `cli/compass_pkg/policy_lint.py` (the checks and the views) and
`cli/compass_pkg/policy_cmd.py` (the two commands). The decisions behind it
are ADR-035 (the merge grammar), ADR-037 (classification), ADR-039 (waivers
and locks), ADR-042 (the shipped preset) and ADR-043 (one project file).

## When the layered lint runs

| Project | What `compass policy lint` runs |
|---|---|
| No `compass.yml`, or a `compass.yml` that Compass does not read | The legacy lint, with the output it always had |
| The framework's own repository | The legacy lint |
| A root `compass.yml` that Compass reads | The layered lint below |
| `--file PATH` | The layered lint over that one file, with the shipped default as its parent |

A `compass.yml` is read when it is the only settings file, or when it has a
top-level `schema:` key. `compass ci` calls the legacy lint directly, so its
output and exit code do not change.

## The layers

| Layer name | Kind | Where it comes from |
|---|---|---|
| `default` | `parent` | `governance/presets/default/` (the shipped preset) |
| `project` | `project` | `compass.yml` in the project root |
| `issue` | `issue` | the `config:` of the issue's `manifest.yml`, only with `--issue SLUG` |

A `compass.yml` in a folder below the project root is ignored, and lint
warns about it.

## The order of the checks

Lint runs five groups in this order. It stops after the first group that has
an error, so a later group never reports a fault that only follows from an
earlier one. Warnings never stop it and never fail it.

| Group | What it checks | Codes |
|---|---|---|
| `layer` | Each layer alone, before anything merges | `L-LOAD`, `L-KEY-NOT-TEXT`, `L-SCHEMA`, `L-SETTINGS-KEY`, `L-UNLOCK-PLACEMENT`, `L-IMPL-UNKNOWN`, `L-IMPL-TEMPLATED`, `W-APPROVED-ON-ISSUE`, `L-IGNORED-FILE` (warning) |
| `merge` | The merge grammar, layer by layer. It reports every fault of the first layer that does not apply | the merge's own `M-*` codes, such as `M-ADD-EXISTS`, `M-SET-UNKNOWN`, `M-REF-REMOVED` |
| `resolved` | The merged result as a whole | `M-REF-UNKNOWN`, `M-WEIGHT-TIE`, `M-HIT-MISSING`, `M-HIT-DISALLOWED`, `M-ALIAS-COLLISION`, `M-CYCLE`, `M-BOOKKEEPING-INPUT`, `M-DIRECTORY-DEPENDENCY`, `M-LIST-KIND-UNEVALUATED` (warning) |
| `locks` | What the locks above a layer refuse, and each refused unlock | `K-LOCK-REFUSED`, `K-UNLOCK-REFUSED`, `K-UNPROVABLE`, `E-EVALUATION` |
| `classification` | Waivers, the classifier's verdict on each layer, and the vocabulary | `C-LOOSENING`, `C-INCOMPARABLE`, `V-VOCABULARY-CHANGE`, `W-UNNEEDED`, the waivers' own `W-*` codes, `E-EVALUATION` |

### Codes

| Code | Level | Meaning |
|---|---|---|
| `L-LOAD` | error | The file does not parse, or repeats a key. The path is from the project root, or the file's own name when it is outside it |
| `L-KEY-NOT-TEXT` | error | A mapping key anywhere in a layer that YAML reads as a boolean, a number or null, such as an unquoted `on:`, `no:`, `true:` or `1:`. The path is the mapping that holds it, and the message gives the key as parsed and the quoted form to write, such as `"on":`. The layer is not read further, so no later group runs |
| `L-SCHEMA` | error | A key or value that the layer's schema does not allow |
| `L-SETTINGS-KEY` | error | A settings key in a parent. Settings belong in the project's own `compass.yml` |
| `L-UNLOCK-PLACEMENT` | error | An `unlock` outside the project layer, or a top-level `unlocks` |
| `L-IMPL-UNKNOWN` | error | A check names an `impl` that the check registry does not hold |
| `L-IMPL-TEMPLATED` | error | An `impl` that is a template, not a name |
| `L-IGNORED-FILE` | warning | A `compass.yml` below the project root, which is not read |
| `M-REF-UNKNOWN` | error | A field, or a rule's effect (`EFFECT_TARGETS` in `catalogue_spec.py` says which catalogue each effect names), names an id that no entry defines |
| `M-WEIGHT-TIE` | error | Two delivery approaches have the same weight |
| `M-LIST-KIND-UNEVALUATED` | warning | A stage's `entry` or `exit` list names a check of a kind this version does not evaluate (`judged` or `evidence`). The check fails in `compass check`, whatever the capability. The exit code does not change |
| `M-HIT-MISSING` | error | A rule set uses an effect and names no `hit:` policy for it. `EFFECT_POLICIES` in `catalogue_spec.py` lists the effects and the policies each allows |
| `M-HIT-DISALLOWED` | error | A `hit:` policy the effect does not allow, or an unknown effect |
| `M-ALIAS-COLLISION` | error | One name or alias belongs to two entries of a catalogue |
| `M-CYCLE` | error | Artifacts depend on each other in a cycle. The message gives the path, such as `a -> b -> a`, and the finding sits on the `depends_on` of the first artifact in id order |
| `M-BOOKKEEPING-INPUT` | error | An artifact lists in `depends_on` an artifact marked `bookkeeping: true`, a record the framework keeps about the work (the dashboard, the receipt, the verification report). A bookkeeping artifact may itself depend on others. The finding sits on the dependent artifact's `depends_on` |
| `M-DIRECTORY-DEPENDENCY` | error | An artifact lists in `depends_on` an artifact whose `file` ends in `/`, a directory. An artifact depends on files, so a verification report names the evidence ids it cites instead. The finding sits on the dependent artifact's `depends_on` |
| `M-EFFECT-UNKNOWN` | error | A rule's `then:` holds a key that is neither an effect nor a qualifier (`ceiling`, `until`), such as a misspelt `force_minimum_aproach`. `EFFECT_QUALIFIERS` in `catalogue_spec.py` lists the qualifiers |
| `M-ADD-EXISTS` | error | A full entry names an id that exists, with no `replace: true` |
| `M-ADD-PARTIAL` | error | A new entry lacks a required field |
| `M-SET-UNKNOWN` | error | `set:` on an id the layer above does not hold |
| `M-REPLACE-UNKNOWN` | error | `replace: true` on an id the layer above does not hold |
| `M-REMOVE-UNKNOWN` | error | `remove: true` on an id the layer above does not hold |
| `M-OP-CONFLICT` | error | One entry holds more than one of a full entry, `set`, `replace` and `remove` |
| `M-OP-DUPLICATE` | error | One id or key is in two documents of one layer (found when split files are combined, not in a single file) |
| `M-OP-LAYER` | error | A layer uses an operation it may not |
| `M-LIST-OP-OUTSIDE-SET` | error | `add:` or `remove:` on a list outside `set:` |
| `M-LIST-REMOVE-ABSENT` | error | `remove:` of an item the list does not hold |
| `M-LIST-ADD-PRESENT` | error | `add:` of an item the list already holds |
| `M-MAP-OP-OUTSIDE-SET` | error | `set:` or `remove:` on a map outside `set:` |
| `M-MAP-REMOVE-ABSENT` | error | `remove:` of a key the map does not hold |
| `M-FIELD-UNKNOWN` | error | `set:` names a field the catalogue does not define |
| `M-FIELD-LAYER` | error | A field this layer may not set, such as a stage's `mode` outside the issue layer |
| `M-FIELD-SHAPE` | error | A value of the wrong shape, or a blank name or alias |
| `M-REF-REMOVED` | error | `remove: true` on an entry something still refers to |
| `K-LOCK-REFUSED` | error | A layer loosens, or changes in a way that cannot be compared, an entry a lock covers |
| `K-UNLOCK-REFUSED` | error | An `unlock` that does not stand: not the owner's, no waiver, a hard lock, or an entry that is not locked |
| `K-UNPROVABLE` | error | The configuration has more than eight named labels, so no lock can be shown to hold |
| `E-EVALUATION` | error | The evaluator rejects the configuration. It is reported once, with the evaluator's own text, and the lock refusal that says the same is not counted again |
| `C-LOOSENING` | error | A layer is looser than the layer above, and no waiver excuses it |
| `C-INCOMPARABLE` | error | A layer changes something that cannot be compared with the layer above, and no waiver excuses it |
| `V-VOCABULARY-CHANGE` | warning | A layer adds or removes a value of a dimension. The classifier does not read a value that no rule reads, so this is reported on its own |
| `W-APPROVED-ON-ISSUE` | error | An issue waiver carries `approved_on` |
| `W-UNNEEDED` | warning | A waiver excuses nothing |
| `W-NO-OPERATION` | error | A waiver sits in an entry with none of `set`, `replace` and `remove` |
| `W-SHAPE` | error | A waiver is not a mapping |
| `W-KEY-UNKNOWN` | error | A waiver holds a key it may not, such as `covers` |
| `W-REASON` | error | A waiver has no reason |
| `W-APPROVED-BY` | error | A waiver has no `approved_by` |
| `W-UNAPPROVED` | error | `approved_by` is `UNAPPROVED` |
| `W-LEGACY` | warning | `approved_by: LEGACY`: no approval is recorded |
| `W-LEGACY-DATED` | error | A `LEGACY` waiver carries `approved_on` |
| `W-LEGACY-ISSUE` | error | An issue waiver uses `LEGACY` |
| `W-APPROVED-ON-MISSING` | error | A project waiver has no `approved_on` |
| `W-APPROVED-ON-FORM` | error | `approved_on` is not a date |
| `W-APPROVED-ON-FUTURE` | error | `approved_on` is later than today |
| `W-NO-OWNER` | error | The project names no owner, so nobody may approve a waiver |
| `W-APPROVERS-SHAPE` | error | `approvers` is not a mapping of kind to a list of names |
| `W-APPROVER-NOT-ALLOWED` | error | The approver is not in the allowed list |
| `W-APPROVAL-MISSING` | error | An issue waiver's `approved_by` is not a record in the issue's evidence |
| `W-APPROVAL-TYPE` | error | That record is not a `human-approval` |
| `W-APPROVAL-DECISION` | error | The record does not hold `decision: approved` |
| `W-APPROVAL-FIELDS` | error | The record lacks `approver`, `role`, `scope` or `timestamp` |
| `W-APPROVAL-WAIVER` | error | The record does not approve this waiver's entry and values |
| `W-APPROVAL-UNCHECKED` | error | The waiver's values were not derived, so the record cannot be matched |
| `LEGACY-STRUCTURE` | error | A structural fault in the copied governance files (legacy mode) |
| `LEGACY-WAIVER` | error | A malformed `waived:` entry (legacy mode) |
| `LEGACY-WAIVED` | info | A rule the project waived: a recorded decision, not drift (legacy mode, JSON only) |
| `LEGACY-DRIFT` | warning, or error with `governance_drift: strict` | The copied governance lacks a rule or check the framework ships (legacy mode) |
| `LEGACY-DRIFT-UNCOMPARED` | warning | The copy could not be compared with the framework's (legacy mode) |

## Options and exit codes

| Option | Meaning |
|---|---|
| `--file PATH` | Lint one `compass.yml` as the project layer, over the shipped default |
| `--issue SLUG` | Add the issue's `config:` as the issue layer, judged at the issue's own assessment and not over the whole grid (a project layer is still judged over the grid), and look up its approvals in the issue's evidence. Without it no issue is read: there is no `COMPASS_ISSUE` or current-task fallback. A project with no `compass.yml` lints the issue's config over the shipped default |
| `--exhaustive` | Classify with the full grid, not the grouped one |
| `--json` | Print the document below |

| Exit | Meaning |
|---|---|
| 0 | Pass: no error. Warnings may be printed |
| 1 | Fail: at least one error |
| 2 | An input cannot be read: a `--file` that is not there, or an issue that does not exist |

Text output is `compass policy lint: PASS` or `compass policy lint: FAIL`,
then one line per finding: `  - CODE [layer] path: message`. A warning line
starts `  - warning CODE`.

## `compass policy lint --json`

```json
{
  "schema": 1,
  "mode": "layered",
  "result": "fail",
  "layers": [{"name": "default", "kind": "parent"}, {"name": "project", "kind": "project"}],
  "stopped_after": "layer",
  "counts": {"errors": 1, "warnings": 0},
  "findings": [
    {"code": "L-SCHEMA", "level": "error", "layer": "project", "path": "stages",
     "group": "layer", "message": "expected a mapping keyed by id", "detail": null}
  ]
}
```

| Key | Type | Meaning |
|---|---|---|
| `schema` | integer | The version of this shape. It is 1 |
| `mode` | `layered` or `legacy` | Which lint ran |
| `result` | `pass` or `fail` | `fail` when `counts.errors` is above 0 |
| `layers` | list | Each layer in order, root first, as `name` and `kind`. A project file that did not load is still named. Legacy mode has one: `legacy` |
| `stopped_after` | string or null | The group after which the lint stopped, or null |
| `counts` | object | `errors` and `warnings`, both integers |
| `findings` | list | Every finding, in the order below |

Each finding has these keys, in this order:

| Key | Type | Meaning |
|---|---|---|
| `code` | string | One of the codes above |
| `level` | `error`, `warning` or `info` | Only an error fails the lint. `info` is a recorded decision and appears in legacy mode only |
| `layer` | string | The layer the finding belongs to |
| `path` | string | The key path, such as `checks.tests-pass.severity`, or a waiver id such as `project:checks.tests-pass` |
| `group` | string | `layer`, `merge`, `resolved`, `locks`, `classification` or `legacy` |
| `message` | string | A sentence for a person |
| `detail` | object or null | Extra facts for a machine, below |

`detail` is null except for these:

- `C-LOOSENING`, `C-INCOMPARABLE`: `result`, `assessment` (the first assessment where the change shows), `outcome`, `field`, `key`, `parent` (the value in the layer above) and `child` (the new value).
- `K-LOCK-REFUSED`: `field`, `key`, `outcome`, `level` (`true` or `"hard"`), `parent`, `child` and `where`.
- `V-VOCABULARY-CHANGE`: `dimension`, `added` and `removed`.

Findings are ordered by group (in the order of the table above), then by
layer (root first), then by `path`, `code` and `message`. The document holds
no time and no path outside the project, so the same input gives the same
bytes. `tests/test_policy_lint.py` pins each key list.

## `compass policy effective`

`compass policy effective` prints what the configuration resolves to. `compass
check` and the evaluator still read the legacy governance files until the
generation store lands, so this view is not yet what they use. It prints every
resolved field of the project, one line each: the path, the value, the source layer, the operation and the
waiver. A stage list that a capability switch has not turned on is marked
`(inactive: entry-exit-evaluation off)`.

```
stages.plan.entry   [dor-summary-filled, ...]   default@6.0.0 (add)  (inactive: entry-exit-evaluation off)
checks.suite-passed.severity   advisory   project (set, waiver by jed72, 2026-10-05)
stages.define.mode   light   issue (set)
```

| Option | Meaning |
|---|---|
| `--issue SLUG` | Resolve the issue's `config:` over the live project file. No generation is stored yet, so the view always reads the live file. Without it no issue is read: there is no `COMPASS_ISSUE` or current-task fallback |
| `--json` | Print the document below |

Exit 0 on success. Exit 2 when the layers cannot be resolved (the message
names the first fault and points to `compass policy lint`).

A project with no `compass.yml` shows the shipped default alone.

### Which fields are listed

- `capabilities.<name>`, then `owner`, then `approvers.<kind>`: each takes the value of the last layer that holds it.
- Then each catalogue in this order: `dimensions`, `stages`, `approaches`, `rules`, `checks`, `gates`, `artifacts`, `vocabulary`. Within one, entries are in id order, and fields are in the order of the field table in `catalogue_spec.py`.
- A field is listed only when its entry holds it. After an entry's fields comes `<entry>.locked` when a lock holds the entry, read from the layers: `true` or `"hard"`, with the layer that declared it. A lock an owner's unlock lifted is not listed.
- Settings keys (`autonomy`, `adoption` and the others) are not part of a layer and are not listed.

### Operations

`op` is how the source layer last wrote the field:

| `op` | Meaning |
|---|---|
| `add` | The layer added the entry or the capability |
| `replace` | The layer replaced the entry with `replace: true` |
| `set` | The layer changed the field with `set:` |

## `compass policy effective --json`

```json
{
  "schema": 1,
  "scope": {"kind": "project", "issue": null, "resolved": "live"},
  "layers": [
    {"name": "default", "kind": "parent", "version": "6.0.0", "digest": "sha256:..."},
    {"name": "project", "kind": "project", "version": null, "digest": "sha256:..."}
  ],
  "fields": [
    {"path": "checks.suite-passed.severity", "value": "advisory", "source": "project",
     "op": "set",
     "waiver": {"id": "project:checks.suite-passed", "scope": "project",
                "approved_by": "jed72", "approved_on": "2026-10-05"},
     "note": null}
  ]
}
```

| Key | Type | Meaning |
|---|---|---|
| `schema` | integer | The version of this shape. It is 1 |
| `scope` | object | `kind` (`project` or `issue`), `issue` (the slug or null) and `resolved` (always `live` until the generation store exists) |
| `layers` | list | Each layer, root first, with `name`, `kind`, `version` and `digest` |
| `fields` | list | Every resolved field, in the order above |

Each layer has these keys, in this order: `name`, `kind`, `version` (the
shipped default's version, null for the others) and `digest` (over the
layer's parsed content, so a comment or layout change does not move it).

Each field has these keys, in this order:

| Key | Type | Meaning |
|---|---|---|
| `path` | string | `catalogue.id.field`, or `capabilities.name`, `owner`, `approvers.kind` |
| `value` | any | The resolved value |
| `source` | string | `default@<version>`, `project` or `issue` |
| `op` | string | `add`, `replace` or `set` |
| `waiver` | object or null | The waiver that excuses this field, or null |
| `note` | string or null | `inactive: <capability> off` for a stage list that is switched off |

A waiver object has these keys, in this order: `id` (`scope:catalogue.entry`),
`scope` (`project` or `issue`), `approved_by` (a name for a project waiver,
an evidence id for an issue waiver) and `approved_on` (a date for a project
waiver, null for an issue waiver, whose approval record carries its own
time).

The document holds no time and no path outside the project, so the same
input gives the same bytes. `tests/test_policy_lint.py` pins each key list.

## What this page does not cover

- The per-issue generation store and `--live`: the effective view reads the live project file until the store exists.
- `compass policy diff`, which has its own page: [policy-diff.md](policy-diff.md).
- `compass policy migrate`, which has its own page: [policy-migrate.md](policy-migrate.md).
- `compass policy update`, which has its own page: [policy-update.md](policy-update.md).
- The settings-conflict refusal (`compass check` and the pre-tool hook own it).
