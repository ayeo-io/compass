"""`compass next` on the four-stage path (ADR-092): the stage and the `next:` command.

`cli/compass_pkg/next_step.py` decides the one command that comes next from an
issue's records, read top to bottom, first match wins. `compass next` prints it
after the stage as `<Stage> | next: <command>`, and `compass next --json` gains
it as a `next` field.

No verb writes a path manifest yet, so each test writes one by hand: a manifest
with an `evidence_required` list is a path issue (`path_stages.is_path_issue`).
An issue assessed before the path keeps its `stages:` map, and `compass next`
shows its stage as the path stage it maps to.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
SHIM = ROOT / "bin" / "compass-statusline"
sys.path.insert(0, str(ROOT / "cli"))

import yaml  # noqa: E402  (the bundled copy, once compass_pkg is on the path)

from compass_pkg import lifecycle, next_cmd, next_step  # noqa: E402

SLUG = "the-issue"
LIGHT = ["scenarios", "red-before-green", "suite-green", "correctness", "governance",
         "traceability"]
THREE_GATES = ["verify.correctness", "verify.governance", "verify.traceability"]
SCENARIO = {"id": "TRC-001", "title": "the change", "intent": "INT-1",
            "tests": ["tests/test_it.py::test_it"]}


def _env(**extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDECODE", "NO_COLOR", "COMPASS_COLOR", "COLUMNS", "COMPASS_ISSUE")}
    env.update(extra)
    return env


def _path_issue(root: Path, *, evidence=LIGHT, scenarios=(), gates_pass=False, reds=(),
                outer_reds=(), greens=(), outer_greens=(), files=(), raw=None) -> Path:
    """A project at `root` whose one issue is a path issue with these records,
    each written where the command that makes it writes it."""
    task = root / ".compass" / "work" / SLUG
    (task / "evidence").mkdir(parents=True)
    (root / ".compass" / "current-task").write_text(SLUG + "\n")
    manifest = {
        "schema_version": "2.0", "issue": SLUG, "created": "2026-11-05", "status": "active",
        "delivery_approach": "delivery",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "small", "goal": "delivery"},
        "evidence_required": list(evidence),
        "gates": [{"id": g, "status": "pass" if gates_pass else "pending", "evidence": []}
                  for g in THREE_GATES],
        "scenarios": [dict(s) for s in scenarios],
        "evidence": [],
    }
    for loop_reds, suffix in ((reds, ""), (outer_reds, ".outer")):
        for sid in loop_reds:
            record = {"passed": False, "exit_code": 1, "scenario": sid,
                      "timestamp": "2026-11-05T10:00:00Z",
                      "loop": "outer" if suffix else "inner"}
            (task / "evidence" / f"red-{sid}{suffix}.json").write_text(json.dumps(record))
    for sid in greens:
        record = {"passed": True, "exit_code": 0, "scenario": sid,
                  "timestamp": "2026-11-05T11:00:00Z"}
        (task / "evidence" / f"green-{sid}.json").write_text(json.dumps(record))
        manifest["evidence"].append({"id": f"EV-T-{sid}", "type": "test-run",
                                     "path": f"evidence/green-{sid}.json", "scenario": sid})
    for sid in outer_greens:
        record = {"passed": True, "exit_code": 0, "scenario": sid, "loop": "outer",
                  "candidate": "build-7", "client": "cli",
                  "timestamp": "2026-11-05T11:00:00Z"}
        (task / "evidence" / f"green-{sid}.outer.json").write_text(json.dumps(record))
        manifest["evidence"].append({"id": f"EV-T-{sid}-outer", "type": "test-run",
                                     "path": f"evidence/green-{sid}.outer.json",
                                     "scenario": sid})
    for name in files:
        (task / "evidence" / name).write_text("{}")
    manifest.update(raw or {})
    (task / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    return task


def _load(task: Path) -> dict:
    return next_cmd._typed(yaml.safe_load((task / "manifest.yml").read_text()))


def _next(root: Path, *extra, **env):
    r = subprocess.run([sys.executable, str(CLI), "next", *extra], cwd=root,
                       capture_output=True, text=True, env=_env(**env))
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


# --- the table, one row at a time --------------------------------------------------------

ROWS = {
    "assessed, no scenario": (
        dict(), "compass scenario add TRC-001 --intent <intent id> --test <path::name>"),
    "a scenario with no test": (
        dict(scenarios=[dict(SCENARIO, tests=[])]),
        "compass scenario tests set TRC-001 --test <path::name>"),
    "scenario approval owed": (
        dict(evidence=LIGHT + ["scenario-approval"], scenarios=[SCENARIO]),
        "compass evidence request --checkpoint specify, then stop for /compass:approve"),
    "S17 applies, no outer-loop red": (
        dict(evidence=LIGHT + ["outer-loop"], scenarios=[SCENARIO]),
        "compass tdd-red --loop outer --scenario TRC-001 -- <acceptance test command>"),
    "a scenario with no red": (
        dict(scenarios=[SCENARIO]), "compass tdd-red --scenario TRC-001 -- <test command>"),
    "a red with no green": (
        dict(scenarios=[SCENARIO], reds=["TRC-001"]),
        "compass tdd-green --scenario TRC-001 -- <test command>"),
    # Where `S17` applies the green is the outer loop's, which names the candidate
    # the isolation proof is then made on.
    "S17 applies, no outer-loop green": (
        dict(evidence=LIGHT + ["outer-loop"], scenarios=[SCENARIO],
             outer_reds=["TRC-001"], greens=["TRC-001"]),
        "compass tdd-green --loop outer --scenario TRC-001 --candidate <build id>|local "
        "--client api|web|cli -- <acceptance test command>"),
    "isolation owed": (
        dict(evidence=LIGHT + ["outer-loop", "isolation"], scenarios=[SCENARIO],
             outer_reds=["TRC-001"], outer_greens=["TRC-001"]),
        "compass isolation record --candidate build-7 --client cli "
        "--parallel \"<acceptance suite command>\" "
        "--repeat \"<scenario test command> {tests}\""),
    "layering owed": (
        dict(evidence=LIGHT + ["outer-loop", "isolation", "layering"], scenarios=[SCENARIO],
             outer_reds=["TRC-001"], outer_greens=["TRC-001"],
             files=["isolation-proof.json"]),
        "compass layering record --test-path <layering test path> "
        "-- <layering test command>"),
    "a review gate pending": (
        dict(scenarios=[SCENARIO], reds=["TRC-001"], greens=["TRC-001"],
             raw={"gates": [{"id": g, "status": "pending", "evidence": []}
                            for g in THREE_GATES + ["verify.regression"]]}),
        "compass gate pass verify.regression --evidence <EV-id>"),
    # `compass quick-fix finish` passes the three immovable gates itself.
    "only the three immovable gates pending": (
        dict(scenarios=[SCENARIO], reds=["TRC-001"], greens=["TRC-001"]),
        next_step.FINISH),
    "human approval owed": (
        dict(evidence=LIGHT + ["human-approval"], scenarios=[SCENARIO], reds=["TRC-001"],
             greens=["TRC-001"], gates_pass=True),
        "compass evidence request --check human-approval-present"),
    "every gate passes": (
        dict(scenarios=[SCENARIO], reds=["TRC-001"], greens=["TRC-001"], gates_pass=True),
        "compass check, then compass ship-commit -m \"<message>\""),
}


@pytest.mark.parametrize("case", list(ROWS))
def test_each_row_of_the_table_names_its_command(tmp_path, case):
    """The first row whose records match gives the command."""
    kwargs, expected = ROWS[case]
    task = _path_issue(tmp_path, **kwargs)
    assert next_step.next_command(_load(task), str(task)) == expected, case


def test_no_manifest_names_go():
    assert next_step.next_command(None, None) == '/compass:go "<what you want>"'


def test_a_closed_issue_has_no_next_command(tmp_path):
    task = _path_issue(tmp_path, scenarios=[SCENARIO], reds=["TRC-001"], greens=["TRC-001"],
                       gates_pass=True, raw={"status": "done", "close_reason": "completed"})
    assert next_step.next_command(_load(task), str(task)) is None
    assert _next(tmp_path) == "all phases complete\n"


def test_a_narrative_scenario_needs_no_test_and_no_red(tmp_path):
    task = _path_issue(tmp_path, scenarios=[dict(SCENARIO, tests=[], verifiable="narrative")])
    assert next_step.next_command(_load(task), str(task)) == next_step.FINISH


# --- stage completion on the path --------------------------------------------------------

STAGES = {
    "assessed, no scenario": (dict(), "specify"),
    "a scenario with no test": (dict(scenarios=[dict(SCENARIO, tests=[])]), "specify"),
    "a scenario with its test": (dict(scenarios=[SCENARIO]), "build"),
    "a red, no green": (dict(scenarios=[SCENARIO], reds=["TRC-001"]), "build"),
    "a green with no red": (dict(scenarios=[SCENARIO], greens=["TRC-001"]), "build"),
    "a red, then a green": (dict(scenarios=[SCENARIO], reds=["TRC-001"], greens=["TRC-001"]),
                            "ship"),
    "every gate passes": (dict(scenarios=[SCENARIO], reds=["TRC-001"], greens=["TRC-001"],
                               gates_pass=True), "ship"),
}


@pytest.mark.parametrize("case", list(STAGES))
def test_the_path_stage_comes_from_the_records(tmp_path, case):
    kwargs, expected = STAGES[case]
    task = _path_issue(tmp_path, **kwargs)
    assert next_cmd._current_phase_from_task(_load(task), str(task)) == expected, case


def test_specify_waits_for_a_listed_checkpoint(tmp_path):
    """Specify is done only when the `specify` checkpoint has an outcome where it
    is listed."""
    task = _path_issue(tmp_path, scenarios=[SCENARIO], raw={"checkpoints": ["specify"]})
    assert next_cmd._current_phase_from_task(_load(task), str(task)) == "specify"
    task = _path_issue(tmp_path / "b", scenarios=[SCENARIO], raw={
        "checkpoints": ["specify"], "checkpoint_outcomes": [
            {"stage": "specify", "outcome": "waited", "by": "owner",
             "at": "2026-11-05T10:00:00Z", "evidence": "EV-CP-specify"}]})
    assert next_cmd._current_phase_from_task(_load(task), str(task)) == "build"


# --- what `compass next` prints ------------------------------------------------------------

def test_compass_next_prints_the_stage_and_the_next_command(tmp_path):
    _path_issue(tmp_path)
    assert _next(tmp_path) == (
        "Specify [gate: verify.correctness] | next: compass scenario add TRC-001 "
        "--intent <intent id> --test <path::name>\n")


def test_compass_next_at_build(tmp_path):
    _path_issue(tmp_path, scenarios=[SCENARIO], reds=["TRC-001"])
    assert _next(tmp_path) == (
        "Build [gate: verify.correctness] | next: compass tdd-green --scenario TRC-001 "
        "-- <test command>\n")


def test_the_rail_shows_the_four_path_stages(tmp_path):
    _path_issue(tmp_path, scenarios=[SCENARIO])
    out = _next(tmp_path, COMPASS_COLOR="always", NO_COLOR="1", COLUMNS="200")
    assert "Assess ✓ → Specify ✓ → Build ● → Ship ○" in out, out
    assert "Next: /compass:" not in out, out


def test_compass_next_json_gains_the_next_field(tmp_path):
    """The `--json` document keeps its keys and gains `next`."""
    _path_issue(tmp_path, scenarios=[SCENARIO])
    doc = json.loads(_next(tmp_path, "--json"))
    assert list(doc) == ["output", "structured", "note", "next"], doc
    assert doc["output"] == [
        "Build [gate: verify.correctness] | next: compass tdd-red --scenario TRC-001 "
        "-- <test command>"]
    assert doc["structured"] is False
    assert doc["next"] == "compass tdd-red --scenario TRC-001 -- <test command>"


def test_compass_next_json_on_a_closed_issue_has_a_null_next(tmp_path):
    _path_issue(tmp_path, raw={"status": "done", "close_reason": "completed"})
    doc = json.loads(_next(tmp_path, "--json"))
    assert doc["output"] == ["all phases complete"] and doc["next"] is None, doc


# --- an issue assessed before the path ----------------------------------------------------

LEGACY_STAGES = {"assess": "light", "define": "light", "refine": "collapsed",
                 "plan": "collapsed", "breakdown": "skipped", "implement": "light",
                 "verify": "light", "ship": "light"}


def _legacy_issue(root: Path, **raw) -> Path:
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    (root / ".compass" / "current-task").write_text(SLUG + "\n")
    manifest = {"schema_version": "2.0", "issue": SLUG, "created": "2026-11-05",
                "status": "active", "delivery_approach": "quick-fix",
                "stages": dict(LEGACY_STAGES),
                "gates": [{"id": g, "status": "pending"} for g in THREE_GATES],
                "scenarios": [SCENARIO]}
    manifest.update(raw)
    (task / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    return task


@pytest.mark.parametrize("legacy,shown", [
    ("define", "Specify"), ("refine", "Specify"), ("plan", "Specify"),
    ("breakdown", "Build"), ("implement", "Build"), ("verify", "Ship"), ("ship", "Ship")])
def test_an_old_issue_shows_its_path_stage(tmp_path, legacy, shown):
    """The legacy stage stays the stage the readers act on; only the shown word maps."""
    task = _legacy_issue(tmp_path, current_phase=legacy)
    assert next_cmd._current_phase_from_task(_load(task), str(task)) == legacy
    line = _next(tmp_path)
    assert line.startswith(shown + " [gate: verify.correctness] | next: "), line
    status = subprocess.run([str(SHIM)], input=json.dumps({"cwd": str(tmp_path)}),
                            capture_output=True, text=True, env=_env(COLUMNS="200"),
                            timeout=30).stdout
    assert f" · {shown} · " in status, status


def test_an_old_issue_gets_a_next_command(tmp_path):
    _legacy_issue(tmp_path)
    assert _next(tmp_path) == (
        "Build [gate: verify.correctness] | next: compass tdd-red --scenario TRC-001 "
        "-- <test command> | Refine, Plan collapsed in this approach\n")


def test_an_old_issue_keeps_its_legacy_hint_on_the_rail(tmp_path):
    """The stage commands still exist for an old issue until they are removed."""
    _legacy_issue(tmp_path, delivery_approach="regular",
                  stages=dict(LEGACY_STAGES, refine="light", plan="light"))
    out = _next(tmp_path, COMPASS_COLOR="always", NO_COLOR="1", COLUMNS="200")
    assert "Specify ●" in out and "Next: /compass:refine" in out, out


# --- `depends_on` `until` -------------------------------------------------------------------

def test_until_accepts_the_path_stages_and_the_legacy_names():
    for value in ("specify", "build", "ship", "define", "refine", "plan", "breakdown",
                  "implement", "verify", "done", "in-review"):
        assert value in lifecycle.UNTIL_VALUES, value
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text())
    enum = schema["properties"]["depends_on"]["items"]["properties"]["until"]["enum"]
    assert enum == list(lifecycle.UNTIL_VALUES)


@pytest.mark.parametrize("until,stage,met", [
    # Both legacy: judged in the legacy order, as before.
    ("plan", "refine", False), ("plan", "breakdown", True), ("verify", "implement", False),
    ("ship", "verify", False),
    # A path `until` on an old issue, and a legacy `until` on a path issue: judged
    # through the mapping.
    ("build", "implement", True), ("build", "plan", False), ("specify", "define", True),
    ("implement", "build", True), ("verify", "build", False),
    ("plan", "specify", True), ("build", "specify", False), ("ship", "build", False),
])
def test_until_is_judged_through_the_mapping(until, stage, met):
    assert lifecycle.reached(until, "in-progress", stage, None) is met, (until, stage)


def test_a_path_issue_at_build_is_in_scope_for_its_dependencies(tmp_path):
    task = _path_issue(tmp_path, scenarios=[SCENARIO], reds=["TRC-001"])
    assert lifecycle.in_scope(_load(task), str(task)) is True
