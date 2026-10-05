"""A route that breaks work down across agents earns the distribution map.

`scripts/multiagent.sh` reads a distribution map. The feature route
computed `breakdown: multiagent` but did not earn a map, so
`compass issue artifact distribution-map` refused to register one, and the
map only worked as an unregistered file beside the manifest.

Scenario ids: FRM-1 and FRM-2, in the delivery approach of issue
`feature-route-omits-the-map`.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "governance" / "routing-policy.yml"

SLUG = "feat"
BODY = {"assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "standard", "goal": "delivery",
                       "role": "engineer", "labels": []},
        "scenarios": []}


def test_frm_1_a_feature_assessment_earns_and_registers_the_map(make_task, run_cli, project):
    make_task(SLUG, BODY)
    evaluate = run_cli("approach", "evaluate", "--issue", SLUG, "--write")
    assert evaluate.returncode == 0, evaluate.combined
    doc = project / "docs" / "compass" / "map.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# Distribution map\n")
    register = run_cli("issue", "artifact", "distribution-map", "--issue", SLUG,
                       "--status", "draft", "--path", "docs/compass/map.md")
    assert register.returncode == 0, register.combined


def test_frm_2_every_multiagent_route_earns_the_map():
    routes = yaml.safe_load(POLICY.read_text())
    shapes = next(v for v in routes.values()
                  if isinstance(v, dict) and "regular" in v and "full" in v)
    multiagent = [name for name, shape in shapes.items()
                  if isinstance(shape, dict)
                  and (shape.get("stages") or {}).get("breakdown") == "multiagent"]
    assert multiagent, "no route has a multiagent breakdown"
    for name in multiagent:
        assert "distribution-map" in (shapes[name].get("artifacts") or {}), name
