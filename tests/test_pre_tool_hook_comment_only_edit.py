"""An Edit that changes only comments of Python or YAML needs no failing test.

The pre-tool hook refused a change to a comment in a production file, as it
refuses any change to code. It now proves from the file on disk that an Edit of
a `.py`, `.yml` or `.yaml` file changed only comments, docstrings or layout, and
lets it through with no issue lookup. The proof is a comparison: the hook reads
the file once, applies the Edit in memory, and compares the syntax tree (Python)
or the YAML events before and after. Every doubt keeps today's verdict, which is
a refusal when no failing test is on record: a file over 1 MiB, a file that does
not parse, a pragma, a hidden character, a check that fails or runs too long.
Shell and every other language are not covered.

The hook is run for real on a scratch project. The timing tests carry the
`serial` marker: a wall-clock bound fails at random when workers share the CPU.

Scenario ids: see hooks-comment-only-edits-and-prose/acceptance-criteria.md.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from test_session_issue import _issue

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "pre-tool.sh"

PY = "cli/compass_pkg/routing.py"
CI = ".github/workflows/ci.yml"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _project(tmp_path, *, issue=True, globs=None):
    """A project that opted in. With `issue` it has one assessed issue with no
    failing test on record, so a code edit is refused."""
    root = tmp_path / "proj"
    (root / ".compass" / "work").mkdir(parents=True)
    if issue:
        _issue(root, "issue-a", red=False)
        (root / ".compass" / "current-task").write_text("issue-a\n")
    if globs is not None:
        (root / ".compass" / "config.yml").write_text(
            f"version: 1.0.0\nenforcement:\n  code_globs: {globs}\n")
    return root


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


def _env(root, path=None):
    env = {k: v for k, v in os.environ.items()
           if k not in ("COMPASS_ISSUE", "CLAUDE_CODE_SESSION_ID")
           and not k.startswith("GIT_")}
    env["CLAUDE_PROJECT_DIR"] = str(root)
    if path is not None:
        env["PATH"] = path
    return env


def _call(root, payload, *, path=None, timeout=60):
    started = time.monotonic()
    result = subprocess.run(["bash", str(HOOK)], input=json.dumps(payload),
                            capture_output=True, text=True, env=_env(root, path),
                            cwd=str(root), timeout=timeout)
    return time.monotonic() - started, result


def _edit(root, rel, old, new, *, text=None, replace_all=False, path=None,
          timeout=60):
    """Write `text` to `rel` when given, then run an Edit of it. Returns the
    completed hook process."""
    if text is not None:
        _write(root, rel, text)
    tool_input = {"file_path": str(root / rel), "old_string": old,
                  "new_string": new}
    if replace_all:
        tool_input["replace_all"] = True
    return _call(root, {"tool_name": "Edit", "tool_input": tool_input},
                 path=path, timeout=timeout)[1]


def _allowed(r):
    assert r.returncode == 0, r.stderr
    assert r.stderr == "", r.stderr


def _refused(r, code="no-red-on-record"):
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert r.stderr.rstrip().endswith(f"[{code}]"), r.stderr


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

ROUTING = ('# Retry three times.\n'
           'def route(issue):\n'
           '    """Return the route."""\n'
           '    return issue.slug  # the slug names the folder\n')


@pytest.mark.parametrize("old, new", [
    pytest.param("# Retry three times.", "# Retry up to three times.",
                 id="a-comment-line"),
    pytest.param('"""Return the route."""', '"""Return the route for an issue."""',
                 id="a-docstring"),
    pytest.param("# Retry three times.\ndef route",
                 "# Retry three times.\n\ndef route", id="a-blank-line"),
    pytest.param("# the slug names the folder", "# the slug is the folder name",
                 id="a-trailing-comment"),
    pytest.param("return issue.slug", "return issue.slug ",
                 id="whitespace-after-code"),
])
def test_python_comment_docstring_blank_line_and_trailing_comment_edits_are_allowed(
        tmp_path, old, new):
    """Scenario id: `TRC-001` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _allowed(_edit(root, PY, old, new, text=ROUTING))


@pytest.mark.parametrize("text, old, new", [
    pytest.param('url = "http://x.example/#top"\n', "#top", "#bottom",
                 id="text-after-a-hash-inside-a-string"),
    pytest.param("# retries = 3\n", "# retries = 3", "retries = 3",
                 id="turns-a-comment-into-code"),
    pytest.param("retries = 3\n", "retries = 3", "# retries = 3",
                 id="turns-code-into-a-comment"),
    pytest.param("retries = 3  # how often\n", "retries = 3  # how often",
                 "retries = 4  # how many", id="a-comment-and-a-code-line"),
    pytest.param("# cache\n@cache\ndef f(): pass\n", "# cache\n@cache",
                 "# memo\n@lru_cache", id="a-comment-and-a-decorator-line"),
    pytest.param("x = 1 \\\n+ 2\n", "+ 2", "# + 2",
                 id="a-line-a-backslash-joins-to-code"),
])
def test_python_edit_that_is_more_than_a_comment_is_refused(tmp_path, text, old, new):
    """Scenario id: `TRC-002` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit(root, PY, old, new, text=text))


@pytest.mark.parametrize("text, old, new", [
    pytest.param('TEMPLATE = """\nHello\n"""\n', "Hello", "Goodbye",
                 id="a-triple-quoted-string-a-name-holds"),
    pytest.param('f"""Run {NAME}."""\nx = 1\n', "Run", "Stop",
                 id="an-f-string-first-statement"),
    pytest.param('def f():\n    """Doc."""\n    """More."""\n', "More.", "Other.",
                 id="a-second-string-statement"),
    pytest.param('def f():\n    """Doc."""\n    pass\n', "def f():",
                 "def f():\n    x = 1",
                 id="a-docstring-with-a-statement-above-it"),
])
def test_change_to_a_string_that_is_not_a_docstring_is_refused(tmp_path, text, old, new):
    """Scenario id: `TRC-043` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit(root, PY, old, new, text=text))


