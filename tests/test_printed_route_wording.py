"""Printed output names the delivery approach and its stages.

The frozen vocabulary retired "route" for the delivery approach, and the
manifest calls its parts `stages`. Printed output still said "candidate
shape", "wrote route, phases, gates", "Has the route been evaluated?" and
"Route distribution:", so a reader could not match it to the manifest
(#108). Machine keys such as `candidate_route` are unchanged.

Scenario id: RW-1 (issue `printed-route-wording`).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

ANSI = re.compile(r"\x1b\[[0-9;]*m")
RETIRED = re.compile(r"\broute\b|candidate shape|\bphases\b", re.I)


def _cli(root, *args):
    r = subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                       capture_output=True, text=True)
    return ANSI.sub("", r.stdout + r.stderr)


def _project(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    for cmd in (["init", "-q"], ["config", "user.email", "t@e.com"],
                ["config", "user.name", "t"]):
        subprocess.run(["git", *cmd], cwd=root, check=True)
    (root / "README.md").write_text("hi\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
    _cli(root, "quick-fix", "start", "g-fix", "--risk", "trivial - x",
         "--familiarity", "brownfield-mapped - x", "--size", "atomic - x",
         "--intent", "i", "--scenario", "Given a, when b, then c",
         "--test", "tests/test_x.py")
    return root


def _retired(text):
    return sorted({m.group(0).lower() for m in RETIRED.finditer(text)})


def test_rw_1_evaluate_prints_no_retired_word(tmp_path):
    root = _project(tmp_path)
    out = _cli(root, "approach", "evaluate", "--issue", "g-fix", "--verbose",
               "--write")
    out += _cli(root, "approach", "evaluate", "--issue", "g-fix", "--verbose",
                "--write", "--reason", "same again")
    assert _retired(out) == [], out


def test_rw_1_gate_pass_and_check_ask_about_the_delivery_approach(tmp_path):
    root = _project(tmp_path)
    out = _cli(root, "gate", "pass", "verify.nope", "--issue", "g-fix",
               "--evidence", "EV-1")
    assert "delivery approach" in out and _retired(out) == [], out
    from compass_pkg.checks import _check_gate_evidence
    _ok, detail = _check_gate_evidence({"gates": []}, str(tmp_path))
    assert "delivery approach" in detail and _retired(detail) == [], detail


def test_rw_1_retro_prints_no_retired_word(tmp_path):
    root = _project(tmp_path)
    out = _cli(root, "retro")
    assert _retired(out) == [], out
