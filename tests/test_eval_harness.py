"""Tests for evals/harness.py (SPT-1 - a run is recorded under either condition).

None of these tests call a real model. A fake `claude` executable, built by
`_write_fake_claude` below, replays a fixed set of line-delimited JSON
events - the same envelope the real CLI's `--output-format` produces - and
logs every argument list, working directory, directory listing and
environment it was called with, so the assertions below read the harness's
own command line and child process back rather than guessing at them.

The scenario fixture is built by `_write_scenario`, and the plugin-source
fixture by `_write_plugin_repo`, entirely inside this file: a small git
repository stands in for this checkout, so a test never copies the real
repository's tracked tree.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
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

The harness gives its child a built environment, not an inherited one - so
this script cannot read an environment variable to learn what a specific
test needs. It reads a config file next to itself instead
(`fake_claude_config.json`): the log path every call appends its own record
to, and what a test wants switched on for that run - the cost it reports, a
write outside its own directory, a simulated permission denial.
"""
import json
import os
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CONFIG_PATH = _HERE / "fake_claude_config.json"


def _config():
    if _CONFIG_PATH.is_file():
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def _listing(root):
    found = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in names:
            full = os.path.join(base, name)
            found.append(os.path.relpath(full, root))
    return sorted(found)


def main():
    if sys.argv[1:] == ["--version"]:
        print("fake-claude 9.9.9")
        return

    config = _config()
    cwd = os.getcwd()
    record = {
        "args": sys.argv[1:],
        "cwd": cwd,
        "listing": _listing(cwd),
        "env": dict(os.environ),
        # Resolved now, from inside the call, because the harness's own
        # PATH entries (in particular the plugin copy's bin/) may be gone
        # by the time a test can look.
        "resolved_compass": shutil.which("compass", path=os.environ.get("PATH", "")),
    }

    # The plugin copy the harness built for this call, if any - inspected
    # now, from inside the call, because the harness deletes it once the
    # call returns.
    if "--plugin-dir" in sys.argv:
        plugin_dir = sys.argv[sys.argv.index("--plugin-dir") + 1]
        readme = os.path.join(plugin_dir, "README.md")
        compass_bin = os.path.join(plugin_dir, "bin", "compass")
        record["plugin_copy"] = {
            "dir_writable": os.access(plugin_dir, os.W_OK),
            "readme_text": (open(readme, encoding="utf-8").read()
                             if os.path.isfile(readme) else None),
            "readme_writable": os.access(readme, os.W_OK),
            "compass_executable": os.access(compass_bin, os.X_OK),
        }

    with open(config["log_path"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")

    target = os.path.join(cwd, "seed.txt")
    if os.path.isfile(target):
        with open(target, "a", encoding="utf-8") as fh:
            fh.write("edited by the fake CLI\\n")

    escape_path = config.get("escape_path")
    if escape_path:
        with open(escape_path, "a", encoding="utf-8") as fh:
            fh.write("reached from outside the temporary repository\\n")

    cost = float(config.get("cost", 0.02))
    session_id = "fake-session-0001"
    deny_tool = config.get("deny_tool")

    tool_uses = [
        {"type": "tool_use", "id": "toolu_1", "name": "Read",
         "input": {"file_path": "seed.txt"}},
        {"type": "tool_use", "id": "toolu_2", "name": "Edit",
         "input": {"file_path": "seed.txt"}},
    ]
    results = []
    for call in tool_uses:
        if deny_tool and call["name"] == deny_tool:
            results.append({
                "type": "tool_result", "tool_use_id": call["id"],
                "content": "Claude requested permissions to use the "
                           + call["name"] + " tool, but you have not "
                           "granted it yet.",
                "is_error": True,
            })
        else:
            results.append({
                "type": "tool_result", "tool_use_id": call["id"],
                "content": call["name"] + " ok", "is_error": False,
            })

    permission_denials = [{"tool_use_id": "toolu_2"}] if deny_tool else []

    events = [
        {"type": "system", "subtype": "init", "session_id": session_id,
         "cwd": cwd, "model": "fake-model-1"},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "about to look at seed.txt"},
            tool_uses[0],
            tool_uses[1],
        ]}},
        {"type": "user", "message": {"role": "user", "content": results}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "fixed it"},
        ]}},
        {"type": "result", "subtype": "success", "session_id": session_id,
         "total_cost_usd": cost, "result": "fixed it",
         "permission_denials": permission_denials},
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


