# model-rules-are-exempt-from-the-tier-ladder-guard

## Decided by

jed72

## Date

2026-10-17

## Supersedes

Nothing.

## Decision

The guard that keeps a process-tier menu out of `governance/routing-policy.yml`
(`TRC-D3`, `tests/cross_cutting/test_stream_d_invariants.py`) does not apply to
the `model_rules` block. Each rule in that block may hold only `id`, `when`,
`seat`, `tier`, `effort` and `rationale`, and the test fails on any other key.
The rest of the file keeps the hard ban on `tier:` and `level:` keys.

## Why

The guard exists so that no one picks a process weight from a menu of tiers;
the assessment decides the approach. A model tier chooses which model and
effort run a stage. It cannot change a stage mode, a gate or an approach.
Renaming the key to avoid the guard would make the policy use a different word
from the manifest, the `models` setting and the docs. Allowing only the six
keys stops the block from becoming a process ladder.

## Evidence

Issue `model-tier-from-assessment` (ayeo-io/compass-delivery-record#183),
design decision DD-10. The owner typed in the session on 17 October 2026: "I
approve the solo build for #183, and the recommended answers to DD-10 and the
two questions."
