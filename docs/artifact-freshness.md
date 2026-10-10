# Artifact freshness

This page is the owning doc for the capability `artifact-freshness`. Compass
always records the digest of a document when the document is written. With the
capability on, it also reports the document as stale when an artifact it
depends on has changed since. A stale document is refused at ship and at the
entry of a stage that consumes it. The code is
`cli/compass_pkg/freshness.py`. `compass issue artifact set` writes the
records, and `compass check`, `compass next`, `compass issue receipt` and
`compass ship-commit` read them.

The decision to keep the refusals opt-in is in
`governance/decisions/2026-10-05-artifact-freshness-stays-opt-in.md`. The
decision to record the digests always is in
`governance/decisions/2026-10-10-artifact-freshness-records-digests-always.md`.
The dependencies come from the artifact catalogue, which `compass policy lint`
checks as a graph (see `docs/policy-lint.md`).

## Switching it on

```yaml
capabilities:
  artifact-freshness: true
```

With the capability off, the digests are still recorded, and no reader
changes: `compass check`, `compass next`, the receipt and `compass
ship-commit` name no stale document and refuse nothing for one. The digest is
what tells a rewrite of an approved document from a repeat registration (see
[Rewriting an approved document](#rewriting-an-approved-document)). An issue
reads the capability from its stored generation (see
`docs/generation-store.md`), so turning it on changes nothing for an issue
until the next `compass approach evaluate --write`.

The shipped default declares no `depends_on`. A project adds the
dependencies it wants, for example:

```yaml
artifacts:
  technical-design:
    set: {depends_on: [acceptance-criteria]}
```

## What is recorded

`compass issue artifact set` records the fields below on every registration,
whatever the capability says. With no configuration to read, it records the
document's own digest and no upstream.

`compass issue artifact set <kind> --status ...` stamps the document's entry in
the manifest's `artifacts:` registry:

```yaml
artifacts:
- id: ART-TECHNICAL_DESIGN
  kind: technical-design
  status: draft
  digest: sha256:...
  upstream:
    acceptance-criteria: sha256:...
```

| Field | Meaning |
|---|---|
| `digest` | The SHA-256 of the document's file when it was last written |
| `upstream` | The SHA-256 of each artifact the document `depends_on`, as it was then. An upstream with no file is left out |

The digest is the one a judged check uses for its inputs (see
`docs/judged-checks.md`). An entry is stamped only when its file has other
bytes than the `digest` it holds, or when it holds no `upstream` yet.
Registering a document again without changing it therefore does not refresh
its `upstream`. A document is written against the upstream as it was when its
file last changed.

Nothing else writes either field. A presence check, `compass check` and
`compass issue artifact set` on an unchanged file never clear staleness.

## Rewriting an approved document

A document that reads `approved` and whose file now has other bytes than its
recorded `digest` goes back to `draft` when a stage command registers it again,
whatever `--status` the command passes. Its `approved_by` and `approved_at` are
removed, the entry records the new digest, and `reason` says the document
changed after it was approved, by whom and between which digests. An unchanged
file keeps `approved` with the same approver and time. An approved entry with no
recorded digest, such as a migrated one, is treated as unchanged and gets its
digest recorded. ADR-050 holds the decision.

## When a document is stale

Staleness is computed from the records and the files as they are now. A
document that records `upstream` is stale when:

- an artifact it depends on has other bytes now than the digest recorded;
- an artifact it depends on has no file now (`<id> is missing now`);
- an artifact it depends on had no recorded digest when the document was
  written and has a file now (`<id> was not recorded when this was written`);
- an artifact it depends on has a file that cannot be read now
  (`<id> cannot be read now`);
- an artifact it depends on is stale itself (`<id> is stale`). Staleness
  passes down the graph, so a change to an acceptance criterion makes the
  design stale, and the verification report that depends on the design;
- its own `upstream` record is not a map (`upstream record is not a map`).
  A record that cannot be compared fails closed.

A document with no `upstream` record is not tracked. A document registered by
an earlier build, or in a project with no configuration to read, holds none. A
project that turns the capability on has nothing stale for such a document
until it is written again.
Staleness passes down only through tracked documents. If a middle document
has no `upstream` record, a change above it leaves the document below it
fresh, because the middle document is never stale. Rewriting a middle
document does not clear the one below it, which recorded the middle
document's old digest.

## What a stale document blocks

| Where | Effect |
|---|---|
| `compass ship-commit` | Refuses to land while any tracked document is stale. It names each one and the cause, and commits nothing |
| Entry to `implement` | The stage consumes `acceptance-criteria` and `technical-design`. `compass check` fails once the issue has reached `implement`, and `compass next` appends `entry not met: <kind> is stale` |
| `compass check` at `ship` | A document that no stage consumes fails the check once the issue has reached `ship` |

The stages that consume documents are the `CONSUMES` table in
`freshness.py`. It is code, not configuration, in this version.

## Where it shows

`compass check` adds a guardrail `artifact-freshness`, with one result for
each tracked document. A row has the four keys of every row: `guardrail`,
`name`, `status` (`pass`, `fail` or `nothing-to-check`) and `detail`. The
detail starts with `fresh` or `stale`:

| Detail | Status |
|---|---|
| `fresh - written against acceptance-criteria` | `pass` |
| `stale - acceptance-criteria changed (sha256:... then sha256:...); blocks entry to implement` | `fail` |
| `stale - ...; blocks entry to implement (not yet due)` | `pass`: the issue has not reached the stage |
| `no document records the digests of its upstream` | `nothing-to-check`, one row named `freshness` |

`compass issue receipt` adds an "Artifact freshness" section before the
verdict, with the same detail for each tracked document. It adds nothing when
no document is tracked. The receipt has no JSON form.

`compass ship-commit` refuses with exit 2, like its other refusals, and
prints this text on stderr, naming each stale document:

```
compass: compass ship-commit: refusing to land - 1 artifact(s) are stale:
  technical-design: acceptance-criteria changed (sha256:... then sha256:...)
```

## Limits

- Registering a document records that it was written against the upstream as
  it is now. The CLI cannot tell a document that was rewritten from one that
  was changed by a space. Compass checks bytes, not meaning.
- Omitting a document stops tracking it. `compass issue artifact set <kind>
  --status omitted --reason ...` is allowed even for a stale document,
  because an omission carries a recorded reason. An omitted entry is not
  stamped and is not reported.
- `digest` and `upstream` are ordinary manifest data. A hand edit of them
  defeats the check, as a hand edit of `gates:` does. Compass does not
  protect either from a person who edits the manifest.
- If the configuration cannot be read, `compass issue artifact set` records
  the document's own digest and no upstream, and still saves the status.
- `compass issue artifact set` refuses, and saves nothing, when the document or
  an artifact it depends on has a file that cannot be read. It names the
  files.
- If freshness cannot be evaluated while the capability is on, `compass
  ship-commit` refuses to land and says why, the receipt says so in its
  section, and `compass next` names it at a stage that consumes a document.
- The stages that consume documents are fixed in the code.
- A check result is not marked stale. A judged check already fails when its
  inputs change (see `docs/judged-checks.md`).
- The capability stays off in the shipped default until a run has measured
  its cost.