# --- a scenario fixture and a plugin-source fixture, owned by this file ----

def _write_scenario(tmp_path: Path, *, follow_ups: list[str] | None = None,
                     budget_usd: float = 3.0) -> Path:
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
        "follow_ups": follow_ups if follow_ups is not None else ["Also handle the edge case."],
        "risky": False,
        "budget_usd": budget_usd,
        "in_scope": ["**"],
        "test_command": "python3 run_tests.py",
        "behaviours": [
            {"id": "fixture_behaviour", "rubric": "unused by this test file"},
        ],
    }
    with (scenario_dir / "scenario.yml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(scenario_yml, fh, sort_keys=False)
    return scenario_dir


def _git_commit_all(repo: Path, message: str) -> None:
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@compass.invalid",
        "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@compass.invalid",
    })
    subprocess.run(["git", "init", "-q"], cwd=str(repo), env=env, check=True)
    subprocess.run(["git", "add", "-A"], cwd=str(repo), env=env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=str(repo),
                    env=env, check=True)


def _write_plugin_repo(root: Path) -> Path:
    """A small git repository standing in for this checkout - the compass
    condition's plugin source, so a test never archives the real one."""
    root.mkdir(parents=True, exist_ok=True)
    bin_dir = root / "bin"
    bin_dir.mkdir()
    compass_script = bin_dir / "compass"
    compass_script.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "import sys\n"
        "\n"
        "if sys.argv[1:2] == ['init']:\n"
        "    os.makedirs('.compass', exist_ok=True)\n"
        "    with open(os.path.join('.compass', 'marker-from-init.txt'), 'w',\n"
        "              encoding='utf-8') as handle:\n"
        "        handle.write('the plugin copy ran compass init here\\n')\n"
        "elif sys.argv[1:2] == ['--version']:\n"
        "    print('fixture-compass 9.9.9')\n",
        encoding="utf-8",
    )
    compass_script.chmod(
        compass_script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
    )
    (root / "README.md").write_text(
        "A fixture plugin, standing in for this repository in these tests.\n",
        encoding="utf-8",
    )
    _git_commit_all(root, "plugin source")
    return root


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


@pytest.fixture
def plugin_source_dir(tmp_path: Path) -> Path:
    return _write_plugin_repo(tmp_path / "plugin-source")


def _configure_fake_claude(fake_claude: Path, log_path: Path,
                            extra_config: dict | None) -> None:
    config = {"log_path": str(log_path), **(extra_config or {})}
    config_path = fake_claude.parent / "fake_claude_config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")


def _run_condition(tmp_path, scenario_dir, fake_claude, condition, monkeypatch,
                    plugin_source, *, out_suffix: str = "", extra_config=None):
    log_path = tmp_path / f"log-{condition}{out_suffix}.jsonl"
    out_dir = tmp_path / f"out-{condition}{out_suffix}"
    _configure_fake_claude(fake_claude, log_path, extra_config)
    exit_code = harness.main([
        "--scenario", str(scenario_dir),
        "--condition", condition,
        "--claude", str(fake_claude),
        "--out", str(out_dir),
        "--plugin-source", str(plugin_source),
    ])
    assert exit_code == 0
    calls = _read_log(log_path)
    out_files = sorted(out_dir.glob("*.json"))
    assert len(out_files) == 1
    record = json.loads(out_files[0].read_text(encoding="utf-8"))
    return calls, record, out_files[0]


# --- 1. the plugin copy -----------------------------------------------------

def test_compass_condition_gets_a_read_only_plugin_copy_at_head(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    calls, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir,
    )
    args = calls[0]["args"]
    plugin_dir = Path(args[args.index("--plugin-dir") + 1])
    plugin_copy = calls[0]["plugin_copy"]

    assert plugin_dir != plugin_source_dir
    assert plugin_copy["readme_text"] == \
        (plugin_source_dir / "README.md").read_text(encoding="utf-8")
    assert plugin_copy["dir_writable"] is False
    assert plugin_copy["readme_writable"] is False
    assert plugin_copy["compass_executable"] is True

    # the copy's own compass init ran before the seed commit: its marker is
    # part of the seed itself, not something the session changed.
    assert ".compass/marker-from-init.txt" in record["compass_files"]
    assert "marker-from-init.txt" not in record["diff"]


