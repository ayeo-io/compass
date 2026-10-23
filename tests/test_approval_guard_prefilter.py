"""The shell prefilter of the approval guard (issue
`approval-guard-ifs-as-and-delegation-globs`).

The hook starts python3 for the guard only when a call can need it. A glob
character after `.compass/` or after `deleg` in a Bash command can reach the
delegation files, so it must start the guard. An ordinary call must not, or
every shell command would pay for a python3 start.

The test runs a copy of the hook in which the guard module raises. The hook
refuses a call whose guard cannot run (`reader-failed`), so a refusal shows
that the call started the guard and a pass shows that it did not.

Scenario id: `TRC-013` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from test_pre_tool_hook import HOOK_PATH, _guarded_project  # noqa: E402

# Each command holds a glob character after `.compass/` or `deleg`.
STARTS_GUARD = (
    "cat .compass/deleg*/*",
    "cat .comp*/deleg*/*",
    "ls .compass/work/*",
    "cat .compass/deleg?tions/DL-1.yml",
    "cat .compass/[d]eleg*/*",
    "ls .compass/d*",
    # Letter case is ignored, as macOS opens a path in any case.
    "cat .Compass/Deleg*/*",
    # A glob before `deleg` starts the guard too: the hook tests the command
    # twice, so the glob in one copy comes after `deleg` in the other.
    "cat .c*/delegations",
    # A flag or verb built with braces or ANSI-C quoting shows no `--del`.
    "compass evidence approve --{delegated,x}",
    "compass evidence appr{ove,x}",
    "compass evidence $'appro\\x76e'",
)

# None of these can reach the delegation folder through a glob.
STARTS_NO_GUARD = (
    "ls src/*.py",
    "cat docs/*.md",
    "git status",
    "grep -rn approve src",
    "ls",
    "compass evidence list --scope x",
    "echo {a,b} $'x'",
)


def _broken_copy(tmp_path):
    """A copy of the plugin whose guard module cannot be imported."""
    keep = shutil.ignore_patterns("__pycache__", "*.pyc")
    copy = tmp_path / "plugin"
    for folder in ("hooks", "scripts/lib", "cli"):
        shutil.copytree(ROOT / folder, copy / folder, ignore=keep)
    guard = copy / "cli" / "compass_pkg" / "approval_guard.py"
    guard.write_text("raise RuntimeError('the guard cannot run')\n", encoding="utf-8")
    return copy / "hooks" / "pre-tool.sh"


def _run(hook, project, command):
    body = {"tool_name": "Bash", "session_id": "sess-prefilter",
            "tool_input": {"command": command}, "cwd": str(project)}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project), PYTHONDONTWRITEBYTECODE="1")
    started = time.monotonic()
    result = subprocess.run(["bash", str(hook)], input=json.dumps(body),
                            capture_output=True, text=True, env=env)
    return result, time.monotonic() - started


def test_trc_013_prefilter_starts_guard_only_where_needed(tmp_path):
    """Scenario id: `TRC-013` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    project, _ = _guarded_project()
    try:
        broken = _broken_copy(tmp_path)

        for command in STARTS_GUARD:
            r, _ = _run(broken, project, command)
            assert r.returncode == 2 and "[reader-failed]" in r.stderr, (
                command, r.returncode, r.stderr)

        for command in STARTS_NO_GUARD:
            r, took = _run(broken, project, command)
            assert r.returncode == 0, (command, r.returncode, r.stderr)
            assert took < 2.0, (command, took)

        # Control on the intact hook: the broken copy does not pass the first
        # set merely because every call is refused.
        for command in STARTS_NO_GUARD:
            r, _ = _run(HOOK_PATH, project, command)
            assert r.returncode == 0, (command, r.returncode, r.stderr)
        r, _ = _run(HOOK_PATH, project, "cat .compass/delegations/DL-1.yml")
        assert r.returncode == 2 and "[delegation-protected]" in r.stderr, r.stderr
        # The glob form reaches the same folder and the guard must refuse it
        # with the same code.
        r, _ = _run(HOOK_PATH, project, "cat .compass/deleg*/*")
        assert r.returncode == 2 and "[delegation-protected]" in r.stderr, (
            r.returncode, r.stderr)
    finally:
        shutil.rmtree(project, ignore_errors=True)


# --- issue `approval-prefilter-bounds` (delivery-record #246) ---------------
# The shell removes a backslash-newline outside single quotes and joins the
# text around it, so a protected name split that way still reaches its folder.

REQUEST_FOLDER = "approval-" + "requests"
DELEGATION_FOLDER = ".compass/" + "delegations"


def _split(name):
    cut = len(name) // 2
    return name[:cut] + "\\\n" + name[cut:]


