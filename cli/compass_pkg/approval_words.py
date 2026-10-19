# compass_pkg.approval_words - read a Bash command as simple commands
"""Turn the text of a Bash command into pipelines of simple commands, so the
approval guard (`approval_guard`) can judge each word and not the raw text.

The reader holds syntax only: no protected name and no policy. What it does:

- splits a command at `;`, `&&`, `||`, `&`, a newline and a parenthesis into
  pipelines, and at `|` and `|&` into the stages of one pipeline;
- removes quotes and backslashes the way the shell does, and keeps the text
  as written (`raws`), so a caller can see ANSI-C quoting;
- reads `$(...)`, backticks, `<(...)` and `>(...)` again as pipelines marked
  `nested`, and leaves `SUBST` where the substitution stood in a word;
- reads redirects (`>`, `>>`, `<`, `2>`, `&>`, `>|`, `<>`), heredocs
  (`<<`, `<<-`, quoted or not) and here-strings (`<<<`);
- drops a comment and reads leading `VAR=value` words as `assigns`;
- joins a backslash and newline as the shell does between and inside words, but keeps
  it inside the body of a quoted heredoc and ends a comment at its newline, so the
  reader and the shell agree on where a heredoc ends;
- gives each substitution an id: `Pipeline.sub` is the id of the substitution a nested
  pipeline came from, and `Command.subs` says where in the command (a word, an assign,
  a redirect target, a here-string or an unquoted heredoc body) each id stood.

It raises `Unreadable` for an open quote, parenthesis, backtick or `$(`, a
heredoc with no closing delimiter, a `${...}` that holds a quote or a
substitution, a `case` inside a substitution, a pipe with nothing before it
and nesting deeper than `MAX_DEPTH`. The caller then judges the whole text.
Any other construct (`for`, `{ }`, `$((...))`) reads as ordinary words.

The reader keeps no state between calls, and its time is linear in the text:
a substitution is read once, inside the same pass, and the depth is bounded.
"""
# DEPENDENCY: standard library (dataclasses, re). Runs inside hooks/pre-tool.sh,
# so it keeps to syntax that Python 3.10 reads and imports no third-party module.
from __future__ import annotations

import re
from dataclasses import dataclass

#: The deepest nesting of `$(...)`, backticks, `<(...)` and `>(...)` that is read.
MAX_DEPTH = 32
#: Stands in a word where a substitution was; the substitution is a nested pipeline.
SUBST = "\x00"

_ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?\+?=")
_FD = re.compile(r"\d+(?=[<>])")
_OPERATORS = ("<<<", "<<-", "<<", "<>", "<&", "<", ">>", ">&", ">|", ">", "&>>", "&>")
_DUPLICATION = re.compile(r"\d+-?|-")
_UNSAFE_PARAMETER = re.compile(r"""['"`\\\n]|\$[({]""")


def _odd_backslashes(line):
    """True when `line` ends in a backslash that is not itself escaped."""
    return (len(line) - len(line.rstrip("\\"))) % 2 == 1


class Unreadable(Exception):
    """The reader cannot read the command; the caller judges the whole text."""


@dataclass(frozen=True)
class Command:
    words: tuple[str, ...]            # name first; quotes removed; `$` before a quote dropped
    raws: tuple[str, ...]             # the same words as written (for ANSI-C quoting)
    assigns: tuple[str, ...]          # leading VAR=value words, judged like words
    redirects: tuple[tuple[str, str], ...]   # (operator, target); fd duplication has none
    heredoc: str | None               # body of << or <<-
    heredoc_literal: bool             # the delimiter was quoted: the body holds no substitution
    herestring: str | None            # operand of <<<
    assign_raws: tuple[str, ...] = ()  # the assigns as written
    # Where a substitution stood in this command: `(slot, index, id)`. The slot is `w`
    # (a word), `a` (an assign), `r` (a redirect target), `s` (a here-string) or `h` (the
    # body of an unquoted heredoc); the id is the `sub` of the nested pipelines it holds.
    subs: tuple[tuple[str, int, int], ...] = ()


