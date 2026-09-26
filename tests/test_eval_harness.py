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
from datetime import date, timedelta
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
import subprocess
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
        # The seed commit's author and committer, read now because the
        # harness deletes the repository once the call returns - the same
        # allowed `git log` a real session could run.
        "git_log_identity": subprocess.run(
            ["git", "log", "-1", "--format=%an <%ae> %cn <%ce>"],
            cwd=cwd, capture_output=True, text=True,
        ).stdout.strip(),
    }

    # The plugin copy the harness built for this call, if any - inspected
    # now, from inside the call, because the harness deletes it once the
    # call returns.
    if "--plugin-dir" in sys.argv:
        plugin_dir = sys.argv[sys.argv.index("--plugin-dir") + 1]
        readme = os.path.join(plugin_dir, "README.md")
        compass_bin = os.path.join(plugin_dir, "bin", "compass")
        tests_dir = os.path.join(plugin_dir, "tests")
        docs_compass_dir = os.path.join(plugin_dir, "docs", "compass")
        docs_releasing = os.path.join(plugin_dir, "docs", "releasing.md")
        record["plugin_copy"] = {
            "dir_writable": os.access(plugin_dir, os.W_OK),
            "readme_text": (open(readme, encoding="utf-8").read()
                             if os.path.isfile(readme) else None),
            "readme_writable": os.access(readme, os.W_OK),
            "compass_executable": os.access(compass_bin, os.X_OK),
            "evals_dir_exists": os.path.isdir(os.path.join(plugin_dir, "evals")),
            "tests_listing": (sorted(os.listdir(tests_dir))
                               if os.path.isdir(tests_dir) else []),
            "docs_compass_listing": (sorted(os.listdir(docs_compass_dir))
                                      if os.path.isdir(docs_compass_dir) else []),
            "docs_releasing_exists": os.path.isfile(docs_releasing),
        }

    with open(config["log_path"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")

    # A test that wants a call to make no code edit - to check the
    # continuation reply's own trigger, not its cap - sets "no_edit".
    target = os.path.join(cwd, "seed.txt")
    if os.path.isfile(target) and not config.get("no_edit"):
        with open(target, "a", encoding="utf-8") as fh:
            fh.write("edited by the fake CLI\\n")

    escape_path = config.get("escape_path")
    if escape_path:
        os.makedirs(os.path.dirname(escape_path), exist_ok=True)
        with open(escape_path, "a", encoding="utf-8") as fh:
            fh.write("reached from outside the temporary repository\\n")

    if config.get("create_pyc"):
        pycache_dir = os.path.join(cwd, "src", "__pycache__")
        os.makedirs(pycache_dir, exist_ok=True)
        with open(os.path.join(pycache_dir, "inventory.cpython-311.pyc"), "wb") as fh:
            fh.write(b"\\x00\\x01compiled")

    # A test that wants a fresh, untracked path in the seed - to check
    # `changed`'s own "A" status - sets "add_path".
    add_path = config.get("add_path")
    if add_path:
        full = os.path.join(cwd, add_path)
        parent = os.path.dirname(full)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write("added by the fake CLI\\n")

    # A test that wants a seed path removed - to check `changed`'s own "D"
    # status - sets "delete_path".
    delete_path = config.get("delete_path")
    if delete_path:
        full = os.path.join(cwd, delete_path)
        if os.path.isfile(full):
            os.remove(full)

    # A test that wants a second issue directory under `.compass/work/` - to
    # check `manifests` holds more than one - sets "second_manifest_slug".
    second_manifest_slug = config.get("second_manifest_slug")
    if second_manifest_slug:
        manifest_dir = os.path.join(cwd, ".compass", "work", second_manifest_slug)
        os.makedirs(manifest_dir, exist_ok=True)
        with open(os.path.join(manifest_dir, "manifest.yml"), "w",
                  encoding="utf-8") as fh:
            fh.write("issue: " + second_manifest_slug + "\\nstatus: active\\n")

    cost = float(config.get("cost", 0.02))
    session_id = "fake-session-0001"
    deny_tool = config.get("deny_tool")
    closing_text = "fixed it"

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
            {"type": "text", "text": closing_text},
        ]}},
        {"type": "result", "subtype": config.get("result_subtype", "success"),
         "session_id": session_id,
         "total_cost_usd": cost, "result": closing_text,
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
                     budget_usd: float = 3.0,
                     continue_reply: str | None = None) -> Path:
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
    if continue_reply is not None:
        scenario_yml["continue_reply"] = continue_reply
    with (scenario_dir / "scenario.yml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(scenario_yml, fh, sort_keys=False)

    # The harness now copies only a scenario's own git-tracked files, the
    # same way it reads the real evals/scenarios/ tree, so this fixture
    # must be a git repository too - otherwise nothing would be tracked and
    # the harness would copy nothing.
    _git_commit_all(scenario_dir, "scenario fixture")
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


def _write_plugin_repo(root: Path, *, init_exit_code: int = 0,
                        write_config_yml: bool = False) -> Path:
    """A small git repository standing in for this checkout - the compass
    condition's plugin source, so a test never archives the real one.
    `init_exit_code` lets a test give this fixture's own `compass init` a
    failure, without touching the real CLI. `write_config_yml` makes that
    same `init` also stamp `.compass/config.yml` with today's date, the way
    the real CLI's own template does, for a test that checks the harness
    backdates it."""
    root.mkdir(parents=True, exist_ok=True)
    bin_dir = root / "bin"
    bin_dir.mkdir()
    compass_script = bin_dir / "compass"
    config_yml_block = (
        "    import datetime\n"
        "    _stamp = datetime.date.today().isoformat()\n"
        "    with open(os.path.join('.compass', 'config.yml'), 'w',\n"
        "              encoding='utf-8') as cfg:\n"
        "        cfg.write('initialised:\\n  by: \"compass init\"\\n  at: \"'"
        " + _stamp + '\"\\n')\n"
        "        cfg.write(\"records_signed_since: '\" + _stamp + \"'\\n\")\n"
    ) if write_config_yml else ""
    compass_script.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "import sys\n"
        "\n"
        "if sys.argv[1:2] == ['init']:\n"
        f"    if {init_exit_code} != 0:\n"
        "        sys.stderr.write('fixture compass init failed\\n')\n"
        f"        sys.exit({init_exit_code})\n"
        "    os.makedirs('.compass', exist_ok=True)\n"
        "    with open(os.path.join('.compass', 'marker-from-init.txt'), 'w',\n"
        "              encoding='utf-8') as handle:\n"
        "        handle.write('the plugin copy ran compass init here\\n')\n"
        f"{config_yml_block}"
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
    evals_dir = root / "evals" / "scenarios" / "fixture-scenario"
    evals_dir.mkdir(parents=True)
    (evals_dir / "scenario.yml").write_text(
        "failure_mode: what this fixture scenario measures\n", encoding="utf-8"
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


def test_plugin_copy_leaves_out_evals(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    """A compass session could `Read` the scenario's own rubric out of the
    plugin copy, one path away from the hook refusal it saw. `evals/` never
    reaches the copy."""
    calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir, out_suffix="-no-evals",
    )
    assert calls[0]["plugin_copy"]["evals_dir_exists"] is False
    # the fixture plugin source still has it - the harness leaves it out,
    # the source never loses it.
    assert (plugin_source_dir / "evals" / "scenarios" / "fixture-scenario"
            / "scenario.yml").is_file()


def test_plugin_copy_leaves_out_test_eval_files(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    """A probe session read tests/test_eval_scenarios.py out of the plugin
    copy and learned a scenario's rubric from its first line, one `Read`
    away from the hook refusal it saw. Every tests/test_eval_*.py must be
    left out too, not only evals/ itself."""
    tests_dir = plugin_source_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_eval_scenarios.py").write_text(
        "the rubric this file would give away\n", encoding="utf-8")
    (tests_dir / "test_eval_harness.py").write_text(
        "this file's own rubric-adjacent text\n", encoding="utf-8")
    (tests_dir / "test_terminology.py").write_text(
        "an ordinary repository test, kept\n", encoding="utf-8")
    _git_commit_all(plugin_source_dir, "add test files")

    calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir, out_suffix="-no-eval-tests",
    )
    tests_listing = calls[0]["plugin_copy"]["tests_listing"]
    assert tests_listing == ["test_terminology.py"]
    # the fixture plugin source still has both files - the harness leaves
    # them out, the source never loses them.
    assert (plugin_source_dir / "tests" / "test_eval_scenarios.py").is_file()
    assert (plugin_source_dir / "tests" / "test_eval_harness.py").is_file()


def test_bare_condition_gets_no_plugin_dir(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir,
    )
    assert "--plugin-dir" not in calls[0]["args"]


def test_compass_condition_also_gets_add_dir_for_the_plugin_copy(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    """Three real compass sessions had `cat templates/manifest.yml` refused
    because the plugin copy sits outside the working directory. `--add-dir`
    admits it, alongside `--plugin-dir`."""
    calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir, out_suffix="-add-dir",
    )
    args = calls[0]["args"]
    plugin_dir_arg = args[args.index("--plugin-dir") + 1]
    assert "--add-dir" in args
    assert args[args.index("--add-dir") + 1] == plugin_dir_arg


def test_bare_condition_gets_no_add_dir(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-no-add-dir",
    )
    assert "--add-dir" not in calls[0]["args"]


def test_plugin_copy_leaves_out_docs_compass_eval_reports(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    """A published eval report under `docs/compass/` would tell a later
    compass session everything a scenario is scored on. It must be as
    unreadable as `evals/` itself, while an ordinary issue directory - one
    whose name does not say "eval" - still travels."""
    docs_compass_dir = plugin_source_dir / "docs" / "compass"
    docs_compass_dir.mkdir(parents=True)
    (docs_compass_dir / "2026-09-26-eval-pilot.md").write_text(
        "the published pilot report\n", encoding="utf-8")
    kept_dir = docs_compass_dir / "2026-09-26-an-ordinary-issue"
    kept_dir.mkdir()
    (kept_dir / "intent.md").write_text("an ordinary issue document\n",
                                         encoding="utf-8")
    _git_commit_all(plugin_source_dir, "add docs/compass files")

    calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir, out_suffix="-no-eval-docs",
    )
    docs_listing = calls[0]["plugin_copy"]["docs_compass_listing"]
    assert docs_listing == ["2026-09-26-an-ordinary-issue"]
    # the fixture plugin source still has both - the harness leaves the
    # report out, the source never loses it.
    assert (docs_compass_dir / "2026-09-26-eval-pilot.md").is_file()


def test_plugin_copy_leaves_out_the_releasing_guide(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    """`docs/releasing.md` names the harness and the two conditions by name,
    the same kind of leak the eval reports under `docs/compass/` are left
    out for. A compass session must not read it inside the plugin copy."""
    docs_dir = plugin_source_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "releasing.md").write_text(
        "how a release runs the eval scenarios before merging\n",
        encoding="utf-8")
    _git_commit_all(plugin_source_dir, "add docs/releasing.md")

    calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir, out_suffix="-no-releasing-doc",
    )
    assert calls[0]["plugin_copy"]["docs_releasing_exists"] is False
    # the fixture plugin source still has it - the harness leaves it out,
    # the source never loses it.
    assert (docs_dir / "releasing.md").is_file()


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


