---
id: ADR-003
title: Inline Tag Dod Syntax
status: accepted
date: 2026-05-23
supersedes: ''
superseded_by: ''
---

## Context

The Definition of Done (DoD) in `verification-report.md` consisted of simple
checkbox lines (`- [ ] description`).  A human ticking the box was the only
way to mark a line done.  This meant "the test passes" could clear a DoD item
the same way as "branch protection is configured" - no distinction between
automated evidence and a human assertion.  Guardrail `G4` (evidence, not
assertion) was eroding.

The framework needed a way for an unchecked DoD line to reference typed
evidence or an explicit follow-up, so the check is mechanical rather than
relying on the human remembering to tick after actually doing the work.

## Decision

Two inline tag forms on the DoD line itself:

```
- [ ] (evidence: EV-<id>) <description>   → passes if EV-<id> is in manifest.yml.evidence with an accepted type
- [ ] (follow-up: FU-<id>) <description>  → passes if FU-<id> is in manifest.yml.follow_ups with status: outstanding
- [ ] <description>                        → bare unchecked - fails compass check
- [x] <description>                        → human ticked - passes
```

`compass check` parses each line under the DoD heading with a regex.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Free-text `EV-A1` anywhere on line | Minimal typing | False-positive risk on prose mentioning evidence ids |
| Markdown footnote `[^EV-A1]` | Familiar syntax | Visually noisy; some renderers mangle footnotes |
| Separate JSON sidecar mapping line → evidence | Decouples content from structure | Asks humans to maintain a parallel structure |

## Consequences

**Positive:**
- DoD clearance is mechanical: `compass check` can check it without human interpretation.
- `G4` (evidence, not assertion) is enforced at the DoD level.
- Follow-up deferral is explicit and typed, not a narrative workaround.
<!-- absorbed: "- The `templates/verification-report.md` must be updated to teach the syntax." -->

**Negative:**
- Learning curve: contributors must learn the `(evidence: ...)` syntax.

**Neutral / follow-on:**
- Mistyped tags fail loudly, which is the desired behavior.

## References

- The requirements review, where the Definition-of-Done evidence syntax was settled
- The technical design's inline-tag design decision
- Guardrail `G4` (evidence, not assertion)
