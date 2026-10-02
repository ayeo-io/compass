"""Define asks which failure modes a brief implies; a mode not covered is
recorded as de-scoped and listed by the verifier: the failure-modes-in-define
issue, GitHub issue #282.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"


def _compass(root: Path, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True)


@pytest.fixture
def issue(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    r = _compass(root, "quick-fix", "start", "demo", "--risk", "trivial - x",
                 "--familiarity", "brownfield-mapped - x", "--size", "small - x",
                 "--intent", "INT-1", "--scenario", "Given x then y", "--test", "tests/t.py")
    assert r.returncode == 0, r.stdout + r.stderr
    return root


def _descoped(root: Path) -> list:
    m = yaml.safe_load((root / ".compass" / "work" / "demo" / "manifest.yml").read_text())
    return m.get("failure_modes_descoped") or []


@pytest.mark.parametrize("rel", ["commands/define.md", "skills/bdd-specification/SKILL.md"])
def test_define_asks_the_author_with_two_worked_examples(rel):
    """FM-A."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert "input classes and failure modes" in text
    assert "compass scenario descope" in text
    assert len(re.findall(r"^\s*-?\s*\*\*Worked example", text, re.M)) >= 2, rel


def test_descope_records_mode_reason_and_date(issue):
    """FM-B."""
    r = _compass(issue, "scenario", "descope", "a lessons file that is not UTF-8",
                 "--reason", "the hook already keeps the contract", "--issue", "demo")
    assert r.returncode == 0, r.stdout + r.stderr
    [entry] = _descoped(issue)
    assert entry["mode"] == "a lessons file that is not UTF-8"
    assert entry["reason"] == "the hook already keeps the contract"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(entry["recorded"]))
    lint = _compass(issue, "issue", "lint", "--issue", "demo")
    assert lint.returncode == 0, lint.stdout + lint.stderr


@pytest.mark.parametrize("mode, reason", [("", "a reason"), ("a mode", ""), ("  ", "x")])
def test_descope_refuses_an_empty_mode_or_reason(issue, mode, reason):
    """FM-B."""
    r = _compass(issue, "scenario", "descope", mode, "--reason", reason, "--issue", "demo")
    assert r.returncode != 0
    assert _descoped(issue) == []


def test_descope_refuses_a_repeat(issue):
    """FM-B."""
    _compass(issue, "scenario", "descope", "Same Mode", "--reason", "x", "--issue", "demo")
    r = _compass(issue, "scenario", "descope", "same  mode", "--reason", "y", "--issue", "demo")
    assert r.returncode != 0
    assert len(_descoped(issue)) == 1


def test_the_schema_accepts_the_key_and_refuses_a_bad_entry():
    """FM-B: the optional key is declared, with its three fields required."""
    import json
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text())
    prop = schema["properties"]["failure_modes_descoped"]
    assert prop["type"] == "array"
    assert set(prop["items"]["required"]) == {"mode", "reason", "recorded"}
    for rel in ("templates/manifest.yml", "schemas/manifest.reference.yml"):
        assert "failure_modes_descoped" in (ROOT / rel).read_text(encoding="utf-8"), rel


def test_verify_lists_each_descoped_mode():
    """FM-C."""
    verifier = (ROOT / "agents" / "verifier.md").read_text(encoding="utf-8")
    assert "failure_modes_descoped" in verifier
    report = (ROOT / "templates" / "verification-report.md").read_text(encoding="utf-8")
    assert "Failure modes de-scoped at define" in report


def test_the_subcommand_is_on_the_public_surface():
    """FM-D."""
    assert "compass scenario descope" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert "'scenario descope'" in (ROOT / "cli" / "compass_pkg" / "verb_help.py").read_text()
    assert "descope" in _compass(ROOT, "scenario", "--help").stdout


def test_lint_refuses_a_bad_entry(issue):
    """FM-B: a descoped entry with no reason fails `compass issue lint`."""
    path = issue / ".compass" / "work" / "demo" / "manifest.yml"
    m = yaml.safe_load(path.read_text())
    m["failure_modes_descoped"] = [{"mode": "x", "recorded": "2026-10-02"}]
    path.write_text(yaml.safe_dump(m, sort_keys=False))
    r = _compass(issue, "issue", "lint", "--issue", "demo")
    assert r.returncode != 0 and "reason" in r.stdout + r.stderr


def test_an_empty_key_does_not_crash(issue):
    """FM-B: `failure_modes_descoped:` with no value is treated as empty."""
    path = issue / ".compass" / "work" / "demo" / "manifest.yml"
    path.write_text(path.read_text() + "failure_modes_descoped:\n")
    r = _compass(issue, "scenario", "descope", "a mode", "--reason", "x", "--issue", "demo")
    assert r.returncode == 0 and "Traceback" not in r.stderr, r.stderr
    assert len(_descoped(issue)) == 1


def test_a_repeat_is_found_across_case_folding(issue):
    """FM-B."""
    _compass(issue, "scenario", "descope", "STRASSE", "--reason", "x", "--issue", "demo")
    r = _compass(issue, "scenario", "descope", "straße", "--reason", "y", "--issue", "demo")
    assert r.returncode != 0
