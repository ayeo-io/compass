"""The legacy readers stay until 8.0.0, and no live file says otherwise
(issue `release-7-0-0-prep`).

Scenario ids: `TRC-015` to `TRC-018` in release-7-0-0-prep/acceptance-criteria.md.

The scan reads tracked files only. A line that promises an old form until 7.0.0
carries the allow marker `legacy-date-scan: allow - <reason>` when the promise
is still true, such as a notice string that cannot print with an empty alias
table. The marker covers the line it is on and nothing else.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"

ADVISORY = "the old word is read until 9.0.0"
SIZE_NOTICE = "compass: size standard is now medium; the old word is read until 9.0.0."

SCANNED_ROOTS = ("cli/", "docs/", "governance/", "skills/", "commands/", "agents/")
SKIPPED = ("governance/decisions/", "architecture/decisions/", "docs/system-spec.md", "tests/")

MARKER = re.compile(r"legacy-date-scan: allow - \S")

# A reader or a command spelling that is read, works or is removed "until" or
# "at" 7.0.0. The sentences that state what 7.0.0 itself removes or starts
# ("from 7.0.0", "ticked on the page before 7.0.0", "retired_in: 7.0.0") do not match.
PATTERNS = [
    re.compile(r"\b(read|reads|works?|working|stays?|kept|keeps|accepted)\b[^\n]*?\buntil 7\.0\.0", re.S),
    re.compile(r"\buntil 7\.0\.0 removes\b"),
    re.compile(r"\b7\.0\.0 (stops reading|refuses it|refuses an old)\b"),
    re.compile(r"\b(views?|readers?|adapter)\b[^\n]{0,60}\bat 7\.0\.0\b"),
    re.compile(r"\b(read|reads|works?|working|stays?|kept|keeps)\b[^\n]*?\bthrough 6\.x\b", re.S),
]


def scan_text(text):
    """The 1-based numbers of the lines that promise an old form until 7.0.0.

    A sentence wrapped over two lines is read as one; the line where the match
    ends is the one reported, and it is the line the marker must be on."""
    lines = text.splitlines()
    hits = []
    for number, line in enumerate(lines, 1):
        if MARKER.search(line):
            continue
        previous = lines[number - 2].strip() if number > 1 else ""
        joined = (previous + " " + line.strip()).strip()
        offset = len(previous) + 1 if previous else 0
        for pattern in PATTERNS:
            if any(m.end() > offset for m in pattern.finditer(joined)):
                hits.append(number)
                break
    return hits


def scan_files(paths):
    """`(path, line number, line)` for each hit in the text files `paths`."""
    found = []
    for path in paths:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        lines = text.splitlines()
        for number in scan_text(text):
            found.append((str(path), number, lines[number - 1].strip()))
    return found


def live_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                         check=True).stdout.splitlines()
    chosen = []
    for rel in out:
        if rel.startswith(SKIPPED) or rel == "docs/system-spec.md":
            continue
        if rel.startswith(SCANNED_ROOTS) or ("/" not in rel and rel.endswith(".md")):
            if (ROOT / rel).is_file():
                chosen.append(ROOT / rel)
    return chosen


def _cli(root, *args):
    env = dict(os.environ)
    env.pop("COMPASS_ISSUE", None)
    env["GIT_CEILING_DIRECTORIES"] = str(Path(root).parent)
    env["COMPASS_OFFLINE"] = "1"
    return subprocess.run([sys.executable, str(CLI), *args], cwd=str(root),
                          capture_output=True, text=True, env=env, timeout=120)


def test_the_lint_advisory_says_8_0_0(tmp_path):
    """Scenario id: `TRC-015` in release-7-0-0-prep/acceptance-criteria.md."""
    (tmp_path / ".compass").mkdir()
    (tmp_path / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@6\n\n"
        "approaches:\n  regular:\n    set:\n      stages: {plan: \"full\"}\n",
        encoding="utf-8")
    subprocess.run(["git", "init", "--quiet", "-b", "main"], cwd=tmp_path, check=True)
    result = _cli(tmp_path, "policy", "lint")
    lines = [line for line in result.stderr.splitlines() if line.startswith("advisory:")]
    assert lines, result.stdout + result.stderr
    assert all(line.endswith(ADVISORY) for line in lines), lines


def test_the_size_notice_says_8_0_0():
    """Scenario id: `TRC-016` in release-7-0-0-prep/acceptance-criteria.md."""
    result = _cli(ROOT, "approach", "evaluate", "--assessment", "risk=contained",
                  "--assessment", "familiarity=brownfield-mapped",
                  "--assessment", "size=standard", "--json")
    assert result.returncode == 0, result.stderr
    assert SIZE_NOTICE in result.stderr.splitlines(), result.stderr


def test_no_live_file_promises_an_old_form_until_7_0_0():
    """Scenario id: `TRC-017` in release-7-0-0-prep/acceptance-criteria.md."""
    found = scan_files(live_files())
    shown = [f"{Path(p).relative_to(ROOT)}:{n}: {line[:120]}" for p, n, line in found]
    assert shown == [], "\n".join(shown)


def test_the_scan_reports_a_planted_line(tmp_path):
    """Scenario id: `TRC-018` in release-7-0-0-prep/acceptance-criteria.md."""
    bare = tmp_path / "bare.md"
    bare.write_text("Intro.\n\nthe old word is read until 7.0.0\n", encoding="utf-8")
    marked = tmp_path / "marked.md"
    marked.write_text(
        "Intro.\n\nthe old word is read until 7.0.0 "
        "<!-- legacy-date-scan: allow - a planted line -->\n", encoding="utf-8")
    found = scan_files([bare, marked])
    assert [(Path(p).name, n) for p, n, _ in found] == [("bare.md", 3)]


def test_a_marker_without_a_reason_does_not_hide_a_line(tmp_path):
    """The marker needs a reason; a bare marker hides nothing."""
    path = tmp_path / "bare_marker.md"
    path.write_text("the old word is read until 7.0.0 legacy-date-scan: allow -\n",
                    encoding="utf-8")
    assert len(scan_files([path])) == 1


def test_the_scan_reads_a_sentence_wrapped_over_two_lines(tmp_path):
    path = tmp_path / "wrapped.md"
    path.write_text("The old spelling keeps working\nuntil 7.0.0 and then ends.\n",
                    encoding="utf-8")
    assert [n for _, n, _ in scan_files([path])] == [2]


def test_the_scan_leaves_the_true_sentences_alone(tmp_path):
    path = tmp_path / "true.md"
    path.write_text(
        "ticked on the page before 7.0.0 (EV-1)\n"
        "From 7.0.0 the shipped trigger is the four labels.\n"
        "RP-ROLE-001: {replaced_by: RP-ART-001, retired_in: 7.0.0}\n"
        "The spelling was removed at 7.0.0.\n", encoding="utf-8")
    assert scan_files([path]) == []
