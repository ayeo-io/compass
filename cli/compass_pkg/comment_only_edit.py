# =============================================================================
# Is an Edit of a Python or YAML file a change to comments only?
# =============================================================================
# hooks/pre-tool.sh refuses an Edit of production code unless a failing test is
# on record. A comment cannot change what code does, so an Edit that changes
# only comments, docstrings or layout needs no failing test and no assessed
# issue. This module proves that from the file on disk and never from the text
# of the Edit: it reads the file once, applies the Edit in memory and compares
# the file before and after.
#
#   * Python: the syntax trees are the same. A docstring that is the first
#     statement of a module, class or function may change its text, unless the
#     file mentions `__doc__`, `getdoc`, `help`, `doctest`, `exec` or `eval`.
#   * YAML: the parser's events are the same (anchors, aliases, tags, values,
#     key order, merge keys). A duplicate key, an alias that expands to more
#     than MAX_ALIAS_NODES nodes and a file that does not parse give "no".
#   * Shell and every other language are not covered: a shell comment cannot be
#     told from a heredoc body or a quoted string without a shell parser.
#
# THE RULE FOR EVERY DOUBT. The answer "yes" needs a positive proof. A file over
# MAX_FILE_BYTES, a file that is not a regular file, a symbolic link, a text
# that is not UTF-8, an Edit whose old text is not found exactly once (or many
# times with replace_all), a pragma, a hidden character, a parse error, a check
# that runs out of budget and an error of any kind all give "no". The hook then
# judges the Edit as it did before this module existed. A comment that carries
# a pragma is code (DD-3 of the decision record). So is an Edit of a Python file
# whose encoding cookie is not utf-8 or ascii or that the Edit adds, removes or
# moves, an Edit that adds a non-ASCII character to a file with an ascii
# cookie, and an Edit of a file whose first line makes a template engine read
# it. The pragma list and the docstring readers are lists of words: a tool that
# is not on them is not seen.
#
# THE TIME BOUND. A parser can be made slow on purpose: PyYAML needs about 90
# seconds for 100,000 "[" characters. The charge is computed before any parse,
# from the size of the larger text, and an Edit that does not fit the budget
# the hook gives is not parsed. A signal.alarm bounds the rest: its default
# action ends the process even inside C code, and the hook reads that as "no".
#
# THE OUTPUT. `main` prints "yes" or "no", then the charge in microseconds, and
# nothing else. It never prints text of the file or of the Edit.
#
# DEPENDENCY: Python 3 standard library, and the vendored yaml for YAML files.
# It is imported only for a YAML file, so a Python edit does not pay for it.
# =============================================================================
from __future__ import annotations

import ast
import gc
import json
import os
import re
import signal
import stat
import unicodedata
import warnings
from typing import NamedTuple

#: The largest file the check reads, and the largest text it compares.
MAX_FILE_BYTES = 1048576
#: Nodes that the aliases of one YAML file may expand to. A bomb is an anchor
#: whose alias is used many times by an anchor that is used many times.
MAX_ALIAS_NODES = 100000
#: The files covered, by suffix. Shell is not in it on purpose.
LANGUAGES = {".py": "python", ".yml": "yaml", ".yaml": "yaml"}

# A comment with a directive that changes what a tool reports or how a file
# runs is code. This is a superset of the list in the acceptance criteria:
# it can refuse more, never less.
_PRAGMA_WORDS = re.compile(
    r"type:|noqa|nosec|fmt:|pragma:|pylint:|mypy:|pyright:|ruff:|flake8|isort:"
    r"|yamllint|shellcheck|nolint|coding[:=]|noinspection|pytype:|pyre-"
    r"|prettier-ignore|@formatter|trunk-ignore|bandit|skipcq|codespell|cspell"
    r"|nosemgrep|gitleaks|checkov|lgtm|nosonar|codeql|yapf|tfsec|trivy",
    re.IGNORECASE)
# The two encodings in which a comment cannot hide a line break. Python reads
# the name of an encoding cookie after lower-casing it and turning "_" to "-".
SAFE_ENCODINGS = frozenset(("utf-8", "utf8", "ascii"))
# PEP 263: a comment on line 1, or on line 2 when line 1 is blank or a comment.
_COOKIE = re.compile(r"[ \t\f]*#.*?coding[:=][ \t]*([-\w.]+)")
_BLANK_OR_COMMENT = re.compile(r"[ \t\f]*(?:[#\r\n]|$)")
_LINE = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)?")
# A file that starts with this line is rendered as a template (cloud-init's
# `## template: jinja`) before the YAML parser reads it.
_TEMPLATE_HEADER = re.compile(r"[ \t]*#+[ \t]*template[ \t]*:", re.IGNORECASE)
# A docstring may change its text only when nothing in the file reads it.
_DOCSTRING_READERS = re.compile(
    r"(?<![A-Za-z0-9])(?:__doc__|getdoc|help|doctest|exec|eval)(?![A-Za-z0-9])")
