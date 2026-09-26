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
repository, unless a test points it elsewhere), with `evals/` and every
`tests/test_eval_*.py` left out so no session can read a scenario's own
rubric, and that copy's own `bin/compass init` runs in the fresh repository
before the seed commit. The child process gets a built environment, not an
inherited one - no `CLAUDE*` variable and no installed plugin's `bin/` reach
it - so a run cannot fall back to whatever `compass` happens to be on the
machine that started it.

`--scenario` takes a scenario id, resolved against `evals/scenarios/<id>/`.
It also accepts a path to a scenario directory directly, which this
repository's own tests use to build a scenario fixture without depending on
the tracked `evals/scenarios/` tree.

Nothing here calls a real model: `--claude` names the executable, so a test
can point it at a stand-in that prints a canned run and records its own
arguments and environment.
"""
from __future__ import annotations

import argparse
import fnmatch
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

# The allow-list a session runs under: the three file tools, `Skill` (so a
# compass session can run a `/compass:*` command - the bare condition has
# none to run), plus one Bash form per command this scenario suite ever
# needs - never a bare `Bash(python3:*)` or `Bash(git:*)`, which would let a
# session run anything. `cat`, `head`, `tail` and `grep` are on the list:
# Compass's own commands, such as `/compass:quick-fix`, read their own
# template with them, and three real compass sessions had exactly these
# refused. A `cat >` onto a protected path is caught by
# `no_evidence_tampering`, not by the allow-list.
ALLOWED_TOOLS: tuple[str, ...] = (
    "Read", "Write", "Edit", "Skill",
    "Bash(python3 -m pytest:*)", "Bash(python -m pytest:*)", "Bash(pytest:*)",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
    "Bash(git add:*)", "Bash(git commit:*)",
    "Bash(compass:*)", "Bash(ls:*)", "Bash(cat:*)",
    "Bash(head:*)", "Bash(tail:*)", "Bash(grep:*)",
)

_DEFAULT_TEST_COMMAND = "python3 -m pytest -q"

# How much of a session's stderr the record keeps - enough to see why a run
# crashed, not the whole of it.
_TAIL_LIMIT = 2000

# How much of a tool call's own output the record keeps. A test command's
# summary line comes last, so keeping only the first 2,000 characters of a
# long run lost it entirely; keeping the start as well as the end keeps
# both the command that ran and how it finished.
_TOOL_OUTPUT_HEAD_LIMIT = 1000
_TOOL_OUTPUT_TAIL_LIMIT = 3000

# An ordinary identity for the one commit the harness itself makes, so a
# machine with no git identity configured still gets a fresh repository, and
# an allowed `git log` shows nothing a session could read as a sign it is
# under test.
_GIT_ENV_EXTRA = {
    "GIT_AUTHOR_NAME": "Sam Taylor",
    "GIT_AUTHOR_EMAIL": "sam@example.com",
    "GIT_COMMITTER_NAME": "Sam Taylor",
    "GIT_COMMITTER_EMAIL": "sam@example.com",
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


# --- the plugin copy --------------------------------------------------------

def _make_plugin_copy(source: Path, dest: Path) -> None:
    """Archive `source`'s tracked files at `HEAD` into `dest`, leave out
    `evals/`, every `tests/test_eval_*.py` and every published eval report
    under `docs/compass/` - together they hold every scenario's own rubric,
    one `Read` away from a compass session otherwise - and make every
    remaining path read-only, so no session - real or fake - can change this
    checkout, or the fixture standing in for it under test."""
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(["git", "archive", "HEAD"], cwd=str(source),
                              capture_output=True, check=True)
    subprocess.run(["tar", "-x"], cwd=str(dest), input=archive.stdout, check=True)
    evals_dir = dest / "evals"
    if evals_dir.is_dir():
        shutil.rmtree(evals_dir)
    tests_dir = dest / "tests"
    if tests_dir.is_dir():
        for eval_test_file in sorted(tests_dir.glob("test_eval_*.py")):
            eval_test_file.unlink()
    docs_compass_dir = dest / "docs" / "compass"
    if docs_compass_dir.is_dir():
        for eval_report in sorted(docs_compass_dir.glob("*eval*")):
            if eval_report.is_dir():
                shutil.rmtree(eval_report)
            else:
                eval_report.unlink()
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
    """Run the plugin copy's own `compass init` before the seed commit. A
    failure here would give a compass run with no `.compass/`, where both
    hooks do nothing and the run silently measures nothing - the same
    silent-empty-seed mistake `_copy_tracked_files` already refuses, so this
    refuses the same way."""
    compass_exe = plugin_copy_dir / "bin" / "compass"
    result = subprocess.run([str(compass_exe), "init"], cwd=str(repo_dir), env=env,
                             capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise SystemExit(
            f"compass init failed in {repo_dir} (exit {result.returncode}): {stderr}")


def _copy_tracked_files(source_dir: Path, dest_dir: Path) -> None:
    """Copy only `source_dir`'s own git-tracked files into `dest_dir`. A
    scenario's seed and overlay directories are tracked inside this
    repository; a local file that never was, such as a stray
    `.pytest_cache/`, must never reach a run, so this reads the tracked file
    list rather than walking the directory.

    A scenario directory outside a git repository gave an empty seed and no
    error: `git ls-files` fails there, and its exit status went unchecked,
    so the harness quietly ran a session in an empty repository instead of
    the seed it was meant to have. Failing, or listing no file, is always a
    mistake - stop instead."""
    result = subprocess.run(["git", "ls-files", "-z"], cwd=str(source_dir),
                             capture_output=True)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", "replace").strip()
        raise SystemExit(
            f"{source_dir} is not inside a git repository, so its seed "
            f"cannot be read (git ls-files: {stderr})")
    raw_names = result.stdout.decode("utf-8", "replace").split("\0")
    names = [name for name in raw_names if name]
    if not names:
        raise SystemExit(f"{source_dir} has no git-tracked file to seed a run with")
    for name in names:
        source_path = source_dir / name
        dest_path = dest_dir / name
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)


def _materialise_repo(scenario_dir: Path, condition: str, repo_dir: Path,
                       plugin_copy_dir: Path | None,
                       child_env: dict[str, str]) -> None:
    """Copy the seed's own git-tracked files, run the plugin copy's `compass
    init` for the compass condition, then lay the condition's own overlay
    over the result - in that order, so the overlay can add to what init
    already wrote and both are part of the seed commit, not a change the
    session made."""
    seed_dir = scenario_dir / "seed"
    if not seed_dir.is_dir():
        raise SystemExit(f"no seed/ directory under {scenario_dir}")
    _copy_tracked_files(seed_dir, repo_dir)

    if condition == "compass":
        if plugin_copy_dir is None:
            raise SystemExit("compass condition needs a plugin copy")
        _run_compass_init(plugin_copy_dir, repo_dir, child_env)

    overlay_name = "seed_compass" if condition == "compass" else "seed_bare"
    overlay_dir = scenario_dir / overlay_name
    if overlay_dir.is_dir():
        _copy_tracked_files(overlay_dir, repo_dir)


def _git(args: list[str], repo_dir: Path, *, env: dict[str, str] | None = None
          ) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo_dir), env=env,
                           capture_output=True, text=True)


def _exclude_pyc_files(repo_dir: Path) -> None:
    """Write `__pycache__/` and `*.pyc` to `.git/info/exclude` before the
    seed commit, so a session that runs the seed's own tests leaves nothing
    for `git add -A` to stage. Without this, `_diff_since_seed` puts a
    `.pyc` path into `changed_paths` that no tool call touched, and the
    judge cannot place the first code edit."""
    exclude_path = repo_dir / ".git" / "info" / "exclude"
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    with exclude_path.open("a", encoding="utf-8") as fh:
        fh.write("__pycache__/\n*.pyc\n")


def _git_init_and_commit(repo_dir: Path) -> str:
    """Turn the materialised directory into a git repository with one
    ordinary commit, and return its id so a later diff can name it directly.
    No tag or branch marks it: a session's own allowed `git log --decorate`
    must show nothing that says a commit is under evaluation, and none of
    six rounds of real sessions ever ran `git tag`. The commit message is
    ordinary too, for the same reason."""
    env = dict(os.environ)
    env.update(_GIT_ENV_EXTRA)
    _git(["init", "-q"], repo_dir, env=env)
    _exclude_pyc_files(repo_dir)
    _git(["add", "-A"], repo_dir, env=env)
    _git(["commit", "-q", "-m", "Initial commit", "--allow-empty"], repo_dir, env=env)
    return _git(["rev-parse", "HEAD"], repo_dir, env=env).stdout.strip()


# --- the child's own environment ---------------------------------------------

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
        # `--add-dir` admits the plugin copy to the session's working
        # directories: Claude Code refused `cat templates/manifest.yml`
        # there in three real compass sessions, because the copy sits
        # outside the temporary repository `--plugin-dir` alone does not
        # widen.
        args += ["--plugin-dir", str(plugin_copy_dir), "--add-dir", str(plugin_copy_dir)]
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


def _head_and_tail(text: str, head_limit: int = _TOOL_OUTPUT_HEAD_LIMIT,
                    tail_limit: int = _TOOL_OUTPUT_TAIL_LIMIT) -> str:
    """Keep the first `head_limit` and the last `tail_limit` characters of a
    tool's own output, whole when it is shorter than both put together. A
    command's summary line comes last, so a run of only its first
    characters can lose it; keeping the end too keeps it."""
    if len(text) <= head_limit + tail_limit:
        return text
    return text[:head_limit] + text[-tail_limit:]


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
                    call["output"] = _head_and_tail(
                        _stringify_tool_output(block.get("content", "")))
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


# --- the continuation reply (§2.2) ------------------------------------------

def _is_test_path(path: str) -> bool:
    """A path this scenario suite treats as a test, not the work itself -
    the same convention `evals/judge.py`'s own `_is_test_path` uses, kept
    here too because whether the continuation reply is due is decided
    before the judge ever sees the record."""
    name = path.rsplit("/", 1)[-1]
    return (name.startswith("test_") or name.endswith("_test.py")
            or path.startswith("tests/"))


def _is_within_compass_or_docs_compass(path: str) -> bool:
    return (path.startswith(".compass/") or path == ".compass"
            or path.startswith("docs/compass/") or path == "docs/compass")


def _in_scope(path: str, in_scope: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in in_scope)


def _has_non_test_in_scope_edit(repo_dir: Path, in_scope: list[str],
                                 seed_commit: str) -> bool:
    """True once a non-test path in `in_scope`, outside `.compass/` and
    `docs/compass/`, differs from the seed commit - the threshold §2.2 sets
    for whether a session has done the work yet."""
    _, changed_paths, _ = _diff_since_seed(repo_dir, seed_commit)
    return any(
        _in_scope(path, in_scope) and not _is_within_compass_or_docs_compass(path)
        and not _is_test_path(path)
        for path in changed_paths
    )


def _maybe_send_continue_reply(claude_exe: str, common_args: list[str],
                                repo_dir: Path, state: dict[str, Any], *,
                                scenario: dict[str, Any], budget_usd: float,
                                replies_sent: int, env: dict[str, str],
                                seed_commit: str
                                ) -> tuple[int, int | None, str | None]:
    """A session run under `-p` gets no answer to a question of its own, so
    it never reaches a decision on its own. Guessing that question from a
    trailing `?` in the last message missed most of them: sessions ask for
    a decision in other shapes, so every ordering scenario under the
    compass condition ended "no edit" instead. The trigger is now whether
    the run has done the work, not the wording of its last message: while
    the last call ended normally (its result subtype is `success` - a call
    that errored gets no reply either), no non-test path in `in_scope` has
    changed against the seed yet, and there is still budget to keep going,
    send the scenario's own `continue_reply` before whatever the harness
    does next - at most once per run, and only for a scenario that carries
    the field. Elsewhere the reply could read as consent to the very
    behaviour being scored, so a scenario without it never gets one.
    Returns the (possibly unchanged) reply count, and the call's own exit
    code and text when a reply was sent."""
    continue_reply = scenario.get("continue_reply")
    if not continue_reply or replies_sent >= 1:
        return replies_sent, None, None
    if not state["subtypes"] or state["subtypes"][-1] != "success":
        return replies_sent, None, None
    remaining = round(budget_usd - state["cost_usd"], 6)
    if remaining <= 0:
        return replies_sent, None, None
    in_scope = scenario.get("in_scope") or ["**"]
    if _has_non_test_in_scope_edit(repo_dir, in_scope, seed_commit):
        return replies_sent, None, None
    exit_code, text = _invoke_claude(
        claude_exe, continue_reply, common_args, repo_dir, state,
        resume=state["session_id"], remaining_budget=remaining, env=env)
    return replies_sent + 1, exit_code, text


def _diff_since_seed(repo_dir: Path, seed_commit: str
                      ) -> tuple[str, list[str], list[dict[str, str]]]:
    """Stage every change (so a new file counts, not only an edited one) and
    diff it against the seed commit - in a temporary index, never the
    repository's own one. `git add -A` used to run against the real index
    while a session's own later call could still read it with the allowed
    `git status`, staging a change the session never made itself. Returns
    the diff text, the changed paths, and each path with its status (`A`,
    `M` or `D`) against the seed."""
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        env["GIT_INDEX_FILE"] = str(Path(tmp) / "index")
        _git(["add", "-A"], repo_dir, env=env)
        diff = _git(["diff", "--cached", "--no-renames", seed_commit],
                     repo_dir, env=env).stdout
        status_output = _git(
            ["diff", "--cached", "--no-renames", "--name-status", seed_commit],
            repo_dir, env=env,
        ).stdout
    changed_paths: list[str] = []
    changed: list[dict[str, str]] = []
    for line in status_output.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        status, path = parts[0][0], parts[-1]
        changed_paths.append(path)
        changed.append({"path": path, "status": status})
    return diff, changed_paths, changed


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


def _manifests(repo_dir: Path) -> dict[str, str]:
    """The content of every issue's `manifest.yml` under `.compass/work/` at
    the end of the run - `assessed_before_first_edit` and
    `resumed_from_record` both decide from the manifest's own end state now,
    not only from the tool calls that could have written it."""
    work_dir = repo_dir / ".compass" / "work"
    if not work_dir.is_dir():
        return {}
    return {
        manifest_path.relative_to(repo_dir).as_posix():
            manifest_path.read_text(encoding="utf-8")
        for manifest_path in sorted(work_dir.glob("*/manifest.yml"))
    }


# --- containment -------------------------------------------------------------

def _checkout_fingerprint(root: Path) -> dict[str, str]:
    """Hash every tracked file's content, plus every untracked one. A status
    code, such as `git status --porcelain`'s `M`, does not change between two
    different edits to the same already-changed file, and collapses a whole
    new directory to one `??` line - so a further edit, or a change inside a
    new directory, would pass unseen. `git ls-files --others` lists the files
    inside an untracked directory itself, so the hash catches both."""
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
    replies_sent = 0
    plugin_copy_dir: Path | None = None
    record_cwd: str | None = None

    try:
        if condition == "compass":
            # The system's default temporary name - no prefix - so a
            # session that can see its own working directory learns
            # neither the scenario nor the condition from its name.
            plugin_copy_dir = Path(tempfile.mkdtemp())
            _make_plugin_copy(plugin_source, plugin_copy_dir)

        child_env = _build_child_env(condition, plugin_copy_dir)
        claude_version = _claude_version(claude_exe, child_env)
        checkout_before = _checkout_fingerprint(plugin_source)
        plugin_before = _dir_snapshot(plugin_copy_dir) if plugin_copy_dir else None

        with tempfile.TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            _materialise_repo(scenario_dir, condition, repo_dir,
                               plugin_copy_dir, child_env)
            seed_commit = _git_init_and_commit(repo_dir)

            common_args = _common_claude_args(condition, plugin_copy_dir)
            budget_usd = float(scenario["budget_usd"])

            remaining = round(budget_usd - state["cost_usd"], 6)
            exit_code, text = _invoke_claude(
                claude_exe, scenario["prompt"], common_args, repo_dir, state,
                resume=None, remaining_budget=remaining, env=child_env)
            if text:
                final_text = text
            replies_sent, reply_exit, reply_text = _maybe_send_continue_reply(
                claude_exe, common_args, repo_dir, state, scenario=scenario,
                budget_usd=budget_usd, replies_sent=replies_sent, env=child_env,
                seed_commit=seed_commit)
            if reply_exit is not None:
                exit_code = reply_exit
            if reply_text:
                final_text = reply_text

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
                replies_sent, reply_exit, reply_text = _maybe_send_continue_reply(
                    claude_exe, common_args, repo_dir, state, scenario=scenario,
                    budget_usd=budget_usd, replies_sent=replies_sent,
                    env=child_env, seed_commit=seed_commit)
                if reply_exit is not None:
                    exit_code = reply_exit
                if reply_text:
                    final_text = reply_text

            state["tool_calls"].sort(key=lambda call: call["index"])
            _finalise_tool_calls(state)
            diff_text, changed_paths, changed = _diff_since_seed(repo_dir, seed_commit)
            test_command = scenario.get("test_command", _DEFAULT_TEST_COMMAND)
            tests_exit_code = _run_test_command(test_command, repo_dir)
            compass_files = _compass_files(repo_dir)
            manifests = _manifests(repo_dir)
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
    # flag says the cost passed the budget either way.
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
        "changed": changed,
        "manifests": manifests,
        "tests_after": {"command": test_command, "exit_code": tests_exit_code},
        "contained": contained,
        "escaped_paths": escaped_paths,
        "stderr_tail": _tail(state["stderr"]),
        "over_budget": over_budget,
        "replies_sent": replies_sent,
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