def test_trc_001_split_request_folder_is_refused(tmp_path):
    """A request folder name split by a backslash-newline starts the guard,
    and the guard refuses it. Scenario `TRC-001` of issue
    `approval-prefilter-bounds`."""
    project, _ = _guarded_project()
    try:
        command = f"cat .compass/work/x/{_split(REQUEST_FOLDER)}/pending/1.yml"
        r, _ = _run(HOOK_PATH, project, command)
        assert r.returncode == 2 and "[approval-request-protected]" in r.stderr, (
            r.returncode, r.stderr)
        r, _ = _run(_broken_copy(tmp_path), project, command)
        assert r.returncode == 2 and "[reader-failed]" in r.stderr, (r.returncode, r.stderr)
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_trc_002_split_delegation_folder_is_refused():
    """A delegation folder name split by a backslash-newline is refused, bare
    or inside double quotes. Scenario `TRC-002` of issue
    `approval-prefilter-bounds`."""
    project, _ = _guarded_project()
    try:
        for command in (f"ls {_split(DELEGATION_FOLDER)}",
                        f'cat "{_split(DELEGATION_FOLDER)}/DL-1.yml"'):
            r, _ = _run(HOOK_PATH, project, command)
            assert r.returncode == 2 and "[delegation-protected]" in r.stderr, (
                command, r.returncode, r.stderr)
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_trc_003_single_quoted_backslash_newline_is_kept():
    """Inside single quotes the shell keeps a backslash-newline, so the text
    names no protected folder and passes. Scenario `TRC-003` of issue
    `approval-prefilter-bounds`."""
    project, _ = _guarded_project()
    try:
        for command in ("echo 'a\\\nb'", f"ls '{_split(DELEGATION_FOLDER)}'"):
            r, _ = _run(HOOK_PATH, project, command)
            assert r.returncode == 0, (command, r.returncode, r.stderr)
    finally:
        shutil.rmtree(project, ignore_errors=True)
    # The guard's text keeps the two characters inside single quotes, and
    # drops them outside quotes and inside double quotes, as the shell does.
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg.approval_guard import _join_continuations
    assert _join_continuations("echo 'a\\\nb'") == "echo 'a\\\nb'"
    assert _join_continuations('echo a\\\nb "c\\\nd"') == 'echo ab "cd"'
    assert _join_continuations("echo $'a\\\nb'") == "echo $'a\\\nb'"


