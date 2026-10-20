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
#: The options of those verbs that take no value, so no word after one is read as its value.
#: Any other option makes the command not simple.
GIT_FLAGS = frozenset("amend no-edit allow-empty allow-empty-message no-verify signoff all "
                      "quiet verbose no-ff ff-only squash force no-commit dry-run".split())
GIT_LETTERS = frozenset("asnqvf")
#: The `gh` subcommands whose `--title`, `--body`, `--notes`, `-t` and `-b` are the text of an
#: issue, a pull request or a release; `gh pr checkout -b` is a branch, so `checkout` is not here.
GH_SUBS = {"issue": ("create", "edit", "comment"),
           "pr": ("create", "edit", "comment", "review", "merge"),
           "release": ("create", "edit")}
GH_TEXT = ("--title", "--body", "--notes", "-t", "-b")
#: A descriptor copied by a redirect (`2>&1`, `>&2`, `>&-`) names no path. One digit, then
#: a blank, a new line, `;`, `&` or the end: the shell ends the copy at those and no other
#: white space, so `>&2<CR>x` writes a file named `2<CR>x`. A descriptor of two digits is
#: not read.
_DUPLICATE = re.compile(r"(?:[0-9]-?|-)(?=[ \t\n;&]|\Z)")
#: zsh reads `<1-3>`, `<->` and `<-5>` as a glob that matches the names of numbers.
_NUMBER_RANGE = re.compile(r"[0-9]*-[0-9]*>")
_DIGITS = re.compile(r"[0-9]+")


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
    """`(words, targets)` of each command; each word is `(value, flag, bare)`. The flag is
    the strongest `$` it held (0, 1 or 2, see `_dollar`), and `bare` is true when the word
    holds a character outside quotes. An unquoted brace, glob, tilde, `^` or `#` character
    makes the command not simple: the shell expands the word before the command runs. So do
    a zsh number range (`<1-3>`), `>!` and a descriptor of two digits. A command that is only
    a copy of a descriptor (`>&2`) is not simple, because zsh runs `cat` for it."""
    n, i = len(t), 0
    commands, words, targets = [], [], []
    word, flag, bare, redirect, joined = None, 0, False, False, False
    quoted, copied = False, False       # a quote or backslash in the word; a copy in the command

    def end_word():
        nonlocal word, flag, bare, redirect, quoted
        if word is not None:
            (targets if redirect else words).append((word, flag, bare))
            redirect = False
        word, flag, bare, quoted = None, 0, False, False

    def end_command(blank_ok):
        nonlocal words, targets, copied
        end_word()
        # zsh runs `cat` for a command that is only a redirect, even `>&2`.
        if redirect or (copied and not words):
            raise _Refuse
        if words or targets:
            commands.append((words, targets))
        elif not blank_ok:
            raise _Refuse
        words, targets, copied = [], [], False

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
            # The descriptor of `2>` is one unquoted digit. A quoted or escaped digit (`\2>`)
            # is an argument to the shell, and a longer number is a descriptor the gate does
            # not read, so neither is simple.
            if word is not None and _DIGITS.fullmatch(word) and not flag:
                if quoted or len(word) > 1:
                    raise _Refuse
                word = None
            if redirect and word is None:
                raise _Refuse
            end_word()
            after = t[i + 1:i + 2]
            if after == "(" or (c == "<" and after in "<>") or (c == ">" and after == "|"):
                raise _Refuse
            if c == "<" and _NUMBER_RANGE.match(t, i + 1):
                raise _Refuse
            if after == "&":
                found = _DUPLICATE.match(t, i + 2)
                if not found:
                    raise _Refuse
                copied = True
                i = found.end() - 1
            else:
                redirect = True
                i += after == ">" and c == ">"
                if c == ">" and t[i + 1:i + 2] in ("|", "!"):     # zsh `>!f` writes `f`
                    raise _Refuse
        elif c in "#=" and word is None:     # a comment; zsh expands `=name` to a path
            raise _Refuse
        else:
            joined = False
            word = "" if word is None else word
            quoted = quoted or c in "\\'\""
            if c == "\\":
                if i + 1 >= n or t[i + 1] == "\n":
                    raise _Refuse
                word += t[i + 1]
                bare = True
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
                if c in "{}*?[~^#":             # zsh with `extendedglob` reads `^x` and `x#`
                    raise _Refuse
                if c == "$":
                    flag = max(flag, _dollar(t, i))
                word += c
                bare = True
        i += 1
    end_command(True)
    if joined or not commands:
        raise _Refuse
    return commands


def _quoted(w, bare, i):
    """True when `w[i]` can be message text: a word made only of quoted characters, so the
    shell does not expand it, that does not start with `@`."""
    return i < len(w) and not bare[i] and not w[i].startswith("@")


def _git_text(w, bare):
    """The indexes of the message values of `git commit` and the like, or None when an option
    is not on `GIT_FLAGS`: it may take the next word as its value (`--author -m`), or read a
    file or a commit (`-F`, `-c`, `-C`, `-t`, `--file`, `--template`)."""
    marks, i = set(), 2
    while i < len(w) and w[i] != "--":
        word, letters = w[i], w[i][1:]
        if word.startswith("--"):
            message, known = word == "--message", word[2:] in GIT_FLAGS
        elif word.startswith("-") and len(word) > 1:
            message = letters[-1] == "m" and set(letters[:-1]) <= GIT_LETTERS
            known = set(letters) <= GIT_LETTERS
        else:                                   # a ref or a path: judged as a word
            i += 1
            continue
        if message:
            if not _quoted(w, bare, i + 1):
                return None
            marks.add(i + 1)
            i += 1
        elif not known:
            return None
        i += 1
    return frozenset(marks)


def _gh_text(w, bare):
    """The indexes of the title, body and notes values of `gh issue`, `pr` and `release`, or
    None when the command holds any other option."""
    marks, i = set(), 3
    while i < len(w):
        if w[i].startswith("-") and len(w[i]) > 1:
            if w[i] not in GH_TEXT or not _quoted(w, bare, i + 1):
                return None
            marks.add(i + 1)
            i += 1
        i += 1
    return frozenset(marks)


def _text(w, bare):
    """The indexes of the message text of one command, or None when it is not simple."""
    if w[0] in ("git", "gh") and len(w) > 1 and w[1].startswith("-"):
        return None                             # a global option: -C, -c, -R, --git-dir
    if len(w) > 2 and w[0] == "git" and w[1] in GIT_MESSAGES:
        return _git_text(w, bare)
    if len(w) > 2 and w[0] == "gh" and w[2] in GH_SUBS.get(w[1], ()):
        return _gh_text(w, bare)
    return frozenset()


def simple(command):
    """The `Command`s of a simple command, in order, or None."""
    try:
        parsed = _split(command)
        found = []
        for words, targets in parsed:
            values = tuple(value for value, _, _ in words)
            if not values or values[0] not in COMMANDS or words[0][1]:
                return None
            text = _text(values, [bare for _, _, bare in words])
            if text is None:
                return None
            # A `$` is allowed in message text alone, and there only before a name.
            if any(flag and (flag > 1 or i not in text) for i, (_, flag, _) in enumerate(words)):
                return None
            if any(flag for _, flag, _ in targets):
                return None
            found.append(Command(values, text, tuple(value for value, _, _ in targets)))
        return tuple(found)
    except (_Refuse, IndexError):
        return None
