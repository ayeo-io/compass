# Guardrails

Guardrails are the few hard limits. They are **checkable** (cleared with
evidence, never a claim), **blocking** (a failed guardrail stops the work),
and **sticky** (slow to add, slower to remove). A guardrail always beats a
strategy.

This file ships with five **default guardrails** active. A project can *add*
guardrails below them; it can also remove one, and `compass check` reports
the omission. `/compass:init` copies this file into the project so the team
can extend it.

**This document explains; `guardrails.yml` enforces.** The companion
`governance/guardrails.yml` is the machine-readable authority for *how each
guardrail is checked* - it names the mechanical check behind every guardrail,
and `compass check` runs those checks against an issue's `manifest.yml` and
`evidence/`. Where this prose and that file could be read to differ on a
mechanical detail, `guardrails.yml` wins.

---

## The default guardrails

These five ship on. They are the floor under every delivery approach,
including the lightest.

### Tested before it lands (`G1`)

**No code reaches `main` unless it traces to a declared test and a green test
run is on record.**

- Compass checks that both exist and line up. It does not observe the declared
  test running - see `docs/safety-contract.md` for what a test-run record does
  and does not establish.
- Checked at Verify and again at ship time. `verification-report.md` carries
  the recorded run.

### Acceptance defined before it is built (`G2`)

**No code is written that no stated, checkable acceptance criterion
describes.**

- The criterion exists before the code does.
- The same criterion is the acceptance check at Verify.

### Traceability holds (`G3`)

**Every change keeps two chains intact, continuously - not reconstructed at
the end.**

- **code → acceptance criterion → intent** - every line traces to a criterion;
  every criterion traces to a stated intent.
- **public claim → backing criterion** - every public or marketing claim
  traces to a criterion that, when checked, backs it.
- A broken chain is a failed guardrail.

### Evidence, not assertion (`G4`)

**A guardrail is cleared with artifacts and command output, never with a
claim.**

- "The tests pass" is the recorded run, not the sentence. "It works" clears
  nothing.
- This guardrail is *about* the others: it defines what "cleared" means.

### A human signs off on the irreversible (`G5`)

**A change that cannot be cleanly undone gets an explicit human checkpoint
before it lands.**

- Applies to anything that can lose data, move money, or breach auth or
  privacy.
- No delivery approach removes this.

The routing policy (`routing-policy.md`) is what makes sure such changes are
*routed* to where the checkpoint happens; this guardrail is what makes the
checkpoint non-negotiable.

---

## Project guardrails

<!-- Add guardrails specific to this project here. Add slowly. A guardrail
     must be HARD (a real must-never), CHECKABLE (you can produce evidence it
     held), and BLOCKING (failing it stops the work). If it is none of those,
     it is a strategy - put it in strategies.md instead.

     Good project guardrails are usually concrete, measurable floors:
       - "Test coverage does not drop below {{N}}%."  (checkable)
       - "No secret or credential is ever committed."  (checkable)
       - "Every migration has a tested rollback."  (checkable)
       - "p95 API latency stays under {{N}}ms; a >10% regression blocks shipping."
     Leave this section empty rather than padding it. Empty is a valid state. -->

_(none yet - the shipped default guardrails apply as-is)_

---

## How guardrails are enforced

- **`compass check`** runs the checks each guardrail names in `guardrails.yml`
  against the issue's `manifest.yml` and `evidence/`, and reports pass or fail
  with specifics. It also fails an issue whose `assessment:` holds a key
  `schemas/manifest.schema.json` does not allow, which the release's `issue
  lint` would refuse.
- **The pre-tool hook** enforces red-before-green in service of `G1`. It is
  approach-aware and does not block on a spike.
- **The `verifier` and `reviewer` agents** at Verify, for the parts that remain
  judgement. `verification-report.md` records each with its evidence.
- **`compass approach evaluate`** at Assess applies the routing rules
  deterministically - see `routing-policy.md` and `routing-policy.yml`.

A guardrail with no way to produce evidence is not a guardrail yet - it is a
strategy that has not been made checkable. If you cannot give it a named check
in `guardrails.yml`, it belongs in `strategies.md`.

**The integrity rule - a declared check must be implemented.**

- `compass policy lint` rejects a guardrail referencing a check the CLI does
  not implement.
- `compass check` fails, rather than warns, if it meets one at run time.
- Adding a project guardrail with a new check means adding that check's
  implementation to the CLI (`CHECK_FNS`) in the same change.

Why it is enforced rather than warned about:
`governance/strategies-rationale.md`, under "The integrity rule".
