# Requirements review - rate-limit-search-endpoint

> **Stage:** refine · **Date:** 2026-04-22 · **Owning agent:** spec-author
> **Requirements review weight (from delivery-approach.md):** light pass

---

## Self-QA of the spec

- Every scenario has an observable `Then` - checked. `TRC-002`'s "the search query
  is not executed" is observable via the query-count assertion in the harness,
  not a wish.
- No two scenarios contradict each other. `TRC-001` and `TRC-002` share a Given
  ("limit is 100/min") and differ only in the client's prior count - that is a
  boundary pair, not a contradiction.
- One untestable phrase found and fixed: an earlier draft of `TRC-003` said the
  response "helps the client back off". Rewritten to the concrete `Retry-After`
  header contract.

## Governance QA of the spec

- No scenario crosses a guardrail. The limiter rejects with a 429 - it does not
  drop, delay silently, or lose a request, so nothing here is irreversible and
  `G5` does not apply.
- No scenario runs against a strategy. `S1` (BDD) and `S2` (TDD) apply normally.
  The `simplest-thing` strategy (`S3`) is honoured: the spec describes a fixed
  window, not a token bucket - see Q1.

---

## Ambiguity ledger

### Q1 - Which window algorithm does the spec assume?

- **Question:** `TRC-004` says "the window rolls over". A fixed window and a
  sliding window both "roll over" but behave differently at the boundary - the
  spec must commit to one or `TRC-004` is not testable.
- **Resolution:** Fixed window. The incident did not involve boundary-burst
  abuse, and a fixed window is simpler to reason about and to test. `TRC-004`'s
  Given was tightened to "rejected at the **end** of a window" to make the
  fixed-window boundary explicit.
- **Decided by:** D. Mensah (engineer), confirmed against the incident write-up.
- **Governance reference:** engineering strategy `S3` - simplest thing that works;
  a sliding window would be solving a problem the incident did not present.
- **Spec change:** `TRC-004` Given edited.
- **Status:** resolved

### Q2 - What happens to a request with no resolvable client id?

- **Question:** The limiter keys on a client id resolved upstream by auth. The
  spec did not say what happens if that id is absent (an unauthenticated path,
  or a misconfiguration).
- **Resolution:** `/search` is behind auth, so a missing client id is a
  misconfiguration, not a user-facing case - it should fail closed (reject)
  rather than fall through unlimited. Handled by a config default
  (`rate_limit.unknown_client = reject`) rather than a new scenario, because it
  is an operational guard, not a behaviour a user experiences.
- **Decided by:** D. Mensah (engineer).
- **Governance reference:** n/a - operational hardening, not a strategy call.
- **Spec change:** no spec change, clarification only. Recorded in `technical-design.md` `DD-2`.
- **Status:** resolved

---

## Gate

- [x] No ambiguity left `open` - Q1 and Q2 are both resolved.
- [x] `acceptance-criteria.md` updated to reflect every resolution (TRC-004 Given tightened; Q2 needed no scenario).
- [x] Non-engineering roles in play have reviewed - n/a, this is an engineer-only issue.

### Definition of Ready

- [x] **Problem traces up** - every scenario serves INT-1 or INT-2, both drawn
      from the incident write-up. No orphaned scenario.
- [x] **Behaviour is Given/When/Then** - all five scenarios have an observable
      `Then`; the one wish ("helps the client back off") was rewritten during
      self-QA (above).
- [x] **Traceability ids assigned** - `TRC-001`…`TRC-005`, all present in
      `acceptance-criteria.md` and `manifest.yml`.
- [x] **Affected surface named** - `delivery-approach.md` §4 and the upcoming `technical-design.md` §4
      name the middleware, the endpoint wiring, and the config addition.
- [x] **No open questions** - the ambiguity ledger above is fully resolved.
- [x] **Delivery approach still fits** - nothing in refine changed the size or
      risk. Feature still fits; no re-assessment needed.

Next stage: **plan** (`/compass:plan`).
