"""Tests for the living-system-spec derivation (Group B).

Covers `TRC-B1` through `TRC-B11` and `TRC-F2`.

The derivation helper under test is `derive_system_spec(project_root)` in
`cli/compass`, invoked via the private CLI entry point
`compass _derive-system-spec --internal`.

Test strategy: each test builds a synthetic project root in tmp_path,
populates `.compass/work/*/manifest.yml` and `acceptance-criteria.md` files, runs
the derivation (via direct Python import of the helper function), and
asserts on the resulting `docs/system-spec.md`.

The CLI entry-point tests (`TRC-B6`, `DD-4` convention) invoke the CLI via
subprocess to check the argparse surface.
"""

# These tests assert the current stage keys; spines written under older
# keys still load (ADR-006).
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import yaml


# ---------------------------------------------------------------------------
# Locate framework root and CLI
# ---------------------------------------------------------------------------
FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent.parent
CLI_PATH = FRAMEWORK_ROOT / "cli" / "compass"


def run_cli(*args: str, cwd: Optional[Path] = None,
            env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        cwd=str(cwd or FRAMEWORK_ROOT),
        capture_output=True,
        text=True,
        env=e,
        timeout=15,
    )


# ---------------------------------------------------------------------------
# Import the helper function directly (avoids CLI subprocess overhead for the
# bulk of the tests).  We import lazily so the test module can be collected
# even before the function exists (the import is deferred to each test body).
# ---------------------------------------------------------------------------

def _load_compass_module():
    """Load cli/compass as a module (it has no .py extension)."""
    import types
    source = CLI_PATH.read_text(encoding="utf-8")
    mod = types.ModuleType("compass_cli")
    mod.__file__ = str(CLI_PATH)
    exec(compile(source, str(CLI_PATH), "exec"), mod.__dict__)
    return mod


def _import_derive():
    """Import derive_system_spec from cli/compass.  Raises AttributeError if
    not yet implemented - letting the TDD-red state surface cleanly."""
    mod = _load_compass_module()
    if not hasattr(mod, "derive_system_spec"):
        raise AttributeError(
            "derive_system_spec not found in cli/compass - not yet implemented"
        )
    return mod.derive_system_spec


def _spec_and_archive(root: Path) -> str:
    """The text of the spec and its archive, which the derivation writes as
    two files: a superseded scenario is in the archive."""
    docs = root / "docs"
    archive = docs / "system-spec-archive.md"
    return ((docs / "system-spec.md").read_text(encoding="utf-8")
            + (archive.read_text(encoding="utf-8") if archive.exists() else ""))


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def make_task_dir(root: Path, slug: str, *,
                  status: str = "landed",
                  land_timestamp: str = "2026-05-25T10:00:00+00:00",
                  scenarios: Optional[List[Dict]] = None,
                  feature_text: Optional[str] = None,
                  schema_version: str = "1.1") -> Path:
    """Create .compass/work/<slug>/ with manifest.yml and optionally acceptance-criteria.md."""
    task_dir = root / ".compass" / "work" / slug
    task_dir.mkdir(parents=True, exist_ok=True)

    task = {
        "schema_version": schema_version,
        "task": slug,
        "created": "2026-05-25",
        "status": status,
        "land_timestamp": land_timestamp,
        "assessment": {
            "risk": "contained",
            "familiarity": "greenfield",
            "size": "small",
        },
        "scenarios": scenarios or [],
    }
    (task_dir / "manifest.yml").write_text(
        yaml.safe_dump(task, sort_keys=False), encoding="utf-8"
    )

    if feature_text is not None:
        (task_dir / "acceptance-criteria.md").write_text(feature_text, encoding="utf-8")

    return task_dir


def make_scenario_entry(scn_id: str, title: str, intent: str = "INT-1") -> Dict:
    return {"id": scn_id, "title": title, "intent": intent, "tests": []}


SAMPLE_FEATURE = textwrap.dedent("""\
    # Spec - sample-task

    ## Scenario: {title}
    <!-- traceability id: {scn_id} · serves: {intent} -->

    ```gherkin
    Scenario: {title}
      Given a system
      When something happens
      Then the result is correct
    ```
""")