@pytest.mark.parametrize("mention", [
    "print(route.__doc__)", "inspect.getdoc(route)", "help(route)",
    "import doctest", 'exec("pass")', 'eval("1")'])
def test_docstring_change_is_refused_when_the_file_reads_docstrings_at_run_time(
        tmp_path, mention):
    """Scenario id: `TRC-044` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    text = f'def route(issue):\n    """Return the route."""\n    return 1\n\n{mention}\n'

    _refused(_edit(root, PY, '"""Return the route."""',
                   '"""Return the route for an issue."""', text=text))


@pytest.mark.parametrize("text, old, new", [
    pytest.param("x = f()\n", "x = f()", "x = f()  # type: ignore", id="type-ignore"),
    pytest.param("x = f()\n", "x = f()", "x = f()  # noqa", id="noqa"),
    pytest.param("x = f()\n", "x = f()", "x = f()  # nosec", id="nosec"),
    pytest.param("x = f()\n", "x = f()", "# fmt: off\nx = f()", id="fmt-off"),
    pytest.param("y = 1  # pragma: no cover\n", "no cover", "no branch",
                 id="pragma-no-cover"),
    pytest.param("y = 1  # pylint: disable=a\n", "=a", "=b", id="pylint"),
    pytest.param("y = 1\n", "y = 1", "# mypy: ignore-errors\ny = 1", id="mypy"),
    pytest.param("#!/usr/bin/env python3\n", "python3", "python3.12", id="shebang"),
    pytest.param("# -*- coding: utf-8 -*-\n", "utf-8", "latin-1", id="encoding"),
    pytest.param("y = 1  # NOQA\n", "y = 1", "y = 2", id="code-beside-a-pragma"),
])
def test_comment_that_carries_a_pragma_shebang_or_encoding_is_code(tmp_path, text, old, new):
    """Scenario id: `TRC-045` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit(root, PY, old, new, text=text))


@pytest.mark.parametrize("character", [
    pytest.param("‮", id="bidirectional-control"),
    pytest.param("​", id="zero-width"),
    pytest.param("\x00", id="nul-byte"),
    pytest.param("\x0c", id="form-feed"),
])
def test_comment_edit_that_adds_a_hidden_control_character_is_refused(tmp_path, character):
    """Scenario id: `TRC-046` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit(root, PY, "# Retry three times.",
                   "# Retry three times." + character,
                   text="# Retry three times.\nx = 1\n"))


def test_write_of_a_python_file_is_refused_even_when_only_a_comment_differs(tmp_path):
    """Scenario id: `TRC-003` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    _write(root, PY, "# Retry three times.\ndef route(issue):\n    return 1\n")
    _, r = _call(root, {"tool_name": "Write", "tool_input": {
        "file_path": str(root / PY),
        "content": "# Retry up to three times.\ndef route(issue):\n    return 1\n"}})

    _refused(r)


@pytest.mark.parametrize("text, old, new", [
    pytest.param("def route(issue):\n    return 1\n", "# no such line",
                 "# another line", id="old-text-is-not-in-the-file"),
    pytest.param("def (:\n# a comment\n", "# a comment", "# another",
                 id="file-does-not-parse-before"),
    pytest.param("x = 1  # a comment\n", "x = 1", "x = (",
                 id="result-does-not-parse"),
])
def test_edit_that_cannot_be_proved_comment_only_is_refused(tmp_path, text, old, new):
    """Scenario id: `TRC-004` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit(root, PY, old, new, text=text))


def test_replace_all_edit_that_reaches_code_is_refused(tmp_path):
    """Scenario id: `TRC-047` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit(root, PY, "retries", "attempts", replace_all=True,
                   text="# retries\nretries = 3\n"))


# ---------------------------------------------------------------------------
# YAML
# ---------------------------------------------------------------------------

def test_yaml_comment_edit_is_allowed(tmp_path):
    """Scenario id: `TRC-005` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _allowed(_edit(root, CI, "# Run the tests", "# Run the whole test suite",
                   text="# Run the tests\nrun: pytest -q\n"))


@pytest.mark.parametrize("text, old, new", [
    pytest.param("run: |\n  # build the docs\n  make docs\n", "# build the docs",
                 "# build docs", id="a-run-block"),
    pytest.param('name: "a # b"\n', "a # b", "a # c", id="a-quoted-string"),
])
def test_yaml_change_inside_a_block_scalar_is_refused(tmp_path, text, old, new):
    """Scenario id: `TRC-006` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit(root, CI, old, new, text=text))