def test_bare_condition_gets_no_plugin_dir(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir,
    )
    assert "--plugin-dir" not in calls[0]["args"]


# --- 2. the child environment ------------------------------------------------

def test_child_environment_drops_claude_variables_and_plugin_bin_paths(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    fake_plugin_bin = (tmp_path / "home" / ".claude" / "plugins" / "cache"
                        / "compass" / "compass" / "4.0.1" / "bin")
    fake_plugin_bin.mkdir(parents=True)
    normal_bin = tmp_path / "usr-bin"
    normal_bin.mkdir()

    # The harness's own git and tar calls still need a working PATH, so the
    # real one stays, after the fixture entries this test is about.
    real_path = os.environ.get("PATH", "")
    monkeypatch.setenv(
        "PATH", os.pathsep.join([str(fake_plugin_bin), str(normal_bin), real_path])
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USER", "fixture-user")
    monkeypatch.setenv("LANG", "en_GB.UTF-8")
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "parent-session")

    bare_calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-env",
    )
    bare_env = bare_calls[0]["env"]
    assert not any(key.startswith("CLAUDE") for key in bare_env)
    assert bare_env["HOME"] == str(tmp_path / "home")
    assert bare_env["USER"] == "fixture-user"
    assert bare_env["LANG"] == "en_GB.UTF-8"
    assert bare_env["TMPDIR"] == str(tmp_path)
    bare_path_entries = bare_env["PATH"].split(os.pathsep)
    assert str(fake_plugin_bin) not in bare_path_entries
    assert str(normal_bin) in bare_path_entries
    assert bare_calls[0]["resolved_compass"] is None

    compass_calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir, out_suffix="-env",
    )
    compass_env = compass_calls[0]["env"]
    assert not any(key.startswith("CLAUDE") for key in compass_env)
    compass_path_entries = compass_env["PATH"].split(os.pathsep)
    assert str(fake_plugin_bin) not in compass_path_entries
    assert str(normal_bin) in compass_path_entries

    plugin_dir_arg = compass_calls[0]["args"][
        compass_calls[0]["args"].index("--plugin-dir") + 1
    ]
    assert compass_path_entries[0] == str(Path(plugin_dir_arg) / "bin")
    assert compass_calls[0]["resolved_compass"] == \
        str(Path(plugin_dir_arg) / "bin" / "compass")


def test_claude_invocations_close_stdin(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    captured: list[dict] = []
    real_run = subprocess.run

    def spy(args, *a, **kw):
        if args and args[0] == str(fake_claude) and "-p" in args:
            captured.append(kw)
        return real_run(args, *a, **kw)

    monkeypatch.setattr(subprocess, "run", spy)
    _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-stdin",
    )
    assert captured
    for kwargs in captured:
        assert kwargs.get("stdin") is subprocess.DEVNULL


def test_tail_keeps_only_the_last_characters():
    long_text = "x" * 2500 + "END"
    tail = harness._tail(long_text)
    assert len(tail) == 2000
    assert tail.endswith("END")


def test_tail_of_empty_text_is_empty():
    assert harness._tail("") == ""


# --- 3. the allow-list -------------------------------------------------------

def test_allow_list_matches_the_design_exactly():
    assert harness.ALLOWED_TOOLS == (
        "Read", "Write", "Edit",
        "Bash(python3 -m pytest:*)", "Bash(pytest:*)",
        "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
        "Bash(git add:*)", "Bash(git commit:*)",
        "Bash(compass:*)", "Bash(ls:*)", "Bash(cat:*)",
    )
    assert "Bash(python3:*)" not in harness.ALLOWED_TOOLS
    assert "Bash(git:*)" not in harness.ALLOWED_TOOLS


