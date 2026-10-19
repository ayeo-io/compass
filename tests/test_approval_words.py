"""The reader of issue `hooks-stop-refusing-harmless-work`:
`compass_pkg.approval_words.read` turns a Bash command into pipelines of simple
commands, and holds syntax only (no protected name, no policy).

No scenario owns these cases; they fix the contract that the guard builds on
(`Command`, `Pipeline`, `Unreadable`, `MAX_DEPTH`). The module does not exist
before the change, so each test imports it inside the test and fails with an
import error until it does. Each case states what the reader returns for one
construct:

- a `;` and a `&&` split a command, and a pipe gives two stages of one pipeline;
- quotes are removed, and ANSI-C quoting is kept in `raws`;
- `$(...)`, backticks, `<(...)` and `>(...)` give nested pipelines, also inside
  a double-quoted string and an unquoted heredoc body;
- a quoted heredoc is literal and has no nested pipeline; `<<-` strips tabs;
  `<<<` fills `herestring`;
- redirect forms give a target, and `2>&1` gives none;
- a comment ends a line, and leading `VAR=x` words are `assigns`;
- an open quote, an open `$(`, a heredoc with no end and 33 nested levels raise
  `Unreadable`, and 20,000 characters are read in under a second.
"""
from __future__ import annotations

import dataclasses
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))


def _mod():
    from compass_pkg import approval_words
    return approval_words


def _read(text):
    return _mod().read(text)


def _commands(text):
    """Every command of the top-level pipelines, in source order."""
    return [c for p in _read(text) if not p.nested for c in p.commands]


def _nested(text):
    return [p for p in _read(text) if p.nested]


# --- splitting --------------------------------------------------------------------------------

def test_a_semicolon_and_double_ampersand_split_a_command_into_pipelines():
    found = _read("echo a; echo b && echo c || echo d")
    assert [p.commands[0].words for p in found] == [
        ("echo", "a"), ("echo", "b"), ("echo", "c"), ("echo", "d")]
    assert all(len(p.commands) == 1 and not p.nested for p in found)


def test_a_newline_and_a_single_ampersand_split_a_command_into_pipelines():
    found = _read("sleep 1 & echo a\necho b")
    assert [p.commands[0].words for p in found] == [("sleep", "1"), ("echo", "a"), ("echo", "b")]


def test_a_pipe_gives_two_stages_of_one_pipeline():
    (pipeline,) = _read("cat x | grep y")
    assert [c.words for c in pipeline.commands] == [("cat", "x"), ("grep", "y")]
    (pipeline,) = _read("cat x |& grep y")
    assert len(pipeline.commands) == 2


def test_parentheses_split_a_subshell_into_commands():
    assert [c.words for c in _commands("(cd x; ls)")] == [("cd", "x"), ("ls",)]


# --- quotes -------------------------------------------------------------------------------------

def test_quotes_are_removed_from_the_words():
    (command,) = _commands("echo \"a b\" 'c d' e\\ f")
    assert command.words == ("echo", "a b", "c d", "e f")


def test_ansi_c_quoting_is_kept_in_raws():
    (command,) = _commands(r"echo $'a\tb'")
    assert command.words[1] == r"a\tb"
    assert command.raws[1] == r"$'a\tb'"
    assert len(command.raws) == len(command.words)


# --- substitutions ------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "echo $(cat x)",
    "echo `cat x`",
    "diff <(cat x) y",
    "tee >(cat x)",
    'echo "a $(cat x) b"',
    "cat <<EOF\n$(cat x)\nEOF",
])
def test_a_substitution_gives_a_nested_pipeline(text):
    inner = _nested(text)
    assert [c.words for p in inner for c in p.commands] == [("cat", "x")], text
    assert any(not p.nested for p in _read(text)), "the outer command is not nested"


def test_a_quoted_heredoc_is_literal_and_has_no_nested_pipeline():
    (command,) = _commands("cat <<'EOF'\n$(cat x)\nEOF")
    assert command.heredoc_literal is True
    assert "$(cat x)" in command.heredoc
    assert not _nested("cat <<'EOF'\n$(cat x)\nEOF")


def test_an_unquoted_heredoc_is_not_literal():
    (command,) = _commands("cat <<EOF\nbody\nEOF")
    assert command.heredoc_literal is False
    assert command.heredoc.splitlines() == ["body"]


def test_a_dash_heredoc_strips_tabs():
    (command,) = _commands("cat <<-EOF\n\tbody\n\tEOF\n")
    assert command.heredoc.splitlines() == ["body"]


def test_a_here_string_fills_herestring():
    (command,) = _commands('cat <<<"hello there"')
    assert command.herestring == "hello there"
    assert command.heredoc is None


# --- redirects, comments, assignments -------------------------------------------------------------

@pytest.mark.parametrize("text, target", [
    ("echo x > out", "out"),
    ("echo x >> out", "out"),
    ("echo x 2> err", "err"),
    ("echo x &> all", "all"),
    ("cat < in", "in"),
])
def test_a_redirect_gives_its_target(text, target):
    (command,) = _commands(text)
    assert [t for _, t in command.redirects] == [target], text
    assert command.words[0] in ("echo", "cat")
    assert target not in command.words


def test_a_file_descriptor_copy_has_no_target():
    (command,) = _commands("make 2>&1")
    assert command.redirects == ()
    assert command.words == ("make",)


def test_a_comment_ends_a_line():
    found = _read("echo a # a comment\necho b")
    assert [p.commands[0].words for p in found] == [("echo", "a"), ("echo", "b")]
    assert not any("comment" in w for p in found for c in p.commands for w in c.words)


def test_leading_assignments_are_assigns_and_not_words():
    (command,) = _commands("FOO=bar BAZ=1 cmd arg")
    assert command.assigns == ("FOO=bar", "BAZ=1")
    assert command.words == ("cmd", "arg")


def test_a_command_is_a_frozen_value():
    (command,) = _commands("ls")
    with pytest.raises(dataclasses.FrozenInstanceError):
        command.words = ("rm",)


# --- what the reader gives up on --------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    'echo "an open quote',
    "echo 'an open quote",
    "echo $(cat x",
    "echo `cat x",
    "cat <<EOF\nbody with no end",
    "echo " + "$(" * 33 + "x" + ")" * 33,
])
def test_the_reader_raises_unreadable(text):
    with pytest.raises(_mod().Unreadable):
        _read(text)


def test_the_depth_bound_is_32_and_a_shallow_nesting_reads():
    assert _mod().MAX_DEPTH == 32
    found = _read("echo " + "$(" * 5 + "x" + ")" * 5)
    assert sum(p.nested for p in found) == 5


@pytest.mark.serial
def test_twenty_thousand_characters_are_read_in_under_a_second():
    text = "echo " + "word " * 4000 + "; echo $(cat x) | wc -l"
    assert len(text) >= 20000
    started = time.perf_counter()
    found = _read(text)
    assert time.perf_counter() - started < 1.0
    assert len(found) >= 2
