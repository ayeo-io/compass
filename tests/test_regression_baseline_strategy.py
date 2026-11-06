"""The regression-baseline strategy (`S6`): a named, SOFT strategy that makes
"green baseline before, re-run after, on shared/critical surface" the
assessed-and-prompted default at verify. Additive only - no new guardrail, no
new gate, never a ship blocker (ADR-002, ADR-006).
"""
from __future__ import annotations

import json

import yaml


def test_s6_registered_in_strategies_md(framework_root):
    """`TRC-R10`-1: strategies.md registers regression-baseline as a soft `S6`."""
    text = (framework_root / "governance" / "strategies.md").read_text()
    assert "S6" in text and ("regression-baseline" in text or "Regression baseline" in text), text[:200]
    low = text.lower()
    assert "soft" in low or "assessed" in low
    assert "verify.regression" in text
    assert "baseline" in low and "before" in low and "after" in low
    # explicitly additive
    assert ("no guardrail" in low or "no new gate" in low)
    assert ("does not block land" in low or "never" in low)


def test_routing_strategy_surfaces_on_touches_no_gate_change(run_cli, make_task):
    """`TRC-R10-2`: approach evaluate surfaces regression-baseline as
    applicable for a cross-cutting issue - without adding or changing a
    gate."""
    body = {"task": "rb", "created": "2026-06-22",
            "assessment": {"risk": "cross-cutting",
                         "familiarity": "brownfield-mapped", "size": "large",
                         "intent": "delivery"}}
    make_task("rb", body)
    r = run_cli("approach", "evaluate", "--issue", "rb", "--json")
    assert r.returncode == 0, r
    data = json.loads(r.stdout)
    applicable = " ".join(str(s) for s in data.get("applicable_strategies", []))
    assert "regression-baseline" in applicable, data
    # no gate named for the strategy; the soft strategy reuses verify.regression
    assert not any("regression-baseline" in g for g in data["gates"]), data
    assert "verify.regression" in data["gates"], data


def test_routing_strategy_absent_on_contained_task(run_cli, make_task):
    """The advisory only fires on shared/critical surface."""
    body = {"task": "rb2", "created": "2026-06-22",
            "assessment": {"risk": "contained",
                         "familiarity": "brownfield-mapped", "size": "small",
                         "intent": "delivery"}}
    make_task("rb2", body)
    r = run_cli("approach", "evaluate", "--issue", "rb2", "--json")
    data = json.loads(r.stdout)
    applicable = " ".join(str(s) for s in data.get("applicable_strategies", []))
    assert "regression-baseline" not in applicable, data


def test_verify_expects_baseline_and_postrun_as_judgement(framework_root):
    """`TRC-R10`-3: the strategy describes a pre+post test-run expectation on
    verify.regression, assessed as judgement (a strategy note)."""
    text = (framework_root / "governance" / "strategies.md").read_text().lower()
    assert "verify.regression" in text
    assert "test-run" in text
    assert "before" in text and "after" in text


def test_build_prompts_baseline_before_change(framework_root):
    """`TRC-R10-4`: the build stage of the go command (the implement command
    until ADR-092) prompts to capture the baseline up front."""
    text = (framework_root / "commands" / "go.md").read_text().lower()
    assert "baseline" in text
    assert "regression-baseline" in text or "regression baseline" in text


def test_absent_baseline_does_not_block_land(framework_root):
    """`TRC-R10-5`: no guardrails.yml check enforces a baseline - its absence
    cannot fail compass check or block ship (soft strategy)."""
    g = yaml.safe_load((framework_root / "governance" / "guardrails.yml").read_text())
    checks = g.get("checks") or {}
    assert not any("regression-baseline" in str(k) or "baseline" in str(k)
                   for k in checks), checks


def test_no_new_guardrail_or_gate_added(framework_root):
    """`TRC-R10`-6: adding `S6` introduces no sixth guardrail and no new gate;
    verify.regression's accepted types are unchanged ([test-run]); guardrails.yml
    does not define the strategy (it is a strategy, not a guardrail)."""
    gov = framework_root / "governance"
    # the five guardrails live in guardrails.md - still `G1`..`G5`, no G6
    md = (gov / "guardrails.md").read_text()
    for gid in ("G1", "G2", "G3", "G4", "G5"):
        assert gid in md, gid
    assert "G6" not in md, "a sixth guardrail must not have been added"
    # verify.regression accepted types unchanged
    g = yaml.safe_load((gov / "guardrails.yml").read_text())
    assert g["gate_evidence_requirements"]["verify.regression"] == ["test-run"]
    # guardrails.yml does not define the strategy (it is soft, lives in strategies.md)
    assert "regression-baseline" not in (gov / "guardrails.yml").read_text()
