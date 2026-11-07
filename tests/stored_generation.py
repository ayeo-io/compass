"""Store a generation whose configuration holds more than the check set does.

Since 9.0.0 `compass.yml` holds settings only (ADR-094): a `checks:`, `gates:`
or `stages:` key is a removed setting, read as if absent. A check, gate or
stage list the check set does not hold now reaches an issue in one way only:
the issue's stored generation, which an 8.x project layer could have filled.
A test that needs such a configuration commits it here, as the 8.x resolver
would have, and then runs the real commands, which read the stored generation.
"""
from __future__ import annotations

import copy
import dataclasses
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))


def commit(root, task_dir, mutate, slug=None, in_place=False):
    """Commit the issue's next generation from the project's live configuration
    changed by `mutate`, a function of the resolved mapping. The manifest's
    `policy:` block is dropped, as a generation stored before 9.0.0 has none.
    With `in_place`, the generation in force is replaced and keeps its number,
    for a test that pins output naming it. Returns the generation number."""
    from compass_pkg import effective, generation
    task_dir = Path(task_dir)
    slug = slug or task_dir.name
    path = task_dir / "manifest.yml"
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    manifest.pop("policy", None)
    held = manifest.get("generation")
    if in_place and held:
        shutil.rmtree(task_dir / "generations" / str(held))
        manifest["generation"] = held - 1
        if not manifest["generation"]:
            del manifest["generation"]
        path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    resolution = effective.resolve_live(str(root), manifest, slug, str(task_dir))
    resolved = copy.deepcopy(resolution.resolved)
    mutate(resolved)
    done = generation.commit(str(task_dir), dataclasses.replace(resolution, resolved=resolved),
                             manifest, force=True)
    return done.number
