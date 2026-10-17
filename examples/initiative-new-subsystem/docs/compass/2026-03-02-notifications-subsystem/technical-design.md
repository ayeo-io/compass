# Plan - notifications-subsystem

> **Stage:** plan · **Date:** 2026-03-07 · **Owning agent:** planner
> **Plan weight (from delivery-approach.md):** technical-design.md + distribution-map.md (initiative)

---

## 1. Approach

A new `src/notifications/` module tree with four parts: `dispatch.py` (turns an
event into a notification and sends it on), `store.py` (the durable store),
`preferences.py` (resolves whether a category reaches a user), and `api.py`
(the read/mark-read/update-preferences surface). One new table,
`migrations/0042_notifications.sql`, holds both notifications and per-user
preferences.

The build splits along the two scenario groups. **Subtask-1** owns dispatch +
store (group A): an event arrives, `dispatch.py` asks `preferences.py` whether
the category is allowed, and on yes writes through `store.py` with the
producer's idempotency key. **Subtask-2** owns preferences (group B):
`preferences.py` is a pure resolver - `(user, category) → deliver | suppress`,
with the security category hard-wired to `deliver`. The two subtasks share only
the migration (both read the table) and `api.py` (both add endpoints) - the
orchestrator owns that shared surface.

Order: the shared `migrations/0042` lands first as a foundation (both subtasks
branch from it), then the two subtasks run in parallel.

## 2. Design decisions (ADR-style)

### `DD-1` - Security override is a fixed category, not a per-notification flag

- **Context:** `TRC-006` / refine Q1 - mute must not be able to suppress
  security notifications. The mechanism had to be chosen.
- **Decision:** A fixed, closed `security` category. `preferences.py` resolves
  any `(user, "security")` query to `deliver` regardless of stored preference.
- **Alternatives considered:** A per-notification `overrides_mute` boolean -
  rejected: intent.md's pre-mortem named exactly this drift ("everything claims
  to be security"). A configurable override list - rejected as v1 over-build.
- **Consequences:** Adding a new must-not-miss category is a code change, not a
  config change. Accepted - it should be: the set of un-mutable things deserves
  a code review.
- **Governance tie:** `intent.md` pre-mortem; product strategy "make the safe
  path the easy path".

### `DD-2` - Idempotency key on the notification row, once-ever dedup

- **Context:** `TRC-002` / refine Q2 - a retried event must not double-deliver.
- **Decision:** The producer gives an idempotency key; `store.py` writes it
  to a unique-constrained column. A second write with the same key is a
  caught-and-logged no-op.
- **Alternatives considered:** A time-windowed dedup cache - rejected: v1 has
  no batching/digest concept (`intent.md` non-goal), so there is no window to
  scope to; once-ever is simpler and correct.
- **Consequences:** Producers must give a stable key. Documented in the
  dispatch contract; the API rejects a dispatch with no key rather than
  silently risking duplicates.
- **Governance tie:** engineering strategy `S3` (simplest thing that works).

### `DD-3` - Durability via write-before-deliver, not an in-memory queue

- **Context:** `TRC-003` / INT-2 - a worker restart must not lose a notification.
  intent.md's pre-mortem flagged "looks durable in dev, isn't under real
  restart" as the top technical risk.
- **Decision:** `dispatch.py` writes the notification to `store.py` (the table)
  *before* it is considered dispatched. Delivery marks a `delivered_at`; an
  undelivered row after restart is simply re-picked. The table is the queue.
- **Alternatives considered:** An in-memory or Redis queue with the table as a
  log - rejected: it reintroduces exactly the lose-on-restart window intent.md
  named as the failure mode.
- **Consequences:** Every notification is a table write before it is "sent" -
  a small latency cost, well inside `TRC-001`'s 5s bound. Worth it: durability is
  an intent.md constraint, not a nice-to-have.
- **Governance tie:** `intent.md` constraint (durable) and pre-mortem.

## 3. Governance check

| Area | Result | Evidence / note |
|---|---|---|
| Guardrails (`G1`-`G5` + project) | pass | `G1`/`G2`/`G3`: all six scenarios stated, and the requirements review closed before implement, each with a planned test and a `TRC-id`; `changed_files` will trace back. `G4`: every gate cleared with pasted evidence in `verification-report.md`. **`G5`: applies** - the issue `labels: [migrations]`; a human signs off `migrations/0042` before ship, recorded as a `human-approval` evidence entry in `manifest.yml`. The plan puts that sign-off into ship explicitly. |
| Method strategies (`S1`-`S4` + project) | followed | `S1` BDD, `S2` TDD apply per subtask. `S3` simplest-thing honoured in `DD-1`, `DD-2`, `DD-3`. No deviation. |
| Product strategies | followed | The plan delivers `intent.md`'s outcome - durable, tunable, security-protected in-app notifications - and stays inside the v1 cut. "Depth for existing users" honoured: category preferences over the existing event types, no breadth grab. |
| Voice & positioning strategies | n/a | No marketer in play for this issue - the launch is a separate later issue. `verify.claims` exists in the gate set but has no claims to check. |
| Routing policy | pass | The plan skips nothing `delivery-approach.md` kept - initiative's de-scope ledger is empty and the plan keeps it empty. RP-FLOOR-003 (the `migrations` floor) is honoured, not dodged: the migration is treated as the irreversible thing it is, with a forward+rollback review and a `G5` sign-off. RP-ROLE-002's Plan block was cleared before this file was written (`intent.md` intent-fidelity check, 2026-03-06). |

## 4. Work units

| Unit | Scenario group(s) it satisfies | Code surface it touches | Independent of |
|---|---|---|---|
| U0 | foundation - none directly | `migrations/0042_notifications.sql` | lands first; U1 and U2 branch from it |
| U1 | group A - `TRC-001`, `TRC-002`, `TRC-003` | `src/notifications/dispatch.py`, `src/notifications/store.py`, `src/notifications/api.py` (read/mark-read endpoints) | independent of U2 - calls `preferences.py` through a narrow interface but does not implement it |
| U2 | group B - `TRC-004`, `TRC-005`, `TRC-006` | `src/notifications/preferences.py`, `src/notifications/api.py` (preference endpoints) | independent of U1 - a pure resolver U1 calls; shares only `api.py` and the migration |

**Parallelism assessment:** U1 and U2 are genuinely independent - disjoint
scenario groups (A vs B) and *near*-disjoint code: their only overlap is
`api.py` (different endpoints) and `migrations/0042` (the shared U0 foundation,
landed first). That overlap is real but small and bounded, which is precisely
the orchestrator's job to watch → **multiagent, 2 subtasks**. `distribution-map.md`
written.

---

## Gate

- [x] Every scenario in `acceptance-criteria.md` is covered by a work unit - U1 covers `TRC-001`…003, U2 covers `TRC-004`…006, U0 is the shared foundation.
- [x] Governance check passes - every guardrail clears with evidence; `G5`'s ship sign-off is part of ship; no strategy deviation to record.
- [x] Parallel work is possible - `distribution-map.md` written next.

Next stage: **breakdown** (`/compass:breakdown`) - runs `scripts/multiagent.sh` with the distribution map.
