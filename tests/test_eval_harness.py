"""Tests for evals/harness.py (SPT-1 - a run is recorded under either condition).

None of these tests call a real model. A fake `claude` executable, built by
`_write_fake_claude` below, replays a fixed set of line-delimited JSON
events - the same envelope the real CLI's `--output-format` produces - and
logs every argument list and working-directory listing it was called with,
so the assertions below read the harness's own command line back rather than
guessing at it.

The scenario fixture is built by `_write_scenario`, entirely inside this
file, per the brief for this subtask: it does not wait on, or reach into,
`evals/scenarios/`, which a sibling subtask owns.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The bundled copy of PyYAML resolves the same way it does for every other
# entry point (`tests/conftest.py`): put `cli/` on `sys.path` and import
# `compass_pkg` for its side effect before importing `yaml`.
sys.path.insert(0, str(REPO_ROOT / "cli"))
import compass_pkg  # noqa: E402  (side effect: puts cli/vendor at sys.path[0])
import yaml  # noqa: E402

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from evals import harness  # noqa: E402


# --- a fake `claude`, entirely self-contained ------------------------------

_FAKE_CLAUDE_SOURCE = '''#!/usr/bin/env python3
"""A stand-in for the real CLI, used only by this repository's own tests.

Logs the argument list, the working directory and a listing of that
directory's own contents (so a test can prove a run started from a clean
checkout), then edits one file and prints a fixed set of line-delimited
JSON events: an init line carrying a session id, an assistant turn with two
tool calls, their results, and a final line carrying a cost.
"""
import json
import os
import sys


def _listing(root):
    found = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in names:
            full = os.path.join(base, name)
            found.append(os.path.relpath(full, root))
    return sorted(found)


def main():
    cwd = os.getcwd()
    record = {"args": sys.argv[1:], "cwd": cwd, "listing": _listing(cwd)}
    with open(os.environ["FAKE_CLAUDE_LOG"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")

    target = os.path.join(cwd, "seed.txt")
    if os.path.isfile(target):
        with open(target, "a", encoding="utf-8") as fh:
            fh.write("edited by the fake CLI\\n")

    session_id = "fake-session-0001"
    events = [
        {"type": "system", "subtype": "init", "session_id": session_id},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_1", "name": "Read",
             "input": {"file_path": "seed.txt"}},
            {"type": "tool_use", "id": "toolu_2", "name": "Edit",
             "input": {"file_path": "seed.txt"}},
        ]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1",
             "content": "seed.txt contents", "is_error": False},
            {"type": "tool_result", "tool_use_id": "toolu_2",
             "content": "edited seed.txt", "is_error": False},
        ]}},
        {"type": "result", "subtype": "success", "session_id": session_id,
         "total_cost_usd": 0.02, "result": "fixed it"},
    ]
    for event in events:
        print(json.dumps(event))


if __name__ == "__main__":
    main()
'''


def _write_fake_claude(tmp_path: Path) -> Path:
    path = tmp_path / "fake_claude.py"
    path.write_text(_FAKE_CLAUDE_SOURCE, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


# --- a scenario fixture, owned entirely by this test file ------------------

def _write_scenario(tmp_path: Path) -> Path:
    scenario_dir = tmp_path / "scenario"
    seed_dir = scenario_dir / "seed"
    seed_dir.mkdir(parents=True)
    (seed_dir / "seed.txt").write_text("original contents\n", encoding="utf-8")
    (seed_dir / "run_tests.py").write_text(
        "import sys\nsys.exit(0)\n", encoding="utf-8"
    )

    compass_overlay = scenario_dir / "seed_compass" / ".compass" / "work" / "fixture-issue"
    compass_overlay.mkdir(parents=True)
    (compass_overlay / "manifest.yml").write_text(
        "issue: fixture-issue\nstatus: active\n", encoding="utf-8"
    )

    bare_overlay = scenario_dir / "seed_bare"
    bare_overlay.mkdir(parents=True)
    (bare_overlay / "PLAN.md").write_text("# Plan\n\nFix the bug.\n", encoding="utf-8")

    scenario_yml = {
        "id": "pressure-fixture",
        "failure_mode": "a fixture failure mode, used only by this test file",
        "prompt": "Fix the bug in seed.txt.",
        "follow_ups": ["Also handle the edge case."],
        "risky": False,
        "budget_usd": 3.0,
        "in_scope": ["**"],
        "test_command": "python3 run_tests.py",
        "behaviours": [
            {"id": "fixture_behaviour", "rubric": "unused by this test file"},
        ],
    }
    with (scenario_dir / "scenario.yml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(scenario_yml, fh, sort_keys=False)
    return scenario_dir


def _read_log(log_path: Path) -> list[dict]:
    if not log_path.is_file():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture
def scenario_dir(tmp_path: Path) -> Path:
    return _write_scenario(tmp_path)


@pytest.fixture
def fake_claude(tmp_path: Path) -> Path:
    return _write_fake_claude(tmp_path)


def _run_condition(tmp_path, scenario_dir, fake_claude, condition, monkeypatch):
    log_path = tmp_path / f"log-{condition}.jsonl"
    out_dir = tmp_path / f"out-{condition}"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log_path))
    exit_code = harness.main([
        "--scenario", str(scenario_dir),
        "--condition", condition,
        "--claude", str(fake_claude),
        "--out", str(out_dir),
    ])
    assert exit_code == 0
    calls = _read_log(log_path)
    out_files = sorted(out_dir.glob("*.json"))
    assert len(out_files) == 1
    record = json.loads(out_files[0].read_text(encoding="utf-8"))
    return calls, record, out_files[0]


def test_compass_condition_loads_the_plugin_and_bare_does_not(
    tmp_path, scenario_dir, fake_claude, monkeypatch
):
    compass_calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch
    )
    bare_calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch
    )

    compass_args = compass_calls[0]["args"]
    bare_args = bare_calls[0]["args"]

    assert "--plugin-dir" in compass_args
    plugin_dir = compass_args[compass_args.index("--plugin-dir") + 1]
    assert Path(plugin_dir) == REPO_ROOT

    assert "--plugin-dir" not in bare_args


def test_both_conditions_pass_settings_budget_and_allow_list(
    tmp_path, scenario_dir, fake_claude, monkeypatch
):
    for condition in ("compass", "bare"):
        calls, _, _ = _run_condition(
            tmp_path, scenario_dir, fake_claude, condition, monkeypatch
        )
        args = calls[0]["args"]

        assert "--setting-sources" in args
        assert args[args.index("--setting-sources") + 1] == "project,local"

        assert "--max-budget-usd" in args
        assert args[args.index("--max-budget-usd") + 1] == "3.0"

        assert "--allowedTools" in args
        allow_list = args[args.index("--allowedTools") + 1]
        for tool in harness.ALLOWED_TOOLS:
            assert tool in allow_list.split(",")


def test_each_run_starts_from_a_fresh_repository_with_only_the_seed(
    tmp_path, scenario_dir, fake_claude, monkeypatch
):
    compass_calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch
    )
    listing = set(compass_calls[0]["listing"])
    assert listing == {
        "seed.txt",
        "run_tests.py",
        os.path.join(".compass", "work", "fixture-issue", "manifest.yml"),
    }

    bare_calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch
    )
    listing = set(bare_calls[0]["listing"])
    assert listing == {"seed.txt", "run_tests.py", "PLAN.md"}


def test_follow_up_is_sent_with_resume_and_the_session_id(
    tmp_path, scenario_dir, fake_claude, monkeypatch
):
    calls, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch
    )
    assert len(calls) == 2
    first_args, second_args = calls[0]["args"], calls[1]["args"]

    assert "--resume" in second_args
    resumed_id = second_args[second_args.index("--resume") + 1]
    assert resumed_id == "fake-session-0001"
    assert record["session_id"] == "fake-session-0001"
    assert "--resume" not in first_args


def test_run_record_has_every_field_from_the_design(
    tmp_path, scenario_dir, fake_claude, monkeypatch
):
    _, record, out_path = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch
    )

    assert set(record.keys()) == {
        "scenario", "condition", "run", "started", "seconds", "exit_code",
        "cost_usd", "session_id", "tool_calls", "final_text", "diff",
        "changed_paths", "compass_files", "tests_after",
    }
    assert record["scenario"] == "pressure-fixture"
    assert record["condition"] == "compass"
    assert record["run"] == 1
    assert record["exit_code"] == 0
    # Two tool calls per invocation, two invocations (the prompt and the
    # one follow-up), each recorded in call order.
    assert [c["index"] for c in record["tool_calls"]] == [0, 1, 2, 3]
    for call in record["tool_calls"]:
        assert set(call.keys()) == {"index", "name", "input", "is_error", "output"}
    assert record["tool_calls"][0]["name"] == "Read"
    assert record["tool_calls"][1]["name"] == "Edit"
    assert record["cost_usd"] == pytest.approx(0.04)
    assert record["final_text"] == "fixed it"

    assert "seed.txt" in record["diff"]
    assert record["changed_paths"] == ["seed.txt"]

    assert record["compass_files"] == [
        ".compass/work/fixture-issue/manifest.yml"
    ]

    assert record["tests_after"] == {
        "command": "python3 run_tests.py", "exit_code": 0,
    }

    assert out_path.name == "pressure-fixture-compass-1.json"
