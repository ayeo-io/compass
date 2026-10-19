"""The migrator keeps its v1-to-v2 mapping after the stubs are removed.

ADR-014 deletes the deprecation stubs. It deliberately does NOT delete the
translation table `compass migrate` reads, and the distinction is the whole
decision:

  * A **stub** answers a caller who typed the old name. With no adopters, it
    is a promise kept to nobody.
  * A **mapping** reads a file that used the old name. Archives written under
    the v1 vocabulary still exist, and Compass tells people to keep them.

Deleting the second along with the first would make v1 archives unreadable.

Scenario ids: see docs/system-spec.md (RCD-F4).
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
MAP = ROOT / "cli" / "migrate-map.yml"

# A v1 manifest: retired key names, retired approach value, retired follow-up
# status. This is what a real archive looks like.
V1_SPINE = """schema_version: "1.2"
task: "legacy-issue"
created: "2026-01-05"
readings:
  risk: contained
  familiarity: brownfield-mapped
  size: small
  goal: delivery
  role: engineer
route: express
topology: solo
phases: {frame: full, specify: light}
"""


def _map():
    import yaml
    sys.path.insert(0, str(ROOT / "cli"))
    import compass_pkg                                   # noqa: F401
    return yaml.safe_load(MAP.read_text()) or {}


def test_rcd_f4_the_translation_table_survives():
    """The sections the migrator reads are still there."""
    data = _map()
    for section in ("values", "artifacts"):
        assert section in data and data[section], (
            f"migrate-map.yml lost its `{section}:` section. That is the "
            f"migrator's translation table for reading v1 archives, not a "
            f"deprecation stub - ADR-014 keeps it deliberately."
        )

    # The specific renames an archive actually needs.
    assert data["artifacts"].get("route.md") == "delivery-approach.md", (
        "the artifact rename map no longer resolves the v1 approach record"
    )
    assert data["values"]["delivery_approach"].get("express") == "quick-fix", (
        "the approach value map no longer resolves the v1 approach names"
    )


def test_rcd_f4b_a_v1_archive_still_lints_after_normalisation(tmp_path):
    """The mapping is not just present - it still does its job.

    A section that exists but is no longer consulted would pass the test
    above while leaving every v1 archive unreadable.
    """
    sys.path.insert(0, str(ROOT / "cli"))
    import compass_pkg                                   # noqa: F401
    import yaml
    from compass_pkg.core import normalize_spine

    manifest = yaml.safe_load(V1_SPINE)
    normalised = normalize_spine(manifest)

    assert "assessment" in normalised, (
        "a v1 manifest's `readings:` no longer normalises to `assessment:` - the "
        "read side of the mapping has stopped working, so every archived "
        "issue is unreadable"
    )
    assert normalised.get("delivery_approach"), (
        "a v1 manifest's `route:` no longer normalises to `delivery_approach:`"
    )


def test_rcd_f4c_migrate_still_runs(tmp_path):
    """The command itself still exists and reports on a v1 issue directory."""
    work = tmp_path / ".compass" / "work" / "legacy-issue"
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text(
        "version: 1.0.0\n", encoding="utf-8")
    (work / "manifest.yml").write_text(V1_SPINE, encoding="utf-8")
    (work / "route.md").write_text("# the v1 approach record\n", encoding="utf-8")

    # `migrate` is dry by default; --apply makes the change.
    result = subprocess.run(
        [sys.executable, str(CLI), "issue", "migrate"],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=120,
    )
    combined = result.stdout + result.stderr

    assert "delivery-approach.md" in combined, (
        f"`compass migrate` no longer reports the v1 artifact rename it would "
        f"apply, so the mapping is present but unused:\n{combined}"
    )
