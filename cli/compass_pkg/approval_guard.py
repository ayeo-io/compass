# compass_pkg.approval_guard - the pre-tool checks on approval state
r"""Decide whether the agent's tool call touches approval state it must not
(ADR-068 decision 10, ADR-069 decisions 4 and 8). `hooks/pre-tool.sh` calls
`check` with the hook input and blocks with the code it returns.

- **How a Bash command is read.** `approval_words.read` splits it into
  simple commands, and the guard judges each command name, redirect target
  and argument, except text. A word is judged by its substring, as before.
  A command the reader cannot read (an open quote, nesting over 32 levels)
  is judged by its whole text, as before.
  - Text is the value of a message option (`-m` and `--message` of `git
    commit`, `tag`, `merge` and `revert`; `--body`, `-b`, `--title` and `-t`
    of `gh`; `--title`, `--note`, `--reason`, `--scope` and `--description`
    of `compass`), every argument of `echo` and `printf`, the pattern of
    `grep`, `rg` and `git grep` and the value of `--grep`, `-S` and `-G` of
    `git log`, and the heredoc body and here-string of `cat`, `tee`, `gh`
    (`issue`, `pr` and `release` only), `git` (the message verbs) and
    `compass`. Text is not judged, unless a later stage of its pipeline is
    not one of `TEXT_SINKS` (`cat tee head tail wc sort uniq cut tr less
    more grep egrep fgrep rg diff pbcopy`, and none given an option that
    starts `--fil`), which sends it to be judged by its whole text. The
    heredoc body or here-string of any other command is judged.
  - A substitution (`$(...)`, backticks, `<(...)`) is read as commands whose
    words are judged. What it prints is judged too, as the word it stands
    for, unless it stands in a text position of its outer command and of
    every command above it (`_text_substitutions`).
  - A bare path argument of `ls`, `wc`, `stat`, `du`, `test` or `[` may name
    a request folder, and one of those or of `cat`, `head`, `tail`, `grep`,
    `rg`, `diff`, `chmod` (a mode that keeps the execute bit) or `git log`,
    `show`, `diff`, `blame`, `status`, `ls-files` or `add` may name the
    prompt hook script. `git mv` and `git rm` may not. `ls`
    alone may name a folder strictly above the configuration folder, with no
    `-R`, `-d` or glob. No exemption holds in a pipe, `$(...)`, backticks
    or `<(...)`, for a `VAR=` word, an option such as `--output=<path>`, or
    the word after `-f`, `--file`, `--files0-from`, `--output`, `--pre` or
    `--exec`.
  - Text that one call writes to a file and then runs is judged, and the
    refusal names the script (`approval_guard_scripts`). A script that one
    call writes and another runs is not followed.
  - A Bash word that holds a glob or brace character in the name of a
    protected folder is judged as before.
- **The auto-memory folder.** Read, Grep, Edit and Write skip the
  transcript tests for `<configuration folder>/projects/<one
  folder>/memory/...`, after the path is joined to the call's `cwd`,
  normalised and case-folded, and its symbolic links are resolved
  (`in_memory_folder`). A path with a glob or brace character, a Grep glob
  with a `..` segment, and a path that leaves the folder are not in it. A
  Bash command that names the folder is refused. A symbolic link inside the
  folder that a Grep over it follows is not detected.
- **Request files.** Edit or Write on a file under an issue's
  `approval-requests/`, or a Bash word that names that folder or the
  prompt hook's entry point, gives `approval-request-protected`.
- **Delegation files.** Edit or Write under `.compass/delegations/`, Read or
  Grep that names that folder by path or by Grep glob, or a Bash word that
  names it, gives `delegation-protected`. The folder holds the salt and hash
  of the code that confirms a g5 delegation.
- **The session transcript.** Claude Code writes a hook's block message to
  the session's transcript file (measured on Claude Code 2.1.301), and the
  block message is where the person sees the code that confirms a g5
  delegation. So `transcript-protected` is given for:
  - Read or Grep on the transcript's folder, inside it, or on any folder
    above it, with `~` and `$HOME` expanded and a relative path joined to
    the call's `cwd`; a Grep with no path searches its `cwd`;
  - Read, Grep, Edit or Write, or a Bash word, that names a
    `.claude*/projects` folder, a configuration folder directly under the
    home folder (`~/.claude*`, ending there) or `CLAUDE_CONFIG_DIR`. A
    project's own `.claude` folder does not count;
  - a Bash word that names the transcript's folder or a folder above it,
    such as `~`, once `~`, `~<name>` and `$HOME` are expanded. A word with a
    glob counts by the folder before the glob.
- **A delegated approval's caller.** A Bash command is a delegated approval
  when one of its words is `approve` and one is `--delegated`, a prefix of
  it of five characters or more, or `--delegated=...`; the earlier rule,
  `evidence approve` beside any word that starts `--del`, also counts. Only
  judged words count, so a commit message that names `--delegated` is text.
  The words are read twice: as the shell splits the command, and again with
  every word that holds a space split once more, to any depth, so `bash -c`,
  `eval` and a pipe into `sh` are read too. Either reading must name the
  caller with
  `--as`, and every `--as` must be the agent Claude Code reports: `main`
  only when the input has neither `agent_type` nor `agent_id`, otherwise the
  exact `agent_type`, plugin prefix included. An `agent_id` with no or an
  empty `agent_type` is refused, because Claude Code's own internal agents
  report that shape (the host measurement on Claude Code 2.1.300, ADR-069).
  Anything else gives `delegation-caller-mismatch`. So does any word without
  white space that holds `--as` and is neither `--as` nor `--as=...`, such
  as `--as${IFS}compass:architect`, `$IFS--as`, `--asmain`, `--assume-yes`
  or `--as-main`: the shell can turn it into `--as`, and the CLI keeps the
  last value. A word with white space is read again as its parts. Quotes
  are removed first, so `"--as"` and `--a''s` count as `--as`.
- **A glob that reaches the delegation files.** A Grep glob, or a Bash word
  with `*`, `?` or `[`, is tested with `fnmatch` against sample paths in
  `.compass/delegations` and against an ordinary path of the same shape
  (`.compass/zz`, or a file `file.yml` inside it). It gives `delegation-protected`
  when it matches a sample and not the ordinary path. Refused: `d*/*`,
  `deleg*/*`, `**/confirm-*`, `deleg?tions`, `**/DL-*.yml`. Accepted, as
  they pick everything: `*`, `**/*`, `*.yml`, `**/*.yml`, `.compass/*`,
  `**/*.md`, `src/*.py`. The samples are written relative to the Grep path
  (so a path that cannot reach the folder, such as `src`, is accepted) or to
  the call's `cwd` for Bash, where `./` is removed and an absolute word is
  read under `cwd`. The line is a heuristic: a glob that picks the
  delegation files together with others, such as `**/*l*.yml`, passes, and
  the 64-bit code keeps the stored hash useless. The glob is read as the
  shell reads it: `[^` counts as `[!`, a POSIX class counts as `?`, and a
  backslash and newline are removed. A Grep glob is also split on commas.
  A delegated approval with a brace expansion in a space-free word is
  refused, because the shell expands `--a{s=main,s=x}` to two `--as=` words.
  A bracket expression that holds a class, a collating symbol or an
  equivalence class (`[[:lower:]x]`, `[[.d.]]`) is read as one character.
- **ANSI-C quoting and braces in an evidence command.** A command that names
  `evidence` (a word `evidence`, a quoted word that holds `compass evidence`,
  or a `--delegated` flag) is refused, with the word named, when a word holds
  ANSI-C quoting with an escape (`$'--a\x73'`, `$'appro\x76e'`) or a brace
  expansion (`--{delegated,x}`, `appr{ove,x}`), whether or not `--delegated`
  shows. The guard does not decode either spelling. `$'--as'` with no escape
  is read as the quoted text. A value with a space or no comma, such as
  `--note '{"a": 1}'`, passes; a compact value with a comma is refused, in
  any `compass evidence` command. A command with the word `compass` (or an
  escape-spelled `compass` in command position) and a word of ANSI-C quoting
  with an escape is refused even when `evidence` is spelled with escapes too:
  `compass $'\x65vidence' $'appro\x76e'` runs `evidence approve`.
- **Limit: a text-matching guard cannot follow what the shell, a spelling or
  an interpreter builds at run time** (variables, command substitution, a
  glob that expands against a file the agent wrote, such as `appro?e` or
  `--a?`, encodings, `python3 -c`). The stored confirmation hash and the
  64-bit code (ayeo-io/compass#599) are the control that holds then.

Each check ignores letter case, because macOS opens a path in any case. The
earlier guard's checks run first, in its order and case, so a call it refused
keeps its refusal code. The glob check is the last Bash check.

The Bash checks match words, as the hook's other Bash checks do. They stop the
agent's ordinary use, not a deliberate workaround. A call is judged by its
whole text when the reader cannot read it, when a runner (`sh`, `eval`,
`source`, `xargs`) is beside a substitution, and when it holds `>(...)`. What
they do not stop:
  - a script that one call writes and another call runs;
  - the output of a command substitution that a shell does not run in the
    same call, and any word built at run time;
  - an option of an exempt command that runs a file the table does not know;
  - a flag or path built from a variable, command substitution, or a value
    read from a file or the environment;
  - arguments built by `xargs` or `printf`;
  - brace expansion in a glob, in Bash or in a Grep glob (`{d,x}eleg*/*`,
    `**/{DL-*,x}.yml`); a brace expansion in a delegated approval is refused;
  - patterns that only zsh reads (`.compass/(deleg\|x)ations/*`,
    `.compass/deleg*/DL-<->.yml`);
  - a case-sensitive glob (`.compass/*/[A-Z]*`, Grep `**/[A-Z]*.yml`): the
    guard lower-cases the glob, so it counts as a glob that picks the
    delegation files together with others, and passes;
  - a Bash command that reads the folder without naming it (`grep -r x
    .compass`, `find .compass -type f -exec cat {} +`);
  - a tool option that takes its own glob (`rg -g`, `find -name`,
    `--include`), and extended globs after `shopt -s extglob`;
  - a Bash glob that spells neither .compass nor deleg, such as
    `cat .c*/d*/*` (the hook does not start the guard for it). `cat
    .c*/delegations` does start it: the hook tests the command twice, so a
    glob before `deleg` comes after `deleg` in the other copy, and the guard
    refuses it. A glob rooted at another folder than `cwd` (`$PWD/...`) is
    also not stopped;
  - a relative path after `cd`, because the guard sees only the `cwd` of the
    call.
The safety contract states these limits.
"""
# DEPENDENCY: standard library (fnmatch, os, re, shlex, unicodedata),
# compass_pkg.approval_words (the reader) and compass_pkg.approval_guard_text (the
# text positions). Runs inside hooks/pre-tool.sh, so it keeps to
# syntax the hook's oldest supported python3 reads (3.10) and imports no
# third-party module.
from __future__ import annotations