# ASCII controls other than tab, line feed and carriage return.
_ASCII_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class Verdict(NamedTuple):
    allowed: bool
    #: A fixed word for tests. Never text of the file.
    reason: str
    #: Microseconds to add to the hook's work budget.
    charge: int


def apply_edit(text: str, old: str, new: str, replace_all: bool) -> str | None:
    """The text after the Edit, or None when the Edit would not apply as the
    tool applies it: an empty or unchanged old text, an old text that is not in
    the file, or one that occurs more than once without replace_all."""
    if not old or old == new:
        return None
    count = text.count(old)
    if count == 0 or (count > 1 and not replace_all):
        return None
    return text.replace(old, new) if replace_all else text.replace(old, new, 1)


def _common_prefix(a: str, b: str, limit: int) -> int:
    """The length of the common prefix, at most `limit`. A binary search over
    slices, so the work is done in C."""
    low, high = 0, limit
    while low < high:
        mid = (low + high + 1) // 2
        if a[:mid] == b[:mid]:
            low = mid
        else:
            high = mid - 1
    return low


def _common_suffix(a: str, b: str, limit: int) -> int:
    low, high = 0, limit
    while low < high:
        mid = (low + high + 1) // 2
        if a[len(a) - mid:] == b[len(b) - mid:]:
            low = mid
        else:
            high = mid - 1
    return low


def changed_lines(before: str, after: str) -> tuple[list[str], list[str]]:
    """The whole lines that differ, by common prefix and common suffix: the
    lines of `before` and the lines of `after` between them. A line that only
    one text holds is in its list alone."""
    if before == after:
        return [], []
    prefix = _common_prefix(before, after, min(len(before), len(after)))
    start = before.rfind("\n", 0, prefix) + 1
    suffix = _common_suffix(before, after, min(len(before), len(after)) - prefix)
    end_before = len(before) - suffix
    end_after = len(after) - suffix
    # The rest of the last changed line is the same in both texts.
    newline = before.find("\n", end_before)
    extra = (newline if newline != -1 else len(before)) - end_before
    return (before[start:end_before + extra].split("\n"),
            after[start:end_after + extra].split("\n"))


def touches_pragma(lines: list[str]) -> bool:
    """Whether a line is a shebang, or holds a comment mark followed on the
    same line by a pragma word. One `find` and one search for each line, so a
    line of many "#" is not read once for each of them."""
    for line in lines:
        if line.lstrip().startswith("#!"):
            return True
        mark = line.find("#")
        if mark != -1 and _PRAGMA_WORDS.search(line, mark):
            return True
    return False


def _first_two_lines(text: str) -> tuple[str, str]:
    """The first two lines with their line ends, after a byte order mark."""
    pos = 1 if text[:1] == "﻿" else 0
    first = _LINE.match(text, pos)
    second = _LINE.match(text, first.end())
    return first.group(), second.group()


def encoding_cookie(text: str) -> str | None:
    """The encoding name that Python would read from the first two lines of the
    source (PEP 263), as Python normalises it, or None when there is none."""
    first, second = _first_two_lines(text)
    found = _COOKIE.match(first)
    if found is None and _BLANK_OR_COMMENT.match(first):
        found = _COOKIE.match(second)
    return found.group(1).lower().replace("_", "-") if found else None


def encoding_changes_code(before: str, after: str) -> bool:
    """Whether the encoding of the file decides what the Edit means. Python
    decodes the source with the cookie before it parses a line, so a cookie
    such as `utf-7` or `unicode_escape` turns text inside a comment into a line
    break, and a cookie that moves out of the first two lines changes how the
    whole file is read. The parse of the text as UTF-8 proves nothing then."""
    cookie_before = encoding_cookie(before)
    cookie_after = encoding_cookie(after)
    if cookie_before != cookie_after:
        return True
    if cookie_before is not None and cookie_before not in SAFE_ENCODINGS:
        return True
    # Python cannot load an ASCII-cookie file that holds a non-ASCII character,
    # so an Edit that adds one turns a working file into a SyntaxError.
    if cookie_after == "ascii" and not after.isascii():
        return True
    return False


def starts_as_template(text: str) -> bool:
    """Whether the first line makes a template engine read the whole file."""
    return _TEMPLATE_HEADER.match(_first_two_lines(text)[0]) is not None


