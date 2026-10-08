# The generation store

This page is the owning doc for the generation store: the stored, numbered copy
of the configuration an issue runs against. It states what a generation
holds, how a commit writes it, the states a generation folder can be in, and
what reads it. The decision behind it is ADR-036. The code is
`cli/compass_pkg/generation.py` (the files, the commit and the states) and
`cli/compass_pkg/effective.py` (the reading interface and the live
resolution).

## What is built

The store, its commit, the readers, the refusal of a check whose implementation
major differs and the commands that change what it holds are built:
`compass issue migrate-config`, `compass issue configure` (propose, preview,
`--discard`, `--commit`) and `--reset-config` on the reassess
([issue-configure.md](issue-configure.md)). The modules that read
configuration (`routing`, `check_cmd`, `checks`, `receipt`, `manifest`,
`calibration`, `flow`, `quick_fix_cmd`, `loop_ceilings`, `lessons`,
`review_rules` and `approach_diagram`) ask `effective.view_or_legacy` first.
An issue with a generation is judged by that generation, whatever the project's
`compass.yml` or governance files now say. See "Reading" for the one case that
reads the governance files.

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
| `resolved.yml` | The configuration after every layer is merged: the eight catalogues, the evidence types, the capability switches, the approach and the ceilings the issue's overlay names, the autonomy value, and the conformance status. | At commit, then fixed. |
| `provenance.yml` | `fields`: for each field, the layers that wrote it and the operation of each. `waivers`: each waiver with the parent value it saw. `classification`: for the project and issue layers, that the lint raised no error (`result: accepted`) and which waivers the layer holds. It holds no classifier points: a generation stored by this version has no `points` key, and a reader must treat absent points as "not recorded", never as zero. | At commit, then fixed. |
| `versions.yml` | `resolver` and `cli` versions, `parents` (reference, version, digest, source; a git parent adds `sha`, with `source: git`, see [git-parents.md](git-parents.md)), `project` (path, digest, git blob), `issue_overlay_digest`, and `implementations`: the version of each check implementation the configuration uses. | At commit, then fixed. |
| `records.yml` | The status of each approval, waiver and check result at commit: `valid`, `superseded` or `invalidated`, with a reason. | At commit, then fixed. |
| `complete` | A marker holding a digest of each of the four files above. | Last of the four-file commit. |
| `results.yml` | The latest `compass check` verdict for each check: `verdict` (`pass`, `fail`, `advisory` or `nothing-to-check`), `at`, the implementation id and version, a digest of the check's definition, and `status`. | After each `compass check`, replacing the file. The marker does not cover it. |
| `proposed.yml` | A pending change to the issue's `config:` layer: `schema`, `issue`, `base_generation`, `base_config_digest` and `overlay`. The state table below recognises it, and a reassess applies it. | By `compass issue configure`, in the folder above the generation in force. Removed by the reassess that applies it, or by `--discard`. |

Every file begins `schema: 1`. A digest is `sha256:` and the hex digest of the
file's parsed content in canonical JSON, so a comment or a line ending does
not change it and a changed value does.

`versions.yml` records the check implementation versions so that `compass check`
can refuse a check whose implementation major differs from the one the
generation recorded (see "Implementation versions" below).

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

## Commit paths

A new generation is committed in three ways. Each goes through `generation.commit`.

| Path | Command | Stores |
|---|---|---|
| Reassess | `compass approach evaluate --write` | The configuration resolved now. The normal path. |
| Migrate | `compass issue migrate-config` | The stored configuration, pinned to the installed versions. |
| Recovery | `compass issue configure --commit` | A leftover generation folder nobody adopted, when it still matches what a fresh resolution gives. |

## Implementation versions

Each check implementation has a version (`check_registry.py`). A generation
records the version of each implementation it uses, the resolver version and
the schema of its files in `versions.yml`.

