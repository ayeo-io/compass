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
- A project sets `language` in its own `compass.yml`, as a BCP 47 tag such as `en-US`. A preset cannot carry the key (ADR-043).
- The session-start hook adds one line only when `language` is set. Unset means no instruction: Compass says nothing about language and the agent follows the repository's existing prose.
- These files are exempt, because they are frozen or immutable: merged decision records, `governance/presets/default@6`, the shipped-releases archive, the compatibility corpora, `cli/vendor`, GitHub's own `cancelled` status and other immutable records. Their spelling does not change.
- Old typed names, such as the old spellings of a flag, a key or a value, are accepted until 8.0.0. The CLI does not print them back.
- The term `catalogue` becomes `catalog` in the frozen vocabulary (`governance/terminology.yml`). The old word stays as the term's other form, the version field is raised, and the meaning does not change (TRC-069, ADR-012). This record is the only record of that change.
- The spelling guard comes in two stages: string literals and help text in the 7.0.0 pull request that converts the CLI, then each group of prose files as it is converted. The full guard and the conversion script are issue #243.
- The definitions in `governance/terminology.yml` that `docs/glossary.md` shows change in spelling only, in the pull request that converts the prose. No meaning changes.

## Why

Programming languages and most development tooling use US spelling, so the framework speaks the language of code. The "British English" rule in the Plain English section gave every adopter's documents, issues and commit messages en-GB, whatever their own language. A US team accepts "behaviour" in a README but not in its own record, and a team that writes in another language had no option at all. A project now chooses its language, and Compass gives no preference by default.

## Evidence

The owner's comment on issue #241: https://github.com/ayeo-io/compass-delivery-record/issues/241#issuecomment-6273616740
