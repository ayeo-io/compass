#!/usr/bin/env python3
"""Compares a batch's changed files against its merge base, to show that a
prose rewrite changed no behaviour: no printed string, no asserted string
and no code body. `prose-breaks-the-writing-style` needs this because
`verify.architecture` accepts only a `test-run` or a `command-output`
(`gate_evidence_requirements` in `governance/guardrails.yml`), and this is the command that produces one.

Comparison, per file type:

- Python: the abstract syntax tree at both revisions, with a leading
  docstring stripped from every module, class and function body. Comments
  never enter an abstract syntax tree, so stripping the docstring is the
  whole of the work.
- Shell: the file with `#` comment text removed.
- No extension: the shebang decides. `#!...python...` takes the Python reader
  and a shell interpreter takes the shell reader, so `cli/compass` is read as
  Python and `bin/compass` as bash. See `_suffix_from_shebang`.
- YAML: every line with a `PROSE_KEYS` key's value blanked, and every
  whole-line or trailing `#` comment dropped - the same positions
  `tests/test_writing_style.py`'s `_yaml_spans` reads as prose, so the two
  halves cannot disagree about what prose is. A prose sequence item is
  blanked to one marker each, so rewording is free and adding or removing an
  item is not. Read as text, not parsed: `import yaml` outside
  `cli/compass_pkg/`, `cli/compass` or a `compass_python` heredoc does not
  resolve through this repository's one shared PyYAML mechanism
  (`tests/test_bundled_pyyaml.py`), and this script is none of those three.
- JSON: parsed structure, with `description` values blanked.
- Markdown: the contents of every fenced code block and every link target.
  A markdown file has no other behaviour.

The shell and YAML readers empty a line to remove prose from it, so they
compare the sequence of non-empty lines rather than the joined text. See
`_significant_lines`. The markdown and JSON readers cannot carry that
defect and do not use it: markdown collects the fenced lines and link
targets it cares about instead of blanking what it does not, and JSON
compares parsed structures, where neither formatting nor a line count
exists. `tests/test_writing_style.py` holds a case for each of the four, so
the two that are immune are recorded as checked rather than assumed.

`--allow-pinned-test PATH=REASON` excuses one test file entirely. The reason
is required and is printed beside the path, because an allowance nobody
explained is the same defect as a loosened matcher. The path must sit under
`tests/`, so the flag can never excuse a production file.

Exactly two things qualify, and nothing else:

1. A test whose assertion pinned wording this issue rewrites (`PBW-D6`). The
   prose and the assertion change in one commit, so the assertion change is
   not a behaviour change to find.
2. `tests/test_writing_style.py`, the mechanism file this issue's plan
   needs every batch to edit. Each batch deletes its own pending list and
   lowers `PENDING_PATHS_HIGH_WATER`, so every batch changes it. It is not
   audited surface: this issue introduced it and it has its own tests.

A production file, a test this issue merely happens to touch, or a real
behaviour change someone would rather not explain are all outside the flag.

WHAT THIS TOOL CANNOT SEE
=========================

The exit code is not a proof of no behaviour change; it is the result of the
comparisons below. `verify.architecture` rests on an architect's judgement of
the remaining differences (`DD-4`), and these are the gaps that judgement has
to cover.

- **Shell, across lines.** The comment scan reads one line at a time, so a
  quoted string or a here-document body spanning several lines is read as
  unquoted. A `#` inside such a body is taken for a comment and the text
  after it is dropped from the comparison.
- **Shell, beyond comments.** Two scripts with identical non-comment lines
  are called equal. Nothing checks that a command means what it did: a
  changed file mode, a renamed function used only by name, or a behaviour
  that depends on line numbers is invisible here.
- **YAML, one deliberate blind spot.** A prose key whose value is empty and
  whose children are a mapping keeps those children compared. That errs
  towards reporting a difference that is not one, which costs a second look
  rather than a missed change.
- **YAML, sequence items.** A prose sequence item's text is not compared at
  all, only the number of items. Rewording one is free by design, so a
  rewrite that changes what a tie-breaker actually advises is invisible here
  and only a reader can catch it.
- **YAML, read as text.** Values are compared as written, so a rewrite that
  turns a block scalar into a flow scalar reads as a change even when a
  parser would call the two identical. A quote spanning lines is read one
  line at a time, so a `#` on a continuation line is taken for a comment.
- **Markdown.** Only fenced code blocks and link targets are compared. An
  indented code block, a reference-style link definition and an HTML block
  are not read at all.
- **Python.** Only the abstract syntax tree is compared, with leading
  docstrings removed. A changed comment is invisible, which is intended, but
  so is a change that changes behaviour without changing the tree.
- **A file with no extension and no shebang** is read as shell. That is a
  fallback, not a claim about the file. Checked against every extensionless
  tracked file here: `Makefile` and `.github/CODEOWNERS` both use `#` for a
  comment, so the reader is right about them, and `VERSION` plus four
  `examples/.../current-task` files hold one line of data with no `#`. A file
  of a new shape added to that set would be read on an assumption nobody
  restated.
- **Any other file type** is reported as changed and left to the architect,
  because guessing would be worse.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The one list `tests/test_writing_style.py`'s `_yaml_spans` also reads (DD-1:
# reused, not copied - finding 1, `review-dimensions.md`, found the two
# already drifted once, on `biases`, precisely because each file held its
# own copy).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prose_keys import PROSE_KEYS  # noqa: E402

_YAML_KEY_RE = re.compile(r"^(\s*-?\s*)([\w.\-]+)\s*:\s?(.*)$")


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                           text=True, check=True).stdout


def _merge_base(cwd: Path) -> str:
    try:
        return _git(["merge-base", "HEAD", "origin/main"], cwd).strip()
    except subprocess.CalledProcessError:
        return _git(["rev-parse", "HEAD~1"], cwd).strip()


def _show(cwd: Path, rev: str, path: str) -> str | None:
    result = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=cwd,
                             capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout


def _changed_files(cwd: Path, base: str) -> list[str]:
    out = _git(["diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"], cwd)
    return [line for line in out.splitlines() if line]


_SHEBANG_LANGUAGES = (
    ("python", ".py"),
    ("bash", ".sh"),
    ("zsh", ".sh"),
    ("dash", ".sh"),
    ("ksh", ".sh"),
    ("sh", ".sh"),
)


def _suffix_from_shebang(text: str) -> str | None:
    """The suffix an extensionless file's shebang implies, or None.

    Checked against every extensionless tracked file in this repository.
    `cli/compass` is the one Python entry point and was being read as shell.
    `bin/compass` really is bash, so it was already right. The rest -
    `Makefile`, `.github/CODEOWNERS`, `VERSION` and four
    `examples/.../current-task` files - carry no shebang and keep the shell
    reader, which is a fallback rather than a claim: `Makefile` and
    `CODEOWNERS` both use `#` for a comment, so it reads them correctly, and
    the other five hold a single line of data with no `#` in it. `LICENSE` and
    `cli/vendor/LICENSE-PyYAML` never reach here, being excluded paths.

    "python" is tested before "sh" because a path can hold both, and the
    longest sensible match has to win.
    """
    first = text.split("\n", 1)[0]
    if not first.startswith("#!"):
        return None
    interpreter = first[2:].strip().lower()
    for name, suffix in _SHEBANG_LANGUAGES:
        if name in interpreter:
            return suffix
    return None


def _strip_python_docstrings(text: str) -> str | None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef))
                and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            body.pop(0)
    return ast.dump(tree)


def _significant_lines(text: str) -> list[str]:
    """The lines that carry something, with trailing whitespace dropped.

    Both strippers below remove prose by emptying the line that held it, so
    the count of empty lines is a count of removed prose and says nothing
    about behaviour. Comparing joined text counted them, and a rewrite that
    changed how many lines a comment block occupied therefore read as a
    behaviour change with no behaviour changed. Almost every rewrite moves a
    comment's line count, so that comparison reported on almost every file.

    A blank line already in the source is dropped for the same reason: it
    separates prose, and neither shell nor YAML gives it meaning. The
    remaining lines are still compared as an ordered sequence, so a command
    line that changes, moves or disappears is still a difference.
    """
    return [stripped for stripped in
            (line.rstrip() for line in text.splitlines()) if stripped]


def _strip_one_shell_comment(line: str) -> str:
    """One line, with a trailing comment removed and quoted text kept.

    A `#` opens a comment only when it starts a word and no quote is open.
    Matching ` #` by pattern instead cut `echo "tag #alpha"` down to
    `echo "tag`, so a change to the part after the hash compared equal and
    the tool missed a changed command. That is a false negative in the one
    tool whose purpose is proving no behaviour changed, which is the
    direction that costs something.

    The scan tracks single quotes, double quotes and backslash escapes, which
    is what distinguishes a comment from `$#`, `${#var}`, a hash inside a
    `sed` expression and a quoted literal. It reads one line at a time and so
    does not track a quote or a here-document body that spans lines - see the
    module docstring for what that means.
    """
    in_single = False
    in_double = False
    at_word_start = True
    i = 0
    while i < len(line):
        char = line[i]
        if in_single:
            # Nothing escapes inside single quotes, not even a backslash.
            if char == "'":
                in_single = False
            at_word_start = False
        elif in_double:
            if char == "\\" and i + 1 < len(line):
                i += 2
                at_word_start = False
                continue
            if char == '"':
                in_double = False
            at_word_start = False
        else:
            if char == "\\" and i + 1 < len(line):
                i += 2
                at_word_start = False
                continue
            if char == "#" and at_word_start:
                return line[:i].rstrip()
            if char == "'":
                in_single = True
            elif char == '"':
                in_double = True
            at_word_start = char.isspace()
        i += 1
    return line


def _strip_shell_comments(text: str) -> str:
    return "\n".join(_strip_one_shell_comment(line)
                     for line in text.splitlines())




_YAML_COMMENT_LINE_RE = re.compile(r"^\s*#")


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _strip_inline_comment(line: str) -> str:
    """Drop a `#` comment trailing real content on the same line - a plain
    sequence item such as `- agents/    # why it is exempt` is not under a
    `PROSE_KEYS` key, so `_yaml_spans` only reaches its comment through the
    whole-line walk, which a trailing comment is not. Left unhandled, a
    reworded (or deleted) trailing comment reads as the sequence item
    itself changing. No marker is left behind - a comment carries no
    behaviour whether it is present, reworded, or gone, so a line that had
    one and a line that never did must blank to the same thing. Quote-aware,
    since a `#` inside a quoted value is data, not a comment - the same
    rule YAML itself uses."""
    in_single = in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or line[i - 1].isspace():
                return line[:i].rstrip()
    return line


def _blank_yaml_prose(text: str) -> str:
    """Every line, with a `PROSE_KEYS` key's value blanked, every `#` comment
    dropped - whole-line or trailing - and a prose value's continuation lines
    collapsed into its one blanked key line. A differing line count would
    otherwise read a rewrapped paragraph as changed when every non-prose byte
    is identical. Matches what `_yaml_spans` reads as prose, so the two halves
    cannot disagree about what prose is. Read as text rather than parsed - see
    the module docstring for why - so a value's own indentation governs where
    its continuation ends.

    A trailing `#` is a comment only outside a quoted scalar, so
    `_strip_inline_comment` tracks quote state rather than refusing any line
    that holds a quote. Nothing is left in its place: a comment carries no
    behaviour whether it is present, reworded or gone, so a line that had one
    and a line that never did must blank to the same thing.

    Three shapes follow a `PROSE_KEYS` key, and they are not the same:

    - **A value on the key's own line**, whether a block indicator such as
      `>` or `|` or the first line of a plain scalar. The key line stands for
      the value and its indented continuation lines go.
    - **A sequence.** Each item blanks to one `-` marker and its wrapped
      continuation lines go, so an item can be reworded and rewrapped freely
      while the item COUNT is still compared. Deleting a tie-breaker from
      `governance/routing-policy.yml`'s `biases:` is not a rewording, and a
      reader would never see it go. An item that is itself a mapping
      (`- name: x`) is left alone, because its keys are values.
    - **A mapping.** Left entirely alone. Its keys are values, not prose, and
      swallowing them would make this tool miss the change it exists to find.
    """
    lines = []
    block_indent: int | None = None
    seq_indent: int | None = None
    for line in text.splitlines():
        if block_indent is not None:
            if line.strip() == "" or _line_indent(line) > block_indent:
                continue  # one line already stands for the whole block
            block_indent = None
        if seq_indent is not None:
            if line.strip() == "":
                continue
            if _line_indent(line) > seq_indent:
                stripped = line.strip()
                if _YAML_KEY_RE.match(line):
                    pass  # a mapping under the key, or `- key: value`
                elif stripped.startswith("-"):
                    lines.append(f"{' ' * (seq_indent + 2)}-")
                    continue  # one marker per item keeps the count compared
                else:
                    continue  # a wrapped continuation of the item above
            seq_indent = None
        if _YAML_COMMENT_LINE_RE.match(line):
            continue  # a whole-line comment carries no behaviour
        line = _strip_inline_comment(line)
        match = _YAML_KEY_RE.match(line)
        if match and match.group(2) in PROSE_KEYS:
            lines.append(f"{match.group(1)}{match.group(2)}:")
            if match.group(3).strip():
                block_indent = _line_indent(line)
            else:
                seq_indent = _line_indent(line)
        else:
            lines.append(line)
    return "\n".join(lines)


def _blank_json_descriptions(node):
    if isinstance(node, dict):
        return {k: ("" if k == "description" else _blank_json_descriptions(v))
                for k, v in node.items()}
    if isinstance(node, list):
        return [_blank_json_descriptions(v) for v in node]
    return node


_FENCE_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")
_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _markdown_behaviour(text: str) -> str:
    """Fenced content stays in document order - a fence can hold a real
    shell session or a config example where sequence is the point. Link
    targets are compared as a sorted set instead: a table row moving to fix
    a genuinely wrong position (an index that listed one entry out of
    numeric order) reorders the links `_LINK_RE` extracts even though every
    href is byte-identical, and a reader following any of them still lands
    in the same place regardless of row order. Sorting drops sensitivity to
    THAT reordering while still catching a link actually retargeted, added,
    or removed."""
    fenced: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            fenced.append(line)
    links = sorted(_LINK_RE.findall(text))
    return "\n".join(fenced) + "\n" + "\n".join(links)


def _compare_file(cwd: Path, base: str, path: str) -> str | None:
    """None if the two revisions have equal behaviour, else a reason."""
    old = _show(cwd, base, path)
    new = _show(cwd, "HEAD", path)
    if old is None:
        return None  # new file - nothing existed before it to preserve
    if new is None:
        return "deleted"
    if old == new:
        return None
    suffix = Path(path).suffix
    if suffix == "":
        # No extension, so the shebang says what the file is. Dispatching on
        # the suffix alone sent `cli/compass` - Python, with a shebang and no
        # extension - to the shell reader, which reported a docstring rewrite
        # as "a command line changed". The expensive half is the other
        # direction: a changed Python body read by a reader that cannot see a
        # Python body would have passed, in the command every adopter runs.
        suffix = _suffix_from_shebang(old) or suffix
    if suffix == ".py":
        old_ast = _strip_python_docstrings(old)
        new_ast = _strip_python_docstrings(new)
        if old_ast is None or new_ast is None:
            return "does not parse as Python"
        if old_ast != new_ast:
            return "code body changed"
        return None
    if suffix == ".sh" or suffix == "":
        if (_significant_lines(_strip_shell_comments(old))
                != _significant_lines(_strip_shell_comments(new))):
            return "a command line changed"
        return None
    if suffix in (".yml", ".yaml"):
        if (_significant_lines(_blank_yaml_prose(old))
                != _significant_lines(_blank_yaml_prose(new))):
            return "a non-prose value changed"
        return None
    if suffix == ".json":
        try:
            old_data = _blank_json_descriptions(json.loads(old))
            new_data = _blank_json_descriptions(json.loads(new))
        except json.JSONDecodeError:
            return "does not parse as JSON"
        if old_data != new_data:
            return "a non-description value changed"
        return None
    if suffix == ".md":
        if _markdown_behaviour(old) != _markdown_behaviour(new):
            return "a fenced code block or a link target changed"
        return None
    return "changed, and this tool does not know how to read this file type"


def _parse_allowances(raw: list[str]) -> tuple[dict[str, str], str | None]:
    """`PATH=REASON` pairs, or an error message naming what was wrong.

    A reason is required, and it is printed beside the path in the run's
    output. An allowance nobody explained is the same defect as a loosened
    matcher: the report goes quiet and the record does not say why.
    """
    allowances: dict[str, str] = {}
    for entry in raw:
        path, separator, reason = entry.partition("=")
        path = path.strip()
        reason = reason.strip()
        if not separator or not reason:
            return {}, (
                f"--allow-pinned-test {entry!r} states no reason - refused. "
                "Use --allow-pinned-test PATH=REASON. An allowance with no "
                "reason hides a change instead of explaining it.")
        if not path.startswith("tests/"):
            return {}, (
                f"--allow-pinned-test {path} is not under tests/ - refused.")
        allowances[path] = reason
    return allowances, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=None)
    parser.add_argument("--allow-pinned-test", action="append", default=[],
                         dest="allowed", metavar="PATH=REASON")
    args = parser.parse_args(argv)

    cwd = Path.cwd()
    allowances, error = _parse_allowances(args.allowed)
    if error is not None:
        print(error)
        return 1

    base = args.base or _merge_base(cwd)
    head = _git(["rev-parse", "HEAD"], cwd).strip()
    changed = _changed_files(cwd, base)
    print(f"base: {base}")
    print(f"head: {head}")
    print(f"files compared: {len(changed)}")

    exit_code = 0
    for path in changed:
        if path in allowances:
            print(f"  {path}: allowed - {allowances[path]}")
            continue
        reason = _compare_file(cwd, base, path)
        if reason is not None:
            print(f"  {path}: {reason}")
            exit_code = 1
    unused = sorted(set(allowances) - set(changed))
    for path in unused:
        print(f"  {path}: allowed but not in the diff - the allowance did "
              f"nothing")
    if exit_code == 0:
        print("no changed file altered behaviour")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
