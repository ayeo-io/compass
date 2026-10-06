# Schemas

Schemas for the five machine-readable Compass files. Each of the first three
comes in two forms; `signals.yml` and `compass.yml` have no readable
companion.

| File | Executable schema | Readable companion |
|---|---|---|
| `governance/routing-policy.yml` | `routing-policy.schema.json` | `routing-policy.reference.yml` |
| `governance/guardrails.yml` | `guardrails.schema.json` | `guardrails.reference.yml` |
<!-- vocabulary-scan: allow - the row names files on disk by their real names -->
| `.compass/work/<issue>/manifest.yml` | `manifest.schema.json` | `manifest.reference.yml` |
| `governance/signals.yml` | `signals.schema.json` | none |
| `compass.yml` (a project's configuration file, ADR-043) | `compass.schema.json` | none |

**The `.schema.json` files are real, executable JSON Schema** (draft-07;
`compass.schema.json` declares 2020-12 and uses only what draft-07 also
reads) and are the authority for structure. `compass.schema.json` is
generated from `cli/compass_pkg/catalogue_spec.py` and is never edited by
hand. **The `.reference.yml` files are the
human-readable companions** - JSON Schema is precise but hard to read at a
glance, so each field is also documented in a plain annotated YAML file. Where
the two could be read to differ, the `.schema.json` wins.

## How validation works

`compass policy lint` and `compass issue lint` check in two layers:

1. **The built-in structural linter - always runs.** No dependencies. It
   does the one thing JSON Schema *cannot*: cross-check that every
   guardrail's declared `checks` is actually implemented in the CLI's
   `CHECK_FNS`. A declared check with no implementation is the gap the
   linter exists to catch - see `governance/guardrails.md`.
2. **JSON Schema validation - runs when `jsonschema` is installed.** Fuller
   structural coverage (required keys, enums, nested shapes) against the
   `.schema.json` files. `jsonschema` is an *optional* dependency Compass does
   not bundle; PyYAML, the CLI's one hard dependency, travels inside the
   plugin (`cli/vendor/yaml/`) instead. If `jsonschema` is absent, the lint
   commands say so and run on the built-in linter alone.

So: `pip install jsonschema` for the full check; the CLI works without it.

If you extend a policy file, keep it consistent with both forms and re-run the
linter.
