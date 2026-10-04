# Intent - first-hour

Rival products appear as codes R1 to R9; the maintainer holds the key.

> **Author:** jed72 · **Date:** 2026-08-26
> **Governance owner check:** consistent with `governance/strategies.md`.
> This intent document is the parent of six issues. Each issue's
> `manifest.yml` names the INT ids it traces to. It lives here, not under
> `.compass/work/`, because it is the first human-facing artifact under the
> `docs/compass/` convention that INT-3 introduces.

---

## Problem

A Claude Code user's first hour with Compass is worse than their first hour
with R1, even though Compass has the stronger mechanism underneath
(routing, evidence, traceability, CI). The plugin hook refuses code edits in
repos that have never opted in; nothing loads the operating contract into a
session; a feature run reads roughly three times the instruction prose; and
the docs still use retired names in places. Reviewers also have nowhere
obvious to read an issue's spec, design and verification report - they sit
in `.compass/work/` next to machine state.

## Desired outcome

Someone who installs Compass from the marketplace gets the same
frictionless first hour they would get from R1, and finds the
mechanism (routing, evidence, traceability, CI) already working underneath
it. Human-facing artifacts are where a reviewer would look for them.

## Success signals

- INT-1 A repo without `.compass/` is never blocked by the hook; the user
  sees nothing until they opt in.
- INT-2 The operating contract is present after every session start, clear
  and compact, without the model having to choose to load it; every command
  resolves its templates and governance from the plugin root.
- INT-3 Every artifact a human reviews (intent, acceptance criteria,
  technical design, distribution map, threat model, rollback plan,
  verification report, ADRs) lives under `docs/compass/`; `.compass/work/`
  holds only the manifest, evidence and markers.
- INT-4 A quick-fix issue reads one command and one skill and produces the
  manifest plus red/green evidence and nothing else; resident per-turn cost is
  at or under R1's (about 1k tokens).
- INT-5 A green cannot be recorded without a red on record for the same
  scenario; the hook checks a digested red record rather than an empty
  marker; fail-closed behaviour is the same for every python failure mode.
- INT-6 The public surface carries no retired vocabulary, no dead links, and
  no claim that contradicts the routing policy.
- INT-7 A written recommendation exists on which parts of R1's SDD
  controller loop transfer to the orchestrator/builder protocol.

## Constraints

- The routing engine, typed evidence and check semantics do not change
  shape; this is a product-layer fix, not a rewrite of the mechanism.
- Backward compatibility with 2.0 manifests holds (ADR-006).
- `.compass/work/` stays as the machine record; nothing that `compass check`
  reads moves out of it.
- Claude Code only. No cross-LLM work in this cycle.

## Non-goals

- Codex or any other runtime.
- New guardrail checks or gates (the number of guardrails stays at five).
- A third vocabulary rename. ADR-012 freezes the vocabulary before INT-6
  starts, and INT-6 removes the retired names once.

## Internal FAQ

**Why now?**
The comparison against R1 6.3.0 on 26 Aug 2026 found Compass ahead
on mechanism and behind on the first hour. The blockers are small relative
to the mechanism, and every week they stand costs adopters.

**What is in v1, and what is explicitly later?**
v1 is INT-1 to INT-6. INT-7 is a spike whose conclusion decides whether a
seventh issue exists. Merging skills beyond what INT-4 needs is later.

**How will we know it worked?**
A fresh marketplace install, in an unrelated repo, edits a file without
being blocked (INT-1). A quick fix in a Compass project completes with one
command read and under 10k tokens of framework prose (INT-4). A reviewer
opens `docs/compass/<issue>/` and finds everything they need (INT-3).

**What could make this fail?**
INT-3 is the one that changes the most code: two locations for one issue
means the manifest must carry artifact paths and every reader (check, next,
analyze, receipt, ship-commit, the hook's exemptions, the examples, CI
fixtures) must follow them. Doing INT-6 before INT-3 does the rename twice.
Doing INT-5 before INT-3 writes the red-record check against paths that are
about to move.

## Affected roles

- engineer - all issues.
- product-owner - INT-3, because the placement of human artifacts is a
  product decision, and the intent-fidelity check applies before the plan
  stage.

---

## Intent-fidelity check (filled before the plan stage)

- [x] Every success signal above maps to at least one scenario in each
  issue's `acceptance-criteria.md`.
- [x] No scenario contradicts a constraint, pursues a non-goal, or runs
  against a product strategy.
- [x] Checked by: jed72 on 2026-09-23.

**What this signature accepts.** Every signal maps to scenarios, and two
things fall short of what the intake asked for. jed72 accepted both on
2026-09-23.

- INT-4 asks for resident per-turn cost at or under R1's, about 1,000
  tokens. The issue that delivers and measures it records about 1,600. The
  rest of INT-4, one command and one skill and nothing else written, is
  delivered and verified.
- Two of the seven issues that trace to this intake, `hook-as-guest` and
  `evidence-gaps`, are still active, so their signals are served on paper
  rather than by a landed record.

The signal-by-signal mapping this rests on was written by the product owner
role at the verify stage of the issue `prose-breaks-the-writing-style`, and
is filed with that issue's evidence.
