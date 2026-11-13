"""Write a document's entry into an issue's `artifacts:` list, as a release before 9.0.0 did.

9.0.0 registers no document (ADR-091): `compass issue artifact set` is removed. A manifest
an older release wrote still holds the list, and the readers that read it (the stage an
issue has reached, the path of an older spec, the migration) still read it. A test that
needs such a manifest writes the entry with this helper, the way the removed verb wrote it.
"""
from __future__ import annotations

from pathlib import Path

import yaml


def entry_id(kind):
    return "ART-" + kind.upper().replace("-", "_")


def register(task_dir, kind, path, status="draft", depth="lightweight", **more):
    """Add or replace the entry of `kind` in the manifest in `task_dir`. `path` is the
    document's project-relative path. Returns the entry written."""
    manifest = Path(task_dir) / "manifest.yml"
    body = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    entries = [a for a in body.get("artifacts") or []
               if not (isinstance(a, dict) and a.get("kind") == kind)]
    entry = {"id": entry_id(kind), "kind": kind, "status": status, "depth": depth,
             "path": str(path), "reason": "registered by a release before 9.0.0", **more}
    entries.append(entry)
    body["artifacts"] = entries
    manifest.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return entry
