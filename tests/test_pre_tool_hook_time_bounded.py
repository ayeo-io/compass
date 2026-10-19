"""The pre-tool hook refuses a Bash command it cannot scan in time.

A Bash command over 98304 bytes made the hook run for tens of seconds, and a
hook that Claude Code kills for running too long can let the call run. The hook
now counts the command once and refuses an over-limit command where Compass is
in use. Under the limit, the two slow scans give the same answers, faster.

The timing tests carry the `serial` marker: a wall-clock bound fails at random
when workers share the CPU. Each bound is at most half of the 10 second success
signal and at least twice what the scan took when it was measured (`S5`).

Scenario ids: see pre-tool-hook-time-bounded/acceptance-criteria.md.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "pre-tool.sh"

LIMIT = 98304
FAST = 5.0       # seconds: half of the 10 s success signal


def _utf8_locale():
    """The name of a UTF-8 locale on this machine, or None. The hook is slowest
    in such a locale, because bash walks multibyte text one character at a
    time, so the timing tests run in it."""
    out = subprocess.run(["locale", "-a"], capture_output=True, text=True).stdout
    names = out.split()
    for wanted in ("en_US.UTF-8", "en_US.utf8", "C.UTF-8", "C.utf8"):
        if wanted in names:
            return wanted
    return None


UTF8 = _utf8_locale()


def _project(tmp_path):
    """A project that opted in, has an assessed issue and no failing test."""
    root = tmp_path / "proj"
    work = root / ".compass" / "work" / "demo"
    work.mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (root / ".compass" / "current-task").write_text("demo\n")
    (work / "manifest.yml").write_text(
        'schema_version: "2.0"\ntask: demo\ncreated: "2026-08-14"\n'
        'status: active\ndelivery_approach: feature\n'
        'assessment:\n  risk: contained\n  familiarity: brownfield-mapped\n'
        '  size: small\n  goal: delivery\n  role: engineer\n  labels: []\n')
    (work / "delivery-approach.md").write_text("# Delivery approach\n")
    (work / "acceptance-criteria.md").write_text("# Acceptance criteria\n")
    return root


def _guest(tmp_path):
    """A folder that never opted in: no `.compass/` directory."""
    root = tmp_path / "guest"
    root.mkdir()
    return root


def _call(root, tool, tool_input, tmp_path, transcript=None, locale=UTF8,
          timeout=60, path_prefix=None):
    """Run the hook once, in a UTF-8 locale when the machine has one. Returns
    (seconds, completed process). `path_prefix` puts a folder first on PATH."""
    body = {"tool_name": tool, "session_id": "sess-time", "tool_input": tool_input}
    if transcript is not None:
        body["transcript_path"] = str(transcript)
    path = "/usr/bin:/bin:/usr/local/bin"
    if path_prefix is not None:
        path = f"{path_prefix}:{path}"
    env = {"PATH": path,
           "HOME": str(tmp_path / "home"), "CLAUDE_PROJECT_DIR": str(root)}
    if locale:
        env["LC_ALL"] = locale
    started = time.monotonic()
    # Its own process group, so that a hook still running at the time limit is
    # stopped with the `awk` and `python3` processes it started.
    proc = subprocess.Popen(
        ["bash", str(HOOK)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, cwd=str(root), env=env,
        start_new_session=True)
    try:
        out, err = proc.communicate(json.dumps(body), timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise AssertionError(
            f"the hook was still running after {timeout} s") from None
    result = subprocess.CompletedProcess(proc.args, proc.returncode, out, err)
    return time.monotonic() - started, result


def _bash(root, command, tmp_path, **kw):
    return _call(root, "Bash", {"command": command}, tmp_path, **kw)


def _exact(head: str, size: int, tail: str = "E") -> str:
    """`head`, filler lines of 12 bytes, then `tail`: exactly `size` bytes.
    The command ends with a non-newline character, so `$(...)` keeps every
    byte and the size the hook reports is exact."""
    pad = size - len(head.encode()) - len(tail.encode())
    assert pad >= 0
    lines, rest = divmod(pad, 12)
    text = head + "filler line\n" * lines
    if rest:
        text += "x" * (rest - 1) + "\n"
    command = text + tail
    assert len(command.encode()) == size
    return command


def _plain(size: int) -> str:
    """A plain text command: it writes nowhere, so the hook allows it."""
    return _exact("cat <<'E'\n", size)


def _writing(size: int) -> str:
    """A command that writes a heredoc to a file under docs/."""
    return _exact("cat > docs/out.md <<'E'\n", size)


# ---------------------------------------------------------------------------
# Group A - the length limit
# ---------------------------------------------------------------------------

@pytest.mark.serial
def test_a_bash_command_over_the_limit_is_refused_in_seconds(tmp_path):
    """Scenario id: `TRC-001` in pre-tool-hook-time-bounded/acceptance-criteria.md"""
    root = _project(tmp_path)
    seconds, r = _bash(root, _plain(LIMIT + 1), tmp_path)

    assert r.returncode == 2, (r.returncode, r.stderr)
    assert seconds < FAST, f"the refusal took {seconds:.1f} s"
    assert "98305 bytes" in r.stderr and "98304 bytes" in r.stderr, r.stderr
    assert "Write tool" in r.stderr and "git commit -F" in r.stderr, r.stderr
    assert r.stderr.rstrip().endswith("[bash-command-too-long]"), r.stderr
    assert "filler line" not in r.stderr, "the refusal quotes the command"


@pytest.mark.serial
def test_a_bash_command_at_the_limit_is_judged_as_before(tmp_path):
    """Scenario id: `TRC-002` in pre-tool-hook-time-bounded/acceptance-criteria.md"""
    root = _project(tmp_path)
    seconds, r = _bash(root, _plain(LIMIT), tmp_path)

    assert r.returncode == 0, (r.returncode, r.stderr)
    assert r.stderr == "", r.stderr
    assert seconds < FAST, f"the hook took {seconds:.1f} s at the limit"


@pytest.mark.skipif(UTF8 is None,
                    reason="this machine has no en_US.UTF-8 or C.UTF-8 locale, "
                           "so bash cannot count characters apart from bytes")
def test_the_limit_counts_bytes_not_characters(tmp_path):
    """Scenario id: `TRC-004` in pre-tool-hook-time-bounded/acceptance-criteria.md"""
    root = _project(tmp_path)
    command = "€" * 40000          # three bytes each: 120000 bytes
    assert len(command.encode()) == 120000
    _, r = _bash(root, command, tmp_path)

    assert r.returncode == 2, (r.returncode, r.stderr)
    assert "120000 bytes" in r.stderr, r.stderr
    assert "[bash-command-too-long]" in r.stderr, r.stderr


@pytest.mark.parametrize("tool, tool_input", [
    pytest.param("Write", {"file_path": "docs/big.md", "content": "x" * 200000},
                 id="write"),
    pytest.param("Edit", {"file_path": "docs/big.md", "old_string": "a",
                          "new_string": "x" * 200000}, id="edit"),
])
def test_a_large_write_or_edit_is_not_refused_for_its_length(
        tmp_path, tool, tool_input):
    """Scenario id: `TRC-006` in pre-tool-hook-time-bounded/acceptance-criteria.md"""
    root = _project(tmp_path)
    (root / "docs").mkdir()
    _, r = _call(root, tool, tool_input, tmp_path)

    assert r.returncode == 0, (r.returncode, r.stderr)
    assert "bash-command-too-long" not in r.stderr, r.stderr


@pytest.mark.serial
def test_a_repository_that_has_not_opted_in_is_not_refused_for_length(tmp_path):
    """Scenario id: `TRC-007` in pre-tool-hook-time-bounded/acceptance-criteria.md"""
    root = _guest(tmp_path)
    seconds, r = _bash(root, _writing(240000), tmp_path)

    assert r.returncode == 0, (r.returncode, r.stderr)
    assert r.stderr == "", r.stderr
    assert seconds < FAST, f"the hook took {seconds:.1f} s outside Compass"


@pytest.mark.serial
@pytest.mark.parametrize("names, code", [
    pytest.param("TRANSCRIPT", "transcript-protected", id="transcript"),
    pytest.param(".compass/delegations/DL-1.yml", "delegation-protected",
                 id="delegation-file"),
])
def test_an_over_limit_command_naming_approval_state_is_still_refused_where_compass_is_not_in_use(
        tmp_path, names, code):
    """Scenario id: `TRC-015` in pre-tool-hook-time-bounded/acceptance-criteria.md"""
    root = _guest(tmp_path)
    folder = tmp_path / "home" / ".claude" / "projects" / "-guest"
    folder.mkdir(parents=True)
    transcript = folder / "s.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")
    named = str(transcript) if names == "TRANSCRIPT" else names
    command = _exact("cat <<'E'\n", 240000 - len(f"\ncat {named}"),
                     tail="E") + f"\ncat {named}"
    assert len(command) == 240000

    seconds, r = _bash(root, command, tmp_path, transcript=transcript)

    assert r.returncode == 2, (r.returncode, r.stderr)
    assert f"[{code}]" in r.stderr, r.stderr
    assert "bash-command-too-long" not in r.stderr, r.stderr
    assert seconds < FAST * 2, f"the guard took {seconds:.1f} s"


# ---------------------------------------------------------------------------
# Group B - speed under the limit
# ---------------------------------------------------------------------------

@pytest.mark.serial
def test_a_long_allowed_command_under_the_limit_finishes_in_time(tmp_path):
    """Scenario id: `TRC-008` in pre-tool-hook-time-bounded/acceptance-criteria.md"""
    root = _project(tmp_path)
    seconds, r = _bash(root, _writing(90000), tmp_path)

    assert r.returncode == 0, (r.returncode, r.stderr)
    assert seconds < FAST, f"the hook took {seconds:.1f} s"


@pytest.mark.serial
def test_a_long_allowed_command_that_starts_with_a_variable_finishes_in_time(
        tmp_path):
    """Scenario id: `TRC-009` in pre-tool-hook-time-bounded/acceptance-criteria.md"""
    root = _project(tmp_path)
    head = f"S={root}/docs/gen\ncat > $S/out.md <<'E'\n"
    seconds, r = _bash(root, _exact(head, 90000), tmp_path)

    assert r.returncode == 0, (r.returncode, r.stderr)
    assert seconds < FAST, f"the hook took {seconds:.1f} s"


@pytest.mark.serial
def test_a_command_of_many_leading_statements_before_a_variable_finishes_in_time(
        tmp_path):
    """The statement walk of the variable expansion is linear in the command
    (supports `TRC-009` in pre-tool-hook-time-bounded/acceptance-criteria.md).
    14000 leading `cd` lines took 22 s when each line was matched against the
    whole rest of the command."""
    root = _project(tmp_path)
    command = ("cd /x\n" * 14000 + f"S={root}/docs/gen\n"
               "cat > $S/out.md <<'E'\nhi\nE")
    assert len(command) < LIMIT
    seconds, r = _bash(root, command, tmp_path)

    assert r.returncode == 0, (r.returncode, r.stderr)
    assert seconds < FAST, f"the hook took {seconds:.1f} s"


@pytest.mark.serial
def test_a_reassigned_variable_before_a_heredoc_over_a_pipe_buffer_is_still_not_expanded(
        tmp_path):
    """Scenario id: `TRC-010` in pre-tool-hook-time-bounded/acceptance-criteria.md

    A check written as `printf | grep -q` stops at its first match, printf dies
    of SIGPIPE on a body longer than the 65536-byte pipe buffer, and under
    pipefail that reads as "no match" - which would expand the variable and
    allow a write into the project."""
    root = _project(tmp_path)
    scratch = tmp_path / "scratch"
    head = f"S={scratch}; read S; echo x > $S/app.py; cat <<'E'\n"
    command = head + "filler line\n" * 7500 + "E"
    assert 65536 < len(command) <= LIMIT
    seconds, r = _bash(root, command, tmp_path)

    assert r.returncode == 2, (r.returncode, r.stderr)
    assert "bash-command-too-long" not in r.stderr, r.stderr
    assert seconds < FAST, f"the hook took {seconds:.1f} s"


@pytest.mark.serial
@pytest.mark.xfail(strict=True, reason=(
    "TRC-012 waits for the architect's decision on the second limit (DD-7). "
    "After the faster scans this command takes more than 100 s: each `cp` line "
    "is a write candidate that costs about 50 ms, and the flattening of "
    "unclosed substitutions grows faster than their number. "
    "See result.md of subtask-1."))
def test_many_unclosed_substitutions_under_the_limit_end_in_time(tmp_path):
    """Scenario id: `TRC-012` in pre-tool-hook-time-bounded/acceptance-criteria.md"""
    root = _project(tmp_path)
    command = "cp x $(\n" * 4000          # 8 bytes a line: 32000 bytes
    assert len(command) == 32000
    seconds, r = _bash(root, command, tmp_path, timeout=10)

    assert r.returncode in (0, 2), (r.returncode, r.stderr)
    assert seconds < FAST, f"the hook took {seconds:.1f} s"


# ---------------------------------------------------------------------------
# Group D - many write candidates. The configuration reader is a Python start
# of about 50 ms. It ran once for every candidate; it now runs once per call.
# ---------------------------------------------------------------------------

def _project_with_globs(tmp_path, globs_yaml: str):
    """A project whose settings file declares `enforcement.code_globs`."""
    root = _project(tmp_path)
    (root / ".compass" / "config.yml").write_text(
        f"version: 1.0.0\nenforcement:\n  code_globs: {globs_yaml}\n")
    return root


def _counting_python(tmp_path, fail=False):
    """A folder with a `python3` that counts the starts of the code_globs reader
    (one line in `counter` for each) and then runs the real one. With `fail`,
    that reader exits 9 and does not run."""
    folder = tmp_path / "counting-bin"
    folder.mkdir(parents=True)
    counter = tmp_path / "counter"
    counter.write_text("")
    real = shutil.which("python3", path="/usr/bin:/bin:/usr/local/bin")
    wrapper = folder / "python3"
    wrapper.write_text(
        "#!/bin/bash\n"
        'if [ "$1" != "-" ]; then exec ' + real + ' "$@"; fi\n'
        'f="$(mktemp)"; cat > "$f"\n'
        'if grep -q code_globs "$f"; then\n'
        f'  echo x >> {counter}\n'
        + ("  echo 'reader broke' >&2; exit 9\n" if fail else "") +
        "fi\n"
        'exec ' + real + ' "$@" < "$f"\n')
    wrapper.chmod(0o755)
    return folder, counter


def _starts(counter) -> int:
    return len(counter.read_text().split())


@pytest.mark.serial
def test_many_distinct_write_targets_read_the_configuration_once(tmp_path):
    """Scenario id: `TRC-016` in pre-tool-hook-time-bounded/acceptance-criteria.md"""
    root = _project_with_globs(tmp_path, '["*.zzz"]')
    folder, counter = _counting_python(tmp_path)
    command = "\n".join(f"cp a b{i}" for i in range(200))
    seconds, r = _bash(root, command, tmp_path, path_prefix=folder)

    assert r.returncode == 0, (r.returncode, r.stderr)
    assert _starts(counter) == 1, f"the reader started {_starts(counter)} times"
    assert seconds < 3.0, f"the hook took {seconds:.1f} s"


@pytest.mark.serial
@pytest.mark.parametrize("line, code", [
    pytest.param("cp a b", 0, id="allowed"),
    pytest.param("cp a src/app.py", 2, id="refused"),
])
def test_identical_write_targets_end_in_time_with_one_verdict(
        tmp_path, line, code):
    """Scenario id: `TRC-017` in pre-tool-hook-time-bounded/acceptance-criteria.md"""
    root = _project_with_globs(tmp_path, '["*.zzz"]')
    _, one = _bash(root, line, tmp_path)
    seconds, many = _bash(root, "\n".join([line] * 200), tmp_path)

    assert one.returncode == code, (one.returncode, one.stderr)
    assert many.returncode == one.returncode, (many.returncode, many.stderr)
    assert many.stderr == one.stderr, many.stderr
    assert seconds < 1.0, f"the hook took {seconds:.1f} s"


@pytest.mark.serial
@pytest.mark.parametrize("globs, last", [
    pytest.param('["*.zzz"]', "x.zzz", id="plain-glob"),
    pytest.param('["[x]*.qqq"]', "xfile.qqq", id="bracket-glob"),
])
def test_a_broken_configuration_reader_still_refuses_with_the_cache(
        tmp_path, globs, last):
    """Scenario id: `TRC-022` in pre-tool-hook-time-bounded/acceptance-criteria.md

    A glob that matches a later candidate is still enforced after the first
    read, and a reader that cannot run still refuses."""
    many = "\n".join(f"cp a b{i}" for i in range(30))
    root = _project_with_globs(tmp_path, globs)
    _, r = _bash(root, f"{many}\ncp a {last}", tmp_path)
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert last in r.stderr, r.stderr

    broken = _project_with_globs(tmp_path / "broken", '"not a list"')
    _, r = _bash(broken, f"{many}\ncp a b", tmp_path)
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert "[config-invalid]" in r.stderr, r.stderr

    folder, counter = _counting_python(tmp_path / "failing", fail=True)
    root = _project_with_globs(tmp_path / "failing", '["*.zzz"]')
    _, r = _bash(root, f"{many}\ncp a b", tmp_path, path_prefix=folder)
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert "[reader-failed]" in r.stderr, r.stderr
    assert _starts(counter) == 1, "the failed reader started again"


# ---------------------------------------------------------------------------
# The faster scans give the same answers. Two differential tests, one for the
# transcript-guard prefilter and one golden corpus for expand_command_variable.
# They serve TRC-011 and TRC-010 and need no scenario of their own.
# ---------------------------------------------------------------------------

def _bash_run(script: str, *args: str, locale=UTF8):
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin"}
    if locale:
        env["LC_ALL"] = locale
    return subprocess.run(["bash", "-c", script, "x", *args], capture_output=True,
                          text=True, env=env, timeout=120)


def _hook_block(begin: str, end: str) -> str:
    text = HOOK.read_text(encoding="utf-8")
    found = re.search(rf"^[ \t]*# {begin}.*?\n(.*?)^[ \t]*# {end}\n", text,
                      re.S | re.M)
    assert found, f"hooks/pre-tool.sh has no `{begin}` ... `{end}` block"
    return found.group(1)


# The expression the hook used before: written out here so that the new one is
# compared with it, not with itself.
OLD_BARE = r'''_bare="${_text//[\'\"\\]/}"'''

PREFILTER_CORPUS = [
    "", "plain text", "ls -la", "cat <<'E'\nbody\nE", 'echo "quoted"', "it's",
    "back\\slash", "--d''elegated", "-\\-delegated", "$'--delegated'",
    "--del\"\"egated", "cat .compass/delegations/DL-1.yml", "cat ~/.cl''aude/x",
    "caf\u00e9 '\u20ac' \"\u00fc\"", "\u20ac" * 300, "a'" * 300, 'a"' * 300,
    "a\\" * 300, "x" * 5000, "x" * 5000 + "'", "'" + "x" * 5000,
    ("it's a \"q\" \\w " * 40), ("approval-requests/" + "'" * 3) * 5,
    "line one\nline two '\nline three \\\n", "tab\t'\t\"\t\\",
    "trailing newline'\n", "a" * 255 + "'", "a" * 256 + "'", "a" * 257 + "'",
    "'" * 255, "'" * 256, "'" * 257, ("--del" + "'" * 2 + "egated ") * 60,
    "/.claude/projects/-p/s.jsonl " + "'" * 400,
]


def test_the_faster_prefilter_gives_the_same_bare_text_as_the_old_expression():
    """`_bare`, and so the set of commands sent to the approval guard, is the
    same as before for every text in a corpus of quotes, backslashes, ANSI-C
    quotes, multibyte text, newlines and lengths around the 256-character
    switch (supports `TRC-011` and `TRC-010` in
    pre-tool-hook-time-bounded/acceptance-criteria.md)."""
    new = _hook_block("prefilter-bare-begin", "prefilter-bare-end")
    patterns = ("*approval-requests*|*prompt-approval.sh*|*.compass/delegations*|"
                "*--del*|*.claude*|*CLAUDE_CONFIG_DIR*")
    for text in PREFILTER_CORPUS:
        outputs = []
        for expr in (OLD_BARE, new):
            script = (f'_text="$1"\n{expr}\n'
                      f'printf "%s" "$_bare"; printf "\\0"\n'
                      f'case "$_text $_bare" in {patterns}) printf 1;; *) printf 0;; esac')
            r = _bash_run(script, text)
            assert r.returncode == 0, (text[:60], r.stderr)
            outputs.append(r.stdout)
        # `$(...)` drops trailing newlines from the bare text; no pattern can
        # tell, and the match decision (the last character) is compared too.
        old_bare, old_hit = outputs[0].rsplit("\0", 1)
        new_bare, new_hit = outputs[1].rsplit("\0", 1)
        assert new_bare.rstrip("\n") == old_bare.rstrip("\n"), text[:60]
        assert new_hit == old_hit, (text[:60], old_hit, new_hit)


def test_the_prefilter_block_removes_the_three_characters_in_both_branches():
    """A fault that drops the backslash from either branch must show: each
    branch is run on a short and a long text that holds all three."""
    new = _hook_block("prefilter-bare-begin", "prefilter-bare-end")
    for text in ("a'b\"c\\d", ("a'b\"c\\d" * 100)):
        r = _bash_run(f'_text="$1"\n{new}\nprintf "%s" "$_bare"', text)
        assert r.returncode == 0, r.stderr
        assert r.stdout == text.replace("'", "").replace('"', "").replace("\\", "")


SC = "/tmp/golden_sc"
GOLDEN_GENERATORS = {
    "cds-200-then-assign":
        lambda: "cd /x\n" * 200 + f"S={SC}\ncat > $S/out.md <<'E'\nhi\nE",
    "cds-and-200": lambda: "cd /x && " * 200 + f"S={SC} && echo x > $S/p.py",
    "plain-100-then-assign": lambda: "ls /tmp\n" * 100 + f"S={SC}\necho x > $S/p.py",
    "quotes-heavy": lambda: (f"S='{SC}'\n"
                             + "echo \"it's\" 'a \"b\"' >> /dev/null\n" * 150
                             + "echo x > $S/p.py"),
    "reassigned-late": lambda: f"S={SC}\n" + "echo hi\n" * 300 + "S=src\necho x > $S/p.py",
    "mention-in-body": lambda: (f"S={SC}; cat <<'E'\n" + "line with S inside\n" * 400
                                + "E\necho x > $S/p.py"),
    "binder-in-body": lambda: (f"S={SC}; cat <<'E'\n" + "filler\n" * 400
                               + "eval x\nE\necho x > $S/p.py"),
    "refs-only-body": lambda: (f"S={SC}; cat <<'E'\n" + "see $S and ${S}\n" * 400
                               + "E\necho x > $S/p.py"),
    "multibyte": lambda: f"S={SC}\n" + "echo \u20ac\u20ac \u00e9\n" * 100 + "echo x > $S/p.py",
    "long-heredoc-4000": lambda: (f"S={SC}; read S; echo x > $S/p.py; cat <<'E'\n"
                                  + "filler line\n" * 4000 + "E"),
    "long-ok-4000": lambda: (f"S={SC}; echo x > $S/p.py; cat <<'E'\n"
                             + "filler line\n" * 4000 + "E"),
    # Statements around the 4096-character window the faster walk reads.
    "boundary-4090": lambda: "a" * 4090 + f"; S={SC}\necho x > $S/p.py",
    "boundary-4094": lambda: "a" * 4094 + f"; S={SC}\necho x > $S/p.py",
    "boundary-4095": lambda: "a" * 4095 + f"; S={SC}\necho x > $S/p.py",
    "boundary-4096": lambda: "a" * 4096 + f"; S={SC}\necho x > $S/p.py",
    "boundary-4100": lambda: "a" * 4100 + f"; S={SC}\necho x > $S/p.py",
    "boundary-chain-0": lambda: "cd /x && " * 455 + f"S={SC} && echo x > $S/p.py",
    "boundary-chain-3": lambda: "zzz;" + "cd /x && " * 455 + f"S={SC} && echo x > $S/p.py",
    "boundary-chain-8": lambda: "zzzzzzzz;" + "cd /x && " * 455 + f"S={SC} && echo x > $S/p.py",
    "boundary-510": lambda: "a" * 510 + f"; S={SC}\necho x > $S/p.py",
    "boundary-511": lambda: "a" * 511 + f"; S={SC}\necho x > $S/p.py",
    "boundary-512": lambda: "a" * 512 + f"; S={SC}\necho x > $S/p.py",
    "boundary-513": lambda: "a" * 513 + f"; S={SC}\necho x > $S/p.py",
    "boundary-1023": lambda: "a" * 1023 + f"; S={SC}\necho x > $S/p.py",
    "boundary-1025": lambda: "a" * 1025 + f"; S={SC}\necho x > $S/p.py",
    "boundary-two-words": lambda: "a " * 255 + f"b; S={SC}\necho x > $S/p.py",
    "boundary-assign-quoted": lambda: (f"T='{'q' * 500}'\n" + f"S={SC}\n"
                                       + "echo x > $S/p.py"),
    "long-plain-statement": lambda: "a" * 9000 + f"; S={SC}; echo x > $S/p.py",
    **{f"chain512-{p}": (lambda p=p: "z" * p + ";" + "cd /x && " * 56
                         + f"S={SC} && echo x > $S/p.py") for p in range(9)},
    "long-quoted-value": lambda: f"S='{SC}" + "/x" * 3000 + "'\necho x > $S/p.py",
    "long-leading-blanks": lambda: " " * 5000 + f"S={SC}\necho x > $S/p.py",
    "quoted-value-over-newline": lambda: f"S='{SC}\n/x'\necho x > $S/p.py",
    "assign-then-long-statements": lambda: (f"S={SC}\n" + ("b" * 5000 + "\n") * 3
                                            + "echo x > $S/p.py"),
}

# GOLDEN-DATA-BEGIN
GOLDEN_COMMANDS = {
    't000': 'echo x > /tmp/golden_proj/../elsewhere/app.py',
    't001': 'echo x > /tmp/golden_proj/src/../tests/test_app.py',
    't002': 'echo x > /tmp/golden_proj/src/../docs/notes.md',
    't003': 'cp "$(echo \'(\')" /tmp/golden_sc/out.py',
    't004': 'mv "$(grep -l \'x(\' a)" /tmp/golden_sc/out.py',
    't005': 'echo x > $X/../.compass/../src/app.py',
    't006': 'echo x > $X/../tests/../src/app.py',
    't007': 'echo x > ${X}/../.compass/../src/app.py',
    't008': 'echo x > ~/../tests/../src/app.py',
    't009': 'cp a.py $X/../.compass/../src/app.py',
    't010': 'echo x > /tmp/golden_proj/$X/../spec/../src/app.py',
    't011': 'echo x > $X/../src/test_app.py',
    't012': 'echo x > $X/../src/app_test.py',
    't013': 'echo x > $X/../notes.md',
    't014': 'echo x > $X/../tests/conftest.py',
    't015': 'S=/tmp/golden_sc; mkdir -p $S && echo x > $S/plant.py',
    't016': "S=/tmp/golden_sc && cat > $S/plant.py <<'EOF'\nprint(1)\nEOF",
    't017': 'S=/tmp/golden_sc; echo x > ${S}/plant.py',
    't018': 'S="/tmp/golden_sc"; echo x > $S/plant.py',
    't019': "S='/tmp/golden_sc'; echo x > $S/plant.py",
    't020': 'export S=/tmp/golden_sc; echo x > $S/plant.py',
    't021': 'S=/tmp/golden_sc\necho x > $S/plant.py',
    't022': 'F=/tmp/golden_sc/plant.py; echo x > $F',
    't023': 'S=/tmp/golden_sc; T=/tmp/golden_sc/t; echo x > $T/plant.py',
    't024': 'S=/tmp/golden_sc; echo x | tee $S/plant.py',
    't025': 'S=/tmp/golden_sc; cp /etc/hosts $S/plant.py',
    't026': 'cd /tmp/golden_proj; S=/tmp/golden_sc; echo x > $S/plant.py',
    't027': 'cd /tmp/golden_proj && S=/tmp/golden_sc && mkdir -p $S && echo x > $S/plant.py',
    't028': 'export A=1 B=2; set -e; S=/tmp/golden_sc; echo x > $S/plant.py',
    't029': 'S=/tmp/golden_sc; python3 -c "print((1))" > $S/plant.py',
    't030': 'S=/tmp/golden_proj/src; echo x > $S/app.py',
    't031': 'S=/tmp/golden_proj; echo x > $S/src/app.py',
    't032': 'S=/tmp/golden_sc; S=/tmp/golden_proj/src; echo x > $S/app.py',
    't033': 'S=/tmp/golden_sc; echo x > src/app.py',
    't034': 'S=/tmp/golden_sc; cp $S/a.py src/app.py',
    't035': 'S=/tmp/golden_sc; echo x | tee $S/log.txt src/app.py',
    't036': 'S=/tmp/golden_sc; echo x > $S/plant.py; echo y > src/app.py',
    't037': 'S=/tmp/golden_sc; cp $S/a.py src/app.py; ls $S',
    't038': 'S=$(pwd)/src; echo x > $S/app.py',
    't039': 'S=`pwd`/src; echo x > $S/app.py',
    't040': 'S=/$(echo /tmp/golden_proj)/src; echo x > $S/app.py',
    't041': 'echo x > $S/app.py',
    't042': 'T=/tmp/golden_sc; S=$T; echo x > $S/app.py',
    't043': 'S=${HOME}/src; echo x > $S/app.py',
    't044': 'S=~/src; echo x > $S/app.py',
    't045': 'S=src; echo x > $S/app.py',
    't046': 'S=/tmp/golden_sc; echo x > $S/$T/app.py',
    't047': 'S=/tmp/golden_sc; S=src; echo x > $S/app.py',
    't048': 'S=/tmp/golden_sc && S=/tmp/golden_proj/src && echo x > $S/app.py',
    't049': 'S=/tmp/golden_sc; cd /tmp/golden_proj; S=src; echo x > $S/app.py',
    't050': 'S=/tmp/golden_sc; S+=/../proj/src; echo x > $S/app.py',
    't051': 'S=/tmp/golden_sc; read S < /dev/null; echo x > $S/app.py',
    't052': 'S=/tmp/golden_sc; for S in src; do echo x > $S/app.py; done',
    't053': 'S=/tmp/golden_sc; export S=src; echo x > $S/app.py',
    't054': 'S=/tmp/golden_sc; unset S; echo x > $S/app.py',
    't055': 'S=/tmp/golden_sc true; echo x > $S/app.py',
    't056': 'false && S=/tmp/golden_sc; echo x > $S/app.py',
    't057': '(S=/tmp/golden_sc); echo x > $S/app.py',
    't058': 'echo x > $S/app.py; S=/tmp/golden_sc',
    't059': 'S=/tmp/golden_sc; eval "$X"; echo x > $S/app.py',
    't060': 'S=/tmp/golden_sc; source ./env.sh; echo x > $S/app.py',
    't061': 'S=/tmp/golden_sc; . ./env.sh; echo x > $S/app.py',
    't062': 'S=/tmp/golden_sc; V=S; printf -v "$V" src; echo x > $S/app.py',
    't063': 'S=/tmp/golden_sc; V=S; declare "$V=src"; echo x > $S/app.py',
    't064': 'S=/tmp/golden_sc; trap "$X" DEBUG; echo x > $S/app.py',
    't065': 'S=/tmp/golden_sc; V=S; (( $V = 1 )); echo x > $S/app.py',
    't066': 'cd /tmp/golden_proj && S=/tmp/golden_sc; echo x > $S/app.py',
    't067': 'cd /tmp/golden_proj && S=/tmp/golden_sc && true; echo x > $S/app.py',
    't068': 'cd /tmp/golden_proj && S=/tmp/golden_sc || echo x > $S/app.py',
    't069': 'readonly S; S=/tmp/golden_sc; echo x > $S/app.py',
    't070': 'source ./env.sh; S=/tmp/golden_sc; echo x > $S/app.py',
    't071': 'trap x DEBUG; S=/tmp/golden_sc; echo x > $S/app.py',
    't072': 'if true; then S=/tmp/golden_sc; fi; echo x > $S/app.py',
    't073': 'while false; do S=/tmp/golden_sc; done; echo x > $S/app.py',
    't074': 'S=/tmp/golden_sc; mkdir -p $S; read S; echo x > $S/app.py',
    't075': 'S=/tmp/golden_sc/../proj/src; echo x > $S/app.py',
    't076': 'S=/tmp/golden_sc; echo x > $S/../proj/src/app.py',
    't077': 'echo x > /tmp/golden_sc/../proj/src/app.py',
    't078': 'echo x > /tmp/../tmp/golden_proj/src/app.py',
    't079': 'echo x > //tmp/golden_proj/src/app.py',
    't080': 'echo x > /tmp/golden_proj/./src/app.py',
    't081': 'echo x > /tmp/golden_proj/src//app.py',
    't082': 'echo x > /TMP/GOLDEN_PROJ/src/app.py',
    't083': 'S=//tmp/golden_proj; echo x > $S/src/app.py',
    't084': 'S=/tmp/x; echo x > $S/../../tmp/golden_proj/src/app.py',
    't085': 'echo x > $X/../src/app.py',
    't086': 'echo x > /tmp/golden_proj/$X/../../x/src/app.py',
    't087': 'echo x > ~/../../tmp/golden_proj/src/app.py',
}

# (command id or generator name, target, result; None = the target unchanged)
GOLDEN_ROWS = [
    ('t000', '/plain/path', None),
    ('t001', '/plain/path', None),
    ('t002', '/plain/path', None),
    ('t003', '/plain/path', None),
    ('t004', '/plain/path', None),
    ('t005', '$X/../.compass/../src/app.py', None),
    ('t005', '/plain/path', None),
    ('t006', '$X/../tests/../src/app.py', None),
    ('t006', '/plain/path', None),
    ('t007', '${X}/../.compass/../src/app.py', None),
    ('t007', '/plain/path', None),
    ('t008', '/plain/path', None),
    ('t009', '$X/../.compass/../src/app.py', None),
    ('t009', '/plain/path', None),
    ('t010', '$X/../spec/../src/app.py', None),
    ('t010', '/plain/path', None),
    ('t011', '$X/../src/test_app.py', None),
    ('t011', '/plain/path', None),
    ('t012', '$X/../src/app_test.py', None),
    ('t012', '/plain/path', None),
    ('t013', '$X/../notes.md', None),
    ('t013', '/plain/path', None),
    ('t014', '$X/../tests/conftest.py', None),
    ('t014', '/plain/path', None),
    ('t015', '$S', '/tmp/golden_sc'),
    ('t015', '$S/plant.py', '/tmp/golden_sc/plant.py'),
    ('t015', '/plain/path', None),
    ('t016', '$S/plant.py', '/tmp/golden_sc/plant.py'),
    ('t016', '/plain/path', None),
    ('t017', '${S}/plant.py', '/tmp/golden_sc/plant.py'),
    ('t017', '/plain/path', None),
    ('t018', '$S/plant.py', '/tmp/golden_sc/plant.py'),
    ('t018', '/plain/path', None),
    ('t019', '$S/plant.py', '/tmp/golden_sc/plant.py'),
    ('t019', '/plain/path', None),
    ('t020', '$S/plant.py', '/tmp/golden_sc/plant.py'),
    ('t020', '/plain/path', None),
    ('t021', '$S/plant.py', '/tmp/golden_sc/plant.py'),
    ('t021', '/plain/path', None),
    ('t022', '$F', '/tmp/golden_sc/plant.py'),
    ('t022', '/plain/path', None),
    ('t023', '$T/plant.py', '/tmp/golden_sc/t/plant.py'),
    ('t023', '/plain/path', None),
    ('t024', '$S/plant.py', '/tmp/golden_sc/plant.py'),
    ('t024', '/plain/path', None),
    ('t025', '$S/plant.py', '/tmp/golden_sc/plant.py'),
    ('t025', '/plain/path', None),
    ('t026', '$S/plant.py', '/tmp/golden_sc/plant.py'),
    ('t026', '/plain/path', None),
    ('t027', '$S', '/tmp/golden_sc'),
    ('t027', '$S/plant.py', '/tmp/golden_sc/plant.py'),
    ('t027', '/plain/path', None),
    ('t028', '$S/plant.py', '/tmp/golden_sc/plant.py'),
    ('t028', '/plain/path', None),
    ('t029', '$S/plant.py', '/tmp/golden_sc/plant.py'),
    ('t029', '/plain/path', None),
    ('t030', '$S/app.py', '/tmp/golden_proj/src/app.py'),
    ('t030', '/plain/path', None),
    ('t031', '$S/src/app.py', '/tmp/golden_proj/src/app.py'),
    ('t031', '/plain/path', None),
    ('t032', '$S/app.py', None),
    ('t032', '/plain/path', None),
    ('t033', '/plain/path', None),
    ('t034', '$S/a.py', '/tmp/golden_sc/a.py'),
    ('t034', '/plain/path', None),
    ('t035', '$S/log.txt', '/tmp/golden_sc/log.txt'),
    ('t035', '/plain/path', None),
    ('t036', '$S/plant.py', '/tmp/golden_sc/plant.py'),
    ('t036', '/plain/path', None),
    ('t037', '$S/a.py', '/tmp/golden_sc/a.py'),
    ('t037', '$S', '/tmp/golden_sc'),
    ('t037', '/plain/path', None),
    ('t038', '$S/app.py', None),
    ('t038', '/plain/path', None),
    ('t039', '$S/app.py', None),
    ('t039', '/plain/path', None),
    ('t040', '$S/app.py', None),
    ('t040', '/plain/path', None),
    ('t041', '$S/app.py', None),
    ('t041', '/plain/path', None),
    ('t041', '$S/app.py', None),
    ('t041', '/plain/path', None),
    ('t042', '$T', '/tmp/golden_sc'),
    ('t042', '$S/app.py', None),
    ('t042', '/plain/path', None),
    ('t043', '${HOME}/src', None),
    ('t043', '$S/app.py', None),
    ('t043', '/plain/path', None),
    ('t044', '$S/app.py', None),
    ('t044', '/plain/path', None),
    ('t045', '$S/app.py', None),
    ('t045', '/plain/path', None),
    ('t046', '$S/$T/app.py', None),
    ('t046', '/plain/path', None),
    ('t047', '$S/app.py', None),
    ('t047', '/plain/path', None),
    ('t048', '$S/app.py', None),
    ('t048', '/plain/path', None),
    ('t049', '$S/app.py', None),
    ('t049', '/plain/path', None),
    ('t050', '$S/app.py', None),
    ('t050', '/plain/path', None),
    ('t051', '$S/app.py', None),
    ('t051', '/plain/path', None),
    ('t052', '$S/app.py', None),
    ('t052', '/plain/path', None),
    ('t053', '$S/app.py', None),
    ('t053', '/plain/path', None),
    ('t054', '$S/app.py', None),
    ('t054', '/plain/path', None),
    ('t055', '$S/app.py', None),
    ('t055', '/plain/path', None),
    ('t056', '$S/app.py', None),
    ('t056', '/plain/path', None),
    ('t057', '$S/app.py', None),
    ('t057', '/plain/path', None),
    ('t058', '$S/app.py', None),
    ('t058', '/plain/path', None),
    ('t059', '$X', None),
    ('t059', '$S/app.py', None),
    ('t059', '/plain/path', None),
    ('t060', '$S/app.py', None),
    ('t060', '/plain/path', None),
    ('t061', '$S/app.py', None),
    ('t061', '/plain/path', None),
    ('t062', '$V', None),
    ('t062', '$S/app.py', None),
    ('t062', '/plain/path', None),
    ('t063', '$V', None),
    ('t063', '$S/app.py', None),
    ('t063', '/plain/path', None),
    ('t064', '$X', None),
    ('t064', '$S/app.py', None),
    ('t064', '/plain/path', None),
    ('t065', '$V', None),
    ('t065', '$S/app.py', None),
    ('t065', '/plain/path', None),
    ('t066', '$S/app.py', None),
    ('t066', '/plain/path', None),
    ('t067', '$S/app.py', None),
    ('t067', '/plain/path', None),
    ('t068', '$S/app.py', None),
    ('t068', '/plain/path', None),
    ('t069', '$S/app.py', None),
    ('t069', '/plain/path', None),
    ('t070', '$S/app.py', None),
    ('t070', '/plain/path', None),
    ('t071', '$S/app.py', None),
    ('t071', '/plain/path', None),
    ('t072', '$S/app.py', None),
    ('t072', '/plain/path', None),
    ('t073', '$S/app.py', None),
    ('t073', '/plain/path', None),
    ('t074', '$S', None),
    ('t074', '$S/app.py', None),
    ('t074', '/plain/path', None),
    ('t075', '$S/app.py', None),
    ('t075', '/plain/path', None),
    ('t076', '$S/../proj/src/app.py', None),
    ('t076', '/plain/path', None),
    ('t077', '/plain/path', None),
    ('t078', '/plain/path', None),
    ('t079', '/plain/path', None),
    ('t080', '/plain/path', None),
    ('t081', '/plain/path', None),
    ('t082', '/plain/path', None),
    ('t083', '$S/src/app.py', '//tmp/golden_proj/src/app.py'),
    ('t083', '/plain/path', None),
    ('t084', '$S/../../tmp/golden_proj/src/app.py', None),
    ('t084', '/plain/path', None),
    ('t085', '$X/../src/app.py', None),
    ('t085', '/plain/path', None),
    ('t086', '$X/../../x/src/app.py', None),
    ('t086', '/plain/path', None),
    ('t087', '/plain/path', None),
    ('cds-200-then-assign', '$S/out.md', '/tmp/golden_sc/out.md'),
    ('cds-200-then-assign', '/plain/path', None),
    ('cds-and-200', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('cds-and-200', '/plain/path', None),
    ('plain-100-then-assign', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('plain-100-then-assign', '/plain/path', None),
    ('quotes-heavy', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('quotes-heavy', '/plain/path', None),
    ('reassigned-late', '$S/p.py', None),
    ('reassigned-late', '/plain/path', None),
    ('mention-in-body', '$S/p.py', None),
    ('mention-in-body', '/plain/path', None),
    ('binder-in-body', '$S/p.py', None),
    ('binder-in-body', '/plain/path', None),
    ('refs-only-body', '$S', '/tmp/golden_sc'),
    ('refs-only-body', '${S}', '/tmp/golden_sc'),
    ('refs-only-body', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('refs-only-body', '/plain/path', None),
    ('multibyte', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('multibyte', '/plain/path', None),
    ('long-heredoc-4000', '$S/p.py', None),
    ('long-heredoc-4000', '/plain/path', None),
    ('long-ok-4000', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('long-ok-4000', '/plain/path', None),
    ('boundary-4090', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-4090', '/plain/path', None),
    ('boundary-4094', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-4094', '/plain/path', None),
    ('boundary-4095', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-4095', '/plain/path', None),
    ('boundary-4096', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-4096', '/plain/path', None),
    ('boundary-4100', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-4100', '/plain/path', None),
    ('boundary-chain-0', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-chain-0', '/plain/path', None),
    ('boundary-chain-3', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-chain-3', '/plain/path', None),
    ('boundary-chain-8', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-chain-8', '/plain/path', None),
    ('boundary-510', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-510', '/plain/path', None),
    ('boundary-511', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-511', '/plain/path', None),
    ('boundary-512', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-512', '/plain/path', None),
    ('boundary-513', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-513', '/plain/path', None),
    ('boundary-1023', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-1023', '/plain/path', None),
    ('boundary-1025', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-1025', '/plain/path', None),
    ('boundary-two-words', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-two-words', '/plain/path', None),
    ('boundary-assign-quoted', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('boundary-assign-quoted', '/plain/path', None),
    ('long-plain-statement', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('long-plain-statement', '/plain/path', None),
    ('chain512-0', '$S/p.py', None),
    ('chain512-0', '/plain/path', None),
    ('chain512-1', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('chain512-1', '/plain/path', None),
    ('chain512-2', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('chain512-2', '/plain/path', None),
    ('chain512-3', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('chain512-3', '/plain/path', None),
    ('chain512-4', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('chain512-4', '/plain/path', None),
    ('chain512-5', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('chain512-5', '/plain/path', None),
    ('chain512-6', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('chain512-6', '/plain/path', None),
    ('chain512-7', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('chain512-7', '/plain/path', None),
    ('chain512-8', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('chain512-8', '/plain/path', None),
    ('long-quoted-value', '$S/p.py', SC + '/x' * 3000 + '/p.py'),
    ('long-quoted-value', '/plain/path', None),
    ('long-leading-blanks', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('long-leading-blanks', '/plain/path', None),
    ('quoted-value-over-newline', '$S/p.py', None),
    ('quoted-value-over-newline', '/plain/path', None),
    ('assign-then-long-statements', '$S/p.py', '/tmp/golden_sc/p.py'),
    ('assign-then-long-statements', '/plain/path', None),
]
# GOLDEN-DATA-END


def _expand_function() -> str:
    text = HOOK.read_text(encoding="utf-8")
    found = re.search(r"^expand_command_variable\(\) \{\n.*?^\}\n", text, re.S | re.M)
    assert found, "hooks/pre-tool.sh has no expand_command_variable function"
    return found.group(0)


def test_expand_command_variable_gives_the_same_results_as_before(tmp_path):
    """Each row is a command and a target with the result the function gave
    before it was made faster, taken from the unchanged function (supports
    `TRC-010` in pre-tool-hook-time-bounded/acceptance-criteria.md)."""
    function = tmp_path / "expand.sh"
    function.write_text(_expand_function(), encoding="utf-8")
    script = 'set -euo pipefail\nsource "$1"\nexpand_command_variable "$2" "$3"'
    bad = []
    for key, target, expected in GOLDEN_ROWS:
        command = GOLDEN_COMMANDS[key] if key in GOLDEN_COMMANDS else GOLDEN_GENERATORS[key]()
        r = _bash_run(script, str(function), target, command)
        want = (target if expected is None else expected) + "\n"
        if r.returncode != 0 or r.stdout != want:
            bad.append((key, target, expected, r.returncode, r.stdout[:80], r.stderr[:80]))
    assert not bad, bad[:5]
