"""The plugin directory's validator reads every hook script, each command
pre-approves only the commands it runs, and a subprocess gets only the
environment it needs.

| Scenario | What it checks |
|---|---|
| `TRC-A1` | no hook script holds a here-document or an inline Python program |
| `TRC-A2` | no hook script is longer than the validator reads in full |
| `TRC-A3` | a moved program reads the hook's standard input only where it did |
| `TRC-A4` | no entry hook runs a command inside a double-quoted string |
| `TRC-A5` | no entry hook nests a quote inside a double-quoted string |
| `TRC-B1` | no command pre-approves bare `Bash` |
| `TRC-B2` | a command that writes only issue state writes only there |
| `TRC-B3` | a command that runs a `compass` verb pre-approves `compass` |
| `TRC-C1` | `gh` gets an allow-list of the environment |
| `TRC-C2` | the Codex adapter's shared hooks get an allow-list of the environment |
| `TRC-K1` | the plugin copy passes the directory checks of the local `claude` command |
| `TRC-K2` | no new subprocess gets the whole environment, no new binary file, nothing new in `bin/` |

The directory's safety scan and policy review run on its servers only, so most
of these tests check the rules its report states, not the validator itself.
The test for the local checks runs them where `claude` is installed. The two
scenarios with the K ids are from ayeo-io/compass-delivery#319.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import github_labels  # noqa: E402

#: The hook scripts the plugin runs. Only the owner changes the approval prompt
#: hook: the pre-tool hook refuses an agent read or edit of it.
HOOKS = ("pre-tool.sh", "post-tool.sh", "stop.sh", "session-start.sh",
         "approval-summary.sh", "prompt-approval.sh")
LONGEST = 700


def _scripts():
    found = [ROOT / "hooks" / name for name in HOOKS]
    found += sorted((ROOT / "hooks" / "lib").glob("*.sh"))
    found += sorted((ROOT / "scripts" / "lib").glob("*.sh"))
    found.append(ROOT / "bin" / "compass")
    return found


def _code_lines(path):
    """The script's lines that are not comments, with their numbers."""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.lstrip().startswith("#"):
            yield number, line


HERE_DOCUMENT = re.compile(r"(?<!<)<<(?!<)")
INLINE_PROGRAM = re.compile(r"\b(?:python3?|compass_python)\s+-c?(?:\s|$|[\"'])")
PROGRAM_FILE = re.compile(r"hooks/py/([\w.-]+\.py)")


def test_trc_a1_no_hook_script_carries_an_inline_program():
    found = []
    for path in _scripts():
        rel = path.relative_to(ROOT)
        for number, line in _code_lines(path):
            if HERE_DOCUMENT.search(line):
                found.append(f"{rel}:{number}: here-document: {line.strip()}")
            if INLINE_PROGRAM.search(line):
                found.append(f"{rel}:{number}: inline program: {line.strip()}")
            for name in PROGRAM_FILE.findall(line):
                if not (ROOT / "hooks" / "py" / name).is_file():
                    found.append(f"{rel}:{number}: names a missing program hooks/py/{name}")
    assert not found, "\n".join(found)


def test_trc_a2_no_hook_script_is_too_long():
    long = [f"{p.relative_to(ROOT)}: {n} lines" for p in _scripts()
            if (n := len(p.read_text(encoding="utf-8").splitlines())) > LONGEST]
    assert not long, "\n".join(long)


#: The hooks the validator reads as entry points. It cannot read a command
#: inside a double-quoted string, such as `x="$(cmd)"` or
#: `"$(dirname "$(dirname "$d")")"`, so it refused both as running a program
#: it cannot name (UNPINNED_NPX on the 8.0.1 copy).
ENTRY_HOOKS = ("pre-tool.sh", "post-tool.sh")


def _commands_inside_quotes(text):
    """How many `$(` start inside a double-quoted string. Inside `$(...)`
    quoting starts again, so the stack holds each context in turn."""
    stack, found, i = [], 0, 0
    while i < len(text):
        c, top = text[i], (stack[-1] if stack else None)
        if top == "'":
            if c == "'":
                stack.pop()
        elif c == "\\":
            i += 1
        elif c == "$" and text[i + 1:i + 2] == "(":
            found += top == '"'
            stack.append("$(")
            i += 1
        elif top == '"':
            if c == '"':
                stack.pop()
        elif c in "'\"":
            stack.append(c)
        elif c == "(":
            stack.append("(")
        elif c == ")" and top in ("$(", "("):
            stack.pop()
        i += 1
    return found


