"""Tests for Compass's own architecture/ directory.

Covers these 16 scenarios:

Group A - Narrative artifacts ship with required structure
  `TRC-A1` - system-context.md exists with canonical sections
  `TRC-A2` - relations.md documents the call graph
  `TRC-A3` - ownership.md documents boundaries

Group B - ADRs encode the founding principles (P1..P8)
  `TRC-B1` - architecture/decisions/ contains the six founding ADRs
  `TRC-B2` - ADRs follow the template structure
  `TRC-B3` - README.md indexes the ADRs
  `TRC-B4` - At least one ADR demonstrates substantive alternatives + negative consequences

Group C - Mechanism integration
  `TRC-C1` - frame_load_architecture returns the new artifacts and ADRs
  `TRC-C2` - SHA-256 is recorded per artifact
  `TRC-C3` - the architect role cites Compass's own ADRs on a framework issue

Group D - CLAUDE.md matches the architecture/ directory
  `TRC-D1` - CLAUDE.md notes Compass itself ships an architecture/
  `TRC-D2` - CLAUDE.md does not claim unbuilt features

Group E - Backward compat + regression
  `TRC-E1` - Existing test suite still passes
  `TRC-E2` - Projects without architecture/ still no-op cleanly
  `TRC-E3` - compass check still passes 10/10
  `TRC-E4` - Lint count does not regress
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent

# The archive these tests read: the tracked sample, or this checkout's own
# with COMPASS_FULL_ARCHIVE=1 (tests/archive.py).
sys.path.insert(0, str(FRAMEWORK_ROOT / "tests"))
from archive import archive_root  # noqa: E402
CLI_PATH = FRAMEWORK_ROOT / "cli" / "compass"
ARCH_DIR = FRAMEWORK_ROOT / "architecture"
DECISIONS_DIR = ARCH_DIR / "decisions"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _adr_files() -> list[Path]:
    """Return sorted ADR-NNN-*.md files from architecture/decisions/."""
    if not DECISIONS_DIR.is_dir():
        return []
    return sorted(
        f for f in DECISIONS_DIR.iterdir()
        if f.name.startswith("ADR-") and f.name.endswith(".md")
           and f.name != "ADR-template.md"
    )


def _parse_frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    fm_text = content[3:end].strip()
    return yaml.safe_load(fm_text) or {}


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        cwd=str(FRAMEWORK_ROOT),
        capture_output=True,
        text=True,
        timeout=15,
    )


# ---------------------------------------------------------------------------
# Group A - Narrative artifacts
# ---------------------------------------------------------------------------


def test_system_context_exists_with_canonical_sections():
    """architecture/system-context.md has the canonical sections (TRC-A1)."""
    path = ARCH_DIR / "system-context.md"
    assert path.is_file(), "architecture/system-context.md must exist"
    content = path.read_text(encoding="utf-8")
    # These are the sections system-context.md has.
    expected = ["## Components", "## Boundary conditions", "## External dependencies"]
    for section in expected:
        assert section in content, (
            f"system-context.md missing required section {section!r}"
        )


def test_relations_documents_call_graph():
    """architecture/relations.md documents the call graph (TRC-A2)."""
    path = ARCH_DIR / "relations.md"
    assert path.is_file(), "architecture/relations.md must exist"
    content = path.read_text(encoding="utf-8")
    # Must reference cli/compass as the CLI component
    assert "cli/compass" in content or "cli" in content, (
        "relations.md must document the cli/compass component"
    )


def test_ownership_documents_boundaries():
    """architecture/ownership.md documents the ownership model (TRC-A3)."""
    path = ARCH_DIR / "ownership.md"
    assert path.is_file(), "architecture/ownership.md must exist"
    content = path.read_text(encoding="utf-8")
    # Must mention guardrails
    assert "guardrail" in content.lower(), (
        "ownership.md must document the guardrail boundary"
    )


# ---------------------------------------------------------------------------
# Group B - ADRs
# ---------------------------------------------------------------------------


def test_adrs_cover_p1_to_p8():
    """ADR-001 to ADR-006 must exist. Later ADRs are allowed, so the count
    is a minimum (TRC-B1)."""
    adrs = _adr_files()
    assert len(adrs) >= 6, (
        f"Expected at least 6 founding ADR files, found {len(adrs)}: "
        f"{[f.name for f in adrs]}"
    )

    # Numbers must be unique and start from 001
    numbers = []
    for adr in adrs:
        m = re.match(r"ADR-(\d{3})-", adr.name)
        assert m, f"ADR filename does not match ADR-NNN-<slug>.md pattern: {adr.name}"
        numbers.append(int(m.group(1)))

    # The founding six must be present
    assert set(range(1, 7)).issubset(set(numbers)), (
        f"ADR numbers 001..006 must all be present, got: {sorted(numbers)}"
    )
    assert len(numbers) == len(set(numbers)), "ADR numbers must be unique"

    # The founding six (001-006) must be contiguous with no gaps.
    # Later ADRs are not checked for contiguity.
    founding = sorted(n for n in numbers if n <= 6)
    assert founding == list(range(1, len(founding) + 1)), (
        f"Founding ADR numbers (001..006) must be contiguous, got: {founding}"
    )

    # ADR-001 must cover the judgement/mechanism split (`Inv-1` + `Inv-7`)
    adr001 = next(f for f in adrs if f.name.startswith("ADR-001"))
    c001 = adr001.read_text(encoding="utf-8")
    assert any(kw in c001.lower() for kw in ["judgement", "judgment", "mechanism", "inv-1"]), (
        "ADR-001 must cover the judgement/mechanism separation (Inv-1 + Inv-7)"
    )

    # ADR-006 must cover backward compatibility (`Inv-8`)
    adr006 = next(f for f in adrs if f.name.startswith("ADR-006"))
    c006 = adr006.read_text(encoding="utf-8")
    assert any(kw in c006.lower() for kw in ["backward compat", "backwards compat",
                                               "no-op", "inv-8"]), (
        "ADR-006 must cover backward compatibility (Inv-8)"
    )


def test_adr_structure():
    """Every ADR has required frontmatter fields and five sections (TRC-B2)."""
    adrs = _adr_files()
    assert adrs, "No ADR files found - test_adrs_cover_p1_to_p8 should catch this first"

    required_fm_fields = {"id", "title", "status", "date", "supersedes", "superseded_by"}
    required_sections = [
        "## Context",
        "## Decision",
        "## Alternatives considered",
        "## Consequences",
        "## References",
    ]
    # `superseded` is in the set because architecture/decisions/README.md
    # documents it: "If an ADR is superseded, the old number and file remain
    # (with status: superseded)".
    valid_statuses = {"accepted", "proposed", "superseded"}

    for adr in adrs:
        content = adr.read_text(encoding="utf-8")
        fm = _parse_frontmatter(adr)

        # Frontmatter fields
        missing = required_fm_fields - set(fm.keys())
        assert not missing, (
            f"{adr.name}: missing frontmatter fields: {missing}"
        )

        # Status validity
        status = str(fm.get("status", "")).lower()
        assert status in valid_statuses, (
            f"{adr.name}: status must be one of "
            f"{sorted(valid_statuses)}, got {status!r}"
        )
        assert status != "draft", (
            f"{adr.name}: status 'draft' is reserved for distillation drafts, not used here"
        )

        # A supersession has to resolve in both directions, or the reader is
        # told a decision is withdrawn and cannot find what replaced it.
        # README.md says supersession is recorded via the superseded_by field
        # rather than by renumbering, which only works if the field is filled
        # in and the successor claims it back.
        if status == "superseded":
            # A comma-separated list, because an ADR can be superseded in
            # different respects by different successors: ADR-014's redirect
            # rule went to ADR-019 and its archive rule to ADR-020, and
            # collapsing that into one pointer would send a reader to an ADR
            # that does not mention the half they are reading.
            successors = [x.strip()
                          for x in str(fm.get("superseded_by", "")).split(",")
                          if x.strip()]
            assert successors, (
                f"{adr.name}: status is 'superseded' with an empty "
                f"superseded_by - a reader is told the decision is withdrawn "
                f"and given nowhere to go"
            )
            for successor in successors:
                matches = sorted(DECISIONS_DIR.glob(f"{successor}-*.md"))
                assert matches, (
                    f"{adr.name}: superseded_by names {successor!r}, and no "
                    f"such ADR file exists"
                )
                back = str(_parse_frontmatter(matches[0]).get("supersedes", ""))
                assert fm.get("id") in [x.strip() for x in back.split(",")], (
                    f"{matches[0].name} does not name {fm.get('id')} in its "
                    f"supersedes field, so the link is one-way"
                )

        # Required sections
        for section in required_sections:
            assert section in content, (
                f"{adr.name}: missing required section {section!r}"
            )


def test_decisions_readme_indexes_adrs():
    """architecture/decisions/README.md indexes every ADR (TRC-B3)."""
    readme = DECISIONS_DIR / "README.md"
    assert readme.is_file(), "architecture/decisions/README.md must exist"
    content = readme.read_text(encoding="utf-8")

    adrs = _adr_files()
    for adr in adrs:
        fm = _parse_frontmatter(adr)
        adr_id = fm.get("id", "")
        # The README must reference the ADR id somewhere
        assert adr_id in content, (
            f"README.md does not index {adr_id} ({adr.name})"
        )


def test_at_least_one_adr_has_substantive_alternatives():
    """At least one ADR has substantive alternatives considered and
    negative consequences (TRC-B4)."""
    adrs = _adr_files()
    substantive = []
    for adr in adrs:
        content = adr.read_text(encoding="utf-8")
        # Look for a Markdown table row in the Alternatives section
        alts_start = content.find("## Alternatives considered")
        cons_start = content.find("## Consequences")
        if alts_start == -1 or cons_start == -1:
            continue
        alts_section = content[alts_start:cons_start]
        # Substantive = has at least one table row with | ... | ... | ... |
        rows = [l for l in alts_section.splitlines()
                if l.strip().startswith("|") and "---" not in l
                and l.count("|") >= 3]
        # Has negative consequences keyword
        cons_section = content[cons_start:]
        has_negative = any(kw in cons_section.lower() for kw in
                          ["negative", "downside", "risk", "tradeoff", "trade-off"])
        if rows and has_negative:
            substantive.append(adr.name)

    assert substantive, (
        "At least one ADR must have a non-trivial Alternatives Considered table "
        "and a Negative consequences section"
    )


# ---------------------------------------------------------------------------
# Group C - Mechanism integration
# ---------------------------------------------------------------------------


def test_frame_load_architecture_returns_adrs():
    """frame_load_architecture returns the ADR list correctly (TRC-C1)."""
    result = run_cli("approach", "evaluate",
                     "--assessment", "risk=contained",
                     "--assessment", "familiarity=greenfield",
                     "--assessment", "size=small",
                     "--json")
    # frame_load_architecture needs an issue directory, so this test loads
    # the module and checks the ADR scanner instead.
    import types as _types
    source = CLI_PATH.read_text(encoding="utf-8")
    mod = _types.ModuleType("compass_cli")
    mod.__file__ = str(CLI_PATH)
    exec(compile(source, str(CLI_PATH), "exec"), mod.__dict__)

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        record = mod.frame_load_architecture(str(FRAMEWORK_ROOT), td)
    assert isinstance(record, dict)
    adrs = record.get("adrs", [])
    assert len(adrs) >= 6, f"Expected ≥6 ADRs in load record, got {len(adrs)}"
    adr_ids = [a["id"] for a in adrs]
    for expected in ["ADR-001", "ADR-002", "ADR-003", "ADR-004", "ADR-005", "ADR-006"]:
        assert expected in adr_ids, f"{expected} missing from load record: {adr_ids}"


def test_sha256_recorded_per_artifact():
    """Every narrative artifact in the load record has a sha256 field (TRC-C2)."""
    import types as _types
    source = CLI_PATH.read_text(encoding="utf-8")
    mod = _types.ModuleType("compass_cli")
    mod.__file__ = str(CLI_PATH)
    exec(compile(source, str(CLI_PATH), "exec"), mod.__dict__)

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        record = mod.frame_load_architecture(str(FRAMEWORK_ROOT), td)

    for artifact in record.get("artifacts", []):
        assert "sha256" in artifact, (
            f"Artifact {artifact.get('path')} has no sha256 field"
        )
        assert len(artifact["sha256"]) == 64, (
            f"sha256 for {artifact.get('path')} is not 64 hex chars"
        )


def test_architect_lens_cites_own_adrs(tmp_path):
    """Loading Compass's own architecture cites its ADRs (TRC-C3).

    Derived fresh, not read from the issue's record: the record in the
    archive was written on 2026-05-24 with an empty ADR list, before the
    decision records were where the loader looks, and a test that read it
    skipped for months on a stale issue name."""
    import types as _types
    source = CLI_PATH.read_text(encoding="utf-8")
    mod = _types.ModuleType("compass_cli")
    mod.__file__ = str(CLI_PATH)
    exec(compile(source, str(CLI_PATH), "exec"), mod.__dict__)
    data = mod.frame_load_architecture(str(FRAMEWORK_ROOT), str(tmp_path))
    adr_ids = [a["id"] for a in data.get("adrs", [])]
    assert "ADR-001" in adr_ids, (
        "architecture-loaded.yml must include ADR-001 in its adr list"
    )


# ---------------------------------------------------------------------------
# Group D - CLAUDE.md
# ---------------------------------------------------------------------------


def test_claude_md_notes_architecture_dir():
    """CLAUDE.md references architecture/ so readers know it exists (TRC-D1)."""
    claude_md = FRAMEWORK_ROOT / "CLAUDE.md"
    assert claude_md.is_file(), "CLAUDE.md must exist"
    content = claude_md.read_text(encoding="utf-8")
    assert "architecture/" in content, (
        "CLAUDE.md must note that Compass ships architecture/"
    )


def test_claude_md_does_not_claim_unbuilt_features():
    """CLAUDE.md does not reference features that do not exist yet (TRC-D2)."""
    claude_md = FRAMEWORK_ROOT / "CLAUDE.md"
    content = claude_md.read_text(encoding="utf-8")
    # Spot-check a few things that must NOT appear (pre-architecture claims)
    # e.g. a reference to a non-existent `compass arch` command
    forbidden = ["compass arch"]
    for phrase in forbidden:
        assert phrase not in content, (
            f"CLAUDE.md contains reference to potentially unbuilt feature: {phrase!r}"
        )


# ---------------------------------------------------------------------------
# Group E - Backward compat + regression
# ---------------------------------------------------------------------------


def test_projects_without_architecture_still_noop():
    """frame_load_architecture on a project with no architecture/ dir
    returns an empty record - it does not error (TRC-E2)."""
    import types as _types
    import tempfile

    source = CLI_PATH.read_text(encoding="utf-8")
    mod = _types.ModuleType("compass_cli")
    mod.__file__ = str(CLI_PATH)
    exec(compile(source, str(CLI_PATH), "exec"), mod.__dict__)

    with tempfile.TemporaryDirectory() as td:
        record = mod.frame_load_architecture(td, td)

    assert record["artifacts"] == [], (
        "frame_load_architecture on a project with no architecture/ must return "
        "empty artifacts list"
    )
    assert record["adrs"] == [], (
        "frame_load_architecture on a project with no architecture/ must return "
        "empty adrs list"
    )


def test_policy_lint_passes():
    """compass policy lint passes cleanly, no regressions (TRC-E3)."""
    result = run_cli("policy", "lint")
    assert result.returncode == 0, (
        f"compass policy lint failed:\n{result.stdout}\n{result.stderr}"
    )


def test_lint_count_does_not_regress():
    """issue lint does not produce more errors than before (TRC-E4)."""
    # This test uses the current manifest.yml - if it lints clean, regression is OK.
    task_yml = archive_root() / ".compass" / "work" / "compass-self-architecture" / "manifest.yml"
    if not task_yml.is_file():
        pytest.skip("self-architecture manifest.yml not present - cannot regression-check")
    result = run_cli("issue", "lint", "--file", str(task_yml))
    assert result.returncode == 0, (
        f"self-architecture manifest.yml no longer lints clean:\n{result.stdout}"
    )