import fnmatch
import os
import re
import shlex
import unicodedata

from compass_pkg.approval_guard_scripts import scripts
from compass_pkg.approval_guard_text import (HEREDOC_TEXT, SEARCH_VALUES, TEXT_COMMANDS,
                                              git_start, heredoc_is_text, is_compass, is_sink,
                                              skipped, text_marks)
from compass_pkg.approval_words import Unreadable, read

REQUEST_FOLDER = "approval-requests"
HOOK_ENTRY = "prompt-approval.sh"
DELEGATION_FOLDER = ".compass/delegations"
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
READ_TOOLS = ("Read", "Grep")
#: A Claude Code configuration folder's transcripts, however it is spelled.
#: macOS opens a path in any letter case, so each check also runs on the
#: lower-cased text, after the earlier guard's checks.
TRANSCRIPTS = re.compile(r"\.claude[\w.-]*/projects(?:/|\b)|CLAUDE_CONFIG_DIR")
#: A shell glob or brace character: a word holding one names every path it
#: expands to.
GLOB = re.compile(r"[*?\[{]")
#: A brace expansion: `{` with a `,` or `..` before the closing `}`.
BRACE = re.compile(r"\{[^{}]*(?:,|\.\.)[^{}]*\}")
#: How deep a command nested in quoted words is read, such as
#: `bash -c "bash -c '...'"`.
NESTING = 8
#: The longest part of a refused word that a refusal shows.
SHOWN_MAX = 80
#: Control, format and line-separator characters: none reaches a person's screen.
HIDDEN = ("Cc", "Cf", "Zl", "Zp")
NONE = frozenset()