def test_head_and_tail_keeps_the_first_1000_and_the_last_3000_characters():
    text = "A" * 1000 + "middle text nobody keeps" * 200 + "Z" * 3000
    kept = harness._head_and_tail(text)
    assert len(kept) == 4000
    assert kept.startswith("A" * 1000)
    assert kept.endswith("Z" * 3000)


def test_head_and_tail_returns_the_whole_text_when_it_is_short():
    text = "short tool output\n"
    assert harness._head_and_tail(text) == text


def test_consume_events_truncates_a_long_tool_output_keeping_start_and_end():
    """Plain `pytest` with three failures printed 2,335 characters and its
    summary line, the last one, was lost when only the first 2,000 were
    kept. Keeping the last characters too keeps a late summary line."""
    summary_line = "1 failed, 2 passed in 0.01s"
    long_output = ("HEAD" * 250) + ("MIDDLE" * 700) + summary_line
    events = [
        {"type": "system", "subtype": "init", "session_id": "s1",
         "cwd": "/tmp/fixture", "model": "m"},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {}},
        ]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1",
             "content": long_output, "is_error": False},
        ]}},
    ]
    text = "\n".join(json.dumps(event) for event in events)
    state = harness._new_run_state()
    harness._consume_events(text, state)

    output = state["tool_calls"][0]["output"]
    assert len(output) == 4000
    assert output.startswith("HEAD")
    assert output.endswith(summary_line)


