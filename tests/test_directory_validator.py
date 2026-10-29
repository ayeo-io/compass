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

The validator runs on the directory's servers only, so these tests check the
rules its report states, not the validator itself.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

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


# The hook scenarios a client observes - a missing or unreadable part, an
# unreadable shared helper - are executable specifications in
# tests/acceptance/hooks/test_hook_refusals.py (ayeo-io/compass-delivery#306).
