"""`compass check` never prints PASS for a check that inspected nothing.

The JSON marked such checks `nothing-to-check`, while the text views
labelled them PASS and counted them in "1 of 22 check(s) failed", which
invites a reader to count the rest as clean (#110). The text views now
label them NOTHING TO CHECK and count them apart. The exit code is
unchanged: having nothing to check is not a failure.

Scenario id: NI-1 (issue `nothing-inspected-is-not-pass`).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _cli(root, *args):
    r = subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                       capture_output=True, text=True)
    return r.returncode, ANSI.sub("", r.stdout + r.stderr)


def _fresh_quick_fix(tmp_path):
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


def _json(root):
    _code, out = _cli(root, "check", "--issue", "g-fix", "--json")
    return json.loads(out)


def test_ni_1_verbose_labels_nothing_to_check_apart(tmp_path):
    root = _fresh_quick_fix(tmp_path)
    data = _json(root)
    empty = {c["name"] for c in data["checks"] if c["status"] == "nothing-to-check"}
    assert empty, "the fixture must have checks with nothing to inspect"
    _code, out = _cli(root, "check", "--issue", "g-fix", "--verbose")
    for name in empty:
        assert f"    PASS {name}:" not in out, name
        assert f"    NOTHING TO CHECK {name}:" in out, name


def test_ni_1_the_failing_verdicts_count_only_checks_that_inspected_something(tmp_path):
    root = _fresh_quick_fix(tmp_path)
    data = _json(root)
    inspected = data["ran"] - data["nothing_to_check"]
    code, verbose = _cli(root, "check", "--issue", "g-fix", "--verbose")
    assert (f"compass check: FAIL - {data['failed']} of {inspected} check(s) "
            f"failed, {data['nothing_to_check']} had nothing to check.") in verbose
    _code, default = _cli(root, "check", "--issue", "g-fix")
    first = default.splitlines()[0]
    assert "had nothing to check" in first, first
    assert code != 0, "a failing check still fails the run"
