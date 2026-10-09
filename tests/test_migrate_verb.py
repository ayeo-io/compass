"""`compass migrate` reports by default; `--apply` makes the change; a second
apply changes nothing. The v1-to-v2 mapping lives in cli/migrate-map.yml.

The mapping lives in the scan-exempt cli/migrate-map.yml, which the migrator
consumes, so the enforced CLI never carries a v1 spelling in a literal. The
1.x fixtures are constructed here: nothing current serves as un-migrated
input, because this repository's own archive is already migrated.
"""

# These tests assert the current names (technical-design.md, intent.md).
# Older manifests and documents still load (ADR-006).
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
CLI = REPO_ROOT / "cli" / "compass"

V1_SPINE = {
    "schema_version": "1.1", "task": "old-one", "created": "2026-01-01",
    "status": "landed",
    "readings": {"blast_radius": "contained", "terrain": "greenfield",
                 "magnitude": "small", "intent": "delivery",
                 "role": "engineer", "touches": []},
    "route": "express", "topology": "solo", "fired_guardrails": [],
    "phases": {}, "evidence": [], "gates": [], "scenarios": [],
    "changed_files": [], "claims": [],
    "backfills": [{"id": "BF-1", "description": "d", "status": "owed"}],
    "reframes": [], "friction": [],
}


def _v1_project(tmp_path):
    root = tmp_path / "proj"
    d = root / ".compass" / "work" / "old-one"
    d.mkdir(parents=True)
    (d / "manifest.yml").write_text(yaml.safe_dump(V1_SPINE, sort_keys=False))
    (d / "route.md").write_text("# Route\n")
    (d / "brief.md").write_text("# Brief\n")
    return root


def _run(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=str(root),
                          capture_output=True, text=True, timeout=60)


def test_dry_run_reports_and_writes_nothing(tmp_path):
    """`TRC-1`: the default run is a report, not a change - it names what
    would happen and how to make it happen, and touches nothing."""
    root = _v1_project(tmp_path)
    before = sorted(p.name for p in
                    (root / ".compass" / "work" / "old-one").iterdir())
    r = _run(root, "migrate")
    assert r.returncode == 0, r.stderr[-400:]
    assert "would" in r.stdout.lower(), (
        "the dry-run report does not speak in the conditional:\n" + r.stdout)
    assert "--apply" in r.stdout, (
        "the report does not tell the reader how to execute:\n" + r.stdout)
    after = sorted(p.name for p in
                   (root / ".compass" / "work" / "old-one").iterdir())
    assert before == after, "dry run changed the tree"
    manifest = yaml.safe_load(
        (root / ".compass" / "work" / "old-one" / "manifest.yml").read_text())
    assert "readings" in manifest, "dry run rewrote the manifest"


def test_apply_migrates_a_v1_tree(tmp_path):
    """`TRC-2`: --apply renames the v1 artifacts and rewrites the manifest to
    schema 2.0 - keys, values, and filenames."""
    root = _v1_project(tmp_path)
    r = _run(root, "migrate", "--apply")
    assert r.returncode == 0, r.stderr[-400:]
    d = root / ".compass" / "work" / "old-one"
    # `migrate` renames the file and moves it to
    # `docs/compass/<created>-<slug>/`, so ask the resolver for it.
    import sys as _sys
    _sys.path.insert(0, str(REPO_ROOT / "cli"))
    from compass_pkg.core import FOUND, resolve_artifact
    for kind, retired in (("delivery-approach", "route.md"),
                          ("intent", "brief.md")):
        state, path, reason = resolve_artifact(str(d), kind)
        assert state == FOUND, (
            f"{retired} did not rename: {kind} resolves as {state} ({reason})")
        assert "docs/compass" in path.replace("\\", "/"), (
            f"{kind} was renamed but not relocated: {path}")
    assert not (d / "route.md").exists()
    # `TRC-E5` leaves a pointer at this one name, so an install predating the
    # artifact registry is not locked out of every code edit. A pointer holds
    # the new path and nothing else, so it is not the record left behind.
    left = (d / "delivery-approach.md").read_text(encoding="utf-8")
    assert "<!-- compass: moved -->" in left, (
        "the renamed file is still beside the manifest as a document rather "
        f"than as the TRC-E5 pointer:\n{left[:200]}")
    manifest = yaml.safe_load((d / "manifest.yml").read_text())
    assert str(manifest["schema_version"]) == "3.0"
    assert "assessment" in manifest and "readings" not in manifest
    assert manifest["follow_ups"][0]["status"] == "outstanding", (
        "the 1.x follow-up state did not migrate")