def test_trc_a4_no_entry_hook_runs_a_command_inside_a_quoted_string():
    found = []
    for name in ENTRY_HOOKS:
        path = ROOT / "hooks" / name
        for number, command in _commands_in(path):
            if _commands_inside_quotes(command):
                found.append(f"hooks/{name}:{number}: {command.strip()}")
    assert not found, "\n".join(found)


def test_trc_a4_the_quote_reader_finds_a_command_inside_quotes():
    assert _commands_inside_quotes('x="$(cmd)"') == 1
    assert _commands_inside_quotes('x="$(cd "$(dirname "$d")" && pwd)"') == 2
    assert _commands_inside_quotes('x=$(cd "$(dirname "$d")" && pwd)') == 1
    assert _commands_inside_quotes("x=$(printf '%s' \"$y\" | jq -r '.a')") == 0
    assert _commands_inside_quotes("echo '\"$(not run)\"'") == 0


def _quotes_inside_quotes(text):
    """How many quotes sit inside a double-quoted string: an escaped `\\"`, a
    `$'...'` string, or a quote inside a `${...}` expansion. The validator
    still blocked the 8.0.2 copy once no command sat in a double-quoted
    string; a test branch that rewrote only such lines in the two entry hooks
    passed it."""
    stack, found, i = [], 0, 0
    while i < len(text):
        c, top = text[i], (stack[-1] if stack else None)
        if top == "'":
            if c == "'":
                stack.pop()
        elif top == "${":
            if c in "\"'":
                found += 1
            elif c == "}":
                stack.pop()
        elif c == "\\":
            found += top == '"' and text[i + 1:i + 2] == '"'
            i += 1
        elif top == '"':
            if c == '"':
                stack.pop()
            elif c == "$" and text[i + 1:i + 2] == "'":
                found += 1
            elif c == "$" and text[i + 1:i + 2] == "{":
                stack.append("${")
                i += 1
        elif c in "'\"":
            stack.append(c)
        i += 1
    return found


def test_trc_a5_no_entry_hook_nests_a_quote_inside_a_quoted_string():
    found = []
    for name in ENTRY_HOOKS:
        for number, command in _commands_in(ROOT / "hooks" / name):
            if _quotes_inside_quotes(command):
                found.append(f"hooks/{name}:{number}: {command.strip()}")
    assert not found, "\n".join(found)


def test_trc_a5_the_quote_reader_finds_a_quote_inside_quotes():
    assert _quotes_inside_quotes('t="${a#"$b"/}"') == 2
    assert _quotes_inside_quotes('f="${f//\\\\\\"/\\"}"') == 2
    assert _quotes_inside_quotes("f=\"${f//x/$'\\t'}\"") == 2
    assert _quotes_inside_quotes("echo \"a $'b'\"") == 1
    assert _quotes_inside_quotes('t=${a:${#b}+1}') == 0
    assert _quotes_inside_quotes('f=${f//"$bs$q"/"$q"}') == 0
    assert _quotes_inside_quotes("x=\"$a ${b:-c}\" y='\"${z}\"'") == 0


#: Programs that read the hook's own standard input, as the `-c` program they
#: replace did: the summary reads the prompt's session and prompt ids.
READS_HOOK_INPUT = ("approval_summary.py",)


def _commands_in(path):
    """Each command with its `\\`-continued lines joined, and its first line."""
    pending, first = "", 0
    for number, line in _code_lines(path):
        if not pending:
            first = number
        if line.rstrip().endswith("\\"):
            pending += line.rstrip()[:-1] + " "
            continue
        yield first, pending + line
        pending = ""


def test_trc_a3_a_moved_program_reads_stdin_only_where_it_did():
    """A program read from a here-document saw end-of-file on its standard
    input, so its call from a file closes standard input. A program that was
    fed a pipe keeps the pipe."""
    calls = []
    for path in _scripts():
        for number, line in _commands_in(path):
            named = PROGRAM_FILE.search(line)
            if named and re.search(r"\b(?:compass_python|python3)\b", line):
                piped = re.search(r"\|\s*(?:compass_python|python3)\b", line)
                closed = "</dev/null" in line
                passed_on = named.group(1) in READS_HOOK_INPUT
                calls.append((path.relative_to(ROOT), number, piped or closed or passed_on,
                              line.strip()))
    assert calls, "no script runs a program from hooks/py/"
    open_input = [f"{p}:{n}: {text}" for p, n, ok, text in calls if not ok]
    assert not open_input, "\n".join(open_input)


