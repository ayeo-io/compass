#!/usr/bin/env python3
# =============================================================================
# compass - start one `claude -p` session
# =============================================================================
# The one place Compass starts a model session (ADR-030). `compass run`
# calls it once per cycle, and the eval harness (`evals/harness.py`) calls it
# for every session it drives, so the two cannot drift into two launchers
# with different arguments or different handling of a hung session.
#
# It starts the process and returns what came back. It reads no credential
# and adds none: the caller's environment is passed on as it is.
#
# DEPENDENCY: standard library (json, os, signal, subprocess).
# =============================================================================
"""Start one `claude -p` call and read the result event it prints."""
from __future__ import annotations

import json
import os
import signal
import subprocess
from typing import NamedTuple


class Launch(NamedTuple):
    """What one call returned. `timed_out` is True when the call ran past
    its timeout and was ended; `returncode` is then -1."""
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


def launch_claude(claude_exe, message, args, cwd, env, timeout=None):
    """Run `claude -p <message> <args...>` in `cwd` with `env`, with no
    standard input, and return a `Launch`.

    With a `timeout`, the session starts in its own process group, and a
    call past `timeout` seconds has the whole group ended - the session and
    anything it started - and is reported as timed out, not raised. Ending
    only `claude` would leave a command it started running after the run
    has stopped. Without a timeout the call waits, as the eval harness's
    sessions, bounded by their budget, always have."""
    command = [claude_exe, "-p", message, *args]
    if timeout is None:
        proc = subprocess.run(command, cwd=str(cwd), env=env,
                              capture_output=True, text=True,
                              stdin=subprocess.DEVNULL)
        return Launch(proc.returncode, proc.stdout or "", proc.stderr or "",
                      False)
    proc = subprocess.Popen(command, cwd=str(cwd), env=env, text=True,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _end_group(proc)
        stdout, stderr = proc.communicate()
        return Launch(-1, stdout or "", stderr or "", True)
    except BaseException:
        # Interrupted (Ctrl-C, a cancelled CI job): the session has its own
        # group, so the signal did not reach it. End it before going on.
        _end_group(proc)
        proc.wait()
        raise
    return Launch(proc.returncode, stdout or "", stderr or "", False)


def _end_group(proc):
    """End the session's process group: the session and what it started."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proc.kill()


def session_summary(stdout):
    """The last `result` event's session id, cost, error flag and final
    text, read from
    the line-delimited JSON output, or empty values when it holds none."""
    summary = {"session_id": None, "cost_usd": None, "is_error": None,
               "result": None}
    for line in (stdout or "").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            summary = {"session_id": event.get("session_id"),
                       "cost_usd": event.get("total_cost_usd"),
                       "is_error": event.get("is_error"),
                       "result": event.get("result")}
    return summary
