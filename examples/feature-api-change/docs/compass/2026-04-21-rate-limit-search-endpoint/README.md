# rate-limit-search-endpoint

<!-- compass:render header -->
**`rate-limit-search-endpoint`** - regular - done (completed) - stage done - gates 6/6
Owner: not recorded - Created: 2026-04-21 - Completed: 2026-08-04
To see this issue across the board, run `compass board render`.
<!-- /compass:render -->

<!-- compass:render ask -->
**Issue**

Add per-client rate limiting to the public `/search` endpoint - it has no limit today and one client's bulk job degraded latency for everyone last week.

**Scenarios**

- `TRC-001` - Requests under the limit pass through unchanged
- `TRC-002` - The request over the limit is rejected with 429
- `TRC-003` - A 429 response tells the client when to retry
- `TRC-004` - The window resets and the client can call again
- `TRC-005` - Two clients have independent limits
<!-- /compass:render -->

<!-- compass:render decision-required -->
No decision required. Nothing is awaiting approval.
<!-- /compass:render -->

<!-- compass:render acceptance -->
Acceptance: 1 of 5 scenarios passed

- `TRC-001` - Requests under the limit pass through unchanged - passed
- `TRC-002` - The request over the limit is rejected with 429 - not yet passed
- `TRC-003` - A 429 response tells the client when to retry - not yet passed
- `TRC-004` - The window resets and the client can call again - not yet passed
- `TRC-005` - Two clients have independent limits - not yet passed
<!-- /compass:render -->

<!-- compass:render related -->
None
<!-- /compass:render -->

<!-- compass:render decisions -->
- `DD-1` - Counter storage backend
- `DD-2` - Fixed window, fail-closed on unknown client
<!-- /compass:render -->

<!-- compass:render artifacts -->
Documents: 5 registered, 0 approved

| Document | Status | Approved by | Why it exists |
|---|---|---|---|
| [acceptance-criteria](acceptance-criteria.md) | draft | - | found on disk when the documents were relocated |
| [delivery-approach](delivery-approach.md) | draft | - | found on disk when the documents were relocated |
| [requirements-review](requirements-review.md) | draft | - | found on disk when the documents were relocated |
| [technical-design](technical-design.md) | draft | - | found on disk when the documents were relocated |
| [verification-report](verification-report.md) | draft | - | found on disk when the documents were relocated |
<!-- /compass:render -->

<!-- compass:render traceability -->
```mermaid
flowchart LR
  classDef open stroke-dasharray: 4 4
  i_INT_1["INT-1"] ==> s_TRC_001["TRC-001"]
  s_TRC_001 ==> t_TRC_001_tests_api_test_rate_limit_py__test_under_limit_passes["tests/api/test_rate_limit.py::test_under_limit_passes"]
  t_TRC_001_tests_api_test_rate_limit_py__test_under_limit_passes ==> e_TRC_001_green_TRC_001_json["green-TRC-001.json"]
  i_INT_1["INT-1"] ==> s_TRC_002["TRC-002"]:::open
  s_TRC_002 ==> t_TRC_002_tests_api_test_rate_limit_py__test_over_limit_returns_429["tests/api/test_rate_limit.py::test_over_limit_returns_429"]
  i_INT_1["INT-1"] ==> s_TRC_004["TRC-004"]:::open
  s_TRC_004 ==> t_TRC_004_tests_api_test_rate_limit_py__test_window_resets["tests/api/test_rate_limit.py::test_window_resets"]
  i_INT_1["INT-1"] ==> s_TRC_005["TRC-005"]:::open
  s_TRC_005 ==> t_TRC_005_tests_api_test_rate_limit_py__test_per_client_isolation["tests/api/test_rate_limit.py::test_per_client_isolation"]
  i_INT_2["INT-2"] ==> s_TRC_003["TRC-003"]:::open
  s_TRC_003 ==> t_TRC_003_tests_api_test_rate_limit_py__test_429_includes_retry_after["tests/api/test_rate_limit.py::test_429_includes_retry_after"]
```
<!-- /compass:render -->

<!-- compass:render deliberately-omitted -->
Nothing recorded as omitted.
<!-- /compass:render -->

<!-- compass:render follow-ups -->
No follow-ups recorded.
<!-- /compass:render -->
