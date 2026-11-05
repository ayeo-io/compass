"""A small, contained change to new code gets the quick-fix process, and a
heavier result names the dimension that caused it.

In the comparison eval run of 30 September (spec B10), a session rated a new function in an existing module
`greenfield`, which the rubric defines as net-new code with no behaviour to
preserve. The quick-fix shape accepted only `brownfield-mapped`, so the
session got the full feature process, stopped to ask, and wrote nothing.

The four-stage path (ADR-092) has no approaches, so the old evaluator is
tested on the 8.0.4 governance copy (`compat_baseline.policy_8_0_4`), and the
same change on the path owes the light evidence row. On the path the quick fix
no longer refuses heavier work: it starts the change and names the evidence it
owes.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


GREENFIELD = {"risk": "contained", "familiarity": "greenfield", "size": "small",
              "goal": "delivery", "urgency": "none", "labels": []}


def _evaluate(**assessment):
    """The approach the 8.x evaluator gives, read from the 8.0.4 governance copy."""
    from compass_pkg import routing
    from compat_baseline import policy_8_0_4
    return routing.evaluate_route(assessment, policy_8_0_4())["delivery_approach"]


def test_a_small_contained_greenfield_change_is_a_quick_fix():
    assert _evaluate(**GREENFIELD) == "quick-fix"


def test_on_the_path_a_small_contained_greenfield_change_owes_the_light_row():
    """The path twin: the 8.x quick fix is the light evidence row (ADR-092)."""
    from compass_pkg import evidence_required
    from compass_pkg.core import load_yaml
    policy = load_yaml(str(ROOT / "governance" / "routing-policy.yml"))
    result = evidence_required.evaluate(GREENFIELD, policy)
    assert result["delivery_approach"] == "delivery"
    assert result["rules_fired"] == ["RP-EVID-LIGHT"], result["rules_fired"]
    assert result["gates"] == ["verify.correctness", "verify.governance",
                               "verify.traceability"]


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=root, check=True)
    return root


def _start_heavier(root, slug):
    return subprocess.run(
        [sys.executable, str(CLI), "quick-fix", "start", slug,
         "--risk", "cross-cutting - every command reads the configuration",
         "--familiarity", "brownfield-unmapped - its behaviour is not pinned by tests",
         "--size", "small - one function and its tests",
         "--intent", "parse_config is easier to read",
         "--scenario", "Given the settings file, when it is parsed, then nothing changes",
         "--test", "tests/test_config.py"],
        cwd=root, capture_output=True, text=True)


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
    assert r.returncode == 0, out
    # The terminal cuts a line at 100 characters; nothing may be lost. Two lines are
    # printed whole whatever their length, so a reader can copy them: the `next:`
    # command (ADR-092 decision 8) and the path of the acceptance criteria, which
    # holds the long slug.
    lines = [ln for ln in out.splitlines()
             if not ln.startswith("next: ") and not ln.strip().startswith("record : ")]
    assert "…" not in out and not any(len(line) > 100 for line in lines), out
    assert out.splitlines()[-1].startswith("next: "), out
    assert "refactor-the-configuration-parser-into-helpers" in out, out
    assert "is None" not in out and "labels_any" not in out, out
    # On the path start prints no fired rule; the wrapped rule reaches the reader
    # through `approach evaluate`, cut nowhere.
    shown = subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--issue",
         "refactor-the-configuration-parser-into-helpers", "--verbose"],
        cwd=repo, capture_output=True, text=True)
    assert "(RP-REQUIRE-003, evidence)" in shown.stdout, shown.stdout + shown.stderr
    assert "…" not in shown.stdout, shown.stdout


def test_on_the_path_heavier_work_is_started_and_owes_more_evidence(repo):
    """ADR-092 decision: the quick fix no longer refuses heavier work, so there is
    no blocked dimension to name. The dimension shows as the evidence it adds, each
    with the rule that fired."""
    import yaml
    slug = "refactor-the-configuration-parser-into-helpers"
    r = _start_heavier(repo, slug)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert slug in out, out
    assert "is None" not in out and "labels_any" not in out, out
    m = yaml.safe_load((repo / ".compass" / "work" / slug / "manifest.yml").read_text())
    assert m["delivery_approach"] == "delivery" and "stages" not in m
    # Cross-cutting risk owes the standard row and the architecture review.
    assert "architecture" in m["evidence_required"]
    assert "definition-of-done" in m["evidence_required"]
    fired = {f["id"]: f for f in m["policy_rules_fired"]}
    assert {"RP-EVID-STANDARD", "RP-REQUIRE-003", "RP-FLOOR-002"} <= set(fired), fired
    # A fired rule keeps its reason.
    assert all(f["rationale"] for f in fired.values()), fired