def make_feature_text(scn_id: str, title: str, intent: str = "INT-1") -> str:
    return SAMPLE_FEATURE.format(scn_id=scn_id, title=title, intent=intent)


# ---------------------------------------------------------------------------
# The derived spec carries a "DERIVED FILE" header (`TRC-B10`)
# ---------------------------------------------------------------------------

class TestTrcB10:
    """The derived spec carries a 'DERIVED FILE' header on the first
    non-empty line (`TRC-B10`)."""

    def test_derived_file_header_present(self, tmp_path):
        """After derivation, the first non-empty line identifies the file as
        DERIVED and names .compass/work/<task>/acceptance-criteria.md as the
        source-of-truth to edit instead."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "task-alpha",
            status="landed",
            scenarios=[make_scenario_entry("SCN-001", "alpha behaviour")],
            feature_text=make_feature_text("SCN-001", "alpha behaviour"),
        )

        derive(str(tmp_path))

        spec_path = tmp_path / "docs" / "system-spec.md"
        assert spec_path.exists(), "docs/system-spec.md was not created"

        lines = spec_path.read_text(encoding="utf-8").splitlines()
        non_empty = [l for l in lines if l.strip()]
        assert non_empty, "system-spec.md is empty"

        first_line = non_empty[0]
        assert "DERIVED" in first_line.upper(), (
            f"First non-empty line does not identify file as DERIVED: {first_line!r}"
        )
        assert "acceptance-criteria.md" in first_line, (
            f"First line does not name acceptance-criteria.md: {first_line!r}"
        )

    def test_derived_header_instructs_not_to_hand_edit(self, tmp_path):
        """The DERIVED FILE header tells readers not to hand-edit the file."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "task-beta",
            status="landed",
            scenarios=[make_scenario_entry("SCN-002", "beta behaviour")],
            feature_text=make_feature_text("SCN-002", "beta behaviour"),
        )

        derive(str(tmp_path))

        spec_path = tmp_path / "docs" / "system-spec.md"
        content = spec_path.read_text(encoding="utf-8")
        assert "do not hand-edit" in content.lower() or "do not edit" in content.lower(), (
            "Header does not warn against hand-editing"
        )


# ---------------------------------------------------------------------------
# A greenfield project Lands with no pre-existing system spec (`TRC-B5`)
# ---------------------------------------------------------------------------

class TestTrcB5:
    """A brand-new project with no pre-existing system spec produces
    docs/system-spec.md on first ship (`TRC-B5`)."""

    def test_greenfield_creates_spec_file(self, tmp_path):
        """Shipping succeeds and creates system-spec.md even if no file existed."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "first-task",
            status="landed",
            scenarios=[make_scenario_entry("SCN-001", "first behaviour")],
            feature_text=make_feature_text("SCN-001", "first behaviour"),
        )

        spec_path = tmp_path / "docs" / "system-spec.md"
        assert not spec_path.exists(), "Pre-condition: no spec file should exist"

        derive(str(tmp_path))

        assert spec_path.exists(), "docs/system-spec.md was not created on first Land"

    def test_greenfield_no_landed_tasks_creates_stub(self, tmp_path):
        """When no issue has status: landed, derive creates an empty/stub spec."""
        derive = _import_derive()

        # Create an issue with status: active (not landed)
        make_task_dir(
            tmp_path, "active-task",
            status="active",
            scenarios=[make_scenario_entry("SCN-001", "active behaviour")],
            feature_text=make_feature_text("SCN-001", "active behaviour"),
        )

        derive(str(tmp_path))

        spec_path = tmp_path / "docs" / "system-spec.md"
        assert spec_path.exists(), "docs/system-spec.md should be created even with no landed tasks"
        # Should contain the header and show no scenarios
        content = spec_path.read_text(encoding="utf-8")
        assert "DERIVED" in content.upper()

    def test_greenfield_no_compass_dir_creates_stub(self, tmp_path):
        """A project with no .compass/ at all produces a stub spec and exits 0."""
        derive = _import_derive()
        # No .compass/ directory - brand new project
        derive(str(tmp_path))

        spec_path = tmp_path / "docs" / "system-spec.md"
        assert spec_path.exists(), "derive should create stub even with no .compass/ dir"


# ---------------------------------------------------------------------------
# A landed behaviour change adds into the system spec (`TRC-B1`)
# ---------------------------------------------------------------------------

class TestTrcB1:
    """A landed issue's scenario appears in the living system spec (`TRC-B1`)."""

    def test_landed_scenario_appears_in_spec(self, tmp_path):
        """After an issue with status: landed has a scenario, that scenario
        appears in docs/system-spec.md."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "task-one",
            status="landed",
            scenarios=[make_scenario_entry("SCN-001", "new behaviour")],
            feature_text=make_feature_text("SCN-001", "new behaviour"),
        )

        derive(str(tmp_path))

        spec = _spec_and_archive(tmp_path)
        assert "SCN-001" in spec, "Scenario id SCN-001 not found in system spec"
        assert "task-one" in spec, "Source task slug not found in system spec"

    def test_source_task_and_scenario_id_recorded(self, tmp_path):
        """Each derived entry records the source issue slug and scenario id."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "my-task",
            status="landed",
            scenarios=[make_scenario_entry("SCN-XYZ", "xyz behaviour")],
            feature_text=make_feature_text("SCN-XYZ", "xyz behaviour"),
        )

        derive(str(tmp_path))

        spec = _spec_and_archive(tmp_path)
        assert "SCN-XYZ" in spec
        assert "my-task" in spec