def _run_bounded(project, command, limit=10.0):
    """`_run` with a hard limit. The hook and the guard it starts run in their
    own process group, which is stopped whole, so a slow guard is not left
    running. The exit code is None when the limit was reached."""
    import signal
    body = {"tool_name": "Bash", "session_id": "sess-prefilter",
            "tool_input": {"command": command}, "cwd": str(project)}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project), PYTHONDONTWRITEBYTECODE="1")
    started = time.monotonic()
    proc = subprocess.Popen(["bash", str(HOOK_PATH)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            env=env, start_new_session=True)
    try:
        _, err = proc.communicate(json.dumps(body), timeout=limit)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        return None, "", time.monotonic() - started
    return proc.returncode, err, time.monotonic() - started


def _decided_fast(project, short, long):
    """The long command finishes in under 2 seconds with the short one's exit code."""
    expected, _, _ = _run_bounded(project, short)
    code, err, took = _run_bounded(project, long)
    assert code is not None and took < 2.0, (long[:40], took)
    assert code == expected, (code, expected, err)


def test_trc_004_long_ansi_c_word_is_decided_fast():
    """An unclosed ANSI-C quote of 90 KB took 10 seconds on main. Scenario
    `TRC-004` of issue `approval-prefilter-bounds`."""
    project, _ = _guarded_project()
    try:
        _decided_fast(project, "compass evidence list $'" + "a" * 10,
                      "compass evidence list $'" + "a" * 90000)
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_trc_005_long_bracket_word_is_decided_fast():
    """`[a` repeated 20,000 times after `.compass/` took 56 seconds on main.
    Scenario `TRC-005` of issue `approval-prefilter-bounds`."""
    project, _ = _guarded_project()
    try:
        _decided_fast(project, "cat .compass/" + "[a" * 5, "cat .compass/" + "[a" * 20000)
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_trc_006_nested_class_openers_are_decided_fast():
    """`[[:` repeated makes each opener search the rest of the glob for a class
    end. Scenario `TRC-006` of issue `approval-prefilter-bounds`."""
    project, _ = _guarded_project()
    try:
        _decided_fast(project, "cat .compass/" + "[[:" * 5, "cat .compass/" + "[[:" * 20000)
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_trc_007_ordinary_commands_start_no_guard(tmp_path):
    """Ordinary commands, and one continued on a second line, start no guard.
    Scenario `TRC-007` of issue `approval-prefilter-bounds`."""
    project, _ = _guarded_project()
    try:
        broken = _broken_copy(tmp_path)
        for command in (*STARTS_NO_GUARD, "printf 'a %s' b \\\nc"):
            r, took = _run(broken, project, command)
            assert r.returncode == 0, (command, r.returncode, r.stderr)
            assert took < 2.0, (command, took)
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_trc_009_long_operator_run_is_decided_fast():
    """The pattern that finds an escape in command position retried from each
    `;` and took 5 seconds here. Scenario `TRC-009` of issue
    `approval-prefilter-bounds`."""
    project, _ = _guarded_project()
    try:
        verb = "compass evid" + "ence list "
        _decided_fast(project, verb + "x;" * 5 + "$'a", verb + "x;" * 45000 + "$'a")
    finally:
        shutil.rmtree(project, ignore_errors=True)


# --- review findings on `approval-prefilter-bounds` -------------------------

def test_trc_010_split_name_after_a_quote_the_shell_does_not_read_is_refused():
    """An apostrophe in a comment, in an unquoted heredoc or inside `$( )` or
    backticks is not a quote to the shell, which still joins the
    backslash-newline after it. Scenario `TRC-010` of issue
    `approval-prefilter-bounds`."""
    project, _ = _guarded_project()
    split = _split(DELEGATION_FOLDER)
    try:
        for command in (f"# don't\ncat {split}/DL-1.yml",
                        f"bash <<EOF\n# don't\ncat {split}/DL-1.yml\nEOF",
                        f"echo \"$(echo \"'\")\"; cat {split}/DL-1.yml",
                        f"echo \"`echo \"'\"`\"; cat {split}/DL-1.yml",
                        f"# it's\ncat .compass/work/x/{_split(REQUEST_FOLDER)}/pending/1.yml"):
            r, _ = _run(HOOK_PATH, project, command)
            assert r.returncode == 2, (command, r.returncode, r.stderr)
    finally:
        shutil.rmtree(project, ignore_errors=True)


def _run_with_transcript(hook, project, command, transcript):
    body = {"tool_name": "Bash", "session_id": "sess-prefilter",
            "tool_input": {"command": command}, "cwd": str(project),
            "transcript_path": transcript}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(["bash", str(hook)], input=json.dumps(body),
                          capture_output=True, text=True, env=env)


def test_trc_011_split_forms_reach_every_prefilter_check(tmp_path):
    """The glob check, the check for `evidence` beside a brace and the walk
    over the folders above the transcript each start the guard on a form
    split by a backslash-newline. Scenario `TRC-011` of issue
    `approval-prefilter-bounds`."""
    project, _ = _guarded_project()
    transcript = str(tmp_path / "cfg" / "projects" / "-p" / "s.jsonl")
    top = str(tmp_path)
    cut = len(top) // 2
    flag = "--" + "{delegated,}"
    verb = "compass evi\\\n" + "dence approve DL-1 --a" + "s main " + flag
    try:
        broken = _broken_copy(tmp_path)
        for command in ("cat .comp\\\nass/d*/*", verb,
                        f"grep -r code {top[:cut]}\\\n{top[cut:]}"):
            r = _run_with_transcript(broken, project, command, transcript)
            assert r.returncode == 2 and "[reader-failed]" in r.stderr, (
                command, r.returncode, r.stderr)
            r = _run_with_transcript(HOOK_PATH, project, command, transcript)
            assert r.returncode == 2, (command, r.returncode, r.stderr)
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_trc_012_long_escape_tail_after_a_protected_name_is_refused_fast():
    """A protected name followed by 22,000 ANSI-C escapes made the escape
    search rescan the word for each one. Scenario `TRC-012` of issue
    `approval-prefilter-bounds`."""
    project, _ = _guarded_project()
    try:
        escape = "$" + "'\\'"
        command = f"cat {DELEGATION_FOLDER}/DL-1.yml; echo x" + escape * 22000
        code, err, took = _run_bounded(project, command)
        assert code == 2 and took < 2.0, (code, took, err[:120])
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_trc_013_bracket_words_with_a_class_end_are_decided_fast():
    """Many `[` before one class end made each `[` scan to the end. Scenario
    `TRC-013` of issue `approval-prefilter-bounds`."""
    project, _ = _guarded_project()
    try:
        _decided_fast(project, "cat .compass/" + "[" * 5 + "[:a:]",
                      "cat .compass/" + "[" * 15000 + "[:a:]")
        _decided_fast(project, "cat .compass/" + "[[:a:]" * 5,
                      "cat .compass/" + "[[:a:]" * 15000)
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_trc_014_long_brace_word_is_decided_fast():
    """An open brace followed by 90,000 commas took 19 seconds in the brace
    pattern. Scenario `TRC-014` of issue `approval-prefilter-bounds`."""
    project, _ = _guarded_project()
    try:
        verb = "compass evid" + "ence list {"
        _decided_fast(project, verb + "," * 5, verb + "," * 90000)
    finally:
        shutil.rmtree(project, ignore_errors=True)
