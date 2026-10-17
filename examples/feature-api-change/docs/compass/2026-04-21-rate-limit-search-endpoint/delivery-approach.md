# Delivery approach - rate-limit-search-endpoint

> **Issue:** Add per-client rate limiting to the public `/search` endpoint - it has no limit today and one client's bulk job degraded latency for everyone last week.
> **Assessed:** 2026-04-21 by D. Mensah (engineer) · **Revision:** 1
> **Reference shape:** feature

---

## 1. The four dimension assessment

| Dimension | Value | One-line justification |
|---|---|---|
| **Risk:** | contained | One endpoint and a new middleware. If the limit is wrong it returns a 429 too eagerly or too late - annoying, recoverable, observable; it does not corrupt or lose anything. |
| **Familiarity:** | brownfield-mapped | The request pipeline and middleware chain are documented and already have a test harness; this adds one well-understood link to a known chain. |
| **Size:** | standard | A new middleware, a config addition, and an endpoint wiring change - several files, a couple of design decisions (storage backend, window algorithm), about two days. |
| **Goal & role** | engineer | An engineer hardening a public endpoint after an incident review. No intent.md - the incident write-up is the intent. |

**Domain tags (`labels:`):** none - the limiter reads a client id that auth already resolved; it does not itself touch auth, payments, personal data, or migrations.

---

## 2. The composed candidate approach

Candidate approach: **feature**, with no deviations from its reference shape.

Candidate review dimensions: correctness, governance, traceability, regression, clarity, and security *scaled to risk* - `contained` means a focused security pass on the new reject path, not a full adversarial sweep.

---

## 3. Routing guardrails that fired

No routing guardrail fired. Candidate delivery approach stands.

`compass approach evaluate` confirmed it: no floor (risk is `contained` not `critical`; `labels` is empty so RP-FLOOR-003 does not match), no cap, no role rule (role is `engineer`). The delivery approach is the unmodified feature shape.

---

## 4. The final approach

### 4a. Per-stage weight

| Stage | Weight | Notes |
|---|---|---|
| Assess | Full | This document. |
| Define | Small feature set | Five scenarios - happy path, the over-limit reject, the retry-after contract, the window reset, per-client isolation. See `acceptance-criteria.md`. |
| Refine | Light pass | Two ambiguities surfaced and resolved; spec QA'd against itself and governance. See `requirements-review.md`. |
| Plan | Real `technical-design.md` | Two design decisions recorded (storage backend, window algorithm); governance check run. |
| Breakdown | Skipped (solo) | The work units share surface - see `technical-design.md` §4. Solo on the current branch. |
| Implement | Full TDD | Five scenarios, red→green→refactor each. Test surface scaled to `contained`. |
| Verify | Full - one gate | Six review dimensions, all evidenced in `verification-report.md`. |
| Ship | Full | Commit on the current branch, regression run, living docs updated, one devlog entry. |

### 4b. Gate set

- Number of gates: the feature gate at Verify (the feature's mid-implement check was a quick spec re-read against `technical-design.md` §4 - logged in `devlog.md`, no separate artifact).
- Review dimensions applied: correctness, governance, traceability, regression, clarity, security.
- Immovable gates added: verify.correctness, verify.governance, verify.traceability. `verify.regression` is part of feature's own shape. No `verify.claims` - no marketer in play.

### 4c. Multiagent orchestration

- Orchestration: solo
- Subtask count: n/a - Plan §4 found the three work units share the middleware surface; splitting them would create a merge conflict, not parallelism.
- Orchestrator agent: n/a (solo)

---

## 5. The de-scope ledger

| Stage / check | Action | Safe to skip / collapse because… |
|---|---|---|
| Breakdown | skipped | The three work units (middleware, endpoint wiring, config) all touch `rate_limit.py` or depend on it. They are not independent - disjoint code is one of the two independence tests and it fails. Solo is correct, not a shortcut. |
| Dedicated orchestrator agent | skipped | Standing feature de-scope: at solo/≤3 subtasks the lead builder integrates; a separate orchestrator is overhead. |

Note what is *not* in this ledger: refine is not skipped - a feature's spec is a feature set, and there was real ambiguity to resolve (`requirements-review.md`). The requirements review is *light*, never absent, on a feature.

---

## 6. Outstanding follow-ups

- [x] None outstanding. A feature runs its pipeline in order; it borrows no process weight from the front.

---

## 7. Human overrides

No human overrides. Delivery approach confirmed as composed.

---

## 8. Confirmation

- [x] Delivery approach presented to the invoker and confirmed.
- [x] Every dimension in §1 has a justification.
- [x] Every skipped stage in §5 has a "safe to skip because…" line.
- [x] Not a spike - no `.spike` marker needed.
- [x] `devlog.md` opened with the assess entry.

Next stage: **define** (`/compass:define`).
