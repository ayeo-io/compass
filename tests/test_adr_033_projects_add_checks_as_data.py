"""ADR-033 replaces ADR-002, ADR-010 is accepted, and two decisions on the
configurable framework are in the ledger (issue
`adr-projects-add-checks-as-data`).

On 2026-10-05 the maintainer approved a framework where a project adds
checks, gates and assessment-dimension values as configuration, while the
five guardrails and the shipped core stay framework-owned and locked.
ADR-002 forbade that, and the invariants on guardrails and routing
(`Inv-2`, `Inv-3`) restated it, so the records must change before any of it
is built. These tests pin the records, not the reasoning.

The one scenario of the issue (`TRC-001`).
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / "architecture" / "decisions"
INDEX = DECISIONS / "README.md"
CONTEXT = ROOT / "architecture" / "system-context.md"
LEDGER = ROOT / "governance" / "decisions"


def _record(adr_id: str) -> Path:
    [path] = sorted(DECISIONS.glob(f"{adr_id}-*.md"))
    return path


def _frontmatter(adr_id: str) -> dict:
    header = _record(adr_id).read_text(encoding="utf-8").split("---\n", 2)[1]
    out = {}
    for line in header.splitlines():
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def _index_row(prefix: str) -> str:
    rows = [line for line in INDEX.read_text(encoding="utf-8").splitlines()
            if line.startswith(prefix)]
    assert len(rows) == 1, (prefix, rows)
    return rows[0]


def test_trc_001_adr_033_supersedes_adr_002():
    new = _frontmatter("ADR-033")
    old = _frontmatter("ADR-002")
    assert new["status"] == "accepted"
    assert new["supersedes"] == "ADR-002"
    assert old["status"] == "superseded"
    assert old["superseded_by"] == "ADR-033"
    assert "| superseded by ADR-033 |" in _index_row("| [ADR-002]")
    assert "| accepted |" in _index_row("| [ADR-033]")


def test_trc_001_adr_010_is_accepted():
    assert _frontmatter("ADR-010")["status"] == "accepted"
    assert "| accepted |" in _index_row("| [ADR-010]")


def test_trc_001_invariants_name_the_framework_core():
    inv2 = _index_row("| Inv-2 |")
    inv3 = _index_row("| Inv-3 |")
    assert "Five framework guardrails" in inv2 and "ADR-033" in inv2
    assert "framework decision" in inv3 and "ADR-033" in inv3
    context = CONTEXT.read_text(encoding="utf-8")
    assert "The router is not extensible in-line" not in context
    assert "ADR-033" in context


@pytest.mark.parametrize("slug", [
    "follow-on-prds-written-when-slice-1-lands",
    "artifact-freshness-stays-opt-in",
])
def test_trc_001_decision_is_in_the_ledger(slug):
    [path] = sorted(LEDGER.glob(f"2026-10-05-{slug}.md"))
    text = path.read_text(encoding="utf-8")
    assert "jed72" in text
    for section in ("## Decision", "## Why", "## Evidence"):
        assert section in text, section
