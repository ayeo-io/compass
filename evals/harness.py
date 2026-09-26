"""Run one eval scenario under one condition and write a run record.

    python3 evals/harness.py --scenario <id> --condition compass|bare \\
        [--runs N] [--out DIR] [--claude PATH]

For each run this copies the scenario's seed (and the condition's own
overlay, if the scenario has one) into a fresh temporary git repository,
drives the named CLI executable there once for the prompt and once more per
follow-up (each later call carrying `--resume` and the session id the first
call returned), runs the seed's own test command, and writes a JSON record
of what happened - every tool call in call order, the diff against the seed
commit, the files left under `.compass/`, the exit status and the cost - to
`<out>/<scenario id>-<condition>-<run number>.json`.

`--scenario` takes the id documented in `technical-design.md` section 2.1,
resolved against `evals/scenarios/<id>/`. It also accepts a path to a
scenario directory directly - the design does not say which, and this
repository's own tests use it to build a fixture scenario that does not
live under the tracked `evals/scenarios/` tree, which a sibling piece of
this issue owns.

Nothing here calls a real model: `--claude` names the executable, so a test
can point it at a stand-in that prints a canned run and records its own
arguments.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# The bundled copy of PyYAML resolves the same way it does for every other
# Compass entry point: put `cli/` on `sys.path` and import `compass_pkg` for
# its side effect before importing `yaml`, so a clean checkout needs nothing
# beyond the standard library and what this repository already carries.
sys.path.insert(0, str(REPO_ROOT / "cli"))
import compass_pkg  # noqa: E402  (side effect: puts cli/vendor at sys.path[0])
import yaml  # noqa: E402

# "The file tools" (technical-design.md section 2.2): the three tools that
# read, write or edit a file, as distinct from the six Bash forms below,
# which are commands. Read/Write/Edit plus that Bash list is the full
# allow-list; a session cannot run any other command on this machine.
ALLOWED_TOOLS: tuple[str, ...] = (
    "Read", "Write", "Edit",
    "Bash(python3:*)", "Bash(pytest:*)", "Bash(git:*)",
    "Bash(compass:*)", "Bash(ls:*)", "Bash(cat:*)",
)

_DEFAULT_TEST_COMMAND = "python3 -m pytest -q"

# A fixed identity for the one commit the harness itself makes, so a machine
# with no git identity configured still gets a fresh repository.
_GIT_ENV_EXTRA = {
    "GIT_AUTHOR_NAME": "compass-eval-harness",
    "GIT_AUTHOR_EMAIL": "eval-harness@compass.invalid",
    "GIT_COMMITTER_NAME": "compass-eval-harness",
    "GIT_COMMITTER_EMAIL": "eval-harness@compass.invalid",
}


def _resolve_scenario_dir(value: str) -> Path:
    """`value` as a scenario id under `evals/scenarios/`, unless it already
    names a directory - see the module docstring for why a direct path is
    accepted too."""
    candidate = Path(value)
    if candidate.is_dir():
        return candidate
    return REPO_ROOT / "evals" / "scenarios" / value


def load_scenario(scenario_dir: Path) -> dict[str, Any]:
    """Read `scenario.yml`, filling in the two keys this module needs a
    default for."""
    path = scenario_dir / "scenario.yml"
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data.setdefault("follow_ups", [])
    data.setdefault("test_command", _DEFAULT_TEST_COMMAND)
    return data


def _materialise_repo(scenario_dir: Path, condition: str, repo_dir: Path) -> None:
    """Copy the seed, then the condition's own overlay if the scenario has
    one, into `repo_dir`."""
    seed_dir = scenario_dir / "seed"
    if not seed_dir.is_dir():
        raise SystemExit(f"no seed/ directory under {scenario_dir}")
    shutil.copytree(seed_dir, repo_dir, dirs_exist_ok=True)
    overlay_name = "seed_compass" if condition == "compass" else "seed_bare"
    overlay_dir = scenario_dir / overlay_name
    if overlay_dir.is_dir():
        shutil.copytree(overlay_dir, repo_dir, dirs_exist_ok=True)


def _git(args: list[str], repo_dir: Path, *, env: dict[str, str] | None = None
          ) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo_dir), env=env,
                           capture_output=True, text=True)


def _git_init_and_commit(repo_dir: Path) -> None:
    """Turn the materialised directory into a git repository with one
    commit, tagged `seed`, so a later `git diff seed` names it directly."""
    env = dict(os.environ)
    env.update(_GIT_ENV_EXTRA)
    _git(["init", "-q"], repo_dir, env=env)
    _git(["add", "-A"], repo_dir, env=env)
    _git(["commit", "-q", "-m", "seed", "--allow-empty"], repo_dir, env=env)
    _git(["tag", "seed"], repo_dir, env=env)


def _common_claude_args(scenario: dict[str, Any], condition: str) -> list[str]:
    args = [
        "--output-format", "stream-json",
        "--verbose",
        "--setting-sources", "project,local",
        "--max-budget-usd", str(scenario["budget_usd"]),
        "--permission-mode", "acceptEdits",
        "--allowedTools", ",".join(ALLOWED_TOOLS),
    ]
    if condition == "compass":
        args += ["--plugin-dir", str(REPO_ROOT)]
    return args


def _stringify_tool_output(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            else:
                parts.append(json.dumps(block))
        return "".join(parts)
    return json.dumps(content)


def _new_run_state() -> dict[str, Any]:
    return {"tool_calls": [], "counter": 0, "session_id": None, "cost_usd": 0.0}


def _consume_events(output: str, state: dict[str, Any]) -> str:
    """Read one CLI call's line-delimited JSON events into `state`, in
    place, and return that call's own final text (the caller decides
    whether it replaces the run's final text)."""
    pending: dict[str, dict[str, Any]] = {}
    final_text = ""
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        message = event.get("message") or {}
        if kind == "system" and event.get("subtype") == "init":
            state["session_id"] = event.get("session_id") or state["session_id"]
        elif kind == "assistant":
            for block in message.get("content") or []:
                if block.get("type") == "tool_use":
                    pending[block.get("id")] = {
                        "index": state["counter"],
                        "name": block.get("name"),
                        "input": block.get("input") or {},
                    }
                    state["counter"] += 1
                elif block.get("type") == "text" and block.get("text"):
                    final_text = block["text"]
        elif kind == "user":
            for block in message.get("content") or []:
                if block.get("type") == "tool_result":
                    call = pending.pop(block.get("tool_use_id"), None)
                    if call is None:
                        continue
                    call["is_error"] = bool(block.get("is_error", False))
                    call["output"] = _stringify_tool_output(
                        block.get("content", ""))[:2000]
                    state["tool_calls"].append(call)
        elif kind == "result":
            state["session_id"] = event.get("session_id") or state["session_id"]
            if "result" in event:
                final_text = event["result"]
            state["cost_usd"] += float(event.get("total_cost_usd") or 0.0)
    return final_text


