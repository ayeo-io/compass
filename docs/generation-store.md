# The generation store

This page is the owning doc for the generation store: the stored, numbered copy
of the configuration an issue runs against. It states what a generation
holds, how a commit writes it, the states a generation folder can be in, and
what reads it. The decision behind it is ADR-036. The code is
`cli/compass_pkg/generation.py` (the files, the commit and the states) and
`cli/compass_pkg/effective.py` (the reading interface and the live
resolution).

## What is built

The store and its commit are built, with the commands that change what it
holds: `compass issue configure` (propose, preview, `--discard`, `--commit`) and
`--reset-config` on the reassess ([issue-configure.md](issue-configure.md)). The modules that read governance
(`routing`, `check_cmd`, `checks`, `receipt`, `manifest`, `calibration`,
`flow`, `quick_fix_cmd`, `loop_ceilings`, `lessons`) still read live
governance. `effective_for` returns the stored generation, and a later change
moves those modules onto it. Until then a stored generation records the
configuration an issue was assessed under, and `compass check` writes its
results next to it, but a project edit still reaches an open issue through
those readers.

## The manifest keys

| Key | Meaning |
|---|---|
| `generation: n` | The generation the issue runs against. The manifest names it, and it is the authority. |
| `generation: 0` | The issue was assessed under 6.x and has no generation yet. A command that needs its configuration refuses and names `compass approach evaluate --write`. |
| no `generation` key | The issue predates 6.0.0. It reads live governance as 5.6.0 did, and `compass approach evaluate --write` gives it generation 1. |
| `config:` | The issue's own configuration layer. It is an input: editing it changes nothing until a commit. |

`templates/manifest.yml` ships `generation: 0`.

## The generation folder

`.compass/work/<slug>/generations/<n>/` holds:

| File | Holds | Written |
|---|---|---|
| `resolved.yml` | The configuration after every layer is merged: the eight catalogues, the evidence types, the capability switches, the approach the issue's overlay names, the autonomy value, and the conformance status. | At commit, then fixed. |
| `provenance.yml` | `fields`: for each field, the layers that wrote it and the operation of each. `waivers`: each waiver with the parent value it saw. `classification`: for the project and issue layers, that the lint raised no error (`result: accepted`) and which waivers the layer holds. It holds no classifier points: a generation stored by this version has no `points` key, and a reader must treat absent points as "not recorded", never as zero. | At commit, then fixed. |
| `versions.yml` | `resolver` and `cli` versions, `parents` (reference, version, digest, source), `project` (path, digest, git blob), `issue_overlay_digest`, and `implementations`: the version of each check implementation the configuration uses. | At commit, then fixed. |
| `records.yml` | The status of each approval, waiver and check result at commit: `valid`, `superseded` or `invalidated`, with a reason. | At commit, then fixed. |
| `complete` | A marker holding a digest of each of the four files above. | Last of the four-file commit. |
| `results.yml` | The latest `compass check` verdict for each check: `verdict` (`pass`, `fail` or `nothing-to-check`), `at`, the implementation id and version, a digest of the check's definition, and `status`. | After each `compass check`, replacing the file. The marker does not cover it. |
| `proposed.yml` | A pending change to the issue's `config:` layer: `schema`, `issue`, `base_generation`, `base_config_digest` and `overlay`. The state table below recognises it, and a reassess applies it. | By `compass issue configure`, in the folder above the generation in force. Removed by the reassess that applies it, or by `--discard`. |

Every file begins `schema: 1`. A digest is `sha256:` and the hex digest of the
file's parsed content in canonical JSON, so a comment or a line ending does
not change it and a changed value does.

`versions.yml` records the check implementation versions so that a later
change can refuse a run when an implementation's major version differs from
the one the generation recorded. That refusal is not built yet.

## A commit

`compass approach evaluate --write` commits. It checks each layer alone and
merges them, which stops a layer that does not load or merge. Then, holding an
exclusive lock on `.compass/work/<slug>/.generation.lock`, it compares the
result with the generation in force. When something changed and a write
follows, it runs the layered lint first, because the lint includes the
classifier and is slow on a project layer. If the lint reports an error,
nothing is written. Then:

