# compass_pkg.approval_words - read a Bash command only when it is simple
"""The simple-command gate of the approval guard (`approval_guard`).

`simple(command)` returns the words of a command, or None. None means the
guard must judge the whole text of the command, as it did before the gate. The
gate fails closed: every shape it does not name is None.

A command is simple when it is one command, or plain commands joined by `&&`,
`;` or a new line, and each of them:

- starts with a name on `COMMANDS` (no path, no `VAR=` word, no function);
- holds no pipe, `&`, `||`, parenthesis, backtick, heredoc, here-string,
  process substitution, comment or backslash at the end of a line;
- holds no `$` in a word that is not message text, and no `$(`, `${`, `$'`,
  `$"` or backtick in message text.

Message text is the only text the guard does not judge. It is the value of
`-m`, `-am` or `--message` for `git commit`, `tag`, `merge` and `revert`, and
of `--title`, `--body`, `--notes`, `-t` and `-b` for `gh issue`, `pr` and
`release`. A `git` command with `-F`, `--file`, `-c` or `--exec` has none, and
neither has a `git` or `gh` command whose second word is not the verb, as in
`git -C dir commit` or `gh alias set`.

Quotes and backslashes are removed as the shell removes them. A redirect gives
a target, which the guard judges as a word. The time is linear in the text.
"""
# DEPENDENCY: standard library (re). Runs inside hooks/pre-tool.sh, so it keeps to
# syntax that Python 3.10 reads and imports no third-party module.
from __future__ import annotations

import re
from typing import NamedTuple

#: The only command names a simple command may start with. A command with a text
#: position or an exemption is here; any other name is judged by its whole text.
COMMANDS = ("git", "gh", "ls", "wc", "stat", "cat")
GIT_MESSAGES = ("commit", "tag", "merge", "revert")
GH_VERBS = ("issue", "pr", "release")
GH_TEXT = ("--title", "--body", "--notes", "-t", "-b")
#: A descriptor copied by a redirect (`2>&1`, `>&2`, `>&-`) names no path.
_DUPLICATE = re.compile(r"(?:\d+-?|-)(?![^\s;&])")


class Command(NamedTuple):
    words: tuple        # name first; quotes removed
    text: frozenset     # the indexes of the words that are message text
    targets: tuple      # the targets of its redirects


class _Refuse(Exception):
    """The command is not simple."""


def _dollar(t, i):
    """1 for `$` before a name, 2 for any other `$`: `$(`, `${`, `$'`, `$"`, `$$`."""
    return 1 if t[i + 1:i + 2].isalnum() or t[i + 1:i + 2] == "_" else 2


def _split(t):
    """`(words, targets)` of each command; each word is `(value, flag)`, and the flag is
    the strongest `$` it held (0, 1 or 2, see `_dollar`)."""
    n, i = len(t), 0
    commands, words, targets = [], [], []
    word, flag, redirect, joined = None, 0, False, False

    def end_word():
        nonlocal word, flag, redirect
        if word is not None:
            (targets if redirect else words).append((word, flag))
            redirect = False
        word, flag = None, 0

    def end_command(blank_ok):
        nonlocal words, targets
        end_word()
        if redirect:
            raise _Refuse
        if words or targets:
            commands.append((words, targets))
        elif not blank_ok:
            raise _Refuse
        words, targets = [], []

    while i < n:
        c = t[i]
        if c in " \t":
            end_word()
        elif c in "\n;":
            if c == ";" and t[i + 1:i + 2] in (";", "&"):
                raise _Refuse
            end_command(c == "\n")
        elif c == "&":
            if t[i + 1:i + 2] != "&":
                raise _Refuse
            end_command(False)
            joined, i = True, i + 1
        elif c in "|()`":
            raise _Refuse
        elif c in "<>":
            if word is not None and word.isdigit() and not flag:
                word = None                     # the descriptor of `2>`
            if redirect and word is None:
                raise _Refuse
            end_word()
            after = t[i + 1:i + 2]
            if after == "(" or (c == "<" and after in "<>") or (c == ">" and after == "|"):
                raise _Refuse
            if after == "&":
                found = _DUPLICATE.match(t, i + 2)
                if not found:
                    raise _Refuse
                i = found.end() - 1
            else:
                redirect = True
                i += after == ">" and c == ">"
        elif c in "#=" and word is None:     # a comment; zsh expands `=name` to a path
            raise _Refuse
        else:
            joined = False
            word = "" if word is None else word
            if c == "\\":
                if i + 1 >= n or t[i + 1] == "\n":
                    raise _Refuse
                word += t[i + 1]
                i += 1
            elif c == "'":
                end = t.find("'", i + 1)
                if end < 0:
                    raise _Refuse
                word += t[i + 1:end]
                i = end
            elif c == '"':
                i += 1
                while i < n and t[i] != '"':
                    if t[i] == "\\" and t[i + 1:i + 2] in ("$", "`", '"', "\\"):
                        i += 1
                    elif t[i] == "\\" and t[i + 1:i + 2] == "\n":
                        raise _Refuse
                    elif t[i] == "`":
                        raise _Refuse
                    elif t[i] == "$":
                        flag = max(flag, _dollar(t, i))
                    word += t[i]
                    i += 1
                if i >= n:
                    raise _Refuse
            else:
                if c == "$":
                    flag = max(flag, _dollar(t, i))
                word += c
        i += 1
    end_command(True)
    if joined or not commands:
        raise _Refuse
    return commands


def _git_text(w):
    """The indexes of the message of `git commit` and the like; none when the command can
    read its message from a file (`-F`, `--file`, `-c`) or run a command (`--exec`)."""
    marks, i = set(), 2
    while i < len(w):
        word = w[i]
        if word.startswith(("--file", "--exec")):
            return frozenset()
        if word == "--message":
            marks.add(i + 1)
            i += 1
        elif word.startswith("--message="):
            marks.add(i)
        elif word.startswith("-") and not word.startswith("--"):
            for j, letter in enumerate(word[1:], 1):
                if letter in "Fc":
                    return frozenset()
                if letter == "m":
                    if word[j + 1:]:
                        marks.add(i)
                    else:
                        marks.add(i + 1)
                        i += 1
                    break
        i += 1
    return frozenset(marks)


def _gh_text(w):
    """The indexes of the title, body and notes of `gh issue`, `pr` and `release`."""
    marks, i = set(), 2
    while i < len(w):
        option, equals, _ = w[i].partition("=")
        if equals and option in GH_TEXT:
            marks.add(i)
        elif w[i] in GH_TEXT:
            marks.add(i + 1)
            i += 1
        i += 1
    return frozenset(marks)


def _text(w):
    if len(w) > 2 and w[0] == "git" and w[1] in GIT_MESSAGES:
        return _git_text(w)
    if len(w) > 2 and w[0] == "gh" and w[1] in GH_VERBS:
        return _gh_text(w)
    return frozenset()


def simple(command):
    """The `Command`s of a simple command, in order, or None."""
    try:
        parsed = _split(command)
        found = []
        for words, targets in parsed:
            values = tuple(value for value, _ in words)
            if not values or values[0] not in COMMANDS or words[0][1]:
                return None
            text = _text(values)
            # A `$` is allowed in message text alone, and there only before a name.
            if any(flag and (flag > 1 or i not in text) for i, (_, flag) in enumerate(words)):
                return None
            if any(flag for _, flag in targets):
                return None
            found.append(Command(values, text, tuple(value for value, _ in targets)))
        return tuple(found)
    except (_Refuse, IndexError):
        return None