@pytest.mark.parametrize("text, old, new", [
    pytest.param("a: &base 1\nb: *base\n", "&base", "&root", id="renames-an-anchor"),
    pytest.param("a: &base 1\nb: *base\n", "*base", "1",
                 id="replaces-an-alias-by-its-value"),
    pytest.param("a: &x {k: 1}\nb:\n  <<: *x\n  k: 1\n", "<<: *x\n  ", "",
                 id="removes-a-merge-key"),
    pytest.param("a: 1\nb: 2\n", "a: 1\nb: 2", "b: 2\na: 1",
                 id="swaps-the-order-of-two-keys"),
    pytest.param("a: 1\n", "a: 1", "a: 1\na: 2", id="adds-a-duplicate-key"),
    pytest.param("a: 1\n", "a: 1", "a: !!str 1", id="adds-a-tag"),
    pytest.param("a: 1\n", "a: 1", 'a: "1"', id="quotes-a-number-into-a-string"),
    pytest.param("# no\na: 1\na: 2\n", "# no", "# yes", id="a-duplicate-already-there"),
])
def test_yaml_change_that_keeps_the_data_but_changes_the_nodes_is_refused(
        tmp_path, text, old, new):
    """Scenario id: `TRC-048` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit(root, CI, old, new, text=text))


# ---------------------------------------------------------------------------
# Shell and other languages: judged as before
# ---------------------------------------------------------------------------

SHELL = "hooks/example.sh"


@pytest.mark.parametrize("text, old, new", [
    pytest.param("cat <<'EOF'\n# text\nEOF\n", "# text", "# other", id="heredoc-body"),
    pytest.param('echo "a\n# b\nc"\n', "# b", "# d", id="quoted-string"),
    pytest.param("x=$(\n# in\necho a\n)\n", "# in", "# out", id="substitution"),
    pytest.param('cat <<< "# x"\n', "# x", "# y", id="here-string"),
    pytest.param("case $x in\n  a#b) ;;\nesac\n", "a#b", "a#c", id="case-pattern"),
    pytest.param("y=${v#pre}\n", "pre", "post", id="parameter-trim"),
    pytest.param("n=$#\n", "n=$#", "n=$1", id="argument-count"),
    pytest.param("n=${#items[@]}\n", "items", "other", id="length-expansion"),
    pytest.param("echo a#b\n", "a#b", "a#c", id="word-with-a-hash"),
    pytest.param("[[ $x =~ # ]]\n", "=~ #", "=~ @", id="test-with-a-hash-pattern"),
    pytest.param("echo a \\\n# b\n", "# b", "# c", id="after-a-continuation"),
    pytest.param("n=0  # start\n", "# start", "# begin", id="comment-after-code"),
    pytest.param("#!/usr/bin/env bash\n", "bash", "sh", id="shebang"),
    pytest.param("# Count the files.\nn=0\n", "# Count the files.",
                 "# Count the files in the folder.", id="whole-line-comment"),
])
def test_shell_edit_that_is_more_than_a_whole_line_comment_is_refused(tmp_path, text, old, new):
    """Scenario id: `TRC-008` in hooks-comment-only-edits-and-prose/acceptance-criteria.md

    Shell is not covered: every edit of a declared shell file keeps today's
    verdict, a comment edit included."""
    root = _project(tmp_path, globs='["hooks/*.sh"]')

    _refused(_edit(root, SHELL, old, new, text=text))


def test_shell_lexer_error_refuses_the_edit(tmp_path):
    """Scenario id: `TRC-051` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path, globs='["hooks/*.sh"]')

    _refused(_edit(root, SHELL, "# note", "# a note",
                   text="# note\necho 'unclosed\n"))


@pytest.mark.parametrize("rel, old, new", [
    pytest.param("src/app.js", "// retry", "// retry twice", id="javascript"),
    pytest.param("src/main.go", "// Run", "// Run the server", id="go"),
    pytest.param("db/migrations/001_add.sql", "-- add column", "-- add the column",
                 id="sql"),
    pytest.param("infra/main.tf", "# region", "# the region", id="terraform"),
    pytest.param("Dockerfile", "# base image", "# the base image", id="dockerfile"),
])
def test_comment_edit_in_an_uncovered_language_is_refused(tmp_path, rel, old, new):
    """Scenario id: `TRC-009` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit(root, rel, old, new, text=f"{old}\n"))


# ---------------------------------------------------------------------------
# A check that cannot run, and the issue lookup
# ---------------------------------------------------------------------------

def _python_that_fails_the_check(tmp_path):
    """A folder with a `python3` that exits 9 for the comment-only check and runs
    the real one for every other reader. Returns a PATH that holds it first."""
    shim = tmp_path / "shim"
    shim.mkdir()
    script = shim / "python3"
    script.write_text(
        "#!/bin/sh\n"
        'for a in "$@"; do\n'
        '  case "$a" in *comment_only_edit*) exit 9 ;; esac\n'
        "done\n"
        f'exec "{sys.executable}" "$@"\n')
    script.chmod(0o755)
    return f"{shim}:{os.environ['PATH']}"


def test_comment_check_that_cannot_run_leaves_the_verdict_unchanged(tmp_path):
    """Scenario id: `TRC-010` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    r = _edit(root, PY, "# Retry three times.", "# Retry up to three times.",
              text=ROUTING, path=_python_that_fails_the_check(tmp_path))

    _refused(r)