# --- the commands ----------------------------------------------------------------------------

#: The commands that write only issue state and documents. The rest write code or
#: project files: define (a hotfix's reproduction test), go, implement, quick-fix,
#: resume and ship (living documents anywhere in the project).
ISSUE_STATE_ONLY = ("assess", "breakdown", "consult", "design", "flow", "init", "intent",
                    "plan", "position", "refine", "status", "verify")
SCOPES = ("./.compass/**", "./docs/**")


def _allowed(path):
    match = re.search(r"^allowed-tools: (.*)$", path.read_text(encoding="utf-8"), re.M)
    if not match:
        return None
    return [t.strip() for t in re.split(r",\s*(?![^()]*\))", match.group(1))]


def _commands():
    return [p for p in sorted((ROOT / "commands").glob("*.md")) if _allowed(p) is not None]


def test_trc_b1_no_command_pre_approves_every_shell_command():
    found = []
    for path in _commands():
        for tool in _allowed(path):
            if tool == "Bash":
                found.append(f"{path.stem}: bare Bash")
            elif tool.startswith("Bash(") and not tool.startswith("Bash(compass "):
                found.append(f"{path.stem}: {tool} does not name the compass CLI")
    assert _commands(), "no command declares allowed-tools"
    assert not found, "\n".join(found)


def test_trc_b2_issue_state_commands_scope_their_writes():
    found = []
    for name in ISSUE_STATE_ONLY:
        tools = _allowed(ROOT / "commands" / f"{name}.md")
        assert tools is not None, name
        scopes = SCOPES + (("./compass.yml",) if name == "init" else ())
        for tool in tools:
            if tool in ("Write", "Edit"):
                found.append(f"{name}: bare {tool}")
            match = re.fullmatch(r"(Write|Edit)\((.*)\)", tool)
            if match and match.group(2) not in scopes:
                found.append(f"{name}: {tool} is outside {scopes}")
    assert not found, "\n".join(found)


def test_trc_b3_a_command_that_runs_compass_pre_approves_it():
    found = []
    for path in _commands():
        body = path.read_text(encoding="utf-8").split("---", 2)[2]
        if re.search(r"`compass [a-z]", body) and "Bash(compass *)" not in _allowed(path):
            found.append(path.stem)
    assert not found, f"these commands run a compass verb without Bash(compass *): {found}"


# --- the environment -------------------------------------------------------------------------

SECRET = "AWS_SECRET_ACCESS_KEY"


class _Done:
    returncode = 0
    stdout = "{}"
    stderr = ""


def test_trc_c1_gh_gets_only_the_variables_it_needs(monkeypatch):
    seen = {}

    def run(argv, **kwargs):
        seen.update(kwargs["env"])
        return _Done()

    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("HOME", "/home/someone")
    monkeypatch.setenv("GH_TOKEN", "a-token")
    monkeypatch.setenv(SECRET, "do-not-pass")
    monkeypatch.setattr(github_labels.subprocess, "run", run)
    github_labels._gh(["api", "user"])
    assert seen["PATH"] == "/usr/bin"
    assert seen["HOME"] == "/home/someone"
    assert seen["GH_TOKEN"] == "a-token"
    assert seen["GH_PROMPT_DISABLED"] == "1"
    assert SECRET not in seen


