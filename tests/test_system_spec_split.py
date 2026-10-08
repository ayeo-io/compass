"""The living spec holds only current behaviour; the archive holds the rest.

The derivation writes the current behaviour to `docs/system-spec.md`, with a
one-line pointer, and every archived section to `docs/system-spec-archive.md`.
The spec has no word cap: it keeps every current scenario, one issue heading
and one line per scenario.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
from compass_pkg.flow import derive_system_spec  # noqa: E402


def _landed(root, slug, when, scn_id, title, intent):
    """One landed issue holding an old scenario that names its replacement."""
    d = root / ".compass" / "work" / slug
    d.mkdir(parents=True)
    (d / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": slug, "created": "2026-05-25",
        "status": "landed", "land_timestamp": when,
        "assessment": {"risk": "contained", "familiarity": "greenfield", "size": "small"},
        "scenarios": [
            {"id": scn_id, "title": title, "intent": intent, "tests": [],
             "superseded_by": ["SCN-NEW"]},
            {"id": "SCN-NEW", "title": "new way", "intent": intent, "tests": []},
        ],
    }, sort_keys=False))


def test_current_and_archived_behaviour_go_to_separate_files(tmp_path):
    _landed(tmp_path, "old", "2026-05-25T08:00:00+00:00", "SCN-OLD", "old way", "INT-1")
    derive_system_spec(str(tmp_path))
    spec = (tmp_path / "docs" / "system-spec.md").read_text()
    archive = (tmp_path / "docs" / "system-spec-archive.md").read_text()
    assert "SCN-NEW" in spec and "SCN-OLD" not in spec
    assert "## Archived Behaviour" not in spec
    assert "system-spec-archive.md" in spec
    assert "## Archived Behaviour" in archive
    assert "### old way _(archived)_" in archive and "`SCN-OLD`" in archive
    assert "SCN-NEW" not in archive


def test_the_archive_carries_each_section_as_the_one_file_did(tmp_path):
    """Byte-preserved: each archived section is the same text it was."""
    _landed(tmp_path, "old", "2026-05-25T08:00:00+00:00", "SCN-OLD", "old way", "INT-1")
    derive_system_spec(str(tmp_path))
    archive = (tmp_path / "docs" / "system-spec-archive.md").read_text()
    assert ("### old way _(archived)_\n\n- **Scenario id:** `SCN-OLD`\n"
            "- **Intent:** `INT-1`\n- **Source issue:** `old`\n"
            "- **Landed:** 2026-05-25\n") in archive


def _write_issue(root, slug, when, scenarios):
    d = root / ".compass" / "work" / slug
    d.mkdir(parents=True)
    (d / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": slug, "created": "2026-05-25",
        "status": "landed", "land_timestamp": when,
        "assessment": {"risk": "contained", "familiarity": "greenfield", "size": "small"},
        "scenarios": scenarios,
    }, sort_keys=False))


def _entries(spec):
    """The scenario lines of the current-behaviour section."""
    return [ln for ln in spec.splitlines() if ln.startswith("- `")]


def test_an_issue_is_one_heading_and_each_scenario_one_line(tmp_path):
    _write_issue(tmp_path, "alpha", "2026-05-25T08:00:00+00:00", [
        {"id": "TRC-001", "title": "first\nbehaviour", "intent": "INT-1", "tests": []},
        {"id": "TRC-002", "title": "second behaviour", "intent": ["INT-1", "INT-2"],
         "tests": []},
    ])
    derive_system_spec(str(tmp_path))
    spec = (tmp_path / "docs" / "system-spec.md").read_text()
    assert "### alpha (completed 2026-05-25)\n" in spec
    assert _entries(spec) == ["- `TRC-001` first behaviour",
                              "- `TRC-002` second behaviour"]


def test_the_spec_holds_exactly_the_landed_scenarios_not_superseded(tmp_path):
    _write_issue(tmp_path, "alpha", "2026-05-25T08:00:00+00:00", [
        {"id": "TRC-001", "title": "kept", "intent": "INT-1", "tests": []},
        {"id": "TRC-002", "title": "replaced", "intent": "INT-1", "tests": [],
         "superseded_by": ["TRC-001"]},
    ])
    _write_issue(tmp_path, "beta", "2026-05-26T08:00:00+00:00", [
        {"id": "TRC-001", "title": "same ids, other issue", "intent": "INT-1",
         "tests": []},
    ])
    derive_system_spec(str(tmp_path))
    spec = (tmp_path / "docs" / "system-spec.md").read_text()
    assert _entries(spec) == ["- `TRC-001` kept",
                              "- `TRC-001` same ids, other issue"]


def test_the_committed_spec_lists_every_non_superseded_scenario_of_its_issues():
    """Counted against the manifests of the issues the spec names."""
    work = ROOT / ".compass" / "work"
    spec = (ROOT / "docs" / "system-spec.md").read_text(encoding="utf-8")
    headings = [ln for ln in spec.splitlines() if ln.startswith("### ")]
    # A spec derived before 6.0.0 says "landed"; the next derivation says
    # "completed". Both name an issue.
    assert headings and all(re.fullmatch(r"### \S+ \((?:landed|completed) [0-9-]*\)", h)
                            for h in headings), "an issue is not one heading"
    expected = 0
    for heading in headings:
        manifest = work / heading[4:].split(" (")[0] / "manifest.yml"
        if not manifest.is_file():
            return  # the local archive of issues lacks one, so cannot count
        scenarios = (yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}).get(
            "scenarios") or []
        expected += sum(1 for s in scenarios
                        if isinstance(s, dict) and not s.get("superseded_by"))
    assert len(_entries(spec)) == expected
