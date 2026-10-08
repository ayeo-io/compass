"""`compass retro` ignores a re-assessment of kind `configuration`.

A reassess that changes only an issue's `config:` layer records an entry of
kind `configuration`. It says nothing about how assessment sizes work, so the
sizing signal ignores it, as it ignores `policy-correction`.

Scenario id: CR-8 (issue `configure-and-reassess`).
"""
from __future__ import annotations

import json


def _task(slug, entries):
    return {"task": slug, "created": "2026-10-08",
            "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                           "size": "small", "goal": "delivery"},
            "delivery_approach": entries[-1]["to_route"],
            "reassessments": [dict(e, reason="x", date="2026-10-08") for e in entries]}


def _data(run_cli):
    r = run_cli("retro", "--json")
    assert r.returncode == 0, r
    payload = json.loads(r.stdout)
    return payload.get("data", payload)


def test_cr_8_a_configuration_entry_does_not_move_the_sizing_signal(run_cli, make_task):
    make_task("t1", _task("t1", [{"from_route": "feature", "to_route": "initiative"}]))
    before = _data(run_cli)
    assert (before["up"], before["down"], before["sideways"]) == (1, 0, 0)
    make_task("t2", _task("t2", [{"from_route": "feature", "to_route": "feature",
                                  "kind": "configuration",
                                  "generation": {"from": 1, "to": 2}}]))
    after = _data(run_cli)
    assert (after["up"], after["down"], after["sideways"]) == (1, 0, 0), after


def test_cr_8_the_same_entry_of_kind_judgement_would_count(run_cli, make_task):
    """The test above can fail: without the kind, the entry is a sideways move."""
    make_task("t1", _task("t1", [{"from_route": "feature", "to_route": "initiative"}]))
    make_task("t2", _task("t2", [{"from_route": "feature", "to_route": "feature",
                                  "kind": "judgement"}]))
    data = _data(run_cli)
    assert data["sideways"] == 1, data