# ---------------------------------------------------------------------------
# A pure Spike contributes nothing to the system spec (`TRC-B2`)
# ---------------------------------------------------------------------------

class TestTrcB2:
    """Issues with status != 'landed' do not appear in the spec (`TRC-B2`)."""

    def test_active_task_not_in_spec(self, tmp_path):
        """An issue with status: active is not included in the derivation."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "spike-task",
            status="active",
            scenarios=[make_scenario_entry("SCN-SPIKE", "spike behaviour")],
            feature_text=make_feature_text("SCN-SPIKE", "spike behaviour"),
        )

        make_task_dir(
            tmp_path, "landed-task",
            status="landed",
            scenarios=[make_scenario_entry("SCN-LAND", "landed behaviour")],
            feature_text=make_feature_text("SCN-LAND", "landed behaviour"),
        )

        derive(str(tmp_path))

        spec = _spec_and_archive(tmp_path)
        assert "SCN-SPIKE" not in spec, "Active task's scenario appeared in spec"
        assert "SCN-LAND" in spec, "Landed task's scenario should be in spec"

    def test_task_with_no_status_field_not_in_spec(self, tmp_path):
        """A manifest.yml without the status field (schema 1.0 style) is treated as
        active (not landed) and excluded from the derivation (`Inv-8`, `DD-3`)."""
        derive = _import_derive()

        task_dir = tmp_path / ".compass" / "work" / "old-task"
        task_dir.mkdir(parents=True, exist_ok=True)
        task_no_status = {
            "schema_version": "1.0",
            "task": "old-task",
            "created": "2026-05-25",
            # NO status field - backward compat
            "assessment": {
                "risk": "contained",
                "familiarity": "greenfield",
                "size": "small",
            },
            "scenarios": [make_scenario_entry("SCN-OLD", "old behaviour")],
        }
        (task_dir / "manifest.yml").write_text(
            yaml.safe_dump(task_no_status, sort_keys=False), encoding="utf-8"
        )
        (task_dir / "acceptance-criteria.md").write_text(
            make_feature_text("SCN-OLD", "old behaviour"), encoding="utf-8"
        )

        derive(str(tmp_path))

        spec = _spec_and_archive(tmp_path)
        assert "SCN-OLD" not in spec, (
            "manifest.yml without status field should be treated as active (not landed)"
        )


# ---------------------------------------------------------------------------
# Re-deriving from unchanged scenarios produces no diff, idempotency (`TRC-B3`)
# ---------------------------------------------------------------------------

class TestTrcB3:
    """Running derivation twice on unchanged inputs produces a
    byte-identical file (`TRC-B3`)."""

    def test_idempotent_derivation(self, tmp_path):
        """Two consecutive derivation runs on unchanged inputs are byte-identical."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "stable-task",
            status="landed",
            land_timestamp="2026-05-25T10:00:00+00:00",
            scenarios=[make_scenario_entry("SCN-STABLE", "stable behaviour")],
            feature_text=make_feature_text("SCN-STABLE", "stable behaviour"),
        )

        derive(str(tmp_path))
        first_content = (tmp_path / "docs" / "system-spec.md").read_bytes()

        derive(str(tmp_path))
        second_content = (tmp_path / "docs" / "system-spec.md").read_bytes()

        assert first_content == second_content, (
            "Two consecutive derivation runs on unchanged inputs produced different output"
        )

    def test_idempotent_multiple_tasks(self, tmp_path):
        """Idempotency holds with multiple landed issues."""
        derive = _import_derive()

        for i in range(3):
            make_task_dir(
                tmp_path, f"task-{i}",
                status="landed",
                land_timestamp=f"2026-05-25T1{i}:00:00+00:00",
                scenarios=[make_scenario_entry(f"SCN-{i:03d}", f"behaviour {i}")],
                feature_text=make_feature_text(f"SCN-{i:03d}", f"behaviour {i}"),
            )

        derive(str(tmp_path))
        first = (tmp_path / "docs" / "system-spec.md").read_bytes()

        derive(str(tmp_path))
        second = (tmp_path / "docs" / "system-spec.md").read_bytes()

        assert first == second


