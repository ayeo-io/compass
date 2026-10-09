"""The glossary says what a term means, and only that.

A reader took "Not: An epic" under `initiative` to mean that epic was dropped.
The derived glossary and `compass terminology` therefore carry no "Not" line
and no former name. A contrast a reader needs is written positively inside
the definition.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
TERMINOLOGY = ROOT / "governance" / "terminology.yml"
GLOSSARY = ROOT / "docs" / "glossary.md"

# Entries that carried a `not:` field before this change.
FORMER_NOT_ENTRIES = [
    "manifest", "initiative", "issue", "feature", "bug", "task", "design",
    "plan", "technical-design", "feature-file", "assessment", "traceability",
    "intent", "router", "assess", "requirements-review", "follow-up",
    "receipt", "ship", "stage-mode", "PX", "RP", "LS", "RR",
]


def meaning_only_problems(text: str) -> list[str]:
    """Name each line of rendered vocabulary that is not a meaning."""
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("**Not:**"):
            found.append(f"line {n}: a Not line: {stripped[:60]}")
        elif stripped.lower().startswith("not:"):
            found.append(f"line {n}: a not: line: {stripped[:60]}")
        if "v1 called this" in line:
            found.append(f"line {n}: a former name: {stripped[:60]}")
    return found


def _derive(tmp_path: pathlib.Path) -> str:
    out = tmp_path / "glossary.md"
    result = subprocess.run(
        [sys.executable, str(CLI), "_derive-glossary", "--internal",
         "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return out.read_text(encoding="utf-8")


def test_the_derived_glossary_defines_meaning_only(tmp_path):
    problems = meaning_only_problems(_derive(tmp_path))
    assert not problems, "the derived glossary says what a term is not:\n" + \
        "\n".join(problems)


def test_the_committed_glossary_defines_meaning_only():
    problems = meaning_only_problems(GLOSSARY.read_text(encoding="utf-8"))
    assert not problems, "docs/glossary.md says what a term is not:\n" + \
        "\n".join(problems)


def test_compass_terminology_prints_no_not_line():
    for term in FORMER_NOT_ENTRIES:
        result = subprocess.run(
            [sys.executable, str(CLI), "terminology", term],
            cwd=ROOT, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, f"{term}: {result.stdout}{result.stderr}"
        assert "v1 called this" not in result.stdout, term
        assert not [l for l in result.stdout.splitlines()
                    if l.strip().startswith("not:")], (
            f"`compass terminology {term}` prints a not: line")


def test_the_vocabulary_file_has_no_not_field():
    doc = yaml.safe_load(TERMINOLOGY.read_text(encoding="utf-8"))
    holders = [name for section in ("terms", "codes")
               for name, e in (doc.get(section) or {}).items()
               if isinstance(e, dict) and "not" in e]
    assert not holders, f"entries still carry a `not:` field: {holders}"


def test_the_check_reports_a_planted_not_line():
    """Prove the check can fail: plant each shape it exists to catch."""
    clean = "### issue\n\nThe atomic tracked unit of work.\n"
    assert meaning_only_problems(clean) == []
    assert meaning_only_problems(clean + "\n**Not:** An epic.\n")
    assert meaning_only_problems(clean + "\n  not:     An epic.\n")
    assert meaning_only_problems(clean + '\nv1 called this "Land".\n')
