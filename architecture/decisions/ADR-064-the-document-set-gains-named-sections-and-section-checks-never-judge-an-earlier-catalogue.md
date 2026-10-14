---
id: ADR-064
title: The document set gains named sections, and the section checks never judge an earlier catalogue
status: proposed
date: 2026-10-14
supersedes: ''
superseded_by: ''
---

Proposed by the planner for document-set-sections on 2026-10-14, from the candidate record in that issue's architecture notes. compass:architect accepts or revises it for jed72 at verify.

## Context

A team used to a traditional design pack looks for four things a Compass issue did not give them: non-functional requirements, data and interface contracts, a verification plan, and risks with dependencies. The documents were also harder to read than they needed to be: section numbers skipped when an optional section was dropped, every spec repeated a nine-line block on how each role reads it, each kind opened with a different header, and the quick-fix record wrote its assessment and policy tables by hand.

Five earlier decisions bound the answer:

- ADR-053: the catalogue lists each kind's headings per depth, and a stored generation keeps its own lists (decision 5).
- ADR-036: an issue runs against the generation it was assessed under.
- ADR-006: an archived issue must behave as before.
- ADR-051: rendered blocks are derived in place by pure renderers, a check never reads a rendered page (decision 13), and compatibility contract 3 allows only exact verdict moves (decision 18).
- ADR-050: `artifacts-approved` is a blocking check that sits in no gate, so a waiver can excuse it.

Most of the archive predates generations. In the maintainer's checkout on 2026-10-14, 454 of 501 manifests have no `generation` key, and an issue with no key in a project with a `compass.yml` is judged by the live configuration. A new check added to the live configuration would therefore judge most of the archive.

## Decision

1. **Named sections.** Catalogue headings carry no section number. A heading keeps its words and loses only its leading number. The acceptance criteria gain `Non-functional requirements`; the technical design gains `Data and interfaces`, `Verification plan` and `Risks and dependencies`, at both depths. `template show` matches a heading with a leading number to the named heading of the same words, so an issue on an earlier generation keeps its template prose. The role block lives once, in `docs/roles-guide.md`. Existing documents are not rewritten.

2. **Two section checks that never judge an earlier catalogue.** `nfr-rows-resolved` and `contracts-declared` are deterministic, blocking and unlocked, and sit in no gate and no stage list, so no locked guardrail changes and an issue waiver can make either advisory. `compass check` runs them, and `artifacts-approved`, through one helper for checks outside a gate. Each check reads `nothing-to-check`, with `on_skipped: not-applicable`, when the first of these holds:
   1. the issue has no `generation` key;
   2. the issue is closed;
   3. the document the check reads is not registered with a path;
   4. the issue's stored catalogue does not list the section at the depth the issue registers the document.
   A stored generation that does not declare a check never runs it; the issue gains it at its next `compass approach evaluate --write`. Each check's corpus holds these shapes with the verdict `nothing-to-check`. `contracts-declared` reads its trigger patterns from its `params` in `checks.yml`, which a project layer can extend.

3. **Two new block kinds and a conditional column.** `document-header` opens every catalogue document except the verification note and shows the issue, approach, stage, owner, status, date, upstream documents and audience, read from the records only. `dependencies` lists `depends_on` in the board's words through `lifecycle.judge` and is a cross-issue part. The `coverage` block gains a `Kind` column only when the issue's technical design holds a `Verification plan` heading, so no archived coverage block changes. No check parses the verification plan.

4. **The quick-fix record is rendered.** Its Assessment and Policy rules fired sections are the existing `assessment` and `policy-rules` blocks, filled through the render path. `compass quick-fix start` becomes a render trigger. This settles ADR-055 decision 9.

5. **Compatibility contract 3 gains two allowed moves.** Each new check may appear on the archive sample only when the recorded verdicts have no row for it and its new verdict is exactly `nothing-to-check`. Any other verdict, including `pass`, stays a difference. No baseline file is rewritten.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Add the checks to G2 and G4 | The checks are about acceptance and evidence | G2 and G4 are locked; a change needs jed72, and a check in a gate cannot be waived |
| Add the checks to a stage list | Each check has a natural stage | A stage list feeds the `dor` and `dod` blocks, so every archived block would go stale |
| Rely on stored generations alone | ADR-036 already keeps old issues on their own configuration | 454 of 501 archived manifests hold no generation and are judged by the live view |
| Rewrite archived documents with the new headings and header | One look across old and new documents | Header markers count in the masked digest, so every approved document would read as edited, and the archive would need a migrate and the `migrations` label |
| Render the `Kind` column on every coverage block | One block shape | Every done issue's own-record block would go stale until a full re-render |
| Shorter new names, such as `Design decisions` | Shorter headings | A generation-1 heading with its number stripped would no longer match, and its prose would be lost |

## Consequences

**Positive:**
- A new regular or full issue has the four sections from its templates, and two of them are checked.
- No archived issue is judged by the new checks, and no archived document or digest moves.
- One helper runs every check outside a gate.

**Negative:**
- Old and new documents look different: archived documents keep numbered headings and the role block.
- Three Definition of Done statements still cite `§1` and `§2` of the verification report, which new reports no longer number; changing them would make the `dod` block stale on every issue that reads the live configuration.

**Neutral / follow-on:**
- `compass check --json` gains two rows on issues that declare the checks, which ADR-046's additive rule allows.
- `template show` no longer prints the Home, Traditional name and Depth lines; the header block replaces them.

## References

- ADR-006: backward compatibility.
- ADR-033: declared data a project can extend.
- ADR-036: an issue runs against a stored generation.
- ADR-038: check implementations carry versions.
- ADR-050: `artifacts-approved` sits in no gate.
- ADR-051: rendered blocks, decisions 2, 3, 8, 13, 17 and 18.
- ADR-053: the artifact catalogue, decisions 3 and 5.
- ADR-055: the delivery-approach record, decision 9.
- ADR-062: dependencies between issues, decision 7.
- `docs/artifact-catalogue.md` and `docs/rendered-blocks.md` own the facts.
