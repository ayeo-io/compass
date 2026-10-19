# compass_pkg.approval_guard_text - which words of one Bash command are text
"""The approval guard (`approval_guard`) does not judge text: the value of a
message option, the arguments of `echo` and `printf`, a search pattern. This
module holds the fixed list of those positions, one table row for each, so a
widening is a visible diff that needs a twin test row.

`text_marks(words)` takes the words of one simple command, name first, and
returns `{index: (judged part, text)}`. The judged part of a word such as
`--note=x` is `--note`; it is empty for a word that is wholly text. A command
this module does not list has no text, and every word of it is judged.

- `echo` and `printf`: every argument.
- `git commit`, `tag`, `merge`, `revert`: `-m`, `--message`, and a cluster such
  as `-am`. `git log`: `--grep`, `-S` and `-G`. `git grep`, `grep`, `egrep`,
  `fgrep` and `rg`: the pattern, which is the first word that is not an option,
  or the value of `-e`. With `-f` or `--file` the pattern is in a file, and every
  other word is a path. An option the tables do not know leaves no text, so a
  word is judged and never skipped by mistake.
- `gh`: `--body`, `-b`, `--title`, `-t`; its heredoc and here-string are text for
  `gh issue`, `gh pr` and `gh release` only. `compass`: `--title`, `--note`,
  `--reason`, `--scope`, `--description`.
- `rg --files` lists files and takes no pattern, so none of its words is text.

Both forms of an option, `--opt value` and `--opt=value`, give the same text. A
value of `--body-file`, `--file` or `-F` is a path and never text. `git` is read
only after `--no-pager` and `-C <dir>`; any other global option leaves no text.
"""
# DEPENDENCY: standard library only. Runs inside hooks/pre-tool.sh, so it keeps to
# syntax that Python 3.10 reads.
from __future__ import annotations

GIT_MESSAGES = ("commit", "tag", "merge", "revert")
#: Commands that read piped text as data. Text piped into any other command is
#: judged, because that command can turn it into a write or a run (`git commit -F -`,
#: `gh api --input -`) or is unknown.
TEXT_SINKS = frozenset("cat tee head tail wc sort uniq cut tr less more grep egrep fgrep rg "
                       "diff pbcopy".split())
#: A sink that is given an option which starts like `--files0-from` reads the files its
#: input names, so it is no sink: `printf '%s\0' <file> | sort --files0-from=-` prints the file.
FILE_LIST_OPTION = "--fil"
#: Commands whose heredoc body and here-string are text. For `git` only the verbs of
#: `GIT_MESSAGES` count, because the body of `git apply` is a patch that writes files. For
#: `gh` only the subcommands of `GH_TEXT_COMMANDS` count, because `gh alias import -` reads
#: its aliases from standard input and an alias that starts with `!` runs a shell.
HEREDOC_TEXT = frozenset(("cat", "tee", "gh", "git", "compass"))
GH_TEXT_COMMANDS = frozenset(("issue", "pr", "release"))
#: Commands that have a text position (`text_marks`). `git` counts for the verbs of
#: `GIT_MESSAGES`, `log` and `grep`.
TEXT_COMMANDS = frozenset(("echo", "printf", "gh", "compass", "grep", "egrep", "fgrep", "rg", "git"))
GH_TEXT = frozenset(("--body", "-b", "--title", "-t"))
COMPASS_TEXT = frozenset(("--title", "--note", "--reason", "--scope", "--description"))
#: Per searcher: the letters of its options without a value, and with one.
SEARCH_LETTERS = {
    "grep": ("abcEFGHhIiJLlnoPqRrsTUuVvwxyZz", "ABCDdm"),
    "rg": ("bcFHhIiLlnNoPqsSuUvwxz0", "ABCEdgjMmrtT"),
    "git grep": ("aIiHhnoLlcqvwzpWEFGPrus", "ABCm"),
}
SEARCHERS = {"grep": "grep", "egrep": "grep", "fgrep": "grep", "rg": "rg"}
SEARCH_FLAGS = frozenset("""--recursive --line-number --ignore-case --files-with-matches
    --files-without-match --count --no-messages --with-filename --no-filename --word-regexp
    --line-regexp --invert-match --only-matching --quiet --silent --extended-regexp
    --fixed-strings --perl-regexp --text --null --hidden --smart-case --no-ignore --follow
    --multiline --no-heading --heading --json --files --stats --no-line-number
    --case-sensitive""".split())
#: Options whose next word is their value: judged, and never the search pattern.
SEARCH_VALUES = frozenset("""--max-count --after-context --before-context --context --include
    --exclude --exclude-dir --exclude-from --include-from --label --directories --devices
    --binary-files --glob --iglob --type --type-not --max-depth --threads --replace --encoding
    --sort --sortr --max-columns --max-filesize --pre --pre-glob --hostname-bin --ignore-file
    --path-separator""".split())


def is_compass(word):
    """The word `compass`, or a path that ends in it, as in `./cli/compass`. A
    longer word that holds the characters (`compass-700`) is not it."""
    return word.rsplit("/", 1)[-1] == "compass"


def command_name(words):
    """The name that selects a command's text positions: an exact name, or
    `compass` for a path that ends in it. A wrapper such as `env`, or any other
    path, selects none."""
    if not words:
        return ""
    return "compass" if is_compass(words[0]) else words[0]


