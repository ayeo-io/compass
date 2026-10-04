"""Every screen that names a fired policy rule prints it through one function.

`approach evaluate` (its summary and its verbose view) and `issue receipt`
each built the line themselves, and the copies drifted: a plain-language
fix reached one screen and not the other (#109). They now share
`render.fired_rule_line`, and each screen prints exactly what it printed
before, pinned below.

Scenario id: FR-1 (issue `one-fired-rule-formatter-shared`).
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
    # An auth label raises the approach, so rules fire.
    _cli(root, "quick-fix", "start", "auth-fix", "--risk", "contained - x",
         "--familiarity", "brownfield-mapped - x", "--size", "small - x",
         "--labels", "auth", "--intent", "i",
         "--scenario", "Given a, when b, then c", "--test", "tests/test_x.py")
    return root


FLOOR = "Domain risk overrides size. A one-line auth change is not small"


def test_fr_1_each_screen_prints_what_it_printed_before(tmp_path):
    root = _project(tmp_path)
    summary = _cli(root, "approach", "evaluate", "--issue", "auth-fix", "--summary")
    assert f"  - {FLOOR} (RP-FLOOR-003, floor)\n" in summary
    verbose = _cli(root, "approach", "evaluate", "--issue", "auth-fix", "--verbose")
    assert f"    {FLOOR} (RP-FLOOR-003, floor)\n" in verbose
    assert ("    Irreversible-surface issues have consistency checked before "
            "they ship (RP-REQUIRE-002, requirement)\n") in verbose
    receipt = _cli(root, "issue", "receipt", "--issue", "auth-fix")
    assert f"    {FLOOR} (RP-FLOOR-003)\n" in receipt
    assert ("    Work on a trust boundary states the threats it considered "
            "(RP-REQUIRE-005)\n") in receipt


def test_fr_1_the_formatter_covers_each_shape():
    from compass_pkg.render import fired_rule_line
    rule = {"id": "RP-X-1", "kind": "floor", "rationale": "Says why.  "}
    assert fired_rule_line(rule) == "Says why (RP-X-1, floor)"
    assert fired_rule_line(rule, with_kind=False) == "Says why (RP-X-1)"
    assert fired_rule_line({"id": "RP-X-2"}, with_kind=False) == "(RP-X-2)"
    assert fired_rule_line("RP-X-3", with_kind=False) == "(RP-X-3)"


def test_fr_1_both_modules_use_the_one_formatter():
    for name in ("routing.py", "receipt.py"):
        src = (ROOT / "cli" / "compass_pkg" / name).read_text(encoding="utf-8")
        assert "fired_rule_line" in src, name
        assert "rationale']).rstrip().rstrip('.')" not in src, name
        assert 'rationale"]).rstrip().rstrip(".")' not in src, name
        assert "rationale.rstrip().rstrip('.')" not in src, name
