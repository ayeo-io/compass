"""Every `compass <subcommand>` shown in the docs must be a real subcommand.

An instruction to run `compass frame --reassess` looked runnable and was
not: there is no `frame` subcommand, and reassessment is the slash command
`/compass:assess --reassess`. Which is worse than no instruction: the
reader tries it, gets an argparse error, and loses confidence in the rest
of the page.

This scans code spans and fenced blocks (not prose, where "compass" is the
framework's name rather than a command) across every documented surface.
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPASS_CLI = ROOT / "cli" / "compass"

SEARCH_DIRS = ("skills", "commands", "docs", "routes", "governance", "templates")

# Proposals and analyses argue for commands that do not exist yet, or compare
# Compass to other tools - naming a hypothetical command is the point there.
# This test covers the surfaces that tell a reader what to run *today*.
EXCLUDED_DIRS = ("docs/proposals", "docs/analysis", "docs/compass/")

# `compass --help` renders positional choices as {a,b,c}; anything else after
# `compass` in a code span is either a global flag or a typo.
GLOBAL_FLAGS = {"--help", "-h", "--version"}

INVOCATION_RE = re.compile(r"\bcompass\s+(--?[a-zA-Z-]+|[a-z][a-z0-9-]*)")
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
FENCE_RE = re.compile(r"^```.*?^```", re.M | re.S)


def _subcommands():
    out = subprocess.run(
        [sys.executable, str(COMPASS_CLI), "--help"],
        capture_output=True, text=True, check=True, timeout=30,
    ).stdout
    m = re.search(r"\{([a-zA-Z0-9_,\-]+)\}", out)
    assert m, f"could not parse subcommands from --help:\n{out}"
    return set(m.group(1).split(","))


def _markdown_files(root=ROOT):
    # Only what git tracks: an untracked planning file on one machine may
    # name a verb that is planned, not shipped, and no reader sees it.
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root,
                         capture_output=True, text=True, check=True).stdout
    tracked = {p for p in out.split("\0") if p}
    files = [root / "CLAUDE.md", root / "README.md"]
    for d in SEARCH_DIRS:
        files += sorted((root / d).rglob("*.md"))
    return [
        f for f in files
        if f.exists() and f.relative_to(root).as_posix() in tracked
        and not any(f.relative_to(root).as_posix().startswith(d) for d in EXCLUDED_DIRS)
    ]


# A line carrying the repository's `vocabulary-scan: allow` marker is exempt,
# for the same reason the vocabulary scan honours it: a page that RECORDS a
# removal has to name the removed spelling, or a reader whose script broke
# cannot match the error they got to the row that fixes it. Recording is not
# teaching.
#
# The REASON is mandatory, and the pattern is the vocabulary scan's own, so
# the two stay identical. A bare `vocabulary-scan: allow` with nothing after
# it would be an unconditional skip - any line in any live document could
# silence this guard, with no reason and no count.
#
# Counted as well as reasoned, but counted in ONE place: the ceiling lives in
# `tests/test_docs_prose.py::test_the_allow_marker_list_stays_short`, which
# reads the same surfaces. Two ceilings would be two numbers to keep in step.
# `grep -rn "vocabulary-scan: allow" .` enumerates every marker with its
# reason.
#
# Imported rather than defined: see tests/allow_marker.py.
from allow_marker import ALLOW_MARKER_RE  # noqa: E402


def _invocations(text):
    """Yield every `compass <word>` inside a code span or fenced block."""
    for fence in FENCE_RE.findall(text):
        for line in fence.splitlines():
            if ALLOW_MARKER_RE.search(line):
                continue
            line = line.lstrip("$ ").strip()
            if line.startswith("compass "):
                yield from INVOCATION_RE.findall(line)[:1]
    # Code spans are matched without their surrounding line, so an exempt
    # line is skipped by removing it before the spans are read.
    outside = "\n".join(l for l in FENCE_RE.sub("", text).splitlines()
                        if not ALLOW_MARKER_RE.search(l))
    for span in CODE_SPAN_RE.findall(outside):
        span = span.strip()
        if span.startswith("compass "):
            yield from INVOCATION_RE.findall(span)[:1]


def test_every_documented_compass_invocation_is_a_real_subcommand():
    known = _subcommands() | GLOBAL_FLAGS
    bad = []
    for path in _markdown_files():
        for word in _invocations(path.read_text(encoding="utf-8")):
            if word not in known:
                bad.append(f"{path.relative_to(ROOT)}: `compass {word}`")
    assert not bad, (
        "These docs tell the reader to run a subcommand that does not exist:\n  "
        + "\n  ".join(sorted(set(bad)))
        + f"\n\nReal subcommands: {', '.join(sorted(_subcommands()))}"
    )
