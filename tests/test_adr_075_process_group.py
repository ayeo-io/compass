"""ADR-075 corrects ADR-061 decision 5 and the issue_detail docstring names its imports (TRC-001)."""
from __future__ import annotations

import ast
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import readiness_run  # noqa: E402

DECISIONS = ROOT / "architecture" / "decisions"
ADR_075 = next(iter(DECISIONS.glob("ADR-075-*.md")), None)
ADR_061 = next(DECISIONS.glob("ADR-061-*.md"))
ISSUE_DETAIL = ROOT / "cli" / "compass_pkg" / "issue_detail.py"

# ADR-061 is an accepted record on main: a correction is a new entry, so its bytes never change.
ADR_061_SHA256 = "69bcf8d7361501888463bb4e68ce0d35e81edbd7a6beba3c933d6354eed4accc"


def _record_text(path):
    return path.read_text(encoding="utf-8")


def check_record(text, grace):
    """Return what the record text lacks; an empty list means it is sound."""
    missing = []
    if not re.search(r"^status: accepted$", text, re.M):
        missing.append("status accepted")
    for word in ("SIGTERM", "SIGKILL", "ADR-061"):
        if word not in text:
            missing.append(word)
    if f"`STOP_GRACE_SECONDS` is {grace}" not in text:
        missing.append("grace value")
    for path_word in ("normal exit", "time limit", "interrupt", "error"):
        if path_word not in text:
            missing.append(path_word)
    if "before the temporary worktree is removed" not in text:
        missing.append("worktree order")
    if "does not supersede" not in text:
        missing.append("amends, not supersedes")
    return missing


def test_the_record_states_the_stop_sequence_on_every_exit_path():
    assert ADR_075 is not None, "ADR-075 does not exist"
    assert check_record(_record_text(ADR_075), readiness_run.STOP_GRACE_SECONDS) == []


def test_the_check_reports_a_record_that_drops_sigkill():
    text = _record_text(ADR_075).replace("SIGKILL", "KILL")
    assert "SIGKILL" in check_record(text, readiness_run.STOP_GRACE_SECONDS)


def test_the_index_lists_the_record_as_accepted():
    index = _record_text(DECISIONS / "README.md")
    row = [line for line in index.splitlines() if line.startswith("| [ADR-075]")]
    assert len(row) == 1
    assert "| accepted |" in row[0]
    assert "ADR-061" in row[0]


def test_adr_061_is_unchanged():
    assert hashlib.sha256(ADR_061.read_bytes()).hexdigest() == ADR_061_SHA256


def _imported_compass_modules(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "compass_pkg":
            names.update(alias.name for alias in node.names)
    return names


def test_the_issue_detail_docstring_names_every_compass_import_and_no_other():
    source = ISSUE_DETAIL.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = _imported_compass_modules(tree)
    doc = ast.get_docstring(tree)
    comment = next(line for line in source.splitlines() if line.startswith("# DEPENDENCY"))
    comment = comment + " " + source.split("# DEPENDENCY", 1)[1].split("from __future__", 1)[0]
    leaf_sentence = doc.split("This module is a leaf:", 1)[1]
    named = set(re.findall(r"`(\w+)`", leaf_sentence.split("and none")[0]))
    assert named == imported, (named, imported)
    for module in imported:
        assert module in comment, module
    for stale in ("next_cmd", "stable_ids"):
        assert stale not in comment
        assert stale not in leaf_sentence