`compass check` compares the major of each with the installed one
(`cli/compass_pkg/impl_versions.py`):

- A different **implementation** major refuses that check only. It does not run
  and it records no result. Every other check runs. A refused check that blocks
  counts as a failure. One that is advisory for this assessment does not, and the
  text views list it as an advisory failure. `--json` reports `"status": "refused"` for
  both. The `detail` names the
  implementation, both versions and `compass issue migrate-config`:

```json
{
  "guardrail": "G1",
  "name": "suite-passed",
  "status": "refused",
  "detail": "refused: suite-passed 0.9.0 is recorded, 1.0.0 is installed, a different major, so it did not run. Run `compass issue migrate-config --issue feature` to store a new generation pinned to the installed versions; it invalidates the results recorded under the old ones, so each check runs again."
}
```

- A different **resolver** or **schema** major can change what every check means,
  so `compass check` runs none and exits 2. Other commands do not compare
  versions yet.
- The same major, with a different minor or patch, is not refused.

`compass issue migrate-config [--issue SLUG]` fixes both. It stores a new
generation with the same resolved configuration and provenance, and with
`versions.yml` set to the installed implementation, resolver and CLI versions.
It marks every check result the old generation recorded `invalidated` in
`records.yml`, and the new generation has no `results.yml`, so each check runs
again. Exit 0, or 2 on error.

- It does not read the project's files. A project edit reaches the issue only
  through `compass approach evaluate --write`, which classifies it.
- It refuses a landed issue and writes nothing.
- When the generation already holds the installed versions it says "no change"
  and writes nothing.
- An issue with no `generation:` key, or at generation 0, is adopted: its live
  configuration becomes generation 1, and `provenance.yml` carries `adopted: adopted from live governance`.
- It keeps the manifest's text and changes only the `generation:` line.

The build rule that keeps a verdict from changing without a major bump, and the
list of what each implementation's corpus exercises, are in
[check-implementations.md](check-implementations.md). Within a major, the corpus is
the only evidence of compatibility.

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
through the legacy adapter in place of the shipped default. The adapter also
converts the `project:` guardrails of such a copy: each becomes a guardrail gate
with its own checks and its stage from `checked_at`, and a `command-passes`
check becomes a check named for the guardrail id and name (`PG-E-command-and-suite`)
that carries the guardrail's `params`. A guardrail that omits a default the
framework ships is still reported as absent by `compass check` and
`compass approach evaluate --verbose`, with or without a generation.

`EffectiveView.evaluator_policy()` returns the routing policy in the shape
`evaluate_route` takes, built by `obligations.policy_adapter` from the resolved
configuration. `effective` and `classify` are the only modules that may import
`obligations` (ADR-037); readers call the view.

### What a reader calls

A reader module calls `effective.view_or_legacy(task_dir)`. It returns a view,
or None when the module must read the governance files as before. That is only
an issue with no `generation:` key (or no issue) in a project with no
`compass.yml`. A generation of 0, or one that is not whole, raises.

