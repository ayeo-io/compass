"""A small change on unmapped ground gets advice, not a floor.

In the comparison run of 30 Sep 2026
(docs/compass/2026-09-30-eval-comparison-discriminating.md), two of the three
stops followed a small, contained change rated brownfield-unmapped: the
small-change shape left it out and the unmapped-familiarity floor
(`RP-FLOOR-002`) sent it to define at full weight. Such a change now gets no
blocking question, and unfamiliar ground becomes advice. Critical risk and
the four domain labels keep their floors (issue #324).

Scenario ids: UA-1 and UA-2; the other two tests are regression checks (issue `unmapped-small-change-advisory`).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


def _evaluate(**readings):
    args = []
    for key, value in readings.items():
        args += ["--assessment", f"{key}={value}"]
    r = subprocess.run([sys.executable, str(CLI), "approach", "evaluate",
                        "--json", *args], cwd=ROOT, capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


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
    assert "behaviour-mapping" not in unmapped["required_skills"]
    advice = [s["strategy"] for s in unmapped["applicable_strategies"]]
    assert "behaviour-mapping" in advice, advice


@pytest.mark.parametrize("readings", [
    {"risk": "contained", "size": "standard"},
    {"risk": "contained", "size": "large"},
    {"risk": "cross-cutting", "size": "small"},
    {"risk": "critical", "size": "atomic"},
    {"risk": "contained", "size": "small", "labels": "auth"},
    {"risk": "trivial", "size": "atomic", "labels": "migrations"},
])
def test_the_floor_still_applies_beyond_small_unlabelled_work(readings):
    result = _evaluate(familiarity="brownfield-unmapped", intent="delivery",
                       **readings)
    assert "RP-FLOOR-002" in _fired(result)
    assert result["stages"].get("define") == "full"
    assert "behaviour-mapping" in result["required_skills"]


@pytest.mark.parametrize("readings, floor", [
    ({"risk": "critical"}, "RP-FLOOR-001"),
    ({"risk": "contained", "labels": "auth"}, "RP-FLOOR-003"),
])
def test_critical_and_domain_floors_still_win(readings, floor):
    result = _evaluate(familiarity="brownfield-unmapped", size="small",
                       intent="delivery", **readings)
    assert floor in _fired(result)
    assert result["delivery_approach"] == "initiative"


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
    record = next((repo / "docs" / "compass").glob("*-tidy-config")) \
        / "delivery-approach.md"
    text = record.read_text(encoding="utf-8")
    assert "## Advice" in text, text
    advice = text.split("## Advice", 1)[1].split("\n## ", 1)[0]
    assert "behaviour-mapping" in advice and "RP-ADV-002" in advice, advice
