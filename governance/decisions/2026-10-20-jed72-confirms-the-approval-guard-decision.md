# jed72-confirms-the-approval-guard-decision

## Decided by

jed72

## Date

2026-10-20

## Supersedes

`governance/decisions/2026-10-19-the-approval-guard-judges-words-not-text.md`

## Decision

jed72 confirms the decision of 2026-10-19 as written, with all six statements. The approval guard reads a simple Bash command as words and judges every other command by its whole text. It is defense in depth and not a hard boundary. A script that one call writes and another call runs stays an accepted limit. The broader word reader stays out of 7.0.0 and waits in ayeo-io/compass-delivery-record#247.

This entry replaces the sentence "jed72 has not yet confirmed it" in the earlier record, which an entry on `main` cannot change. Nothing else differs between the two.

## Why

The earlier record was written by compass:architect for jed72, who was away. jed72 has now read it and confirms it. The 7.0.0 release shipped the change (ayeo-io/compass#663) under that record.

## Evidence

- The earlier record, `governance/decisions/2026-10-19-the-approval-guard-judges-words-not-text.md`.
- Pull request ayeo-io/compass#663, merged on 2026-10-19, and the release v7.0.0 of 2026-10-20.
- jed72's confirmation in the 7.0.0 release session on 2026-10-20: "confirm the #663 decision record".
