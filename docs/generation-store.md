# The generation store

The owning doc for the generation store: the stored, numbered copy of the
configuration an issue runs against. It says what a generation holds, how a
commit writes it, the states of a generation folder and what reads it. The
decision is ADR-036. Code: `cli/compass_pkg/generation.py` (the files, the
commit and the states) and `cli/compass_pkg/effective.py` (the reading
interface and the live resolution).

An issue with a generation is judged by that generation, whatever the
project's `compass.yml` now says. A new generation is resolved from the
fixed check set (`governance/check-set.yml`, ADR-094) with the tighten-only
settings of `compass.yml` applied. An issue has no configuration layer of
its own: `compass issue configure` and `--reset-config` are removed.

## The manifest keys

| Key | Meaning |
|---|---|
| `generation: n` | The generation the issue runs against. The manifest names it, and it is the authority. |
| `generation: 0` | The issue was assessed under 6.x and has no generation yet. A command that needs its configuration refuses and names `compass approach evaluate --write`. |
| no `generation` key | The issue predates 6.0.0. It reads live governance, and `compass approach evaluate --write` gives it generation 1. |
| `policy:` | The policy the generation in force was committed under (ADR-094). See below. |
| `config:` | The issue's own configuration layer in 8.x. It is not written or read. A generation committed with it keeps its effect. `compass check` names one the generation in force was not committed with, and `compass issue lint` warns about it. |

`templates/manifest.yml` ships `generation: 0`.

The `policy:` block holds:

| Key | Holds |
|---|---|
| `check_set` | The check set's id and version, such as `compass-checks@9.0.0` |
| `check_set_sha256` | The sha256 of the check set file, lowercase hex as `sha256sum` prints it |
| `settings_sha256` | The sha256 of `compass.yml`, or null without one |
| `tightened` | The tighten-only settings applied, as written |
| `autonomy` | The autonomy `resolved.yml` holds: from `compass.yml`, else `balanced` |
| `resolved` | The digest the generation's `complete` marker holds for `resolved.yml` |

- Each generation commit writes the block. A reassess that commits nothing
  writes it for the generation in force.
- A manifest written before 9.0.0 has no block, and a block written before
  `autonomy` was recorded has no `autonomy`. Both stay valid.
