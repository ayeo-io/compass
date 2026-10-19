# compass_pkg.policy_migrate_undo - `compass policy migrate --undo`
"""Put a migrated project back as it was before `compass policy migrate --apply`.

`plan(root)` reads the migration marker and checks every digest before
anything is written, and raises `CompassError` for each refusal. `apply`
then runs the steps `plan` returned, in order: restore the old settings
file and any deleted governance file from the legacy folder, remove
`compass.yml`, remove the state file when the migration made it, and
remove the marker last. The marker is the proof that an undo is still owed,
so a rerun after any stop finishes the job.

The undo never discards an edit. A file that changed since the migration is
refused by name, and there is no override.
"""
# DEPENDENCY: standard library (dataclasses, datetime, json, os); the bundled PyYAML;
# compass_pkg.atomic_io, core and policy_migrate.
from __future__ import annotations

import datetime
import json
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


NO_MARKER = ("There is no .compass/migration.yml, so there is nothing to undo. "
             "Nothing was changed.")
MANUAL = ("migration.yml has no digest of compass.yml, so the undo cannot tell whether you "
          "edited it. Nothing was changed. To go back by hand, copy .compass/legacy/config.yml "
          "to .compass/config.yml, then remove compass.yml, .compass/migration.yml and, when "
          "created_state in migration.yml is true, .compass/state.yml.")
BY_HAND = "Keep the file, or go back by hand with the steps in docs/policy-migrate.md."


def _digests(marker, created):
    """The source digests and the written digests, or a refusal with the manual steps."""
    sources, written = marker.get("sources"), marker.get("written")
    if not isinstance(sources, dict) or not isinstance(written, dict):
        raise CompassError(MANUAL)
    needed = [pm.COMPASS_YML] + ([pm.STATE_YML] if created else [])
    listed = [rel for rel in SOURCES if rel in sources]
    if not listed or not all(isinstance(written.get(rel), str) for rel in needed) \
            or not all(isinstance(sources[rel], str) for rel in listed):
        raise CompassError(MANUAL)
    return sources, written


def _changed(root, rel, digest):
    """Whether the file is there and is not the one the migration recorded."""
    return _present(root, rel) and pm.file_digest(_path(root, rel)) != digest


def _check(root, marker, listed, digests, written, created):
    """Refuse at the first thing that would make the undo lose work, in a fixed order."""
    for rel in listed:
        legacy = _legacy(rel)
        if not _present(root, legacy) or pm.file_digest(_path(root, legacy)) != digests[rel]:
            raise CompassError(
                f"{legacy} is missing or is not the copy the migration made, so the undo "
                f"cannot restore {rel} exactly. Nothing was changed. "
                "Go back by hand with the steps in docs/policy-migrate.md.")
    checked = [(pm.COMPASS_YML, written[pm.COMPASS_YML])]
    if created:
        checked.append((pm.STATE_YML, written[pm.STATE_YML]))
    checked += [(rel, digests[rel]) for rel in listed]
    for rel, digest in checked:
        if _changed(root, rel, digest):
            raise CompassError(f"{rel} changed since the migration, so the undo would discard "
                               f"your edits. Nothing was changed. {BY_HAND}")
    count = _signed_since(root, _migrated_at(root, marker))
    if count:
        many = count != 1
        raise CompassError(
            f"{count} signed record{'s exist' if many else ' exists'} since the migration. "
            f"The undo would leave {'them' if many else 'it'} without the settings that judged "
            f"{'them' if many else 'it'}. Nothing was changed. "
            "Go back by hand with the steps in docs/policy-migrate.md.")


def _when(value):
    """A time as an aware UTC-based datetime, or None when it cannot be read."""
    text = str(value)
    try:
        when = datetime.datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=datetime.timezone.utc)


def _migrated_at(root, marker):
    """When the migration ran; the marker's own modification time when it says nothing readable."""
    stamp = _when(marker["migrated_at"]) if "migrated_at" in marker else None
    if stamp is None:
        mtime = os.stat(_path(root, pm.MIGRATION_YML)).st_mtime
        stamp = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc)
    return stamp


def _evidence_files(root):
    """The regular `.json` files in each issue's evidence folder, no links."""
    work = _path(root, ".compass/work")
    if not os.path.isdir(work):
        return
    for issue in sorted(os.scandir(work), key=lambda entry: entry.name):
        folder = os.path.join(issue.path, "evidence")
        if issue.is_symlink() or not issue.is_dir() or os.path.islink(folder):
            continue
        if os.path.isdir(folder):
            for entry in sorted(os.scandir(folder), key=lambda item: item.name):
                if entry.name.endswith(".json") and entry.is_file(follow_symlinks=False):
                    yield entry.path


def _signed_since(root, since):
    """How many signed records are at or after `since`, or have no readable time.

    A record is signed when it has a `content_digest`. Nothing else in it is
    read, and nothing of it is printed.
    """
    count = 0
    for path in _evidence_files(root):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                record = json.load(fh)
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict) or not record.get("content_digest"):
            continue
        stamp = _when(record.get("timestamp"))
        count += stamp is None or stamp >= since
    return count


def plan(root) -> UndoPlan:
    """Read the marker and the project, check every digest, return the steps.

    Writes nothing. Raises `CompassError` for every refusal.
    """
    marker = _marker(root)
    if marker is None:
        raise CompassError(NO_MARKER)
    created = marker.get("created_state") is True
    digests, written = _digests(marker, created)
    listed = [rel for rel in SOURCES if rel in digests]
    _check(root, marker, listed, digests, written, created)
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
    """Copy the legacy copy of `rel` back to `rel`, byte for byte."""
    with open(_path(root, _legacy(rel)), "rb") as fh:
        text = fh.read().decode("utf-8")
    # newline="" writes the line endings as they are, so a CRLF file comes back unchanged.
    atomic_write_text(_path(root, rel), text, newline="")


def remove_compass_yml(root) -> None:
    """Remove `compass.yml`."""
    os.remove(_path(root, pm.COMPASS_YML))


def remove_state(root) -> None:
    """Remove the state file the migration made."""
    os.remove(_path(root, pm.STATE_YML))


def remove_marker(root) -> None:
    """Remove the migration marker. It is always the last step."""
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