# --- the policy tables: a widening is a one-line diff that needs a twin test row ---------------

#: Commands that show names or counts, so a bare path argument may name a request
#: folder or the prompt hook script.
LISTERS = frozenset(("ls", "wc", "stat", "du", "test", "["))
#: Commands that read a file, so a bare path argument may name the prompt hook script.
SCRIPT_READERS = frozenset(("cat", "head", "tail", "grep", "rg", "diff", "chmod"))
#: `git mv` and `git rm` are left out: one replaces the script and the other deletes it.
GIT_READS = frozenset("log show diff blame status ls-files add".split())
#: A `chmod` mode that keeps the script runnable by its owner: `+x`, or digits whose owner
#: digit has the execute bit. `-x`, `000` and `644` stop the approval hook.
CHMOD_KEEPS = re.compile(r"(?:[ugoa]*\+[rwxXst]+(?:,[ugoa]*\+[rwxXst]+)*|[0-7]?[1357][0-7]{2})")
CHMOD_OPTIONS = re.compile(r"-[RvfHLPh]+")
#: Options whose value is a path, a command or a file to write, never a bare path argument.
PATH_OPTIONS = frozenset(("-f", "--file", "--files0-from", "--output", "--pre", "--exec"))
#: Commands that run text. A substitution next to one, or into one, is judged as text.
RUNNERS = frozenset("sh bash zsh dash ksh eval source . xargs exec".split())
ESCAPED_NAME = re.compile(r"\$'[^']*\\")
SHADOWS = re.compile(r"(?:^|[;&|(){\n])\s*(?:function\s|alias\s|[A-Za-z_][\w.-]*\s*\(\s*\))")
ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=")


def exempt_commands():
    """The commands that hold an exemption from the request-folder rule or have a text
    position, read from the tables above, named as `tests/approval_guard_cases.py`
    counts them (`git` is `git commit`, `egrep` and `fgrep` are `grep`). A test ties this
    set to the table of counter-examples, so a widening needs three calls that stay refused."""
    names = set(LISTERS) | set(TEXT_COMMANDS) | set(HEREDOC_TEXT)
    return {"grep" if n in ("egrep", "fgrep") else "git commit" if n == "git" else n
            for n in names}


def script_commands():
    """The commands that may name the prompt hook script as a bare argument, besides
    `LISTERS`, read from the tables above."""
    return set(SCRIPT_READERS) | {"git " + verb for verb in GIT_READS}


def shown_word(word, found=""):
    """A refused word as a refusal shows it: no control, format or line-separator
    character, and at most `SHOWN_MAX` characters, so a hostile word cannot add text to
    the message. A longer word is cut around `found`, the protected part, so it is shown."""
    kept = "".join(c for c in str(word) if unicodedata.category(c) not in HIDDEN)
    if len(kept) <= SHOWN_MAX:
        return kept
    at = kept.lower().find(str(found).lower()) if found else -1
    if at < 0:
        return kept[:SHOWN_MAX]
    start = at if len(found) >= SHOWN_MAX else at - (SHOWN_MAX - len(found)) // 2
    start = max(0, min(start, len(kept) - SHOWN_MAX))
    return kept[start:start + SHOWN_MAX]


def _path(text):
    return str(text or "").replace("\\", "/")


def caller(event):
    """The agent Claude Code reports for this call: `main`, its exact
    `agent_type`, or None when the input does not name one."""
    has_type = "agent_type" in event
    has_id = event.get("agent_id") not in (None, "")
    agent_type = event.get("agent_type")
    if not has_type and not has_id:
        return "main"
    if isinstance(agent_type, str) and agent_type.strip():
        return agent_type
    return None


def _words(command):
    # shlex does not read ANSI-C quoting, so `$'approve'` would keep its `$`.
    # Dropping the `$` reads the word as the quoted text the shell runs.
    command = re.sub(r"\$(?=['\"])", "", command)
    # The shell drops a backslash and newline: `--a\<newline>s` runs as `--as`.
    command = command.replace("\\\n", "")
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _nested_words(words):
    """The words, then the words of each word that holds a space, such as the
    argument of `bash -c` or `eval`, read again. The first reading of the
    command is the caller's, so the rereads go to `NESTING - 1` levels."""
    found = list(words)
    level = [w for w in found if re.search(r"\s", w)]
    for _ in range(NESTING - 1):
        if not level:
            break
        following = []
        for text in level:
            parts = _words(text)
            found.extend(parts)
            following.extend(w for w in parts if re.search(r"\s", w))
        level = following
    return found


