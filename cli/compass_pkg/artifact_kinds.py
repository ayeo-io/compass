# compass_pkg.artifact_kinds - what the catalogue says about each kind of document
"""Read a document kind's catalogue entry, with the gaps of an old one filled.

The artifacts catalogue describes each kind of document: the stage that owns
it, the role that writes it, who reads it, the name the industry uses for it
and its headings per depth. Every reader that needs one of those facts asks
here, so a stored generation that predates a field is read the same way by
all of them.

A generation stores the configuration as it was resolved. One stored before
the descriptive fields existed holds entries with a `file` and sometimes a
`stage`, and nothing else. `entry` returns such an entry with each absent
descriptive field taken from the shipped default, for a kind the shipped
default declares. A project's own kind is returned as stored, because the
framework knows nothing about it. `required_when` and `every_approach` are
never filled: they decide what an issue owes, and a stored generation keeps
the obligations it was stored with.
"""
# DEPENDENCY: standard library; compass_pkg.core (FRAMEWORK_ROOT, load_yaml).
# It is a leaf: it imports no command module, so every reader can import it.
from __future__ import annotations

import copy
import os

from compass_pkg.core import FRAMEWORK_ROOT, CompassError, load_yaml

#: The fields read from the shipped default when a stored entry lacks them.
FILLED_FIELDS = ("stage", "owner", "audience", "stands_for", "sections", "depends_on")

_SHIPPED = {}


def shipped():
    """The shipped default's artifacts catalogue, or {} when it cannot be read.
    Read once per process."""
    if "artifacts" not in _SHIPPED:
        path = os.path.join(FRAMEWORK_ROOT, "governance", "presets", "default",
                            "artifacts.yml")
        try:
            body = (load_yaml(path) or {}).get("artifacts")
        except (CompassError, OSError):
            body = None
        _SHIPPED["artifacts"] = body if isinstance(body, dict) else {}
    return _SHIPPED["artifacts"]


def entry(view, kind):
    """The catalogue entry of `kind` in `view`'s configuration, or None when
    the catalogue does not declare it. A shipped kind's absent descriptive
    fields are filled from the shipped default. The result is a copy."""
    config = getattr(view, "config", None) if view is not None else None
    catalogue = config.get("artifacts") if isinstance(config, dict) else None
    stored = catalogue.get(kind) if isinstance(catalogue, dict) else None
    if not isinstance(stored, dict):
        return None
    found = copy.deepcopy(stored)
    default = shipped().get(kind)
    if isinstance(default, dict):
        for field in FILLED_FIELDS:
            if field not in found and field in default:
                found[field] = copy.deepcopy(default[field])
    return found
