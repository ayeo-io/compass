"""The safety-critical spike-vs-floor routing-conflict cases.

When the candidate delivery approach is spike (goal=exploration) and a
routing-policy floor would raise it to a delivery approach (because the
work touches risky surface), the evaluator must refuse - silent promotion
of a spike into delivery would break the guarantee that exploration cannot
become delivery. The honest output is a routing conflict that needs a
reassessment.
"""
from __future__ import annotations

import json

import pytest


def _readings_to_args(d):
    out = []
    for k, v in d.items():
        if isinstance(v, list):
            out.extend(["--assessment", f"{k}=" + ",".join(v)])
        else:
            out.extend(["--assessment", f"{k}={v}"])
    return out


@pytest.mark.parametrize("domain", ["auth", "payments", "personal-data", "migrations"])
def test_spike_conflict_on_g5_domains(run_cli, domain):
    """Spike + a label on auth/payments/personal-data/migrations => routing
    conflict (exit non-zero, message says so)."""
    r = run_cli("approach", "evaluate", "--json",
                *_readings_to_args({"risk": "contained",
                                    "familiarity": "brownfield-mapped",
                                    "size": "small",
                                    "intent": "exploration",
                                    "labels": [domain]}))
    assert r.returncode != 0, f"expected conflict for {domain}, got success: {r}"
    combined = (r.stdout + r.stderr).lower()
    assert "routing conflict" in combined, r
    # the message should mention that the spike candidate would be promoted
    # so a human understands what to do next
    assert "exploration" in combined or "spike" in combined, r


def test_spike_conflict_on_critical_blast_radius(run_cli):
    """Spike + critical risk => the critical-floor would raise the
    delivery approach to initiative. That is exactly the unsafe-promotion
    case."""
    r = run_cli("approach", "evaluate", "--json",
                *_readings_to_args({"risk": "critical",
                                    "familiarity": "brownfield-mapped",
                                    "size": "small",
                                    "intent": "exploration"}))
    assert r.returncode != 0, r
    assert "routing conflict" in (r.stdout + r.stderr).lower(), r


def test_safe_exploration_still_routes_to_spike(run_cli):
    """Exploration on safe surface still routes to Spike - the safety
    mechanism does not over-fire."""
    r = run_cli("approach", "evaluate", "--json",
                *_readings_to_args({"risk": "contained",
                                    "familiarity": "brownfield-mapped",
                                    "size": "small",
                                    "intent": "exploration",
                                    "labels": []}))
    assert r.returncode == 0, r
    data = json.loads(r.stdout)
    assert data["delivery_approach"] == "spike"
    assert data["candidate_route"] == "spike"


def test_spike_conflict_message_actionable(run_cli):
    """The conflict message must tell the user what to do next - reassess."""
    r = run_cli("approach", "evaluate", "--json",
                *_readings_to_args({"risk": "contained",
                                    "familiarity": "brownfield-mapped",
                                    "size": "small",
                                    "intent": "exploration",
                                    "labels": ["auth"]}))
    assert r.returncode != 0, r
    msg = (r.stdout + r.stderr).lower()
    # the message should suggest a reassessment as the answer
    assert "re-assess" in msg, r