def _invoke_claude(claude_exe: str, message: str, common_args: list[str],
                    repo_dir: Path, state: dict[str, Any], *,
                    resume: str | None) -> tuple[int, str]:
    args = [claude_exe, "-p", message, *common_args]
    if resume:
        args += ["--resume", resume]
    proc = subprocess.run(args, cwd=str(repo_dir), capture_output=True, text=True)
    final_text = _consume_events(proc.stdout, state)
    return proc.returncode, final_text


def _diff_since_seed(repo_dir: Path) -> tuple[str, list[str]]:
    """Stage every change (so a new file counts, not only an edited one)
    and diff it against the `seed` tag."""
    _git(["add", "-A"], repo_dir)
    diff = _git(["diff", "--cached", "seed"], repo_dir).stdout
    names = _git(["diff", "--cached", "--name-only", "seed"], repo_dir).stdout
    changed_paths = [line for line in names.splitlines() if line]
    return diff, changed_paths


def _run_test_command(test_command: str, repo_dir: Path) -> int:
    proc = subprocess.run(shlex.split(test_command), cwd=str(repo_dir),
                           capture_output=True, text=True)
    return proc.returncode


def _compass_files(repo_dir: Path) -> list[str]:
    compass_dir = repo_dir / ".compass"
    if not compass_dir.is_dir():
        return []
    return sorted(
        p.relative_to(repo_dir).as_posix()
        for p in compass_dir.rglob("*") if p.is_file()
    )


def run_once(scenario: dict[str, Any], scenario_dir: Path, condition: str,
             run_index: int, claude_exe: str) -> dict[str, Any]:
    """Do one run of `scenario` under `condition` and return its record."""
    started = datetime.now(timezone.utc).isoformat()
    clock_start = time.monotonic()
    state = _new_run_state()
    final_text = ""
    exit_code = 0

    with tempfile.TemporaryDirectory(
        prefix=f"compass-eval-{scenario['id']}-{condition}-"
    ) as tmp:
        repo_dir = Path(tmp)
        _materialise_repo(scenario_dir, condition, repo_dir)
        _git_init_and_commit(repo_dir)

        common_args = _common_claude_args(scenario, condition)
        exit_code, text = _invoke_claude(
            claude_exe, scenario["prompt"], common_args, repo_dir, state,
            resume=None)
        if text:
            final_text = text

        for follow_up in scenario.get("follow_ups") or []:
            exit_code, text = _invoke_claude(
                claude_exe, follow_up, common_args, repo_dir, state,
                resume=state["session_id"])
            if text:
                final_text = text

        state["tool_calls"].sort(key=lambda call: call["index"])
        diff_text, changed_paths = _diff_since_seed(repo_dir)
        test_command = scenario.get("test_command", _DEFAULT_TEST_COMMAND)
        tests_exit_code = _run_test_command(test_command, repo_dir)
        compass_files = _compass_files(repo_dir)

    return {
        "scenario": scenario["id"],
        "condition": condition,
        "run": run_index,
        "started": started,
        "seconds": round(time.monotonic() - clock_start, 3),
        "exit_code": exit_code,
        "cost_usd": round(state["cost_usd"], 6),
        "session_id": state["session_id"],
        "tool_calls": state["tool_calls"],
        "final_text": final_text,
        "diff": diff_text,
        "changed_paths": changed_paths,
        "compass_files": compass_files,
        "tests_after": {"command": test_command, "exit_code": tests_exit_code},
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one eval scenario under one condition and record it."
    )
    parser.add_argument("--scenario", required=True,
                         help="a scenario id under evals/scenarios/, or a "
                              "path to a scenario directory")
    parser.add_argument("--condition", required=True, choices=["compass", "bare"])
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--out", default=None,
                         help="defaults to evals/out/ under this repository")
    parser.add_argument("--claude", default="claude",
                         help="the executable to run - a real CLI, or a "
                              "stand-in for a test")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    scenario_dir = _resolve_scenario_dir(args.scenario)
    if not scenario_dir.is_dir():
        print(f"no scenario directory at {scenario_dir}", file=sys.stderr)
        return 1
    scenario = load_scenario(scenario_dir)
    out_dir = Path(args.out) if args.out else (REPO_ROOT / "evals" / "out")
    out_dir.mkdir(parents=True, exist_ok=True)

    for run_index in range(1, args.runs + 1):
        record = run_once(scenario, scenario_dir, args.condition, run_index,
                           args.claude)
        out_path = out_dir / f"{scenario['id']}-{args.condition}-{run_index}.json"
        out_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
