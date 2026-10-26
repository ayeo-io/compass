---
STATUS: ACCEPTED
date: 2026-05-24
---

# Compass - Component Relations

<!-- the assess stage reads this file and includes it in architecture-loaded.yml as a
     narrative artifact. The architect reads it to determine which
     labels in manifest.yml.assessment map to known component names, so
     it knows when to fire automatically at the define stage.

     Format: keep component names consistent with the labels used in
     manifest.yml.assessment.labels so the role can match them.

     Direction: A -> B means A reads or calls B (A is the caller/reader,
     B is the callee/source). -->

## Call graph and read graph

The following table enumerates every non-trivial relation between Compass
components. Relations are ordered by the calling component.

| From | To | Transport | Purpose | Criticality |
|---|---|---|---|---|
| `cli/compass` | `governance/routing-policy.yml` | file read | `compass approach evaluate` applies routing policy at assess | high |
| `cli/compass` | `governance/guardrails.yml` | file read | `compass check` runs gate assertions against this schema | high |
| `cli/compass` | `governance/strategies.md` | file read | strategy documentation consulted by CLI subcommands | medium |
| `cli/compass` | `governance/signals.yml` | file read | `compass rework-scan` and `compass retro` read signal patterns | medium |
| `cli/compass` | `architecture/` | file read | `frame_load_architecture` reads all `*.md` files and `decisions/ADR-*.md` into `architecture-loaded.yml` | medium |
| `cli/compass` | `.compass/work/` | file read/write | every subcommand (assess, check, tdd-red, tdd-green, rework-scan, retro) reads and writes issue manifests under this directory | high |
| `cli/compass` | `.compass/current-task` | file read | resolves the active issue slug for hooks and subcommands that don't receive `--issue` explicitly | high |
| `hooks/pre-tool.sh` | `.compass/work/<issue>/.red` | file read | the hook checks for the `.red` marker before allowing code-editing tool calls; absent marker → edit blocked | high |
| `hooks/pre-tool.sh` | `.compass/current-task` | file read | resolves which issue's `.red` marker to check | high |
| `hooks/pre-tool.sh` | `hooks/lib/pre-tool-*.sh` | sourced in order at the top level | the rest of the hook; every part is checked before any runs, and a missing or unreadable part refuses the call | high |
| `scripts/lib/compass-python.sh`, `scripts/lib/python-check.sh` | `hooks/py/lib_*.py` | python3 call | the setting reader and the version probe the shared shell libraries run | medium |
| `hooks/pre-tool.sh` | `cli/compass_pkg/comment_only_edit.py` and the edited `.py`, `.yml` or `.yaml` file | python3 call with the tool call on stdin; file read | an Edit that the module proves changes only comments, docstrings or layout is allowed with no failing test and no issue lookup; any doubt, failure or overrun gives the verdict the hook gave before, and a missing `python3` refuses (`docs/safety-contract.md`) | high |
| `hooks/stop.sh` | `governance/signals.yml` | file read | reads scope-bloat and rework signal patterns at session end | medium |
| `hooks/stop.sh` | `.compass/work/<issue>/devlog.md` | file read | scans the session's devlog for rework signals before the session closes | medium |
| `hooks/stop.sh` | `.compass/current-task` | file read | resolves the active issue for devlog location | medium |
| `architect` (agent) | `architecture/` | file read | reads `system-context.md`, `relations.md`, `ownership.md`, `invariants.yml` (if present), and all `decisions/ADR-*.md` to build its consultation context | medium |
| `architect` (agent) | `.compass/work/<issue>/acceptance-criteria.md` | file read | reads scenarios the issue must satisfy | medium |
| `architect` (agent) | `.compass/work/<issue>/technical-design.md` | file read | reads the technical approach to annotate | medium |
| `architect` (agent) | `.compass/work/<issue>/architecture-loaded.yml` | file read | reads the assess stage's load record if present | medium |
| `architect` (agent) | `.compass/work/<issue>/architecture-notes.md` | file write | writes its output (annotations, boundary risks, candidate ADR titles) | medium |
| `agents/spec-author.md` | `architecture/decisions/ADR-*.md` | via `architecture-loaded.yml` | reads ADR summaries (id, title, status) to avoid re-litigating closed decisions | low |
| `agents/planner.md` | `.compass/work/<issue>/architecture-notes.md` | file read | planner reads architect output to compose `technical-design.md §2` design decisions | medium |
| `cli/compass` (`release notes`) | `.compass/work/` and git | file read, `git` read | `compass release notes --since <ref>` reads completed issue manifests with `load_yaml`, the living spec committed at HEAD and at the ref, and commit reachability; it writes nothing (ADR-065) | low |
| `templates/<kind>.md` | `cli/compass_pkg/template_lists.py`, `cli/compass_pkg/policy_lint.py` | file read | `compass issue template show` reads the file to print it; `compass policy lint` reads it to check an artifact kind's sections | low |
| `templates/architecture/` | n/a | reference only | the subfolder is not listed by `compass issue template show` and no CLI path reads it; an adopter copies it by hand to bootstrap their own `architecture/` tree | n/a |

## Prohibited relations

The following relations must never be created. They would violate invariants
or cross boundary rules encoded in the ADRs.

- **`architect` must not read any directory other than `architecture/`** -
  the role reads exactly `architecture/` at the project root. Reading any
  sibling or adjacent directory that might contain draft or provisional content
  would introduce undeclared dependencies. The role reads `architecture/` only.
  (Cited source: `TRC-D2` and the `architect` agent's hard boundaries.)

- **Any mechanism must not write into `manifest.yml.assessment`** - the assessment is the
  human's judgement field; mechanism-produced state lives in `architecture-loaded.yml`
  and elsewhere in `manifest.yml`. (See ADR-001.)

- **`hooks/stop.sh` and `compass rework-scan` must not mutate `manifest.yml`** -
  both are read-only over the manifest. Detection is advisory; blocking on
  detection would violate ADR-003 (Flow advises, never gates) and the
  invariant behind it, `Inv-4`.

- **`compass retro` must not mutate `manifest.yml`** - `compass retro` aggregates
  re-assessment data read-only; it never writes back to individual issue manifests
  (`Inv-4`: Flow advises, never gates).

## Known interface contracts

| Contract | Location | Notes |
|---|---|---|
| Issue manifest schema (`manifest.yml`) | `cli/compass` (validated inline), `schemas/manifest.schema.json` | `schema_version: '2.0'`; fields: assessment, delivery_approach, orchestration, stages, evidence, gates, scenarios, changed_files, claims, follow_ups, reassessments |
| Architecture load record | `cli/compass` (`frame_load_architecture`) | `schema_version: '1.0'`; fields: artifacts (path, sha256, type), adrs (id, path, title, status), loaded_at |
| ADR frontmatter | `architecture/decisions/ADR-*.md` | Required fields: id, title, status, date, supersedes, superseded_by. Status: accepted \| proposed \| superseded. |
| Routing policy schema | `governance/routing-policy.yml` | Consumed by `compass approach evaluate`; schema validated by `tests/test_policy_integrity.py` |
| Guardrails schema | `governance/guardrails.yml` | Consumed by `compass check`; checks gate evidence types |
