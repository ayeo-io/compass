"""Review rules are data, scoped by file, with what not to flag: the
review-rules-as-data issue, GitHub issue #255.

`compass policy review-rules --changed-files` prints the rules in
`governance/review-rules.yml` whose patterns match the files a change
touches, and `compass policy lint` refuses a malformed rule.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
RULES = ROOT / "governance" / "review-rules.yml"


def _compass(cwd: Path, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=cwd,
                          capture_output=True, text=True)


def _ids(out: str) -> set:
    return set(re.findall(r"^## (RR-\d{3})\b", out, re.M))


def _rules() -> list:
    return yaml.safe_load(RULES.read_text(encoding="utf-8"))["rules"]


@pytest.fixture
def project(tmp_path):
    """A Compass project with the repository's governance YAML, so
    `policy lint` has a policy to read."""
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    gov = root / "governance"
    gov.mkdir()
    for name in ("routing-policy.yml", "guardrails.yml"):
        shutil.copy(ROOT / "governance" / name, gov / name)
    return root


def _rule(**over) -> dict:
    rule = {
        "id": "RR-001", "blocking": True, "file_patterns": ["hooks/*"],
        "enforces": "G1", "rule": "A hook check refuses when it cannot run.",
        "allowed": [], "incident": "Commit 9bc086c.",
    }
    rule.update(over)
    return rule


def _write_rules(root: Path, rules: list) -> None:
    (root / "governance" / "review-rules.yml").write_text(
        yaml.safe_dump({"rules": rules}, sort_keys=False), encoding="utf-8")


def _rules_scoped_only_to(prefixes: tuple) -> set:
    """Ids of the rules every one of whose patterns starts with a prefix."""
    return {r["id"] for r in _rules()
            if all(p.startswith(prefixes) for p in r["file_patterns"])}


def test_a_hook_change_gets_the_hook_rules_and_no_template_rule():
    """RV-A: hooks/pre-tool.sh gets each hook rule, and no rule scoped only
    to templates or the adopter's reading path."""
    r = _compass(ROOT, "policy", "review-rules", "--changed-files", "hooks/pre-tool.sh")
    assert r.returncode == 0, r.stdout + r.stderr
    got = _ids(r.stdout)
    hook_rules = {r["id"] for r in _rules()
                  if any(p.startswith("hooks/") for p in r["file_patterns"])}
    assert len(hook_rules) >= 2, "the seed rules must hold at least two hook rules"
    assert hook_rules <= got, sorted(hook_rules - got)
    elsewhere = _rules_scoped_only_to(
        ("templates/", "commands/", "skills/", "agents/", "approaches/",
         "CLAUDE.md", "compass-contract.md"))
    assert elsewhere, "the seed rules must hold a rule scoped to the reading path"
    assert not (elsewhere & got), sorted(elsewhere & got)
    assert "Files: hooks/pre-tool.sh" in r.stdout


def test_a_template_change_gets_the_reading_path_rule_and_no_hook_rule():
    """RV-A, the other way round: the matching is by file, not a fixed list."""
    r = _compass(ROOT, "policy", "review-rules", "--changed-files",
                 "templates/verification-report.md")
    assert r.returncode == 0, r.stdout + r.stderr
    got = _ids(r.stdout)
    assert not (_rules_scoped_only_to(("hooks/",)) & got)
    assert _rules_scoped_only_to(("templates/", "commands/", "skills/", "agents/",
                                  "approaches/", "CLAUDE.md",
                                  "compass-contract.md")) & got


def test_each_printed_rule_carries_its_incident_and_allowed_list(project):
    """RV-A: a reviewer sees why the rule exists and what not to flag."""
    _write_rules(project, [_rule(allowed=["A comment that quotes the old rule."])])
    r = _compass(project, "policy", "review-rules", "--changed-files", "hooks/stop.sh",
                 "README.md")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "## RR-001 (blocking, enforces G1)" in r.stdout
    assert "Files: hooks/stop.sh" in r.stdout and "README.md" not in r.stdout
    assert "Do not flag: A comment that quotes the old rule." in r.stdout
    assert "Incident: Commit 9bc086c." in r.stdout