def _as_values(words):
    """Every value given to `--as`: the CLI keeps the last one."""
    values = []
    for i, word in enumerate(words):
        if word == "--as" and i + 1 < len(words):
            values.append(words[i + 1])
        elif word.startswith("--as="):
            values.append(word[len("--as="):])
    return values


def _delegated_flag(word):
    """`--delegated`, a prefix of it of five characters or more, or
    `--delegated=...`; not an unrelated flag such as `--delimiter`."""
    return (len(word) >= 5 and "--delegated".startswith(word)) or word.startswith(
        "--delegated=")


def _delegated_approve(words, earlier=False):
    """True for a command that may run a delegated `compass evidence approve`:
    a word, or a part of one cut at a shell operator, is `approve`, and a
    word is the `--delegated` flag. With `earlier`, the rule of the earlier
    guard also counts: `evidence approve` and any word that starts `--del`."""
    if earlier and any(a == "evidence" and b == "approve" for a, b in zip(words, words[1:])) \
            and any(w.startswith("--del") for w in words):
        return True
    runs = any(part == "approve" for w in words for part in re.split(r"[;&|()<>`]+", w))
    return runs and any(_delegated_flag(w) for w in words)


def _unreadable_as(words):
    """Space-free words that hold `--as` and are neither `--as` nor
    `--as=...`. A word with white space is read again as its parts."""
    return [w for w in words
            if "--as" in w and w != "--as" and not w.startswith("--as=")
            and not re.search(r"\s", w)]


#: A word that holds ANSI-C quoting with an escape: `$'--a\x73'` runs as
#: `--as`. Without a backslash, `$'--as'` is the quoted text, which `_words`
#: already reads.
ANSI_C = re.compile(r"\S*\$'[^']*\\\S*")

#: A word with an escape in command position (the start, or after an
#: operator or a variable assignment): `$'\x63ompass'` runs as `compass`.
ESCAPED_COMMAND = re.compile(
    r"(?:^|[;&|(`\n]|\$\()\s*(?:\w+=\S*\s+)*\S*\$'[^']*\\")


def _names_evidence(words, nested):
    """True when a word is `evidence`, or a quoted word holds `compass
    evidence` (the argument of `bash -c`, `eval` or a pipe into `sh`), or a
    word is the `--delegated` flag."""
    return (any(w == "evidence" or "compass evidence" in w for w in words)
            or any(_delegated_flag(w) for w in nested))


def _built_word(words, nested, raw, compass, escaped):
    """A word of a command that names evidence and holds ANSI-C quoting or a
    brace expansion, else None. The shell turns `$'appro\\x76e'` into
    `approve` and `--{delegated,x}` into `--delegated`; the guard does not
    decode them, so it refuses the command whether or not `--delegated` shows.
    `raw` is the words as written, `compass` is true when a word is `compass`,
    and `escaped` when a command name is spelled with an escape."""
    found = ANSI_C.search(raw)
    # A command that holds `compass` (or spells it with an escape in command
    # position) may spell every word with an escape, so `evidence` need not
    # show: `compass $'\x65vidence' $'appro\x76e'` runs `evidence approve`.
    evidence = _names_evidence(words, nested)
    if found and (evidence or compass or escaped):
        return found.group(0)
    if not evidence:
        return None
    for word in nested:
        if BRACE.search(word) and not re.search(r"\s", word):
            return word
    return None


def _caller_mismatch(words, nested, who):
    """`(named, caller)` when a delegated approval does not name its caller.
    The top-level words keep the earlier guard's rule, so nothing it refused
    is allowed now."""
    for words, earlier in ((words, True), (nested, False)):
        if not _delegated_approve(words, earlier):
            continue
        values = _as_values(words)
        wrong = [v for v in values if v != who]
        if not values or who is None or wrong:
            return (wrong[0] if wrong else values[0] if values else None), who
        # The shell can turn such a word into `--as` (`--as${IFS}x`), so the
        # value the CLI records may differ from the one checked above.
        unreadable = _unreadable_as(words)
        if unreadable:
            return unreadable[0], who
        # Brace expansion turns `--a{s=main,s=x}` into two `--as=` words. A
        # word that holds a space (a quoted value) is read again as its parts.
        braced = [w for w in words if BRACE.search(w) and not re.search(r"\s", w)]
        if braced:
            return braced[0], who
    return None


def _transcript_folder(event):
    path = event.get("transcript_path")
    return os.path.dirname(_path(path)) if path else ""


def _home():
    return os.environ.get("HOME") or os.path.expanduser("~")


def _config_folder():
    """A configuration folder directly under the home folder, as a word ends:
    `~/.claude-x`, `$HOME/.claude-x/` or `<home>/.claude-x/*`. A project's
    own `.claude` folder, or a file in either, does not match."""
    home = re.escape(_path(_home()).rstrip("/"))
    return re.compile(r"(?:~|\$\{?HOME\}?|%s)/+\.claude[\w.-]*/*\*?"
                      r"(?=$|[\s\"'`;|&()<>])" % home, re.I)