def _runtime():
    spec = importlib.util.spec_from_file_location(
        "codex_runtime_under_test", ROOT / "adapters" / "codex" / "runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_trc_c2_codex_shared_hooks_get_only_the_variables_they_need(monkeypatch, tmp_path):
    runtime = _runtime()
    seen = {}

    def run(argv, **kwargs):
        seen.update(kwargs["env"])
        return _Done()

    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("HOME", "/home/someone")
    monkeypatch.setenv("COMPASS_ISSUE", "an-issue")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/another/project")
    monkeypatch.setenv(SECRET, "do-not-pass")
    monkeypatch.setattr(runtime.subprocess, "run", run)
    runtime.shared_hook("stop.sh", {"cwd": str(tmp_path)})
    assert seen["PATH"] == "/usr/bin"
    assert seen["HOME"] == "/home/someone"
    assert seen["COMPASS_ISSUE"] == "an-issue"
    assert seen["CLAUDE_PLUGIN_ROOT"] == str(ROOT)
    assert "CLAUDE_PROJECT_DIR" not in seen
    assert SECRET not in seen


# --- what the plugin copy holds ----------------------------------------------------------------


def _plugin_files():
    """The tracked files the plugin copy ships, by the rules of
    scripts/plugin-files.txt. A new file counts once it is staged."""
    spec = importlib.util.spec_from_file_location(
        "build_plugin_copy_under_test", ROOT / "scripts" / "build-plugin-copy.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    keep, drop = build.wanted(str(ROOT), "HEAD")
    listed = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True,
                            text=True, check=True).stdout.split("\0")
    return [p for p in listed if p and build._selected(p, keep, drop)]


_RUNS = ("run", "Popen", "call", "check_call", "check_output")


def _whole_environment_calls(source):
    """Each `subprocess` call that gets the person's whole environment, as
    (function, line): one with no `env=`, or with an `env=` built from
    `os.environ`. A call that passes `**kwargs` is not judged, because its
    caller chooses the environment."""
    found = []

    class Calls(ast.NodeVisitor):
        def __init__(self):
            self.functions = []

        def visit_FunctionDef(self, node):
            self.functions.append(node.name)
            self.generic_visit(node)
            self.functions.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr in _RUNS
                    and isinstance(func.value, ast.Name) and func.value.id == "subprocess"
                    and not any(k.arg is None for k in node.keywords)):
                env = [k.value for k in node.keywords if k.arg == "env"]
                if not env or "os.environ" in ast.unparse(env[0]):
                    found.append((self.functions[-1] if self.functions else "<module>",
                                  node.lineno))
            self.generic_visit(node)

    Calls().visit(ast.parse(source))
    return found


_GIT = ("runs git in the person's repository, and git reads their configuration, "
        "credential helper and SSH agent from the environment")
_PROJECT = "runs the person's own test or project command, which needs their environment"

#: The calls that keep the whole environment, with the reason. 8.0.4 passed the
#: directory with each of them. A new call needs an allow-list, as the tests
#: above give `gh` and the Codex hooks, or an entry here that a reviewer accepts.
INHERITS_ENVIRONMENT = {
    ("cli/compass_pkg/analyze.py", "_git_out"): _GIT,
    ("cli/compass_pkg/analyze.py", "_landed_before"): _GIT,
    ("cli/compass_pkg/checks.py", "_git_out"): _GIT,
    ("cli/compass_pkg/checks.py", "_check_command_passes"): _PROJECT,
    ("cli/compass_pkg/decisions.py", "_git"): _GIT,
    ("cli/compass_pkg/decisions.py", "history_problems"): _GIT,
    ("cli/compass_pkg/effective.py", "_git_blob"): _GIT,
    ("cli/compass_pkg/flow.py", "git"): _GIT,
    ("cli/compass_pkg/github_links.py", "_git"): _GIT,
    ("cli/compass_pkg/landed_by.py", "_git_commit_subject"): _GIT,
    ("cli/compass_pkg/landed_by.py", "_git_is_usable"): _GIT,
    ("cli/compass_pkg/lessons.py", "_decider"): _GIT,
    ("cli/compass_pkg/manifest.py", "_git"): _GIT,
    ("cli/compass_pkg/manifest.py", "cmd_land_commit"):
        "runs the project's own pre-commit hooks, which need the person's environment",
    ("cli/compass_pkg/publish_check.py", "_ignored"): _GIT,
    ("cli/compass_pkg/quick_fix_cmd.py", "_untracked_paths"): _GIT,
    ("cli/compass_pkg/quick_fix_cmd.py", "_write_start_state"): _GIT,
    ("cli/compass_pkg/quick_fix_cmd.py", "_untraced_since_start"): _GIT,
    ("cli/compass_pkg/quick_fix_cmd.py", "_commit_files"): _GIT,
    ("cli/compass_pkg/quick_fix_cmd.py", "_write_verification_note"): _GIT,
    ("cli/compass_pkg/readiness_record.py", "_git"): _GIT,
    ("cli/compass_pkg/readiness_run.py", "_git"): _GIT,
    ("cli/compass_pkg/readiness_run.py", "_run_one"): _PROJECT,
    ("cli/compass_pkg/record.py", "_git"): _GIT,
    ("cli/compass_pkg/release_notes.py", "_git"): _GIT,
    ("cli/compass_pkg/replay.py", "_git"): _GIT,
    ("cli/compass_pkg/ship_commit_reason.py", "_pre_commit_hook_can_run"): _GIT,
    ("cli/compass_pkg/spec_refresh.py", "_git"): _GIT,
    ("cli/compass_pkg/start_state.py", "_git_changed_paths"): _GIT,
    ("cli/compass_pkg/start_state.py", "_record_path"): _GIT,
    ("cli/compass_pkg/start_state.py", "_tracked_paths"): _GIT,
    ("cli/compass_pkg/subtasks.py", "_git"): _GIT,
    ("cli/compass_pkg/tdd.py", "_run_test"): _PROJECT,
    ("cli/compass_pkg/tip_scope.py", "_git"): _GIT,
}


