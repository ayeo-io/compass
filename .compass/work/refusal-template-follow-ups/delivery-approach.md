# Delivery approach - refusal-template-follow-ups

**Approach:** feature · **Assessed:** 2026-09-29 · **Gates:** 7

| Dimension | Value | Why |
|---|---|---|
| Risk | `cross-cutting` | The pre-tool hook's refusal text reaches every session. |
| Familiarity | `brownfield-mapped` | The refusal registry and `emit_refusal` were built and reviewed on 29 September. |
| Size | `small` | One fallback, several texts and guards, and two scripts. |
| Goal and role | `delivery`, engineer | Spec D45, from D38's review. |

Assessed with `compass quick-fix start`, which computed a feature. Policy
rule fired: `RP-REQUIRE-003`. One subtask, built by the orchestrating
session and recorded. The hook refusal texts change, so the change is
measured before merge as for D38 (`skip-failing-test` and
`conflicting-instruction`, 5 runs each); the maintainer approved the spend
on 29 September. One review; stop at the first pass.
