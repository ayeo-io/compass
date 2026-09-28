"""`compass retro` weighs a re-assessment by the route names manifests record.

Retro counts each re-assessment as up, down or sideways by the routes'
weights in `governance/routing-policy.yml`. The policy's `route_shapes` keys
are the machine names (`express`, `standard`, `expedition`), while manifests
record `quick-fix`, `feature` and `initiative`. Retro maps a route name to
its key through the `delivery_approach` table in `cli/migrate-map.yml`, so
both spellings weigh the same. A route with no weight is reported as
unweighed, not counted as sideways.

Scenario ids: RWC-1 to RWC-3, in the delivery approach of issue
`retro-weighs-only-retired-route-names`.
"""
from __future__ import annotations

import json


def _task(slug, transitions):
    return {"task": slug, "created": "2026-09-25",
            "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                           "size": "small", "goal": "delivery"},
            "delivery_approach": transitions[-1][1],
            "reassessments": [{"from_route": fr, "to_route": to, "reason": "x",
                               "date": "2026-09-25"} for fr, to in transitions]}


def _retro(run_cli):
    r = run_cli("retro", "--json")
    assert r.returncode == 0, r
    return r, json.loads(r.stdout)


def _data(payload):
    return payload.get("data", payload)


def test_rwc_1_current_route_names_count_up_and_down(run_cli, make_task):
    make_task("t1", _task("t1", [("quick-fix", "feature")]))
    make_task("t2", _task("t2", [("feature", "initiative")]))
    make_task("t3", _task("t3", [("initiative", "feature")]))
    _, payload = _retro(run_cli)
    data = _data(payload)
    assert (data["up"], data["down"], data["sideways"]) == (2, 1, 0), data


def test_rwc_1_retired_and_current_names_weigh_the_same(run_cli, make_task):
    make_task("t1", _task("t1", [("express", "feature")]))
    make_task("t2", _task("t2", [("standard", "feature")]))
    _, payload = _retro(run_cli)
    data = _data(payload)
    assert (data["up"], data["down"], data["sideways"]) == (1, 0, 1), data


def test_rwc_2_a_route_with_no_weight_is_unweighed_not_sideways(run_cli, make_task):
    make_task("t1", _task("t1", [("bespoke", "feature")]))
    r, payload = _retro(run_cli)
    data = _data(payload)
    assert data["sideways"] == 0, data
    assert data["unweighed"] == 1, data
    text = run_cli("retro").stdout
    assert "unweighed" in text and "bespoke -> feature" in text, text


def test_rwc_3_retro_prints_no_retired_name_for_assessment(run_cli, make_task):
    make_task("t1", _task("t1", [("quick-fix", "feature")]))
    make_task("t2", _task("t2", [("initiative", "quick-fix")]))
    text = run_cli("retro").stdout
    assert "Needle" not in text, text
