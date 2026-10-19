# compass_pkg.approval_guard - the pre-tool checks on approval state
"""Decide whether the agent's tool call touches approval state it must not
(ADR-068 decision 10, ADR-069 decisions 4 and 8). `hooks/pre-tool.sh` calls
`check` with the hook input and blocks with the code it returns.

- **Request files.** Edit or Write on a file under an issue's
  `approval-requests/`, or a Bash command that names that folder or the
  prompt hook's entry point, gives `approval-request-protected`.
- **Delegation files.** Edit or Write under `.compass/delegations/`, Read or
  Grep that names that folder by path or by Grep glob, or a Bash command that
  names it, gives `delegation-protected`. The folder holds the salt and hash
  of the code that confirms a g5 delegation.
- **The session transcript.** Claude Code writes a hook's block message to
  the session's transcript file (measured on Claude Code 2.1.301), and the
  block message is where the person sees the code that confirms a g5
  delegation. So `transcript-protected` is given for:
  - Read or Grep on the transcript's folder, inside it, or on any folder
    above it, with `~` and `$HOME` expanded and a relative path joined to
    the call's `cwd`; a Grep with no path searches its `cwd`;
  - Read, Grep, Edit or Write, or a Bash command, that names a
    `.claude*/projects` folder, a configuration folder directly under the
    home folder (`~/.claude*`, ending there) or `CLAUDE_CONFIG_DIR`. A
    project's own `.claude` folder does not count;
  - a Bash word that names the transcript's folder or a folder above it,
    such as `~`, once `~`, `~<name>` and `$HOME` are expanded. A word with a
    glob counts by the folder before the glob.
- **A delegated approval's caller.** A Bash command is a delegated approval
  when one of its words is `approve` and one is `--delegated`, a prefix of
  it of five characters or more, or `--delegated=...`; the earlier rule,
  `evidence approve` beside any word that starts `--del`, also counts. The
  words are read twice: as the shell splits the command, and again with
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

Each check ignores letter case, because macOS opens a path in any case. The
earlier guard's checks run first, in its order and case, so a call it refused
keeps its refusal code. The glob check is the last Bash check.

The Bash checks match text, as the hook's other Bash checks do. They stop the
agent's ordinary use, not a deliberate workaround. What they do not stop:
  - a flag or path built from a variable, command substitution, or a value
    read from a file or the environment;
  - arguments built by `xargs` or `printf`;
  - brace expansion in a glob (`{d,x}eleg*/*`); a brace expansion in a
    delegated approval is refused;
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
# DEPENDENCY: standard library (os, re, shlex). Runs inside hooks/pre-tool.sh,
# so it keeps to syntax the hook's oldest supported python3 reads.
from __future__ import annotations

import fnmatch
import os
import re
import shlex

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


def _nested_words(command):
    """The command's words, then the words of each word that holds a space,
    such as the argument of `bash -c` or `eval`, read again to `NESTING`."""
    found = []
    level = [command]
    for _ in range(NESTING):
        following = []
        for text in level:
            words = _words(text)
            found.extend(words)
            following.extend(w for w in words if re.search(r"\s", w))
        if not following:
            break
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


def _caller_mismatch(command, who):
    """`(named, caller)` when a delegated approval does not name its caller.
    The top-level words keep the earlier guard's rule, so nothing it refused
    is allowed now."""
    for words, earlier in ((_words(command), True), (_nested_words(command), False)):
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


def _names_transcript(text, folder):
    text = _path(text)
    lower = text.lower()
    return (bool(TRANSCRIPTS.search(text)) or bool(folder and folder in text)
            or bool(TRANSCRIPTS.search(lower)) or bool(folder and folder.lower() in lower)
            or bool(_config_folder().search(text)))


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


#: A delegation path and the ordinary path of the same shape outside the
#: folder. A glob that matches the first and not the second picks the
#: delegation files; one that matches both only picks "everything".
DELEGATION_SAMPLES = (
    (".compass/delegations", ".compass/zz"),
    (".compass/delegations/DL-1.yml", ".compass/zz/file.yml"),
    (".compass/delegations/confirm-s.yml", ".compass/zz/file.yml"),
)


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
    glob = re.sub(r"\[\[:\w+:\]\]", "?", glob)
    glob = re.sub(r"\[:\w+:\]", "?", glob)
    glob = glob.replace("[^", "[!")

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
    root = _resolved(".", cwd)
    relative = [(s, p) for s, p in DELEGATION_SAMPLES]
    absolute = [(root + "/" + s, root + "/" + p) for s, p in DELEGATION_SAMPLES]
    for word in words:
        if re.search(r"\s", word):
            continue
        for part in re.split(r"[;&|()<>`=]+", word):
            if not any(c in part for c in "*?["):
                continue
            part = _expand_home(_path(part))
            if os.path.isabs(part):
                if _glob_selects(_norm(part), absolute, False):
                    return True
                continue
            while part.startswith("./"):
                part = part[2:]
            if _glob_selects(os.path.normpath(part), relative, False):
                return True
    return False


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
    if tool in READ_TOOLS:
        cwd = str(event.get("cwd") or "")
        target = _path(tool_input.get("file_path") or tool_input.get("path"))
        if target and (_names_transcript(target, folder)
                       or _config_folder().search(_resolved(target, cwd))):
            return "transcript-protected", {"target": target, "tool": tool}
        named = _in_delegations(tool_input, cwd)
        if named:
            return "delegation-protected", {"target": named, "tool": tool}
        # A Grep with no path searches its working folder.
        searched = target or (cwd if tool == "Grep" else "")
        if searched and _above_or_in(_resolved(searched, cwd), folder):
            return "transcript-protected", {"target": searched, "tool": tool}
        return None
    if tool in EDIT_TOOLS:
        target = _path(tool_input.get("file_path") or tool_input.get("path")
                       or tool_input.get("notebook_path"))
        # The earlier guard's checks first, in its order, so a call it refused
        # keeps its code; then the same checks in any letter case.
        for path in (target, target.lower()):
            if f"/{REQUEST_FOLDER}/" in path and ".compass/" in path:
                return "approval-request-protected", {"target": target, "tool": tool}
            if f"{DELEGATION_FOLDER}/" in path:
                return "delegation-protected", {"target": target, "tool": tool}
            if _names_transcript(path, folder):
                return "transcript-protected", {"target": target, "tool": tool}
        return None
    if tool != "Bash":
        return None
    command = str(tool_input.get("command") or "")
    text = _path(command)
    # The earlier guard's checks run first, in its order and letter case, so a
    # call it refused keeps the code it was refused with. The checks this
    # issue added follow.
    if REQUEST_FOLDER in command or HOOK_ENTRY in command:
        return "approval-request-protected", {
            "target": "a command naming approval requests", "tool": tool}
    if DELEGATION_FOLDER in command:
        return "delegation-protected", {
            "target": "a command naming .compass/delegations", "tool": tool}
    if TRANSCRIPTS.search(text) or (folder and folder in text):
        return "transcript-protected", {
            "target": "a command naming a session transcript", "tool": tool}
    found = _caller_mismatch(command, caller(event))
    if found:
        named, who = found
        return "delegation-caller-mismatch", {
            "named": named or "no --as", "caller": who or "an agent with no agent type"}
    lower = command.lower()
    if REQUEST_FOLDER in lower or HOOK_ENTRY in lower:
        return "approval-request-protected", {
            "target": "a command naming approval requests", "tool": tool}
    if DELEGATION_FOLDER in lower:
        return "delegation-protected", {
            "target": "a command naming .compass/delegations", "tool": tool}
    if TRANSCRIPTS.search(_path(lower)) or (folder and folder.lower() in lower):
        return "transcript-protected", {
            "target": "a command naming a session transcript", "tool": tool}
    if _config_folder().search(text):
        return "transcript-protected", {
            "target": "a command naming a Claude Code configuration folder", "tool": tool}
    if any(_word_above(w, folder) for w in _nested_words(command)):
        return "transcript-protected", {
            "target": "a command naming a folder above the session transcript",
            "tool": tool}
    # Last, so a call an earlier check refuses keeps its code.
    if _bash_glob_reaches(_nested_words(command), str(event.get("cwd") or "")):
        return "delegation-protected", {
            "target": "a command with a glob that can match .compass/delegations",
            "tool": tool}
    return None