@dataclass(frozen=True)
class Pipeline:
    commands: tuple[Command, ...]     # the stages of one pipeline, in order
    nested: bool                      # read from inside $(...), backticks, <(...) or >(...)
    sub: int = -1                     # the id of the substitution it came from; -1 at the top


class _Builder:
    """A command while it is read; a heredoc body arrives at the next newline."""

    def __init__(self):
        self.words, self.raws, self.assigns, self.assign_raws = [], [], [], []
        self.redirects, self.heredoc, self.literal, self.herestring = [], None, False, None
        self.used = False
        self.subs = []

    def build(self):
        return Command(tuple(self.words), tuple(self.raws), tuple(self.assigns),
                       tuple(self.redirects), self.heredoc, self.literal, self.herestring,
                       tuple(self.assign_raws), tuple(self.subs))


def read(text):
    """The pipelines of `text` in source order, then the nested ones. Raises
    `Unreadable`."""
    parser = _Parser(text, 0)
    try:
        top = parser.sequence(False)
    except RecursionError:
        raise Unreadable("nesting is too deep")
    return tuple(top) + tuple(parser.nested)


class _Parser:
    def __init__(self, text, depth, counter=None):
        self.t, self.n, self.i, self.depth = text, len(text), 0, depth
        self.nested = []
        self.counter = counter if counter is not None else [0]   # one id count for all levels
        self.open_words = []        # the ids of the substitutions of each word being read
        self.word_subs = ()         # the ids that the last word held

    def new_id(self):
        self.counter[0] += 1
        return self.counter[0]

    def skip_continuation(self):
        """Skip a backslash and newline: the shell joins the two lines. Quoted
        heredoc bodies and comments are read elsewhere and keep theirs."""
        if self.t.startswith("\\\n", self.i):
            self.i += 2
            return True
        return False

    # --- one level: a command list, or the inside of `$( )` -----------------------------------

    def sequence(self, closer):
        t, pipes, stages, cmd, pending, paren = self.t, [], [], _Builder(), [], 0

        def end_command():
            nonlocal cmd
            if cmd.used:
                stages.append(cmd)
            cmd = _Builder()

        def end_pipeline():
            nonlocal stages
            end_command()
            if stages:
                pipes.append(stages)
            stages = []

        closed = False
        while self.i < self.n:
            c = t[self.i]
            if c in " \t":
                self.i += 1
            elif c == "\\" and self.skip_continuation():
                pass
            elif c == "\n":
                self.i += 1
                if not (stages and not cmd.used):    # a line after a pipe continues it
                    end_pipeline()
                for item in pending:
                    self.heredoc_body(*item)
                pending = []
            elif c == "#":
                while self.i < self.n and t[self.i] != "\n":
                    self.i += 1
            elif c == ";":
                self.i += 1
                end_pipeline()
            elif c == "&" and t[self.i + 1:self.i + 2] != ">":
                self.i += 2 if t[self.i + 1:self.i + 2] == "&" else 1
                end_pipeline()
            elif c == "|":
                double = t[self.i + 1:self.i + 2] == "|"
                self.i += 2 if double or t[self.i + 1:self.i + 2] == "&" else 1
                if double:
                    end_pipeline()
                    continue
                if not (cmd.used or stages):
                    raise Unreadable("a pipe with nothing before it")
                end_command()
            elif c == "(":
                self.i += 1
                if stages and not cmd.used:     # `a | (b)`: a later stage that is not a sink
                    pseudo = _Builder()
                    pseudo.words, pseudo.raws, pseudo.used = ["("], ["("], True
                    stages.append(pseudo)
                end_pipeline()
                paren += 1
            elif c == ")":
                self.i += 1
                end_pipeline()
                if paren > 0:
                    paren -= 1
                elif closer:
                    closed = True
                    break
            elif c in "<>&" or (c.isdigit() and _FD.match(t, self.i)):
                if c in "<>" and t[self.i + 1:self.i + 2] == "(":
                    self.add_word(cmd, closer)
                else:
                    self.redirect(cmd, pending)
            else:
                self.add_word(cmd, closer)
        if closer and not closed:
            raise Unreadable("a $( without its )")
        if pending:
            raise Unreadable("a heredoc with no closing delimiter")
        end_pipeline()
        return [Pipeline(tuple(b.build() for b in stage), False) for stage in pipes]

    # --- words ---------------------------------------------------------------------------------

    def add_word(self, cmd, closer):
        start = self.i
        text = self.word()
        raw = self.t[start:self.i]
        cmd.used = True
        if not cmd.words and _ASSIGN.match(raw):
            cmd.subs.extend(("a", len(cmd.assigns), sub) for sub in self.word_subs)
            cmd.assigns.append(text)
            cmd.assign_raws.append(raw)
            return
        cmd.subs.extend(("w", len(cmd.words), sub) for sub in self.word_subs)
        # `case x in a) ...` inside a substitution ends the substitution at its `)`
        # for this reader and not for the shell, so text after it would read wrongly.
        if closer and not cmd.words and raw == "case":
            raise Unreadable("a case inside a substitution")
        cmd.words.append(text)
        cmd.raws.append(raw)

    def word(self):
        """The next word, quotes removed. `word_subs` holds the ids of the
        substitutions it held, in order."""
        mine = []
        self.open_words.append(mine)
        try:
            return self.read_word()
        finally:
            self.open_words.pop()
            self.word_subs = tuple(mine)

    def read_word(self):
        t, out = self.t, []
        while self.i < self.n:
            c = t[self.i]
            if c in " \t\n;&|()<>":
                if c in "<>" and t[self.i + 1:self.i + 2] == "(":
                    self.i += 2
                    out.append(self.substitution())
                    continue
                break
            if c == "\\":
                if self.skip_continuation():
                    continue
                out.append(t[self.i + 1] if self.i + 1 < self.n else "\\")
                self.i += 2
            elif c == "'":
                end = t.find("'", self.i + 1)
                if end < 0:
                    raise Unreadable("an open quote")
                out.append(t[self.i + 1:end])
                self.i = end + 1
            elif c == '"':
                self.double_quoted(out)
            elif c == "$":
                self.dollar(out, False)
            elif c == "`":
                out.append(self.backtick())
            else:
                out.append(c)
                self.i += 1
        return "".join(out)

    def double_quoted(self, out):
        t = self.t
        self.i += 1
        while self.i < self.n:
            c = t[self.i]
            if c == '"':
                self.i += 1
                return
            if c == "\\" and self.skip_continuation():
                continue
            if c == "\\" and self.i + 1 < self.n and t[self.i + 1] in '$`"\\':
                out.append(t[self.i + 1])
                self.i += 2
            elif c == "$":
                self.dollar(out, True)
            elif c == "`":
                out.append(self.backtick())
            else:
                out.append(c)
                self.i += 1
        raise Unreadable("an open quote")

    def dollar(self, out, quoted):
        t, i = self.t, self.i
        after = t[i + 1:i + 2]
        if after == "(":
            self.i += 2
            out.append(self.substitution())
        elif after == "{":
            end = t.find("}", i + 2)
            # A quote or a substitution inside `${...}` is read differently by each shell.
            if end < 0 or _UNSAFE_PARAMETER.search(t, i + 2, end):
                raise Unreadable("a ${ that the reader cannot follow")
            out.append(t[i:end + 1])
            self.i = end + 1
        elif after == "'" and not quoted:          # ANSI-C quoting: the text is kept as written
            j = i + 2
            while j < self.n and t[j] != "'":
                j += 2 if t[j] == "\\" else 1
            if j >= self.n:
                raise Unreadable("an open quote")
            out.append(t[i + 2:j])
            self.i = j + 1
        elif after == '"' and not quoted:          # `$"..."`: the `$` is dropped
            self.i += 1
        else:
            out.append("$")
            self.i += 1

    def substitution(self):
        """The inside of `$(`, `<(` or `>(`, which the caller has consumed."""
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise Unreadable("nesting is too deep")
        ident = self.new_id()
        pipes = self.sequence(True)
        self.depth -= 1
        self.nested.extend(Pipeline(p.commands, True, ident) for p in pipes)
        self.open_words[-1].append(ident)
        return SUBST

    def backtick(self):
        t, j, inner = self.t, self.i + 1, []
        while j < self.n and t[j] != "`":
            if t[j] == "\\" and j + 1 < self.n and t[j + 1] in "`\\$":
                j += 1
            inner.append(t[j])
            j += 1
        if j >= self.n:
            raise Unreadable("an open backtick")
        self.i = j + 1
        ident = self.new_id()
        self.child("".join(inner), ident=ident)
        self.open_words[-1].append(ident)
        return SUBST

    def child(self, text, start=0, closer=False, ident=-1):
        """Read `text` as a nested level; return where the reading stopped."""
        if self.depth + 1 > MAX_DEPTH:
            raise Unreadable("nesting is too deep")
        sub = _Parser(text, self.depth + 1, self.counter)
        sub.i = start
        pipes = sub.sequence(closer)
        self.nested.extend(sub.nested)
        self.nested.extend(Pipeline(p.commands, True, ident) for p in pipes)
        return sub.i

    # --- redirects and heredocs ----------------------------------------------------------------

    def redirect(self, cmd, pending):
        t = self.t
        fd = _FD.match(t, self.i)
        self.i = fd.end() if fd else self.i
        op = next((o for o in _OPERATORS if t.startswith(o, self.i)), None)
        if op is None:                      # a lone `&` is handled by the caller; this is `&`+other
            raise Unreadable("an operator the reader does not know")
        self.i += len(op)
        while self.i < self.n:
            if t[self.i] in " \t":
                self.i += 1
            elif not self.skip_continuation():
                break
        start = self.i
        if self.i >= self.n or (t[self.i] in "\n;|&()<>" and not t.startswith(("<(", ">("), self.i)):
            raise Unreadable("a redirect with no target")
        target = self.word()
        cmd.used = True
        slot = "s" if op == "<<<" else "r"
        cmd.subs.extend((slot, len(cmd.redirects), sub) for sub in self.word_subs)
        if op in ("<<", "<<-"):
            literal = bool(re.search(r"""['"\\]""", t[start:self.i]))
            if not target:
                raise Unreadable("a heredoc with no delimiter")
            # A second heredoc on one command adds its body to the first.
            cmd.literal = literal and (cmd.literal if cmd.heredoc is not None else True)
            cmd.heredoc = cmd.heredoc or ""
            pending.append((cmd, target, op == "<<-", literal))
        elif op == "<<<":
            cmd.herestring = target
        elif op in ("<&", ">&") and _DUPLICATION.fullmatch(target):
            pass                            # `2>&1` copies a descriptor and names no path
        else:
            cmd.redirects.append((op, target))

    def heredoc_body(self, cmd, delimiter, strip, literal):
        t, lines = self.t, []
        while True:
            if self.i >= self.n:
                raise Unreadable("a heredoc with no closing delimiter")
            end = t.find("\n", self.i)
            line = t[self.i:] if end < 0 else t[self.i:end]
            self.i = self.n if end < 0 else end + 1
            # An unquoted body joins a line that ends in a backslash with the next
            # line, and the delimiter must then stand alone on the joined line. A
            # quoted body keeps the backslash and newline, so its delimiter can follow.
            while not literal and self.i < self.n and _odd_backslashes(line) and end >= 0:
                end = t.find("\n", self.i)
                more = t[self.i:] if end < 0 else t[self.i:end]
                self.i = self.n if end < 0 else end + 1
                line = line[:-1] + more
            if strip:
                line = line.lstrip("\t")
            if line == delimiter:
                break
            lines.append(line)
        body = "\n".join(lines) + "\n" if lines else ""
        cmd.heredoc += body
        if not literal:
            cmd.subs.extend(("h", 0, sub) for sub in self.body_substitutions(body))

    def body_substitutions(self, body):
        """An unquoted heredoc body holds `$(...)` and backticks that run. The ids of
        the substitutions it holds."""
        j, found = 0, []
        while j < len(body):
            c = body[j]
            if c == "\\":
                j += 2
            elif c == "$" and body.startswith("$(", j):
                found.append(self.new_id())
                j = self.child(body, j + 2, True, found[-1])
            elif c == "`":
                end = body.find("`", j + 1)
                if end < 0:
                    raise Unreadable("an open backtick")
                found.append(self.new_id())
                self.child(body[j + 1:end].replace("\\`", "`"), ident=found[-1])
                j = end + 1
            else:
                j += 1
        return found
