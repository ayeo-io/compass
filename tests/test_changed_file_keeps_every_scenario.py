"""`compass changed-file add` records every scenario it is given.

A file can serve several scenarios, and `--scenario` may be repeated to say
so. Every value given is recorded, merged with the scenarios the file
already traces to, without duplicates.

Scenario ids: CKS-1 and CKS-2, in the delivery approach of issue
`changed-file-keeps-one-scenario`.
"""
from __future__ import annotations

import yaml

BODY = {"assessment": {"risk": "contained", "familiarity": "greenfield",
                       "size": "small", "goal": "delivery",
                       "role": "engineer", "labels": []},
        "scenarios": []}


def _traced(task_dir, path):
    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    return [cf.get("scenarios") for cf in task.get("changed_files") or []
            if cf.get("path") == path]


def test_cks_1_a_repeated_scenario_flag_records_every_value(make_task, run_cli, project):
    task_dir = make_task("cks", BODY)
    (project / "src").mkdir()
    (project / "src" / "a.py").write_text("x = 1\n")
    result = run_cli("changed-file", "add", "src/a.py", "--issue", "cks",
                     "--scenario", "S-1", "--scenario", "S-2", "--scenario", "S-3")
    assert result.returncode == 0, result.combined
    assert _traced(task_dir, "src/a.py") == [["S-1", "S-2", "S-3"]]


def test_cks_2_a_later_add_keeps_the_earlier_scenarios(make_task, run_cli, project):
    task_dir = make_task("cks", BODY)
    (project / "src").mkdir()
    (project / "src" / "a.py").write_text("x = 1\n")
    for scenarios in (["S-1"], ["S-2", "S-1"]):
        flags = [f for s in scenarios for f in ("--scenario", s)]
        result = run_cli("changed-file", "add", "src/a.py", "--issue", "cks", *flags)
        assert result.returncode == 0, result.combined
    assert _traced(task_dir, "src/a.py") == [["S-1", "S-2"]]