def git_start(words):
    """The index of the subcommand of `git`, after `--no-pager` and `-C <dir>`, or
    -1 when another global option comes first or there is none."""
    i = 1
    while i < len(words):
        if words[i] == "--no-pager":
            i += 1
        elif words[i] == "-C" and i + 1 < len(words):
            i += 2
        else:
            break
    return -1 if i >= len(words) or words[i].startswith("-") else i


#: Words that begin a command without being it: `do ls` runs `ls`.
KEYWORDS = frozenset(("do", "then", "else", "elif", "if", "while", "until", "time", "!", "{"))


def skipped(words):
    """How many leading keywords (`do`, `then`) a command's words have."""
    skip = 0
    while skip < len(words) - 1 and words[skip] in KEYWORDS:
        skip += 1
    return skip


def is_sink(words):
    """True when a pipeline stage reads its input as data: a command of `TEXT_SINKS`
    that is not given an option that reads a list of files."""
    return bool(words) and words[0] in TEXT_SINKS and not any(
        w.startswith(FILE_LIST_OPTION) for w in words[1:])


def heredoc_is_text(words):
    """True when the heredoc body and the here-string of a command (name first) are
    text: the command is in `HEREDOC_TEXT`, and for `git` and `gh` the subcommand is too."""
    name = command_name(words)
    if name not in HEREDOC_TEXT:
        return False
    if name == "git":
        at = git_start(words)
        return at > 0 and words[at] in GIT_MESSAGES
    if name == "gh":
        return len(words) > 1 and words[1] in GH_TEXT_COMMANDS
    return True


def _options(words, start, names):
    """The value of each option in `names`, in both forms."""
    marks, i = {}, start
    while i < len(words):
        opt, equals, value = words[i].partition("=")
        if equals and opt in names:
            marks[i] = (opt, value)
        elif words[i] in names and i + 1 < len(words):
            marks[i + 1] = ("", words[i + 1])
            i += 1
        i += 1
    return marks


def _message_marks(words, start):
    """The text of `-m`, `--message` and a cluster such as `-am`."""
    marks, i = {}, start
    while i < len(words):
        word = words[i]
        if word == "--message" and i + 1 < len(words):
            marks[i + 1] = ("", words[i + 1])
            i += 1
        elif word.startswith("--message="):
            marks[i] = ("--message", word.partition("=")[2])
        elif word.startswith("-") and not word.startswith("--"):
            for j, letter in enumerate(word[1:], 1):
                if letter == "m":
                    if word[j + 1:]:
                        marks[i] = (word[:j + 1], word[j + 1:])
                    elif i + 1 < len(words):
                        marks[i + 1] = ("", words[i + 1])
                        i += 1
                    break
                if letter in "CcFtSu":      # these take a value that is not text
                    break
        i += 1
    return marks


def _search_marks(words, start, family):
    """The pattern of a search command, and the value of `-e`."""
    flags, values = SEARCH_LETTERS[family]
    marks, positional, from_option, unknown, ended = {}, [], False, False, False
    # `rg --files` lists files and takes no pattern: every other word is a path.
    listing = family == "rg" and "--files" in words[start:]
    i = start
    while i < len(words):
        word = words[i]
        if ended or word == "-" or not word.startswith("-"):
            positional.append(i)
        elif word == "--":
            ended = True
        elif word.startswith("--"):
            opt, equals, value = word.partition("=")
            if opt == "--regexp":
                from_option = True
                if equals:
                    marks[i] = (opt, value)
                elif i + 1 < len(words):
                    marks[i + 1] = ("", words[i + 1])
                    i += 1
            elif opt == "--file":
                from_option = True
                i += 0 if equals else 1
            elif not equals and opt in SEARCH_VALUES:
                i += 1
            elif not equals and opt not in SEARCH_FLAGS:
                unknown = True
        else:
            for j, letter in enumerate(word[1:], 1):
                if letter in "ef":
                    from_option = True
                    rest = word[j + 1:]
                    if letter == "e" and rest:
                        marks[i] = (word[:j + 1], rest)
                    elif letter == "e" and i + 1 < len(words):
                        marks[i + 1] = ("", words[i + 1])
                        i += 1
                    elif letter == "f" and not rest:
                        i += 1                  # the next word is a path
                    break
                if letter in values:
                    i += 0 if word[j + 1:] else 1
                    break
                if letter not in flags:
                    unknown = True
                    break
        i += 1
    if positional and not from_option and not unknown and not listing:
        marks[positional[0]] = ("", words[positional[0]])
    return marks


def text_marks(words):
    """`{index: (judged part, text)}` for the words of one command that are text."""
    name = command_name(words)
    if name not in TEXT_COMMANDS:
        return {}
    if name in ("echo", "printf"):
        return {i: ("", w) for i, w in enumerate(words) if i}
    if name == "gh":
        return _options(words, 1, GH_TEXT)
    if name == "compass":
        return _options(words, 1, COMPASS_TEXT)
    if name in SEARCHERS:
        return _search_marks(words, 1, SEARCHERS[name])
    at = git_start(words) if name == "git" else -1
    if at > 0 and words[at] in GIT_MESSAGES:
        return _message_marks(words, at + 1)
    if at > 0 and words[at] == "log":
        marks = _options(words, at + 1, ("--grep", "-S", "-G"))
        for i in range(at + 1, len(words)):
            if words[i][:2] in ("-S", "-G") and len(words[i]) > 2 and i not in marks:
                marks[i] = (words[i][:2], words[i][2:])
        return marks
    if at > 0 and words[at] == "grep":
        return _search_marks(words, at + 1, "git grep")
    return {}
