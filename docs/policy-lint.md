# Policy lint and the policy view

This page is the owning doc for `compass policy lint` and `compass policy
show`. It states what each command checks or shows and the exact shape of the
JSON each one prints. The finding codes and both JSON shapes are a public
contract: a change to a key, its order or a code is a breaking change.

Since 9.0.0 Compass runs one fixed check set, `governance/check-set.yml`
(ADR-094). `compass.yml` holds settings only, and five of them can tighten the
set ([configuration.md](configuration.md)). So `policy lint` lints a file of
settings, and `policy show` names the check set, its digest and the settings
that tighten it.

The code is `cli/compass_pkg/policy_cmd.py` (the two commands),
`cli/compass_pkg/settings_lint.py` (the settings lint and the schema of
`compass.yml`) and `cli/compass_pkg/governance.py` (the step `compass ci` runs).

## What `compass policy lint` runs

| Project | What it runs |
|---|---|
| A root `compass.yml` that Compass reads, the framework's own repository included | The settings lint, and the lint of the project's own governance files |
| No `compass.yml` Compass reads | The lint of the project's own governance files: the project has no settings |
| No `compass.yml` Compass reads, and a copy of `routing-policy.yml` or `guardrails.yml` | A refusal with exit 2 (`governance-copy-removed`) |
| `--file PATH` | The settings lint of that one file |

A `compass.yml` is read when it is the only settings file, or when it has a
top-level `schema:` key. 9.0.0 does not read a copy of the governance files
(ADR-098): such a project runs `compass policy migrate` on 8.x first, which
writes its `compass.yml`.

The lint of the project's own governance files checks the optional files of
its `governance/` folder, read by path: `quarantine.yml`, `review-rules.yml`
and `architecture-sources.yml`. Each fault is an `L-GOVERNANCE-FILE` error.
`compass ci` runs the same lint as its first step.

9.0.0 removed the drift report, which compared a governance copy with the
framework's, and the `governance_drift` setting that made it fail (ADR-098).
It also removed the framework mode, which linted the framework's frozen
`governance/` files before its `compass.yml`. `scripts/validate.sh` runs this
lint, so CI fails on a `compass.yml` a commit would refuse.

Every command that resolves a policy (`compass check` on an issue with no
stored generation, `compass approach evaluate`, assess) runs the same settings
lint first, and refuses with exit 2 when it finds an error.

## The settings lint

The settings lint (`settings_lint.lint`) checks the file over the resolved
check set:

| Code | Level | Meaning |
|---|---|---|
| `L-SETTING-UNKNOWN` | error | A key `compass.yml` cannot hold |
| `L-SETTING-INVALID` | error | A value of the wrong shape, a tighten-only setting that would not add to what an issue owes (a token outside the closed set, a project check that reuses a shipped id, a stage other than `build` or `ship`, a capability other than `entry-exit-evaluation`), or an assessment value the check set does not declare |
| `L-IMPL-UNKNOWN` | error | After the tighten-only settings are applied, a check names an implementation the CLI does not hold (safety-contract guarantee 2) |
| `L-PARENT-REMOVED` | error | `extends:` names a git parent. A team parent can hold checks this file does not show, so every command that resolves a policy refuses with exit 2 until it is deleted. Move the team's checks into the tighten-only settings and delete `extends:`, or stay on 8.x. `compass migrate` refuses a git parent too |
| `L-GOVERNANCE-FILE` | error | A fault in `governance/quarantine.yml`, `review-rules.yml` or `architecture-sources.yml`, such as a quarantine entry with no `tracking_task`. The path names the file |
| `L-SETTING-REMOVED` | warning | A key 9.0.0 removed. It is not read. The catalog keys `dimensions`, `stages`, `rules`, `checks`, `gates` and `vocabulary`, with every entry operation inside them, `extends: compass:default@<n>`, `preset`, `preset_index` and `approvers.project-waiver` (ADR-094); and the keys of ADR-090 to ADR-093 (`models`, `multiagent`, `living_spec`, `artifacts`, `approaches`, `prices`, `github_labels`, `readiness` and the readiness-only fields of `project`); and `governance_drift` (ADR-098). The message ends with what replaces the key, "Replacement: `<setting>`." or "Removed: nothing replaces it.", then "`compass migrate` rewrites it." when `compass migrate` handles the key. An `extends:` that pins the default below `@8` is still read for one thing: it keeps the acceptance strategy `S17` off, so its replacement is `acceptance_strategy: {state: off, reason: ...}` |

## Options and exit codes

