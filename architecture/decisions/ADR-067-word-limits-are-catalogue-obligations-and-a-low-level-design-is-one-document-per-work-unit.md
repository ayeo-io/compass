---
id: ADR-067
title: Word limits are catalogue obligations, the design-size check never judges an earlier catalogue, and a low-level design is one registered document per work unit
status: proposed
date: 2026-10-15
supersedes: ''
superseded_by: ''
---

## Context

Full-approach designs reached a median of 46,494 bytes over 7 issues (PRD 35, 10 October 2026). PRD 35 requirement DS-6 asks for a word limit per document kind and depth, a lint finding over the limit, and a `compass check` refusal of a design far over it at plan exit. DS-7 asks for a low-level design per work unit on the full approach.

Four earlier decisions bound the answer:

- **ADR-036 and ADR-064 decision 2.** An issue is judged by the configuration it was stored with. 454 of 501 archived manifests have no `generation` key and read the live view, so a new reader must decline on them first.
- **ADR-053 decision 5.** `artifact_kinds.entry` fills an earlier generation's absent descriptive fields from the shipped default. A field that decides a verdict must not be filled.
- **ADR-054.** A catalogue `file` knows one placeholder, `<n>`, for rounds. Rounds have a latest; work units do not.
- **ADR-033 and the locked guardrails.** The `G2` and `G4` guardrails and the `assess`, `verify` and `ship` stages are locked. A check in a stage list changes the `plan-exit` block of every archived issue.

compass:architect ruled the boundaries for jed72 on 2026-10-15 (AD-1 to AD-9 in the issue `word-ceilings-and-lld`).

## Decision

1. **`word_ceiling` is an obligation field.** It is an optional map from depth to a positive whole number on any catalogue kind. The shipped default sets it on `technical-design` (4,000 thorough, 1,200 lightweight) and `acceptance-criteria` (5,000 thorough, 1,500 lightweight). It is never filled by the stored-generation fallback, and the classifier compares it by identity, like `required_when`.
2. **One function counts words.** A word is a whitespace-separated token of `doc_sections.visible(rendered_blocks.masked_text(text))`. Rendered block interiors, marker lines and HTML comments add nothing. Headings, prose, tables and code fences count.
3. **`compass issue lint` reports two notes and never changes its exit code.** One names a registered document over its limit. The other names a full issue's work unit with no registered low-level design. Both decline on the first four conditions of decision 4.
4. **`design-within-word-ceiling` is a check outside every gate.** It is deterministic, blocking and unlocked, with `on_skipped: not-applicable` and a threshold factor of 1.5 in `params`. It joins no gate and no stage list. It reads `nothing-to-check` on the first of these that holds:
   1. the manifest has no `generation` key;
   2. the issue is closed;
   3. no `technical-design` is registered with a path;
   4. the issue's catalogue has no `word_ceiling` for it at the registered depth;
   5. plan exit is not yet due.

   Otherwise it passes at or under the factor times the limit and fails above it, whatever low-level designs exist.
5. **A low-level design is one registry entry per unit.** A catalogue `file` may hold a `<unit>` placeholder and one directory part, never with `<n>`. A unit is `U` and a whole number from 1 with no leading zero. Each entry holds a `unit` key. A reader with no unit named refuses when two or more are registered. No approach names the kind; the planner registers each file at plan.
6. **Compatibility contract 3 admits the new check's row as `nothing-to-check` only**, as it does for the two section checks of ADR-064.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| A bare `ceiling` key, as DS-6 writes it | The PRD's wording | "Ceiling" already names subtask and loop limits (ADR-044) |
| The check in `stages.plan.exit` | Plan exit is where DS-6 places it | Every archived `plan-exit` block goes stale |
| The check in a gate | Gates already run at the `verify` stage | `G2` and `G4` are locked |
| Units as rounds (`low-level-design-<n>.md`) | Reuses ADR-054 | "Round" gains a second meaning, and the latest-round default is wrong for units |
| One registry entry for the whole folder | Fewer entries | The registry, approval and digest readers expect one file per entry |
| A pass when every unit has a file | DS-6's "unless the overflow has moved" | A stub file per unit would pass a design that kept its overflow |
| The limit filled into earlier generations | One catalogue for all | Earlier-generation issues would be judged by rules they were not stored with |

## Consequences

- A reviewer gets a design and a spec with a stated size, and a builder gets a document for one unit.
- An issue adopts the limits and the check only at its next `compass approach evaluate --write`.
- A regular design over 6,000 words is refused too; its planner shortens it or reassesses to full.
- The classifier version moves, so stored classifications are recomputed once.
- No section of a low-level design is checked. A stub unit file clears nothing, because the refusal reads the design's own count.

## References

- ADR-006, ADR-033, ADR-036, ADR-038, ADR-044, ADR-050, ADR-051, ADR-053, ADR-054, ADR-064.
- The architecture notes and the technical design of the issue `word-ceilings-and-lld`, which give the rulings and design decisions behind this record.
- The word-ceiling check, the design-size check, the artifact-kinds module, the default preset's artifact catalogue and its checks file. The units that build them will name the files.
