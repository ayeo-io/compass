"""A gap in the checkpoint table waits; a wrong route key is refused.

A policy with no `autonomy_checkpoints:` table waits at every hand-off the
route runs. A table that left out one value, or one route under a value,
gave that case no checkpoints, so a session never waited: the opposite of
leaving the whole table out. And a misspelt route key, or a retired name
beside its current one, was accepted silently (issue #330).

Scenario id: CT-1 (issue `checkpoint-table-gaps`).

The table is the 8.x one, read over the 8.0.4 governance copy. Since 9.0.0
the shipped default's path issue takes its checkpoints from its evidence, not
from this table (ADR-092 open question 7), and the default names only the
spike and the path, so a regular approach and its retired name are absent.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import compat_baseline as cb  # noqa: E402
from compass_pkg.policy import checkpoint_table_errors  # noqa: E402
from compass_pkg.routing import evaluate_route  # noqa: E402

FEATURE = {"risk": "contained", "familiarity": "brownfield-mapped",
           "size": "medium", "goal": "delivery", "role": "engineer",
           "labels": []}
EVERY = ["assess", "define", "refine", "plan"]


def _policy():
    # A new copy on each call, so a test can change it.
    return cb.policy_8_0_4()


def test_ct_1_a_missing_route_waits_at_every_hand_off():
    policy = _policy()
    del policy["autonomy_checkpoints"]["balanced"]["regular"]
    assert evaluate_route(FEATURE, policy, "balanced")["checkpoints"] == EVERY


def test_ct_1_a_missing_value_waits_at_every_hand_off():
    policy = _policy()
    del policy["autonomy_checkpoints"]["autonomous"]
    assert evaluate_route(FEATURE, policy, "autonomous")["checkpoints"] == EVERY


def test_ct_1_a_listed_empty_route_still_never_waits():
    assert evaluate_route(FEATURE, _policy(), "autonomous")["checkpoints"] == []


def test_ct_1_a_misspelt_route_key_is_refused():
    policy = _policy()
    policy["autonomy_checkpoints"]["balanced"]["feeture"] = ["plan"]
    errors = checkpoint_table_errors(policy)
    assert any("feeture" in e for e in errors), errors


def test_ct_1_a_route_named_twice_is_refused():
    policy = _policy()
    policy["autonomy_checkpoints"]["balanced"]["standard"] = ["plan"]
    errors = checkpoint_table_errors(policy)
    assert any("standard" in e and "regular" in e for e in errors), errors
