# compass_pkg.readiness_run - runs the project commands a readiness run needs
"""Run the project commands of a readiness run, one at a time, in one
temporary worktree of HEAD (ADR-061).

- The temporary worktree is a detached `git worktree add` of HEAD in the
  system temp folder, named `compass-readiness-<process id>-<random>`. It is
  outside `multiagent.worktree_root` and not counted against
  `max_worktrees`. It holds no ignored or uncommitted file, and whatever a
  command writes there is removed with it, so the working tree never changes.
- It is removed in a `finally` block with `git worktree remove --force`, then
  `git worktree prune`.
- Each command runs in a new session. At its limit its whole process group is
  sent SIGKILL, so a build's child process cannot outlive the run.
- The commands share `COMMAND_SECONDS`. The timed test command also stops at
  its own limit. `COMPASS_READINESS_BUDGET_SECONDS` can only lower the
  budget, and only tests set it.

Nothing here decides whether a command may run: the caller asks
`project_commands.command_permission` first, and calls this only when it
allows and at least one command is declared.
"""
# DEPENDENCY: standard library (contextlib, dataclasses, os, shutil, signal,
# subprocess, sys, tempfile, time); imports nothing from Compass.
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass

#: The settings keys of the project commands, in the order they run: the
#: floor's commands first (build, then tests, then lint), then type check,
#: then format check. `test` stands for whichever key the test signal times.
ORDER = ("build_command", "test", "lint_command", "typecheck_command", "format_check_command")
TOTAL_SECONDS = 300
COMMAND_SECONDS = 270
BUDGET_ENV = "COMPASS_READINESS_BUDGET_SECONDS"
WORKTREE_PREFIX = "compass-readiness-"
#: How much of a command's output a reason keeps: the end, where a failure is.
OUTPUT_TAIL = 2000


@dataclass(frozen=True)
class Planned:
    """One command to run: the signal it decides, the settings key and the
    command text, and its own limit in seconds (None: only the budget)."""
    signal_id: str
    key: str
    command: str
    limit_seconds: float | None = None


@dataclass(frozen=True)
class Outcome:
    """What happened to one planned command. `status` is `passed`, `failed`,
    `over-limit` (its own limit stopped it), `over-budget` (the budget
    stopped it) or `not-started` (the budget ended before it began)."""
    signal_id: str
    key: str
    command: str
    status: str
    exit_code: int | None = None
    duration_seconds: float | None = None
    output_tail: str = ""


def command_budget(env=None, warn=None):
    """The seconds the project commands share: `COMMAND_SECONDS`, or the
    test variable when it is a positive number, never more than
    `COMMAND_SECONDS`. Any other value is ignored with a warning."""
    env = os.environ if env is None else env
    raw = env.get(BUDGET_ENV)
    if raw is None or raw == "":
        return COMMAND_SECONDS
    try:
        value = float(raw)
    except ValueError:
        value = 0.0
    if not value > 0:
        (warn or _warn)(f"{BUDGET_ENV}={raw!r} is not a positive number of seconds; "
                        f"using {COMMAND_SECONDS}")
        return COMMAND_SECONDS
    return min(value, COMMAND_SECONDS)


def _warn(text):
    print(f"compass readiness: warning: {text}", file=sys.stderr)


def _git(root, *argv, check=True):
    done = subprocess.run(["git", *argv], cwd=root, capture_output=True, text=True,
                          timeout=120)
    if check and done.returncode != 0:
        raise OSError((done.stderr or done.stdout).strip() or f"git {argv[0]} failed")
    return done


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _owner_pid(path):
    """The process id in a temporary worktree's folder name, or None for
    any other worktree."""
    name = os.path.basename(path.rstrip(os.sep))
    if not name.startswith(WORKTREE_PREFIX):
        return None
    pid, _, _ = name[len(WORKTREE_PREFIX):].partition("-")
    return int(pid) if pid.isdigit() else None


def remove_left_worktrees(root):
    """Remove the temporary worktrees a killed run left: those whose process
    id is no longer alive, then prune. A worktree whose process is alive
    belongs to a run still going on, perhaps in another checkout of this
    repository, and is kept. Returns the paths removed."""
    listing = _git(root, "worktree", "list", "--porcelain", check=False)
    if listing.returncode != 0:
        return []
    removed = []
    for line in listing.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        path = line.split(" ", 1)[1]
        pid = _owner_pid(path)
        if pid is None or _alive(pid):
            continue
        _git(root, "worktree", "remove", "--force", path, check=False)
        shutil.rmtree(path, ignore_errors=True)
        removed.append(path)
    if removed:
        _git(root, "worktree", "prune", check=False)
    return removed


@contextmanager
def temporary_worktree(root):
    """A detached worktree of HEAD in the system temp folder, removed and
    pruned however the block ends."""
    folder = tempfile.mkdtemp(prefix=f"{WORKTREE_PREFIX}{os.getpid()}-")
    try:
        _git(root, "worktree", "add", "--detach", "--quiet", folder, "HEAD")
        yield folder
    finally:
        _git(root, "worktree", "remove", "--force", folder, check=False)
        _git(root, "worktree", "prune", check=False)
        shutil.rmtree(folder, ignore_errors=True)


def _stop(proc):
    """Stop a command that ran over its limit, with every process it
    started: the command leads its own process group (`start_new_session`),
    so the group is the command and its children."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proc.kill()
    proc.wait()


def _run_one(entry, cwd, seconds_left):
    own_limit = entry.limit_seconds is not None and entry.limit_seconds <= seconds_left
    limit = entry.limit_seconds if own_limit else seconds_left
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as output:
        start = time.monotonic()
        proc = subprocess.Popen(entry.command, shell=True, cwd=cwd, stdout=output,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                start_new_session=True)
        try:
            code = proc.wait(timeout=limit)
            status = "passed" if code == 0 else "failed"
        except subprocess.TimeoutExpired:
            _stop(proc)
            code, status = None, "over-limit" if own_limit else "over-budget"
        duration = round(time.monotonic() - start, 1)
        output.seek(0)
        tail = output.read()[-OUTPUT_TAIL:]
    return Outcome(entry.signal_id, entry.key, entry.command, status, code, duration, tail)


def run_commands(root, planned, budget_seconds, started=None):
    """Run each planned command in one temporary worktree of HEAD, sharing
    `budget_seconds` from `started` (a `time.monotonic()` value; now when not
    given). Returns one `Outcome` per planned command, in the order run."""
    started = time.monotonic() if started is None else started
    deadline = started + budget_seconds
    outcomes = []
    with temporary_worktree(root) as folder:
        for entry in order(planned):
            seconds_left = deadline - time.monotonic()
            if seconds_left <= 0:
                outcomes.append(Outcome(entry.signal_id, entry.key, entry.command,
                                        "not-started"))
                continue
            outcomes.append(_run_one(entry, folder, seconds_left))
    return outcomes


#: The keys the test signal can time; each runs in the `test` place of `ORDER`.
TEST_KEYS = ("test_command", "test_micro_command")


def order(planned):
    """`planned` in the order the commands run: by `ORDER`, then any other
    command (one a project layer added) in the order given."""
    def rank(item):
        index, entry = item
        place = "test" if entry.key in TEST_KEYS else entry.key
        return (ORDER.index(place) if place in ORDER else len(ORDER), index)
    return [entry for _, entry in sorted(enumerate(planned), key=rank)]
