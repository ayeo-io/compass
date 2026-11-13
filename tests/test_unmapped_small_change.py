"""A small change on unmapped ground gets advice, not a floor.

In the comparison run of 30 Sep 2026
(docs/compass/2026-09-30-eval-comparison-discriminating.md), two of the three
stops followed a small, contained change rated brownfield-unmapped: the
small-change shape left it out and the unmapped-familiarity floor
(`RP-FLOOR-002`) sent it to define at thorough weight. Such a change now gets no
blocking question, and unfamiliar ground becomes advice. Critical risk and
the four domain labels keep their floors (issue #324).

Scenario ids: UA-1 and UA-2; the other two tests are regression checks (issue `unmapped-small-change-advisory`).

The four-stage path (ADR-092) has no approaches and no stage modes. The 8.x
rules are tested on the 8.0.4 governance copy (`compat_baseline.policy_8_0_4`),
and each has a path twin that reads `evidence_required.evaluate` on the live
default: the floor and the advice keep their rules, and an approach or a stage
mode becomes the evidence owed.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from check_set_files import view as shipped_view  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


def _readings(readings):
    """The assessment the evaluators take: `intent` is the old name of `goal`, and
    `labels` is a comma-separated list, as `--assessment` takes it."""
    out = {"urgency": "none", "labels": []}
    for key, value in readings.items():
        if key == "labels":
            out["labels"] = value.split(",")
        else:
            out["goal" if key == "intent" else key] = value
    return out


def _evaluate(**readings):
    """What the 8.x evaluator gives, on the 8.0.4 governance copy."""
    from compass_pkg import routing
    from compat_baseline import policy_8_0_4
    return routing.evaluate_route(_readings(readings), policy_8_0_4())


def _owed(**readings):
    """What the same assessment owes on the path, under the live default."""
    from compass_pkg import evidence_required
    from compass_pkg.core import load_yaml
    policy = shipped_view("routing-policy.yml")
    return evidence_required.evaluate(_readings(readings), policy)


def _fired(result):
    return [f["id"] for f in result["policy_rules_fired"]]


@pytest.mark.parametrize("size", ["atomic", "small"])
@pytest.mark.parametrize("risk", ["trivial", "contained"])
def test_ua_1_a_small_unmapped_change_gets_the_mapped_route(size, risk):
    unmapped = _evaluate(risk=risk, familiarity="brownfield-unmapped",
                         size=size, intent="delivery")
    mapped = _evaluate(risk=risk, familiarity="brownfield-mapped",
                       size=size, intent="delivery")
    assert unmapped["delivery_approach"] == mapped["delivery_approach"]
    assert "RP-FLOOR-002" not in _fired(unmapped)
    assert "behavior-mapping" not in unmapped["required_skills"]
    advice = [s["strategy"] for s in unmapped["applicable_strategies"]]
    assert "behavior-mapping" in advice, advice


@pytest.mark.parametrize("size", ["atomic", "small"])
@pytest.mark.parametrize("risk", ["trivial", "contained"])
def test_ua_1_on_the_path_a_small_unmapped_change_owes_what_a_mapped_one_owes(size, risk):
    unmapped = _owed(risk=risk, familiarity="brownfield-unmapped", size=size,
                     intent="delivery")
    mapped = _owed(risk=risk, familiarity="brownfield-mapped", size=size,
                   intent="delivery")
    assert unmapped["evidence_required"] == mapped["evidence_required"]
    assert unmapped["gates"] == mapped["gates"]
    assert "RP-FLOOR-002" not in unmapped["rules_fired"]
    assert "atdd" not in unmapped["required_skills"]
    advice = [s["strategy"] for s in unmapped["applicable_strategies"]]
    assert "atdd" in advice, advice


FLOOR_READINGS = [
    {"risk": "contained", "size": "medium"},
    {"risk": "contained", "size": "large"},
    {"risk": "cross-cutting", "size": "small"},
    {"risk": "critical", "size": "atomic"},
    {"risk": "contained", "size": "small", "labels": "auth"},
    {"risk": "trivial", "size": "atomic", "labels": "migrations"},
]


@pytest.mark.parametrize("readings", FLOOR_READINGS)
def test_the_floor_still_applies_beyond_small_unlabelled_work(readings):
    result = _evaluate(familiarity="brownfield-unmapped", intent="delivery",
                       **readings)
    assert "RP-FLOOR-002" in _fired(result)
    assert result["stages"].get("define") == "thorough"
    assert "behavior-mapping" in result["required_skills"]


@pytest.mark.parametrize("readings", FLOOR_READINGS)
def test_on_the_path_the_floor_still_applies_beyond_small_unlabelled_work(readings):
    result = _owed(familiarity="brownfield-unmapped", intent="delivery", **readings)
    assert "RP-FLOOR-002" in result["rules_fired"]
    # ADR-092 decision: no stage modes, so the floor cannot force define to
    # thorough. The path has its four fixed stages, and the floor keeps its skill.
    assert result["stages"] == ("assess", "specify", "build", "ship")
    # #360 merged the skill into `atdd`, which the check set names.
    assert "atdd" in result["required_skills"]


CRITICAL_AND_DOMAIN = [
    ({"risk": "critical"}, "RP-FLOOR-001"),
    ({"risk": "contained", "labels": "auth"}, "RP-FLOOR-003"),
]


@pytest.mark.parametrize("readings, floor", CRITICAL_AND_DOMAIN)
def test_critical_and_domain_floors_still_win(readings, floor):
    result = _evaluate(familiarity="brownfield-unmapped", size="small",
                       intent="delivery", **readings)
    assert floor in _fired(result)
    assert result["delivery_approach"] == "full"


@pytest.mark.parametrize("readings, floor", CRITICAL_AND_DOMAIN)
def test_on_the_path_critical_and_domain_work_owes_the_person_approvals_full_owed(
        readings, floor):
    """ADR-099 decisions 4 and 5: no approaches and no reviews. The floors that
    forced `full` leave the common row and the scenario approval; a domain
    label adds the human sign-off (`G5`)."""
    result = _owed(familiarity="brownfield-unmapped", size="small", intent="delivery",
                   **readings)
    assert result["rules_fired"][0] == "RP-EVID-COMMON", (floor, result["rules_fired"])
    assert "scenario-approval" in result["evidence_required"], floor
    for token in ("definition-of-done", "architecture"):
        assert token not in result["evidence_required"], (floor, token)
    assert ("human-approval" in result["evidence_required"]) is ("labels" in readings)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=root, check=True)
    return root


def test_ua_2_quick_fix_start_takes_it_and_records_the_advice(repo):
    r = subprocess.run(
        [sys.executable, str(CLI), "quick-fix", "start", "tidy-config",
         "--risk", "contained - one function",
         "--familiarity", "brownfield-unmapped - its behaviour is not pinned by tests",
         "--size", "small - one function and its tests",
         "--intent", "parse_config is easier to read",
         "--scenario", "Given the settings file, when it is parsed, then nothing changes",
         "--test", "tests/test_config.py"],
        cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    # 9.0.0 writes no delivery-approach.md (ADR-091), and on the path start writes
    # no devlog (ADR-092 open question 8). `start` prints no `advice :` line
    # (ADR-099); the advice is in the view of the assessment.
    assert not (repo / ".compass" / "work" / "tidy-config" / "devlog.md").exists()
    assert "advice :" not in r.stdout, r.stdout
    shown = subprocess.run([sys.executable, str(CLI), "approach", "evaluate", "--issue",
                            "tidy-config", "--verbose"], cwd=repo,
                           capture_output=True, text=True)
    assert shown.returncode == 0, shown.stdout + shown.stderr
    advice = [ln for ln in shown.stdout.splitlines() if "[RP-ADV-002]" in ln]
    assert advice and "atdd" in advice[0], shown.stdout
    from compass_pkg import path_stages
    import yaml
    manifest = yaml.safe_load(
        (repo / ".compass" / "work" / "tidy-config" / "manifest.yml").read_text())
    assert path_stages.is_path_issue(manifest)
    assert "RP-FLOOR-002" not in _fired(manifest)
