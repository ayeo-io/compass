---
id: ADR-091
title: Compass needs only the acceptance criteria
status: accepted
date: 2026-11-04
supersedes: ''
superseded_by: ''
---

## Context

Compass 9.0.0 keeps one issue document, the acceptance criteria (ayeo-io/compass-delivery#345 and #353). Before 9.0.0 an approach owed up to seven documents, and Compass wrote, catalogued and checked each one:

- the required documents: the delivery approach, the intent, the requirements review, the technical design, its low-level design units, the distribution map, the verification report, the verification note, the bug report, the threat model, the rollback plan, the review rounds and the spike conclusion;
- the artifact catalogue (`artifacts:` in the shipped default), the artifact status of each registered document (`compass issue artifact set`, the check `artifacts-approved`) and artifact freshness (the capability `artifact-freshness`);
- rendered blocks, the issue page and the project index (`compass issue render`, the check `rendered-blocks-current`);
- the receipt (`compass issue receipt`) and `compass analyze` (the check `consistency-check-passes`);
- the living spec, `docs/system-spec.md`, derived at each landing (`compass spec sync`, ADR-026).

The documents cost 12 to 27 writes a run, and each later request reads them again (the 9.0.0 repositioning proposal of 31 October 2026, which #345 links). The tests and the records are the proof; the documents restate them.

Archived issues hold these documents and records: a manifest's `artifacts:` list, stored generations that list the removed checks, and frozen presets (`default@6`, `default@7`) that declare the catalogue. A record must stay readable, and no archived issue may go from pass to fail.

## Decision

1. **One required document.** Compass needs and checks only `acceptance-criteria.md`, at `docs/compass/<created>-<slug>/acceptance-criteria.md`. A team can keep its own notes; Compass neither needs nor checks them. No command reads a removed document, so `compass plan lint` (the placeholder scan of the technical design) and the landing refusal `project-decision-unrecorded` (ADR-072, which read the design's decision scopes) go too.
2. **Fourteen templates go.** `delivery-approach`, `verification-note`, `technical-design`, `low-level-design`, `distribution-map`, `verification-report`, `intent`, `requirements-review`, `threat-model`, `rollback-plan`, `bug-report`, `review`, `spike-conclusion` and `incident`. `acceptance-criteria`, `devlog`, `pull-request-body`, `manifest.yml` and `templates/architecture/` stay. The five role templates (`positioning`, `launch-readiness`, `ui-contract`, `product-owner-review`, `architecture-notes`) stay until #354 removes the role entry points. No kept template holds a rendered-block marker, and the acceptance criteria hold no Coverage ledger.
3. **No artifact catalogue.** The shipped default declares an empty `artifacts:` catalogue, so every reader that loads the preset by its list of catalogues still finds the file. It declares no approach `artifacts:` map, no `add_artifact` floor and no `artifact-rules` rule set. The fields stay valid in the configuration catalogue and are not read, so a frozen preset and a stored generation still load. A project `compass.yml` can no longer change the catalogue: the merge leaves a project `artifacts:` key out, and `compass policy lint` names it (`L-SETTING-REMOVED`). `nfr-rows-resolved` reads the sections of the acceptance criteria from the last shipped catalogue, `default@7`, when the issue's configuration declares none.
4. **No artifact status or freshness.** `compass issue artifact set`, `compass issue artifact-path` and `compass issue template show` are removed, with the document form of an approval (`compass evidence approve --artifact` and `compass evidence request --artifact`). A pending request for a document, written before 9.0.0, closes with nothing written. Routing writes no `artifacts:` list, and no stage record (a red, an acceptance record, a gate pass, a landing or a quick-fix finish) moves a document's status. `compass issue migrate` still settles the statuses a 6.0.0 record holds and writes the item records a pre-7.0.0 verification report holds, but adds no marker and no verification note. The capability `artifact-freshness` stays valid and is not read.
5. **No rendered blocks.** `compass issue render`, the issue page and the project index are removed. A document written before 9.0.0 can still hold block markers: the readers that digest or parse it leave the block lines out, as before, so a recorded digest still matches.
6. **No receipt, no `compass analyze`, no living spec.** `compass issue receipt`, `compass analyze`, `compass spec sync` and `_derive-system-spec` are removed, with `docs/system-spec.md` and `docs/system-spec-archive.md`. `compass ship-commit` and `compass quick-fix finish` derive nothing. `compass adr new` and `compass ci` move to their own modules.
7. **Removed checks.** `rendered-blocks-current`, `artifacts-approved`, `consistency-check-passes`, `design-within-word-ceiling`, `contracts-declared` and `borrowed-documents-answered` move to the table of removed checks (`check_registry.REMOVED`), with no replacement. A stored generation that lists one reports it as nothing to check. `dashboard-current` names no replacement either, because its replacement is removed.
8. **Kept checks that read a document.**
   - `nfr-rows-resolved` reads the acceptance criteria at the fixed path, or at the path an older manifest registered.
   - `dod-evidence-typed` 2.1.0: on an issue created on or after 2026-11-04 it is judged once every gate has passed, with no report. An older issue keeps the rule it had: judged when its verification report exists. `compass ship-commit` runs it as the landing check, in place of `artifacts-approved`, and refuses to land while it fails (`definition-of-done-open`).
   - `spike-conclusion-present` is unchanged. Its record is written with `compass evidence add EV-SPIKE --type spike-conclusion --path <file> --decision <decision> [--next-issue <slug>]`.
   - The Definition of Ready applies where the issue's `refine` mode is `lightweight` or `thorough`, and the Definition of Done where `verify` is `thorough`: the same approaches as before. A stored configuration whose approach still declares an `artifacts:` map is read by its map, as before. In the shipped default their items no longer name a removed document or a section of one: seven statements now name the record instead. A stored generation keeps the statements it was written with.
9. **The delivery approach is the manifest.** The pre-tool hook, `compass next` and the stop hook read the manifest's `delivery_approach:` instead of `delivery-approach.md`. `compass approach show` prints the decision. `compass quick-fix start` writes no document: the quick fix's intent sentence, scenario, advice and de-scope reasons, which the manifest has no key for, open its `devlog.md`.
10. **Old records, settings and stored generations.**
    - A manifest's `artifacts:` list and evidence of type `artifact-approval` or `consistency-check` stay valid and are not written.
    - The `compass.yml` keys `living_spec` and `artifacts`, and the capability `artifact-freshness` set to true, stay valid and are not read. `compass policy lint` names each one as removed in 9.0.0 (`L-SETTING-REMOVED`, a warning).
    - A removed verb fails to parse, and the error names it as removed in 9.0.0 with this ADR.
    - The archived documents on disk stay where they are. Only `acceptance-criteria.md` is read.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Keep the documents but stop checking them | Fewer changes to tests and fixtures | The writes and the re-reads are the cost #345 removes; a document no check reads still costs both |
| Keep a catalogue with the acceptance criteria alone | `nfr-rows-resolved` reads its sections from it | One fixed document needs no catalogue; the two section names are fixed in code |
| Delete the catalogue fields from the configuration schema | Less code | A frozen preset and every stored generation declare them, so an archived issue would fail to load |
| Keep `compass issue render` for the acceptance criteria | The coverage block shows test records beside the scenarios | `compass check` and `compass status` show the same records; a block costs a write each time a record changes |
| Keep `rendered-blocks-current` and let it pass with no blocks | No removed-check entry | A check that can only pass checks nothing |
| Delete `delivery-approach.md` but keep the hook reading it | No hook change | Every code edit on a new issue would be refused (`no-delivery-approach`) |

## Consequences

- An issue writes one document. A stage command writes no other document and registers nothing.
- An archived issue keeps its verdict or moves from fail to pass, never from pass to fail.
- A project on `compass:default@6` or `@7` still has an approach `artifacts:` map in its preset. Nothing reads it.
- The `positioning` artifact rule no longer adds the `verify.claims` gate, because no command reads which documents an issue has on disk. The landing refusal `artifact-rule-not-applied` goes with that reading. #354 decides how claims are reviewed.

## Open questions

Each question has the default this change builds.

1. **Which fourteen templates?** Default: the fourteen in decision 2; the five role templates wait for #354.
2. **Does `delivery-approach.md` go?** Default: yes; the manifest holds the decision. `CLAUDE.md` names the file under "When you are unsure" and needs an owner's edit.
3. **Does the GitHub issue page post go with the issue page?** Default: yes. `github_labels.page` stays valid and is not read; labels still sync.
4. **Where does the spike decision get recorded?** Default: `compass evidence add --decision`, as decision 8 says.
5. **When does `dod-evidence-typed` judge a new issue?** Default: once every gate has passed.
6. **Does `devlog.md` stay?** Default: yes, until #351 replaces the stages.
7. **Do the slug and title guards stay?** They were added for the living spec. Default: yes; the release line and the board still print titles.

## References

- ayeo-io/compass-delivery#353 [Remove every required document except the acceptance criteria] and its parent, #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail].
- ADR-026 (ship-commit derives the living spec), ADR-050 (artifact status), ADR-051 (rendered blocks), ADR-064 (section checks), ADR-067 (word limits), ADR-090 (one session).
- `cli/compass_pkg/check_registry.py` (`REMOVED`), `cli/compass_pkg/removed_parts.py`.
