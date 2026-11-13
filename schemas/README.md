# Schemas

Schemas for the two machine-readable Compass files. The manifest comes in two
forms; `compass.yml` has no readable companion. 9.0.0 deleted the
generated views `routing-policy.yml` and `guardrails.yml`
and their schemas (ADR-098): the check set, `governance/check-set.yml`, is the
only machine-readable policy. 9.0.0 removed
the readiness record and its schema (ADR-093); a `.compass/readiness.yml`
left in a checkout is not read. 9.0.0 also removed `signals.yml` and its
schema (ADR-094): the stop hook's scope-bloat phrases are fixed in
`hooks/py/stop_scan.py`, and a project's own copy is not read.

| File | Executable schema | Readable companion |
|---|---|---|
<!-- vocabulary-scan: allow - the row names files on disk by their real names -->
| `.compass/work/<issue>/manifest.yml` | `manifest.schema.json` | `manifest.reference.yml` |
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

`compass issue lint` checks a manifest in two layers, and `compass policy lint`
checks `compass.yml` with the settings lint (`docs/policy-lint.md`):

1. **The built-in structural linter - always runs.** No dependencies.
2. **JSON Schema validation - runs when `jsonschema` is installed.** Fuller
   structural coverage (required keys, enums, nested shapes) against the
   `.schema.json` files. `jsonschema` is an *optional* dependency Compass does
   not bundle; PyYAML, the CLI's one hard dependency, travels inside the
   plugin (`cli/vendor/yaml/`) instead. If `jsonschema` is absent, the lint
   commands say so and run on the built-in linter alone.

So: `pip install jsonschema` for the full check; the CLI works without it.

If you extend a policy file, keep it consistent with both forms and re-run the
linter.
