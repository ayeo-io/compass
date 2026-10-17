# Plan - rate-limit-search-endpoint

> **Stage:** plan · **Date:** 2026-04-23 · **Owning agent:** planner
> **Plan weight (from delivery-approach.md):** real technical-design.md (no distribution-map - solo delivery approach)

---

## 1. Approach

Add a `RateLimitMiddleware` to the existing request pipeline, positioned after
the auth middleware (so the client id is already resolved) and before the
endpoint handler. The middleware reads a per-client request count for the current
fixed window from a shared store, compares it to the configured limit, and
either passes the request through (incrementing the count) or short-circuits
with a 429 carrying a `Retry-After` header.

Order of work: the middleware and its store come first (TRC-001…`TRC-005` all
depend on it), then the endpoint wiring on `/search`, then the config keys. The
five scenarios are built one at a time, red→green→refactor, in the order they
appear in `acceptance-criteria.md` - `TRC-001` establishes the pass-through path,
`TRC-002` the reject path, and the rest layer on.

## 2. Design decisions (ADR-style)

### `DD-1` - Counter storage backend

- **Context:** The window counts must be shared across API workers, or each
  worker would enforce its own fraction of the limit and the real limit would
  be N times higher than configured.
- **Decision:** Use the Redis instance the platform already runs, with a key
  per `(client_id, window)` and a TTL equal to the window length so expired
  windows clean themselves up.
- **Alternatives considered:** (a) In-process counters - rejected, does not
  survive multiple workers, which is the whole failure the incident showed.
  (b) A new dedicated datastore - rejected as disproportionate; Redis is
  already a dependency and already used for sessions.
- **Consequences:** Commits us to Redis being available for `/search` to
  enforce limits; if Redis is down the middleware fails open (logged) so search
  stays up - degraded enforcement beats a downed endpoint. Recorded so it is a
  decision, not a surprise.
- **Governance tie:** engineering strategy `S3` (simplest thing that works) -
  reuse the running dependency rather than add one.

### `DD-2` - Fixed window, fail-closed on unknown client

- **Context:** refine Q1 settled the window algorithm (fixed); refine Q2
  asked what happens with no resolvable client id.
- **Decision:** Fixed window keyed on the minute boundary. A request with no
  resolvable client id is rejected (`rate_limit.unknown_client = reject`) -
  `/search` is behind auth so this can only be a misconfiguration, and failing
  closed is the safe direction.
- **Alternatives considered:** Sliding window - rejected in refine Q1 as
  solving a problem the incident did not present. Fall-through-unlimited for
  unknown clients - rejected: it is an unprotected path in the protection
  being added.
- **Consequences:** Boundary bursts (two windows' worth of requests across a
  minute boundary) are possible and accepted; if that ever becomes a real abuse
  vector it is a follow-up issue for a sliding window, not a hidden assumption.
- **Governance tie:** engineering strategy `S3`; and the fail-closed default
  follows the rule "do not add a protection with a gap in it".

## 3. Governance check

| Area | Result | Evidence / note |
|---|---|---|
| Guardrails (`G1`-`G5` + project) | pass | `G2`: all five acceptance scenarios stated before implement (`acceptance-criteria.md`, refine-complete). `G1`/`G3`: each scenario has a planned test and a traceability id; `changed_files` will trace back to them. `G5`: not applicable - the change touches no auth/payments/personal-data/migrations surface (the limiter *reads* an already-resolved client id, it does not change auth). |
| Method strategies (`S1`-`S4` + project) | followed | `S1` BDD and `S2` TDD apply as the default. `S3` simplest-thing honoured in `DD-1` and `DD-2`. No deviation. |
| Product strategies | n/a | No product owner in play; no `intent.md`. |
| Voice & positioning strategies | n/a | No marketer in play. |
| Routing policy | pass | The design skips nothing `delivery-approach.md` kept. Breakdown is skipped because §4 finds the units share surface - that matches `delivery-approach.md` §5, it does not contradict it. No floor was due and none is dodged. |

## 4. Work units

| Unit | Scenario group(s) it satisfies | Code surface it touches | Independent of |
|---|---|---|---|
| U1 | group A - `TRC-001`…`TRC-005` | `src/api/middleware/rate_limit.py` (new) | nothing - U2 and U3 both depend on it |
| U2 | group A - `TRC-001`, `TRC-002` | `src/api/routes/search.py` (wire the middleware in) | shares surface with U1 - needs U1's middleware to exist |
| U3 | group A - `TRC-002`, `TRC-004` | `src/api/config.py` (limit, window, unknown-client default) | shares surface with U1 - the middleware reads these keys |

**Parallelism assessment:** all three units converge on `rate_limit.py` - U2
imports it, U3 is read by it. Disjoint code is one of the two independence
tests and it fails. Splitting into worktrees would create a merge
conflict, not parallelism → **solo**. No `distribution-map.md` written.

---

## Gate

- [x] Every scenario in `acceptance-criteria.md` is covered by a work unit (U1 covers all five; U2 and U3 add the wiring and config the middleware needs).
- [x] Governance check passes - every guardrail clears with evidence; no strategy deviation to record.
- [x] No parallel work possible - the units share surface, so no `distribution-map.md`. Orchestration confirmed solo.

Next stage: **implement** (`/compass:implement`) - straight to implement, the delivery approach is solo.
