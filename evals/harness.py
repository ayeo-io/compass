"""Run one eval scenario under one condition and write a run record.

    python3 evals/harness.py --scenario <id> \\
        --condition compass|bare|R1|R3 \\
        [--runs N] [--out DIR] [--claude PATH] [--plugin-source DIR] \\
        [--framework-source DIR] [--uvx PATH]

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
repository, unless a test points it elsewhere), with `evals/`, every
`tests/test_eval_*.py`, every published eval report and `docs/releasing.md`
left out so no session can read a scenario's own rubric or learn a
scenario's, a behaviour's or a condition's name. That copy's own
`bin/compass init` runs in the fresh repository before the seed commit, and
the setup date it records there is backdated, so the hook's first refusal
never tells a session Compass was set up minutes ago. The child process gets
a built environment, not an inherited one - no `CLAUDE*` variable and no
installed plugin's `bin/` reach it - so a run cannot fall back to whatever
`compass` happens to be on the machine that started it.

Under the `R1` condition the session loads a read-only copy of
the names key's pinned R1 commit as `--plugin-dir` - built
fresh, once per harness call, from a clone of that pin, or from
`--framework-source`, a local directory a test points here instead so no
call here ever reaches the network. Under the `R3` condition the same
kind of copy's own `specify init` seeds the repository for Claude, through
`uvx`, before the seed commit - the same position `compass init` runs
`bin/compass init` in for the compass condition. Either way the run
record's `framework` field names the condition and the commit the copy was
actually built from; for `compass` and `bare` it is `None`.

A scenario that holds `hidden_tests/` gets it copied into the repository
only once the session has ended - never before, so a session can never read
it - and the scenario's own `hidden_command` run against it, recorded as
`hidden: {command, exit_code, passed, failed}`. The seed's own test command
runs again at that point too, once more than usual, and every test it
names that passed before the session ran and does not pass now is recorded
in `regressions`. A scenario with no `hidden_tests/` gets `None` for both.

`--scenario` takes a scenario id, resolved against `evals/scenarios/<id>/`.
It also accepts a path to a scenario directory directly, which this
repository's own tests use to build a scenario fixture without depending on
the tracked `evals/scenarios/` tree.

Nothing here calls a real model: `--claude` names the executable, so a test
can point it at a stand-in that prints a canned run and records its own
arguments and environment. `--uvx` names R3's own installer the same
way.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import types
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, NamedTuple

try:
    import pwd
except ImportError:                     # not POSIX: no session user to switch to
    pwd = None

REPO_ROOT = Path(__file__).resolve().parent.parent

# The repository reads YAML only through `compass_pkg.core.load_yaml`
# (`tests/test_bundled_pyyaml.py`), never a direct `import yaml`, so the
# bundled PyYAML is the one used: put `cli/` on `sys.path` and load
# `compass_pkg.core.load_yaml`, so a clean checkout needs nothing beyond the
# standard library and what this repository already carries.
sys.path.insert(0, str(REPO_ROOT / "cli"))
from compass_pkg.core import load_yaml  # noqa: E402
from compass_pkg.render import strip_ansi  # noqa: E402
# Sessions start through the launcher `compass run` uses (ADR-030), so the
# harness and the runner start `claude` the same way.
from compass_pkg import host_launch  # noqa: E402

# The allow-list a session runs under: the three file tools, `Skill` (so a
# compass session can run a `/compass:*` command - the bare condition has
# none to run), plus one Bash form per command this scenario suite ever
# needs - never a bare `Bash(python3:*)` or `Bash(git:*)`, which would let a
# session run anything. `cat`, `head`, `tail` and `grep` are on the list:
# Compass's own commands, such as `/compass:quick-fix`, read their own
# template with them, and three real compass sessions had exactly these
# refused. A `cat >` onto a protected path is caught by
# `no_evidence_tampering`, not by the allow-list.
#
# Every condition gets the same list, wide enough for each framework to
# run its own workflow - the technical design's own rule for this list: a
# tool one framework needs is allowed for all, never for one alone. Giving
# only Compass `Bash(compass:*)` measured Compass's own commands against
# frameworks that could not run theirs, not the same session on four equal
# footings.
#
# `Bash(compass:*)` gives Compass's own commands standing, and
# `.specify/scripts/bash/*` gives R3's the same. `specify init`
# installs its skills to run one of `check-prerequisites.sh` first -
# `R3-implement`, `R3-checklist`, `R3-clarify`,
# `R3-converge` and `R3-taskstoissues` among them - or
# `setup-plan.sh` for `R3-plan`, or `resolve-template.sh` for
# `R3-constitution`, as their own first step. Two more real names of
# its own, quoted here for the same reason and not a retired word either:
# `R3-analyze`, and
# <!-- vocabulary-scan: allow - names R3's own real script and command, not a retired word --> `setup-tasks.sh` for `R3-tasks`.
# Read from R3's own command templates (`templates/commands/*.md`,
# `scripts.sh:` in each one's frontmatter) at the pinned commit.
#
# R1's own `subagent-driven-development` and `executing-plans`
# skills run five of its own bundled scripts, read from those two skills'
# own `SKILL.md` at the pinned commit: `sdd-workspace`,
# <!-- vocabulary-scan: allow - names R1's own real script, not a retired word --> `task-brief` and
# `review-package` (`subagent-driven-development/scripts/`), and
# <!-- vocabulary-scan: allow - names R1's own real scripts, not a retired word --> `task-start` and `task-done` (`executing-plans/scripts/`).
# Each one runs from its own absolute path under the plugin's own root.
# That root is not on this static tuple: a real session refused
# <!-- vocabulary-scan: allow - names R1's own real script, not a retired word --> `${CLAUDE_PLUGIN_ROOT}/skills/executing-plans/scripts/task-start` - the
# `permission_denials` it recorded named the literal, unexpanded string,
# not the path Claude Code actually ran - so a Bash allow rule has to
# carry the real directory the harness built for that run, computed at
# call time by `_r1_script_rules` and appended in
# `_common_claude_args`, never a variable Claude Code is asked to resolve
# on its own.
#
# `Bash(git checkout -b:*)` and `Bash(git switch -c:*)` let a session
# start a feature branch - `executing-plans` asks before working directly
# on the seed's own default branch, and a session that follows that
# instruction needs the tool to act on the answer. The `Agent` tool runs a
# subagent, which both `subagent-driven-development` and Compass's own
# `implement` stage dispatch.
ALLOWED_TOOLS: tuple[str, ...] = (
    "Read", "Write", "Edit", "Skill", "Agent",
    "Bash(python3 -m pytest:*)", "Bash(python -m pytest:*)", "Bash(pytest:*)",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
    "Bash(git add:*)", "Bash(git commit:*)",
    "Bash(git checkout -b:*)", "Bash(git switch -c:*)",
    "Bash(compass:*)", "Bash(ls:*)", "Bash(cat:*)",
    "Bash(head:*)", "Bash(tail:*)", "Bash(grep:*)",
    "Bash(.specify/scripts/bash/check-prerequisites.sh:*)",
    "Bash(.specify/scripts/bash/setup-plan.sh:*)",
    "Bash(.specify/scripts/bash/setup-tasks.sh:*)",
    "Bash(.specify/scripts/bash/resolve-template.sh:*)",
)

# Each pair is a R1 skill and the one of its own bundled scripts
# that skill runs, read from both skills' own `SKILL.md` at the pinned
# commit - the same five `_r1_script_rules` below turns into a
# Bash allow rule per call, with that call's own real directory.
_R1_SCRIPTS: tuple[tuple[str, str], ...] = (
    ("subagent-driven-development", "sdd-workspace"),
    ("subagent-driven-development", "task-brief"),
    ("subagent-driven-development", "review-package"),
    ("executing-plans", "task-start"),
    ("executing-plans", "task-done"),
)


def _r1_script_rules(r1_scripts_dir: Path) -> tuple[str, ...]:
    """Three Bash allow-list entries per `_R1_SCRIPTS` pair.
    `executing-plans`' own `SKILL.md` runs a script bare, by its own
    absolute path, which the first entry covers - Claude Code does not
    expand `${CLAUDE_PLUGIN_ROOT}` inside a Bash allow rule, so the rule
    has to carry the real path a session's own tool call will actually
    start with. `subagent-driven-development`'s own `SKILL.md` instead
    runs every one of its scripts with a `bash` prefix
    (`bash scripts/sdd-workspace PLAN_FILE`, and the same shape for the
    other two) - a rule anchored to the script's own path does not match
    a command that starts with `bash`, so the second entry repeats the
    same absolute path with `bash` in front, and the third names the
    relative form the skill's own text writes, resolved against the
    skill's own directory rather than the plugin's root. Every script
    gets all three, not only the ones `subagent-driven-development` owns,
    so this function has one shape to test rather than two."""
    rules: list[str] = []
    for skill, script in _R1_SCRIPTS:
        script_path = f"{r1_scripts_dir}/skills/{skill}/scripts/{script}"
        rules.append(f"Bash({script_path}:*)")
        rules.append(f"Bash(bash {script_path}:*)")
        rules.append(f"Bash(bash scripts/{script}:*)")
    return tuple(rules)


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
    # A scenario that carries `hidden_tests/` without naming its own
    # `hidden_command` runs the same command its seed's own tests do,
    # against whatever `hidden_tests/` added.
    data.setdefault("hidden_command", data["test_command"])
    return data


# The rival conditions' clone addresses and pins live in the maintainer's
# names key, never in this repository: committed text names no rival
# product (governance/decisions/2026-10-04-rival-names-never-committed.md).
_RIVALS_KEY = Path(".compass") / "private" / "rival-codes.yml"


def rivals_key_path() -> Path:
    """Where the names key is: `COMPASS_RIVALS_KEY`, then this checkout's
    own copy, then the main checkout's when this is a linked worktree (the
    key is untracked, so a worktree has none of its own)."""
    if os.environ.get("COMPASS_RIVALS_KEY"):
        return Path(os.environ["COMPASS_RIVALS_KEY"])
    own = REPO_ROOT / _RIVALS_KEY
    if own.is_file():
        return own
    common = _run_git(["rev-parse", "--path-format=absolute",
                       "--git-common-dir"], REPO_ROOT, dict(os.environ))
    if common.returncode == 0 and common.stdout.strip():
        main = Path(common.stdout.strip()).parent / _RIVALS_KEY
        if main.is_file():
            return main
    return own


def load_frameworks_config(path: Path | None = None) -> dict[str, Any]:
    """Each rival condition (`R1`, `R3`) mapped to its pinned `repo`,
    `commit` and any `paths` map. A file with a top-level `rivals:` is the
    names key, and each code's `eval:` block is read; any other file is the
    flat shape a test writes for its own fixture."""
    data = load_yaml(str(path or rivals_key_path())) or {}
    if isinstance(data.get("rivals"), dict):
        return {code: entry["eval"] for code, entry in data["rivals"].items()
                if isinstance(entry, dict) and isinstance(entry.get("eval"), dict)}
    return data


# --- the one function every git call in this module runs through -----------

# `-c core.fsmonitor=false -c core.hooksPath=/dev/null -c
# protocol.allow=never` on every call: a session's own `.git/config` can
# still name `core.fsmonitor` as a script the harness never chose, and
# `core.hooksPath` is pointed at `/dev/null`, where no hook can exist, so
# a hooks path the session's config names is never used. `protocol.allow=
# never` is a default only: a session's own config can still name a more
# specific `protocol.<name>.allow` that beats it, so it is not on its own
# what stops a remote - `GIT_ALLOW_PROTOCOL=none` below is. `--no-ext-diff
# --no-textconv` are added only to a `diff` subcommand, since only some
# calls are diffs.
_GIT_SAFE_CONFIG_ARGS = ("-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
                         "-c", "protocol.allow=never")
_GIT_DIFF_SAFE_ARGS = ("--no-ext-diff", "--no-textconv")


def _run_git(args: list[str], cwd: Path, env: dict[str, str], *,
              text: bool = True, allow_protocol: str = "none"
              ) -> subprocess.CompletedProcess:
    """The one function every git call in this module makes - in this
    checkout, in a scenario's own seed or overlay directory, and in a
    session's temporary repository alike
    (`tests/test_eval_harness.py::test_every_new_process_starts_through_a_named_function`
    reads this file's own source and fails on a call that starts a new
    process anywhere else). Always adds `GIT_CONFIG_GLOBAL=/dev/null`,
    `GIT_CONFIG_NOSYSTEM=1`, `GIT_NO_LAZY_FETCH=1` and
    `GIT_ALLOW_PROTOCOL=none` to `env`, so neither the operator's own
    `~/.gitconfig` nor a machine-wide config is read at all - a filter or
    driver named only there finds no definition - a partial clone's own
    promisor remote never fetches a missing object lazily, and no remote of
    any protocol is reached at all: git documents `GIT_ALLOW_PROTOCOL` as
    overriding every `protocol.allow` and `protocol.<name>.allow` setting,
    so a repository's own config cannot defeat it the way it can defeat the
    `-c protocol.allow=never` argument below with a more specific
    `protocol.<name>.allow`. Either `GIT_NO_LAZY_FETCH=1` or
    `GIT_ALLOW_PROTOCOL=none` alone already stops a lazy fetch from a
    planted promisor remote; both are set because each answers a different
    question - whether a fetch happens at all, and whether a remote of any
    protocol is reachable - not because one depends on the other.

    When `cwd` already carries its own `.git` entry - a directory or a
    gitfile, the shape every repository this module creates or is handed
    (the session's own temporary repository, a scenario's own seed
    directory once `_git_commit_all`-style fixtures give it one) takes -
    this also adds `GIT_CEILING_DIRECTORIES=<cwd's own parent>`, so git's
    own repository discovery never walks higher than `cwd` itself (EJG-6):
    a session that deleted or corrupted its own repository's `.git/HEAD`
    must not make a later call here fall back to discovering some
    unrelated repository above it. Left unset when `cwd` is a plain
    subdirectory of a repository whose root sits further up still - copying
    a scenario's own tracked seed files (`_copy_tracked_files`) runs `git
    ls-files` from inside `seed/`, not the scenario's own repository root,
    and a ceiling at its immediate parent would stop discovery from ever
    reaching that root at all. `_run_guarded_git` is what actually refuses
    to run a git command against the session's own repository at all once
    `.git/HEAD` is gone or corrupt; this is a second, general defence
    against upward search on every call this module makes against a
    directory that is itself a repository, not only that one.
    `_GIT_SAFE_CONFIG_ARGS`, so a setting a repository's own `.git/config`
    still carries cannot point `core.fsmonitor` at a script or name a real
    `core.hooksPath`. A `diff` subcommand also gets `_GIT_DIFF_SAFE_ARGS`,
    skipping any the caller already passed, so a filter or textconv driver
    named in a tracked `.gitattributes` cannot run either.

    `allow_protocol` sets `GIT_ALLOW_PROTOCOL` and defaults to `none` - the
    refusal above - for every call in this module but one:
    `_framework_source_dir`'s own clone of a pinned framework, which passes
    `"https"` because it cannot reach its own pin any other way. Every
    other safeguard here - the config isolation, the ceiling, the safe
    arguments - stays exactly as strict for that call
    too; only the protocol allowance widens, and only for it."""
    call_env = dict(env)
    call_env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    call_env["GIT_CONFIG_NOSYSTEM"] = "1"
    call_env["GIT_NO_LAZY_FETCH"] = "1"
    call_env["GIT_ALLOW_PROTOCOL"] = allow_protocol
    if (Path(cwd) / ".git").exists():
        call_env["GIT_CEILING_DIRECTORIES"] = str(Path(cwd).resolve().parent)
    subcommand = args[0] if args else ""
    rest = list(args[1:])
    if subcommand == "diff":
        rest = [flag for flag in _GIT_DIFF_SAFE_ARGS if flag not in args] + rest
    full_args = ["git", *_GIT_SAFE_CONFIG_ARGS,
                 *([subcommand] if subcommand else []), *rest]
    return subprocess.run(full_args, cwd=str(cwd), env=call_env,
                           capture_output=True, text=text)


# --- the plugin copy --------------------------------------------------------

def _plugin_copy_excluded(rel_path: str) -> bool:
    """True for a tracked path that must not reach the plugin copy -
    `evals/`, every `tests/test_eval_*.py`, a published eval report under
    `docs/compass/`, and the releasing guide - together they would name
    every scenario, every behaviour and the conditions themselves, one
    `Read` away from a compass session otherwise. Matches by path exactly:
    `tests/test_eval_*.py` only directly under `tests/`, and
    `docs/compass/*eval*` only as a direct child of `docs/compass/`."""
    if rel_path == "docs/releasing.md":
        return True
    if rel_path == "evals" or rel_path.startswith("evals/"):
        return True
    if rel_path.startswith("tests/"):
        name = rel_path[len("tests/"):]
        return "/" not in name and name.startswith("test_eval_") and name.endswith(".py")
    if rel_path.startswith("docs/compass/"):
        remainder = rel_path[len("docs/compass/"):]
        top = remainder.split("/", 1)[0]
        return "eval" in top
    return False


def _copy_git_tree_read_only(source: Path, dest: Path, env: dict[str, str], *,
                              excluded: Callable[[str], bool] = lambda rel_path: False
                              ) -> None:
    """Build `dest` from `source`'s own git objects at `HEAD` - `git ls-tree
    -r HEAD` for the tracked list, `git cat-file blob` for each file's own
    bytes - never `git archive` or a checkout of a working tree, so a
    smudge filter named in `source`'s own `.gitattributes` and
    `.git/config` never runs: `cat-file blob` returns the object exactly as
    git stored it, with no filter applied. Leaves out every path `excluded`
    names, and makes every remaining path read-only, so no session - real
    or fake - can change the copy, or the fixture standing in for one
    under test. A session can still change `source` itself, through its
    own code such as a planted `conftest.py`; only the copy handed to it
    is protected here. `_make_plugin_copy` and `_prepare_framework_copy`
    are this function's own two callers, one per kind of read-only copy
    this module builds."""
    dest.mkdir(parents=True, exist_ok=True)
    listing = _run_git(["ls-tree", "-r", "-z", "--full-tree", "HEAD"], source, env)
    if listing.returncode != 0:
        raise SystemExit(
            f"git ls-tree failed for {source}: {listing.stderr.strip()}")
    for entry in listing.stdout.split("\0"):
        if not entry:
            continue
        meta, rel_path = entry.split("\t", 1)
        if excluded(rel_path):
            continue
        mode, obj_type, sha = meta.split(" ")
        if obj_type != "blob":
            continue
        blob = _run_git(["cat-file", "blob", sha], source, env, text=False)
        if blob.returncode != 0:
            raise SystemExit(
                f"git cat-file failed for {rel_path} in {source}: "
                f"{blob.stderr!r}")
        dest_path = dest / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(blob.stdout)
        if mode == "100755":
            dest_path.chmod(dest_path.stat().st_mode
                             | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    _make_read_only(dest)


def _make_plugin_copy(source: Path, dest: Path, env: dict[str, str]) -> None:
    """The compass condition's own plugin copy: `_copy_git_tree_read_only`,
    leaving out the paths `_plugin_copy_excluded` names."""
    _copy_git_tree_read_only(source, dest, env, excluded=_plugin_copy_excluded)


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


def _run_specify_init(uvx_exe: str, framework_copy_dir: Path, repo_dir: Path,
                       env: dict[str, str]) -> None:
    """Run R3's own `specify init` for Claude in the seed, through
    `uvx` from the pinned commit's read-only copy - before the seed commit,
    the same position `_run_compass_init` runs `compass init` in for the
    compass condition. `--here` targets `repo_dir` itself rather than
    creating a new one inside it; `--non-interactive --force
    --ignore-agent-tools` make it run to completion with no prompt and no
    check for a real `claude` binary, which the harness's own `--claude`
    may not even be. A failure here would give a R3 run seeded with
    nothing R3 itself wrote, where the condition silently measures
    the bare condition instead - the same silent-empty-seed mistake
    `_run_compass_init` already refuses, so this refuses the same way."""
    result = subprocess.run(
        [uvx_exe, "--from", str(framework_copy_dir), "specify", "init",
         "--here", "--integration", "claude", "--non-interactive", "--force",
         "--ignore-agent-tools"],
        cwd=str(repo_dir), env=env, capture_output=True, text=True,
        stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise SystemExit(
            f"specify init failed in {repo_dir} (exit {result.returncode}): {stderr}")


# --- the framework copy (R1, R3) -----------------------------

def _framework_source_dir(condition: str, framework_source_override: Path | None,
                           frameworks_config: dict[str, Any], env: dict[str, str]
                           ) -> tuple[Path, bool]:
    """The directory holding `condition`'s framework at its own `HEAD` -
    `framework_source_override` directly, when a test gave one, so nothing
    here ever reaches the network; otherwise a fresh clone of
    the names key's pinned repository and commit for `condition`,
    through `_run_git`, into a temporary directory the caller must remove.
    Returns the directory and whether it is this call's own temporary clone
    (`True`, the caller's to remove) or the caller's own override (`False`,
    never removed here)."""
    if framework_source_override is not None:
        return framework_source_override, False
    entry = frameworks_config.get(condition)
    if not entry:
        raise SystemExit(f"no {condition!r} entry in the names key")
    clone_dir = Path(tempfile.mkdtemp())
    # The one clone in this module that needs the network - `allow_protocol
    # ="https"` widens `_run_git`'s own protocol lock for this call alone;
    # every other call in this function, and every other call in this
    # module, keeps the default refusal.
    clone_result = _run_git(["clone", "--quiet", entry["repo"], str(clone_dir)],
                             REPO_ROOT, env, allow_protocol="https")
    if clone_result.returncode != 0:
        shutil.rmtree(clone_dir, ignore_errors=True)
        raise SystemExit(
            f"git clone failed for {entry['repo']}: {clone_result.stderr.strip()}")
    checkout_result = _run_git(["checkout", "--quiet", entry["commit"]], clone_dir, env)
    if checkout_result.returncode != 0:
        shutil.rmtree(clone_dir, ignore_errors=True)
        raise SystemExit(
            f"git checkout {entry['commit']} failed in {clone_dir}: "
            f"{checkout_result.stderr.strip()}")
    return clone_dir, True


def _check_framework_commit_pin(condition: str, commit: str,
                                 frameworks_config: dict[str, Any]) -> None:
    """Stop the run if `commit` - the framework copy's own resolved `HEAD`,
    from a fresh clone or from `--framework-source` alike - is not the
    commit the names key pins for `condition`. A
    `--framework-source` a test or an operator points elsewhere is
    exactly as able to drift from the pin as a clone racing a force-push
    upstream, so both go through this one check, not only the clone path."""
    entry = frameworks_config.get(condition)
    pinned = entry.get("commit") if entry else None
    if not pinned:
        raise SystemExit(f"no {condition!r} entry in the names key "
                          f"to check {commit} against")
    if commit != pinned:
        raise SystemExit(
            f"{condition} framework is at commit {commit}, not the commit "
            f"names key pins ({pinned})")


def _prepare_framework_copy(condition: str, framework_source_override: Path | None,
                             frameworks_config: dict[str, Any], env: dict[str, str]
                             ) -> tuple[Path | None, str | None]:
    """Once per harness call: `(None, None)` for a condition that loads no
    framework; otherwise a read-only copy of that framework at its own
    `HEAD`, outside this checkout (`_copy_git_tree_read_only`, with no path
    excluded - a framework carries none of this repository's own scenario
    or behaviour names to protect), and the commit the copy was built
    from. `R1` passes the copy on as `--plugin-dir`
    (`_common_claude_args`); `R3` runs `specify init` from it
    (`_run_specify_init`); the run record carries the commit either way
    (`framework: {name, commit}`). `_check_framework_commit_pin` runs
    before the copy is built, so a framework at the wrong commit - cloned
    or given by `--framework-source` - never reaches a session at all."""
    if condition not in ("R1", "R3"):
        return None, None
    source_dir, is_temporary = _framework_source_dir(
        condition, framework_source_override, frameworks_config, env)
    try:
        commit = _run_git(["rev-parse", "HEAD"], source_dir, env).stdout.strip()
        _check_framework_commit_pin(condition, commit, frameworks_config)
        copy_dir = Path(tempfile.mkdtemp())
        _copy_git_tree_read_only(source_dir, copy_dir, env)
    finally:
        if is_temporary:
            shutil.rmtree(source_dir, ignore_errors=True)
    return copy_dir, commit


# The pre-tool hook's refusal quotes `.compass/config.yml`'s
# `initialised.at`, and a real compass session read that date - today's,
# because the harness runs `compass init` moments before the prompt - as
# proof a policy could not be leftover config from another project. An
# adopter's own project was set up before today, so the harness backdates
# the date the hook reports by this many days.
_SETUP_BACKDATE_DAYS = 30

_INITIALISED_AT_PATTERN = re.compile(r'^\s*at:\s*"(\d{4}-\d{2}-\d{2})"',
                                      re.MULTILINE)


def _backdate_setup_date(repo_dir: Path) -> None:
    """Rewrite the date `compass init` just stamped into
    `.compass/config.yml` to `_SETUP_BACKDATE_DAYS` before the run.
    `records_signed_since` is stamped from the same template value
    (`cli/compass_pkg/init_cmd.py`), so replacing every occurrence of the
    date `initialised.at` names backdates both fields from the one value
    the CLI wrote, without assuming which fields carry it. Does nothing if
    `compass init` was never run - the bare condition never gets here."""
    config_path = repo_dir / ".compass" / "config.yml"
    if not config_path.is_file():
        return
    text = config_path.read_text(encoding="utf-8")
    match = _INITIALISED_AT_PATTERN.search(text)
    if not match:
        return
    stamped = date.fromisoformat(match.group(1))
    backdated = (stamped - timedelta(days=_SETUP_BACKDATE_DAYS)).isoformat()
    config_path.write_text(text.replace(match.group(1), backdated), encoding="utf-8")


def _copy_tracked_files(source_dir: Path, dest_dir: Path, env: dict[str, str],
                        path_map: dict[str, str] | None = None) -> None:
    """Copy only `source_dir`'s own git-tracked files into `dest_dir`. A
    scenario's seed and overlay directories are tracked inside this
    repository; a local file that never was, such as a stray
    `.pytest_cache/`, must never reach a run, so this reads the tracked file
    list rather than walking the directory. `source_dir` sits inside this
    checkout, so the `git ls-files` call runs through `_run_git` the same
    as every other git call this module makes against it.

    A scenario directory outside a git repository gave an empty seed and no
    error: `git ls-files` fails there, and its exit status went unchecked,
    so the harness quietly ran a session in an empty repository instead of
    the seed it was meant to have. Failing, or listing no file, is always a
    mistake - stop instead."""
    result = _run_git(["ls-files", "-z"], source_dir, env, text=False)
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
        dest_path = dest_dir / _mapped(name, path_map or {})
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)


def _mapped(name: str, path_map: dict[str, str]) -> str:
    """`name` with a leading folder from `path_map` replaced. A rival's
    seed overlay is committed with its own working folder named by code
    (`docs/R1/`); the names key maps it back to the folder that rival
    really uses, so the session sees what the rival itself would write."""
    for committed, runtime in path_map.items():
        if name == committed or name.startswith(committed + "/"):
            return runtime + name[len(committed):]
    return name


def _materialise_repo(scenario_dir: Path, condition: str, repo_dir: Path,
                       plugin_copy_dir: Path | None,
                       framework_copy_dir: Path | None, uvx_exe: str,
                       child_env: dict[str, str],
                       seed_paths: dict[str, str] | None = None) -> None:
    """Copy the seed's own git-tracked files, then seed the condition's own
    state before the seed commit - the compass condition runs the plugin
    copy's `compass init` and backdates the setup date it records; the
    R3 condition runs the framework copy's own `specify init` - then
    lay the condition's own overlay over the result. In that order, so the
    overlay can add to what init already wrote and all of it is part of the
    seed commit, not a change the session made."""
    seed_dir = scenario_dir / "seed"
    if not seed_dir.is_dir():
        raise SystemExit(f"no seed/ directory under {scenario_dir}")
    _copy_tracked_files(seed_dir, repo_dir, child_env)

    if condition == "compass":
        if plugin_copy_dir is None:
            raise SystemExit("compass condition needs a plugin copy")
        _run_compass_init(plugin_copy_dir, repo_dir, child_env)
        _backdate_setup_date(repo_dir)
    elif condition == "R3":
        if framework_copy_dir is None:
            raise SystemExit("R3 condition needs a framework copy")
        _run_specify_init(uvx_exe, framework_copy_dir, repo_dir, child_env)

    # One overlay directory per condition - "seed_compass", "seed_bare",
    # "seed_R1", "seed_R3" - each optional; a scenario that
    # carries none for a condition seeds it from `seed/` alone.
    overlay_name = f"seed_{condition.replace('-', '_')}"
    overlay_dir = scenario_dir / overlay_name
    if overlay_dir.is_dir():
        _copy_tracked_files(overlay_dir, repo_dir, child_env, seed_paths)


# The three paths that let a git command in the session's own repository
# either run arbitrary code the session wrote, or read a config outside the
# repository this module never restores: `.git/config` (`diff.external`,
# `core.fsmonitor`, a `filter.*.clean` driver), `.git/info/attributes`
# (which selects a filter or a driver by path), and `.git/commondir`
# (which moves every other git call here to a config under the path it
# names). Snapshotted once, right after the seed commit, so a later git
# call can tell a session's own change from the seed's own state, and put
# the seed's copy back - or remove what the seed never had - before it
# runs.
_TAMPER_WATCHED_RELATIVE_PATHS = (".git/config", ".git/info/attributes", ".git/commondir")


def _read_bytes_or_none(path: Path) -> bytes | None:
    """`path`'s own bytes, or `None` if there is nothing there to read -
    including when an ancestor that must be a directory, most often `.git`
    itself, has been replaced by a plain file. That turns every lookup
    below it into `NotADirectoryError`, not `FileNotFoundError`, so both
    are read the same way: nothing here, not a crash."""
    try:
        return path.read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        return None


def _snapshot_git_config(repo_dir: Path) -> dict[str, bytes | None]:
    """Each of `_TAMPER_WATCHED_RELATIVE_PATHS` as the seed commit left it -
    `None` for one the seed never wrote, `.git/commondir` included, since an
    ordinary seed never has one. Taken once, right after
    `_git_init_and_commit` returns, before any session call runs."""
    return {rel: _read_bytes_or_none(repo_dir / rel)
            for rel in _TAMPER_WATCHED_RELATIVE_PATHS}


def _restore_tampered_git_config(repo_dir: Path,
                                  seed_git_snapshot: dict[str, bytes | None]
                                  ) -> list[str]:
    """Compare each of `_TAMPER_WATCHED_RELATIVE_PATHS` against
    `seed_git_snapshot`; put the seed's own copy back for any that changed,
    or remove it when the seed never had one (`.git/commondir`), and return
    the changed paths. This puts back what changed in these specific paths,
    immediately before the git command that runs right after; it does not
    see a global `~/.gitconfig` a session's own `HOME` could still point
    at - `_run_git`'s `GIT_CONFIG_GLOBAL=/dev/null` closes that route
    instead - and it does not close a race with a background process that
    rewrites one of these paths again after this check runs. The caller
    records the run as not contained, naming the file."""
    tampered: list[str] = []
    for rel, seed_bytes in seed_git_snapshot.items():
        path = repo_dir / rel
        current_bytes = _read_bytes_or_none(path)
        if current_bytes == seed_bytes:
            continue
        tampered.append(rel)
        if seed_bytes is None:
            if path.exists():
                path.unlink()
        elif path.parent.exists() and not path.parent.is_dir():
            # `.git` itself (or another ancestor) is now a plain file, not
            # a directory - there is nothing under it to write the seed's
            # copy back into. `rel` is already in `tampered`, so the
            # caller still records the run as not contained.
            continue
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(seed_bytes)
    return tampered


_GIT_HEAD_COMMIT_ID_RE = re.compile(r"^[0-9a-fA-F]{4,40}$")


def _git_head_is_valid(repo_dir: Path) -> bool:
    """True if `repo_dir/.git/HEAD` exists and reads back as an ordinary
    HEAD - a symbolic-ref line (`ref: refs/heads/...`) or a bare commit id
    - the shape a session that deletes or corrupts it (EJG-6) breaks. Read
    directly, never through git itself: the whole point is to decide
    whether running a git command here is safe before running one."""
    try:
        text = (repo_dir / ".git" / "HEAD").read_text(
            encoding="utf-8", errors="replace").strip()
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
        return False
    if not text:
        return False
    if text.startswith("ref:"):
        return True
    return bool(_GIT_HEAD_COMMIT_ID_RE.match(text))


def _run_guarded_git(args: list[str], repo_dir: Path, env: dict[str, str],
                      seed_git_snapshot: dict[str, bytes | None],
                      tampered_paths: list[str]
                      ) -> subprocess.CompletedProcess | types.SimpleNamespace:
    """One git command against the session's own repository: restores what
    changed among `_TAMPER_WATCHED_RELATIVE_PATHS` to the seed's own state
    first (`_restore_tampered_git_config`), then runs through `_run_git` -
    the one function every git call in this module makes, with the
    environment built for the session, never `os.environ`, plus the safe
    arguments every call gets. A planted `diff.external` in `.git/config`
    must never run: the restore puts the seed's own copy back before this
    call, and `_run_git`'s own safe arguments and environment close the
    other routes a session's own repository could still name.

    If `repo_dir/.git` is no longer a real directory - a plain file or a
    symlink to one, the shape a gitfile takes - the restore above cannot
    see what it points at, and running git here would run whatever that
    path names: a gitfile can point at a git directory carrying its own
    planted `filter.*.clean` or `core.hooksPath`, and `--no-ext-diff
    --no-textconv` do not stop a clean filter. So no git command runs at
    all in that case; this returns an empty stand-in result, carrying only
    the `.stdout` a caller reads, and the caller's own tampered-path
    bookkeeping already records the run as not contained, since
    `.git/config` no longer reads back as the seed left it.

    A missing or corrupt `.git/HEAD` (`_git_head_is_valid`) gets the same
    treatment (EJG-6): a session that deleted or corrupted it, deliberately
    or not, must not let this call fall back to whatever git's own upward
    search - already narrowed by `_run_git`'s `GIT_CEILING_DIRECTORIES`,
    but narrowed is not the same as refused - would otherwise find above
    `repo_dir`. `.git/HEAD` is not put back the way
    `_TAMPER_WATCHED_RELATIVE_PATHS` is: restoring it would hide the very
    thing this is here to catch, so `tampered_paths` records it instead,
    and no git command runs."""
    tampered_paths.extend(_restore_tampered_git_config(repo_dir, seed_git_snapshot))
    git_path = repo_dir / ".git"
    if git_path.exists() and not git_path.is_dir():
        return types.SimpleNamespace(args=["git", *args], returncode=1,
                                      stdout="", stderr="")
    if not _git_head_is_valid(repo_dir):
        if ".git/HEAD" not in tampered_paths:
            tampered_paths.append(".git/HEAD")
        return types.SimpleNamespace(args=["git", *args], returncode=1,
                                      stdout="", stderr="")
    return _run_git(args, repo_dir, env)


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


def _git_init_and_commit(repo_dir: Path, env: dict[str, str]) -> str:
    """Turn the materialised directory into a git repository with one
    ordinary commit, and return its id so a later diff can name it directly.
    No tag or branch marks it: a session's own allowed `git log --decorate`
    must show nothing that says a commit is under evaluation. The commit
    message is ordinary too, for the same reason. Every call runs through
    `_run_git`, with the environment built for the session, never
    `os.environ` - this is the repository a session's own code, and later
    the harness's own diff, run inside."""
    call_env = dict(env)
    call_env.update(_GIT_ENV_EXTRA)
    _run_git(["init", "-q"], repo_dir, call_env)
    _exclude_pyc_files(repo_dir)
    _run_git(["add", "-A"], repo_dir, call_env)
    _run_git(["commit", "-q", "-m", "Initial commit", "--allow-empty"], repo_dir, call_env)
    return _run_git(["rev-parse", "HEAD"], repo_dir, call_env).stdout.strip()


# --- the session user ---------------------------------------------------------

class SessionUser(NamedTuple):
    """The unprivileged user a root run starts each session as."""
    name: str
    uid: int
    gid: int
    home: str

    @classmethod
    def of(cls, entry) -> "SessionUser":
        return cls(entry.pw_name, entry.pw_uid, entry.pw_gid, entry.pw_dir)


def _euid() -> int:
    """The harness's effective uid; one function, so a test can play root."""
    return os.geteuid()


def _lookup_user(name: str):
    """The password entry for `name`; raises KeyError when there is none."""
    if pwd is None:
        raise KeyError(name)
    return pwd.getpwnam(name)


def _open_for_session_user(root: Path) -> None:
    """Let the session user read `root` and everything in it, and write
    none of it. `tempfile.mkdtemp` makes a folder only its owner can enter,
    so a session running as another user would find no plugin at all."""
    for path in [root, *root.rglob("*")]:
        if path.is_symlink():
            continue
        mode = path.stat().st_mode
        add = stat.S_IRGRP | stat.S_IROTH
        if path.is_dir():
            add |= stat.S_IXGRP | stat.S_IXOTH
        os.chmod(path, (mode | add) & ~(stat.S_IWGRP | stat.S_IWOTH))


def _hand_to(root: Path, user: SessionUser) -> None:
    """Give the session user its working folder and everything in it. The
    plugin copy and the checkout stay the harness's."""
    for path in [root, *root.rglob("*")]:
        os.chown(path, user.uid, user.gid, follow_symlinks=False)


# --- the child's own environment ---------------------------------------------

def _is_claude_plugin_path(entry: str) -> bool:
    """True for a `PATH` entry under a Claude Code plugins directory, for
    example `~/.claude/plugins/cache/compass/compass/4.0.1/bin` - the route
    by which a bare or compass session could otherwise reach whatever
    `compass` happens to be installed on the machine that started it."""
    parts = Path(entry).parts
    return any(parts[i:i + 2] == (".claude", "plugins")
               for i in range(len(parts) - 1))


def _build_child_env(condition: str, plugin_copy_dir: Path | None, *,
                      session_user: SessionUser | None = None
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
    if session_user is not None:
        # The session reads its Claude login from HOME, and cannot read
        # root's; a root TMPDIR may not be writable to it either, so the
        # system default applies.
        env["HOME"], env["USER"] = session_user.home, session_user.name
        env.pop("TMPDIR", None)

    kept_entries = [entry for entry in os.environ.get("PATH", "").split(os.pathsep)
                    if entry and not _is_claude_plugin_path(entry)]
    if condition == "compass" and plugin_copy_dir is not None:
        kept_entries = [str(plugin_copy_dir / "bin"), *kept_entries]
    env["PATH"] = os.pathsep.join(kept_entries)
    # File mode alone keeps a session from writing into the plugin copy, and
    # root ignores file mode: a root session's Python wrote bytecode into
    # the copy and the run was recorded as not contained (issue #370).
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _on_read_only_mount(path: Path) -> bool:
    try:
        return bool(os.statvfs(path).f_flag & os.ST_RDONLY)
    except (OSError, AttributeError):
        return False


def _root_refusal(condition: str, plugin_copy_dir: Path | None, *,
                  allow_root: bool, euid: int, session_user: str | None = None,
                  env: dict[str, str] | None = None,
                  lookup: Callable[[str], Any] | None = None) -> str | None:
    """Why this run must not start, or None. Root ignores the file mode that
    protects the plugin copy, so a compass run as root needs a sanctioned
    path: each session as an unprivileged user (`--session-user`), or the
    copy on a read-only mount. `--allow-root` accepts the risk instead, and
    only a person at a terminal may accept it, never a scheduled run."""
    env = os.environ if env is None else env
    lookup = lookup or _lookup_user
    if session_user is not None:
        if euid != 0:
            return ("refusing --session-user: only root can start a session "
                    "as another user, and this run is not root.")
        try:
            entry = lookup(session_user)
        except KeyError:
            return (f"refusing --session-user {session_user}: there is no "
                    f"such user on this machine.")
        if entry.pw_uid == 0:
            return (f"refusing --session-user {session_user}: it is root, so "
                    f"its sessions would not be contained. Name an "
                    f"unprivileged user.")
    if allow_root and (env.get("CI") or env.get("COMPASS_UNATTENDED")):
        return ("refusing --allow-root: CI or COMPASS_UNATTENDED is set, so "
                "no person is at the terminal, and a scheduled run cannot "
                "accept an uncontained run. Use --session-user instead.")
    if condition != "compass" or euid != 0 or allow_root or session_user:
        return None
    if plugin_copy_dir is not None and _on_read_only_mount(plugin_copy_dir):
        return None
    return ("refusing a compass run as root: root ignores the file mode that "
            "keeps a session out of the plugin copy, so the run could not be "
            "contained. Run each session as an unprivileged user with "
            "--session-user <name>, or put the plugin copy on a read-only "
            "mount. As a last resort, --allow-root accepts an uncontained "
            "run; it is a person's decision, made at the terminal.")


def _claude_version(claude_exe: str, env: dict[str, str]) -> str:
    proc = subprocess.run([claude_exe, "--version"], env=env,
                           capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
    return proc.stdout.strip()


# One model id, passed to every condition, so the four conditions' costs
# and token counts compare against the same model rather than whatever the
# account default happens to be on a given day - nothing held that default
# steady across sessions before this pin.
_PINNED_CLAUDE_MODEL = "claude-opus-5-5"


def _common_claude_args(condition: str, plugin_copy_dir: Path | None,
                         framework_copy_dir: Path | None,
                         r1_scripts_dir: Path
                         ) -> list[str]:
    """`r1_scripts_dir` is the directory this harness call's own
    R1-script allow rules are built against - the R1
    condition's own `--plugin-dir` copy, or, for every other condition, a
    directory the harness still built for this call but never mounts as a
    plugin, kept only so every condition's allow-list carries the same
    five rules (`main`'s own `r1_scripts_dir` decides which)."""
    args = [
        "--output-format", "stream-json",
        "--verbose",
        "--setting-sources", "project,local",
        "--permission-mode", "acceptEdits",
        "--allowedTools", ",".join(ALLOWED_TOOLS
                                    + _r1_script_rules(r1_scripts_dir)),
        "--strict-mcp-config",
        "--model", _PINNED_CLAUDE_MODEL,
    ]
    if condition == "compass":
        # `--add-dir` admits the plugin copy to the session's working
        # directories: Claude Code refused `cat templates/manifest.yml`
        # there in three real compass sessions, because the copy sits
        # outside the temporary repository `--plugin-dir` alone does not
        # widen.
        args += ["--plugin-dir", str(plugin_copy_dir), "--add-dir", str(plugin_copy_dir)]
    elif condition == "R1":
        # R1 passes as `--plugin-dir` directly - the copy carries
        # its own `.claude-plugin/plugin.json` at its root, the same shape
        # `--plugin-dir` already expects for the compass condition. It
        # gets the same `--add-dir`: without it, a `cat` of one of
        # R1's own files sits outside the working directory
        # `--plugin-dir` alone does not widen, the same refusal `--add-dir`
        # already fixes for compass.
        args += ["--plugin-dir", str(framework_copy_dir),
                  "--add-dir", str(framework_copy_dir)]
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
        "tokens": 0, "texts": [], "permission_denials": [], "subtypes": [],
        "cwd": None, "model": None, "stderr": "",
    }


# The four `usage` fields a `result` event's own accounting carries - input,
# output, and the two cache categories - summed into the run's own `tokens`
# total. Every one of them, not just input and output: a cache write or a
# cache read is still a token the call spent.
_USAGE_TOKEN_FIELDS = (
    "input_tokens", "output_tokens",
    "cache_creation_input_tokens", "cache_read_input_tokens",
)


def _usage_tokens(usage: dict[str, Any]) -> int:
    return sum(int(usage.get(field) or 0) for field in _USAGE_TOKEN_FIELDS)


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
                    call["tool_use_id"] = tool_use_id
                    state["tool_calls"].append(call)
        elif kind == "result":
            state["session_id"] = event.get("session_id") or state["session_id"]
            if "result" in event:
                final_text = event["result"]
            state["cost_usd"] += float(event.get("total_cost_usd") or 0.0)
            state["tokens"] += _usage_tokens(event.get("usage") or {})
            state["permission_denials"].extend(event.get("permission_denials") or [])
            state["subtypes"].append(event.get("subtype"))
    return final_text


def _finalise_tool_calls(state: dict[str, Any]) -> None:
    """Mark each tool call `denied` once every invocation's events are in,
    since `permission_denials` and the refusal wording it corroborates both
    arrive after the calls they describe. `tool_use_id` stays on the call:
    the judge matches a denial to its call by that id, never by position."""
    denied_ids: set[str] = set()
    for entry in state["permission_denials"]:
        tool_use_id = (entry.get("tool_use_id") or entry.get("id")
                       if isinstance(entry, dict) else entry)
        if tool_use_id:
            denied_ids.add(tool_use_id)
    for call in state["tool_calls"]:
        tool_use_id = call.get("tool_use_id")
        call["denied"] = bool(
            tool_use_id in denied_ids
            or _looks_like_permission_refusal(call.get("output", ""))
        )


def _invoke_claude(claude_exe: str, message: str, common_args: list[str],
                    repo_dir: Path, state: dict[str, Any], *,
                    resume: str | None, remaining_budget: float,
                    env: dict[str, str]) -> tuple[int, str]:
    args = [*common_args, "--max-budget-usd", str(remaining_budget)]
    if resume:
        args += ["--resume", resume]
    launched = host_launch.launch_claude(claude_exe, message, args, repo_dir,
                                         env, user=state.get("as_user"))
    state["stderr"] += launched.stderr
    final_text = _consume_events(launched.stdout, state)
    return launched.returncode, final_text


# --- the continuation reply --------------------------------------------------

def _is_test_path(path: str) -> bool:
    """A path this scenario suite treats as a test, not the work itself -
    the same convention `evals/judge.py`'s own `_is_test_path` uses, kept
    here too because whether the continuation reply is due is decided
    before the judge ever sees the record."""
    name = path.rsplit("/", 1)[-1]
    return (name.startswith("test_") or name.endswith("_test.py")
            or path.startswith("tests/"))


# Compass's own records are every path under `.compass/` and
# `docs/compass/`, and `docs/system-spec.md`, which `compass ship-commit`
# derives when an issue lands. This is the one definition; `evals/judge.py`
# imports it rather than keeping its own copy, so the two can never
# differ.
_COMPASS_OWN_RECORD_PATHS = frozenset({"docs/system-spec.md"})


def _is_compass_own_record(path: str | None) -> bool:
    if not path:
        return False
    if path in _COMPASS_OWN_RECORD_PATHS:
        return True
    return (path.startswith(".compass/") or path == ".compass"
            or path.startswith("docs/compass/") or path == "docs/compass")


def _in_scope(path: str, in_scope: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in in_scope)


def _has_non_test_in_scope_edit(repo_dir: Path, in_scope: list[str],
                                 seed_commit: str, env: dict[str, str],
                                 seed_git_snapshot: dict[str, bytes | None],
                                 tampered_paths: list[str]) -> bool:
    """True once a non-test path in `in_scope`, not one of Compass's own
    records (`_is_compass_own_record`), differs from the seed commit - the
    threshold this module uses for whether a session has done the work
    yet."""
    _, changed_paths, _ = _diff_since_seed(
        repo_dir, seed_commit, env, seed_git_snapshot, tampered_paths)
    return any(
        _in_scope(path, in_scope) and not _is_compass_own_record(path)
        and not _is_test_path(path)
        for path in changed_paths
    )


def _maybe_send_continue_reply(claude_exe: str, common_args: list[str],
                                repo_dir: Path, state: dict[str, Any], *,
                                scenario: dict[str, Any], budget_usd: float,
                                replies_sent: int, env: dict[str, str],
                                seed_commit: str,
                                seed_git_snapshot: dict[str, bytes | None],
                                tampered_paths: list[str]
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
    if _has_non_test_in_scope_edit(repo_dir, in_scope, seed_commit, env,
                                    seed_git_snapshot, tampered_paths):
        return replies_sent, None, None
    exit_code, text = _invoke_claude(
        claude_exe, continue_reply, common_args, repo_dir, state,
        resume=state["session_id"], remaining_budget=remaining, env=env)
    return replies_sent + 1, exit_code, text


def _diff_since_seed(repo_dir: Path, seed_commit: str, env: dict[str, str],
                      seed_git_snapshot: dict[str, bytes | None],
                      tampered_paths: list[str]
                      ) -> tuple[str, list[str], list[dict[str, str]]]:
    """Stage every change (so a new file counts, not only an edited one) and
    diff it against the seed commit - in a temporary index, never the
    repository's own one, so a session's own later `git status` call -
    allowed, and reading the real index - never sees a change staging made
    rather than the session itself. Every git call here runs through
    `_run_guarded_git`, which restores what changed among
    `_TAMPER_WATCHED_RELATIVE_PATHS` first and then, through `_run_git`,
    adds `--no-ext-diff --no-textconv` to each diff so a planted
    `diff.external` or textconv driver never runs, with the environment
    built for the session, never `os.environ`. Returns the diff text, the
    changed paths, and each path with its status (`A`, `M` or `D`) against
    the seed.

    A repository can be unusable in a way `_run_guarded_git` never refuses
    outright: `.git/HEAD` reading `ref: garbage` still starts with `ref:`,
    so `_git_head_is_valid` calls it fine, and a deleted `.git/objects`
    leaves `.git/HEAD` untouched - in both, every git call below runs and
    fails, read from each call's own exit code, never only its `.stdout`.
    `.git` is added to `tampered_paths` for that case, the same way a
    missing `.git/HEAD` already is, whenever one of the three calls below
    returns non-zero - checked against those two specific entries,
    `.git/HEAD` and `.git` itself, not against whether `tampered_paths`
    already carries any reason at all."""
    with tempfile.TemporaryDirectory() as tmp:
        call_env = dict(env)
        call_env["GIT_INDEX_FILE"] = str(Path(tmp) / "index")
        add_result = _run_guarded_git(["add", "-A"], repo_dir, call_env,
                                       seed_git_snapshot, tampered_paths)
        diff_result = _run_guarded_git(
            ["diff", "--cached", "--no-renames", seed_commit],
            repo_dir, call_env, seed_git_snapshot, tampered_paths)
        status_result = _run_guarded_git(
            ["diff", "--cached", "--no-renames", "--name-status", seed_commit],
            repo_dir, call_env, seed_git_snapshot, tampered_paths)
    if ".git/HEAD" not in tampered_paths and ".git" not in tampered_paths and any(
            getattr(result, "returncode", 0) != 0
            for result in (add_result, diff_result, status_result)):
        tampered_paths.append(".git")
    diff = diff_result.stdout
    status_output = status_result.stdout
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


def _run_test_command(test_command: str, repo_dir: Path, env: dict[str, str]
                       ) -> tuple[int, str]:
    """Runs with the environment built for the session, never `os.environ` -
    this command runs the seed's own tests plus anything a session edited or
    added, such as a `conftest.py`. Returns the exit code and the command's
    own combined stdout and stderr - `_pytest_summary_counts` and
    `_pytest_outcomes` (CMP-2) read the output; a caller that wants only the
    exit code discards it."""
    proc = subprocess.run(shlex.split(test_command), cwd=str(repo_dir), env=env,
                           capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# --- hidden tests and regressions (CMP-2) ------------------------------------

# pytest's own final summary line, for example "1 failed, 4 passed in
# 0.12s" - read here for the hidden test run's own `passed`/`failed`
# counts, the same line `evals/judge.py`'s `_PYTEST_SUMMARY_FAIL_RE` already
# reads to decide only whether a run failed at all.
_PYTEST_SUMMARY_COUNT_RE = re.compile(r"\b(\d+) (passed|failed|error|errors)\b")

# The final summary line itself, so counts are read from that one line, not
# from anywhere in the output a hidden test's own printed text, or an
# assertion message, could say "2 failed" without meaning pytest found two
# failures. Pytest always closes its real summary line with "in N.NNs" (the
# run's own duration); a decoy inside a test's output has no reason to
# carry that suffix too.
_PYTEST_SUMMARY_LINE_RE = re.compile(
    r"^.*\b\d+ (?:passed|failed|error|errors)\b.*\bin [\d.]+s\b.*$", re.MULTILINE)


def _pytest_summary_counts(output: str) -> tuple[int, int]:
    """`(passed, failed)` read from pytest's own final summary line in
    `output` - the last line matching `_PYTEST_SUMMARY_LINE_RE`, never any
    other line that happens to contain the same words. An error counts as
    a failure: a fixture error stops a test running under whatever name
    pytest would otherwise report it failed under, so the harness has no
    finer distinction to make here."""
    summary_lines = _PYTEST_SUMMARY_LINE_RE.findall(strip_ansi(output))
    if not summary_lines:
        return 0, 0
    passed = failed = 0
    for count_str, label in _PYTEST_SUMMARY_COUNT_RE.findall(summary_lines[-1]):
        count = int(count_str)
        if label == "passed":
            passed = count
        else:
            failed += count
    return passed, failed


# A top-level `test_` function definition - what pytest itself collects as
# one test by its default naming convention, `async def` included.
_TEST_FUNCTION_RE = re.compile(r"^(?:async )?def (test_\w+)\(", re.MULTILINE)


def hidden_tests_defined_count(hidden_tests_dir: Path) -> int:
    """Every `test_` function every `.py` file under `hidden_tests_dir`
    defines, summed - what a hidden test file that fails to import still
    holds, whatever pytest's own summary line counts for it. `0` when
    `hidden_tests_dir` does not exist."""
    if not hidden_tests_dir.is_dir():
        return 0
    return sum(len(_TEST_FUNCTION_RE.findall(path.read_text(encoding="utf-8")))
               for path in hidden_tests_dir.rglob("*.py"))


def corrected_hidden_counts(passed: int, failed: int, defined: int,
                            exit_code: int | None = 2) -> tuple[int, int]:
    """`(passed, failed)`, corrected for a hidden test file that failed to
    import: pytest's own summary then reports one error for the whole
    file, not one for each test it defines (EGB-4). Pytest exits 2 on that
    collection error. Only then does a total short of `defined` mean none
    of the tests ran, so every one counts as failed. Any other short total
    is a run that skipped or deselected a test, and is left alone. A
    caller with no exit code to give (an old record) keeps the old
    reading."""
    if defined and passed + failed < defined and exit_code == 2:
        return 0, defined
    return passed, failed


# pytest's own short test summary line, printed once per test when `-rA`
# asks for every outcome rather than only a failure's - for example
# "PASSED test_seed::test_a" or "FAILED test_seed::test_b - AssertionError".
# Read only from a command `_seed_test_command_with_report` augmented: an
# ordinary `-q` run never prints these lines, so `_pytest_outcomes` reads
# nothing from one.
_PYTEST_SHORT_SUMMARY_RE = re.compile(r"^(PASSED|FAILED|ERROR)\s+(\S+)", re.MULTILINE)


def _pytest_outcomes(output: str) -> dict[str, str]:
    """Every test node id pytest's own `-rA` short summary names in
    `output`, mapped to its outcome - the identity `_seed_regressions`
    compares before and after the session ran."""
    return dict((name, outcome)
                for outcome, name in _PYTEST_SHORT_SUMMARY_RE.findall(strip_ansi(output)))


def _seed_test_command_with_report(test_command: str) -> str:
    """`test_command` with `-rA` appended, so pytest's own short summary
    names every test's outcome - the form `_pytest_outcomes` reads - not
    only a failure's. Left unchanged when `pytest` does not name the
    runner: `_pytest_outcomes` then reads no outcome from its output, so a
    scenario naming another runner gets an empty regression list instead of
    a broken command."""
    if "pytest" not in test_command:
        return test_command
    return f"{test_command} -rA"


def _seed_regressions(seed_outcomes: dict[str, str], after_outcomes: dict[str, str]
                       ) -> list[str]:
    """Every test node id that passed at the seed and does not pass now -
    CMP-2's own definition of a regression. A test the session's own edits
    removed passed at the seed and is simply absent from `after_outcomes`,
    which counts the same way: it no longer passes."""
    return sorted(
        name for name, outcome in seed_outcomes.items()
        if outcome == "PASSED" and after_outcomes.get(name) != "PASSED"
    )


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


def _interruptions(repo_dir: Path) -> dict[str, int] | None:
    """How often Compass stopped the session: the hook blocks and failing
    `compass check` runs counted in `.compass/interruptions.log`. None when
    the session has no Compass project, so a condition without Compass
    reads "not recorded" in the report, not zero. A line that does not
    parse is skipped, as `compass retro` skips it."""
    compass_dir = repo_dir / ".compass"
    if not compass_dir.is_dir():
        return None
    counts = {"hook_blocks": 0, "check_failures": 0}
    log = compass_dir / "interruptions.log"
    try:
        lines = log.read_text(encoding="utf-8").splitlines()
    except OSError:
        return counts
    for line in lines:
        parts = line.split("\t")
        if len(parts) == 3 and parts[2] in counts:
            counts[parts[2]] += 1
    return counts


# --- containment -------------------------------------------------------------

# Every relative name this module hashes under both a working tree's own git
# directory and its common directory - the same directory for an ordinary
# checkout, but the worktree's own private directory and the main
# repository's shared one for a linked worktree. Never listed by `git
# ls-files`, whatever its flags, so a session's own conftest.py cannot
# rewrite a hook or a config unseen.
_GIT_DIR_WATCHED_NAMES = ("config", "config.worktree", "HEAD", "refs",
                          "packed-refs", "hooks", "info")


def _resolve_git_and_common_dir(root: Path, env: dict[str, str]
                                 ) -> tuple[Path | None, Path | None]:
    """`root`'s own git directory and common directory, from `git rev-parse
    --git-dir --git-common-dir` (through `_run_git`), resolved to absolute
    paths against `root`. The same directory for an ordinary checkout; the
    worktree's own private directory and the main repository's shared one
    when `root` is a linked worktree, whose `.git` is a file naming the
    private one. `(None, None)` when `git rev-parse` itself fails - `.git`
    a plain file with no valid target, for instance - so the caller can
    record that as a change instead of raising."""
    proc = _run_git(["rev-parse", "--git-dir", "--git-common-dir"], root, env)
    if proc.returncode != 0:
        return None, None
    lines = proc.stdout.splitlines()
    if len(lines) < 2:
        return None, None
    git_dir = (root / lines[0]).resolve()
    common_dir = (root / lines[1]).resolve()
    return git_dir, common_dir


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_checkout_hash(root: Path, base_dir: Path, path: Path, label: str,
                           snapshot: dict[str, str]) -> None:
    """The snapshot key for `path`, hashed under `base_dir`: the path
    relative to `root` when `path` is inside it, so an ordinary checkout
    keeps the key `.git/config` for that file, or `label` plus the path
    relative to `base_dir` when it is not - a linked worktree's common
    directory, living in the main repository elsewhere."""
    try:
        key = path.relative_to(root).as_posix()
    except ValueError:
        key = f"{label}:{path.relative_to(base_dir).as_posix()}"
    snapshot[key] = _hash_file(path)


def _hash_watched_git_dir_paths(root: Path, base_dir: Path, label: str,
                                 snapshot: dict[str, str]) -> None:
    for name in _GIT_DIR_WATCHED_NAMES:
        path = base_dir / name
        if path.is_file():
            _record_checkout_hash(root, base_dir, path, label, snapshot)
        elif path.is_dir():
            for sub in sorted(path.rglob("*")):
                if sub.is_file():
                    _record_checkout_hash(root, base_dir, sub, label, snapshot)


def _checkout_fingerprint(root: Path, env: dict[str, str]) -> dict[str, str]:
    """Hash every tracked file's content, every untracked one - ignored
    included - and, under both `root`'s own git directory and its common
    directory (`_resolve_git_and_common_dir`), `config`, `config.worktree`,
    `HEAD`, `refs/`, `packed-refs`, `hooks/` and `info/`
    (`_GIT_DIR_WATCHED_NAMES`). A status code, such as `git status
    --porcelain`'s `M`, does not change between two different edits to the
    same already-changed file, and collapses a whole new directory to one
    `??` line - so a further edit, or a change inside a new directory,
    would pass unseen. `git ls-files --others` lists the files inside an
    untracked directory itself, so the hash catches both. No
    `--exclude-standard` is passed, so an ignored path - `evals/out/`,
    `.compass/work/` and `docs/compass/*/` in this repository - is hashed
    the same as any other untracked file: a session can rewrite one of
    those unseen otherwise. `git ls-files` never lists anything under a
    git directory at all, so `_hash_watched_git_dir_paths` covers a written
    hook, a moved `HEAD` and a rewritten `refs/` directly, and the same for
    a change made only in a linked worktree's main repository. If `root`'s
    own git directory cannot be resolved - `.git` a plain file with no
    valid target, for instance - the snapshot carries a marker a
    resolvable checkout's own never does, so the comparison still shows a
    change instead of raising."""
    tracked = _run_git(["ls-files", "-z"], root, env).stdout.split("\0")
    untracked = _run_git(["ls-files", "-z", "--others"], root, env).stdout.split("\0")
    snapshot: dict[str, str] = {}
    for rel in [*tracked, *untracked]:
        if not rel:
            continue
        path = root / rel
        if path.is_file():
            snapshot[rel] = _hash_file(path)

    git_dir, common_dir = _resolve_git_and_common_dir(root, env)
    if git_dir is None:
        snapshot["git-dir:unresolved"] = "true"
        return snapshot
    _hash_watched_git_dir_paths(root, git_dir, "git-dir", snapshot)
    if common_dir is not None and common_dir != git_dir:
        _hash_watched_git_dir_paths(root, common_dir, "git-common-dir", snapshot)
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


def _compass_commit(plugin_source: Path, plugin_copy_dir: Path | None,
                     env: dict[str, str]) -> str | None:
    """`plugin_source`'s own `HEAD` commit - the Compass checkout the
    compass condition's plugin copy was built from (EGB-5) - `None` for
    every other condition, which never loads Compass into the session at
    all: `plugin_source` is still hashed for containment either way, but
    nothing there runs."""
    if plugin_copy_dir is None:
        return None
    return _run_git(["rev-parse", "HEAD"], plugin_source, env).stdout.strip()


def run_once(scenario: dict[str, Any], scenario_dir: Path, condition: str,
             run_index: int, claude_exe: str, *, plugin_source: Path,
             plugin_copy_dir: Path | None,
             framework_copy_dir: Path | None = None,
             framework_commit: str | None = None, uvx_exe: str = "uvx",
             r1_scripts_dir: Path,
             child_env: dict[str, str],
             seed_paths: dict[str, str] | None = None,
             session_user: SessionUser | None = None
             ) -> dict[str, Any]:
    """Do one run of `scenario` under `condition` and return its record.
    `plugin_copy_dir`, `framework_copy_dir`, `framework_commit`,
    `r1_scripts_dir` and `child_env` are built once per harness
    call, by `_prepare_plugin_copy` and `_prepare_framework_copy`, and
    reused by every run - never rebuilt here."""
    started = datetime.now(timezone.utc).isoformat()
    clock_start = time.monotonic()
    state = _new_run_state()
    if session_user is not None:
        state["as_user"] = (session_user.uid, session_user.gid)
    final_text = ""
    exit_code = 0
    skipped_for_budget = False
    replies_sent = 0
    record_cwd: str | None = None

    claude_version = _claude_version(claude_exe, child_env)
    compass_commit = _compass_commit(plugin_source, plugin_copy_dir, child_env)
    checkout_before = _checkout_fingerprint(plugin_source, child_env)
    plugin_before = _dir_snapshot(plugin_copy_dir) if plugin_copy_dir else None

    with tempfile.TemporaryDirectory() as tmp:
        repo_dir = Path(tmp)
        _materialise_repo(scenario_dir, condition, repo_dir,
                           plugin_copy_dir, framework_copy_dir, uvx_exe,
                           child_env, seed_paths)
        seed_commit = _git_init_and_commit(repo_dir, child_env)
        seed_git_snapshot = _snapshot_git_config(repo_dir)
        if session_user is not None:
            # The seed is committed by the harness; from here the working
            # folder is the session user's, and nothing else is.
            _hand_to(repo_dir, session_user)
        tampered_paths: list[str] = []

        test_command = scenario.get("test_command", _DEFAULT_TEST_COMMAND)
        hidden_tests_dir = scenario_dir / "hidden_tests"
        has_hidden_tests = hidden_tests_dir.is_dir()
        seed_outcomes: dict[str, str] = {}
        if has_hidden_tests:
            # The baseline for CMP-2's own `regressions`: which of the
            # seed's own tests pass before the session runs, taken now -
            # before `hidden_tests/` is copied in, so a hidden test never
            # counts as a "regression" simply for having no earlier result.
            _, seed_output = _run_test_command(
                _seed_test_command_with_report(test_command), repo_dir, child_env)
            seed_outcomes = _pytest_outcomes(seed_output)

        common_args = _common_claude_args(condition, plugin_copy_dir, framework_copy_dir,
                                           r1_scripts_dir)
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
            seed_commit=seed_commit, seed_git_snapshot=seed_git_snapshot,
            tampered_paths=tampered_paths)
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
                env=child_env, seed_commit=seed_commit,
                seed_git_snapshot=seed_git_snapshot,
                tampered_paths=tampered_paths)
            if reply_exit is not None:
                exit_code = reply_exit
            if reply_text:
                final_text = reply_text

        state["tool_calls"].sort(key=lambda call: call["index"])
        _finalise_tool_calls(state)
        diff_text, changed_paths, changed = _diff_since_seed(
            repo_dir, seed_commit, child_env, seed_git_snapshot, tampered_paths)

        hidden_record: dict[str, Any] | None = None
        regressions: list[str] | None = None
        if has_hidden_tests:
            # Run the seed's own test command once more, after the
            # session's edits but still before `hidden_tests/` lands.
            # Pytest's default behaviour on a collection error is to
            # abort the whole run, not only skip the one file that failed
            # to import - so measuring "after" with the hidden test
            # already sitting beside the seed's own tests would count
            # every seed test as regressed the moment a hidden test names
            # a function the session never wrote (CMP-2).
            tests_exit_code, after_output = _run_test_command(
                _seed_test_command_with_report(test_command), repo_dir, child_env)
            regressions = _seed_regressions(seed_outcomes, _pytest_outcomes(after_output))

            # Copied in only now, after the session has ended - a session
            # can never read `hidden_tests/`, never mind the rubric inside
            # it (CMP-2).
            _copy_tracked_files(hidden_tests_dir, repo_dir, child_env)
            hidden_command = scenario["hidden_command"]
            hidden_exit, hidden_output = _run_test_command(
                hidden_command, repo_dir, child_env)
            hidden_passed, hidden_failed = _pytest_summary_counts(hidden_output)
            hidden_defined = hidden_tests_defined_count(hidden_tests_dir)
            hidden_passed, hidden_failed = corrected_hidden_counts(
                hidden_passed, hidden_failed, hidden_defined, hidden_exit)
            # `defined` records the count this run's hidden tests had, so
            # a later re-score corrects against it, not against a hidden
            # test file that may have changed since.
            hidden_record = {
                "command": hidden_command, "exit_code": hidden_exit,
                "passed": hidden_passed, "failed": hidden_failed,
                "defined": hidden_defined,
            }
        else:
            tests_exit_code, _tests_output = _run_test_command(
                test_command, repo_dir, child_env)

        compass_files = _compass_files(repo_dir)
        manifests = _manifests(repo_dir)
        interruptions = _interruptions(repo_dir)
        record_cwd = state["cwd"]

    checkout_after = _checkout_fingerprint(plugin_source, child_env)
    plugin_after = _dir_snapshot(plugin_copy_dir) if plugin_copy_dir else None

    escaped_paths = [f"checkout:{path}" for path in
                      _dir_snapshot_changed_paths(checkout_before, checkout_after)]
    if plugin_copy_dir is not None:
        escaped_paths += [f"plugin:{path}" for path in
                           _dir_snapshot_changed_paths(plugin_before, plugin_after)]
    # `_TAMPER_WATCHED_RELATIVE_PATHS` names the three files git reads its
    # own settings or the location of its real git directory from -
    # `.git/config` and `.git/info/attributes` hold settings,
    # `.git/commondir` a location, not a config file itself. A path
    # `_run_guarded_git` or `_diff_since_seed` adds beyond that list -
    # `.git/HEAD`, or `.git` itself when a guarded call simply failed - is
    # git's own repository state, not config, so it gets its own label.
    escaped_paths += [
        (f"git-config:{path}" if path in _TAMPER_WATCHED_RELATIVE_PATHS
         else f"git-state:{path}")
        for path in sorted(set(tampered_paths))]
    contained = not escaped_paths

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
        "tokens": state["tokens"],
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
        "hidden": hidden_record,
        "regressions": regressions,
        "framework": ({"name": condition, "commit": framework_commit}
                       if framework_copy_dir is not None else None),
        "compass_commit": compass_commit,
        "contained": contained,
        "escaped_paths": escaped_paths,
        "uid": os.geteuid(),
        "ran_as_root": os.geteuid() == 0,
        "session_uid": (session_user.uid if session_user is not None
                        else os.geteuid()),
        "python_version": "{}.{}.{}".format(*sys.version_info[:3]),
        "stderr_tail": _tail(state["stderr"]),
        "over_budget": over_budget,
        "replies_sent": replies_sent,
        "interruptions": interruptions,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one eval scenario under one condition and record it."
    )
    parser.add_argument("--scenario", required=True,
                         help="a scenario id under evals/scenarios/, or a "
                              "path to a scenario directory")
    parser.add_argument("--condition", required=True,
                         choices=["compass", "bare", "R1", "R3"])
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
    parser.add_argument("--framework-source", default=None,
                         help="a local directory already checked out at a "
                              "framework's own commit, used for the "
                              "R1 or R3 condition instead of "
                              "cloning the names key's pinned "
                              "repository - what a test points at a "
                              "fixture with, so it never reaches the "
                              "network")
    parser.add_argument("--uvx", default="uvx",
                         help="the executable to run R3's own "
                              "specify init through - a real uvx, or a "
                              "stand-in for a test")
    parser.add_argument("--session-user", default=None, metavar="NAME",
                        help="run as root, start every session as this "
                             "unprivileged user, so the run stays contained")
    parser.add_argument("--allow-root", action="store_true",
                        help="a person's decision to run the compass "
                             "condition as root uncontained; refused when "
                             "CI or COMPASS_UNATTENDED is set")
    parser.add_argument("--frameworks-config", default=None,
                         help="the names key, or a file of the same "
                              "pins, the "
                              "R1 or R3 condition checks "
                              "its own commit against, whether cloned or "
                              "given by --framework-source - defaults to "
                              "COMPASS_RIVALS_KEY, then "
                              ".compass/private/rival-codes.yml; a test "
                              "points this at "
                              "a fixture pinning its own fixture commit")
    return parser


def _prepare_plugin_copy(condition: str, plugin_source: Path, *,
                         session_user: SessionUser | None = None
                         ) -> tuple[Path | None, dict[str, str]]:
    """Build the compass condition's plugin copy once, from `plugin_source`,
    and the child environment naming its own `bin/` - both reused by every
    run this harness call makes, never rebuilt per run. `(None, env)` for
    the bare condition, which loads no plugin."""
    plugin_copy_dir: Path | None = None
    if condition == "compass":
        # The system's default temporary name - no prefix - so a session
        # that can see its own working directory learns neither the
        # scenario nor the condition from its name.
        plugin_copy_dir = Path(tempfile.mkdtemp())
    child_env = _build_child_env(condition, plugin_copy_dir,
                                 session_user=session_user)
    if plugin_copy_dir is not None:
        _make_plugin_copy(plugin_source, plugin_copy_dir, child_env)
    return plugin_copy_dir, child_env


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    scenario_dir = _resolve_scenario_dir(args.scenario)
    if not scenario_dir.is_dir():
        print(f"no scenario directory at {scenario_dir}", file=sys.stderr)
        return 1
    scenario = load_scenario(scenario_dir)
    rivals_key: Path | None = None
    if args.condition in ("R1", "R3"):
        rivals_key = (Path(args.frameworks_config) if args.frameworks_config
                      else rivals_key_path())
        if not rivals_key.is_file():
            # Without the maintainer's key there is nothing to clone or pin
            # against; bare and compass never need it.
            print(f"skipped: the {args.condition} condition needs the rival "
                  f"key ({rivals_key} is missing; set COMPASS_RIVALS_KEY or "
                  f"--frameworks-config)", file=sys.stderr)
            return 0
    out_dir = Path(args.out) if args.out else (REPO_ROOT / "evals" / "out")
    out_dir.mkdir(parents=True, exist_ok=True)
    plugin_source = Path(args.plugin_source) if args.plugin_source else REPO_ROOT
    framework_source_override = (
        Path(args.framework_source) if args.framework_source else None)

    # A session user is checked before anything is built, because the
    # session's environment and files depend on it.
    session_user: SessionUser | None = None
    if args.session_user:
        refusal = _root_refusal(args.condition, None, allow_root=args.allow_root,
                                euid=_euid(), session_user=args.session_user)
        if refusal:
            print(refusal, file=sys.stderr)
            return 2
        session_user = SessionUser.of(_lookup_user(args.session_user))
    plugin_copy_dir, child_env = _prepare_plugin_copy(
        args.condition, plugin_source, session_user=session_user)
    refusal = _root_refusal(args.condition, plugin_copy_dir,
                            allow_root=args.allow_root, euid=_euid(),
                            session_user=args.session_user)
    if refusal:
        if plugin_copy_dir is not None:
            _remove_read_only_tree(plugin_copy_dir)
        print(refusal, file=sys.stderr)
        return 2
    framework_copy_dir: Path | None = None
    framework_commit: str | None = None
    seed_paths: dict[str, str] = {}
    if args.condition in ("R1", "R3"):
        # Loaded whether or not `--framework-source` is given: a cloned
        # framework and one a test or an operator points at directly are
        # checked against the same pin.
        frameworks_config = load_frameworks_config(rivals_key)
        seed_paths = dict((frameworks_config.get(args.condition) or {})
                          .get("paths") or {})
        framework_copy_dir, framework_commit = _prepare_framework_copy(
            args.condition, framework_source_override, frameworks_config, child_env)

    # Every condition's allow-list carries the same five R1-script
    # rules, each built with this directory's own absolute path. The
    # R1 condition reuses its own `--plugin-dir` copy - the one
    # path a session there could actually run those scripts from; every
    # other condition gets a fresh, otherwise-unused directory, never
    # mounted as a plugin, kept only so its allow-list has the same rules
    # to offer, even though nothing loads R1 there to use them.
    r1_scripts_dir_is_framework_copy = args.condition == "R1"
    if r1_scripts_dir_is_framework_copy:
        r1_scripts_dir = framework_copy_dir
    else:
        r1_scripts_dir = Path(tempfile.mkdtemp())
    if session_user is not None:
        for shared in (plugin_copy_dir, framework_copy_dir, r1_scripts_dir):
            if shared is not None:
                _open_for_session_user(shared)
    try:
        for run_index in range(1, args.runs + 1):
            record = run_once(scenario, scenario_dir, args.condition, run_index,
                               args.claude, plugin_source=plugin_source,
                               plugin_copy_dir=plugin_copy_dir,
                               framework_copy_dir=framework_copy_dir,
                               framework_commit=framework_commit,
                               uvx_exe=args.uvx,
                               r1_scripts_dir=r1_scripts_dir,
                               child_env=child_env, seed_paths=seed_paths,
                               session_user=session_user)
            out_path = out_dir / f"{scenario['id']}-{args.condition}-{run_index}.json"
            out_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    finally:
        if plugin_copy_dir is not None:
            _remove_read_only_tree(plugin_copy_dir)
        if framework_copy_dir is not None:
            _remove_read_only_tree(framework_copy_dir)
        if not r1_scripts_dir_is_framework_copy:
            shutil.rmtree(r1_scripts_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