def test_second_apply_is_a_no_op(tmp_path):
    """`TRC-3`: idempotent - the second apply changes nothing and says so."""
    root = _v1_project(tmp_path)
    _run(root, "migrate", "--apply")
    d = root / ".compass" / "work" / "old-one"
    snapshot = {p.name: p.read_bytes() for p in d.iterdir() if p.is_file()}
    r = _run(root, "migrate", "--apply")
    assert r.returncode == 0, r.stderr[-400:]
    after = {p.name: p.read_bytes() for p in d.iterdir() if p.is_file()}
    assert snapshot == after, "the second apply changed the tree"
    assert "nothing" in r.stdout.lower() or "0 " in r.stdout, (
        "the no-op run does not say it found nothing to do:\n" + r.stdout)


def test_the_reports_name_the_schema_the_manifest_is_written_in(tmp_path):
    """The apply writes schema 3.0, so the report must not say 2.0."""
    root = _v1_project(tmp_path)
    applied = _run(root, "migrate", "--apply")
    assert "schema 3.0" in applied.stdout and "schema 2.0" not in applied.stdout, applied.stdout
    again = _run(root, "migrate", "--apply")
    assert "schema 3.0" in again.stdout and "schema 2.0" not in again.stdout, again.stdout


def test_mapping_lives_in_the_exempt_data_file():
    """`TRC-4`: the artifact map is data in cli/migrate-map.yml, and the
    migration module consumes it - the enforced CLI never spells a v1
    name in a literal that teaches."""
    data = yaml.safe_load(
        (REPO_ROOT / "cli" / "migrate-map.yml").read_text(encoding="utf-8"))
    artifacts = data.get("artifacts")
    assert artifacts, "migrate-map.yml has no artifacts section"
    assert artifacts.get("route.md") == "delivery-approach.md"
    assert artifacts.get("brief.md") == "intent.md"
    sys.path.insert(0, str(REPO_ROOT / "cli"))
    from compass_pkg import migrate
    assert migrate.artifact_name_map() == artifacts, (
        "the migration module does not consume the data file's map")


def test_apply_migrates_the_shape_value(tmp_path):
    """A migrated manifest must speak the v2 change-type value, not the v1
    shape name - all five cases, with hotfix and spike keeping their
    spelling. The normaliser and the receipt's display layer agree with the
    migrated output."""
    cases = {"express": "quick-fix", "standard": "regular",
             "expedition": "full", "hotfix": "hotfix",
             "spike": "spike"}
    root = tmp_path / "proj"
    for i, (v1, v2) in enumerate(cases.items()):
        d = root / ".compass" / "work" / f"t{i}"
        d.mkdir(parents=True)
        manifest = dict(V1_SPINE); manifest["task"] = f"t{i}"; manifest["route"] = v1
        (d / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    r = _run(root, "migrate", "--apply")
    assert r.returncode == 0, r.stderr[-400:]
    for i, (v1, v2) in enumerate(cases.items()):
        manifest = yaml.safe_load(
            (root / ".compass" / "work" / f"t{i}" / "manifest.yml").read_text())
        assert manifest["delivery_approach"] == v2, (
            f"{v1} migrated to {manifest['delivery_approach']!r}, wanted {v2!r}")
    sys.path.insert(0, str(REPO_ROOT / "cli"))
    from compass_pkg.core import display_shape, normalize_spine
    assert display_shape("quick-fix") == "quick fix", (
        "the receipt would print the machine hyphen for a migrated value")
    norm = normalize_spine({"route": "expedition"})
    assert norm["delivery_approach"] == "full", (
        "the normalizer does not agree with the migrated value")


def test_report_pluralises_properly(tmp_path):
    """'1 issue directorie(s)' is not a sentence."""
    root = _v1_project(tmp_path)
    r = _run(root, "migrate")
    assert "directorie(s)" not in r.stdout, r.stdout
    assert "1 issue directory" in r.stdout, (
        "the singular case does not read as prose:\n" + r.stdout)
