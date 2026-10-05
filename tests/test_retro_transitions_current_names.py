"""`compass retro` counts each route transition once, under current names.

Re-assessments are recorded with the route names in use at the time, so an
older entry says `express -> standard` where a newer one says
`quick-fix -> feature`. Retro keyed its transition count on the recorded
names and mapped them only when printing, so one transition showed as two
rows, and the JSON output kept the retired names (issue #327).

Scenario id: RT-1 (issue `retro-transitions-split-by-old-names`).
"""
from __future__ import annotations

import json

from test_retro_weighs_current_route_names import _task


def test_rt_1_one_transition_is_one_row_under_current_names(run_cli, make_task):
    make_task("t1", _task("t1", [("express", "standard")]))
    make_task("t2", _task("t2", [("quick-fix", "feature")]))
    make_task("t3", _task("t3", [("expedition", "feature")]))
    r = run_cli("retro", "--json")
    assert r.returncode == 0, r
    payload = json.loads(r.stdout)
    transitions = payload.get("data", payload)["transitions"]
    assert transitions == {"quick-fix -> regular": 2,
                           "full -> regular": 1}, transitions
    text = run_cli("retro").stdout
    assert text.count("quick fix -> regular") == 1, text
    assert "quick fix -> regular : 2" in text, text
