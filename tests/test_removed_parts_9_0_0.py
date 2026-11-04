"""What 9.0.0 removed with the stage agents, and how an old record or call reads.

ADR-090 removes the stage agents, the multiagent breakdown, model tiers,
effort per dispatch, execution profiles and the headless runner. A command
line, a project file or a stored record can still name one of them:

- a removed verb or flag fails to parse, and the error names the removal;
- a removed `compass.yml` key is read as before and `compass policy lint`
  names it;
- a stored generation that lists the removed check reports it as nothing to
  check, so no archived issue goes from pass to fail.

Issue: ayeo-io/compass-delivery#352.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))


def _run(args, cwd):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=60)


# --- a removed verb or flag -------------------------------------------------------

REMOVED_CALLS = [
    ["run", "demo", "--stage", "implement", "--stop-file", "stop"],
    ["issue", "subtask", "add", "subtask-1", "--brief", "b.md"],
    ["profile", "show", "default"],
    ["approach", "show", "--model", "implement"],
    ["approach", "show", "--effort", "verify"],
    ["retro", "--models"],
]


@pytest.mark.parametrize("argv", REMOVED_CALLS, ids=lambda a: " ".join(a[:2]))
def test_a_removed_verb_or_flag_names_its_removal(tmp_path, argv):
    proc = _run(argv, tmp_path)
    assert proc.returncode == 2, proc.stderr
    assert "removed in 9.0.0" in proc.stderr, proc.stderr
    assert "ADR-090" in proc.stderr, proc.stderr


def test_a_kept_verb_that_fails_to_parse_gets_no_removal_line(tmp_path):
    proc = _run(["approach", "show", "--no-such-flag"], tmp_path)
    assert proc.returncode == 2
    assert "removed in 9.0.0" not in proc.stderr


def test_the_removal_line_matches_tokens_not_prefixes():
    from compass_pkg import removed_parts
    assert removed_parts.line_for(["running"]) is None
    assert removed_parts.line_for(["issue", "subtasks"]) is None
    assert removed_parts.line_for(["approach", "show", "--models"]) is None
    assert "compass run" in removed_parts.line_for(["run", "x"])
    assert "--model" in removed_parts.line_for(["approach", "show", "--issue", "s",
                                                 "--model", "implement"])


# --- a removed compass.yml key -----------------------------------------------------

def _lint_project(layer):
    from compass_pkg import policy_lint
    from compass_pkg.layers import Layer
    sys.path.insert(0, str(ROOT / "tests"))
    import classifier_fixtures
    parent = Layer("default", "parent", {"schema": 1, **classifier_fixtures.base()}, "d")
    project = Layer("project", "project", {"schema": 1, **layer}, "d")
    return policy_lint.lint_chain(parent, project)


@pytest.mark.parametrize("key,value", [
    ("models", {"strong": "inherit", "standard": "sonnet"}),
    ("multiagent", {"worktree_root": "../wt", "max_worktrees": 4}),
])
def test_a_removed_setting_is_read_and_lint_names_it(key, value):
    report = _lint_project({key: value})
    found = [f for f in report.findings if f.code == "L-SETTING-REMOVED"]
    assert len(found) == 1, [(f.code, f.path) for f in report.findings]
    assert found[0].level == "warning" and found[0].path == key
    assert "removed in 9.0.0" in found[0].message and "ADR-090" in found[0].message
    assert not [f for f in report.findings if f.level == "error"], report.findings


def test_a_project_with_no_removed_setting_gets_no_removal_finding():
    report = _lint_project({"owner": "someone"})
    assert not [f for f in report.findings if f.code == "L-SETTING-REMOVED"]


# --- a stored generation that lists the removed check --------------------------------

def test_the_removed_check_is_in_the_removed_table_with_no_replacement():
    from compass_pkg.check_registry import REGISTRY, REMOVED
    removed = REMOVED["multiagent-run-recorded"]
    assert "multiagent-run-recorded" not in REGISTRY
    assert removed.removed_in == "9.0.0" and removed.replaced_by is None
    assert removed.detail.startswith("nothing to check")
    assert "9.0.0" in removed.detail and "runs in its place" not in removed.detail


def test_a_guardrail_that_lists_the_removed_check_gains_no_replacement():
    from compass_pkg.check_cmd import _with_replacements
    names = ["gate-evidence-present", "multiagent-run-recorded"]
    assert _with_replacements(names, {}) == names


def test_lint_accepts_an_old_copy_that_names_the_removed_check():
    from compass_pkg.policy_lint import _removed_check_note
    note = _removed_check_note("checks.multiagent-run-recorded", "unknown check")
    assert "removed in 9.0.0" in note and "None" not in note