| Call on the view | Returns | Used by |
|---|---|---|
| `evaluator_policy()`, `autonomy` | the routing policy and the autonomy value | `routing`, `quick_fix_cmd`, `flow`, `calibration`, `approach_diagram` |
| `evaluator_issue()` | the issue's own layer as the evaluator takes it: the approach it names, the stage modes it sets and its subtask ceiling, or None | `routing` |
| `guardrail_gates()` | the guardrails in the legacy shape: `defaults`, `spike_guardrails`, `checks` (each check's `severity`, `on_skipped` and `blocking_when`) and `impl` (the implementation each check runs) | `check_cmd` |
| `gate_requirements()` | the evidence types each gate accepts, and the known types | `checks`, `manifest`, `receipt` |
| `command_checks()` | the checks that run a command the project wrote | `checks` |
| `loop_ceiling_rules()` | the loop-ceiling rules | `loop_ceilings` |
| `known_ids()` | the ids of the guardrails that apply to a shipping approach | `lessons`, `review_rules` |
| `matches(when, assessment)` | whether a `when:` clause holds, using the configuration's dimension orders | the callers above |
| `stage_order()` | the stage names in order | `approach_diagram`, `stage_lists` |
| `capabilities`, `config`, `listing_assessment(assessment, approach)` | the capability switches, the catalogues, and the assessment with the derived key `ships` that a check's `when` reads | `stage_lists` |
| `parent_version()`, `pending_config(manifest)` | for the `compass check` header | `check_cmd` |

A check that a project adds under its own id (for example `arch-rule` with
`impl: command-passes`) runs the implementation, and its result carries the
check's id.

`compass approach evaluate --write` computes the outcome from the project's
live configuration when the project has a `compass.yml`, because the commit
stores that configuration. Without `--write` it reads the generation.

The quarantine registry (`governance/quarantine.yml`) is a project file, not
catalogue data, and stays where it is.

## The `compass check` header

An issue with a generation gets a line `generation <n> (parent <version>)`
ahead of the other notices, and in the `--json` document as `generation` and
`parent_version`. When the manifest's `config:` is not the overlay the
generation was committed with, a second line says `pending: config: is not
committed yet; run compass approach evaluate --write`. The line is a notice and
does not change the exit code. An issue with no generation gets neither.

## Severity and `on_skipped` in `compass check`

`compass check` reads three fields of each check from the generation, so a
check the project adds behaves as it declares.

**Effective severity.** A failure blocks only when the check declares
`severity: blocking` and either declares no `blocking_when` or the issue's
assessment matches it. Any other failure is advisory: it is shown, it is not
counted as a failure and it does not fail the run.

**`on_skipped`.** A check that finds nothing to check returns that result
itself. The check's `on_skipped` then decides what it counts as:

| `on_skipped` | Result |
|---|---|
| `not-applicable` | Counted apart as `nothing-to-check`, as before. |
| `pass` | A pass. |
| `fail` | A failure whose detail says the check found nothing to check and declares `on_skipped: fail`. Severity then applies, so with `severity: advisory` it is an advisory failure. |

A record claim that `landed_by` moves to another issue is a relaxation, not a
skipped check. It stays `nothing-to-check` whatever `on_skipped` says.

The shipped checks that can return nothing to check all declare
`on_skipped: not-applicable`, so their verdicts on an existing issue do not
change. An issue with no generation reads the governance files, which declare
neither `severity` nor `on_skipped`, so it behaves as before with one
exception: the files do declare `blocking_when` for `scenarios-are-executable`.
A legacy issue with `bdd_runner` set and no BDD run recorded used to show that
check as `PASS` with an advisory note. It now shows `ADVISORY`, with status
`advisory` and `advisory: 1` in `--json`, and the verdict line names the
advisory failure. The exit code does not change.

**The views.** An advisory failure appears as `ADVISORY <check>: <detail>` in
`--verbose`, as an `ADVISORY` line in the default view, and as a count in the
verdict line ("N failed as advisory (does not block)"). It is not a `FAIL`
and not a `PASS`.

**The `--json` document** has these keys:

| Key | Meaning |
|---|---|
| `issue`, `approach` | the issue slug and its delivery approach |
| `ran` | how many checks ran |
| `failed` | how many checks failed and block |
| `nothing_to_check` | how many checks found nothing to check |
| `advisory` | how many checks failed and do not block |
| `notices` | the header and warning lines |
| `generation`, `parent_version` | only for an issue with a generation |
| `checks` | a list of `{guardrail, name, status, detail}` |

`status` is `pass`, `fail`, `advisory` or `nothing-to-check`. A run fails
only when `failed` is above zero.

## Not built yet

- `policy effective --issue` still resolves the live files and does not read
  the generation.
- The leftover-generation states are reported by `compass ci`, not by
  `compass check`.
