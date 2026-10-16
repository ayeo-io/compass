# the-word-rewrite-is-policy-migrate-words

## Decided by

compass:architect, for jed72, who delegated the choice of spelling in the brief for ayeo-io/compass-delivery-record#34 ("Add a tool that rewrites a project's configuration in the new words").

## Date

2026-10-16

## Supersedes

Nothing.

## Decision

The command that rewrites a project's own configuration in the 6.0.0 words is `compass policy migrate --words [DIR] [--apply] [--i-have-a-copy]`, a mode of the existing verb. It is not a new verb, and it has no alias.

## Why

- ADR-044 limits a leaf verb to `show`, `list`, `add`, `remove`, `set`, `render`, `lint`, `test`, `diff`, `update`, `migrate`, `sync` and `init`. `migrate` already means "bring an old form to the current one", and `compass issue migrate --config` is a mode flag on the same verb. `reword` or `rewrite` would need a named exception in the verb-convention test.
- `--apply` with a dry run by default is the contract `compass policy migrate` already has.
- `compass policy update` moves the shipped default major and re-approves waivers. The rewrite moves no major.
- `compass preset` holds the verbs for preset repositories only. The rewrite also serves a project's own `compass.yml`.
- `--i-have-a-copy` is the override `compass issue migrate --apply` gives its own copy check.
- No release tag holds the spelling, so no alias is owed (governance decision `2026-10-08-a-cli-spelling-is-released-only-when-a-tag-holds-it`).

## Evidence

- `architecture/decisions/ADR-044-vocabulary-and-cli-naming.md`, "The CLI convention".
- `tests/test_cli_renames.py`, the `FIXED` set and `convention_problems`.
- `cli/compass_pkg/policy_cmd.py`, `register` and `register_preset`.
