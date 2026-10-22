# Execution profiles

An execution profile fixes one way of working as a versioned file. It names the model tier and effort, the exact revision of every skill, prompt fragment and piece of tool guidance, and the limits of an unattended run. `compass profile` checks a profile file, stores it as a new version, and resolves a stored version to the exact revision of each component.

A profile decides how eligible work is done. It never decides whether work is allowed. It changes no readiness floor, approval, gate or permission, and nothing selects or runs a profile yet. `compass run` does not read a profile.

## Commands

| Command | What it does |
|---|---|
| `compass profile lint FILE` | Checks one profile file against every rule and prints the 11 required fields. It needs no project. Outside a project it reads the shipped routing policy. |
| `compass profile add FILE` | Runs every `lint` rule, then copies the file unchanged into the store as a new version. It needs a Compass project. |
| `compass profile show ID --version N` | Reads one stored version, runs every `lint` rule, then looks up each component in the component registry. It prints the exact revisions, or refuses. It needs a Compass project. |

All three accept `--json`. A refusal prints one line for each reason on standard output, `<reason code>: <what is wrong>`, with no heading, and exits with code 2. With `--json` a refusal prints a list of `code` and `message`. A success exits with code 0. `profile lint` exits with 2 on a fault, where `policy lint` exits with 1.

`show` never chooses a version. Without `--version` it refuses with `version-required`, so no version is taken as the latest.

## Where the files are

The store and the component registry are in the `profiles` folder at the top of the project. They are committed with the project and sit outside `.compass/`, `governance/` and `compass.yml`.

- A stored version is `profiles/<id>.<version>.yml`, one flat file for each id and version.
- The component registry is the file `component-registry.yml` in `profiles/`. The commands read it and never write it. A person edits it, and a pull request reviews the change.
- The commands build exact names and list nothing. They ignore other files in `profiles/`.
- A symbolic link in `profiles/`, as a stored version or as the registry, is refused as `file-unreadable`.
- `show` refuses a stored file whose id or version is not the one its name gives, as `field-malformed`. The reason reads, for example, "the file name says version 2 but the file holds version 1".
- `add` creates `profiles/` when it is absent.

The format has a JSON Schema, `schemas/execution-profile.schema.json` (draft-07). It states structure and formats only and names no tier, effort level or ceiling. The code in `cli/compass_pkg/execution_profile.py` is the authority. The CLI does not import `jsonschema`; only the tests check files against the schema.

## The profile file

Every field is required. A person writes each one by hand. Any other key is refused.

- `schema`: the number 1.
- `id`: lower-case letters, digits and hyphens, 1 to 64 characters, starting with a letter. It starts the file name, so it has no dot.
- `version`: a whole number of 1 or more. It is 1 when `parent` is null, else the parent's version plus 1.
- `digest`: `sha256:` and 64 lower-case hexadecimal digits.
- `parent`: null, or `version` and `digest` of the version this one came from.
- `owner`: text.
- `approval`: `state` (text), `by` and `at` (text or null). It is part of the content and the digest. `show` reports it and does not enforce it.
- `applies_to`: `task_classes` and `repositories`, two lists that are not empty. Nothing matches them to a work item yet.
- `runner_versions`: a list of versions such as 7.0.0. An empty list is refused as `field-malformed`, because it would make every component compatible.
- `model`: `tier` and `effort`, as `compass approach show` knows them, and `provider_revision`, text or null. A null value means the provider gives no pinned version.
- `components`: `skills`, `prompt_fragments` and `tool_guidance`, each a list of `id` and `revision`. A revision is `sha256:` and 64 lower-case hexadecimal digits. A name such as `latest` is refused. The same id twice in one list is refused.
- `runner_settings`: `max_cycles` (a whole number of 1 or more), `max_minutes` and `max_cost_usd` (numbers above 0).

A profile holds no model name and no copy of the routing policy. It names a tier, and the project's `models` setting maps the tier to a model when `show` runs. A key that copies the routing policy is refused as `policy-copy`.

## The digest

The digest is the SHA-256 of the profile's content in canonical form: the parsed content without `digest`, with sorted keys, no spaces and ASCII only. Key order, spacing and comments do not change it. The order of each list does. Write quoted text for a date in `approval.at`, and write `5` and not `5.0`: a different type gives a different digest.

`lint --json` prints the computed digest in `computed_digest`. Copy it into the file. `lint` prints `digest-mismatch` only when the content has no other fault.

## Versions and the store

- The first version is 1 and has no parent. Version n names version n-1 and its digest as parent.
- `add` stores the bytes of the file unchanged, so comments stay. It writes a temporary file and links it to the final name, which fails if the name exists.
- The same content added again prints "already stored" and exits with 0.
- Different content for a stored version is refused as `version-immutable`.
- A hand edit of a stored file fails the digest check when `show` reads it. A hand edit that also rewrites the digest of the newest version is caught only by review of the pull request.