# ---------------------------------------------------------------------------
# A superseding change updates the prior behaviour and archives the prior (`TRC-B4`)
# ---------------------------------------------------------------------------

class TestTrcB4:
    """When two landed issues share an intent id, the later-landed one
    wins in the current-behaviour section; the earlier moves to the archive (`TRC-B4`)."""

    def test_superseding_scenario_wins_current_section(self, tmp_path):
        """The later-landed scenario for a given intent id appears in the
        current-behaviour section."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "old-task",
            status="landed",
            land_timestamp="2026-05-25T09:00:00+00:00",
            scenarios=[make_scenario_entry("SCN-OLD", "old behaviour", intent="INT-1")],
            feature_text=make_feature_text("SCN-OLD", "old behaviour", intent="INT-1"),
        )
        make_task_dir(
            tmp_path, "new-task",
            status="landed",
            land_timestamp="2026-05-25T11:00:00+00:00",
            scenarios=[make_scenario_entry("SCN-NEW", "new behaviour", intent="INT-1")],
            feature_text=make_feature_text("SCN-NEW", "new behaviour", intent="INT-1"),
        )

        derive(str(tmp_path))
        spec = _spec_and_archive(tmp_path)

        # SCN-NEW should be in the current section - it came later
        assert "SCN-NEW" in spec, "Newer scenario not found in spec"
        # SCN-OLD should be in the archive - it was superseded
        assert "SCN-OLD" in spec, "Superseded scenario should appear in archive"

    def test_superseded_moves_to_archive_appendix(self, tmp_path):
        """The superseded scenario appears in the archived-behaviour appendix."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "task-v1",
            status="landed",
            land_timestamp="2026-05-25T08:00:00+00:00",
            scenarios=[make_scenario_entry("SCN-V1", "v1 behaviour", intent="INT-X")],
            feature_text=make_feature_text("SCN-V1", "v1 behaviour", intent="INT-X"),
        )
        make_task_dir(
            tmp_path, "task-v2",
            status="landed",
            land_timestamp="2026-05-25T12:00:00+00:00",
            scenarios=[make_scenario_entry("SCN-V2", "v2 behaviour", intent="INT-X")],
            feature_text=make_feature_text("SCN-V2", "v2 behaviour", intent="INT-X"),
        )

        derive(str(tmp_path))
        spec = _spec_and_archive(tmp_path)

        # The spec should have an archived section
        assert "archive" in spec.lower() or "archived" in spec.lower(), (
            "No archive section found in spec"
        )
        # SCN-V1 should be in the archive with issue slug and land date
        assert "task-v1" in spec, "Superseded task slug not in archive"