| Option | Meaning |
|---|---|
| `--file PATH` | Lint one `compass.yml` as settings over the check set |
| `--json` | Print the document below |

9.0.0 removed `--offline` (nothing is fetched), and `--issue` and
`--exhaustive` (an issue has no config layer, and the classifier went). A
command line that names one fails to parse with one line that names ADR-094.

| Exit | Meaning |
|---|---|
| 0 | Pass: no error. Warnings may be printed |
| 1 | Fail: at least one error |
| 2 | An input cannot be read, or the project holds a governance copy and no `compass.yml` |

Text output is `compass policy lint: PASS` or `compass policy lint: FAIL`,
then one line per finding: `  - CODE [project] path: message`. A warning line
starts `  - warning CODE`.

## `compass policy lint --json`

```json
{
  "schema": 1,
  "mode": "settings",
  "result": "fail",
  "layers": [{"name": "project", "kind": "project"}],
  "stopped_after": null,
  "counts": {"errors": 1, "warnings": 0},
  "findings": [
    {"code": "L-SETTING-INVALID", "level": "error", "layer": "project",
     "path": "autonomy", "group": "settings",
     "message": "...", "detail": null}
  ]
}
```

| Key | Type | Meaning |
|---|---|---|
| `schema` | integer | The version of this shape. It is 1 |
| `mode` | `settings` | Which lint ran. 8.x also wrote `legacy`, for the lint of a governance copy, which 9.0.0 removed |
| `result` | `pass` or `fail` | `fail` when `counts.errors` is above 0 |
| `layers` | list | `project` |
| `stopped_after` | null | Kept for the 8.x shape |
| `counts` | object | `errors` and `warnings`, both integers |
| `findings` | list | Every finding, errors first, in file order |

Each finding has the keys `code`, `level`, `layer`, `path`, `group`
(`settings`), `message` and `detail` (null), in that order. An
`L-SETTING-REMOVED` finding also has `replacement`, last: the settings that
replace the key, joined with "or", or null when nothing replaces it. One
table, `removed_parts.REPLACEMENTS`, gives the message and `replacement` for
every removed key, so the two cannot disagree (ADR-098 decision 7).

## `compass policy show`

`compass policy show` names the policy the project runs now:

```
Policy: compass-checks@9.0.0 (sha256 7472...)
Settings: compass.yml (sha256 9ab0...)
Tightened:
  signoff_labels: ["billing"]
```

- `Policy:` is the check set's id and version and the sha256 of its file, as
  `sha256sum` prints it.
- `Settings:` is the sha256 of `compass.yml`, or `no compass.yml`.
- `Tightened:` lists the tighten-only settings the file applies, as written,
  or `nothing`.

With `--issue SLUG` it adds the issue's `policy:` block (the policy its stored
generation was committed under, [generation-store.md](generation-store.md)) and
its waivers. An issue assessed before 9.0.0 has no block, and the view says so.
Without `--issue` no issue is read: there is no `COMPASS_ISSUE` or
current-task fallback.

Exit 0 on success. Exit 2 when `compass.yml` cannot be read or extends a git
parent, or when the project holds a governance copy and no `compass.yml`
(`governance-copy-removed`).

## `compass policy show --json`

```json
{
  "check_set": "compass-checks@9.0.0",
  "check_set_sha256": "7472...",
  "settings_sha256": null,
  "tightened": {},
  "issue": {"issue": "feature", "generation": 1, "policy": {"...": "..."},
            "waivers": [{"id": "W-1", "check": "suite-passed", "reason": "..."}]}
}
```

| Key | Type | Meaning |
|---|---|---|
| `check_set` | string | The check set's id and version, such as `compass-checks@9.0.0` |
| `check_set_sha256` | string | The sha256 of the check set's file, as `sha256sum` prints it |
| `settings_sha256` | string or null | The sha256 of `compass.yml`, or null without one |
| `tightened` | object | The tighten-only settings `compass.yml` applies, as written |
| `issue` | object | Only with `--issue`: the issue, its generation, its `policy` and its `waivers` |

`issue` is present only with `--issue`. Its `policy` is the manifest's
`policy:` block, or null.

## What this page does not cover

- The per-issue generation store. [generation-store.md](generation-store.md)
  says what reads a generation.
- `compass policy diff`, `policy update`, `policy migrate`, `preset init` and
  `preset test`, which 9.0.0 removed (ADR-094). A command line that names one
  fails to parse with one line that says what replaces it.
- The settings-conflict refusal (`compass check` and the pre-tool hook own it).