## The component registry

`component-registry.yml` holds one key, `components`, a list. Each entry has `kind` (`skill`, `prompt_fragment` or `tool_guidance`), `id`, `revision`, `runner_versions`, and an optional `approval` with `state`, `by` and `at`. A missing file, an empty file or an absent key holds no entry, so every component is missing. A file that exists and cannot be used is refused with the code that names the fault, the registry path and the position of the entry.

The resolver finds each component by kind, id and exact revision. It never uses another revision.

- Only an `approval` with the state `approved` passes. An absent, `pending` or `rejected` state is not approved. An approval does not carry to another revision.
- Every runner version of the profile must be in the entry's `runner_versions`, compared as exact text.
- `show` prints one line for each fault of a component, in the order skills, prompt fragments, tool guidance, each in file order. A component can have a not-approved line and an incompatible line.

## What is recorded and not checked

- Approval in the registry is a recorded fact and not a checked one. It is text in a committed file. The resolver does not check who wrote it, and no approval guard protects it.
- The resolver trusts the revision an entry gives. It does not check a revision against the skill, prompt or guidance files.
- A hand edit that also rewrites the digest of the newest version is caught only by review.
- The resolver does not check that the provider revision belongs to the model the tier maps to. It prints both, and a reader compares them.

## Reproducibility limits

A limit is a fact `show` prints that stops a reader repeating a run exactly. It is not a refusal, and `show` still exits with 0. The limits are in `reproducibility_limits` in `--json`.

## Ceilings

`runner_settings` cannot exceed the limits of an unattended run. The ceiling of a setting is the lowest limit among the routing policy rules for `run_cycles`, `run_minutes` and `run_cost_usd`, whatever their `when`, because a profile belongs to no assessment. The shipped values are 30 cycles, 240 minutes and 5 US dollars (see `docs/headless-runner.md`). The code reads the policy and holds no copy of the numbers. A setting that no rule limits has no ceiling.

## Reason codes

| Code | Command | Meaning |
|---|---|---|
| `file-unreadable` | all | The file is missing, is a folder, is a symbolic link in `profiles/`, is not UTF-8 text, is not valid YAML, repeats a key, or is empty or not a mapping. |
| `field-missing` | all | A required field is absent. |
| `field-malformed` | all | A value has the wrong type or format, a list that must hold a value is empty, or a stored file's name gives another id or version than its content. |
| `field-unknown` | lint, add, show | The file holds a key the format does not define. |
| `policy-copy` | lint, add, show | The file holds a key that copies the routing policy. |
| `scope-empty` | lint, add, show | `applies_to` holds an empty list. |
| `component-duplicate` | lint, add, show | One kind and id is listed twice. |
| `revision-not-exact` | lint, add, show | A component revision is not `sha256:` and 64 hexadecimal digits. |
| `tier-unknown` | lint, add, show | `model.tier` is not a tier. The line lists the accepted values. |
| `effort-unknown` | lint, add, show | `model.effort` is not an effort level. The line lists the accepted values. |
| `version-not-next` | lint, add, show | The version does not follow its parent. |
| `runner-setting-over-ceiling` | lint, add, show | A runner setting is above the ceiling of the routing policy. |
| `digest-mismatch` | lint, add, show | The recorded digest is not the digest of the content. |
| `version-immutable` | add | The version is stored with other content. |
| `parent-missing` | add | The parent version is not in the store. |
| `parent-digest-mismatch` | add | The parent digest is not the digest of the stored parent. |
| `version-required` | show | No `--version` was given. |
| `profile-missing` | show | The id and version are not in the store. An id that does not have the id format is missing. |
| `component-missing` | show | The registry has no entry for the kind, id and revision. |
| `component-not-approved` | show | The entry's approval state is not `approved`. |
| `component-incompatible` | show | The entry lacks a runner version of the profile. |
| `registry-duplicate` | show | The registry lists one kind, id and revision twice. |
| `model-follows-session` | show | The tier maps to `inherit`, so the model is the one the session runs on. This is a limit. |
| `model-version-not-pinned` | show | The profile has no provider revision. This is a limit. |

## Where the code is

- `cli/compass_pkg/execution_profile.py`: formats, reason codes, the rules, the digest and the ceilings.
- `cli/compass_pkg/execution_profile_store.py`: the store, the component registry, `show` and the limits.
- `cli/compass_pkg/execution_profile_cmd.py`: the command registration and the output.
- `tests/test_execution_profiles.py` and `tests/fixtures/execution-profiles/`: the tests and the four fixtures `valid`, `changed`, `missing-component` and `incompatible-component`.
