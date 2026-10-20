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
    ('git commit -am "msg"', {3}),
    ("git commit -asm 'msg'", {3}),
    ('git commit --message "msg"', {3}),
    ('git commit -a --amend --no-edit -m "msg" -- file', {6}),
    ('git commit -m "a" -- -m', {3}),
    ("git tag -m 'msg' v1", {3}),
    ('git merge --no-ff -m "msg" topic', {4}),
    ('git revert -m "1" abc', {3}),
    ('gh pr create --title "t" --body "b"', {4, 6}),
    ("gh issue comment 5 -b 'b'", {5}),
    ('gh release create v1 --notes "n"', {5}),
    ('gh pr merge 5 -t "t" -b "b"', {5, 7}),
])
def test_the_text_positions_are_the_quoted_values_of_a_message_option(command, text):
    assert _one(command).text == frozenset(text)


@pytest.mark.parametrize("command", [
    "git log -m a",
    "git stash -m a",
    "git status -s",
    "git commit-tree abc",
    "gh api repos/o/r -f body=a",
    "gh alias set x y",
    "gh extension exec x",
    "gh pr checkout 1 -b branch",
    "gh pr view 5 -t x",
    "ls -m a",
    "cat --message a",
])
def test_a_command_outside_the_list_has_no_text_position(command):
    assert _one(command).text == frozenset(), command


@pytest.mark.parametrize("command", [
    # a text value that is not one quoted word
    "git commit -m msg", "git commit -am msg", "git commit -mmsg", "git commit --message=msg",
    'git commit --message="msg"', "git commit --message msg", "git tag -m msg v1",
    "git commit -m x'y'", 'git commit -m "x"y', "git commit -m", 'git commit -m "x" -m',
    'gh pr create --title t --body "b"', 'gh pr create --title=t --body "b"',
    'gh pr create --title "t" --body=b', 'gh pr create --title "t" --body "@file"',
    'git commit -m "@file"',
    # brace, glob and tilde expansion happen before the command runs
    'git commit -m {a,b}', 'git commit -m "x" {a,b}', 'git commit -m x{,\\ -F\\ f}',
    'git commit -m "x"{,-F}', "git commit -m *", "git commit -m ?", "git commit -m [a]",
    "git commit -m ~", 'git commit -m "x" ~/f', "ls a/*", "ls ~", "ls {a,b}", "cat f?", "ls [ab]",
    "git commit -m 'x' --message ~",
    # an option the gate does not know may take the next word as its value
    "git commit -m x -F f", 'git commit -m "x" --file=f', 'git commit -m "x" --file f',
    'git commit -m "x" -c abc', 'git commit -m "x" -aF f', 'git commit -m "x" --exec=x',
    'git commit --pathspec-from-file -m "x"', 'git commit --author -m "x"', 'git commit -t -m "x"',
    'git commit -C -m "x"', 'git commit -m "x" -C HEAD', 'git commit -m "x" --template=f',
    'git commit -m "x" --reuse-message=HEAD', 'git commit -m "x" --reedit-message=HEAD',
    'git tag -m "x" -F f v1', 'git merge -m "x" -X theirs main', 'git commit -m "x" -S',
    'gh pr create --title "t" --body-file f', 'gh pr create --title "t" -F f',
    'gh pr create --draft --title "t"', 'gh release create v1 --repo -t "x"',
    'gh issue create --title "t" --template f',
    # a global option before the verb changes the directory or the configuration
    'git -C dir commit -m "x"', 'git -c alias.commit=x commit -m "x"', "git --git-dir=d status",
    'gh -R o/r pr create --body "b"', "gh --version",
])
def test_a_text_value_must_be_a_quoted_word(command):
    assert _simple(command) is None, command


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
    # a copy of a descriptor ends only at a blank, a new line, `;` or `&`: the shell reads any
    # other white space character as part of a file name
    *[f"ls >&2{c}x" for c in ("\r", "\x0c", "\x0b", "\x85", "\xa0", " ", " ")],
    *[f"ls 2>&1{c}" for c in ("\r", "\x0c", "\x0b", "\x85", "\xa0", " ", " ")],
    "ls >&1\r", "ls >&-\xa0", "ls >&22", "ls >&2x", "ls >&2-x",
    # zsh writes `>&1-` to a file named `1-`, where bash moves the descriptor
    "ls >&2-", "ls 2>&1-", "ls -2>&1- dir/sub a-b 0<t2", "ls >&2- ; ls",
    # zsh reads a number range as a glob
    "cat x <1-3> -l", "ls <->", "wc<-5> -1", "ls <1-3>x", "ls <3->",
    # zsh with `extendedglob` reads `^x` and `x#` as a glob
    "ls ^x", "ls a#", "cat a#b", "ls ^",
    # zsh runs `cat` for a command that is only a redirect, a copy of a descriptor too
    ">&2", "2>&1", "ls; >&2", "ls\n>&2", "ls && >&2", "ls ; 2>&1 ;",
    # zsh writes `>!f` to `f`, and `>>!f` too
    "ls >!f", "ls >>!f", "ls >! f",
    # a quoted or escaped digit is an argument to the shell, and a long number is a descriptor
    "ls \\2>f", "ls '2'>f", 'ls "2">f', "ls 11>f", "ls 22>&1", "ls 007>f",
]


@pytest.mark.parametrize("command", NOT_SIMPLE)
def test_a_command_that_is_not_simple_is_not_read(command):
    assert _simple(command) is None, command


def test_the_module_docstring_lists_every_shape_the_gate_refuses():
    """The docstring is where a maintainer looks for what the gate refuses, so each
    refusal the review added must be named there."""
    from compass_pkg import approval_words
    doc = " ".join(approval_words.__doc__.split())
    for shape in ("`^x`", "`a#`", "`<1-3>`", "`>!`", "`>&2`", "`>&2-`", "`\\2>`",
                  "two digits"):
        assert shape in doc, (shape, doc)


def test_the_command_names_are_the_fixed_list():
    from compass_pkg import approval_words
    assert set(approval_words.COMMANDS) == {"git", "gh", "ls", "wc", "stat", "cat"}


def test_a_long_command_is_read_in_linear_time():
    command = "ls " + "a" * 100000 + ' && git commit -m "' + "b " * 50000 + '"'
    started = time.perf_counter()
    assert _simple(command) is not None
    assert time.perf_counter() - started < 1.0
