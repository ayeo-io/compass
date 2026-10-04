"""An issue slug that names an eval scenario is refused when it is made.

The living spec lists every landed issue by slug, and the eval plugin copy
ships the spec, so a slug must name no eval scenario. Titles were checked
(#283); a slug was not, and CI failed after the issue landed (#382).

Scenario id: SN-1 (issue `slug-names-an-eval-scenario`).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from test_quick_fix_verbs import _run, _start, repo  # noqa: E402,F401


def _plant_eval_scenario(root):
    scen = root / "evals" / "scenarios" / "cmp-demo"
    scen.mkdir(parents=True)
    (scen / "scenario.yml").write_text("id: cmp-demo\n", encoding="utf-8")


def test_sn_1_quick_fix_start_refuses_a_slug_naming_an_eval_scenario(repo):
    _plant_eval_scenario(repo)
    result = _start(repo, "cmp-demo-token-fix")
    assert result.returncode != 0, result.stdout
    assert "cmp-demo" in result.stderr and "eval" in result.stderr
    assert not (repo / ".compass" / "work" / "cmp-demo-token-fix").exists()


def test_sn_1_a_slug_naming_none_is_accepted(repo):
    _plant_eval_scenario(repo)
    result = _start(repo, "demo-token-fix")
    assert result.returncode == 0, result.stderr


def test_sn_1_approach_evaluate_refuses_it_too(repo):
    _plant_eval_scenario(repo)
    task = repo / ".compass" / "work" / "cmp-demo-thing"
    task.mkdir(parents=True)
    (task / "manifest.yml").write_text(
        "schema_version: '2.0'\nissue: cmp-demo-thing\ncreated: '2026-10-04'\n"
        "status: active\nassessment:\n  risk: trivial\n  familiarity: "
        "brownfield-mapped\n  size: atomic\n  goal: delivery\n  role: engineer\n"
        "  labels: []\n", encoding="utf-8")
    result = _run(repo, "approach", "evaluate", "--issue", "cmp-demo-thing",
                  "--write")
    assert result.returncode != 0, result.stdout
    assert "cmp-demo" in result.stderr