def test_a_file_no_rule_covers_prints_no_rule(project):
    """RV-A: no match is said plainly, not silently."""
    _write_rules(project, [_rule()])
    r = _compass(project, "policy", "review-rules", "--changed-files", "src/app.py")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not _ids(r.stdout)
    assert "no review rule applies" in r.stdout


def test_rules_option_reads_another_file(project, tmp_path):
    """RV-B: CI can pass the base branch's copy of the rules."""
    _write_rules(project, [_rule()])
    other = tmp_path / "base-rules.yml"
    other.write_text(yaml.safe_dump({"rules": [_rule(id="RR-009")]}), encoding="utf-8")
    r = _compass(project, "policy", "review-rules", "--rules", str(other),
                 "--changed-files", "hooks/pre-tool.sh")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _ids(r.stdout) == {"RR-009"}


def test_no_rules_file_is_said_and_passes(project):
    """RV-B: a project with no rules file, and the shipped copy is not used."""
    r = _compass(project, "policy", "review-rules", "--changed-files", "hooks/pre-tool.sh")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not _ids(r.stdout)
    assert "governance/review-rules.yml" in r.stdout


def test_a_missing_rules_option_file_fails(project, tmp_path):
    """RV-B: a --rules path that does not exist is an error, not no rules."""
    r = _compass(project, "policy", "review-rules", "--rules", str(tmp_path / "nope.yml"),
                 "--changed-files", "a.py")
    assert r.returncode != 0
    assert "nope.yml" in r.stdout + r.stderr


@pytest.mark.parametrize("bad, field", [
    ({"id": "R-1"}, "id"),
    ({"blocking": "yes"}, "blocking"),
    ({"file_patterns": []}, "file_patterns"),
    ({"file_patterns": "hooks/*"}, "file_patterns"),
    ({"enforces": "S99"}, "enforces"),
    ({"rule": "word " * 151}, "words"),
    ({"enforces": ["G1"]}, "enforces"),
    ({"incident": ""}, "incident"),
    ({"allowed": "anything"}, "allowed"),
])
def test_lint_refuses_a_malformed_rule(project, bad, field):
    """RV-C: each field is checked, and the error names the rule and field."""
    _write_rules(project, [_rule(**bad)])
    r = _compass(project, "policy", "lint")
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "Traceback" not in out, out
    assert "review-rules.yml" in out and field in out


def test_lint_refuses_a_repeated_id(project):
    """RV-C."""
    _write_rules(project, [_rule(), _rule(file_patterns=["templates/*"])])
    r = _compass(project, "policy", "lint")
    assert r.returncode != 0
    assert "RR-001" in r.stdout and "repeated" in r.stdout


def test_lint_passes_a_good_rules_file(project):
    """RV-C: a well-formed file does not change lint's result."""
    _write_rules(project, [_rule()])
    r = _compass(project, "policy", "lint")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "FAIL" not in r.stdout, r.stdout


def test_the_repository_rules_pass_lint():
    """RV-C and RV-E: the shipped seed rules are well formed."""
    r = _compass(ROOT, "policy", "lint")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "FAIL" not in r.stdout, r.stdout


def test_reviewer_reads_the_rules():
    """RV-D."""
    text = (ROOT / "agents" / "reviewer.md").read_text(encoding="utf-8")
    assert "compass policy review-rules --changed-files" in text
    assert "RR-" in text
    assert re.search(r"`allowed`", text)


def test_at_least_ten_rules_each_with_an_openable_incident():
    """RV-E: an incident names a pull request, issue or commit."""
    rules = _rules()
    assert len(rules) >= 10
    for r in rules:
        assert re.search(r"#\d+|\b[Cc]ommit [0-9a-f]{7,}\b", r["incident"]), r["id"]


def test_the_verb_is_on_the_public_surface():
    """RV-F."""
    assert "compass policy review-rules" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert "policy review-rules" in (ROOT / "cli" / "compass_pkg" / "verb_help.py").read_text(
        encoding="utf-8")
    help_out = _compass(ROOT, "policy", "--help").stdout
    assert "review-rules" in help_out