def _is_binary(data):
    """A file the directory reads as binary: a NUL byte, or bytes that are not UTF-8."""
    if b"\0" in data:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


#: The binary files the plugin ships, each one in 8.0.4 when it passed the directory.
BINARY_FILES = {
    "assets/board-example.png": "the board image the README shows",
    "assets/compass-icon.png": "the plugin's icon",
    "governance/shipped-releases.tar.xz": "the governance files of each release, which "
                                          "`compass policy migrate` reads",
}

#: The launchers in `bin/`. ayeo-io/compass-delivery#312 decides whether `bin/`
#: moves; until then nothing is added to it.
BIN_FILES = ("bin/compass", "bin/compass-statusline")



def test_trc_k2_the_environment_reader_finds_a_whole_environment():
    source = (
        "import os, subprocess\n"
        "def inherits():\n"
        "    subprocess.run(['git', 'status'])\n"
        "def copies():\n"
        "    subprocess.run(['tool'], env=os.environ.copy())\n"
        "def spreads():\n"
        "    subprocess.Popen(['tool'], env={**os.environ, 'A': '1'})\n"
        "def names_it():\n"
        "    subprocess.check_output(['tool'], env=os.environ)\n"
        "def allow_listed(env):\n"
        "    subprocess.run(['gh'], env=env)\n")
    assert _whole_environment_calls(source) == [
        ("inherits", 3), ("copies", 5), ("spreads", 7), ("names_it", 9)]


def test_trc_k2_no_subprocess_gets_the_whole_environment():
    found, seen = [], set()
    for path in _plugin_files():
        if not path.endswith(".py") or path.startswith("cli/vendor/"):
            continue
        for function, line in _whole_environment_calls((ROOT / path).read_text(encoding="utf-8")):
            seen.add((path, function))
            if (path, function) not in INHERITS_ENVIRONMENT:
                found.append(f"{path}:{line}: {function} gives a subprocess the whole environment")
    stale = sorted(set(INHERITS_ENVIRONMENT) - seen)
    assert not found, "\n".join(found)
    assert not stale, f"these exceptions match no call any more; remove them: {stale}"


def test_trc_k2_the_binary_reader_finds_a_binary_file():
    assert _is_binary(b"\x89PNG\r\n\x1a\n\0\0")
    assert _is_binary(b"caf\xe9")
    assert not _is_binary("café → ok\n".encode("utf-8"))


def test_trc_k2_no_plugin_file_is_binary():
    found = [f"{path}: a binary file" for path in _plugin_files()
             if path not in BINARY_FILES and _is_binary((ROOT / path).read_bytes())]
    assert not found, "\n".join(found)


def test_trc_k2_bin_holds_only_the_launchers():
    found = [f"{path}: a file added to bin/" for path in _plugin_files()
             if path.startswith("bin/") and path not in BIN_FILES]
    assert not found, "\n".join(found)


def test_trc_k1_the_plugin_copy_passes_the_directory_validator(tmp_path):
    claude = shutil.which("claude")
    if not claude:
        pytest.skip("the claude command is not installed; the release checklist runs this")
    copy = tmp_path / "copy"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build-plugin-copy.py"),
                    "--ref", "HEAD", "--out", str(copy)], check=True, capture_output=True)
    run = subprocess.run([claude, "plugin", "validate", "--profile", "directory", "--strict",
                          str(copy)], capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "found nothing to report" in run.stdout, run.stdout


# The hook scenarios a client observes - a missing or unreadable part, an
# unreadable shared helper - are executable specifications in
# tests/acceptance/hooks/test_hook_refusals.py (ayeo-io/compass-delivery#306).
