#!/usr/bin/env python3
# =============================================================================
# scripts/voice-tells.py - an advisory grep for the three writing-voice tells
# a fixed string can find.
# =============================================================================
# The reference at skills/compass-runtime/writing-voice.md names nine habits
# that make Compass session prose narrate the framework instead of
# communicating a decision. Six of those need a reader. Three do not: "I will
# now proceed", "Upon completion", "utilize" - and this script greps exactly
# those three, over one issue's markdown artifacts, so a reviewer has
# something to glance at before reading closely.
#
# USAGE
#   scripts/voice-tells.py [PATH ...]
#
#   No arguments: scan every *.md file under the current issue's directory,
#   .compass/work/<slug>/, where <slug> is read from .compass/current-task
#   (resolved by walking up from the current directory to find .compass/).
#   With arguments: scan exactly those files and directories instead.
#
# NEEDLES
#   Matched case-insensitively on a word boundary - \bUTILIZE\b does not
#   match "utilizes" or "utilization", by design:
#       I will now proceed
#       Upon completion
#       utilize
#
#   Fenced code blocks and blockquotes are blanked (not dropped, so reported
#   line numbers stay true to the file) before matching - the same rule
#   `compass plan lint` uses, because every document that explains this
#   check has to quote the strings it looks for.
#
# EXIT CODE
#   0. Always - including when there is no current issue to resolve, and
#   including when a given path does not exist (a mistyped path is reported
#   as "nothing found there", never raised). This is advisory: it is
#   registered in no `guardrails.yml` entry, and moves no gate. Judge each
#   hit; a quotation is not a defect.
# =============================================================================
from __future__ import annotations

import os
import re
import sys

TELLS = [
    "I will now proceed",
    "Upon completion",
    "utilize",
]

_NEEDLE_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in TELLS) + r")\b",
    re.IGNORECASE,
)


def _scannable_lines(text):
    """Yield (lineno, text), with fenced code blocks and blockquotes blanked.

    Blanked rather than dropped, so a reported line number still points the
    reader at the right line. Borrowed from compass plan lint's
    _plan_lint_scannable in cli/compass_pkg/policy.py.
    """
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            yield lineno, ""
            continue
        if in_fence or stripped.startswith(">"):
            yield lineno, ""
            continue
        yield lineno, line


def _hits_in_file(path):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        return []
    hits = []
    for lineno, line in _scannable_lines(text):
        for match in _NEEDLE_RE.finditer(line):
            hits.append((path, lineno, match.group(0)))
    return hits


def _find_upwards(start, name):
    """The nearest ancestor of `start` (inclusive) containing `name`, or
    None. Same walk-up rule the CLI uses to find a project's .compass/."""
    current = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(current, name)):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _markdown_under(directory):
    files = []
    for dirpath, _dirnames, filenames in os.walk(directory):
        for name in sorted(filenames):
            if name.endswith(".md"):
                files.append(os.path.join(dirpath, name))
    return sorted(files)


def _default_scope():
    """(files, label) for the current issue's markdown artifacts.

    Returns ([], None) whenever any link in the chain is missing - no
    project, no pointer, no slug, no issue directory. There is no current
    issue to resolve; the script still runs and still exits 0.
    """
    project = _find_upwards(os.getcwd(), ".compass")
    if not project:
        return [], None
    pointer = os.path.join(project, ".compass", "current-task")
    if not os.path.isfile(pointer):
        return [], None
    try:
        with open(pointer, encoding="utf-8") as fh:
            slug = fh.read().strip()
    except (OSError, UnicodeDecodeError):
        # An unreadable or non-UTF-8 pointer is treated the same as a
        # missing one - there is no current issue to resolve, not a crash.
        # The contract is exit 0, always; this is the pointer-read half of
        # the same guard _hits_in_file already applies to a markdown file.
        return [], None
    if not _safe_slug(slug):
        return [], None
    issue_dir = os.path.join(project, ".compass", "work", slug)
    if not os.path.isdir(issue_dir):
        return [], None
    return _markdown_under(issue_dir), issue_dir


def _safe_slug(slug):
    """Is `slug` a bare directory name - no path separator, no ".." or "."?

    The slug comes from a file the user (or another tool) writes, and it is
    about to be joined onto a directory path. Without this, an absolute
    slug replaces the whole prefix (os.path.join("/a/b", "/etc") == "/etc")
    and a "../" slug walks out of the work directory - a default-scoped run
    would then report a path outside the current issue directory, which is
    exactly what TRC-F2 says never happens.
    """
    if not slug or slug in (".", ".."):
        return False
    return os.path.basename(slug) == slug


def _explicit_scope(paths):
    """Every markdown file named or contained by the given paths.

    A path that is neither a file nor a directory is skipped, not raised -
    the single exit code means a mistyped path is reported as "nothing
    found there", never a crash.
    """
    files = []
    for p in paths:
        if os.path.isdir(p):
            files.extend(_markdown_under(p))
        elif os.path.isfile(p):
            files.append(p)
    return sorted(files)


def main(argv):
    if argv:
        files = _explicit_scope(argv)
        where = ", ".join(argv)
    else:
        files, issue_dir = _default_scope()
        where = issue_dir or "no current issue"

    all_hits = []
    for f in files:
        all_hits.extend(_hits_in_file(f))

    if not all_hits:
        print(
            f"voice tells: clean - no findable tell in {len(files)} "
            f"markdown file(s) under {where}"
        )
        return 0

    print(f"voice tells: {len(all_hits)} possible tell(s) in {where} [advisory]")
    for path, lineno, needle in all_hits:
        print(f'  {path}:{lineno}: "{needle}"')
    print()
    print(
        "  Advisory, not a gate - this exits 0, moves no gate, and is "
        "registered in no guardrail. Judge each hit; a quotation is not a "
        "defect."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