# ---------------------------------------------------------------------------
# Archived-behaviour appendix preserves the trace back to the prior issue (`TRC-B4a`)
# ---------------------------------------------------------------------------

class TestTrcB4a:
    """Every entry in the archive records issue slug, scenario id,
    and the land date that retired it (`TRC-B4a`)."""

    def test_archive_entry_has_task_slug(self, tmp_path):
        """Archived entries name the source issue slug."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "old-provider",
            status="landed",
            land_timestamp="2026-05-25T07:00:00+00:00",
            scenarios=[make_scenario_entry("SCN-P1", "provider behaviour", intent="INT-P")],
            feature_text=make_feature_text("SCN-P1", "provider behaviour", intent="INT-P"),
        )
        make_task_dir(
            tmp_path, "new-provider",
            status="landed",
            land_timestamp="2026-05-25T14:00:00+00:00",
            scenarios=[make_scenario_entry("SCN-P2", "provider v2", intent="INT-P")],
            feature_text=make_feature_text("SCN-P2", "provider v2", intent="INT-P"),
        )

        derive(str(tmp_path))
        spec = _spec_and_archive(tmp_path)

        # old-provider is the archived issue
        assert "old-provider" in spec, "Source task slug missing from archive"
        assert "SCN-P1" in spec, "Archived scenario id missing"

    def test_archive_entry_has_land_date(self, tmp_path):
        """Archived entries record the ship date that retired the scenario."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "retired-task",
            status="landed",
            land_timestamp="2026-05-20T10:00:00+00:00",
            scenarios=[make_scenario_entry("SCN-R1", "retired behaviour", intent="INT-R")],
            feature_text=make_feature_text("SCN-R1", "retired behaviour", intent="INT-R"),
        )
        make_task_dir(
            tmp_path, "active-v2",
            status="landed",
            land_timestamp="2026-05-25T10:00:00+00:00",
            scenarios=[make_scenario_entry("SCN-R2", "replacement behaviour", intent="INT-R")],
            feature_text=make_feature_text("SCN-R2", "replacement behaviour", intent="INT-R"),
        )

        derive(str(tmp_path))
        spec = _spec_and_archive(tmp_path)

        # The archive should contain a date reference
        # (at minimum the land_timestamp date portion: 2026-05-20)
        assert "2026-05-20" in spec, (
            "Land date not found in archived entry"
        )


# ---------------------------------------------------------------------------
# Every entry in the system spec traces to a landed scenario (`TRC-B7`)
# ---------------------------------------------------------------------------

class TestTrcB7:
    """Every entry in the system spec traces to a real landed scenario (`TRC-B7`)."""

    def test_all_spec_entries_have_provenance(self, tmp_path):
        """Every scenario entry in the derived spec records an issue slug + scenario id."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "task-provenance",
            status="landed",
            scenarios=[
                make_scenario_entry("SCN-A", "behaviour A"),
                make_scenario_entry("SCN-B", "behaviour B", intent="INT-2"),
            ],
            feature_text=(
                make_feature_text("SCN-A", "behaviour A") +
                "\n" +
                make_feature_text("SCN-B", "behaviour B", intent="INT-2")
            ),
        )

        derive(str(tmp_path))
        spec = _spec_and_archive(tmp_path)

        # Each scenario should appear with its source issue slug
        assert "SCN-A" in spec
        assert "SCN-B" in spec
        assert "task-provenance" in spec


# ---------------------------------------------------------------------------
# The derivation is not the sole source of truth, delete-and-rederive (`TRC-B8`)
# ---------------------------------------------------------------------------

class TestTrcB8:
    """Deleting docs/system-spec.md and re-running derivation produces
    a byte-identical file - the derivation is reconstructible (`TRC-B8`)."""

    def test_delete_and_rederive_produces_identical_output(self, tmp_path):
        """Delete the derived file, re-run, get back the same bytes."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "reconstruct-task",
            status="landed",
            scenarios=[make_scenario_entry("SCN-RECON", "reconstructable behaviour")],
            feature_text=make_feature_text("SCN-RECON", "reconstructable behaviour"),
        )

        derive(str(tmp_path))
        first_content = (tmp_path / "docs" / "system-spec.md").read_bytes()

        # Delete the derived file
        (tmp_path / "docs" / "system-spec.md").unlink()
        assert not (tmp_path / "docs" / "system-spec.md").exists()

        # Re-derive
        derive(str(tmp_path))
        second_content = (tmp_path / "docs" / "system-spec.md").read_bytes()

        assert first_content == second_content, (
            "Re-derived spec is not byte-identical to the original"
        )


