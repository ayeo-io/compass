"""The v2 artifact names - templates and the CLI code that resolves them.

The templates carry the v2 filenames, two new intake templates exist, and
the CLI resolves every per-issue artifact by its v2 name: `compass check`,
`analyze`, `receipt`, `next`, `flow` and the derivation all read the v2
names.

Docstrings cite the acceptance criteria by TRC id.
"""

# These tests assert the current file names; files written under older
# names still load (ADR-006).
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "cli"))

# The v1-to-v2 rename map. verification-report.md, manifest.yml,
# distribution-map.md, positioning.md, launch-readiness.md, ui-contract.md,
# and devlog.md keep their names - they are already plain English.
V2_TO_V1 = {
    "intent.md": "brief.md",
    "acceptance-criteria.md": "spec.feature.md",
    "delivery-approach.md": "route.md",
    "requirements-review.md": "clarifications.md",
    "technical-design.md": "plan.md",
}
NEW_INTAKE_TEMPLATES = {"bug-report.md", "incident.md"}


def test_templates_carry_the_v2_names():
    """`TRC-A1`: no template keeps a v1 name. 9.0.0 deleted every renamed
    template except the acceptance criteria, and both intake templates
    (ADR-091), so only that one is still expected."""
    names = {p.name for p in (REPO_ROOT / "templates").iterdir() if p.is_file()}
    leftover = set(V2_TO_V1.values()) & names
    assert "acceptance-criteria.md" in names
    assert not (set(V2_TO_V1) - {"acceptance-criteria.md"}) & names
    assert not NEW_INTAKE_TEMPLATES & names
    assert not leftover, f"templates still carrying v1 names: {sorted(leftover)}"


def test_artifact_path_resolves_v2_names_only(tmp_path):
    """`TRC-A2`: the runtime resolver reads v2 filenames only; the v1 map
    lives in the migration module."""
    from compass_pkg import core

    d = tmp_path / "issue"
    d.mkdir()
    (d / "brief.md").write_text("v1")
    (d / "intent.md").write_text("v2")
    resolved = Path(core.artifact_path(str(d), "intent.md"))
    assert resolved.name == "intent.md" and resolved.read_text() == "v2"


def test_migration_renames_a_v1_issue_directory(tmp_path):
    """`TRC-A3`: an un-migrated issue directory becomes resolvable by
    migrating it - the migration module owns the v1 filename map the
    runtime no longer consults."""
    from compass_pkg import core, migrate

    old_dir = tmp_path / "old-issue"
    old_dir.mkdir()
    (old_dir / "spec.feature.md").write_text("# old spec")
    notes = migrate.migrate_issue_dir(str(old_dir))
    assert any("spec.feature.md" in n for n in notes)
    resolved = Path(core.artifact_path(str(old_dir), "acceptance-criteria.md"))
    assert resolved.read_text() == "# old spec"


def test_bdd_extraction_output_is_named_for_acceptance_criteria():
    """`TRC-A4`: the extracted runnable Gherkin file is named
    acceptance-criteria.feature, not spec.feature, when no features dir is <!-- vocabulary-scan: allow - contrasts the v2 name with the retired one -->
    configured."""
    from compass_pkg import bdd

    out = bdd.default_extract_path("/tmp/some-issue-dir")
    assert Path(out).name == "acceptance-criteria.feature", (
        f"extraction output is {Path(out).name}; the v2 name is "
        "acceptance-criteria.feature"
    )
