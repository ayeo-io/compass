# Fixture: the same words in their ordinary English sense

<!-- Input for tests/test_terminology.py. Nothing in this file may be
     flagged: every line reuses a banned word in an ordinary sense the
     patterns must tolerate. A hit here means a pattern is too broad. -->

First frame the problem, then take a well-worn route to work.
The courier offers express delivery, and the landing gear folds away.
While reading the file we found the estimate off by an order of magnitude.
Machine state lives in manifest.yml; the current-task pointer names it; pass
--issue to override, and the issue-slug and <task-id> forms stay machine state.
The `<issue-slug>` directory stays machine state during the transition.
The issue types are feature, bug and task; set the issue type to task for upkeep.
Please specify the format, clarify your intent, and distribute the load evenly.
Planes land safely when checklists hold, and boats land their catch.
The change touches the parser but nothing else.
One machine form of the follow-up ledger stays legal until the CLI verbs
rename: the data team backfilled last month's metrics overnight.
Code spans and fenced blocks are scanned (ADR-015), so only live spellings
belong here: run `/compass:assess`, `compass approach evaluate`,
open `delivery-approach.md`, `intent.md`, or `acceptance-criteria.md`, settle
what is outstanding with `compass follow-up resolve`, and read the
`assessment:` block or the `labels:` list in the manifest.

```yaml
# A fenced block is scanned like any other line now. These are the live keys.
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: small
delivery_approach: quick-fix
follow_ups: []
```
When an intent document exists, invoke the product-owner agent by its machine name.
We frame the problem before we start; planes land when the tower clears
them, and the driver computed a route home without any of this.
The navigation app composed a scenic detour, not that this matters here.

The seam of a garment runs down the sleeve, and a coal seam is a geological
term. A tailor checks every seam before pressing.

We triage the backlog every Monday, sorting between issues by urgency - which is the ordinary verb and stays legal, because it is what `compass flow` does rather than what one stage of the pipeline does.

The designer sketched a wireframe on paper before touching Figma. That is the ordinary noun and is fine.

We wrote the product requirements down before starting.

The spine of the book was cracked, and she felt a shiver run down her spine. A
hardback's spine carries the title.

## ADR-023 - the ordinary senses these bans must NOT catch

`upstream` and `downstream` are ordinary English and share five letters with the
retired unit-of-work word. The pattern's lookbehind is the only thing keeping
them out, so they are pinned here: 40 such uses were counted in scanned prose
when the ban was written, and every one of them is legitimate.

The intake sits upstream of the acceptance criteria.
Downstream agents read the artifact the stage before them wrote.
Pay the upstream cost once rather than the downstream cost repeatedly.
An upstream role hands work to the downstream one.
