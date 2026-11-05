"""Every screen that names a fired policy rule prints it through one function.

`approach evaluate` (its summary and its verbose view) and `issue receipt`
each built the line themselves, and the copies drifted: a plain-language
fix reached one screen and not the other (#109). They shared
`render.fired_rule_line`, and each screen prints exactly what it printed
before, pinned below. 9.0.0 removed the receipt (ADR-091).

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


ARCHITECTURE = "A change to a `G5` surface owes the architecture review"
SIGN_OFF = "A change to a `G5` surface owes a person's sign-off before it ships"


def test_fr_1_each_screen_prints_what_it_printed_before(tmp_path):
    # The issue is on the four-stage path (ADR-092): an auth label adds evidence,
    # and each rule is named by the evidence it adds.
    root = _project(tmp_path)
    summary = _cli(root, "approach", "evaluate", "--issue", "auth-fix", "--summary")
    assert f"  - {ARCHITECTURE} (RP-REQUIRE-004, evidence)\n" in summary
    verbose = _cli(root, "approach", "evaluate", "--issue", "auth-fix", "--verbose")
    assert f"    {ARCHITECTURE} (RP-REQUIRE-004, evidence)\n" in verbose
    # A guardrail code is in backticks, as its rationale writes it.
    assert f"    {SIGN_OFF} (`G5`, guardrail)\n" in verbose


def test_fr_1_the_verbose_view_on_the_path_uses_path_words(tmp_path):
    root = _project(tmp_path)
    verbose = _cli(root, "approach", "evaluate", "--issue", "auth-fix", "--verbose")
    assert "  evidence row    : RP-EVID-STANDARD\n" in verbose, verbose
    assert "first approach" not in verbose and "quick fix" not in verbose, verbose
    assert "(G5," not in verbose, verbose


def test_fr_1_a_floor_on_the_path_keeps_only_the_effects_the_path_has(tmp_path):
    """`RP-FLOOR-002` forced the define stage to thorough and required a skill. The
    path has no stage modes, so its entry keeps the skill alone."""
    root = tmp_path / "p"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    _cli(root, "quick-fix", "start", "unmapped", "--risk", "contained - x",
         "--familiarity", "brownfield-unmapped - x", "--size", "medium - x",
         "--intent", "i", "--scenario", "Given a, when b, then c", "--test", "tests/test_x.py")
    import yaml
    manifest = yaml.safe_load(
        (root / ".compass" / "work" / "unmapped" / "manifest.yml").read_text())
    floor = next(f for f in manifest["policy_rules_fired"] if f["id"] == "RP-FLOOR-002")
    assert floor["changed"] == ["skill 'behavior-mapping' required"], floor
    verbose = _cli(root, "approach", "evaluate", "--issue", "unmapped", "--verbose")
    assert "forced to thorough" not in verbose, verbose


def test_fr_1_the_formatter_covers_each_shape():
    from compass_pkg.render import fired_rule_line
    rule = {"id": "RP-X-1", "kind": "floor", "rationale": "Says why.  "}
    assert fired_rule_line(rule) == "Says why (RP-X-1, floor)"
    assert fired_rule_line(rule, with_kind=False) == "Says why (RP-X-1)"
    assert fired_rule_line({"id": "RP-X-2"}, with_kind=False) == "(RP-X-2)"
    assert fired_rule_line("RP-X-3", with_kind=False) == "(RP-X-3)"
    assert fired_rule_line({"id": "G5", "kind": "guardrail", "rationale": "Why."}) == \
        "Why (`G5`, guardrail)"
    assert fired_rule_line({"id": "S17"}, with_kind=False) == "(`S17`)"


def test_fr_1_the_evaluator_uses_the_one_formatter():
    for name in ("routing.py",):
        src = (ROOT / "cli" / "compass_pkg" / name).read_text(encoding="utf-8")
        assert "fired_rule_line" in src, name
        assert "rationale']).rstrip().rstrip('.')" not in src, name
        assert 'rationale"]).rstrip().rstrip(".")' not in src, name
        assert "rationale.rstrip().rstrip('.')" not in src, name