# --- 3. the allow-list -------------------------------------------------------

def test_allow_list_matches_the_design_exactly():
    """The allow-list: `Skill` so a compass session can run a `/compass:*`
    command, `python -m pytest` alongside `python3 -m pytest`, `cat` on the
    list - Compass's own commands, such as `/compass:quick-fix`, read their
    own template with it, and a `cat >` onto a protected path is caught by
    `no_evidence_tampering` - and `head`, `tail` and `grep`, the other
    read-only commands those same commands use against the plugin copy."""
    assert harness.ALLOWED_TOOLS == (
        "Read", "Write", "Edit", "Skill",
        "Bash(python3 -m pytest:*)", "Bash(python -m pytest:*)", "Bash(pytest:*)",
        "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
        "Bash(git add:*)", "Bash(git commit:*)",
        "Bash(compass:*)", "Bash(ls:*)", "Bash(cat:*)",
        "Bash(head:*)", "Bash(tail:*)", "Bash(grep:*)",
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


def test_over_budget_flag_when_one_turn_overruns_a_finished_run(
    tmp_path, fake_claude, plugin_source_dir, monkeypatch
):
    """Claude Code checks `--max-budget-usd` between turns, so a single call
    can spend past what was left and still end `success`, with no way to
    see the overrun. `finished` still follows the `result` subtype;
    `over_budget` says the cost passed the budget."""
    scenario_dir = _write_scenario(tmp_path, follow_ups=[], budget_usd=0.25)
    _, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir, out_suffix="-overrun", extra_config={"cost": 0.353},
    )
    assert record["stop_reason"] == "success"
    assert record["finished"] is True
    assert record["cost_usd"] == pytest.approx(0.353)
    assert record["over_budget"] is True


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