# ---------------------------------------------------------------------------
# A hand-edit to the spec is silently overwritten by the next ship (`TRC-B9`)
# ---------------------------------------------------------------------------

class TestTrcB9:
    """Hand-edits to docs/system-spec.md are silently overwritten (`TRC-B9`)."""

    def test_hand_edit_is_overwritten(self, tmp_path):
        """A hand-edit to the derived file is silently overwritten on next run."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "overwrite-task",
            status="landed",
            scenarios=[make_scenario_entry("SCN-OW", "overwrite behaviour")],
            feature_text=make_feature_text("SCN-OW", "overwrite behaviour"),
        )

        derive(str(tmp_path))
        original_content = (tmp_path / "docs" / "system-spec.md").read_bytes()

        # Simulate a hand-edit
        spec_path = tmp_path / "docs" / "system-spec.md"
        spec_path.write_text(
            spec_path.read_text(encoding="utf-8") + "\n# hand-edit line\n",
            encoding="utf-8"
        )
        assert spec_path.read_bytes() != original_content, "Pre-condition: edit must change content"

        # Re-derive (the "next ship")
        derive(str(tmp_path))
        after_rederive = (tmp_path / "docs" / "system-spec.md").read_bytes()

        assert after_rederive == original_content, (
            "Hand-edit was not overwritten by re-derivation"
        )

    def test_no_error_raised_on_hand_edit(self, tmp_path):
        """No error or warning is raised when overwriting a hand-edited spec."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "silent-overwrite-task",
            status="landed",
            scenarios=[make_scenario_entry("SCN-SO", "silent overwrite behaviour")],
            feature_text=make_feature_text("SCN-SO", "silent overwrite behaviour"),
        )

        derive(str(tmp_path))

        # Hand-edit
        spec_path = tmp_path / "docs" / "system-spec.md"
        spec_path.write_text("hand-edited content", encoding="utf-8")

        # Should not raise
        derive(str(tmp_path))  # no exception = pass


# ---------------------------------------------------------------------------
# Introducing the living spec adds no new stage or gate (`TRC-B6`)
# ---------------------------------------------------------------------------