def _names_request(text, exempt=NONE, fold=False):
    """The request folder or prompt hook script name that `text` holds, unless
    the exemption covers it; else an empty string."""
    held = text.lower() if fold else text
    for fragment, thing in ((REQUEST_FOLDER, "request"), (HOOK_ENTRY, "script")):
        if fragment in held and thing not in exempt:
            return fragment
    return ""


def _names_delegation(text, fold=False):
    held = text.lower() if fold else text
    return DELEGATION_FOLDER if DELEGATION_FOLDER in held else ""


def _transcript_text(text, folder, fold):
    """The transcript name that `text` holds, in one letter case."""
    held = _path(text).lower() if fold else _path(text)
    base = folder.lower() if fold else folder
    found = TRANSCRIPTS.search(held)
    if found:
        return found.group(0)
    return folder if folder and base in held else ""


def _names_config(text):
    found = _config_folder().search(_path(text))
    return found.group(0) if found else ""


def _names_transcript(text, folder):
    """The transcript name that a tool path holds, in either letter case, or a
    configuration folder."""
    return (_transcript_text(text, folder, False) or _transcript_text(text, folder, True)
            or _names_config(text))


def _expand_home(text):
    """`~`, `~/...`, `~<name>`, `$HOME` and `${HOME}` at the start of a path,
    expanded."""
    for lead in ("~", "${HOME}", "$HOME"):
        if text == lead or text.startswith(lead + "/"):
            return _home() + text[len(lead):]
    if text.startswith("~"):
        return _path(os.path.expanduser(text))
    return text


def _norm(path):
    """`os.path.normpath`, with leading slashes collapsed (POSIX keeps `//`)
    and in lower case, since macOS opens a path in any case."""
    return re.sub(r"^/+", "/", os.path.normpath(path)).lower()


def _resolved(text, cwd):
    """A Read or Grep path as the tool reads it: home expanded, relative to
    the call's working folder, normalised."""
    text = _expand_home(_path(text))
    if not os.path.isabs(text):
        text = os.path.join(_path(cwd) or os.getcwd(), text)
    return _norm(text)


def _above_or_in(path, folder):
    """True when `path` is `folder`, inside it or a folder above it."""
    if not folder:
        return False
    folder = _norm(folder)
    if path == "/" or path == folder:
        return True
    return folder.startswith(path + "/") or path.startswith(folder + "/")


def _word_above(word, folder):
    """True when a Bash word names the transcript's folder, a path inside it
    or a folder above it, once the shell has removed its quotes. A word with
    a glob or brace character counts by the folder before the first one,
    since it can expand to the transcript: `~/.claude-x/*/s.jsonl`.
    The root folder alone is left out: `/` is also an argument of `tr`,
    `cut` and `expr`, and the safety contract states the gap."""
    path = _expand_home(_path(word))
    glob = GLOB.search(path)
    if glob:
        path = path[:glob.start()].rpartition("/")[0]
    path = re.sub(r"(?:/\*?|/\.)+$", "", path)
    if not folder or not path.startswith("/"):
        return False
    path, folder = _norm(path), _norm(folder)
    return path != "/" and (folder == path or folder.startswith(path + "/")
                            or path.startswith(folder + "/"))


def _memory_tail(path, folder):
    """What follows `memory` in a normalised path of the shape
    `<configuration folder>/projects/<one folder>/memory[/...]`, else None. The
    configuration folder ends in a `.claude*` segment, or its `projects` folder is
    the transcript's own."""
    found = re.fullmatch(r"(.*/\.claude[^/]*)/projects/[^/]+/memory(/.*)?", path)
    if found:
        return found.group(2) or ""
    if folder:
        own = {_norm(os.path.dirname(folder)), _norm(os.path.realpath(os.path.dirname(folder)))}
        for projects in own:
            found = re.fullmatch(re.escape(projects) + r"/[^/]+/memory(/.*)?", path)
            if found:
                return found.group(1) or ""
    return None


def in_memory_folder(path, cwd, folder, inside=False):
    """True when a tool path is in the agent's auto-memory folder, so the
    transcript tests do not apply to it. The path is joined to the call's
    `cwd`, normalised and case-folded, and its symbolic links are resolved; both
    forms must have the shape of `_memory_tail`. A glob or brace character in the
    path is never in the folder. With `inside`, the folder itself does not count
    (a Write or Edit names a file)."""
    text = _expand_home(_path(path))
    if not text or GLOB.search(text):
        return False
    if not os.path.isabs(text):
        text = os.path.join(_path(cwd) or os.getcwd(), text)
    try:
        resolved = _path(os.path.realpath(text))
    except (OSError, ValueError):
        return False
    tails =(_memory_tail(_norm(text), folder), _memory_tail(_norm(resolved), folder))
    return None not in tails and not (inside and not tails[0].strip("/"))


def _glob_climbs(glob):
    """True when a Grep glob holds a `..` segment, as `../*.jsonl` does, or a brace
    expansion that holds `..`, as `{..,x}/*.jsonl` does: ripgrep expands braces."""
    text = _path(glob)
    return ".." in re.split(r"[/\\,\s]+", text) or ("{" in text and ".." in text)


#: A delegation path and the ordinary path of the same shape outside the
#: folder. A glob that matches the first and not the second picks the
#: delegation files; one that matches both only picks "everything".
DELEGATION_SAMPLES = (
    (".compass/delegations", ".compass/zz"),
    (".compass/delegations/DL-1.yml", ".compass/zz/file.yml"),
    (".compass/delegations/confirm-s.yml", ".compass/zz/file.yml"),
)


