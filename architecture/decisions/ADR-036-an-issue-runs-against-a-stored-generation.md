---
id: ADR-036
title: An issue runs against a stored generation of its configuration
status: proposed
date: 2026-10-06
supersedes: ''
superseded_by: ''
---

## Context

Every command reads governance live. `compass approach evaluate`, `compass check` and the receipt each load the routing policy and the guardrails from disk when they run, and nothing records which configuration an issue was assessed under. `--write` folds the computed outcome into the manifest (`cli/compass_pkg/routing.py:622-733`), but not the configuration that produced it. It saves the manifest by rewriting the file in place (`save_manifest`, `cli/compass_pkg/core.py:662-664`), so a crash mid-write can leave it truncated.

That was safe while the configuration changed only with a framework release. ADR-033 (projects add checks, gates and dimension values as data) and ADR-035 (delivery approaches, stages and modes are configuration data) let a project, and a single issue, change it. Without a stored copy:

- a project edit or a CLI upgrade changes the obligations of every open issue mid-flight, with no re-assessment and no record;
- a waiver approved against one parent value would be judged against whatever value the live file holds later;
- two sessions on one issue can disagree about what it owes.

ADR-033 named a stored copy of each issue's resolved configuration as the first of the four mechanisms it depends on. This record decides how that copy is stored, committed and recovered.

## Decision

**An issue runs against a stored, numbered generation of its resolved configuration.** The manifest's `generation: n` names it. For an issue with a generation, no command reads live project configuration.

**A generation is a directory, `.compass/work/<slug>/generations/<n>/`, holding:**

- `resolved.yml`: the configuration after every layer is merged, with the capability switches and the issue-level inputs;
- `provenance.yml`: the layer and operation behind every field, the waivers with the parent value each one saw, and each layer's classification;
- `versions.yml`: the resolver, CLI and parent versions and digests, the project layer's digest and the issue overlay's digest;
- `records.yml`: the status of each approval, waiver and evidence record at commit (`valid`, `superseded` or `invalidated`, with a reason);
- `complete`: a marker written last, holding the digests of the four files above;
- `results.yml`: the latest `compass check` verdict per check, rewritten after each run and not covered by the marker;
- `proposed.yml`: a pending issue-layer change written by `compass issue configure`, when there is one.

**`records.yml` is fixed at commit. Check results live in `results.yml`** (`governance/decisions/2026-10-06-check-results-in-their-own-file.md`). A file that changed after its marker would make the marker meaningless.

**The manifest's `config:` is an input; `generation:` is the authority.** Editing `config:` by hand changes nothing until a commit. `compass check` reports a `config:` that differs from the stored overlay digest as a pending change, and does not fail.

**A commit writes in a fixed order.** Under an exclusive lock on the issue:

1. write `resolved.yml`, `provenance.yml`, `versions.yml` and `records.yml` into `generations/<n+1>/`, each atomically (a temporary file in the same directory, then a rename);
2. write the `complete` marker atomically;
3. replace the manifest atomically, with `generation: n+1` and the computed outcome fields that `--write` writes today.

The manifest replace is the commit point. A crash before it leaves the manifest naming generation n, which is still whole. If the resolved configuration, the overlay and the outcome all equal generation n, nothing is committed and the command says so.

**Three commands commit a generation, and nothing else does:**

- reassess (`compass approach evaluate --write`, run by `/compass:assess` and `/compass:assess --reassess`): the normal path, which also commits generation 1 for a new issue;
- `compass issue migrate-config`: a new generation pinned to the installed implementation, schema and resolver versions, which marks the results the old versions produced as invalidated;
- `compass issue configure --commit <n>`: recovery only, described below.

**`generation: 0` and an absent `generation` mean different things.** The manifest template will ship `generation: 0` (it has no `generation` key today), so:

- `generation: 0` means the issue was assessed under 6.x and has no committed generation yet. A command that needs its configuration refuses and names `compass approach evaluate --write` as the fix. It never guesses.
- No `generation` key means the issue predates 6.0.0. It reads live governance exactly as 5.6.0 did (ADR-006). `compass issue migrate-config` adopts it into the model as generation 1.

**A crash leaves one of two leftover states, and the CLI never adopts one on its own.**

- *Incomplete*: some resolved files and no `complete` marker. `compass check` reports it. `compass issue configure --discard` removes it, and the next reassess overwrites it.
- *Complete but unreferenced*: a marker whose digests match, in a directory numbered above the one the manifest names. `compass check` reports it. `compass issue configure --commit <n>` adopts it only when the manifest still names `n-1`, the live project layer and the pinned parents still match `versions.yml`, and every input digest in `records.yml` still matches its file. It then replaces the manifest and does nothing else. `--discard` removes it instead.

A directory holding only `proposed.yml` is a pending proposal, not a leftover. A manifest that names a generation whose marker is missing or does not match its files is broken: `compass check` refuses, because the authoritative configuration is unreadable.

## Alternatives considered

- **Read live configuration and record only its digest in the manifest.** Rejected: a digest shows that the configuration changed but cannot say what the issue owed before, so a waiver could not be checked against the value it was approved for.
- **Store the resolved configuration inside the manifest.** Rejected: the manifest is replaced on every write, so history would be lost, and a person edits the manifest by hand while a generation must not change after commit.
- **Commit on any command that notices a change.** Rejected: an issue's obligations would move without a re-assessment and without a person seeing the classification. A change takes effect only through one of the three named paths.
- **Keep check results in `records.yml`.** Rejected: the file would change after the marker, so the marker could no longer show that the commit is whole.

## Consequences

- A project edit or a CLI upgrade never changes an open issue. The issue sees the change at its next reassess, which classifies it and invalidates what it affects.
- Each issue gains a directory per generation. The files are small and live in `.compass/work/<slug>/`, so a project commits them or not as it treats the rest of that folder. A project that uses Compass commits it as its audit trail; this repository ignores its own.
- An issue that crashed between assess and its first commit fails closed at `generation: 0`, and the error names the command that fixes it.
- A broken generation stops `compass check` for that issue. Restoring the files or running `compass issue migrate-config` after repair recovers it.
- Readers of governance move behind one interface that loads the generation when the manifest names one, and live configuration otherwise. A test checks that existing modules never read the layers directly.

## References

- ADR-006: backward compatibility; a pre-6.0.0 issue reads live governance.
- ADR-033: the stored copy is the first of four mechanisms its decision depends on.
- ADR-035 (the configuration format) and ADR-037 (a configuration change is classified by its effect over the assessment grid).
- `cli/compass_pkg/routing.py` (`--write`), `cli/compass_pkg/session_lease.py:60-73` (the `flock` pattern the commit lock reuses), `schemas/manifest.schema.json`.
