# spike-conclusion-present-stays-unchanged

## Decided by

jed72

## Date

2026-10-12

## Supersedes

Nothing.

## Decision

The locked check `spike-conclusion-present` stays as it is. It reads the `spike-conclusion` evidence record and nothing else. It does not read the artifact registry.

`compass issue artifact set spike-conclusion --decision <discard|graduate-to-delivery|defer>` registers the document and writes or updates the one `spike-conclusion` evidence record in the same command. `--decision graduate-to-delivery` also needs the slug of the delivery issue the spike graduates to. `--decision` on any other kind is refused.

## Why

Changing a locked check needs a lock-file update and an approval, and a registry entry has no decision field. A command that writes the record the check already reads gives a spike one step to close, with no change to the check.

## Evidence

The requirements review of the issue `artifact-catalogue-fields` (question 23 and the maintainer's answer M1, accepted on 2026-10-12). `tests/test_artifact_catalogue_fields.py::test_acf_30` holds the check's unchanged behaviour and `test_acf_62` the command.
