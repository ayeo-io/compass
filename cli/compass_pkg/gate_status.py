# compass_pkg.gate_status - whether an issue's gates have passed
"""The one answer to "has every gate passed?", and "which have not?".

A gate a release removed (`stable_ids.REMOVED_GATE_IDS`, such as `verify.analyze`,
removed in 9.0.0 by ADR-091) owes nothing. An issue made before the release can
still list it as pending, and it must not hold the issue back. Every reader that
waits for every gate asks here, so none of them waits for a removed gate while
the landing goes on without it:

- the landing (`manifest._unmet_gates`) and its stale-green refusal;
- `evidence-matches-tree`;
- `compass next`;
- `dod-evidence-typed`.
"""
# DEPENDENCY: compass_pkg.stable_ids only, so every module can import it.
from __future__ import annotations

from compass_pkg.stable_ids import REMOVED_GATE_IDS


def live_gates(task):
    """The issue's gate entries, leaving out a gate a release removed."""
    gates = task.get("gates") if isinstance(task, dict) else None
    return [g for g in gates if isinstance(g, dict) and g.get("id") not in REMOVED_GATE_IDS] \
        if isinstance(gates, list) else []


def unmet_gates(task):
    """The ids of the live gates that have not passed, in order."""
    return [g.get("id", "?") for g in live_gates(task) if g.get("status") != "pass"]


def all_gates_passed(task):
    """True when the issue has a live gate and every live gate passed."""
    gates = live_gates(task)
    return bool(gates) and all(g.get("status") == "pass" for g in gates)