def test_containment_flags_a_change_inside_an_untracked_directory(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    """An untracked directory can hold a change that a status code check
    cannot see - a whole new directory collapses to one `??` line either
    way. A content hash catches a change inside it too."""
    escape_target = plugin_source_dir / "new-untracked-dir" / "inside.txt"
    _, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-escaped-dir",
        extra_config={"escape_path": str(escape_target)},
    )
    assert record["contained"] is False
    assert "checkout:new-untracked-dir/inside.txt" in record["escaped_paths"]


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


def test_checkout_fingerprint_catches_a_second_edit_to_an_already_modified_file(
    tmp_path,
):
    """`git status`'s code for a changed tracked file reads `M` both before
    and after a further edit, so a status based check misses it. Hashing
    the content does not."""
    repo = tmp_path / "checkout"
    repo.mkdir()
    (repo / "tracked.txt").write_text("original\n", encoding="utf-8")
    _git_commit_all(repo, "initial")

    (repo / "tracked.txt").write_text("first edit\n", encoding="utf-8")
    before = harness._checkout_fingerprint(repo)

    (repo / "tracked.txt").write_text("second edit\n", encoding="utf-8")
    after = harness._checkout_fingerprint(repo)

    assert harness._dir_snapshot_changed_paths(before, after) == ["tracked.txt"]


def test_checkout_fingerprint_recurses_into_an_untracked_directory(tmp_path):
    """`git status --porcelain` collapses a whole new directory to one `??`
    line, so a change inside it is invisible to a status based check.
    `git ls-files --others` lists the files inside it, so a further edit
    inside the directory is caught too."""
    repo = tmp_path / "checkout"
    repo.mkdir()
    (repo / "tracked.txt").write_text("original\n", encoding="utf-8")
    _git_commit_all(repo, "initial")
    before = harness._checkout_fingerprint(repo)

    new_dir = repo / "new-untracked-dir"
    new_dir.mkdir()
    (new_dir / "inside.txt").write_text("first\n", encoding="utf-8")
    after_created = harness._checkout_fingerprint(repo)
    assert harness._dir_snapshot_changed_paths(before, after_created) == \
        ["new-untracked-dir/inside.txt"]

    (new_dir / "inside.txt").write_text("second\n", encoding="utf-8")
    after_edited = harness._checkout_fingerprint(repo)
    assert harness._dir_snapshot_changed_paths(after_created, after_edited) == \
        ["new-untracked-dir/inside.txt"]


def test_checkout_fingerprint_is_unchanged_when_nothing_moved(tmp_path):
    repo = tmp_path / "checkout"
    repo.mkdir()
    (repo / "tracked.txt").write_text("original\n", encoding="utf-8")
    _git_commit_all(repo, "initial")
    before = harness._checkout_fingerprint(repo)
    after = harness._checkout_fingerprint(repo)
    assert harness._dir_snapshot_changed_paths(before, after) == []


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
        "compass_files", "changed", "manifests", "tests_after", "contained",
        "escaped_paths", "stderr_tail", "over_budget", "replies_sent",
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
    assert record["changed"] == [{"path": "seed.txt", "status": "M"}]

    assert record["compass_files"] == [
        ".compass/marker-from-init.txt",
        ".compass/work/fixture-issue/manifest.yml",
    ]
    assert record["manifests"] == {
        ".compass/work/fixture-issue/manifest.yml":
            "issue: fixture-issue\nstatus: active\n",
    }

    assert record["tests_after"] == {
        "command": "python3 run_tests.py", "exit_code": 0,
    }

    assert record["contained"] is True
    assert record["escaped_paths"] == []
    assert isinstance(record["stderr_tail"], str)
    assert record["over_budget"] is False
    assert record["replies_sent"] == 0

    assert out_path.name == "pressure-fixture-compass-1.json"


def test_changed_reports_an_added_and_a_deleted_path(
    tmp_path, fake_claude, plugin_source_dir, monkeypatch
):
    """`changed` is judge.py's own end-state input: a status per path, not
    only a diff of the text, so a rule can tell whether a path was added,
    changed or deleted since the seed."""
    scenario_dir = _write_scenario(tmp_path, follow_ups=[])
    _, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-changed-add-delete",
        extra_config={"no_edit": True, "add_path": "new_file.txt",
                      "delete_path": "run_tests.py"},
    )
    by_path = {entry["path"]: entry["status"] for entry in record["changed"]}
    assert by_path["new_file.txt"] == "A"
    assert by_path["run_tests.py"] == "D"


