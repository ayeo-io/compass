"""`autonomy:` sets which stage hand-offs wait for a person.

A checkpoint is a hand-off where a session stops and waits: assess step 7,
and the define, refine and plan hand-offs. `.compass/config.yml` can set
`autonomy: controlled | balanced | autonomous` (default balanced). The
routing policy's `autonomy_checkpoints:` table says which checkpoints wait
for each value and route, the evaluator records the answer in the manifest
as `checkpoints:`, and each hand-off waits only when its stage is listed. No
value changes a gate, evidence, the hook or `compass check` (issue #329).

Scenario ids: AU-1 to AU-6 (issue `autonomy-setting`).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]

QUICK_FIX = {"risk": "trivial", "familiarity": "brownfield-mapped",
             "size": "atomic", "intent": "delivery"}
FEATURE = {"risk": "contained", "familiarity": "brownfield-mapped",
           "size": "standard", "intent": "delivery"}
INITIATIVE = {"risk": "contained", "familiarity": "brownfield-mapped",
              "size": "large", "intent": "delivery"}


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=root, check=True)
    (root / ".compass").mkdir()
    (root / ".compass" / "config.yml").write_text("mode: enforced\n")
    return root


def _set_autonomy(root, value):
    (root / ".compass" / "config.yml").write_text(
        f"mode: enforced\nautonomy: {value}\n")


def _run(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True)


def _evaluate(root, readings):
    args = []
    for key, value in readings.items():
        args += ["--assessment", f"{key}={value}"]
    r = _run(root, "approach", "evaluate", "--json", *args)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def _start(root, slug, risk, size):
    return _run(root, "quick-fix", "start", slug,
                "--risk", f"{risk} - why", "--familiarity",
                "brownfield-mapped - the file and its test exist",
                "--size", f"{size} - why", "--intent", "the greeting is right",
                "--scenario", "Given the greeting, when read, then it says hello",
                "--test", "tests/test_greeting.py")


def test_au_1_balanced_is_the_default(project):
    assert _evaluate(project, QUICK_FIX)["checkpoints"] == []
    assert _evaluate(project, FEATURE)["checkpoints"] == ["define", "plan"]
    assert _evaluate(project, INITIATIVE)["checkpoints"] == [
        "assess", "define", "refine", "plan"]
    _start(project, "bigger", "contained", "standard")
    manifest = yaml.safe_load(
        (project / ".compass" / "work" / "bigger" / "manifest.yml").read_text())
    assert manifest["checkpoints"] == ["define", "plan"], manifest


@pytest.mark.parametrize("readings", [QUICK_FIX, FEATURE, INITIATIVE])
def test_au_2_the_setting_changes_only_the_checkpoints(project, readings):
    results = {}
    for value in ("controlled", "balanced", "autonomous"):
        _set_autonomy(project, value)
        results[value] = _evaluate(project, readings)
    rest = [{k: v for k, v in r.items() if k != "checkpoints"}
            for r in results.values()]
    assert rest[0] == rest[1] == rest[2]
    assert results["autonomous"]["checkpoints"] == []
    assert "assess" in results["controlled"]["checkpoints"]


def test_au_3_an_unknown_value_is_refused(project):
    _set_autonomy(project, "relaxed")
    r = _run(project, "approach", "evaluate", "--json",
             "--assessment", "risk=trivial", "--assessment",
             "familiarity=brownfield-mapped", "--assessment", "size=atomic")
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "autonomy" in out and "relaxed" in out, out
    for value in ("controlled", "balanced", "autonomous"):
        assert value in out, out


def test_au_4_the_summary_stays_three_lines_and_names_the_checkpoints(project):
    assert _start(project, "greeting", "trivial", "atomic").returncode == 0
    _start(project, "bigger", "contained", "standard")
    small = _run(project, "approach", "summary", "--issue", "greeting")
    big = _run(project, "approach", "summary", "--issue", "bigger")
    for view in (small, big):
        assert view.returncode == 0, view.stderr
        assert len(view.stdout.strip().splitlines()) == 3, view.stdout
    assert "does not stop to wait for you" in small.stdout.splitlines()[0]
    assert "waits for you at: define, plan" in big.stdout.splitlines()[0]


@pytest.mark.parametrize("command", ["assess", "define", "refine", "plan"])
def test_au_5_each_hand_off_waits_only_when_listed(command):
    text = (ROOT / "commands" / f"{command}.md").read_text(encoding="utf-8")
    if command == "assess":   # its full procedure is a reference file
        text += (ROOT / "approaches" / "assess-procedure.md").read_text(encoding="utf-8")
    assert "`checkpoints:`" in text, command
    assert "devlog.md" in text, command
    assert "autonomy" in text, command


def test_au_6_a_table_naming_another_stage_is_refused(project):
    shutil.copytree(ROOT / "governance", project / "governance")
    path = project / "governance" / "routing-policy.yml"
    policy = yaml.safe_load(path.read_text())
    policy["autonomy_checkpoints"]["balanced"]["regular"].append("verify")
    path.write_text(yaml.safe_dump(policy, sort_keys=False))
    lint = _run(project, "policy", "lint")
    assert lint.returncode != 0, lint.stdout + lint.stderr
    assert "verify" in lint.stdout + lint.stderr
    r = _run(project, "approach", "evaluate", "--json",
             *sum((["--assessment", f"{k}={v}"] for k, v in FEATURE.items()), []))
    assert r.returncode != 0, r.stdout + r.stderr