def _flatten_classes(glob):
    """Replace each whole bracket expression that holds a POSIX class
    (`[:x:]`), collating symbol (`[.x.]`) or equivalence class (`[=x=]`) with
    `?`. `fnmatch` reads none of them, and a replacement inside the set would
    leave `[?x]`, which matches only `?` or `x`."""
    out, i = [], 0
    while i < len(glob):
        if glob[i] != "[":
            out.append(glob[i])
            i += 1
            continue
        j, special = i + 1, False
        if j < len(glob) and glob[j] in "!^":
            j += 1
        if j < len(glob) and glob[j] == "]":
            j += 1
        while j < len(glob) and glob[j] != "]":
            kind = glob[j + 1] if glob[j] == "[" and j + 1 < len(glob) else ""
            end = glob.find(kind + "]", j + 2) if kind in (":", ".", "=") and kind else -1
            if end >= 0:
                special, j = True, end + 2
            else:
                j += 1
        if j >= len(glob):
            out.append(glob[i])
            i += 1
        else:
            out.append("?" if special else glob[i:j + 1])
            i = j + 1
    return "".join(out)


def _glob_selects(glob, pairs, grep):
    """True when `glob` matches the delegation path of some pair and not its
    ordinary counterpart. All text is lower case, because macOS opens a path
    in any case and `fnmatch.fnmatch` would apply the operating system's
    rule. With `grep`, each path is also tried as `/` plus the path, as
    ripgrep reads `**/x`, and a glob without `/` as the bare name."""
    glob = glob.lower()
    # Bash and zsh read `[^x]` as `[!x]` and `[[:lower:]]` as one character;
    # `fnmatch` reads neither. A class becomes `?`, which keeps a refusal
    # that names the delegation folder and accepts a glob that picks every name.
    glob = _flatten_classes(glob).replace("[^", "[!")

    def matches(path):
        path = path.lower()
        tries = [path]
        if grep:
            tries.append("/" + path)
            if "/" not in glob:
                tries.append(path.rpartition("/")[2])
        return any(fnmatch.fnmatchcase(t, glob) for t in tries)

    return any(matches(sample) and not matches(plain) for sample, plain in pairs)


def _relative_pairs(root, searched):
    """The samples written relative to the search path, only for those the
    path can reach: the delegation folder is at or under it."""
    pairs = []
    for sample, plain in DELEGATION_SAMPLES:
        full = _norm(root + "/" + sample)
        if not (searched == "/" or full == searched or full.startswith(searched + "/")):
            continue
        rel = full[len(searched):].strip("/")
        other = _norm(root + "/" + plain)
        other_rel = (other[len(searched):].strip("/")
                     if other.startswith(searched.rstrip("/") + "/") else "\0")
        if rel:
            pairs.append((rel, other_rel))
    return pairs


def _grep_glob_reaches(pattern, searched, cwd):
    pairs = _relative_pairs(_resolved(".", cwd), _resolved(searched, cwd))
    # Claude Code may split the glob on white space or commas; test all forms.
    return any(_glob_selects(g, pairs, True)
               for g in [pattern] + re.split(r"[\s,]+", pattern))


def _bash_glob_reaches(words, cwd):
    """The first word whose glob can match the delegation files, else ''."""
    root = _resolved(".", cwd)
    relative = [(s, p) for s, p in DELEGATION_SAMPLES]
    absolute = [(root + "/" + s, root + "/" + p) for s, p in DELEGATION_SAMPLES]
    for word in words:
        if re.search(r"\s", word):
            continue
        for part in re.split(r"[;&|()<>`]+|(?<!\[)=+(?!\])", word):
            if not any(c in part for c in "*?["):
                continue
            part = _expand_home(_path(part))
            if os.path.isabs(part):
                if _glob_selects(_norm(part), absolute, False):
                    return word
                continue
            while part.startswith("./"):
                part = part[2:]
            if _glob_selects(os.path.normpath(part), relative, False):
                return word
    return ""


def _in_delegations(tool_input, cwd):
    target = _path(tool_input.get("file_path") or tool_input.get("path"))
    if target:
        resolved = _resolved(target, cwd) + "/"
        if (f"/{DELEGATION_FOLDER}/" in resolved
                or f"{DELEGATION_FOLDER}/" in target.lower() + "/"):
            return target
    pattern = _path(tool_input.get("glob"))
    if "delegations" in pattern.lower():
        return f"{target or cwd} with glob {pattern}"
    if pattern and _grep_glob_reaches(pattern, target or cwd or ".", cwd):
        return f"{target or cwd} with glob {pattern}"
    return ""


def check(event):
    """`(code, params)` for a call to refuse, else None."""
    tool = event.get("tool_name") or ""
    tool_input = event.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None
    folder = _transcript_folder(event)
    cwd = str(event.get("cwd") or "")
    if tool in READ_TOOLS:
        target = _path(tool_input.get("file_path") or tool_input.get("path"))
        # A Grep with no path searches its working folder.
        searched = target or (cwd if tool == "Grep" else "")
        # The auto-memory folder skips the transcript tests and no other test.
        memory = bool(searched) and in_memory_folder(searched, cwd, folder) and not (
            tool == "Grep" and _glob_climbs(tool_input.get("glob") or ""))
        if not memory and target and (_names_transcript(target, folder)
                                      or _config_folder().search(_resolved(target, cwd))):
            return "transcript-protected", {"target": target, "tool": tool}
        named = _in_delegations(tool_input, cwd)
        if named:
            return "delegation-protected", {"target": named, "tool": tool}
        if not memory and searched and _above_or_in(_resolved(searched, cwd), folder):
            return "transcript-protected", {"target": searched, "tool": tool}
        return None
    if tool in EDIT_TOOLS:
        target = _path(tool_input.get("file_path") or tool_input.get("path")
                       or tool_input.get("notebook_path"))
        memory = in_memory_folder(target, cwd, folder, inside=True)
        # The earlier guard's checks first, in its order, so a call it refused
        # keeps its code; then the same checks in any letter case.
        for path in (target, target.lower()):
            if f"/{REQUEST_FOLDER}/" in path and ".compass/" in path:
                return "approval-request-protected", {"target": target, "tool": tool}
            if f"{DELEGATION_FOLDER}/" in path:
                return "delegation-protected", {"target": target, "tool": tool}
            if not memory and _names_transcript(path, folder):
                return "transcript-protected", {"target": target, "tool": tool}
        return None
    if tool != "Bash":
        return None
    command = str(tool_input.get("command") or "")
    try:
        pipelines = read(command)
    except (Unreadable, RecursionError):
        # What the reader cannot read is judged by its whole text.
        return _judge_text(command, event, folder)
    # An output process substitution feeds the command's output to a command the
    # reader does not tie to it, and a function or alias can rename a command that
    # has an exemption, so such a command is judged by its whole text.
    material = None if ">(" in command or SHADOWS.search(command) else _material(
        pipelines, folder)
    if material is None:
        return _judge_text(command, event, folder)
    return _judge(event, folder, *material)