- The generation folders are not committed, so this block is the copy a
  reviewer reads, and the source a missing folder is rebuilt from (see "A
  missing folder").

## The generation folder

`.compass/work/<slug>/generations/<n>/` holds:

| File | Holds | Written |
|---|---|---|
| `resolved.yml` | The resolved configuration: the check set with the tighten-only settings applied. It holds the catalogs, the evidence types, the capability switches, the autonomy value and the conformance status. An 8.x generation also holds the approach and the ceilings its overlay named. | At commit, then fixed. |
| `provenance.yml` | `fields`: for each field, the layers that wrote it and the operation of each. Each rule has its own path, `rules.<set>.rules.<id>`; an older generation has no such paths, and a reader must not guess a rule's layer. `waivers`: each waiver with the parent value it saw. `classification`: that the lint raised no error (`result: accepted`) and which waivers the layer holds. It has no `points` key: treat absent points as "not recorded", never as zero. | At commit, then fixed. |
| `versions.yml` | `resolver` and `cli` versions; `parents` (the one parent is the check set, `{ref: compass:checks@9, version, digest, sha256, source: shipped}`; an 8.x git parent added `sha`, `source: git` and a `classification`); `project` (path, digest, git blob); `issue_overlay_digest` (empty since 9.0.0); `implementations`, the version of each check implementation the configuration uses. | At commit, then fixed. |
| `records.yml` | The status of each approval, waiver and check result at commit: `valid`, `superseded` or `invalidated`, with a reason. | At commit, then fixed. |
| `complete` | A marker that holds a digest of each of the four files above. | Last of the four-file commit. |
| `results.yml` | The latest `compass check` verdict for each check: `verdict` (`pass`, `fail`, `advisory` or `nothing-to-check`), `at`, the implementation id and version, a digest of the check's definition, and `status`. | After each `compass check`, replacing the file. The marker does not cover it. |
| `proposed.yml` | An 8.x pending change to the issue's `config:` layer. Nothing reads or writes it. A commit leaves it in place. | By `compass issue configure` in 8.x. |

Every file begins `schema: 1`. A digest is `sha256:` and the hex digest of
the file's parsed content in canonical JSON. A comment or a line ending does
not change it, and a changed value does.

## A commit

`compass approach evaluate --write` commits. It resolves the configuration
first, which runs the settings lint of `compass.yml`. Then it takes an
exclusive lock on `.compass/work/<slug>/.generation.lock` and compares the
result with the generation in force. When something changed:

1. It writes `resolved.yml`, `provenance.yml`, `versions.yml` and `records.yml`
   into `generations/<n+1>/`, each atomically.
2. It writes `complete`, atomically.
3. It replaces `manifest.yml`, atomically, with `generation: n+1` and the
   computed outcome fields. This is the commit point.

- A crash before step 3 leaves the manifest naming generation n, which is
  still whole.
- When the resolved configuration and the computed outcome equal generation
  n, nothing is committed and the command says "no change". The manifest is
  still replaced.
- The gate comments (`# accepts: ...`) are added to the manifest in the same
  replace.
- A reassess can give the commit a stamp, which adds `generation: {from,
  to}` to the `reassessments:` entry in the same replace.
- The manifest's `readiness:` key is not an outcome field. Nothing writes or
  reads it (ADR-093).

The commit refuses, and writes nothing, when:

- the manifest on disk no longer names the generation the command read;
- the next folder holds anything a commit does not write: a file other than
  the four files, `complete`, `proposed.yml` and the temporary files of an
  interrupted write (`.<name>-` and the eight characters `mkstemp` adds), or
  any subfolder. The message names each entry and says to move them out, or
  to remove the folder;
- `generations/`, the next folder or anything inside it is a symbolic link;
- the issue is closed and the result would be a new generation. "No change"
  is still allowed;
- the settings lint rejects `compass.yml`. The message names the file, the
  first error and `compass policy lint`.

It overwrites a leftover folder that holds only files a commit writes: an
incomplete one, one whose marker does not match its files, and a complete
one the manifest does not name. It keeps `proposed.yml`. Each file keeps the
mode of the file it replaces.

## Commit paths

Both paths go through `generation.commit`.

| Path | Command | Stores |
|---|---|---|
| Reassess | `compass approach evaluate --write` | The configuration resolved now. The normal path. |
| Migrate | `compass issue migrate --config` | The stored configuration, pinned to the installed versions. |

## Implementation versions

`versions.yml` records the version of each check implementation
(`check_registry.py`), the resolver version and the schema of the files.
`compass check` compares the major of each with the installed one
(`cli/compass_pkg/impl_versions.py`):

- A different **implementation** major refuses that check only. It does not run
  and records no result. Every other check runs. A refused check that blocks
  counts as a failure. One that is advisory for this assessment does not.
  `--json` reports `"status": "refused"` for both. The `detail` names the
  implementation, both versions and `compass issue migrate --config`:

```json
{
  "guardrail": "G1",
  "name": "suite-passed",
  "status": "refused",
  "detail": "refused: suite-passed 0.9.0 is recorded, 1.1.0 is installed, a different major, so it did not run. Run `compass issue migrate --config --issue feature` to store a new generation pinned to the installed versions; it invalidates the results recorded under the old ones, so each check runs again."
}
```

- A different **resolver** or **schema** major makes every command that reads
  the issue's generation refuse with exit 2. The message names the
  generation, the recorded and installed versions and `compass issue migrate
  --config --issue SLUG`.
- The same major, with a different minor or patch, is not refused.

### The resolver and schema refusal

`generation.load` compares the majors after it reads the generation, and
raises `MajorRefusal`, which `main` prints as `compass: <message>` with exit
2. `MajorRefusal` derives from `BaseException`, so a reader's `except
Exception` fallback cannot catch it.

- A command that changes the issue's records
  (`record_triggers.RECORD_TRIGGERS`, such as `tdd-green` or `scenario add`)
  is refused before it runs, by `command_guard.before_command`, so nothing
  is written.
- That pre-check judges only the issue the command changes
  (`record_triggers.ISSUE_FROM`). So `compass quick-fix start <new-slug>`
  runs while the current issue is refused.
- A command over every issue refuses that issue only. `compass flow` lists it
  as unreadable, and `compass ci` reports it as refused, counts a failure
  and goes on.
- A recorded version that is not a version, such as `v2`, is refused with a
  message that says so. A `versions.yml` that is not a mapping makes the
  generation broken.

These still run:

- `compass issue migrate --config`;
- `compass issue migrate`. It does not pin an issue refused for its resolver
  or schema major, and names `compass issue migrate --config --issue <slug>`;
- `compass policy lint`, `--help` and `--version`.

Limits:

- A command that reads only the manifest, such as `compass approach show`,
  does not refuse.
- The pre-tool hook reads no generation, so it does not compare the majors.
  A guard test in `tests/test_impl_refusal.py` fails at the first resolver
  or schema major bump.
- `checkpoint add` (`record_triggers.EXEMPT`) saves the manifest without the
  pre-check, so it writes to an issue whose generation is refused.

### `compass issue migrate --config`

`compass issue migrate --config [--issue SLUG]` fixes both refusals. Exit 0,
or 2 on error.

- It stores a new generation with the same resolved configuration and
  provenance, and with `versions.yml` set to the installed versions.
- It marks every check result of the old generation `invalidated` in
  `records.yml`. The new generation has no `results.yml`, so each check runs
  again.
- It does not read the project's files. A project edit reaches the issue only
  through `compass approach evaluate --write`.
- It refuses a closed issue and writes nothing.
- When the generation already holds the installed versions and schema, it
  says "no change" and writes nothing.
- An issue with no `generation:` key, or at generation 0, is adopted: its
  live configuration becomes generation 1, and `provenance.yml` holds
  `adopted: adopted from live governance`.
- It changes only the `generation:` line of the manifest.

[check-implementations.md](check-implementations.md) holds the build rule
that keeps a verdict from changing without a major bump. Within a major,
the corpus is the only evidence of compatibility.

## States

`compass ci` reports each issue that has a `generation:` key.

| State | How it is recognized | `compass ci` |
|---|---|---|
| `current` | The number the manifest names, with a matching marker | prints the line |
| `superseded` | A lower number, with a marker | prints nothing |
| `proposal` | Only an 8.x `proposed.yml`, above the current number | prints the line |
| `incomplete` | Some files and no matching marker (above the current number, or below it with no marker); also a folder that holds `proposed.yml` and anything else | prints the line |
| `complete-unreferenced` | A matching marker above the current number | prints the line |
| `broken` | The manifest names a number whose folder, marker or files do not match | fails the run |

- A missing folder is rebuilt from the manifest's `policy:` block first.
  Only when that fails is it `broken`, and `compass ci` adds the reason.
- `compass check` refuses an issue whose generation is broken.
- Only the manifest names the generation in force. A reader never takes a
  leftover folder as it.

## A missing folder

The generation folders are not committed, so a fresh clone has the manifest
and no `generations/<n>/`. Every reader in `effective` first calls
`effective.restore_from_policy`. It acts only when the manifest names
generation n, the folder does not exist at all, and the manifest holds a
`policy:` block:

1. It finds the check set `policy.check_set` names whose file has the sha256
   `policy.check_set_sha256` (`check_set.held`): the shipped file, or an
   earlier release's copy at `governance/check-sets/<id>@<version>.yml`. No
   release has copied one yet.
2. It resolves that check set with `policy.autonomy` and applies
   `policy.tightened`. It does not read `compass.yml`. A block with no
   `autonomy` is tried with each of `controlled`, `balanced` and
   `autonomous`.
3. It uses the result only when the digest of the rebuilt `resolved.yml`
   equals `policy.resolved`.
4. `generation.restore` writes the folder under the generation lock, into a
   hidden folder that it then renames into place.

The rebuilt folder holds:

- `resolved.yml` with the same bytes as the original;
- `provenance.yml` with no field history, and with `restored_from: policy`
  and `restored_at`;
- `versions.yml` with the installed resolver, CLI and implementation versions,
  the check set as the parent, and a `project` entry without a `git_blob`;
- `records.yml` with no record.

The manifest is not changed. Git ignores the rebuilt folder, so it shows in
no `git status`. `compass issue migrate --config` drops the two `restored_`
keys from the provenance it carries forward.

Nothing is written, and the issue stays broken, when the check set is not
held, its sha256 differs, `tightened` cannot be applied, or no digest
matches. The refusal says "its folder is missing" and why the rebuild
failed. A folder that exists but is not whole is never rebuilt. Neither is
one whose manifest has no `policy:` block. The decision is ADR-096
decision 5.

## Reading

`effective.effective_for(task_dir)` returns an `EffectiveView`:

| Issue | `source` | What it reads |
|---|---|---|
| `generation: n`, n at least 1 | `generation` | `generations/<n>/`, checked against its marker, and nothing else |
| no `generation:` key | `live` | the check set with the tighten-only settings of `compass.yml` applied, resolved now; the issue's `config:` is not read (ADR-094) |
| `generation: 0` | none | refuses and names the fix |
| no issue (`task_dir=None`) | `live` | the same, resolved now |

- `effective.resolve_live` reads the check set (`check_set.resolved`) and
  applies the tighten-only settings (`tighten.apply`). Nothing merges.
- Every resolution runs the settings lint first. A `compass.yml` with a lint
  error resolves nothing (exit 2). An `extends:` that names a git parent is
  refused with exit 2 (`L-PARENT-REMOVED`).
- The resolver version is `1.1.0`. A generation that names `1.0.0` still
  loads.
- A project with no `compass.yml` and a copy of `routing-policy.yml` or
  `guardrails.yml` is refused with exit 2 (`governance-copy-removed`,
  ADR-098). The project runs `compass policy migrate` on 8.x first. Only a
  live read is refused: a stored generation is read as stored.
- With `live=True` a stored generation is not read. With no issue, `start`
  names the directory whose project is meant.
- `compass approach evaluate --write` computes the outcome from the live
  configuration, because the commit stores it. Without `--write` it reads
  the generation.
- `effective` is the only module that may import `obligations` (ADR-037).
  Readers call the view.
- `governance/quarantine.yml` is a project file, not catalog data. The check
  `no-trusted-rerun` reads it by path: the project's own, else the
  framework's.

### What a reader calls

| Call on the view | Returns | Used by |
|---|---|---|
| `evaluator_policy()`, `autonomy` | the routing policy, with `signoff_labels` and `require_evidence`, and the autonomy value | `routing`, `quick_fix_cmd`, `flow`, `calibration`, `approach_diagram` |
| `evaluator_issue()` | the 8.x issue layer a stored generation holds: its approach, stage modes, `waived_stages` and subtask ceiling, or None | `routing` |
| `guardrail_gates()` | the guardrails in the legacy shape: `defaults`, `spike_guardrails`, `checks` (each check's `severity`, `on_skipped` and `blocking_when`) and `impl` (the implementation each check runs) | `check_cmd` |
| `gate_requirements()` | the evidence types each gate accepts, and the known types | `checks`, `manifest` |
| `command_checks()` | the checks that run a command the project wrote | `checks` |
| `loop_ceiling_rules()` | the loop-ceiling rules | `loop_ceilings` |
| `known_ids()` | the ids of the guardrails that apply to a shipping approach | `lessons`, `review_rules` |
| `matches(when, assessment)` | whether a `when:` clause holds, using the configuration's dimension orders | the callers above |
| `stage_order()` | the stage names in order | `approach_diagram`, `stage_lists` |
| `capabilities`, `config`, `listing_assessment(assessment, approach)` | the capability switches, the catalogs, and the assessment with the derived key `ships` | `stage_lists` |
| `parent_version()`, `pending_config(manifest)` | for the `compass check` header | `check_cmd` |

A check that a project adds under its own id (for example `arch-rule` with
`impl: command-passes`) runs the implementation, and its result carries the
check's id.

## The `compass check` header

Ahead of the other notices, every run prints:

- `Policy: compass-checks@9.0.0 (sha256 <hex>)`, and `Tightened:` with the
  names of the tighten-only settings applied, when there are any. An issue
  with a generation takes the line from its `policy:` block. One committed
  before 9.0.0 gets no line.
- For an issue with a generation: `generation <n> (parent <version>)`, and
  `generation` and `parent_version` in `--json`.
- When the manifest's `config:` is not the overlay the generation was
  committed with: `config: differs from the generation in force and is not
  read: an issue has no config layer (ADR-094)`. This is a notice and does
  not change the exit code.

## Severity and `on_skipped` in `compass check`

`compass check` reads three fields of each check from the generation.

**Effective severity.** A failure blocks only when the check declares
`severity: blocking` and either declares no `blocking_when` or the issue's
assessment matches it. Any other failure is advisory: it is shown, it is not
counted as a failure and it does not fail the run.

**`on_skipped`** decides what a check that finds nothing to check counts as:

| `on_skipped` | Result |
|---|---|
| `not-applicable` | Counted apart as `nothing-to-check`. |
| `pass` | A pass. |
| `fail` | A failure whose detail says the check found nothing to check and declares `on_skipped: fail`. Severity then applies. |

- The shipped checks that can return nothing to check all declare
  `on_skipped: not-applicable`.
- A record claim that `landed_by` moves to another issue stays
  `nothing-to-check`, whatever `on_skipped` says.
- An issue with no generation reads the governance files, which declare
  neither `severity` nor `on_skipped`. They do declare `blocking_when` for
  `scenarios-are-executable`: a legacy issue with `bdd_runner` set and no
  BDD run recorded shows that check as `ADVISORY`.

**The views.** An advisory failure appears as `ADVISORY <check>: <detail>`
in `--verbose`, as an `ADVISORY` line in the default view, and as a count in
the verdict line ("N failed as advisory (does not block)"). It is not a
`FAIL` and not a `PASS`.

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

## Limits

- `policy show --issue` prints the issue's `policy:` block and its waivers. It
  does not read the generation folder.
- `compass ci` reports the leftover-generation states. `compass check` does
  not.