def test_manifests_holds_more_than_one_issue_directory(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    """`manifests` is the content of every `.compass/work/*/manifest.yml` at
    the end, not only the one the seed started with - a second issue
    directory, however created, still shows up."""
    _, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir, out_suffix="-manifests-two",
        extra_config={"second_manifest_slug": "second-issue"},
    )
    assert set(record["manifests"]) == {
        ".compass/work/fixture-issue/manifest.yml",
        ".compass/work/second-issue/manifest.yml",
    }
    assert "second-issue" in record["manifests"][".compass/work/second-issue/manifest.yml"]


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


def test_seed_copy_uses_only_git_tracked_files(
    tmp_path, fake_claude, plugin_source_dir, monkeypatch
):
    """A seed copied straight from the working tree carries a local file such
    as `.pytest_cache/` along with it, and that directory can name a failing
    test the seed never committed. Only the seed's own git-tracked files
    travel into a run."""
    scenario_dir = _write_scenario(tmp_path)
    stray_dir = scenario_dir / "seed" / ".pytest_cache" / "v" / "cache"
    stray_dir.mkdir(parents=True)
    (stray_dir / "lastfailed").write_text("{}\n", encoding="utf-8")

    calls, _, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-tracked-only",
    )
    listing = calls[0]["listing"]
    assert not any(".pytest_cache" in path for path in listing)
    assert set(listing) == {"seed.txt", "run_tests.py", "PLAN.md"}


def test_seed_commit_message_and_no_tag(tmp_path):
    """Six rounds of real sessions never ran `git tag`, so nothing needs one:
    the harness keeps the seed commit's own id and marks it no other way.
    `git log --decorate` must show no `tag: seed`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "seed.txt").write_text("original\n", encoding="utf-8")
    seed_commit = harness._git_init_and_commit(repo)

    message = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=str(repo),
        capture_output=True, text=True,
    ).stdout.strip()
    assert message == "Initial commit"

    tags = subprocess.run(
        ["git", "tag"], cwd=str(repo), capture_output=True, text=True,
    ).stdout.strip()
    assert tags == ""

    decorated = subprocess.run(
        ["git", "log", "--decorate", "-1"], cwd=str(repo),
        capture_output=True, text=True,
    ).stdout
    assert "tag: seed" not in decorated

    diff = subprocess.run(
        ["git", "diff", seed_commit], cwd=str(repo), capture_output=True, text=True,
    )
    assert diff.returncode == 0


# --- 8. plain text ------------------------------------------------------------

def test_module_docstring_does_not_explain_by_how_the_issue_split_its_work():
    text = (harness.__doc__ or "").lower()
    assert "sibling" not in text
    assert "this issue" not in text


def test_no_bare_defect_id_cited_without_its_meaning():
    """Say what a rule is in the comment, not a bare id nobody outside a
    review can look up."""
    source = Path(harness.__file__).read_text(encoding="utf-8")
    assert "DD-2" not in source
    assert "compass_pkg.core.load_yaml" in source


def test_no_citation_of_a_document_this_repository_does_not_have():
    """A design document and a round's review each live only under
    `docs/compass/*/`, which `.gitignore` excludes - a comment naming one
    points a reader at a file they cannot open. State the rule plainly in
    the comment instead."""
    # Built by concatenation, not as one literal, so this check does not
    # fail on its own source text.
    banned = "technical-design" + ".md", "integrated-" + "review"
    harness_source = Path(harness.__file__).read_text(encoding="utf-8")
    test_source = Path(__file__).read_text(encoding="utf-8")
    for source in (harness_source, test_source):
        for phrase in banned:
            assert phrase not in source


# --- 9. a session's own .pyc files never reach changed_paths ----------------

def test_session_pyc_files_are_excluded_from_changed_paths(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    """A session that runs its tests leaves `__pycache__/*.pyc` files that
    `git add -A` would otherwise stage, which stopped the judge placing the
    first code edit. The harness writes `.git/info/exclude` before the seed
    commit so they never appear."""
    _, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-pyc",
        extra_config={"create_pyc": True},
    )
    assert not any(path.endswith(".pyc") for path in record["changed_paths"])
    assert not any("__pycache__" in path for path in record["changed_paths"])
    assert "src/__pycache__/inventory.cpython-311.pyc" not in record["diff"]


# --- 10. no MCP server reaches the session -----------------------------------

def test_no_mcp_server_reaches_the_session(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    """A real session listed the maintainer's own Slack and Drive connectors
    among its tools. Both conditions must load none."""
    for condition in ("compass", "bare"):
        calls, _, _ = _run_condition(
            tmp_path, scenario_dir, fake_claude, condition, monkeypatch,
            plugin_source_dir, out_suffix=f"-mcp-{condition}",
        )
        assert "--strict-mcp-config" in calls[0]["args"]


# --- 11. no temporary directory name says which condition it is -------------

def test_temporary_directory_names_do_not_name_the_scenario_or_condition(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    """Every temporary directory, the repository and the plugin copy alike,
    takes the system's default temporary name: no prefix names the scenario
    or the condition, so a real session cannot tell from its own working
    directory that it is under evaluation."""
    scenario_id = "pressure-fixture"

    compass_calls, compass_record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir, out_suffix="-naming",
    )
    bare_calls, bare_record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-naming",
    )
    assert compass_record["scenario"] == scenario_id

    compass_repo_name = Path(compass_record["cwd"]).name
    bare_repo_name = Path(bare_record["cwd"]).name
    for name in (compass_repo_name, bare_repo_name):
        assert scenario_id not in name
        assert "compass" not in name
        assert "bare" not in name
        assert "eval" not in name

    plugin_dir_arg = compass_calls[0]["args"][
        compass_calls[0]["args"].index("--plugin-dir") + 1
    ]
    plugin_copy_name = Path(plugin_dir_arg).name
    assert scenario_id not in plugin_copy_name
    assert "eval" not in plugin_copy_name


# --- 12. the seed commit's author is an ordinary name, not the harness's own -

def test_seed_commit_author_is_an_ordinary_name(tmp_path):
    """The seed commit's author is an ordinary name and address - a real
    compass session could run the allowed `git log` and read a name naming
    this evaluation off the seed commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "seed.txt").write_text("original\n", encoding="utf-8")
    harness._git_init_and_commit(repo)

    identity = subprocess.run(
        ["git", "log", "-1", "--format=%an <%ae> %cn <%ce>"],
        cwd=str(repo), capture_output=True, text=True,
    ).stdout.strip()
    assert "eval" not in identity.lower()
    assert "compass" not in identity.lower()