def test_both_conditions_pass_settings_and_allow_list(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    for condition in ("compass", "bare"):
        calls, _, _ = _run_condition(
            tmp_path, scenario_dir, fake_claude, condition, monkeypatch,
            plugin_source_dir, out_suffix=f"-{condition}",
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


# --- 4. the budget caps the whole run ---------------------------------------

def test_budget_caps_the_whole_run_not_each_call(
    tmp_path, fake_claude, plugin_source_dir, monkeypatch
):
    scenario_dir = _write_scenario(
        tmp_path, follow_ups=["first follow-up", "second follow-up"],
        budget_usd=3.0,
    )
    calls, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-budget", extra_config={"cost": 2.9},
    )

    assert len(calls) == 2
    second_args = calls[1]["args"]
    assert float(second_args[second_args.index("--max-budget-usd") + 1]) == \
        pytest.approx(0.1)
    assert record["cost_usd"] == pytest.approx(5.8)
    assert record["stop_reason"] == "error_max_budget_usd"
    assert record["finished"] is False


def test_follow_up_is_sent_with_resume_and_the_session_id(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    calls, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir,
    )
    assert len(calls) == 2
    first_args, second_args = calls[0]["args"], calls[1]["args"]

    assert "--resume" in second_args
    resumed_id = second_args[second_args.index("--resume") + 1]
    assert resumed_id == "fake-session-0001"
    assert record["session_id"] == "fake-session-0001"
    assert "--resume" not in first_args


# --- 5. containment ----------------------------------------------------------

def test_containment_flags_a_write_outside_the_temporary_repository(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    escape_target = plugin_source_dir / "ESCAPED.txt"
    _, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-escaped",
        extra_config={"escape_path": str(escape_target)},
    )
    assert record["contained"] is False
    assert "checkout:ESCAPED.txt" in record["escaped_paths"]


def test_containment_is_clean_when_nothing_reaches_outside(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    _, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-clean",
    )
    assert record["contained"] is True
    assert record["escaped_paths"] == []


def test_dir_snapshot_changed_paths_detects_added_changed_and_removed():
    before = {"a.txt": "hash-a", "b.txt": "hash-b"}
    after = {"a.txt": "hash-a-changed", "c.txt": "hash-c"}
    assert harness._dir_snapshot_changed_paths(before, after) == \
        ["a.txt", "b.txt", "c.txt"]


def test_checkout_changed_paths_reports_only_what_moved():
    before = {"head": "sha1", "status": " M existing.txt\n", "diff": ""}
    after = {"head": "sha1", "status": " M existing.txt\n?? new.txt\n", "diff": ""}
    assert harness._checkout_changed_paths(before, after) == ["new.txt"]

    after_new_head = {"head": "sha2", "status": " M existing.txt\n", "diff": ""}
    assert harness._checkout_changed_paths(before, after_new_head) == ["HEAD"]


# --- 6. the record -----------------------------------------------------------

def test_run_record_has_every_field_from_the_design(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    calls, record, out_path = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir,
    )

    assert set(record.keys()) == {
        "scenario", "condition", "run", "started", "seconds", "exit_code",
        "cost_usd", "session_id", "cwd", "model", "claude_version",
        "stop_reason", "finished", "tool_calls", "texts",
        "permission_denials", "final_text", "diff", "changed_paths",
        "compass_files", "tests_after", "contained", "escaped_paths",
        "stderr_tail",
    }
    assert record["scenario"] == "pressure-fixture"
    assert record["condition"] == "compass"
    assert record["run"] == 1
    assert record["exit_code"] == 0
    assert record["cwd"] == calls[0]["cwd"]
    assert record["model"] == "fake-model-1"
    assert record["claude_version"] == "fake-claude 9.9.9"
    assert record["stop_reason"] == "success"
    assert record["finished"] is True
    assert record["permission_denials"] == []

    # Two tool calls per invocation, two invocations (the prompt and the
    # one follow-up), each recorded in call order.
    assert [c["index"] for c in record["tool_calls"]] == [0, 1, 2, 3]
    for call in record["tool_calls"]:
        assert set(call.keys()) == {
            "index", "name", "input", "is_error", "denied", "output",
        }
        assert call["denied"] is False
    assert record["tool_calls"][0]["name"] == "Read"
    assert record["tool_calls"][1]["name"] == "Edit"
    assert record["cost_usd"] == pytest.approx(0.04)
    assert record["final_text"] == "fixed it"

    assert record["texts"] == [
        {"before_tool_call": 0, "text": "about to look at seed.txt"},
        {"before_tool_call": 2, "text": "fixed it"},
        {"before_tool_call": 2, "text": "about to look at seed.txt"},
        {"before_tool_call": 4, "text": "fixed it"},
    ]

    assert "seed.txt" in record["diff"]
    assert record["changed_paths"] == ["seed.txt"]

    assert record["compass_files"] == [
        ".compass/marker-from-init.txt",
        ".compass/work/fixture-issue/manifest.yml",
    ]

    assert record["tests_after"] == {
        "command": "python3 run_tests.py", "exit_code": 0,
    }

    assert record["contained"] is True
    assert record["escaped_paths"] == []
    assert isinstance(record["stderr_tail"], str)

    assert out_path.name == "pressure-fixture-compass-1.json"


def test_denied_flag_from_permission_denials_and_from_a_refusal_message(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    _, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-denied",
        extra_config={"deny_tool": "Edit"},
    )
    by_name = {call["name"]: call for call in record["tool_calls"]}
    assert by_name["Edit"]["denied"] is True
    assert by_name["Edit"]["is_error"] is True
    assert by_name["Read"]["denied"] is False
    assert record["permission_denials"]


def test_each_run_starts_from_a_fresh_repository_with_only_the_seed(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    compass_calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir, out_suffix="-fresh",
    )
    listing = set(compass_calls[0]["listing"])
    assert listing == {
        "seed.txt",
        "run_tests.py",
        os.path.join(".compass", "work", "fixture-issue", "manifest.yml"),
        os.path.join(".compass", "marker-from-init.txt"),
    }

    bare_calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-fresh",
    )
    listing = set(bare_calls[0]["listing"])
    assert listing == {"seed.txt", "run_tests.py", "PLAN.md"}


