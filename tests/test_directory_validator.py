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
    scripts/plugin-files.txt, as the working tree holds them. A new file counts
    once it is staged; a file deleted but not yet staged is left out."""
    spec = importlib.util.spec_from_file_location(
        "build_plugin_copy_under_test", ROOT / "scripts" / "build-plugin-copy.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    keep, drop = build.wanted(str(ROOT), "HEAD")
    listed = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True,
                            text=True, check=True).stdout.split("\0")
    return [p for p in listed
            if p and build._selected(p, keep, drop) and (ROOT / p).is_file()]


#: The `subprocess` functions that take `env=`, and those that cannot.
_TAKES_ENV = ("run", "Popen", "call", "check_call", "check_output")
_NO_ENV = ("getoutput", "getstatusoutput")
#: The `os` functions that start a process. Each gets the whole environment or
#: one passed by position, so each new call is judged by a reviewer.
_OS_STARTS = re.compile(r"^(?:system|popen|exec\w*|spawn\w*|posix_spawn\w*)$")


def _is_environ(node):
    return (isinstance(node, ast.Attribute) and node.attr == "environ"
            and isinstance(node.value, ast.Name) and node.value.id == "os")


def _filters_by_name(comprehension):
    """A comprehension that keeps only the names it lists: an `if` that tests
    `k in (...)`, alone or with a prefix test. One that only leaves names out,
    such as `if not k.startswith("GIT_")`, keeps the rest of the environment."""
    return any(isinstance(node, ast.Compare) and isinstance(node.ops[0], ast.In)
               for test in comprehension.ifs for node in ast.walk(test))


def _copies_environment(node, assigned, depth=0):
    """Does `node`, given as `env=`, hold the whole environment? A name is read
    from its assignment in the nearest function that assigns it. `None`, a bare
    `os.environ`, its copy, a `dict(...)` or `{**...}` built on it, and a
    comprehension over it with no `if k in (...)` all do. Reading one name
    from it, `os.environ.get("PATH")` or `os.environ["PATH"]`, does not."""
    if depth > 5:
        return False
    again = lambda n: _copies_environment(n, assigned, depth + 1)  # noqa: E731
    if isinstance(node, ast.Constant):
        return node.value is None
    if _is_environ(node):
        return True
    if isinstance(node, ast.Name):
        for scope in reversed(assigned):
            if node.id in scope:
                return any(again(value) for value in scope[node.id])
        return False
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "copy":
            return again(func.value)
        if isinstance(func, ast.Name) and func.id == "dict":
            return any(again(arg) for arg in node.args)
        return False
    if isinstance(node, ast.BoolOp):
        return any(again(value) for value in node.values)
    if isinstance(node, ast.IfExp):
        return again(node.body) or again(node.orelse)
    if isinstance(node, ast.Dict):
        return any(key is None and again(value) for key, value in zip(node.keys, node.values))
    if isinstance(node, ast.DictComp):
        source = node.generators[0]
        over = source.iter.func.value if (isinstance(source.iter, ast.Call)
                                          and isinstance(source.iter.func, ast.Attribute)) \
            else source.iter
        return again(over) and not _filters_by_name(source)
    return False


def _whole_environment_calls(source):
    """Each call that starts a process with the person's whole environment, as
    (function, line), where the function is named with its class or outer
    function, such as `Runner.start` or `outer.inner`. A `subprocess` call with
    no `env=`, or with an `env=` that `_copies_environment` judges whole, counts;
    so do `getoutput`, `os.system`, `os.popen`, `os.exec*` and `os.spawn*`, under
    any name they are imported as. A call that passes `**kwargs`, or an `env`
    parameter it does not assign, is not judged: its caller chooses."""
    tree = ast.parse(source)
    modules, functions = set(), {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {a.asname or a.name for a in node.names if a.name == "subprocess"}
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            functions.update({a.asname or a.name: a.name for a in node.names})
    found = []

    class Calls(ast.NodeVisitor):
        def __init__(self):
            self.scopes, self.assigned = [], [{}]

        def visit_ClassDef(self, node):
            self.scopes.append(node.name)
            self.generic_visit(node)
            self.scopes.pop()

        def visit_FunctionDef(self, node):
            assigned = {}
            for inner in ast.walk(node):
                if isinstance(inner, ast.Assign):
                    for target in inner.targets:
                        if isinstance(target, ast.Name):
                            assigned.setdefault(target.id, []).append(inner.value)
            self.scopes.append(node.name)
            self.assigned.append(assigned)
            self.generic_visit(node)
            self.assigned.pop()
            self.scopes.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def _name(self, func):
            """The `subprocess` or `asyncio` function this call runs, or None."""
            if isinstance(func, ast.Name):
                return functions.get(func.id)
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id in modules:
                    return func.attr
                if func.value.id == "asyncio" and func.attr.startswith("create_subprocess_"):
                    return "run"
                if func.value.id == "os" and _OS_STARTS.match(func.attr):
                    return "os"
            return None

        def visit_Call(self, node):
            name = self._name(node.func)
            whole = False
            if name in ("os",) + _NO_ENV:
                whole = True
            elif name in _TAKES_ENV and not any(k.arg is None for k in node.keywords):
                env = [k.value for k in node.keywords if k.arg == "env"]
                whole = not env or _copies_environment(env[0], self.assigned)
            if whole:
                found.append((".".join(self.scopes) or "<module>", node.lineno))
            self.generic_visit(node)

    Calls().visit(tree)
    return found


_GIT = ("runs git in the person's repository, and git reads their configuration, "
        "credential helper and SSH agent from the environment")
_PROJECT = "runs the person's own test or project command, which needs their environment"

#: The functions whose calls keep the whole environment, with how many such calls
#: each holds and the reason. 8.0.4 passed the directory with each of them. A new call needs an allow-list, as the tests
#: above give `gh` and the Codex hooks, or an entry here that a reviewer accepts.
INHERITS_ENVIRONMENT = {
    ("cli/compass_pkg/analyze.py", "_git_out"): (1, _GIT),
    ("cli/compass_pkg/analyze.py", "_landed_before"): (1, _GIT),
    ("cli/compass_pkg/binding.py", "_git"): (1, _GIT),
    ("cli/compass_pkg/board_trees.py", "_git"): (1, _GIT + "; it leaves out only GIT_ variables"),
    ("cli/compass_pkg/checks.py", "_git_out"): (1, _GIT),
    ("cli/compass_pkg/checks.py", "_check_command_passes"): (1, _PROJECT),
    ("cli/compass_pkg/decisions.py", "_git"): (1, _GIT),
    ("cli/compass_pkg/decisions.py", "history_problems"): (1, _GIT),
    ("cli/compass_pkg/effective.py", "_git_blob"): (1, _GIT),
    ("cli/compass_pkg/flow.py", "_completed_on_this_branch.git"): (1, _GIT),
    ("cli/compass_pkg/github_links.py", "_git"): (1, _GIT),
    ("cli/compass_pkg/landed_by.py", "_git_commit_subject"): (1, _GIT),
    ("cli/compass_pkg/landed_by.py", "_git_is_usable"): (1, _GIT),
    ("cli/compass_pkg/lessons.py", "_decider"): (1, _GIT),
    ("cli/compass_pkg/manifest.py", "_git"): (1, _GIT),
    ("cli/compass_pkg/manifest.py", "cmd_land_commit"):
        (1, "runs the project's own pre-commit hooks, which need the person's environment"),
    ("cli/compass_pkg/publish_check.py", "_ignored"): (1, _GIT),
    ("cli/compass_pkg/quick_fix_cmd.py", "_untracked_paths"): (1, _GIT),
    ("cli/compass_pkg/quick_fix_cmd.py", "_write_start_state"): (3, _GIT),
    ("cli/compass_pkg/quick_fix_cmd.py", "_untraced_since_start"): (1, _GIT),
    ("cli/compass_pkg/quick_fix_cmd.py", "_commit_files"): (1, _GIT),
    ("cli/compass_pkg/quick_fix_cmd.py", "_write_verification_note"): (1, _GIT),
    ("cli/compass_pkg/readiness_record.py", "_git"): (1, _GIT),
    ("cli/compass_pkg/readiness_run.py", "_git"): (1, _GIT),
    ("cli/compass_pkg/readiness_run.py", "_run_one"): (1, _PROJECT),
    ("cli/compass_pkg/record.py", "_git"): (1, _GIT),
    ("cli/compass_pkg/release_notes.py", "_git"): (1, _GIT),
    ("cli/compass_pkg/replay.py", "_git"): (1, _GIT),
    ("cli/compass_pkg/ship_commit_reason.py", "_pre_commit_hook_can_run"): (1, _GIT),
    ("cli/compass_pkg/spec_refresh.py", "_git"): (1, _GIT),
    ("cli/compass_pkg/start_state.py", "_git_changed_paths"): (1, _GIT),
    ("cli/compass_pkg/start_state.py", "_record_path"): (1, _GIT),
    ("cli/compass_pkg/start_state.py", "_tracked_paths"): (1, _GIT),
    ("cli/compass_pkg/migrate_copy_check.py", "_judge.git"): (1, _GIT),
    ("cli/compass_pkg/subtasks.py", "_git"): (1, _GIT),
    ("cli/compass_pkg/tdd.py", "_run_test"): (1, _PROJECT),
    ("cli/compass_pkg/tip_scope.py", "_git"): (1, _GIT),
    ("cli/compass_pkg/worktree_lookup.py", "run_git"): (1, _GIT + "; it leaves out only GIT_ variables"),
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


def test_trc_k2_the_environment_reader_finds_each_way_to_start_a_process():
    source = (
        "import asyncio, os, subprocess as sp\n"
        "from subprocess import run as go, getoutput\n"
        "def held():\n"
        "    env = dict(os.environ, A='1')\n"
        "    sp.run(['x'], env=env)\n"
        "def outer():\n"
        "    env = os.environ.copy()\n"
        "    def inner():\n"
        "        go(['x'], env=env)\n"
        "class Runner:\n"
        "    def start(self):\n"
        "        sp.Popen(['x'], env=None)\n"
        "async def later():\n"
        "    await asyncio.create_subprocess_exec('x')\n"
        "def shells():\n"
        "    os.system('x')\n"
        "    os.popen('x')\n"
        "    getoutput('x')\n"
        "def drops_git():\n"
        "    sp.run(['x'], env={k: v for k, v in os.environ.items() if not k.startswith('GIT_')})\n")
    assert _whole_environment_calls(source) == [
        ("held", 5), ("outer.inner", 9), ("Runner.start", 12), ("later", 14),
        ("shells", 16), ("shells", 17), ("shells", 18), ("drops_git", 20)]


def test_trc_k2_the_environment_reader_passes_a_named_allow_list():
    source = (
        "import os, subprocess\n"
        "KEEP = ('PATH', 'HOME')\n"
        "def kept():\n"
        "    subprocess.run(['x'], env={k: v for k, v in os.environ.items() if k in KEEP})\n"
        "def one_name():\n"
        "    subprocess.run(['x'], env={'PATH': os.environ.get('PATH', '')})\n"
        "def by_key():\n"
        "    subprocess.run(['x'], env={'PATH': os.environ['PATH']})\n"
        "def kept_with_prefix():\n"
        "    env = {k: v for k, v in os.environ.items() if k in KEEP or k.startswith('LC_')}\n"
        "    subprocess.run(['x'], env=env)\n"
        "def passed_on(**kwargs):\n"
        "    subprocess.run(['x'], **kwargs)\n")
    assert _whole_environment_calls(source) == []


def test_trc_k2_no_subprocess_gets_the_whole_environment():
    found, lines = [], {}
    for path in _plugin_files():
        if not path.endswith(".py") or path.startswith("cli/vendor/"):
            continue
        for function, line in _whole_environment_calls((ROOT / path).read_text(encoding="utf-8")):
            lines.setdefault((path, function), []).append(line)
    for key, at in sorted(lines.items()):
        allowed = INHERITS_ENVIRONMENT.get(key, (0, ""))[0]
        if len(at) > allowed:
            found.append(f"{key[0]}:{at[-1]}: {key[1]} gives a subprocess the whole environment "
                         f"({len(at)} calls, {allowed} listed)")
    stale = sorted(key for key, (count, _) in INHERITS_ENVIRONMENT.items()
                   if len(lines.get(key, ())) < count)
    assert not found, "\n".join(found)
    assert not stale, f"these exceptions list more calls than there are; lower them: {stale}"


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
    """The copy is built from HEAD, as the release builds it, so only committed
    work is checked. CI has no `claude` command, so this runs on a machine that
    has one."""
    claude = shutil.which("claude")
    if not claude:
        pytest.skip("the claude command is not installed here; run this test where it is")
    copy = tmp_path / "copy"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build-plugin-copy.py"),
                    "--ref", "HEAD", "--out", str(copy)], check=True, capture_output=True)
    try:
        run = subprocess.run([claude, "plugin", "validate", "--profile", "directory",
                              "--strict", str(copy)], capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        pytest.fail("claude plugin validate gave no answer within 300 seconds")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "found nothing to report" in run.stdout, run.stdout


# The hook scenarios a client observes - a missing or unreadable part, an
# unreadable shared helper - are executable specifications in
# tests/acceptance/hooks/test_hook_refusals.py (ayeo-io/compass-delivery#306).