# --- 13. nothing a session can see says it is under test --------------------

def test_no_visible_name_says_it_is_under_test_or_names_the_scenario(
    tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch
):
    """Checks every temporary path and the seed commit's author together, so
    a name reintroduced in either place is caught."""
    scenario_id = "pressure-fixture"
    forbidden = ("eval", "compass", scenario_id)

    compass_calls, compass_record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir, out_suffix="-tell",
    )
    bare_calls, bare_record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-tell",
    )

    plugin_dir_arg = compass_calls[0]["args"][
        compass_calls[0]["args"].index("--plugin-dir") + 1
    ]
    texts = [
        Path(compass_record["cwd"]).name,
        Path(bare_record["cwd"]).name,
        Path(plugin_dir_arg).name,
        compass_calls[0]["git_log_identity"],
        bare_calls[0]["git_log_identity"],
    ]
    for text in texts:
        lowered = text.lower()
        for word in forbidden:
            assert word not in lowered, f"{word!r} found in {text!r}"


# --- 14. a scenario with continue_reply gets it once, before a code edit ---

def test_continue_reply_sent_once_when_no_code_edit_has_happened_yet(
    tmp_path, fake_claude, plugin_source_dir, monkeypatch
):
    """A session run under `-p` gets no answer to a question of its own, so
    it never reaches a decision on its own. The round 5 review found that
    guessing the question from a trailing `?` missed most of them, so the
    trigger is now whether the work has happened, not the wording of the
    last message: while no non-test path in `in_scope` has changed against
    the seed yet, the harness sends the scenario's own `continue_reply`,
    with `--resume` and the run's remaining budget, before the next
    follow-up."""
    scenario_dir = _write_scenario(
        tmp_path, follow_ups=["first follow-up"],
        continue_reply="Go ahead with whichever option you recommend.",
    )
    calls, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-continue",
        extra_config={"no_edit": True},
    )
    assert len(calls) == 3

    reply_args = calls[1]["args"]
    assert reply_args[reply_args.index("-p") + 1] == \
        "Go ahead with whichever option you recommend."
    assert "--resume" in reply_args
    assert reply_args[reply_args.index("--resume") + 1] == "fake-session-0001"
    # the default fixture scenario has a $3.00 budget and the fake CLI
    # reports a $0.02 cost per call, so $2.98 is left after the initial call.
    assert float(
        reply_args[reply_args.index("--max-budget-usd") + 1]
    ) == pytest.approx(2.98)

    follow_up_args = calls[2]["args"]
    assert follow_up_args[follow_up_args.index("-p") + 1] == "first follow-up"

    assert record["replies_sent"] == 1


def test_no_continue_reply_once_a_code_edit_has_happened(
    tmp_path, fake_claude, plugin_source_dir, monkeypatch
):
    """The fixture's fake CLI edits seed.txt - a path inside `in_scope` - on
    every call by default, so the first call has already done the work the
    reply exists to unblock, and none is sent."""
    scenario_dir = _write_scenario(
        tmp_path, follow_ups=["first follow-up"],
        continue_reply="Go ahead with whichever option you recommend.",
    )
    calls, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-continue-edited",
    )
    assert len(calls) == 2
    assert record["replies_sent"] == 0


