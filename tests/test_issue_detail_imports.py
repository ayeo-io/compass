"""The issue_detail docstring names its imports (TRC-001 of ADR-075).

The test moved here from the ADR-075 process-group test file when 9.0.0
removed `compass readiness` and the readiness runner, which that file checked
against ADR-075 (ADR-093). `issue_detail.py` stays, so its docstring check
stays.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISSUE_DETAIL = ROOT / "cli" / "compass_pkg" / "issue_detail.py"


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
