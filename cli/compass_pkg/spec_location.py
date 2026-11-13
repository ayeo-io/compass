# compass_pkg.spec_location - where an issue's acceptance criteria are
"""The one resolver every reader of the acceptance criteria asks (ADR-091).

9.0.0 registers no document, so a new issue's spec is at its fixed path,
`docs/compass/<created>-<slug>/acceptance-criteria.md`, with no registry entry.
`spec_path` gives, in order:

1. the registered path, when the manifest registers one that is on disk;
2. otherwise the fixed path, when that file exists, whatever the issue's
   `created:` date;
3. otherwise what `core.artifact_path` gives: the flat file beside the manifest,
   which may not exist.

An archived issue keeps its registered path, so what its readers read does not
move. A registered path that leaves the project is refused, as `artifact_path`
refuses it, and the fixed path does not rescue it.
"""
# DEPENDENCY: standard library (os); compass_pkg.core.
from __future__ import annotations

import os

from compass_pkg.core import _entry_for, _registered_path, artifact_path, unregistered_document

KIND = "acceptance-criteria"
NAME = KIND + ".md"


def spec_path(task_dir):
    """The path of the issue's acceptance criteria, which may not exist."""
    entry = _entry_for(task_dir, KIND)
    if entry and entry.get("path"):
        registered, refused = _registered_path(task_dir, entry["path"])
        if refused:
            return artifact_path(task_dir, NAME)
        if os.path.isfile(registered):
            return registered
    return unregistered_document(task_dir, NAME) or artifact_path(task_dir, NAME)