def test_no_continue_reply_for_a_scenario_without_the_field(
    tmp_path, fake_claude, plugin_source_dir, monkeypatch
):
    """A scenario with no `continue_reply` never gets one, even when no
    code edit has happened yet - the reply's wording is the maintainer's
    own call, opted into per scenario, never a default the harness
    invents."""
    scenario_dir = _write_scenario(tmp_path, follow_ups=["first follow-up"])
    calls, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-no-field",
        extra_config={"no_edit": True},
    )
    assert len(calls) == 2
    assert record["replies_sent"] == 0


def test_continue_reply_sent_at_most_once_per_run(
    tmp_path, fake_claude, plugin_source_dir, monkeypatch
):
    """No call ever makes a code edit under this test's fixture, so the cap
    - not the trigger - is what is under test: still one reply for the
    whole run."""
    scenario_dir = _write_scenario(
        tmp_path, follow_ups=["first follow-up", "second follow-up"],
        continue_reply="Go ahead with whichever option you recommend.",
    )
    calls, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "compass", monkeypatch,
        plugin_source_dir, out_suffix="-continue-cap",
        extra_config={"no_edit": True},
    )
    # initial call, one continuation reply, then both scheduled follow-ups -
    # no second reply even though no call ever makes a code edit.
    assert len(calls) == 4
    assert record["replies_sent"] == 1


def test_continue_reply_applies_under_either_condition(
    tmp_path, fake_claude, plugin_source_dir, monkeypatch
):
    scenario_dir = _write_scenario(
        tmp_path, follow_ups=[],
        continue_reply="Go ahead with whichever option you recommend.",
    )
    for condition in ("compass", "bare"):
        calls, record, _ = _run_condition(
            tmp_path, scenario_dir, fake_claude, condition, monkeypatch,
            plugin_source_dir, out_suffix=f"-continue-{condition}",
            extra_config={"no_edit": True},
        )
        assert len(calls) == 2
        assert record["replies_sent"] == 1


# --- 15. a seed with no tracked file is an error, never an empty repository -

def test_copy_tracked_files_errors_when_source_is_not_a_git_repository(tmp_path):
    """A scenario directory outside a git repository gave an empty seed and
    no error: `git ls-files` fails there, and the exit status was ignored."""
    source = tmp_path / "not-a-repo"
    source.mkdir()
    (source / "seed.txt").write_text("original\n", encoding="utf-8")
    dest = tmp_path / "dest"
    dest.mkdir()

    with pytest.raises(SystemExit):
        harness._copy_tracked_files(source, dest)


def test_copy_tracked_files_errors_when_nothing_is_tracked(tmp_path):
    """A git repository with nothing committed lists no file either - the
    same silent, empty seed, from the same untested exit status."""
    source = tmp_path / "empty-repo"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(source), check=True)
    dest = tmp_path / "dest"
    dest.mkdir()

    with pytest.raises(SystemExit):
        harness._copy_tracked_files(source, dest)


def test_copy_tracked_files_still_copies_an_ordinary_tracked_seed(tmp_path):
    """The fix must not touch the ordinary case: a real seed with tracked
    files still copies exactly those files."""
    source = tmp_path / "seed-repo"
    source.mkdir()
    (source / "seed.txt").write_text("original\n", encoding="utf-8")
    _git_commit_all(source, "seed")
    dest = tmp_path / "dest"
    dest.mkdir()

    harness._copy_tracked_files(source, dest)

    assert (dest / "seed.txt").read_text(encoding="utf-8") == "original\n"


# --- 16. every diff is computed with a temporary index, never the session's -
# --- own one -----------------------------------------------------------------