def adds_hidden_character(lines: list[str]) -> bool:
    """Whether a line holds a character that shows nothing or reverses text: a
    control, a format character such as the bidirectional controls and the
    zero-width ones, or a line or paragraph separator. Tab, line feed and
    carriage return are allowed."""
    for line in lines:
        if line.isascii():
            if _ASCII_CONTROL.search(line):
                return True
            continue
        for char in line:
            category = unicodedata.category(char)
            if (category[0] == "C" or category in ("Zl", "Zp")) \
                    and char not in "\t\n\r":
                return True
    return False


_DOCSTRING_HOLDERS = (ast.Module, ast.ClassDef, ast.FunctionDef,
                      ast.AsyncFunctionDef)


def _docstring(node) -> str | None:
    body = node.body
    if body and isinstance(body[0], ast.Expr):
        value = body[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    return None


def _blank_docstrings(tree) -> int:
    """Empty the text of every docstring, in place, and return how many there
    were: the first statement of a module, class or function when it is a
    plain string. An f-string is not a plain string (it is a JoinedStr), so its
    text stays and a change to it shows.

    Only statements are visited: a module, class or function can sit only in a
    list of statements, and a tree has about eight times as many expression
    nodes, which a walk of the whole tree would visit for nothing."""
    blanked = 0
    stack = [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, _DOCSTRING_HOLDERS) and _docstring(node) is not None:
            node.body[0].value.value = ""
            blanked += 1
        for name in ("body", "orelse", "finalbody", "handlers", "cases"):
            children = getattr(node, name, None)
            if isinstance(children, list):
                stack.extend(children)
    return blanked


def python_same(before: str, after: str) -> bool:
    """Whether both texts parse and their syntax trees are the same.

    A docstring's text may differ when that is the only difference, the
    docstring is the first statement of the same module, class or function in
    both texts, and nothing in either text reads docstrings at run time. The
    dumps of the trees are compared as text: they leave out positions and are
    far faster than a walk in Python. A tree too deep to dump is "no"."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree_before = ast.parse(before)
            tree_after = ast.parse(after)
        if ast.dump(tree_before) == ast.dump(tree_after):
            return True
        # A docstring that appears, disappears or moves changes the blanked
        # trees too, because the blank text is the statement's only content.
        # Without a docstring in either tree the difference is code, and the
        # second pair of dumps would only repeat the first.
        if _blank_docstrings(tree_before) + _blank_docstrings(tree_after) == 0:
            return False
        if ast.dump(tree_before) != ast.dump(tree_after):
            return False
    except Exception:           # a syntax error, a null byte, a tree too deep
        return False
    return not (_DOCSTRING_READERS.search(before)
                or _DOCSTRING_READERS.search(after))


def _yaml_signature(yaml, text: str):
    """The events of a YAML text, without style or position, or None when the
    text must not be compared: a duplicate key, an alias to an anchor that is
    not complete, or aliases that expand to more than MAX_ALIAS_NODES nodes.
    The expansion is counted once for each anchor with a table, so a bomb
    costs no more than its text."""
    events = yaml.events
    signature = []
    stack: list[list] = []      # kind, children so far, size, anchor, keys
    sizes: dict[str, int] = {}
    expanded = 0

    def done(size: int, key) -> bool:
        if not stack:
            return True
        frame = stack[-1]
        if frame[0] == "map" and frame[1] % 2 == 0 and key is not None:
            if key in frame[4]:
                return False
            frame[4].add(key)
        frame[1] += 1
        frame[2] = min(frame[2] + size, MAX_ALIAS_NODES + 1)
        return True

    for event in yaml.parse(text, Loader=yaml.SafeLoader):
        if isinstance(event, events.ScalarEvent):
            signature.append(("scalar", event.anchor, event.tag, event.implicit,
                              event.value))
            if event.anchor:
                sizes[event.anchor] = 1
            if not done(1, (event.tag, event.value)):
                return None
        elif isinstance(event, events.AliasEvent):
            signature.append(("alias", event.anchor))
            size = sizes.get(event.anchor)
            if size is None:
                return None
            expanded += size
            if expanded > MAX_ALIAS_NODES or not done(size, None):
                return None
        elif isinstance(event, (events.SequenceStartEvent,
                                events.MappingStartEvent)):
            kind = "seq" if isinstance(event, events.SequenceStartEvent) else "map"
            signature.append((kind, event.anchor, event.tag, event.implicit))
            stack.append([kind, 0, 1, event.anchor, set()])
        elif isinstance(event, (events.SequenceEndEvent, events.MappingEndEvent)):
            frame = stack.pop()
            signature.append(("end",))
            if frame[3]:
                sizes[frame[3]] = frame[2]
            if not done(frame[2], None):
                return None
        elif isinstance(event, events.DocumentStartEvent):
            sizes = {}
            signature.append(("document", event.version,
                              tuple(sorted((event.tags or {}).items()))))
        else:
            signature.append((type(event).__name__,))
    return signature


def yaml_same(before: str, after: str) -> bool:
    """Whether both texts parse and give the same events: the same data, key
    order, anchors, aliases, tags and merge keys. Comments, layout and quote
    style are not part of an event."""
    try:
        import yaml
        signature_before = _yaml_signature(yaml, before)
        if signature_before is None:
            return False
        signature_after = _yaml_signature(yaml, after)
    except Exception:           # a parse error, a reader error, no memory
        return False
    return signature_after is not None and signature_before == signature_after


def _read(path: str) -> str | None:
    """The text of a regular file of at most MAX_FILE_BYTES, or None. A symbolic
    link is not followed, and a pipe or device is not read: the file is opened
    once and judged by that descriptor, so the checks are of what is read."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except (OSError, ValueError):
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
            return None
        chunks, total = [], 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                return None
            chunks.append(chunk)
    finally:
        os.close(fd)
    try:
        return b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError:
        return None


def judge(event: dict, costs: dict[str, int], remaining: int) -> Verdict:
    """The verdict for one tool call. `costs` holds the hook's measured
    figures in microseconds (start, parse_py, parse_yaml, kb_py, kb_yaml), and
    `remaining` is what is left of its work budget."""
    start = costs["start"]

    def no(reason: str, charge: int = start) -> Verdict:
        return Verdict(False, reason, charge)

    if not isinstance(event, dict) or event.get("tool_name") != "Edit":
        return no("not-an-edit")
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return no("no-input")
    path = tool_input.get("file_path")
    old = tool_input.get("old_string")
    new = tool_input.get("new_string")
    if not (isinstance(path, str) and isinstance(old, str) and isinstance(new, str)):
        return no("no-edit")
    language = LANGUAGES.get(os.path.splitext(path)[1])
    if language is None or not os.path.isabs(path):
        return no("not-covered")
    before = _read(path)
    if before is None:
        return no("unreadable-or-too-large")
    after = apply_edit(before, old, new, tool_input.get("replace_all") is True)
    if after is None:
        return no("edit-does-not-apply")
    size = max(len(before.encode("utf-8")), len(after.encode("utf-8")))
    if size > MAX_FILE_BYTES:
        return no("too-large")
    if language == "python" and encoding_changes_code(before, after):
        return no("encoding")
    if starts_as_template(before) or starts_as_template(after):
        return no("template")
    old_lines, new_lines = changed_lines(before, after)
    if touches_pragma(old_lines) or touches_pragma(new_lines):
        return no("pragma")
    if adds_hidden_character(new_lines):
        return no("hidden-character")
    kib = (size + 1023) // 1024
    parse, rate = ((costs["parse_py"], costs["kb_py"]) if language == "python"
                   else (costs["parse_yaml"], costs["kb_yaml"]))
    # The rate is for each KiB of the two texts together, and each of the two
    # parses has a fixed part.
    charge = start + 2 * parse + kib * rate
    if charge > remaining:
        return no("over-budget")
    same = (python_same if language == "python" else yaml_same)(before, after)
    return Verdict(same, "comment-only" if same else "changes-code", charge)


_COST_KEYS = ("start", "parse_py", "parse_yaml", "kb_py", "kb_yaml")


def main(argv: list[str], stdin) -> int:
    """`alarm=<s> remaining=<us> start=.. parse_py=.. parse_yaml=.. kb_py=..
    kb_yaml=..`, the tool call as JSON on stdin. Prints the verdict and the
    charge, one to a line. The alarm is set first and is never cleared: the
    process ends within it."""
    params = {}
    for arg in argv:
        key, _, value = arg.partition("=")
        if value.isdigit() and len(value) <= 9:
            params[key] = int(value)
    if any(key not in params for key in (*_COST_KEYS, "alarm", "remaining")) \
            or params["alarm"] < 1:
        print("no")
        print(0)
        return 0
    signal.alarm(params["alarm"])
    # The process ends after one verdict, and its trees hold millions of
    # objects that collection would only walk again and again.
    gc.disable()
    costs = {key: params[key] for key in _COST_KEYS}
    try:
        verdict = judge(json.load(stdin), costs, params["remaining"])
    except Exception:           # nothing is proved, so nothing is allowed
        verdict = Verdict(False, "failed", costs["start"])
    print("yes" if verdict.allowed else "no")
    print(verdict.charge)
    return 0
