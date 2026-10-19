# compass_pkg.approval_guard_scripts - a script that one Bash call writes and then runs
"""The approval guard (`approval_guard`) does not judge text, so a call that writes
text to a file and then runs the file would hide a protected path in the text. This
module follows the file inside one call and returns its text, so the guard can judge
it as the commands it runs.

What it follows, in one call:

- the text of `echo`, `printf` and a `cat` heredoc or here-string, through the
  `TEXT_SINKS` of a pipeline (`| cat > f`, `| tr a a > f`, `| tee f`);
- a write by a redirect (`>`, `>>`, `>|`) or by `tee`, also through a brace group or
  a subshell (`{ echo x; } > f`: the file holds all the text written so far in the call);
- a copy, move or link (`cp`, `mv`, `ln`) of such a file;
- a change of folder with `cd`, so `cd /tmp; sh s1` runs `/tmp/s1`;
- a run: the file named by any command that is not a plain data command (`ls`, `cat`,
  `grep`, `rm`, `cp` and the like), as a word or as a part of a word that holds white
  space (`bash -c 'source f'`, `python3 -c 'os.system("sh f")'`), or as a `<` redirect.
  So `env bash f`, `bash -o pipefail f`, `command sh f`, `exec sh f`, `find f -exec sh`
  and `rg --pre sh . f` all run it.

What it does not follow, and the safety contract states: a script that one call writes
and another call runs; a file written by any other command (`dd`, `sed -i`, `curl -o`,
an interpreter); a script built at run time; a folder reached by `cd` with a variable or
`~`, which is matched by file name alone.
"""
# DEPENDENCY: standard library (os) and compass_pkg.approval_guard_text. Runs inside
# hooks/pre-tool.sh, so it keeps to syntax that Python 3.10 reads.
from __future__ import annotations

import os

from compass_pkg.approval_guard_text import command_name, heredoc_is_text, is_sink, skipped

#: Commands that only show, count, move or search a file named to them. They do not run it.
DATA_COMMANDS = frozenset("""cat head tail less more grep egrep fgrep ls wc stat du file rm
    chmod touch cp mv ln diff cmp sort uniq cut tr echo printf tee test [ mkdir cd pwd
    basename dirname realpath readlink shasum md5 xxd strings""".split())
#: Words that close a group whose output is redirected: `{ echo x; } > f`.
GROUP_ENDS = frozenset(("}", "done", "fi", "esac"))
WRITE_OPS = (">", ">>", ">|", "&>", "&>>")


def _words(cmd):
    return cmd.words[skipped(cmd.words):]


def _stage_text(cmd):
    """The text a command writes to its output by itself, or None."""
    words = _words(cmd)
    name = command_name(words)
    if name in ("echo", "printf"):
        return " ".join(words[1:])
    own = [s for s in (cmd.heredoc, cmd.herestring) if s]
    if own and (name == "cat" or (name == "tee" and heredoc_is_text(words))):
        return "\n".join(own)
    return None


def _flows(pipe):
    """The text that leaves each stage of a pipeline: a producer's own text, or what a
    sink was fed."""
    out, previous = [], None
    for cmd in pipe.commands:
        own = _stage_text(cmd)
        if own is not None:
            previous = own
        elif not is_sink(_words(cmd)):
            previous = None
        out.append(previous)
    return out


class _Files:
    """The files that the call has written so far, by normalised name."""

    def __init__(self):
        self.text, self.shown, self.cwd, self.loose = {}, {}, "", False

    def key(self, path):
        if self.loose:
            return os.path.basename(path)
        return os.path.normpath(os.path.join(self.cwd, path))

    def write(self, path, text, append=False):
        for key in {self.key(path), os.path.basename(path)}:
            old = self.text.get(key)
            self.text[key] = old + "\n" + text if append and old else text
            self.shown.setdefault(key, path)

    def find(self, path):
        key = self.key(path)
        return key if key in self.text else None

    def change_folder(self, target):
        if not target or target[0] in "~$-" or "\x00" in target:
            self.loose = True           # the folder is unknown: match by file name
        elif target.startswith("/"):
            self.cwd = os.path.normpath(target)
        else:
            self.cwd = os.path.normpath(os.path.join(self.cwd or ".", target))


def _runs(cmd, files):
    """The keys of the written files that a command runs."""
    words = _words(cmd)
    if not words:
        return []
    name = os.path.basename(words[0])
    if name in DATA_COMMANDS and not (name == "rg" and any(w.startswith("--pre") for w in words)):
        return []
    found = []
    for word in list(words) + [t for op, t in cmd.redirects if op == "<"]:
        key = files.find(word)
        if key is not None:
            found.append(key)
        elif any(c.isspace() for c in word):
            found += [k for k, shown in files.shown.items() if shown in word]
    return found


def scripts(pipelines):
    """`[(path, text)]` for each file that a command writes and a later command, or a
    later stage, of the same call runs. Only a script written and run in one call is
    followed."""
    files, found, history = _Files(), {}, []
    for pipe in pipelines:
        if pipe.nested:
            continue
        flows = _flows(pipe)
        for n, cmd in enumerate(pipe.commands):
            words = _words(cmd)
            name = words[0] if words else ""
            text = flows[n]
            if name == "cd" and len(words) > 1:
                files.change_folder(words[1])
            if text is not None:
                history.append(text)
            if name in GROUP_ENDS or (not words and any(op in WRITE_OPS for op, _ in cmd.redirects)):
                text = "\n".join(history)       # a group holds all the text written before it
            for op, target in cmd.redirects:
                if text is not None and op in WRITE_OPS:
                    files.write(target, text, append=op in (">>", "&>>"))
            if name == "tee":
                fed = flows[n - 1] if n else None
                fed = fed if fed is not None else _stage_text(cmd)
                for operand in words[1:]:
                    if fed is not None and not operand.startswith("-"):
                        files.write(operand, fed)
            if os.path.basename(name) in ("cp", "mv", "ln") and len(words) > 2:
                operands = [w for w in words[1:] if not w.startswith("-")]
                sources = [files.find(w) for w in operands[:-1]]
                if any(s is not None for s in sources):
                    files.write(operands[-1], "\n".join(files.text[s] for s in sources if s))
        for cmd in pipe.commands:
            for key in _runs(cmd, files):
                found[files.shown.get(key, key)] = files.text[key]
    return list(found.items())
