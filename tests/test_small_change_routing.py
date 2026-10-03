"""A small, contained change to new code gets the quick-fix process, and a
heavier result names the dimension that caused it.

In the comparison eval run of 30 September (spec B10), a session rated a new function in an existing module
`greenfield`, which the rubric defines as net-new code with no behaviour to
preserve. The quick-fix shape accepted only `brownfield-mapped`, so the
session got the full feature process, stopped to ask, and wrote nothing.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


def _evaluate(**assessment):
    args = []
    for key, value in assessment.items():
        args += ["--assessment", f"{key}={value}"]
    r = subprocess.run([sys.executable, str(CLI), "approach", "evaluate",
                        "--json", *args], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["delivery_approach"]


def test_a_small_contained_greenfield_change_is_a_quick_fix():
    assert _evaluate(risk="contained", familiarity="greenfield", size="small",
                     goal="delivery") == "quick-fix"


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=root, check=True)
    return root


def test_a_heavier_result_names_the_dimension_that_blocked_the_quick_fix(repo):
    r = subprocess.run(
        [sys.executable, str(CLI), "quick-fix", "start", "tidy-config",
         "--risk", "cross-cutting - every command reads the configuration",
         "--familiarity", "brownfield-unmapped - its behaviour is not pinned by tests",
         "--size", "small - one function and its tests",
         "--intent", "parse_config is easier to read",
         "--scenario", "Given the settings file, when it is parsed, then nothing changes",
         "--test", "tests/test_config.py"],
        cwd=repo, capture_output=True, text=True)
    out = r.stdout + r.stderr
    assert r.returncode == 1, out
    assert "blocked: risk is cross-cutting; the quick fix needs " \
        "trivial or contained" in out, out
    assert '/compass:assess --reassess --reason "..."' in out, out
    # A fired rule is named by its reason, with the id in brackets.
    assert re.search(r"\w.* \(RP-FLOOR-002, \w+\)", out), out
    # The terminal cuts a line at 100 characters; nothing may be lost.
    assert "\u2026" not in out and not any(len(line) > 100 for line in out.splitlines()), out


def test_a_long_slug_and_a_wrapped_rule_reach_the_reader_whole(repo):
    r = subprocess.run(
        [sys.executable, str(CLI), "quick-fix", "start",
         "refactor-the-configuration-parser-into-helpers",
         "--risk", "cross-cutting - every command reads the configuration",
         "--familiarity", "brownfield-unmapped - its behaviour is not pinned by tests",
         "--size", "small - one function and its tests",
         "--intent", "parse_config is easier to read",
         "--scenario", "Given the settings file, when it is parsed, then nothing changes",
         "--test", "tests/test_config.py"],
        cwd=repo, capture_output=True, text=True)
    out = r.stdout + r.stderr
    assert "…" not in out and not any(len(line) > 100 for line in out.splitlines()), out
    assert "refactor-the-configuration-parser-into-helpers" in out, out
    assert "(RP-REQUIRE-003, requirement)" in out, out
    assert "is None" not in out and "labels_any" not in out, out
