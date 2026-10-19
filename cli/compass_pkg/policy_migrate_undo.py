# compass_pkg.policy_migrate_undo - `compass policy migrate --undo`
"""Put a migrated project back as it was before `compass policy migrate --apply`.

`plan(root)` reads the migration marker and checks every digest before
anything is written, and raises `CompassError` for each refusal. `apply`
then runs the steps `plan` returned, in order: restore the old settings
file and any deleted governance file from `.compass/legacy`, remove
`compass.yml`, remove `.compass/state.yml` when the migration made it, and
remove the marker last. The marker is the proof that an undo is still owed,
so a rerun after any stop finishes the job.

This is the interface skeleton: every function raises `NotImplementedError`.
"""
# DEPENDENCY: standard library (dataclasses); compass_pkg.policy_migrate.
from __future__ import annotations

from dataclasses import dataclass, field

from compass_pkg import policy_migrate

# The only paths the undo restores. The marker's own `sources` keys are never
# used as paths, so a marker that names a file outside the project changes
# nothing outside it.
SOURCES = policy_migrate.GOVERNANCE_FILES + (policy_migrate.OLD_CONFIG,)


@dataclass
class UndoPlan:
    """The steps of one undo, as data."""

    result: str = "ready"                        # "ready", then "undone" after apply
    sources: list = field(default_factory=list)  # [{"path", "digest"}] in SOURCES order
    files: list = field(default_factory=list)    # [{"action", "path", "to"}] in apply order


def plan(root) -> UndoPlan:
    """Read the marker and the project, check every digest, return the steps.

    Writes nothing. Raises `CompassError` for every refusal.
    """
    raise NotImplementedError


def apply(root, made) -> None:
    """Run the restore and remove steps in `made.files`; set `made.result` to "undone"."""
    raise NotImplementedError


def restore_source(root, rel) -> None:
    """Copy `.compass/legacy/<name>` back to the source path `rel`, byte for byte."""
    raise NotImplementedError


def remove_compass_yml(root) -> None:
    """Remove `compass.yml`."""
    raise NotImplementedError


def remove_state(root) -> None:
    """Remove `.compass/state.yml`."""
    raise NotImplementedError


def remove_marker(root) -> None:
    """Remove `.compass/migration.yml`. It is always the last step."""
    raise NotImplementedError


def report_json(made) -> dict:
    """The report as a dict, keys in order: schema, mode, result, sources, files."""
    raise NotImplementedError


def report_text(made) -> list[str]:
    """The report as lines of text."""
    raise NotImplementedError