def _counting_python(tmp_path):
    """A folder with a `python3` that logs its arguments and runs the real one.
    Returns the PATH that holds it first and the log's path."""
    shim = tmp_path / "count-shim"
    shim.mkdir()
    log = tmp_path / "python3.log"
    log.write_text("")
    script = shim / "python3"
    script.write_text(f'#!/bin/sh\necho "$*" >> "{log}"\nexec "{sys.executable}" "$@"\n')
    script.chmod(0o755)
    return f"{shim}:{os.environ['PATH']}", log


def test_comment_check_starts_only_for_an_edit_that_names_old_and_new_text(tmp_path):
    """Scenario id: `TRC-010` in hooks-comment-only-edits-and-prose/acceptance-criteria.md

    The check starts one python3 process, and only for an Edit of a Python or
    YAML file that holds an old and a new text: any other call has nothing to
    compare, so the hook starts no process for it and judges it as before."""
    root = _project(tmp_path)
    _write(root, PY, ROUTING)
    path, log = _counting_python(tmp_path)
    marker = "comment_only_edit"

    def started(tool_input):
        log.write_text("")
        _call(root, {"tool_name": "Edit", "tool_input": tool_input}, path=path)
        return marker in log.read_text()

    target = str(root / PY)
    assert not started({"file_path": target})
    assert not started({"file_path": target, "old_string": "# Retry three times."})
    assert not started({"file_path": str(root / "notes.txt"),
                        "old_string": "a", "new_string": "b"})
    assert started({"file_path": target, "old_string": "# Retry three times.",
                    "new_string": "# Retry up to three times."})


def _path_without_python(tmp_path):
    """A PATH that holds every tool of /usr/bin and /bin except python."""
    bare = tmp_path / "barebin"
    bare.mkdir()
    for d in ("/usr/bin", "/bin"):
        for name in os.listdir(d):
            if name.startswith("python") or (bare / name).exists():
                continue
            (bare / name).symlink_to(os.path.join(d, name))
    return str(bare)


def test_missing_python3_refuses_a_comment_edit(tmp_path):
    """Scenario id: `TRC-052` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    r = _edit(root, PY, "# Retry three times.", "# Retry up to three times.",
              text=ROUTING, path=_path_without_python(tmp_path))

    _refused(r, "python-missing")


def test_comment_only_edit_needs_no_assessed_issue(tmp_path):
    """Scenario id: `TRC-011` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path, issue=False)

    _allowed(_edit(root, PY, "# Retry three times.", "# Retry up to three times.",
                   text=ROUTING))