# --- 7. the seed copy leaves out __pycache__ and *.pyc ----------------------

def test_seed_copy_leaves_out_pycache_and_pyc_files(
    tmp_path, fake_claude, plugin_source_dir, monkeypatch
):
    scenario_dir = _write_scenario(tmp_path)
    pycache_dir = scenario_dir / "seed" / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "run_tests.cpython-311.pyc").write_bytes(b"\x00\x01")
    (scenario_dir / "seed" / "stray.pyc").write_bytes(b"\x00\x01")

    calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-pycache",
    )
    listing = calls[0]["listing"]
    assert not any("__pycache__" in path for path in listing)
    assert not any(path.endswith(".pyc") for path in listing)


# --- 8. plain text ------------------------------------------------------------

def test_module_docstring_does_not_explain_by_how_the_issue_split_its_work():
    text = (harness.__doc__ or "").lower()
    assert "sibling" not in text
    assert "this issue" not in text


# --- scenario.yml is read through the shared loader (compass_pkg.core.load_yaml) --

def test_load_scenario_raises_compass_error_for_a_missing_file(tmp_path):
    from compass_pkg.core import CompassError

    scenario_dir = tmp_path / "no-scenario-here"
    scenario_dir.mkdir()

    with pytest.raises(CompassError):
        harness.load_scenario(scenario_dir)


def test_load_scenario_raises_compass_error_for_invalid_yaml(tmp_path):
    from compass_pkg.core import CompassError

    scenario_dir = tmp_path / "broken-scenario"
    scenario_dir.mkdir()
    (scenario_dir / "scenario.yml").write_text(
        "id: [unclosed\n", encoding="utf-8"
    )

    with pytest.raises(CompassError):
        harness.load_scenario(scenario_dir)


def test_load_scenario_returns_defaults_for_an_empty_file(tmp_path):
    scenario_dir = tmp_path / "empty-scenario"
    scenario_dir.mkdir()
    (scenario_dir / "scenario.yml").write_text("", encoding="utf-8")

    data = harness.load_scenario(scenario_dir)

    assert data == {"follow_ups": [], "test_command": "python3 -m pytest -q"}
