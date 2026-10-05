"""This repository's own issues do not wait for the maintainer.

The maintainer asked, on 5 October 2026, to stay out of the loop: no
checkpoint waits at define or plan. The project setting that does this is
`autonomy: autonomous` in `.compass/config.yml`, which keeps every hand-off
shown and logged but stops none. It changes no gate, evidence, hook or
`compass check`. Adopters keep the shipped default, `balanced`.

Scenario id: RA-1 (issue `repository-autonomy`).
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.routing import evaluate_route  # noqa: E402


def test_ra_1_this_repository_runs_autonomously():
    config = yaml.safe_load((ROOT / ".compass" / "config.yml").read_text(encoding="utf-8"))
    assert config.get("autonomy") == "autonomous"
    policy = yaml.safe_load((ROOT / "governance" / "routing-policy.yml")
                            .read_text(encoding="utf-8"))
    readings = {"risk": "cross-cutting", "familiarity": "brownfield-mapped",
                "size": "large", "goal": "delivery", "role": "engineer"}
    assert evaluate_route(readings, policy, config["autonomy"])["checkpoints"] == []