def test_diff_since_seed_never_stages_into_the_repository_own_index(tmp_path):
    """`git add -A` used to run against the repository's own index while a
    session's later call could still read it with the allowed `git status` -
    a write the session never made. A temporary index (`GIT_INDEX_FILE`)
    leaves the real one exactly as the session left it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "seed.txt").write_text("original\n", encoding="utf-8")
    seed_commit = harness._git_init_and_commit(repo)
    (repo / "seed.txt").write_text("changed\n", encoding="utf-8")

    real_index = repo / ".git" / "index"
    before = real_index.read_bytes() if real_index.is_file() else None

    diff, changed_paths, changed = harness._diff_since_seed(repo, seed_commit)

    after = real_index.read_bytes() if real_index.is_file() else None
    assert before == after

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(repo),
        capture_output=True, text=True,
    ).stdout
    assert status == " M seed.txt\n"
    assert "seed.txt" in diff
    assert changed_paths == ["seed.txt"]
    assert changed == [{"path": "seed.txt", "status": "M"}]


# --- 17. a failed `compass init` is an error, never a silent empty run ------

def test_run_compass_init_raises_when_the_plugin_copy_fails(tmp_path):
    plugin_copy = _write_plugin_repo(tmp_path / "plugin-copy", init_exit_code=1)
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    with pytest.raises(SystemExit):
        harness._run_compass_init(plugin_copy, repo_dir, dict(os.environ))


def test_run_compass_init_does_not_raise_on_success(tmp_path):
    plugin_copy = _write_plugin_repo(tmp_path / "plugin-copy-ok")
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    harness._run_compass_init(plugin_copy, repo_dir, dict(os.environ))
    assert (repo_dir / ".compass" / "marker-from-init.txt").is_file()


# --- the compass condition's setup date is backdated -------------------------

def test_backdate_setup_date_rewrites_every_occurrence_of_the_stamped_date(
    tmp_path
):
    """The hook's own refusal quotes `initialised.at`, and a real compass
    session read today's date there as proof a policy could not be leftover
    config from another project. `compass init` stamps the same date into
    `records_signed_since` from the one template value it filled in, so
    rewriting every occurrence of the stamped date backdates both fields
    from that one value."""
    repo_dir = tmp_path / "repo"
    compass_dir = repo_dir / ".compass"
    compass_dir.mkdir(parents=True)
    (compass_dir / "config.yml").write_text(
        "version: 1.0.0\n"
        "mode: enforced\n"
        "initialised:\n"
        "  by: \"compass init\"\n"
        "  at: \"2026-09-27\"\n"
        "records_signed_since: '2026-09-27'\n",
        encoding="utf-8",
    )

    harness._backdate_setup_date(repo_dir)

    text = (compass_dir / "config.yml").read_text(encoding="utf-8")
    assert 'at: "2026-08-28"' in text
    assert "records_signed_since: '2026-08-28'" in text
    assert "2026-09-27" not in text


def test_backdate_setup_date_does_nothing_without_a_config_file(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    harness._backdate_setup_date(repo_dir)  # must not raise
    assert not (repo_dir / ".compass").exists()


def test_materialise_repo_backdates_the_setup_date_for_the_compass_condition(
    tmp_path
):
    """Wiring: the compass condition's own `compass init` runs, then the
    date it just stamped is rewritten, before the seed commit - so the
    backdated value is what a session's first hook refusal ever sees."""
    plugin_copy = _write_plugin_repo(tmp_path / "plugin-copy-dated",
                                      write_config_yml=True)
    scenario_dir = _write_scenario(tmp_path)
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    harness._materialise_repo(scenario_dir, "compass", repo_dir, plugin_copy,
                               dict(os.environ))

    config_text = (repo_dir / ".compass" / "config.yml").read_text(encoding="utf-8")
    today = date.today()
    backdated = (today - timedelta(days=30)).isoformat()
    assert f'at: "{backdated}"' in config_text
    assert f'at: "{today.isoformat()}"' not in config_text


# --- 18. the continuation reply follows only a call that ended `success` ----

def test_no_continue_reply_after_a_call_that_did_not_end_in_success(
    tmp_path, fake_claude, plugin_source_dir, monkeypatch
):
    """Design: the reply follows only a call whose result subtype is
    `success`. A call that ended `error_during_execution` gets none, even
    with budget left and no code edit yet."""
    scenario_dir = _write_scenario(
        tmp_path, follow_ups=["first follow-up"],
        continue_reply="Go ahead with whichever option you recommend.",
    )
    calls, record, _ = _run_condition(
        tmp_path, scenario_dir, fake_claude, "bare", monkeypatch,
        plugin_source_dir, out_suffix="-no-reply-on-error",
        extra_config={"no_edit": True, "result_subtype": "error_during_execution"},
    )
    assert len(calls) == 2
    assert record["replies_sent"] == 0


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


# --- 19. the plugin copy names nothing a scenario or a behaviour would give away --

def test_plugin_copy_of_the_real_checkout_names_no_scenario_or_behaviour(
    tmp_path
):
    """Every other test in this file stands a fixture in for this checkout,
    on purpose, so nothing depends on its tracked tree. This one is the
    exception: only the real checkout carries real scenario ids and
    behaviour ids to check against, and only its own copy shows whether a
    file outside `evals/` still names one by accident."""
    scenario_ids = sorted(
        p.parent.name
        for p in (REPO_ROOT / "evals" / "scenarios").glob("*/scenario.yml")
    )
    assert scenario_ids

    from evals import judge  # local: only this test needs the behaviour ids
    behaviour_ids = sorted(judge.BEHAVIOURS.keys())
    assert behaviour_ids

    forbidden = [*scenario_ids, *behaviour_ids, "compass condition", "bare condition"]

    dest = tmp_path / "real-plugin-copy"
    harness._make_plugin_copy(REPO_ROOT, dest)
    try:
        offences = []
        for path in dest.rglob("*"):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for term in forbidden:
                if term in text:
                    offences.append((path.relative_to(dest).as_posix(), term))
        assert offences == []
    finally:
        harness._remove_read_only_tree(dest)
