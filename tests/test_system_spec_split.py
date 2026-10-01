"""The living spec holds only current behaviour; the archive holds the rest.

`docs/system-spec.md` had grown to about 34,000 words, almost all of it
archived scenarios superseded by later ones. The derivation now writes the
current behaviour to `docs/system-spec.md`, with a one-line pointer, and
every archived section to `docs/system-spec-archive.md`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
from compass_pkg.flow import derive_system_spec  # noqa: E402


def _landed(root, slug, when, scn_id, title, intent):
    d = root / ".compass" / "work" / slug
    d.mkdir(parents=True)
    (d / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": slug, "created": "2026-05-25",
        "status": "landed", "land_timestamp": when,
        "assessment": {"risk": "contained", "familiarity": "greenfield", "size": "small"},
        "scenarios": [{"id": scn_id, "title": title, "intent": intent, "tests": []}],
    }, sort_keys=False))


def test_current_and_archived_behaviour_go_to_separate_files(tmp_path):
    _landed(tmp_path, "old", "2026-05-25T08:00:00+00:00", "SCN-OLD", "old way", "INT-1")
    _landed(tmp_path, "new", "2026-05-25T12:00:00+00:00", "SCN-NEW", "new way", "INT-1")
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
    _landed(tmp_path, "new", "2026-05-25T12:00:00+00:00", "SCN-NEW", "new way", "INT-1")
    derive_system_spec(str(tmp_path))
    archive = (tmp_path / "docs" / "system-spec-archive.md").read_text()
    assert ("### old way _(archived)_\n\n- **Scenario id:** `SCN-OLD`\n"
            "- **Intent:** `INT-1`\n- **Source issue:** `old`\n"
            "- **Landed:** 2026-05-25\n") in archive


def test_the_committed_living_spec_is_under_4000_words():
    spec = (ROOT / "docs" / "system-spec.md").read_text(encoding="utf-8")
    assert len(spec.split()) < 4000, len(spec.split())
    assert (ROOT / "docs" / "system-spec-archive.md").is_file()