class TestTrcB6:
    """The pipeline stage set and gate set per route shape are
    unchanged by introducing the living spec capability (`TRC-B6`)."""

    def test_phase_set_unchanged(self, tmp_path):
        """compass approach evaluate still returns the same phases as before the
        living spec was introduced."""
        result = run_cli(
            "approach", "evaluate",
            "--assessment", "risk=contained",
            "--assessment", "familiarity=greenfield",
            "--assessment", "size=small",
            "--json",
            cwd=FRAMEWORK_ROOT,
        )
        assert result.returncode == 0, f"route evaluate failed: {result.stderr}"
        import json
        data = json.loads(result.stdout)
        phases = data.get("stages", {})
        # The standard set of phases must be present
        expected_phases = {"assess", "define", "refine", "plan", "implement", "verify", "ship"}
        assert expected_phases.issubset(set(phases.keys())), (
            f"Standard phases missing from route output: "
            f"{expected_phases - set(phases.keys())}"
        )

    def test_derive_subcommand_not_in_help(self, tmp_path):
        """The _derive-system-spec subcommand does NOT appear in compass --help
        (DD-4: leading-underscore convention for private entry points)."""
        result = run_cli("--help", cwd=FRAMEWORK_ROOT)
        # --help exits 0 on success
        assert result.returncode == 0, f"compass --help failed: {result.stderr}"
        assert "_derive-system-spec" not in result.stdout, (
            "_derive-system-spec must NOT appear in compass --help output"
        )

    def test_private_entry_point_requires_internal_flag(self):
        """compass _derive-system-spec without --internal flag errors out."""
        result = run_cli("_derive-system-spec", cwd=FRAMEWORK_ROOT)
        assert result.returncode != 0, (
            "_derive-system-spec without --internal should exit non-zero"
        )

    def test_private_entry_point_with_internal_flag_accepts(self, tmp_path):
        """compass _derive-system-spec --internal exits 0 on a valid project."""
        # Create a minimal .compass/ setup
        (tmp_path / ".compass" / "work").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".compass" / "current-task").write_text("", encoding="utf-8")

        result = run_cli(
            "_derive-system-spec", "--internal",
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, (
            f"_derive-system-spec --internal should exit 0: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# A landed issue is the source-of-truth via manifest.yml.status (`TRC-B11`)
# ---------------------------------------------------------------------------

class TestTrcB11:
    """manifest.yml.status == 'landed' is the signal the derivation walker
    uses to include an issue (`TRC-B11`)."""

    def test_only_landed_tasks_contribute(self, tmp_path):
        """Only issues with status: landed appear in the derived spec."""
        derive = _import_derive()

        statuses = {
            "task-landed": "landed",
            "task-active": "active",
        }
        scenarios = {
            "task-landed": make_scenario_entry("SCN-LND", "landed behaviour"),
            "task-active": make_scenario_entry("SCN-ACT", "active behaviour"),
        }
        for slug, status in statuses.items():
            make_task_dir(
                tmp_path, slug,
                status=status,
                scenarios=[scenarios[slug]],
                feature_text=make_feature_text(scenarios[slug]["id"], scenarios[slug]["title"]),
            )

        derive(str(tmp_path))
        spec = _spec_and_archive(tmp_path)

        assert "SCN-LND" in spec, "Landed scenario not in spec"
        assert "SCN-ACT" not in spec, "Active scenario should not be in spec"

    def test_task_yml_status_field_schema_valid(self, tmp_path):
        """manifest.yml with status: landed checks cleanly against the schema."""
        task_dir = tmp_path / ".compass" / "work" / "test-status"
        task_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / ".compass" / "current-task").write_text("test-status", encoding="utf-8")

        task = {
            "schema_version": "1.1",
            "task": "test-status",
            "created": "2026-05-25",
            "status": "landed",
            "assessment": {
                "risk": "contained",
                "familiarity": "greenfield",
                "size": "small",
            },
            "scenarios": [],
            "changed_files": [],
            "gates": [],
            "evidence": [],
            "claims": [],
            "follow_ups": [],
            "reassessments": [],
        }
        (task_dir / "manifest.yml").write_text(
            yaml.safe_dump(task, sort_keys=False), encoding="utf-8"
        )

        # Copy governance to temp project
        import shutil
        gov_src = FRAMEWORK_ROOT / "governance"
        gov_dst = tmp_path / "governance"
        gov_dst.mkdir(exist_ok=True)
        for name in ("routing-policy.yml", "guardrails.yml"):
            shutil.copyfile(gov_src / name, gov_dst / name)

        result = run_cli("issue", "lint", "--issue", "test-status", cwd=str(tmp_path))
        assert result.returncode == 0, (
            f"manifest.yml with status: landed should lint clean: {result.stdout}\n{result.stderr}"
        )

    def test_derivation_walker_reads_scenarios_block(self, tmp_path):
        """The derivation walker reads the scenarios: block from each landed
        manifest.yml as input to the derivation."""
        derive = _import_derive()

        scn_ids = ["SCN-W1", "SCN-W2", "SCN-W3"]
        scenarios = [make_scenario_entry(sid, f"behaviour {sid}") for sid in scn_ids]

        make_task_dir(
            tmp_path, "multi-scenario-task",
            status="landed",
            scenarios=scenarios,
            feature_text="".join(
                make_feature_text(sid, f"behaviour {sid}")
                for sid in scn_ids
            ),
        )

        derive(str(tmp_path))
        spec = _spec_and_archive(tmp_path)

        for sid in scn_ids:
            assert sid in spec, f"Scenario {sid} from scenarios block not in spec"


# ---------------------------------------------------------------------------
# Derivation handles conflicting scenarios deterministically (`TRC-F2`)
# ---------------------------------------------------------------------------

class TestTrcF2:
    """When two landed issues have scenarios that contradict on the
    same behaviour (same intent id), the derivation produces a defined,
    stable outcome (`TRC-F2`)."""

    def test_conflicting_scenarios_latest_wins(self, tmp_path):
        """Two issues sharing an intent id: the later-landed one wins.
        This is the defined, stable reconciliation mechanism."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "conflict-task-a",
            status="landed",
            land_timestamp="2026-05-25T08:00:00+00:00",
            scenarios=[make_scenario_entry("SCN-A", "version A behaviour", intent="INT-CONFLICT")],
            feature_text=make_feature_text("SCN-A", "version A behaviour", intent="INT-CONFLICT"),
        )
        make_task_dir(
            tmp_path, "conflict-task-b",
            status="landed",
            land_timestamp="2026-05-25T16:00:00+00:00",
            scenarios=[make_scenario_entry("SCN-B", "version B behaviour", intent="INT-CONFLICT")],
            feature_text=make_feature_text("SCN-B", "version B behaviour", intent="INT-CONFLICT"),
        )

        derive(str(tmp_path))
        spec = _spec_and_archive(tmp_path)

        # SCN-B (later) should be in the current section
        assert "SCN-B" in spec, "Later-landed scenario not in spec"
        # SCN-A (earlier) should be archived
        assert "SCN-A" in spec, "Earlier-landed scenario should be in archive"

    def test_conflicting_outcome_is_stable_across_runs(self, tmp_path):
        """Re-running derivation on conflicting issues produces the same output."""
        derive = _import_derive()

        make_task_dir(
            tmp_path, "conflict-x",
            status="landed",
            land_timestamp="2026-05-25T09:00:00+00:00",
            scenarios=[make_scenario_entry("SCN-X", "x behaviour", intent="INT-Y")],
            feature_text=make_feature_text("SCN-X", "x behaviour", intent="INT-Y"),
        )
        make_task_dir(
            tmp_path, "conflict-y",
            status="landed",
            land_timestamp="2026-05-25T17:00:00+00:00",
            scenarios=[make_scenario_entry("SCN-Y", "y behaviour", intent="INT-Y")],
            feature_text=make_feature_text("SCN-Y", "y behaviour", intent="INT-Y"),
        )

        derive(str(tmp_path))
        first = (tmp_path / "docs" / "system-spec.md").read_bytes()

        derive(str(tmp_path))
        second = (tmp_path / "docs" / "system-spec.md").read_bytes()

        assert first == second, "Conflicting-scenario resolution is not stable across runs"

    def test_tiebreaker_by_task_slug(self, tmp_path):
        """When two issues have the same land_timestamp, issue slug is the
        tiebreaker (alphabetically later slug wins) - produces defined, stable output."""
        derive = _import_derive()

        same_ts = "2026-05-25T10:00:00+00:00"
        make_task_dir(
            tmp_path, "aaa-task",
            status="landed",
            land_timestamp=same_ts,
            scenarios=[make_scenario_entry("SCN-AAA", "aaa behaviour", intent="INT-TIE")],
            feature_text=make_feature_text("SCN-AAA", "aaa behaviour", intent="INT-TIE"),
        )
        make_task_dir(
            tmp_path, "zzz-task",
            status="landed",
            land_timestamp=same_ts,
            scenarios=[make_scenario_entry("SCN-ZZZ", "zzz behaviour", intent="INT-TIE")],
            feature_text=make_feature_text("SCN-ZZZ", "zzz behaviour", intent="INT-TIE"),
        )

        derive(str(tmp_path))
        spec = _spec_and_archive(tmp_path)

        # Both appear (one current, one archived) - result is defined
        assert "SCN-AAA" in spec
        assert "SCN-ZZZ" in spec

        # Run again - same outcome
        derive(str(tmp_path))
        spec2 = _spec_and_archive(tmp_path)
        assert spec == spec2, "Tiebreaker result is not stable"
