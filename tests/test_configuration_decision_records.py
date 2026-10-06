"""Every format decision the configuration foundation builds on is recorded
before its code is written.

The configuration foundation makes delivery approaches, stages, checks and
gates data that a project extends. Its increments each cite a structural
decision (an ADR) or a product decision the maintainer took (a ledger
entry). These are public records, so none may lean on a private planning
document.

Scenario ids: `DR-1` to `DR-4` (issue `configuration-decision-records`).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ADRS = ROOT / "architecture" / "decisions"
LEDGER = ROOT / "governance" / "decisions"

NEW_ADRS = {
    "ADR-035": "delivery-approaches-stages-and-modes-are-configuration",
    "ADR-036": "an-issue-runs-against-a-stored-generation",
    "ADR-037": "configuration-changes-are-classified-by-effect",
    "ADR-038": "check-implementations-carry-versions",
    "ADR-039": "waivers-locks-and-unlocks",
    "ADR-040": "stable-ids-live-in-one-module",
    "ADR-041": "the-configuration-vocabulary",
    "ADR-042": "shipped-defaults-live-in-a-preset-directory",
    "ADR-043": "a-project-has-one-configuration-file",
}

NEW_LEDGER = [
    "2026-10-05-one-merge-grammar",
    "2026-10-05-floors-win-over-the-issue-layer",
    "2026-10-05-ready-and-done-lists-are-configurable",
    "2026-10-06-the-approach-catalogue-is-approaches",
    "2026-10-06-the-adoption-setting-is-adoption",
    "2026-10-06-check-results-in-their-own-file",
    "2026-10-06-legacy-waivers-readable-until-7-0-0",
    "2026-10-06-legacy-governance-readable-until-7-0-0",
    "2026-10-06-evidence-types-stay-framework-owned",
    "2026-10-06-locks-allow-tightening-and-g5-is-hard",
    "2026-10-06-dimensions-keep-tighter",
    "2026-10-06-set-on-a-map-is-key-by-key",
    "2026-10-06-hook-coverage-is-not-verifiable",
    "2026-10-06-policy-diff-has-an-exit-code-flag",
    "2026-10-06-label-cap-stays-at-eight",
    "2026-10-06-the-technical-design-stays-private",
    "2026-10-06-lint-rechecks-a-hand-edited-pin",
    "2026-10-06-cli-state-lives-in-state-yml",
    "2026-10-06-allow-project-commands-moves-to-compass-yml",
    "2026-10-06-default-6-x-never-changes-a-6-0-value",
    "2026-10-06-the-cli-writes-full-shas",
    "2026-10-06-parent-waivers-count-as-applied",
    "2026-10-06-the-preset-flag-is-not-on-compass-init",
]

PRIVATE_PATHS = re.compile(r"docs/(?:analysis|specs|proposals)/")
# The private design's own names: the brief's label and its requirement and
# design ids, none of which a public reader can look up.
PRIVATE_IDS = re.compile(r"\bPRD\b|\b(?:CF|PC|PS|AF|IT|LV|RN|AP|D|X|R)-\d+\b")


def _adr(adr_id):
    found = sorted(ADRS.glob(f"{adr_id}-*.md"))
    assert found, f"{adr_id} is missing"
    return found[0]


# --- every structural decision is a proposed ADR (`DR-1`) ---------------------

@pytest.mark.parametrize("adr_id, slug", sorted(NEW_ADRS.items()))
def test_dr_1_each_structural_decision_is_a_proposed_adr(adr_id, slug):
    path = _adr(adr_id)
    assert path.name == f"{adr_id}-{slug}.md", path.name
    text = path.read_text(encoding="utf-8")
    assert re.search(r"^status: (?:proposed|accepted)$", text, re.M), path.name
    for heading in ("## Context", "## Decision", "## Alternatives considered",
                    "## Consequences"):
        assert heading in text, f"{path.name} has no {heading}"
    alternatives = text.split("## Alternatives considered", 1)[1].split("\n## ", 1)[0]
    assert "Rejected" in alternatives, f"{path.name} rejects no alternative"
    index = (ADRS / "README.md").read_text(encoding="utf-8")
    assert f"[{adr_id}]({path.name})" in index, f"{adr_id} is not in the index"


# --- every product decision has a ledger entry (`DR-2`) -----------------------

@pytest.mark.parametrize("name", NEW_LEDGER)
def test_dr_2_each_product_decision_has_a_ledger_entry(name):
    path = LEDGER / f"{name}.md"
    assert path.is_file(), f"{name} is missing"
    text = path.read_text(encoding="utf-8")
    assert text.startswith(f"# {name[11:]}\n"), path.name
    for heading in ("## Decided by\n\njed72", "## Date\n\n" + name[:10],
                    "## Decision", "## Why", "## Evidence"):
        assert heading in text, f"{path.name} has no {heading!r}"


# --- public records lean on nothing private (`DR-3`) ---------------------------

def _new_records():
    return [_adr(a) for a in NEW_ADRS] + [LEDGER / f"{n}.md" for n in NEW_LEDGER]


def test_dr_3_no_record_cites_a_private_planning_path():
    cited = [p.name for p in _new_records()
             if p.is_file() and PRIVATE_PATHS.search(p.read_text(encoding="utf-8"))]
    assert cited == []


def test_dr_3_no_record_names_the_private_design_or_its_ids():
    named = {p.name: PRIVATE_IDS.findall(p.read_text(encoding="utf-8"))
             for p in _new_records() if p.is_file()}
    assert {k: v for k, v in named.items() if v} == {}


# --- the vocabulary amendment (`DR-4`) --------------------------------------------

def test_dr_4_the_vocabulary_amendment_names_the_new_terms():
    text = _adr("ADR-041").read_text(encoding="utf-8")
    assert "ADR-012" in text
    for key in ("`approaches`", "`approach`", "`force_minimum_approach`", "`adoption`"):
        assert key in text, f"ADR-041 does not name {key}"
    # Each new term is defined, in bold, not just mentioned: "pinned" or
    # "locks" elsewhere in the text would otherwise stand in for it.
    for term in ("catalogue", "layer", "overlay", "preset", "generation", "waiver", "lock",
                 "capability", "stage mode", "project file", "settings key", "pin",
                 "obligation", "classifier"):
        assert f"- **{term}**:" in text, f"ADR-041 does not define {term}"
