"""The decision record that makes the framework's prose US English.

The scenario (TRC-064) is in the acceptance criteria of the issue
`language-key-and-us-english`.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / "governance" / "decisions"
RECORD = DECISIONS / "2026-10-19-framework-prose-is-us-english-a-project-sets-its-language.md"
OLDER = DECISIONS / "2026-10-02-spell-it-artifact.md"


def _text():
    return " ".join(RECORD.read_text(encoding="utf-8").split())


def _section(name):
    m = re.search(rf"^## {name}\n(.*?)(?=^## |\Z)", RECORD.read_text(encoding="utf-8"),
                  flags=re.M | re.S)
    assert m, f"no ## {name} section"
    return " ".join(m.group(1).split())


def test_trc_064_the_record_states_each_fact():
    assert RECORD.is_file()
    assert _section("Decided by") == "jed72"
    assert _section("Date") == "2026-10-19"
    assert "2026-10-02-spell-it-artifact" in _section("Supersedes")
    decision = _section("Decision")
    for fact in (
        "framework's prose is US English",
        "`language` in its own `compass.yml`",
        "preset cannot carry the key (ADR-043)",
        "one line only when `language` is set",
        "unset means no instruction",
        "the \"artifact exception\" ends",
        "accepted until 8.0.0",
        "`catalogue` becomes `catalog`",
        "TRC-069",
        "merged decision records",
        "governance/presets/default@6",
        "shipped-releases",
        "compatibility corpora",
        "cli/vendor",
        "`cancelled`",
        "other immutable records",
    ):
        assert fact.lower() in decision.lower(), fact
    assert _section("Why")
    assert "issues/241#issuecomment-6273616740" in _section("Evidence")


def test_trc_064_the_older_record_is_unchanged():
    head = subprocess.run(["git", "show", "origin/main:governance/decisions/"
                           "2026-10-02-spell-it-artifact.md"], cwd=ROOT,
                          capture_output=True, text=True)
    if head.returncode != 0:
        head = subprocess.run(["git", "show", "HEAD:governance/decisions/"
                               "2026-10-02-spell-it-artifact.md"], cwd=ROOT,
                              capture_output=True, text=True)
    assert head.returncode == 0, head.stderr
    assert OLDER.read_text(encoding="utf-8") == head.stdout
