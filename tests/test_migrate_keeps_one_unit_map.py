"""`compass issue migrate` keeps a distribution map that declares `units: 1`.

The stub rule renames a lightweight map on an issue with fewer than two
subtasks to `distribution-map.md.v6.bak` and supersedes its entry. A map that
declares one work unit is not a stub: `multiagent-run-recorded` reads it from
the registry, so the rename made the check fail on every such issue.

The fixture builds a synthetic 6.x work root in a temporary folder. It touches
no real archive.

Scenario id: `MKU-1`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.multiagent_check import map_units  # noqa: E402

ONE_UNIT_MAP = "# Distribution map\n\nunits: 1\n\nThe main session builds it.\n"


def _issue(root):
    folder = Path(root) / "solo"
    folder.mkdir(parents=True)
    body = {"schema_version": "3.0", "issue": "solo", "created": "2026-10-01",
            "status": "done", "close_reason": "completed", "delivery_approach": "regular",
            "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                           "size": "medium", "goal": "delivery", "role": "engineer",
                           "labels": []},
            "evidence": [],
            "artifacts": [{"id": "ART-DISTRIBUTION_MAP", "kind": "distribution-map",
                           "status": "approved", "depth": "lightweight",
                           "approved_by": "jed72", "approved_at": "2026-10-02T09:00:00Z"}]}
    (folder / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                         encoding="utf-8")
    (folder / "distribution-map.md").write_text(ONE_UNIT_MAP, encoding="utf-8")
    return folder


def _migrate(root, *flags):
    r = subprocess.run([sys.executable, str(CLI), "issue", "migrate", str(root), *flags],
                       cwd=root.parent, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def _map_entry(folder):
    body = yaml.safe_load((folder / "manifest.yml").read_text(encoding="utf-8"))
    return next(a for a in body["artifacts"] if a["kind"] == "distribution-map")


def test_mku_1_migrate_keeps_a_one_unit_map(tmp_path):
    root = tmp_path / "work"
    folder = _issue(root)
    assert map_units(folder) == 1
    dry = _migrate(root)
    applied = _migrate(root, "--apply", "--i-have-a-copy")
    wanted = "distribution maps to rename to distribution-map.md.v6.bak: 0"
    for out in (dry, applied):
        assert wanted in out, out
    # No project marker above the issue folder, so the documents folder is under it.
    docs = folder / "docs" / "compass" / "2026-10-01-solo"
    assert (docs / "distribution-map.md").read_text(encoding="utf-8") == ONE_UNIT_MAP
    assert not (docs / "distribution-map.md.v6.bak").exists()
    entry = _map_entry(folder)
    assert entry["status"] == "approved", entry
    assert entry.get("path"), entry
    assert map_units(folder) == 1