# --- Bash: the words and the text of a command ---------------------------------------------------

def _lists_above(word, folder):
    """True when `word` is a path strictly above the configuration folder and has no
    glob."""
    if not folder or GLOB.search(word):
        return False
    path = re.sub(r"(?:/\*?|/\.)+$", "", _expand_home(_path(word)))
    if not path.startswith("/"):
        return False
    path, config = _norm(path), _norm(os.path.dirname(os.path.dirname(folder)))
    return path != "/" and config.startswith(path + "/")


def _chmod_keeps(words):
    """True when a `chmod` only adds permissions or keeps the owner's execute bit, so it
    cannot stop the approval hook; an option it does not know makes it false."""
    if any(w.startswith("-") and not CHMOD_OPTIONS.fullmatch(w) for w in words[1:]):
        return False
    modes = [w for w in words[1:] if not w.startswith("-")]
    return bool(modes) and CHMOD_KEEPS.fullmatch(modes[0]) is not None


def _allowance(words, assigns, alone):
    """`(things, listing)` for a command: what a bare path argument of it may name,
    `request` (a request folder) and `script` (the prompt hook script), and whether
    it may name a folder above the configuration folder (an `ls` with no `-R` or
    `-d`). An exemption holds only for a command that stands alone."""
    if not alone or assigns or not words:
        return NONE, False
    name = words[0]
    if name == "chmod" and not _chmod_keeps(words):
        return NONE, False
    if name in LISTERS:
        things = frozenset(("request", "script"))
    elif name in SCRIPT_READERS or (name == "git" and git_start(words) > 0
                                    and words[git_start(words)] in GIT_READS):
        things = frozenset(("script",))
    else:
        return NONE, False
    if any(w.startswith(("--output", "--pre", "--exec")) for w in words):
        return NONE, False
    recursive = any(w.startswith("-") and (w in ("--recursive", "--directory") or (
        not w.startswith("--") and re.search("[Rd]", w))) for w in words[1:])
    return things, name == "ls" and not recursive


def _exempt(words, i, folder, allowance):
    """The things the word `words[i]` may name: the `allowance` of its command, and
    `above` for a folder above the configuration folder. Only a bare path argument
    counts: not an option, a `VAR=` word or the value of an option that takes a
    path."""
    things, listing = allowance
    word = words[i]
    if (not things or i == 0 or word.startswith("-") or ASSIGNMENT.match(word)
            or words[i - 1] in PATH_OPTIONS or words[i - 1] in SEARCH_VALUES):
        return NONE
    return things | {"above"} if listing and _lists_above(word, folder) else things


def _text_substitutions(pipelines):
    """The ids of the substitutions whose output stays in text. A substitution in a text
    position (a message, an `echo`, a text heredoc) stays in text when the command that
    holds it does too, all the way up; the words inside it are judged either way. Any other
    substitution is judged as the word it stands for (`cat "$(echo <file>)"` names the
    file), so no text exemption holds inside it."""
    sites = {}                      # id -> (id of the substitution that holds it, in text)
    for pipe in pipelines:
        for n, cmd in enumerate(pipe.commands):
            skip = skipped(cmd.words)
            words = cmd.words[skip:]
            marks, heredoc = text_marks(words), heredoc_is_text(words)
            # Text that a later stage can run or write is judged, so are its substitutions.
            runs = any(not is_sink(c.words) for c in pipe.commands[n + 1:])
            for slot, index, ident in cmd.subs:
                text = (index - skip in marks) if slot == "w" else heredoc and slot in "hs"
                sites[ident] = (pipe.sub, bool(text) and not runs)

    def in_text(ident):
        while ident in sites:           # a site the reader did not report is judged
            holder, text = sites[ident]
            if not text:
                return False
            if holder < 0:
                return True
            ident = holder
        return False

    return {ident for ident in sites if in_text(ident)}