def test_damaged_manifest_lets_nothing_through_except_comment_edits(tmp_path):
    """Scenario id: `TRC-053` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    (root / ".compass" / "work" / "issue-a" / "manifest.yml").write_text(
        "key: [unclosed\n  - : :\n")
    text = "def route(issue):\n    return issue.slug\n"

    _refused(_edit(root, PY, "return issue.slug", "return issue.name", text=text))
    # A comment edit needs no issue at all, so a damaged manifest does not
    # matter to it either.
    _allowed(_edit(root, PY, "def route", "# a note\ndef route", text=text))


def test_edit_of_a_symbolic_link_is_refused(tmp_path):
    """Scenario id: `TRC-004` in hooks-comment-only-edits-and-prose/acceptance-criteria.md

    A symbolic link is not followed: the Edit cannot be proved to change the
    file the person sees at that path."""
    root = _project(tmp_path)
    _write(root, "cli/compass_pkg/real.py", ROUTING)
    link = root / "cli" / "compass_pkg" / "link.py"
    link.symlink_to(root / "cli" / "compass_pkg" / "real.py")

    _refused(_edit(root, "cli/compass_pkg/link.py", "# Retry three times.",
                   "# Retry up to three times."))


# ---------------------------------------------------------------------------
# Mutation proofs
#
# Most scenarios above describe a call that the hook refused before this change
# and still refuses. Such a test passes before the change, so it does not show
# that it can fail. Each case below plants one fault in a copy of the check or
# of the hook, and shows that the hook then LETS THROUGH the call that its twin
# refuses: break the rule, and the twin fails.
#
# Two twins have no fault of one changed line, and here is why. A Write is
# refused (the scenario about a Write) by two separate facts: the check reads
# `old_string` and `new_string`, which a Write does not have. The warning for a
# missing pointer file, and the refusal for a damaged manifest, are compared as
# exact text, or end in the refusal that every other test needs.
# ---------------------------------------------------------------------------

def _mutant(tmp_path, module=None, hook=None):
    """A copy of the hook and of the package, each with its `old` text replaced
    by its `new` once. Returns the script's path."""
    tree = tmp_path / "mutant"
    (tree / "hooks").mkdir(parents=True)
    (tree / "cli").mkdir()
    for name in ("scripts", "governance"):
        (tree / name).symlink_to(ROOT / name)
    (tree / "cli" / "vendor").symlink_to(ROOT / "cli" / "vendor")
    shutil.copytree(ROOT / "cli" / "compass_pkg", tree / "cli" / "compass_pkg",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for path, edits in ((tree / "cli" / "compass_pkg" / "comment_only_edit.py", module),
                        (tree / "hooks" / "pre-tool.sh", hook)):
        text = (ROOT / "cli" / "compass_pkg" / "comment_only_edit.py"
                if path.suffix == ".py" else HOOK).read_text(encoding="utf-8")
        for old, new in (edits or {}).items():
            assert text.count(old) == 1, f"{path.name} does not hold {old!r} once"
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
    (tree / "hooks" / "pre-tool.sh").chmod(0o755)
    return tree / "hooks" / "pre-tool.sh"


def _run_mutant(hook, root, rel, old, new, *, replace_all=False, path=None,
                timeout=60):
    started = time.monotonic()
    tool_input = {"file_path": str(root / rel), "old_string": old,
                  "new_string": new, "replace_all": replace_all}
    proc = subprocess.Popen(
        ["bash", str(hook)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, env=_env(root, path), cwd=str(root),
        start_new_session=True)
    try:
        out, err = proc.communicate(json.dumps(
            {"tool_name": "Edit", "tool_input": tool_input}), timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, 9)
        proc.communicate()
        return None, "timed out", time.monotonic() - started
    return proc.returncode, err, time.monotonic() - started


MODULE_FAULTS = [
    pytest.param(
        {'    if touches_pragma(old_lines) or touches_pragma(new_lines):\n'
         '        return no("pragma")\n': ""},
        PY, "x = f()\n", "x = f()", "x = f()  # type: ignore",
        id="TRC-045-a-pragma-is-not-code"),
    pytest.param(
        {'    if adds_hidden_character(new_lines):\n'
         '        return no("hidden-character")\n': ""},
        PY, "# Retry three times.\nx = 1\n", "# Retry three times.",
        "# Retry three times.‮", id="TRC-046-a-hidden-character-is-allowed"),
    pytest.param(
        {'    return not (_DOCSTRING_READERS.search(before)\n'
         '                or _DOCSTRING_READERS.search(after))': "    return True"},
        PY, 'def route(issue):\n    """Return the route."""\n    return 1\n\nprint(route.__doc__)\n',
        '"""Return the route."""', '"""Return the route for an issue."""',
        id="TRC-044-a-docstring-reader-is-ignored"),
    pytest.param(
        {'        if ast.dump(tree_before) == ast.dump(tree_after):\n'
         '            return True': "        if True:\n            return True"},
        PY, "# retries = 3\n", "# retries = 3", "retries = 3",
        id="TRC-002-the-trees-are-not-compared"),
    pytest.param(
        {'    if count == 0 or (count > 1 and not replace_all):\n'
         '        return None\n': '    if count == 0:\n        return text\n'
                                  '    if count > 1 and not replace_all:\n        return None\n'},
        PY, "def route(issue):\n    return 1\n", "# no such line", "# another line",
        id="TRC-004-an-old-text-that-is-not-found-passes"),
    pytest.param(
        {'    except Exception:           # a syntax error, a null byte, a tree too deep\n'
         '        return False': '    except Exception:\n        return True'},
        PY, "def (:\n# a comment\n", "# a comment", "# another",
        id="TRC-004-a-file-that-does-not-parse-passes"),
    pytest.param(
        {'    return text.replace(old, new) if replace_all else text.replace(old, new, 1)':
         '    return text.replace(old, new, 1)'},
        PY, "# retries\nretries = 3\n", "retries", "attempts",
        id="TRC-047-replace-all-reaches-only-the-first"),
    pytest.param(
        {'            if key in frame[4]:\n                return False\n':
         '            if False:\n                return False\n'},
        CI, "# no\na: 1\na: 2\n", "# no", "# yes",
        id="TRC-048-a-duplicate-key-passes"),
    pytest.param(
        {'            signature.append(("scalar", event.anchor, event.tag, event.implicit,\n'
         '                              event.value))':
         '            signature.append(("scalar", event.value))'},
        CI, "a: 1\n", "a: 1", "a: !!str 1",
        id="TRC-048-a-tag-is-not-compared"),
    pytest.param(
        {'            if expanded > MAX_ALIAS_NODES or not done(size, None):':
         '            if not done(size, None):'},
        ".github/workflows/bomb.yml", None, "# comment", "# another",
        id="TRC-049-an-alias-bomb-passes"),
    pytest.param(
        {'LANGUAGES = {".py": "python", ".yml": "yaml", ".yaml": "yaml"}':
         'LANGUAGES = {".py": "python", ".yml": "yaml", ".yaml": "yaml", ".sh": "shell"}',
         'def judge(': 'def _shell_same(b, a):\n    old, new = changed_lines(b, a)\n'
                       '    return all(l.lstrip().startswith("#") for l in old + new)\n\n\n'
                       'def judge(',
         '    same = (python_same if language == "python" else yaml_same)(before, after)':
         '    same = (python_same if language == "python" else yaml_same if language == '
         '"yaml" else _shell_same)(before, after)'},
        "hooks/example.sh", "cat <<'EOF'\n# text\nEOF\n", "# text", "# other",
        id="TRC-008-shell-is-classified-by-its-hash-lines"),
]


@pytest.mark.parametrize("module, rel, text, old, new", MODULE_FAULTS)
def test_a_fault_in_the_check_lets_through_the_call_its_twin_refuses(
        tmp_path, module, rel, text, old, new):
    """Supports the baseline scenarios named in each id: with the fault planted
    the hook allows what the scenario's test says it refuses."""
    root = _project(tmp_path, globs='["hooks/*.sh"]')
    _write(root, rel, _bomb() if text is None else text)
    hook = _mutant(tmp_path, module=module, hook=(
        {'    /*.py|/*.yml|/*.yaml) ;;': '    /*.py|/*.yml|/*.yaml|/*.sh) ;;'}
         if rel.endswith(".sh") else None))

    # The replace_all Edit names its old text twice and asks for every one.
    status, err, _ = _run_mutant(hook, root, rel, old, new,
                                 replace_all=(old == "retries"))

    assert status == 0, (status, err)


def test_without_the_alarm_a_hostile_yaml_file_runs_past_six_seconds(tmp_path):
    """Supports `TRC-049` in hooks-comment-only-edits-and-prose/acceptance-criteria.md:
    PyYAML needs about 90 seconds for 100000 opening brackets, so without the
    alarm the hook is still running when the test stops it."""
    root = _project(tmp_path)
    _write(root, ".github/workflows/deep.yml", "# comment\n" + "[" * 100000 + "\n")
    hook = _mutant(tmp_path, module={'    signal.alarm(params["alarm"])\n': ""})

    status, _, seconds = _run_mutant(hook, root, ".github/workflows/deep.yml",
                                     "# comment", "# another", timeout=9)

    assert status is None and seconds >= 9, (status, seconds)


def test_without_the_size_limit_a_file_over_one_mebibyte_is_read(tmp_path):
    """Supports `TRC-013` in hooks-comment-only-edits-and-prose/acceptance-criteria.md:
    the limit is what keeps a file of 2 MiB (here comment lines, which parse
    fast) from being compared, and the budget is its second guard."""
    root = _project(tmp_path)
    _write(root, "cli/compass_pkg/huge.py", _comment_lines(2097152))
    hook = _mutant(
        tmp_path,
        module={"MAX_FILE_BYTES = 1048576": "MAX_FILE_BYTES = 10485760"},
        hook={"COST_EDIT_KB_PY=3000": "COST_EDIT_KB_PY=0"})

    status, err, _ = _run_mutant(hook, root, "cli/compass_pkg/huge.py",
                                 "# the first line", "# the 1st line")

    assert status == 0, (status, err)


def test_without_the_budget_check_a_file_past_the_budget_is_parsed(tmp_path):
    """Supports `TRC-050` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    # Comment lines, which parse fast, so the fault shows without the alarm.
    _write(root, "cli/compass_pkg/big.py", "# comment\n" + "#\n" * (900 * 512))
    hook = _mutant(tmp_path, module={"    if charge > remaining:\n"
                                     '        return no("over-budget")\n': ""})

    status, err, _ = _run_mutant(hook, root, "cli/compass_pkg/big.py",
                                 "# comment", "# another")

    assert status == 0, (status, err)


def test_without_the_symbolic_link_rule_a_link_is_followed(tmp_path):
    """Supports `TRC-004` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    _write(root, "cli/compass_pkg/real.py", ROUTING)
    (root / "cli" / "compass_pkg" / "link.py").symlink_to(
        root / "cli" / "compass_pkg" / "real.py")
    hook = _mutant(tmp_path, module={
        "os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK": "os.O_RDONLY | os.O_NONBLOCK"})

    status, err, _ = _run_mutant(hook, root, "cli/compass_pkg/link.py",
                                 "# Retry three times.", "# Retry up to three times.")

    assert status == 0, (status, err)


def test_a_hook_that_allows_when_the_check_fails_lets_through_the_edit_its_twin_refuses(
        tmp_path):
    """Supports `TRC-010` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    _write(root, PY, ROUTING)
    hook = _mutant(tmp_path, hook={
        '    WORK_USED=$((WORK_USED + alarm * 1000000))\n    return 1\n':
        '    WORK_USED=$((WORK_USED + alarm * 1000000))\n    return 0\n'})

    status, err, _ = _run_mutant(hook, root, PY, "# Retry three times.",
                                 "# Retry up to three times.",
                                 path=_python_that_fails_the_check(tmp_path))

    assert status == 0, (status, err)


def test_a_hook_that_skips_the_python_check_lets_a_missing_python_through(tmp_path):
    """Supports `TRC-052` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    _write(root, PY, ROUTING)
    hook = _mutant(tmp_path, hook={
        '    compass_reader_failed "comment-only check" 127\n': "    return 0\n"})

    status, err, _ = _run_mutant(hook, root, PY, "# Retry three times.",
                                 "# Retry up to three times.",
                                 path=_path_without_python(tmp_path))

    assert status == 0, (status, err)


@pytest.mark.parametrize("hook_edit, rel", [
    pytest.param(
        {"      evals/*/seed/*) return 1 ;;": "      evals/*) return 1 ;;"},
        "evals/judge.py", id="TRC-024-evals-outside-seed-is-exempt"),
    pytest.param(
        {'    case "$rel" in\n      evals/*/seed/*) return 1 ;;':
         '    case "${TARGET:-$rel}" in\n      *evals/*/seed/*) return 1 ;;'},
        "evals/scenarios/example/seed/../../../../cli/compass_pkg/routing.py",
        id="TRC-022-a-dot-dot-step-borrows-the-exemption"),
    pytest.param(
        {"      evals/*/seed/*) return 1 ;;": "      evals/*/seed/*|examples/*) return 1 ;;"},
        "examples/bdd-adapters/pytest-bdd/src/reset_password.py",
        id="TRC-024-examples-is-exempt"),
    pytest.param(
        {"      evals/*/seed/*) return 1 ;;": "      evals/*/seed/*|*/vendor/*) return 1 ;;"},
        "cli/vendor/yaml/__init__.py", id="TRC-024-vendored-code-is-exempt"),
    pytest.param(
        {"      evals/*/seed/*) return 1 ;;": "      evals/*/seed/*|.github/scripts/*) return 1 ;;"},
        ".github/scripts/check_mutation_runner.py",
        id="TRC-024-ci-scripts-are-exempt"),
    pytest.param(
        {"      evals/*/seed/*) return 1 ;;": "      evals/*/seed/*|*/examples/*|*/seed/*) return 1 ;;"},
        "src/examples/helpers.py", id="TRC-024-src-examples-is-exempt"),
    pytest.param(
        {"      evals/*/seed/*) return 1 ;;": "      evals/*/seed/*|*/seed/*) return 1 ;;"},
        "db/seed/load.py", id="TRC-024-db-seed-is-exempt"),
])
def test_a_wider_path_exemption_lets_through_the_edit_its_twin_refuses(
        tmp_path, hook_edit, rel):
    """Supports `TRC-022` and `TRC-024` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    hook = _mutant(tmp_path, hook=hook_edit)

    status, err, _ = _run_mutant(hook, root, rel, "x = 1", "x = 2")

    assert status == 0, (status, err)


def test_a_hook_that_does_not_fall_back_lets_the_pointer_to_a_missing_issue_stop_the_edit(
        tmp_path):
    """Supports `TRC-018` in hooks-comment-only-edits-and-prose/acceptance-criteria.md:
    with no fallback the edit is refused for another reason, so the twin that
    expects the most recent issue to judge it fails."""
    root = _project(tmp_path)
    (root / ".compass" / "current-task").write_text("issue-zzz\n")
    _write(root, PY, ROUTING)
    hook = _mutant(tmp_path, hook={
        '  TASK_DIR="$(ls -dt "$WORK_DIR"/*/ 2>/dev/null | head -n1 || true)"':
        '  TASK_DIR=""'})

    status, err, _ = _run_mutant(hook, root, PY, "return issue.slug",
                                 "return issue.name")

    assert status == 2 and "[no-red-on-record]" not in err, (status, err)


# ---------------------------------------------------------------------------
# Size and time
# ---------------------------------------------------------------------------

def _valid_python(lines):
    body = "".join(f"def f{i}(a):\n    # note {i}\n    return a + {i}\n"
                   for i in range(lines // 3))
    return "# the first line\n" + body


@pytest.mark.serial
def test_comment_only_edit_of_a_5000_line_file_is_allowed_within_3_seconds(tmp_path):
    """Scenario id: `TRC-012` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    _write(root, "cli/compass_pkg/big.py", _valid_python(5000))
    seconds, r = _call(root, {"tool_name": "Edit", "tool_input": {
        "file_path": str(root / "cli/compass_pkg/big.py"),
        "old_string": "# the first line", "new_string": "# the 1st line"}})

    _allowed(r)
    assert seconds < 3, f"the hook took {seconds:.1f} s"


def test_file_over_one_mebibyte_keeps_the_old_verdict(tmp_path):
    """Scenario id: `TRC-013` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    text = "# the first line\n" + "x = 1\n" * ((2097152 - 17) // 6)
    text += "#" * (2097152 - len(text.encode()))
    assert len(text.encode()) == 2097152

    _refused(_edit(root, "cli/compass_pkg/huge.py", "# the first line",
                   "# the 1st line", text=text))


def _comment_lines(size):
    text = "# the first line\n" + "#\n" * ((size - 17) // 2)
    text += "#" * (size - len(text.encode()))
    assert len(text.encode()) == size
    return text


@pytest.mark.serial
def test_largest_file_the_check_reads_is_read_within_six_seconds(tmp_path):
    """Scenario id: `TRC-050` in hooks-comment-only-edits-and-prose/acceptance-criteria.md

    The file is the largest the check reads. Its charge is by size, at the rate
    of the slowest shape, so it can be past the work budget: the check then
    does not parse it and the Edit is judged as before. Either verdict is
    right. What the scenario bounds is the time."""
    root = _project(tmp_path)
    _write(root, "cli/compass_pkg/comments.py", _comment_lines(1048576))
    seconds, r = _call(root, {"tool_name": "Edit", "tool_input": {
        "file_path": str(root / "cli/compass_pkg/comments.py"),
        "old_string": "# the first line", "new_string": "# the 1st line"}})

    assert r.returncode in (0, 2), (r.returncode, r.stderr)
    if r.returncode == 2:
        _refused(r)
    assert seconds < 6, f"the hook took {seconds:.1f} s"


@pytest.mark.serial
def test_a_file_of_comments_within_the_budget_is_read_and_allowed(tmp_path):
    """Scenario id: `TRC-050` in hooks-comment-only-edits-and-prose/acceptance-criteria.md

    Half of the largest file is within the budget: it is parsed and allowed."""
    root = _project(tmp_path)
    _write(root, "cli/compass_pkg/comments.py", _comment_lines(524288))
    seconds, r = _call(root, {"tool_name": "Edit", "tool_input": {
        "file_path": str(root / "cli/compass_pkg/comments.py"),
        "old_string": "# the first line", "new_string": "# the 1st line"}})

    _allowed(r)
    assert seconds < 6, f"the hook took {seconds:.1f} s"


def _hook_copy(tmp_path):
    """A copy of the hook that prints the work it had counted when it ended, in
    a folder that links the folders the hook reads. Returns the script's path."""
    tree = tmp_path / "hook-copy"
    (tree / "hooks").mkdir(parents=True)
    for name in ("cli", "scripts", "governance"):
        (tree / name).symlink_to(ROOT / name)
    text = HOOK.read_text(encoding="utf-8")
    old = "\nTARGET_BYTES_LIMIT=2048\n"
    assert old in text
    text = text.replace(
        old, '\ntrap \'echo "WORK_USED=$WORK_USED" >&2\' EXIT\n' + old[1:], 1)
    path = tree / "hooks" / "pre-tool.sh"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def _charged(r) -> int:
    import re
    found = re.findall(r"WORK_USED=(\d+)", r.stderr)
    assert found, r.stderr
    return int(found[-1])


@pytest.mark.serial
@pytest.mark.parametrize("rel, text", [
    pytest.param("cli/compass_pkg/dense.py",
                 "# comment\n" + "a\n" * (700 * 512), id="python-statements-of-two-bytes"),
    pytest.param("cli/compass_pkg/calls.py",
                 "# comment\n" + "f(a, b)\n" * (700 * 128), id="python-calls"),
    pytest.param(".github/workflows/dense.yml",
                 "# comment\nx: [" + "1," * (200 * 512) + "1]\n", id="yaml-flow-numbers"),
    pytest.param(".github/workflows/maps.yml",
                 "# comment\n" + "- a: 1\n  b: 2\n" * (200 * 73), id="yaml-list-of-maps"),
])
def test_the_charged_work_of_an_edit_matches_the_measured_time(tmp_path, rel, text):
    """Supports `TRC-050` in hooks-comment-only-edits-and-prose/acceptance-criteria.md:
    the cost table is in microseconds, so the seconds the hook takes are at most
    three times the work it charged, and at least a fifth of it. The first bound
    is the one that protects: a hook that costs more than it was charged can pass
    its limit. A faster machine takes less than it was charged, which is safe."""
    root = _project(tmp_path)
    _write(root, rel, text)
    started = time.monotonic()
    r = subprocess.run(
        ["bash", str(_hook_copy(tmp_path))],
        input=json.dumps({"tool_name": "Edit", "tool_input": {
            "file_path": str(root / rel), "old_string": "# comment",
            "new_string": "# another"}}),
        capture_output=True, text=True, env=_env(root), cwd=str(root), timeout=60)
    seconds = time.monotonic() - started

    assert r.returncode == 0, (r.returncode, r.stderr[-400:])
    ratio = seconds / (_charged(r) / 1e6)
    print(f"{rel}: {seconds:.2f} s for {_charged(r)} charged: {ratio:.2f}")
    assert 0.2 <= ratio <= 3.0, f"{seconds:.2f} s for {_charged(r)} charged: {ratio:.2f}"


@pytest.mark.serial
@pytest.mark.parametrize("rel, text", [
    pytest.param("cli/compass_pkg/big.py", "# comment\n" + "a\n" * (900 * 512),
                 id="python-900-KiB"),
    pytest.param(".github/workflows/big.yml",
                 "# comment\nx: [" + "1," * (300 * 512) + "1]\n", id="yaml-300-KiB"),
])
def test_an_edit_whose_charge_is_past_the_budget_is_not_parsed(tmp_path, rel, text):
    """Supports `TRC-050` in hooks-comment-only-edits-and-prose/acceptance-criteria.md:
    the charge is computed from the size before any parse, and a file past the
    budget keeps the old verdict at once."""
    root = _project(tmp_path)
    _write(root, rel, text)
    seconds, r = _call(root, {"tool_name": "Edit", "tool_input": {
        "file_path": str(root / rel), "old_string": "# comment",
        "new_string": "# another"}})

    _refused(r)
    assert seconds < 1.5, f"the hook took {seconds:.1f} s: the file was parsed"


def _bomb():
    lines = ["# comment", "a0: &a0 [x]"]
    for i in range(1, 30):
        lines.append(f"a{i}: &a{i} [{', '.join([f'*a{i - 1}'] * 10)}]")
    return "\n".join(lines) + "\n"


@pytest.mark.serial
@pytest.mark.parametrize("rel, text", [
    pytest.param("cli/compass_pkg/nested.py", "# comment\nx = " + "(" * 100000 + "\n",
                 id="100000-nested-parentheses"),
    pytest.param(".github/workflows/bomb.yml", _bomb(), id="alias-bomb"),
    pytest.param(".github/workflows/deep.yml", "# comment\n" + "[" * 100000 + "\n",
                 id="100000-opening-square-brackets"),
])
def test_file_that_exhausts_the_parser_is_refused_within_six_seconds(tmp_path, rel, text):
    """Scenario id: `TRC-049` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)
    assert len(text.encode()) < 1048576
    _write(root, rel, text)
    seconds, r = _call(root, {"tool_name": "Edit", "tool_input": {
        "file_path": str(root / rel), "old_string": "# comment",
        "new_string": "# another"}})

    _refused(r)
    assert seconds < 6, f"the hook took {seconds:.1f} s"
