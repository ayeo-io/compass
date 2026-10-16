"""Red-before-green must apply to shell commands that write production files.

The hook enforced the TDD strategy for the Edit, Write, and MultiEdit tools.
A shell command that writes the same file - `sed -i`, a `>` redirect, an inline
`python3 -c` script - was never seen by it, so choosing a different tool
stepped around the enforcement entirely.

Detection is deliberately conservative and fails OPEN: only recognised write
shapes block, everything else is allowed, and the residual gap is stated in
docs/safety-contract.md. Blocking on suspicion would block `make`, `npm test`,
and every unrecognised command, and an enforcement people disable protects
nothing at all.

Scenarios: hook-bash-write-bypass/acceptance-criteria.md (SCN-A1..F2).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from conftest import write_red_record

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = FRAMEWORK_ROOT / "hooks" / "pre-tool.sh"
HOOKS_JSON = FRAMEWORK_ROOT / "hooks" / "hooks.json"


def _fresh_project_dir() -> Path:
    """A temp dir whose path contains no 'test'/'spec' substring, as a
    matching convention with the fixtures above it.

    The hook exempts a target file whose own basename or project-relative
    path matches, not the project directory's name; a fixture whose target
    lived under a path matching by basename or relative path would be
    exempt for the wrong reason and every assertion below would pass
    without checking anything.
    """
    return Path(tempfile.mkdtemp(prefix="compass-fix-"))


def _project(slug: str = "framed", *, route: bool = True, red: bool = False,
             spike: bool = False) -> tuple[Path, Path]:
    root = _fresh_project_dir()
    task_dir = root / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (root / ".compass" / "current-task").write_text(slug, encoding="utf-8")
    if route:
        (task_dir / "delivery-approach.md").write_text("# Route\n\nroute: standard\n", encoding="utf-8")
    if red:
        write_red_record(task_dir)
    if spike:
        (task_dir / ".spike").write_text("", encoding="utf-8")
    return root, task_dir


def _run(project: Path, payload: dict) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    return subprocess.run(
        ["bash", str(HOOK_PATH)],
        input=json.dumps(payload), capture_output=True, text=True, env=env,
    )


def _bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# ---------------------------------------------------------------------------
# Group A - Bash writes that must be blocked (SCN-A1..A4)
# ---------------------------------------------------------------------------

BLOCKED_SHAPES = [
    pytest.param('echo "x = 1" > src/app.py', id="SCN-A1-redirect"),
    pytest.param('echo "x = 1" >> src/app.py', id="SCN-A1-append"),
    pytest.param("sed -i '' 's/a/b/' src/app.py", id="SCN-A2-sed-inplace"),
    pytest.param("perl -i -pe 's/a/b/' src/app.py", id="SCN-A2-perl-inplace"),
    pytest.param('python3 -c \'open("src/app.py","w").write("x")\'', id="SCN-A3-python-c"),
    pytest.param('echo x | tee src/app.py', id="SCN-A3-tee"),
    pytest.param('cp /tmp/thing.py src/app.py', id="SCN-A3-cp"),
    pytest.param('mv /tmp/thing.py src/app.py', id="SCN-A3-mv"),
    pytest.param('patch -p1 < /tmp/fix.diff', id="SCN-A3-patch"),
    pytest.param('git apply /tmp/fix.diff', id="SCN-A3-git-apply"),
    # Scenario `TRC-B3`: each of these writes the guarded app file through
    # tee, cp or mv, which are found in their own simple command. Taking the last word
    # of the whole line, the hook used to allow the cp shapes with `sudo`,
    # `(...)`, `2>&1` or a command after them.
    pytest.param('echo x|tee src/app.py', id="TRC-B3-tee-no-space"),
    pytest.param('echo x | tee -a /tmp/log.txt src/app.py', id="TRC-B3-tee-two-files"),
    pytest.param('echo x | sudo tee src/app.py > /dev/null', id="TRC-B3-sudo-tee"),
    pytest.param('echo x > >(tee src/app.py)', id="TRC-B3-tee-process-substitution"),
    pytest.param('make && cp a.py src/app.py', id="TRC-B3-cp-after-and"),
    pytest.param('cp a.py src/app.py; echo done', id="TRC-B3-cp-then-command"),
    pytest.param('cp a.py src/app.py 2>&1', id="TRC-B3-cp-dup-stderr"),
    pytest.param('cp a.py src/app.py 2>/dev/null', id="TRC-B3-cp-stderr-to-null"),
    pytest.param('sudo cp a.py src/app.py', id="TRC-B3-sudo-cp"),
    pytest.param('(cp a.py src/app.py)', id="TRC-B3-cp-subshell"),
    pytest.param('{ cp a.py src/app.py; }', id="TRC-B3-cp-group"),
    pytest.param('if true; then cp a.py src/app.py; fi', id="TRC-B3-cp-in-if"),
    pytest.param('cp a.py src/app.py\necho done', id="TRC-B3-cp-own-line"),
    pytest.param('mv -f a.py src/app.py && ls', id="TRC-B3-mv-then-command"),
    pytest.param('git mv a.py src/app.py', id="TRC-B3-git-mv"),
    # A wrapper or a spelled-out path in front of the command word must not
    # hide the write: the hook before this change refused each of these.
    pytest.param('make && timeout 10 cp a.py src/app.py', id="TRC-B3-timeout-cp"),
    pytest.param('echo x | xargs tee src/app.py', id="TRC-B3-xargs-tee"),
    pytest.param('echo x | nice -n 5 tee src/app.py', id="TRC-B3-nice-tee"),
    pytest.param('make && /bin/cp a.py src/app.py', id="TRC-B3-path-cp"),
    pytest.param('ls && \\cp a.py src/app.py', id="TRC-B3-escaped-cp"),
    pytest.param('echo x | /usr/bin/tee src/app.py', id="TRC-B3-path-tee"),
    pytest.param('x=$(cp a.py src/app.py)', id="TRC-B3-cp-in-substitution"),
    pytest.param('make && cp a.py src/app.py # copy', id="TRC-B3-cp-then-comment"),
    # Scenario `TRC-W1`: a substitution, a process substitution, backticks
    # or a line continuation inside a tee, cp or mv command must not cut it
    # in two. The hook before ayeo-io/compass#583 refused each of these; the
    # post-merge review of that PR found #583 allowed them.
    pytest.param('cp $(git rev-parse --show-toplevel)/a.py src/app.py', id="TRC-W1-cp-substitution"),
    pytest.param('cp "$(mktemp)" src/app.py', id="TRC-W1-cp-quoted-substitution"),
    pytest.param('cp `mktemp` src/app.py', id="TRC-W1-cp-backticks"),
    pytest.param('cp <(echo x) src/app.py', id="TRC-W1-cp-process-substitution"),
    pytest.param('mv $(ls /tmp/*.py) src/app.py', id="TRC-W1-mv-substitution"),
    pytest.param('S=/tmp/x; cp $(ls $S/*.py) src/app.py', id="TRC-W1-cp-substitution-with-variable"),
    pytest.param('echo x | tee $(echo /tmp/log.txt) src/app.py', id="TRC-W1-tee-substitution"),
    pytest.param('echo x | tee >(cat) src/app.py', id="TRC-W1-tee-process-substitution"),
    pytest.param('cp a.py \\\n  src/app.py', id="TRC-W1-cp-continuation"),
    pytest.param('echo x | tee \\\n  src/app.py', id="TRC-W1-tee-continuation"),
    pytest.param('mv -f /tmp/a.py \\\n  src/app.py', id="TRC-W1-mv-continuation"),
    pytest.param('x=`cp a.py src/app.py`', id="TRC-W1-cp-inside-backticks"),
    pytest.param('echo "$(cp a.py src/app.py)"', id="TRC-W1-cp-inside-quoted-substitution"),
    pytest.param('echo x > \\\n  src/app.py', id="TRC-W1-redirect-continuation"),
    pytest.param('echo x >| src/app.py', id="TRC-W1-clobber-redirect"),
    # Scenario `TRC-Q1`: a quoted target names the same file as an unquoted
    # one (ayeo-io/compass-delivery-record#184).
    pytest.param('echo x > "src/app.py"', id="TRC-Q1-double-quoted-redirect"),
    pytest.param("echo x > 'src/app.py'", id="TRC-Q1-single-quoted-redirect"),
    pytest.param('echo x >> "src/app.py"', id="TRC-Q1-quoted-append"),
    pytest.param('echo x | tee "src/app.py"', id="TRC-Q1-quoted-tee"),
    pytest.param("cp a.py 'src/app.py'", id="TRC-Q1-quoted-cp"),
    # Scenario `TRC-S1`: a quoted bracket inside a substitution must not
    # keep the span open to the end of the line and hide the destination
    # (ayeo-io/compass-delivery-record#186). The hook before
    # ayeo-io/compass#583 refused each of these.
    pytest.param("cp \"$(echo '(')\" src/app.py", id="TRC-S1-single-quoted-bracket"),
    pytest.param('cp "$(echo "(")" src/app.py', id="TRC-S1-double-quoted-bracket"),
    pytest.param("cp $(echo '(') src/app.py", id="TRC-S1-unquoted-span"),
    pytest.param("cp \"$(echo \"$(echo '(')\")\" src/app.py", id="TRC-S1-nested-span"),
    pytest.param('cp "$(echo \\()" src/app.py', id="TRC-S1-escaped-bracket"),
    pytest.param("cp a.py \"$(echo '(')\" src/app.py", id="TRC-S1-span-in-the-middle"),
    pytest.param("mv \"$(grep -l 'x(' a)\" src/app.py", id="TRC-S1-mv"),
    pytest.param("tee \"$(echo '(')\" src/app.py", id="TRC-S1-tee"),
]


@pytest.mark.parametrize("command", BLOCKED_SHAPES)
def test_write_shape_is_blocked_without_a_red(command):
    """SCN-A1..A3 - a recognised shell write of a source file needs a red first."""
    project, _ = _project(red=False)
    try:
        result = _run(project, _bash(command))
        assert result.returncode == 2, (
            f"expected a block for {command!r}, got exit {result.returncode}\n"
            f"stderr: {result.stderr}"
        )
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_block_message_names_the_command_and_the_tool():
    """A block a reader cannot act on is only half an enforcement."""
    project, _ = _project(red=False)
    try:
        result = _run(project, _bash("sed -i '' 's/a/b/' src/app.py"))
        assert result.returncode == 2
        assert "src/app.py" in result.stderr, result.stderr
        assert "Bash" in result.stderr, result.stderr
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_write_shape_is_allowed_once_a_red_is_on_record():
    """SCN-A4 - the marker means the same thing for Bash as for Edit."""
    project, _ = _project(red=True)
    try:
        result = _run(project, _bash("sed -i '' 's/a/b/' src/app.py"))
        assert result.returncode == 0, result.stderr
    finally:
        shutil.rmtree(project, ignore_errors=True)


# ---------------------------------------------------------------------------
# Group B - Bash that must not be blocked (SCN-B1..B4)
# ---------------------------------------------------------------------------

ALLOWED_COMMANDS = [
    pytest.param('grep -rn "TODO" src/', id="SCN-B1-read-only"),
    pytest.param('ls -la src/', id="SCN-B1-ls"),
    pytest.param('git commit -m "wip"', id="SCN-B1-git-commit"),
    pytest.param('make build', id="SCN-B1-make"),
    pytest.param("cat > tests/test_app.py <<'EOF'\nx\nEOF", id="SCN-B2-test-file"),
    pytest.param('echo "x" > docs/notes.md', id="SCN-B2-markdown"),
    pytest.param('python3 -m pytest -q > /tmp/out.txt', id="SCN-B3-non-code-dest"),
    pytest.param('echo hi > /dev/null', id="SCN-B3-dev-null"),
    pytest.param('git checkout -- src/app.py', id="SCN-B4-git-checkout"),
    pytest.param('git restore src/app.py', id="SCN-B4-git-restore"),
    # Scenario `TRC-B1`: tee writes only its own arguments. The command that feeds it
    # runs the script; it does not write it.
    pytest.param('python3 src/cmp.py a.json | tee /tmp/x/out.txt', id="TRC-B1-tee-input"),
    pytest.param('python3 /tmp/x/cmp.py a.json | tee /tmp/x/out.txt', id="TRC-B1-tee-scratch"),
    # Scenario `TRC-B2`: cp and mv write only their own last argument, not a file that a
    # later command in the same line reads.
    pytest.param('cp /tmp/a.py /tmp/b/ && grep -n x src/app.py', id="TRC-B2-cp-then-read"),
    pytest.param('mv /tmp/a.py /tmp/b.py; cat src/app.py', id="TRC-B2-mv-then-read"),
    pytest.param('cp src/app.py /tmp/app.py', id="TRC-B2-cp-source"),
    # Scenario `TRC-Q1`: a quoted target that is not production code stays
    # allowed once its quotes are removed.
    pytest.param('echo x > "docs/notes.md"', id="TRC-Q1-quoted-markdown"),
    pytest.param("echo x > 'tests/test_app.py'", id="TRC-Q1-quoted-test-file"),
    pytest.param('echo x > "/tmp/x/app.py"', id="TRC-Q1-quoted-outside"),
]


@pytest.mark.parametrize("command", ALLOWED_COMMANDS)
def test_ordinary_command_is_allowed(command):
    """SCN-B1..B4 - the hook does not obstruct work it has no business blocking."""
    project, _ = _project(red=False)
    try:
        result = _run(project, _bash(command))
        assert result.returncode == 0, (
            f"expected {command!r} to be allowed, got exit {result.returncode}\n"
            f"stderr: {result.stderr}"
        )
    finally:
        shutil.rmtree(project, ignore_errors=True)


# ---------------------------------------------------------------------------
# Group C - one classifier, one suspension (SCN-C1, SCN-C2)
# ---------------------------------------------------------------------------

SHARED_PATHS = ["src/app.py", "README.md", "tests/test_app.py", "src/notes.csv"]


@pytest.mark.parametrize("path", SHARED_PATHS)
def test_edit_and_bash_agree_on_the_same_path(path):
    """SCN-C1 - two classifiers would drift; there is only one."""
    project, _ = _project(red=False)
    try:
        as_edit = _run(project, {"tool_name": "Edit", "tool_input": {"file_path": path}})
        as_bash = _run(project, _bash(f'echo "x" > {path}'))
        assert as_edit.returncode == as_bash.returncode, (
            f"{path}: Edit exited {as_edit.returncode} but the equivalent Bash "
            f"redirect exited {as_bash.returncode} - the classifiers disagree."
        )
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_spike_route_suspends_the_check_for_bash_too():
    """SCN-C2 - on a Spike the TDD strategy is suspended, whichever tool is used."""
    project, _ = _project(red=False, spike=True)
    try:
        result = _run(project, _bash('echo "x" > src/probe.py'))
        assert result.returncode == 0, result.stderr
    finally:
        shutil.rmtree(project, ignore_errors=True)


# ---------------------------------------------------------------------------
# Failure modes (SCN-F1, SCN-F2)
# ---------------------------------------------------------------------------

def test_safety_contract_states_the_shell_detection_limit():
    """SCN-F1 - the gap that remains is written down, not left to be found."""
    contract = (FRAMEWORK_ROOT / "docs" / "safety-contract.md").read_text(encoding="utf-8")
    lowered = contract.lower()
    assert "best-effort" in lowered or "best effort" in lowered, (
        "docs/safety-contract.md must say that shell-command detection is "
        "best-effort - the contract currently promises more than the hook does."
    )
    assert "sed -i" in contract, (
        "the contract must name the shell write shapes that are detected, so a "
        "reader can tell which side of the line their command falls on."
    )


UNDETECTED_WRITES = [
    "cp a.ts $(echo src/app.ts)",
    "cp a.ts src/app.ts$(true)",
    "cp -t src /tmp/a.ts",
    "find . -name a.ts -exec cp {} src/app.ts \\;",
    "sudo sh -c 'cp a.ts src/app.ts'",
    'cp "a;b" src/app.ts',
    'cp "$(case x in x) echo y;; esac)" src/app.ts',
]


@pytest.mark.parametrize("command", UNDETECTED_WRITES)
def test_safety_contract_lists_the_writes_the_hook_does_not_detect(command):
    """Scenario `TRC-D1`: each write shape the hook is known to miss is named in the
    contract (ayeo-io/compass-delivery-record#188). The hook must still allow
    each example: if it starts to detect one, this fails, and the list must
    change with it, so the contract never names a gap that is closed."""
    contract = (FRAMEWORK_ROOT / "docs" / "safety-contract.md").read_text(encoding="utf-8")
    assert f"`{command}`" in contract, (
        f"docs/safety-contract.md must list {command!r} among the writes the "
        f"hook does not detect"
    )
    project, _ = _project(red=False)
    try:
        result = _run(project, _bash(command))
        assert result.returncode == 0, (
            f"the hook now refuses {command!r}; remove it from the list of "
            f"undetected writes in docs/safety-contract.md\n{result.stderr}"
        )
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_read_only_command_does_not_consult_task_state():
    """SCN-F2 - the hook now runs on every Bash call; it must be cheap.

    A command with no write-shaped token is allowed without resolving the
    issue, which is checked here by removing .compass entirely: the Edit
    path treats a missing .compass as "assessment has not run" and blocks,
    so if this command is allowed, the hook returned before looking.
    """
    project = _fresh_project_dir()
    try:
        result = _run(project, _bash('grep -rn "TODO" src/'))
        assert result.returncode == 0, (
            f"a read-only command consulted task state and blocked:\n{result.stderr}"
        )
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_hook_is_registered_for_bash():
    """The branch is unreachable unless hooks.json routes Bash to it."""
    registered = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    matchers = [
        entry.get("matcher", "")
        for entry in registered["hooks"]["PreToolUse"]
        if any("pre-tool.sh" in h.get("command", "") for h in entry.get("hooks", []))
    ]
    assert any("Bash" in m for m in matchers), (
        f"pre-tool.sh is not registered for Bash; PreToolUse matchers: {matchers}"
    )
