"""The simple-command gate of issue `hooks-stop-refusing-harmless-work`:
`compass_pkg.approval_words.simple` reads a Bash command as words only when the
whole command is simple, and returns None for everything else, so the approval
guard (`approval_guard`) judges that command by its whole text.

Scenario: `TRC-067`. The gate fails closed. A command is simple when it is one
command, or plain commands joined by `&&`, `;` or a new line, and every
command name is on `COMMANDS`. Each row of `NOT_SIMPLE` is a construct the
adversarial review used to read a protected file through a text position. Each
must return None. A row that returns a command is a bypass.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))


def _simple(command):
    from compass_pkg import approval_words
    return approval_words.simple(command)


def _one(command):
    found = _simple(command)
    assert found is not None and len(found) == 1, (command, found)
    return found[0]


# --- what is simple ---------------------------------------------------------------------------

def test_a_chain_of_plain_commands_is_simple():
    found = _simple("git status && ls docs; wc -l x\ncat y")
    assert [c.words[0] for c in found] == ["git", "ls", "wc", "cat"]


def test_quotes_and_escapes_are_removed_as_the_shell_removes_them():
    command = _one("""ls 'a b' "c d" e\\ f g"h"'i'""")
    assert command.words == ("ls", "a b", "c d", "e f", "ghi")


def test_a_redirect_gives_a_target_and_a_copied_descriptor_gives_none():
    command = _one("ls docs > out.txt 2>&1")
    assert command.words == ("ls", "docs") and command.targets == ("out.txt",)
    assert _one("ls < in.txt").targets == ("in.txt",)
    assert _one("ls >> log").targets == ("log",)


def test_a_dollar_name_is_allowed_only_in_a_message():
    assert _one('git commit -m "fix $HOME handling"').text == frozenset({3})
    assert _one(r'git commit -m "costs \$(5) and \`x\`"').text == frozenset({3})


# --- the text positions -----------------------------------------------------------------------

@pytest.mark.parametrize("command, text", [
    ('git commit -m "a b"', {3}),
    ("git commit -am msg", {3}),
    ("git commit -mmsg", {2}),
    ("git commit --message=msg", {2}),
    ("git commit --message msg", {3}),
    ("git tag -m msg v1", {3}),
    ("git merge -m msg topic", {3}),
    ("git revert -m msg abc", {3}),
    ("gh pr create --title t --body b", {4, 6}),
    ("gh issue comment 5 -b b", {5}),
    ("gh pr create --title=t --body=b", {3, 4}),
    ("gh release create v1 --notes n", {5}),
])
def test_the_text_positions_are_the_values_of_a_message_option(command, text):
    assert _one(command).text == frozenset(text)


@pytest.mark.parametrize("command", [
    "git commit -m a -F file",
    "git commit -m a --file=file",
    "git commit -m a --file file",
    "git commit -m a -c abc",
    "git commit -m a -aF file",
    "git commit -m a --exec=x",
    "git -C dir commit -m a",
    "git -c alias.commit=x commit -m a",
    "git log -m a",
    "git stash -m a",
    "gh pr create --body-file f",
    "gh api repos/o/r -f body=a",
    "gh alias set x y",
    "gh extension exec x",
    "gh -R o/r pr create --body b",
    "ls -m a",
    "cat --message a",
])
def test_a_command_outside_the_list_has_no_text_position(command):
    assert _one(command).text == frozenset()


# --- what is not simple -----------------------------------------------------------------------

NOT_SIMPLE = [
    # a variable or a substitution outside a message, or a substitution in one
    "echo P; cat $_", 'cat "$p"', "cat ${p}", "cat $(echo P)", "cat `echo P`",
    'git commit -m "$(cat f)"', 'git commit -m "`cat f`"', 'git commit -m "${x:=y}"',
    'git commit -m "$((1+1))"', 'git commit -m "$\'a\'"', 'git commit -m "$[1]"',
    "git commit -m $(cat f)", 'gh pr create --body "$(cat f)"', "cat $x", "cat $", "cat \"$\"",
    # a quoting that decodes
    "cat $'a'", "cat $\"a\"", "cat <<$'E\\x4fF'\nx\nEOF\ncat\nE\\x4fF",
    # a heredoc or a here-string
    "cat <<EOF\nx\nEOF", "cat <<'EOF'\nx\nEOF", "cat <<-EOF\nx\nEOF", "cat <<< x",
    # a body and a delimiter that are themselves plain commands
    "cat <<ls\nls\nls", "cat <<-ls\ngit status\nls", "cat <<'cat'\nls\ncat", "git commit -F - <<git\nls\ngit",
    # a process substitution, a pipe, a group
    "cat <(ls)", "ls >(cat)", "ls | cat", "ls |& cat", "ls || ls", "(ls)", "{ ls; }", "ls; (ls)",
    # a name or a state that can change what a command is
    "eval 'git(){ cat \"$3\"; }'; git commit -m P", "f() { :; }", "git() { :; }; git status",
    "function git { :; }", "alias git=cat", "PATH=$PWD/bin:$PATH git commit -m P",
    "FOO=1 git status", "FOO=1", "./compass --note P", "compass --note P", "./git status",
    "/usr/bin/git status", "sh f", "bash f", "source f", ". f", "env git status", "exec ls",
    "command git status", "xargs ls", "echo hi", "printf x", "grep x f", "sort f", "sed p f",
    "cd /tmp && ls", "mystery", "make", "python3 -c x",
    # a shape the reader does not follow
    "ls &", "ls & ls", "ls &> f", "ls >& f", "ls >(", "ls # c", "ls;; ls", "ls &&", "&& ls",
    "ls >", "ls <", "ls > ; ls", "ls\\\nx", "git commit -m 'a", 'git commit -m "a', "ls \\",
    # a backslash and a new line join two lines in the shell and must not be read as one word
    "ls approval-req\\\nuests", "git commit -m a\\\nb", 'git commit -m "a\\\nb"',
    # zsh expands a word that starts with = to the path of a command
    "ls =cat", "cat =ls", "ls a =cat",
    "", "   ", ";", "ls ; ;", "ls ;& ls", "ls <> f", "ls >| f",
]


@pytest.mark.parametrize("command", NOT_SIMPLE)
def test_a_command_that_is_not_simple_is_not_read(command):
    assert _simple(command) is None, command


def test_the_command_names_are_the_fixed_list():
    from compass_pkg import approval_words
    assert set(approval_words.COMMANDS) == {"git", "gh", "ls", "wc", "stat", "cat"}


def test_a_long_command_is_read_in_linear_time():
    command = "ls " + "a" * 100000 + ' && git commit -m "' + "b " * 50000 + '"'
    started = time.perf_counter()
    assert _simple(command) is not None
    assert time.perf_counter() - started < 1.0