1. It writes `resolved.yml`, `provenance.yml`, `versions.yml` and `records.yml`
   into `generations/<n+1>/`, each atomically.
2. It writes `complete`, atomically.
3. It replaces `manifest.yml`, atomically, with `generation: n+1` and the
   computed outcome fields. This is the commit point.

A crash before step 3 leaves the manifest naming generation n, which is still
whole. If the resolved configuration, the issue overlay and the computed
outcome all equal generation n, nothing is committed and the command says
"no change"; the manifest is still replaced, as before. The manifest on disk
must still name the generation the command read, or the commit refuses.

The commit refuses, writing nothing, when:

- generation n+1 already exists and is complete. The message gives the folder's
  path, then the two commands that resolve it: `compass issue configure
  --commit n+1` to adopt it (with `--reason "..."` to keep the reason of the
  interrupted reassess) and `compass issue configure --discard n+1` to remove
  it.
- `generations/`, the next folder or anything inside the next folder is a
  symbolic link. Compass never follows a link there, because the next folder is
  cleared before it is written.
- the issue is landed and the result would be a new generation. A landed issue
  keeps the configuration it landed under. "No change" is still allowed.
- the layered lint rejects the configuration. The message names the file, the
  first error and `compass policy lint`, which shows the rest. `approach
  evaluate` without `--write` still works on such a project.

It overwrites an incomplete folder, including one whose marker does not match
its files, and keeps `proposed.yml` until the manifest is replaced. Each file keeps the mode of the file it
replaces, and a new file gets the mode the umask gives.

The gate comments (`# accepts: ...`) are added to the manifest text inside the
same replace, under the lock.

Three more things the commit takes from the reassess that calls it, described
in [issue-configure.md](issue-configure.md):

- a **proposal** it applies: under the lock the commit checks that
  `proposed.yml` is still the file the reassess read, and removes it after the
  manifest replace (a last step, `proposal`, that a crash can follow);
- a **leftover to adopt**, named by `compass issue configure --commit`: the
  commit writes no file but the manifest, and only when the folder is whole and
  its four files equal what a fresh resolution gives;
- a **stamp** that adds `generation: {from, to}` to the `reassessments:` entry
  the reassess appended, in the same replace.

## States

`compass ci` reports each issue that has a `generation:` key.

| State | How it is recognised | `compass ci` |
|---|---|---|
| `current` | The number the manifest names, with a matching marker | prints the line |
| `superseded` | A lower number, with a marker | prints nothing |
| `proposal` | Only `proposed.yml`, above the current number | prints the line |
| `incomplete` | Some files and no matching marker (above the current number, or below it with no marker); also a folder that holds `proposed.yml` and anything else | prints the line |
| `complete-unreferenced` | A matching marker above the current number | prints the line |
| `broken` | The manifest names a number whose folder, marker or files do not match | fails the run |

`compass check` refuses an issue whose generation is broken. The CLI never
adopts a leftover folder on its own: `compass issue configure --commit`
adopts a complete one when a person runs it, and `compass issue configure
--discard` removes a proposal or a leftover. [issue-configure.md](issue-configure.md)
has the recovery for a crash after each step.

## Reading

`effective.effective_for(task_dir)` returns an `EffectiveView`:

| Issue | `source` | What it reads |
|---|---|---|
| `generation: n`, n at least 1 | `generation` | `generations/<n>/`, checked against its marker, and nothing else |
| no `generation:` key | `live` | the shipped default or the project's copies of the two governance files, then `compass.yml`, then the issue's `config:`, resolved now |
| `generation: 0` | none | refuses and names the fix |
| no issue (`task_dir=None`) | `live` | the project layers, resolved now |

A project with no `compass.yml` and its own `governance/` copies is resolved
through the legacy adapter in place of the shipped default.

`EffectiveView.evaluator_policy()` returns the routing policy in the shape
`evaluate_route` takes, built by `obligations.policy_adapter` from the resolved
configuration. `effective` and `classify` are the only modules that may import
`obligations` (ADR-037); readers call the view.

## Not built yet

- Moving the reading modules onto `effective_for`, and the verdict header and
  pending-change line in `compass check`.
- The refusal of a check implementation whose major version differs, and
  `compass issue migrate-config`.
- `policy effective --issue` still resolves the live files and does not read
  the generation.
