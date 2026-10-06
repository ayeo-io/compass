"""The decisions of 5 and 6 October 2026 that changed the plan are on record.

Each is an entry in `governance/decisions/`, and an entry never changes: a
change of mind is a new entry that supersedes the old one. Four decisions
were taken in conversation and not yet written down.

Scenario id: DE-1 (issue `decisions-2026-10-06`).
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "governance" / "decisions"


def _entry(slug):
    found = sorted(LEDGER.glob(f"2026-10-0*-{slug}.md"))
    assert found, f"no decision entry for {slug}"
    return found[-1].read_text(encoding="utf-8")


def _section(text, name):
    return text.split(f"## {name}", 1)[1].split("\n## ", 1)[0]


@pytest.mark.parametrize("slug, supersedes, says", [
    ("old-route-names-readable-until-7-0-0",
     "2026-10-05-routes-are-quick-fix-regular-full", "7.0.0"),
    ("guardrails-merge-folds-into-prd-22",
     "2026-10-05-guardrails-merge-routing-policy-replaces",
     "configurable framework"),
    ("action-policies-wait-for-prd-19", None, "routing policy as configuration"),
    ("this-repository-may-hold-a-settings-only-compass-yml",
     "2026-10-05-no-project-guardrails-in-this-repository", "compass.yml"),
])
def test_de_1_the_decision_is_on_record(slug, supersedes, says):
    text = _entry(slug)
    assert says in _section(text, "Decision"), slug
    assert "jed72" in _section(text, "Decided by")
    if supersedes:
        assert supersedes in _section(text, "Supersedes"), slug