def _material(pipelines, folder):
    """What `_judge` reads from a read command: `(items, top, exempt, raw,
    escaped)`, or None when the command must be judged by its whole text.

    - `items` are `(text, exempt, label)`: each judged word (label None) and each
      text that runs (label `"text"`, or `("script", path)`);
    - `top` are the words the caller rules read, judged words first, and `exempt`
      the exemptions of the first ones;
    - `raw` is those words as written, for ANSI-C quoting, and `escaped` is true
      when a command name is spelled with an escape."""
    words, exempt, raws, texts, braced = [], [], [], [], []
    escaped = runner = substituted = False

    def add(word, raw, allowed=NONE):
        words.append(word)
        exempt.append(allowed)
        raws.append(raw)

    in_text = _text_substitutions(pipelines)
    for pipe in pipelines:
        alone = len(pipe.commands) == 1 and not pipe.nested
        substituted = substituted or pipe.nested
        # A substitution that is not in text stands for a judged word, so what it prints
        # is judged: its commands have no text position.
        printed = pipe.nested and pipe.sub not in in_text
        for n, cmd in enumerate(pipe.commands):
            # A keyword such as `do` or `then` is followed by the command it starts.
            skip = skipped(cmd.words)
            cwords, craws = cmd.words[skip:], cmd.raws[skip:]
            name = cwords[0] if cwords else ""
            runner = runner or os.path.basename(name) in RUNNERS
            escaped = escaped or bool(craws and ESCAPED_NAME.search(craws[0]))
            marks, spoken = ({} if printed else text_marks(cwords)), []
            allowance = _allowance(cwords, cmd.assigns, alone)
            for assign, raw in zip(cmd.assigns, cmd.assign_raws):
                add(assign, raw)
            for i, word in enumerate(cwords):
                if i not in marks:
                    add(word, craws[i], _exempt(cwords, i, folder, allowance))
                    continue
                judged, value = marks[i]
                spoken.append(value)
                if judged:
                    add(judged, judged)
                # The shell may expand a brace in the value of a compass option, and the
                # earlier guard refused one in any `compass evidence` command.
                if is_compass(name) and BRACE.search(value) and not re.search(r"\s", value):
                    braced.append(value)
            for _, target in cmd.redirects:
                add(target, target)
            body = [s for s in (cmd.heredoc, cmd.herestring) if s]
            if not printed and heredoc_is_text(cwords):
                spoken += body
            elif body:
                texts.append(("text", "\n".join(body)))
            # Text is skipped only when every later stage of its pipeline reads it as
            # data; a stage that can run it or write it sends the text to be judged.
            if spoken and any(not is_sink(c.words) for c in pipe.commands[n + 1:]):
                texts.append(("text", " ".join(spoken)))
    if runner and substituted:      # the output of a substitution may be the script
        return None
    texts += [(("script", path), text) for path, text in scripts(pipelines)]
    items = [(w, e, None) for w, e in zip(words, exempt)]
    top = list(words) + braced
    for label, text in texts:
        items.append((text, NONE, label))
        top += _words(text)
        raws.append(text)
    return items, top, exempt, " ".join(raws), escaped


def _judge_text(command, event, folder):
    """The Bash checks on the whole text of a command, as they ran before the
    reader: for a command the reader cannot read."""
    text = command.replace("\\\n", "")
    return _judge(event, folder, [(command, NONE, "text")], _words(command), [], text,
                  bool(ESCAPED_COMMAND.search(text)), whole=True)


def _refusal(code, tool, text, found, label):
    if label is None:
        target = "the Bash word '%s'" % shown_word(text, found)
    elif label == "text":
        target = "text that holds '%s'" % shown_word(found)
    else:
        target = "script %s that holds '%s'" % (shown_word(label[1]), shown_word(found))
    return code, {"target": target, "tool": tool}


def _first(items, find):
    """`(found, text, label)` for the first item that `find(text, exempt)` names."""
    for text, exempt, label in items:
        found = find(text, exempt)
        if found:
            return found, text, label
    return None


def _judge(event, folder, items, top, exempt, raw, escaped, whole=False):
    """`(code, params)` for a Bash call to refuse, else None. The checks keep the
    order of the earlier guard, so a call it refused keeps its code: the request,
    delegation and transcript names; the caller rules; then the same names in any
    letter case, a configuration folder, a folder above the transcript and a glob."""
    tool = "Bash"
    for code, find in (
            ("approval-request-protected", lambda t, e: _names_request(t, e)),
            ("delegation-protected", lambda t, e: _names_delegation(t)),
            ("transcript-protected", lambda t, e: _transcript_text(t, folder, False))):
        hit = _first(items, find)
        if hit:
            return _refusal(code, tool, hit[1], hit[0], hit[2])
    nested = _nested_words(top)
    compass = ("compass" in raw.lower() if whole else any(is_compass(w) for w in nested))
    built = _built_word(top, nested, raw, compass, escaped)
    if built:
        return "delegation-caller-mismatch", {
            "named": shown_word(built),
            "caller": shown_word(caller(event) or "an agent with no agent type")}
    found = _caller_mismatch(top, nested, caller(event))
    if found:
        named, who = found
        return "delegation-caller-mismatch", {
            "named": shown_word(named or "no --as"),
            "caller": shown_word(who or "an agent with no agent type")}
    for code, find in (
            ("approval-request-protected", lambda t, e: _names_request(t, e, True)),
            ("delegation-protected", lambda t, e: _names_delegation(t, True)),
            ("transcript-protected", lambda t, e: _transcript_text(t, folder, True)),
            ("transcript-protected", lambda t, e: _names_config(t))):
        hit = _first(items, find)
        if hit:
            return _refusal(code, tool, hit[1], hit[0], hit[2])
    for i, word in enumerate(nested):
        if _word_above(word, folder) and not (i < len(exempt) and "above" in exempt[i]):
            return _refusal("transcript-protected", tool, word, word, None)
    # Last, so a call an earlier check refuses keeps its code.
    word = _bash_glob_reaches(nested, str(event.get("cwd") or ""))
    if word:
        return _refusal("delegation-protected", tool, word, word, None)
    return None
