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
        "`catalog` term row keeps `catalogue` as its other form",
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


def test_trc_064_the_record_cites_no_id_a_reader_cannot_open():
    """Issue-local ids (scenarios, questions, units) live in untracked issue
    state, so a record on main must name the subject instead."""
    text = _text()
    assert not re.search(r"\b(?:TRC|FU|RR|DD)-\d+\b|\bQ\d+\b", text)


def test_trc_064_the_record_says_what_the_cli_prints_for_old_names():
    """The CLI does write some old spellings back for one release: the readiness
    record and the compliance JSON hold both, and a refusal names the old code."""
    decision = _section("Decision")
    assert "does not print them back" not in decision
    for fact in ("`catalogue_digest` beside `catalog_digest`",
                 "`behaviour` and `behaviours` beside `behavior` and `behaviors`",
                 "`not-initialised`"):
        assert fact in decision, fact


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


GUIDE = ROOT / "docs" / "upgrade-7-0-0.md"
BEFORE = "## The released spellings end, and the old readers stay until 9.0.0"
SECTION = "## Renamed names"
MARK = "us-english-scan: allow - "


def _guide_section(text):
    start = text.index(SECTION + "\n")
    rest = text[start + len(SECTION):]
    end = re.search(r"^## ", rest, re.M)
    return text[start:start + len(SECTION) + (end.start() if end else len(rest))]


def test_trc_065():
    """Scenario id: `TRC-065` in language-key-and-us-english/acceptance-criteria.md

    The upgrade guide holds one "Renamed names" section after the section on
    the released spellings. It lists each old name, its new name and 9.0.0,
    says what to do about the refusal code, the JSON keys and the project
    names, and marks every line that quotes an old name.
    """
    import sys
    sys.path.insert(0, str(ROOT / "tests"))
    import us_english_words as words

    text = GUIDE.read_text(encoding="utf-8")
    assert text.count(SECTION + "\n") == 1
    assert text.index(BEFORE) < text.index(SECTION)
    section = _guide_section(text)
    rows = [ln for ln in section.splitlines() if ln.startswith("| ") and "`" in ln]
    assert len(rows) == 11
    for row in rows:
        kind, old, new, until = [c.strip() for c in row.split("<!--")[0].strip().strip("|").split("|")]
        assert old.startswith("`") and new.startswith("`") and old != new
        assert until == "9.0.0"
    flat = " ".join(section.split())
    assert "match `not-initialized`" in flat
    assert "`compass:behaviour-mapping` or `dor-behaviour-is-gwt` keeps working" in flat
    assert "reads the refusal code or the `behaviour` JSON keys should move to the new names " \
           "before 9.0.0" in flat
    assert "No manifest, state file or readiness record needs a change" in flat

    # Each line that quotes a listed old word carries the marker and a reason,
    # so the guard reports nothing; the same section without them is reported.
    assert words.scan_text(section) == []
    quoting = [ln for ln in section.splitlines() if words.scan_text(ln.split("<!--")[0])]
    assert len(quoting) >= 10 and all(MARK in ln for ln in quoting)
    stripped = "\n".join(ln.split("<!--")[0] for ln in section.splitlines())
    assert {h[1] for h in words.scan_text(stripped)} >= {"judgement", "behaviour", "catalogue"}
