# framework-prose-is-us-english-a-project-sets-its-language

## Decided by

jed72

## Date

2026-10-19

## Supersedes

`governance/decisions/2026-10-02-spell-it-artifact.md`

## Decision

The framework's prose is US English, and a project sets the language of its own prose.

- The framework's prose is US English. This covers what Compass ships and a user reads or types. The "artifact exception" ends: prose spells every word in US English, and "artifact" is no longer a special case.
- A project sets `language` in its own `compass.yml`, as a BCP 47 tag such as `en-US`. A preset cannot carry the key (ADR-043). The hook and the settings reader take the key from the project's settings file: `compass.yml`, or `.compass/config.yml` when `compass.yml` is absent or has no `schema:`.
- The session-start hook adds one line only when `language` is set to a valid tag. Unset means no instruction: Compass says nothing about language and the agent follows the repository's existing prose. An invalid value adds no line and never blocks the session.
- These files are exempt, because they are frozen or immutable: merged decision records, `governance/presets/default@6`, the shipped-releases archive, the compatibility corpora, `cli/vendor`, GitHub's own `cancelled` status and other immutable records. Their spelling does not change.
- Old typed names, such as the old spellings of a flag, a key or a value, are accepted until 8.0.0. A reader prints one notice on standard error when it meets an old name. For one release the writer of saved output emits both spellings, so a consumer that reads only the old one still works: the readiness record holds `catalogue_digest` beside `catalog_digest`, and `compass retro --compliance` emits `behaviour` and `behaviours` beside `behavior` and `behaviors`. The text of a refusal names the old code `not-initialised` as read until 8.0.0. From 8.0.0 only the US spellings are written and read.
- The term `catalogue` becomes `catalog` in the frozen vocabulary (`governance/terminology.yml`). The `catalog` term row keeps `catalogue` as its other form, the version field is raised, and the meaning does not change (ADR-012). This record is the only record of that change.
- The spelling guard comes in two stages: string literals and help text in the 7.0.0 pull request that converts the CLI, then each group of prose files as it is converted. The full guard and the conversion script are issue #243.
- The definitions in `governance/terminology.yml` that `docs/glossary.md` shows change in spelling only, in the pull request that converts the prose. No meaning changes.

## Why

Programming languages and most development tooling use US spelling, so the framework speaks the language of code. The "British English" rule in the Plain English section gave every adopter's documents, issues and commit messages en-GB, whatever their own language. A US team accepts "behaviour" in a README but not in its own record, and a team that writes in another language had no option at all. A project now chooses its language, and Compass gives no preference by default.

## Evidence

The owner's comment on issue #241: https://github.com/ayeo-io/compass-delivery-record/issues/241#issuecomment-6273616740
