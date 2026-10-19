# compass_pkg.policy_migrate_undo - `compass policy migrate --undo`
"""Put a migrated project back as it was before `compass policy migrate --apply`.

`plan(root)` reads the migration marker and checks every digest before
anything is written, and raises `CompassError` for each refusal. `apply`
then runs the steps `plan` returned, in order: restore the old settings
file and any deleted governance file from `.compass/legacy`, remove
`compass.yml`, remove `.compass/state.yml` when the migration made it, and
remove the marker last. The marker is the proof that an undo is still owed,
so a rerun after any stop finishes the job.

The undo never discards an edit. A file that changed since the migration is
refused by name, and there is no override.
"""
# DEPENDENCY: standard library (dataclasses, os); the bundled PyYAML;
# compass_pkg.atomic_io, core and policy_migrate.
from __future__ import annotations

import os
from dataclasses import dataclass, field

import yaml

from compass_pkg import policy_migrate as pm
from compass_pkg.atomic_io import atomic_write_text
from compass_pkg.core import CompassError

# The only paths the undo restores. The marker's own `sources` keys are never
# used as paths, so a marker that names a file outside the project changes
# nothing outside it.
SOURCES = pm.GOVERNANCE_FILES + (pm.OLD_CONFIG,)
# The old settings file comes back first, so no stop leaves the project with
# neither settings file.
RESTORE_ORDER = (pm.OLD_CONFIG,) + pm.GOVERNANCE_FILES


@dataclass
class UndoPlan:
    """The steps of one undo, as data."""

    result: str = "ready"                        # "ready", then "undone" after apply
    sources: list = field(default_factory=list)  # [{"path", "digest"}] in SOURCES order
    files: list = field(default_factory=list)    # [{"action", "path", "to"}] in apply order


def _path(root, rel):
    return os.path.join(root, *rel.split("/"))


def _present(root, rel):
    return os.path.isfile(_path(root, rel))


def _legacy(rel):
    return f"{pm.LEGACY_DIR}/{rel.rsplit('/', 1)[-1]}"


def _step(action, rel):
    return {"action": action, "path": rel, "to": None}


def _marker(root):
    """The parsed marker; a missing, unreadable or non-mapping file is no marker."""
    if not _present(root, pm.MIGRATION_YML):
        return None
    try:
        with open(_path(root, pm.MIGRATION_YML), "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def plan(root) -> UndoPlan:
    """Read the marker and the project, check every digest, return the steps.

    Writes nothing. Raises `CompassError` for every refusal.
    """
    marker = _marker(root)
    created = marker.get("created_state") is True
    digests = marker.get("sources")
    listed = [rel for rel in SOURCES if rel in digests]
    made = UndoPlan(sources=[{"path": rel, "digest": digests[rel]} for rel in listed])
    files = [_step("restore", rel) for rel in RESTORE_ORDER
             if rel in listed and not _present(root, rel)]
    if _present(root, pm.COMPASS_YML):
        files.append(_step("remove", pm.COMPASS_YML))
    if created and _present(root, pm.STATE_YML):
        files.append(_step("remove", pm.STATE_YML))
    files.append(_step("remove", pm.MIGRATION_YML))
    files += [_step("keep", rel) for rel in listed if _present(root, rel)]
    if not created and _present(root, pm.STATE_YML):
        files.append(_step("keep", pm.STATE_YML))
    made.files = files
    return made


def apply(root, made) -> None:
    """Run the restore and remove steps in `made.files`; set `made.result` to "undone".

    Checks nothing: `plan` checked everything. Each writer is looked up by
    name at call time, so a test can replace one.
    """
    removers = {pm.COMPASS_YML: remove_compass_yml, pm.STATE_YML: remove_state,
                pm.MIGRATION_YML: remove_marker}
    for step in made.files:
        if step["action"] == "restore":
            restore_source(root, step["path"])
        elif step["action"] == "remove":
            removers[step["path"]](root)
    made.result = "undone"


def restore_source(root, rel) -> None:
    """Copy `.compass/legacy/<name>` back to the source path `rel`, byte for byte."""
    with open(_path(root, _legacy(rel)), "rb") as fh:
        text = fh.read().decode("utf-8")
    # newline="" writes the line endings as they are, so a CRLF file comes back unchanged.
    atomic_write_text(_path(root, rel), text, newline="")


def remove_compass_yml(root) -> None:
    """Remove `compass.yml`."""
    os.remove(_path(root, pm.COMPASS_YML))


def remove_state(root) -> None:
    """Remove `.compass/state.yml`."""
    os.remove(_path(root, pm.STATE_YML))


def remove_marker(root) -> None:
    """Remove `.compass/migration.yml`. It is always the last step."""
    os.remove(_path(root, pm.MIGRATION_YML))


def report_json(made) -> dict:
    """The report as a dict, keys in order: schema, mode, result, sources, files."""
    return {"schema": 1, "mode": "undo", "result": made.result,
            "sources": made.sources, "files": made.files}


def report_text(made) -> list[str]:
    """The report as lines of text."""
    ready = made.result == "ready"
    lines = ["compass policy migrate --undo: "
             + ("dry run - nothing was written" if ready else "undone"), "  files:"]
    lines += [f"    {step['action']:<8}{step['path']}" for step in made.files]
    lines.append("  .compass/legacy is kept.")
    if ready:
        lines.append("Run with --apply to make these changes.")
    return lines
