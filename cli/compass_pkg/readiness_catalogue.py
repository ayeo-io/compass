# compass_pkg.readiness_catalogue - the readiness signals in force for a project
"""The `readiness` catalogue a project is measured against, and the floor it makes.

A project that has a `compass.yml` reads the catalogue through the layer chain
(`effective.resolve_live`), so a signal the project adds, sets or takes off the
floor counts. A project with no `compass.yml` reads the shipped `readiness.yml`.

The chain is read whenever `compass.yml` counts, not whenever `effective._layered`
is true. `_layered` is false in the framework's own repository, where the
effective view reads the governance files and skips the project file; reading
through it would ignore a readiness layer there without saying so. The legacy
governance views carry no readiness entry, so they are not read here either.
"""
# DEPENDENCY: standard library (os); compass_pkg.atomic_io, compass_pkg.core
# (FRAMEWORK_ROOT), compass_pkg.effective (resolve_live) and
# compass_pkg.project_settings. Not a leaf: the command and the freshness
# test use it, and the session-start hook does not.
from __future__ import annotations

import copy
import os

from compass_pkg import effective, project_settings
from compass_pkg.atomic_io import load_yaml_strict
from compass_pkg.core import FRAMEWORK_ROOT, CompassError

SHIPPED_FILE = os.path.join("governance", "presets", "default", "readiness.yml")


def shipped():
    """The readiness catalogue the default preset ships."""
    path = os.path.join(FRAMEWORK_ROOT, SHIPPED_FILE)
    try:
        document = load_yaml_strict(path)
    except (OSError, ValueError) as exc:
        raise CompassError(f"the shipped readiness catalogue cannot be read: {exc}") from exc
    return copy.deepcopy(document.get("readiness") or {})


def catalogue(root):
    """The readiness signals in force for the project at `root`, keyed by id."""
    if project_settings.compass_yml_counts(root):
        return copy.deepcopy(effective.resolve_live(root).resolved.get("readiness") or {})
    return shipped()


def floor(signals):
    """The ids of the signals the readiness floor needs, sorted: those whose
    `required_for_autonomous` is true."""
    return sorted(signal_id for signal_id, entry in signals.items()
                  if isinstance(entry, dict) and entry.get("required_for_autonomous") is True)
