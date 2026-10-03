"""A red or green cannot be bound to a scenario the manifest does not hold.

`tdd-red --scenario X` checked X against the manifest's scenarios only when
the list was not empty, so on an issue with no scenarios any id was
accepted. Found landing `premium-scenario-classes`: its reds and greens
were bound to four scenarios that did not exist until `compass check`
caught it at the end (issue #342).

Scenario id: US-1 (issue `red-for-an-unknown-scenario`).
"""
from __future__ import annotations

import yaml

from test_quick_fix_verbs import (GREET_CMD, _base_greeting, _run, _start,  # noqa: F401
                                  repo)


def _empty_scenarios(repo, slug):
    path = repo / ".compass" / "work" / slug / "manifest.yml"
    manifest = yaml.safe_load(path.read_text())
    manifest["scenarios"] = []
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))


def test_us_1_a_red_for_an_unknown_scenario_is_refused(repo):
    _base_greeting(repo)
    assert _start(repo, "fix-greeting").returncode == 0
    _empty_scenarios(repo, "fix-greeting")
    red = _run(repo, "tdd-red", "--issue", "fix-greeting", "--scenario",
               "TRC-009", *GREET_CMD)
    assert red.returncode != 0, red.stdout + red.stderr
    assert "compass scenario add" in red.stdout + red.stderr
    evidence = repo / ".compass" / "work" / "fix-greeting" / "evidence"
    assert not list(evidence.glob("red-TRC-009*")), list(evidence.iterdir())


def test_us_1_a_green_for_an_unknown_scenario_is_refused(repo):
    _base_greeting(repo)
    assert _start(repo, "fix-greeting").returncode == 0
    green = _run(repo, "tdd-green", "--issue", "fix-greeting", "--scenario",
                 "TRC-009", *GREET_CMD)
    assert green.returncode != 0, green.stdout + green.stderr
    assert "compass scenario add" in green.stdout + green.stderr
