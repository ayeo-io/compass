"""Run one eval scenario under one condition and write a run record.

    python3 evals/harness.py --scenario <id> --condition compass|bare \\
        [--runs N] [--out DIR] [--claude PATH] [--plugin-source DIR]

For each run this copies the scenario's seed (and the condition's own
overlay, if the scenario has one) into a fresh temporary git repository,
drives the named CLI executable there once for the prompt and once more per
follow-up (each later call carrying `--resume` and the session id the first
call returned), runs the seed's own test command, and writes a JSON record
of what happened - every tool call in call order, every assistant text
block, the diff against the seed commit, the files left under `.compass/`,
the exit status, the cost and whether the run stayed inside its own
temporary repository - to `<out>/<scenario id>-<condition>-<run number>.json`.

Under the `compass` condition the session never sees the real checkout: it
gets a read-only copy of `--plugin-source`'s tracked files at `HEAD` (this
repository, unless a test points it elsewhere), with `evals/` left out so no
session can read a scenario's own rubric, and that copy's own
`bin/compass init` runs in the fresh repository before the seed commit. The
child process gets a built environment, not an inherited one - no
`CLAUDE*` variable and no installed plugin's `bin/` reach it - so a run
cannot fall back to whatever `compass` happens to be on the machine that
started it.

`--scenario` takes the id documented in `technical-design.md` section 2.1,
resolved against `evals/scenarios/<id>/`. It also accepts a path to a
scenario directory directly, which this repository's own tests use to
build a scenario fixture without depending on the tracked
`evals/scenarios/` tree.

Nothing here calls a real model: `--claude` names the executable, so a test
can point it at a stand-in that prints a canned run and records its own
arguments and environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# The repository reads YAML only through `compass_pkg.core.load_yaml`
# (`tests/test_bundled_pyyaml.py`), never a direct `import yaml`, so the
# bundled PyYAML is the one used: put `cli/` on `sys.path` and load
# `compass_pkg.core.load_yaml`, so a clean checkout needs nothing beyond the
# standard library and what this repository already carries.
sys.path.insert(0, str(REPO_ROOT / "cli"))
from compass_pkg.core import load_yaml  # noqa: E402

# The allow-list a session runs under, exactly (technical-design.md section
# 2.2 step 5): the three file tools, `Skill` (so a compass session can run a
# `/compass:*` command - the bare condition has none to run), plus one Bash
# form per command this scenario suite ever needs - never a bare
# `Bash(python3:*)` or `Bash(git:*)`, which would let a session run
# anything. There is no `cat`: `Read` reads a file, and `cat > file` writes
# one.
ALLOWED_TOOLS: tuple[str, ...] = (
    "Read", "Write", "Edit", "Skill",
    "Bash(python3 -m pytest:*)", "Bash(python -m pytest:*)", "Bash(pytest:*)",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
    "Bash(git add:*)", "Bash(git commit:*)",
    "Bash(compass:*)", "Bash(ls:*)",
)

_DEFAULT_TEST_COMMAND = "python3 -m pytest -q"

# How much of a session's stderr the record keeps - enough to see why a run
# crashed, not the whole of it.
_TAIL_LIMIT = 2000

# A fixed identity for the one commit the harness itself makes, so a machine
# with no git identity configured still gets a fresh repository.
_GIT_ENV_EXTRA = {
    "GIT_AUTHOR_NAME": "compass-eval-harness",
    "GIT_AUTHOR_EMAIL": "eval-harness@compass.invalid",
    "GIT_COMMITTER_NAME": "compass-eval-harness",
    "GIT_COMMITTER_EMAIL": "eval-harness@compass.invalid",
}

# The wording Claude Code uses when a tool call was refused rather than run -
# read alongside `permission_denials`, because that event carries a call's
# id only when the CLI's own bookkeeping caught it.
_PERMISSION_REFUSAL_MARKERS = (
    "requested permissions",
    "have not granted",
    "haven't granted",
    "permission denied",
)


def _resolve_scenario_dir(value: str) -> Path:
    """`value` as a scenario id under `evals/scenarios/`, unless it already
    names a directory - see the module docstring for why a direct path is
    accepted too."""
    candidate = Path(value)
    if candidate.is_dir():
        return candidate
    return REPO_ROOT / "evals" / "scenarios" / value


def load_scenario(scenario_dir: Path) -> dict[str, Any]:
    """Read `scenario.yml` through the shared loader, filling in the two
    keys this module needs a default for. `load_yaml` returns `{}` for an
    empty file and raises `CompassError` for a missing or invalid one."""
    path = scenario_dir / "scenario.yml"
    data = load_yaml(str(path))
    data.setdefault("follow_ups", [])
    data.setdefault("test_command", _DEFAULT_TEST_COMMAND)
    return data


# --- the plugin copy (technical-design.md section 2.2, steps 1 and 2) ------

def _make_plugin_copy(source: Path, dest: Path) -> None:
    """Archive `source`'s tracked files at `HEAD` into `dest`, leave out
    `evals/` - it holds every scenario's own rubric, one `Read` away from a
    compass session otherwise (integrated-review-3.md) - and make every
    remaining path read-only, so no session - real or fake - can change this
    checkout, or the fixture standing in for it under test."""
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(["git", "archive", "HEAD"], cwd=str(source),
                              capture_output=True, check=True)
    subprocess.run(["tar", "-x"], cwd=str(dest), input=archive.stdout, check=True)
    evals_dir = dest / "evals"
    if evals_dir.is_dir():
        shutil.rmtree(evals_dir)
    _make_read_only(dest)


def _make_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        _strip_write_bit(path)
    _strip_write_bit(root)


def _strip_write_bit(path: Path) -> None:
    mode = path.stat().st_mode
    os.chmod(path, mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _remove_read_only_tree(root: Path) -> None:
    """Undo `_make_read_only` before deleting `root` - a read-only directory
    entry cannot be unlinked."""
    for path in root.rglob("*"):
        os.chmod(path, path.stat().st_mode | stat.S_IWUSR)
    os.chmod(root, root.stat().st_mode | stat.S_IWUSR)
    shutil.rmtree(root)


def _run_compass_init(plugin_copy_dir: Path, repo_dir: Path,
                       env: dict[str, str]) -> None:
    compass_exe = plugin_copy_dir / "bin" / "compass"
    subprocess.run([str(compass_exe), "init"], cwd=str(repo_dir), env=env,
                    capture_output=True, text=True, stdin=subprocess.DEVNULL)


def _materialise_repo(scenario_dir: Path, condition: str, repo_dir: Path,
                       plugin_copy_dir: Path | None,
                       child_env: dict[str, str]) -> None:
    """Copy the seed, run the plugin copy's `compass init` for the compass
    condition, then lay the condition's own overlay over the result - in
    that order, so the overlay can add to what init already wrote and both
    are part of the seed commit, not a change the session made."""
    seed_dir = scenario_dir / "seed"
    if not seed_dir.is_dir():
        raise SystemExit(f"no seed/ directory under {scenario_dir}")
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(seed_dir, repo_dir, dirs_exist_ok=True, ignore=ignore)

    if condition == "compass":
        if plugin_copy_dir is None:
            raise SystemExit("compass condition needs a plugin copy")
        _run_compass_init(plugin_copy_dir, repo_dir, child_env)

    overlay_name = "seed_compass" if condition == "compass" else "seed_bare"
    overlay_dir = scenario_dir / overlay_name
    if overlay_dir.is_dir():
        shutil.copytree(overlay_dir, repo_dir, dirs_exist_ok=True, ignore=ignore)


def _git(args: list[str], repo_dir: Path, *, env: dict[str, str] | None = None
          ) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo_dir), env=env,
                           capture_output=True, text=True)


def _exclude_pyc_files(repo_dir: Path) -> None:
    """Write `__pycache__/` and `*.pyc` to `.git/info/exclude` before the
    seed commit, so a session that runs the seed's own tests leaves nothing
    for `git add -A` to stage. Without this, `_diff_since_seed` puts a
    `.pyc` path into `changed_paths` that no tool call touched, and the
    judge cannot place the first code edit (integrated-review-2.md)."""
    exclude_path = repo_dir / ".git" / "info" / "exclude"
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    with exclude_path.open("a", encoding="utf-8") as fh:
        fh.write("__pycache__/\n*.pyc\n")


def _git_init_and_commit(repo_dir: Path) -> None:
    """Turn the materialised directory into a git repository with one
    commit, tagged `seed`, so a later `git diff seed` names it directly."""
    env = dict(os.environ)
    env.update(_GIT_ENV_EXTRA)
    _git(["init", "-q"], repo_dir, env=env)
    _exclude_pyc_files(repo_dir)
    _git(["add", "-A"], repo_dir, env=env)
    _git(["commit", "-q", "-m", "seed", "--allow-empty"], repo_dir, env=env)
    _git(["tag", "seed"], repo_dir, env=env)


# --- the child's own environment (technical-design.md section 2.2, step 3) -

def _is_claude_plugin_path(entry: str) -> bool:
    """True for a `PATH` entry under a Claude Code plugins directory, for
    example `~/.claude/plugins/cache/compass/compass/4.0.1/bin` - the route
    by which a bare or compass session could otherwise reach whatever
    `compass` happens to be installed on the machine that started it."""
    parts = Path(entry).parts
    return any(parts[i:i + 2] == (".claude", "plugins")
               for i in range(len(parts) - 1))


def _build_child_env(condition: str, plugin_copy_dir: Path | None
                      ) -> dict[str, str]:
    """The session's own environment, built from nothing rather than
    filtered from the harness's, so no `CLAUDE*` variable can pass through
    by accident. `PATH` keeps every entry that is not under a Claude Code
    plugins directory, with the plugin copy's own `bin/` put first for the
    compass condition only."""
    env: dict[str, str] = {}
    for key in ("HOME", "USER", "LANG", "TMPDIR"):
        if key in os.environ:
            env[key] = os.environ[key]

    kept_entries = [entry for entry in os.environ.get("PATH", "").split(os.pathsep)
                    if entry and not _is_claude_plugin_path(entry)]
    if condition == "compass" and plugin_copy_dir is not None:
        kept_entries = [str(plugin_copy_dir / "bin"), *kept_entries]
    env["PATH"] = os.pathsep.join(kept_entries)
    return env


def _claude_version(claude_exe: str, env: dict[str, str]) -> str:
    proc = subprocess.run([claude_exe, "--version"], env=env,
                           capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
    return proc.stdout.strip()


def _common_claude_args(condition: str, plugin_copy_dir: Path | None
                         ) -> list[str]:
    args = [
        "--output-format", "stream-json",
        "--verbose",
        "--setting-sources", "project,local",
        "--permission-mode", "acceptEdits",
        "--allowedTools", ",".join(ALLOWED_TOOLS),
        "--strict-mcp-config",
    ]
    if condition == "compass":
        args += ["--plugin-dir", str(plugin_copy_dir)]
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


def _tail(text: str, limit: int = _TAIL_LIMIT) -> str:
    return text[-limit:] if text else ""


def _looks_like_permission_refusal(output: str) -> bool:
    lowered = output.lower()
    return any(marker in lowered for marker in _PERMISSION_REFUSAL_MARKERS)


def _new_run_state() -> dict[str, Any]:
    return {
        "tool_calls": [], "counter": 0, "session_id": None, "cost_usd": 0.0,
        "texts": [], "permission_denials": [], "subtypes": [],
        "cwd": None, "model": None, "stderr": "",
    }


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
            if event.get("cwd"):
                state["cwd"] = event["cwd"]
            if event.get("model"):
                state["model"] = event["model"]
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
                    state["texts"].append({
                        "before_tool_call": state["counter"],
                        "text": block["text"],
                    })
        elif kind == "user":
            for block in message.get("content") or []:
                if block.get("type") == "tool_result":
                    tool_use_id = block.get("tool_use_id")
                    call = pending.pop(tool_use_id, None)
                    if call is None:
                        continue
                    call["is_error"] = bool(block.get("is_error", False))
                    call["output"] = _stringify_tool_output(
                        block.get("content", ""))[:2000]
                    call["_tool_use_id"] = tool_use_id
                    state["tool_calls"].append(call)
        elif kind == "result":
            state["session_id"] = event.get("session_id") or state["session_id"]
            if "result" in event:
                final_text = event["result"]
            state["cost_usd"] += float(event.get("total_cost_usd") or 0.0)
            state["permission_denials"].extend(event.get("permission_denials") or [])
            state["subtypes"].append(event.get("subtype"))
    return final_text


def _finalise_tool_calls(state: dict[str, Any]) -> None:
    """Mark each tool call `denied` once every invocation's events are in,
    since `permission_denials` and the refusal wording it corroborates both
    arrive after the calls they describe."""
    denied_ids: set[str] = set()
    for entry in state["permission_denials"]:
        tool_use_id = (entry.get("tool_use_id") or entry.get("id")
                       if isinstance(entry, dict) else entry)
        if tool_use_id:
            denied_ids.add(tool_use_id)
    for call in state["tool_calls"]:
        tool_use_id = call.pop("_tool_use_id", None)
        call["denied"] = bool(
            tool_use_id in denied_ids
            or _looks_like_permission_refusal(call.get("output", ""))
        )


def _invoke_claude(claude_exe: str, message: str, common_args: list[str],
                    repo_dir: Path, state: dict[str, Any], *,
                    resume: str | None, remaining_budget: float,
                    env: dict[str, str]) -> tuple[int, str]:
    args = [claude_exe, "-p", message, *common_args,
            "--max-budget-usd", str(remaining_budget)]
    if resume:
        args += ["--resume", resume]
    proc = subprocess.run(args, cwd=str(repo_dir), env=env,
                           capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
    state["stderr"] += proc.stderr or ""
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


# --- containment (technical-design.md section 2.2, step 7) -----------------

def _checkout_fingerprint(root: Path) -> dict[str, str]:
    """Hash every tracked file's content, plus every untracked one. A status
    code, such as `git status --porcelain`'s `M`, does not change between two
    different edits to the same already-changed file, and collapses a whole
    new directory to one `??` line - so a further edit, or a change inside a
    new directory, would pass unseen. `git ls-files --others` lists the files
    inside an untracked directory itself, so the hash catches both
    (integrated-review-3.md)."""
    tracked = _git(["ls-files", "-z"], root).stdout.split("\0")
    untracked = _git(["ls-files", "-z", "--others", "--exclude-standard"],
                      root).stdout.split("\0")
    snapshot: dict[str, str] = {}
    for rel in [*tracked, *untracked]:
        if not rel:
            continue
        path = root / rel
        if path.is_file():
            snapshot[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def _dir_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


def _dir_snapshot_changed_paths(before: dict[str, str], after: dict[str, str]
                                 ) -> list[str]:
    return sorted(path for path in before.keys() | after.keys()
                  if before.get(path) != after.get(path))


def _stop_reason_and_finished(subtypes: list[str | None],
                               skipped_for_budget: bool) -> tuple[str, bool]:
    if skipped_for_budget:
        return "error_max_budget_usd", False
    if subtypes:
        return (subtypes[-1] or "unknown"), all(s == "success" for s in subtypes)
    return "no_result_event", False


def run_once(scenario: dict[str, Any], scenario_dir: Path, condition: str,
             run_index: int, claude_exe: str, *,
             plugin_source: Path | None = None) -> dict[str, Any]:
    """Do one run of `scenario` under `condition` and return its record."""
    plugin_source = Path(plugin_source) if plugin_source else REPO_ROOT
    started = datetime.now(timezone.utc).isoformat()
    clock_start = time.monotonic()
    state = _new_run_state()
    final_text = ""
    exit_code = 0
    skipped_for_budget = False
    plugin_copy_dir: Path | None = None
    record_cwd: str | None = None

    # One neutral prefix for every temporary directory this run makes - the
    # repository and the plugin copy alike - so a session that can see its
    # own working directory learns neither the scenario nor the condition
    # from its name (technical-design.md section 2.2; integrated-review-3.md
    # named `compass-eval-skip-failing-test-...` as a real leak).
    temp_dir_prefix = "eval-"

    try:
        if condition == "compass":
            plugin_copy_dir = Path(tempfile.mkdtemp(prefix=temp_dir_prefix))
            _make_plugin_copy(plugin_source, plugin_copy_dir)

        child_env = _build_child_env(condition, plugin_copy_dir)
        claude_version = _claude_version(claude_exe, child_env)
        checkout_before = _checkout_fingerprint(plugin_source)
        plugin_before = _dir_snapshot(plugin_copy_dir) if plugin_copy_dir else None

        with tempfile.TemporaryDirectory(prefix=temp_dir_prefix) as tmp:
            repo_dir = Path(tmp)
            _materialise_repo(scenario_dir, condition, repo_dir,
                               plugin_copy_dir, child_env)
            _git_init_and_commit(repo_dir)

            common_args = _common_claude_args(condition, plugin_copy_dir)
            budget_usd = float(scenario["budget_usd"])

            remaining = round(budget_usd - state["cost_usd"], 6)
            exit_code, text = _invoke_claude(
                claude_exe, scenario["prompt"], common_args, repo_dir, state,
                resume=None, remaining_budget=remaining, env=child_env)
            if text:
                final_text = text

            for follow_up in scenario.get("follow_ups") or []:
                remaining = round(budget_usd - state["cost_usd"], 6)
                if remaining <= 0:
                    skipped_for_budget = True
                    break
                exit_code, text = _invoke_claude(
                    claude_exe, follow_up, common_args, repo_dir, state,
                    resume=state["session_id"], remaining_budget=remaining,
                    env=child_env)
                if text:
                    final_text = text

            state["tool_calls"].sort(key=lambda call: call["index"])
            _finalise_tool_calls(state)
            diff_text, changed_paths = _diff_since_seed(repo_dir)
            test_command = scenario.get("test_command", _DEFAULT_TEST_COMMAND)
            tests_exit_code = _run_test_command(test_command, repo_dir)
            compass_files = _compass_files(repo_dir)
            record_cwd = state["cwd"]

        checkout_after = _checkout_fingerprint(plugin_source)
        plugin_after = _dir_snapshot(plugin_copy_dir) if plugin_copy_dir else None

        escaped_paths = [f"checkout:{path}" for path in
                          _dir_snapshot_changed_paths(checkout_before, checkout_after)]
        if plugin_copy_dir is not None:
            escaped_paths += [f"plugin:{path}" for path in
                               _dir_snapshot_changed_paths(plugin_before, plugin_after)]
        contained = not escaped_paths
    finally:
        if plugin_copy_dir is not None:
            _remove_read_only_tree(plugin_copy_dir)

    stop_reason, finished = _stop_reason_and_finished(
        state["subtypes"], skipped_for_budget)
    # The CLI checks --max-budget-usd between turns, not within one, so a
    # single turn can spend past what was left while the invocation still
    # ends success. `finished` follows the result subtype regardless; this
    # flag says the cost passed the budget either way
    # (technical-design.md section 2.2; integrated-review-3.md, issue).
    over_budget = round(state["cost_usd"], 6) > budget_usd

    return {
        "scenario": scenario["id"],
        "condition": condition,
        "run": run_index,
        "started": started,
        "seconds": round(time.monotonic() - clock_start, 3),
        "exit_code": exit_code,
        "cost_usd": round(state["cost_usd"], 6),
        "session_id": state["session_id"],
        "cwd": record_cwd,
        "model": state["model"],
        "claude_version": claude_version,
        "stop_reason": stop_reason,
        "finished": finished,
        "tool_calls": state["tool_calls"],
        "texts": state["texts"],
        "permission_denials": state["permission_denials"],
        "final_text": final_text,
        "diff": diff_text,
        "changed_paths": changed_paths,
        "compass_files": compass_files,
        "tests_after": {"command": test_command, "exit_code": tests_exit_code},
        "contained": contained,
        "escaped_paths": escaped_paths,
        "stderr_tail": _tail(state["stderr"]),
        "over_budget": over_budget,
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
    parser.add_argument("--plugin-source", default=None,
                         help="the repository copied for the compass "
                              "condition's plugin, and hashed for "
                              "containment either way - defaults to this "
                              "repository")
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
    plugin_source = Path(args.plugin_source) if args.plugin_source else None

    for run_index in range(1, args.runs + 1):
        record = run_once(scenario, scenario_dir, args.condition, run_index,
                           args.claude, plugin_source=plugin_source)
        out_path = out_dir / f"{scenario['id']}-{args.condition}-{run_index}.json"
        out_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
