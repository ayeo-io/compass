# compass_pkg.justifications - the reason a person gave for each assessed value
"""The manifest's top-level `justifications` key holds one line per assessed
dimension, beside `assessment` and never inside it (ADR-055).

`compass approach evaluate --write --justify DIM=TEXT` merges the flags over
the stored key. It demands a non-blank justification for each dimension of type
`enum` or `ordered-enum` whose value is new or changed since the assessment the
last write evaluated (`evaluated_assessment`). A value that is unchanged keeps
its recorded justification, or none on an issue that predates the key, so a
repeated write records no new judgement and owes no new reason.
"""
# DEPENDENCY: standard library; compass_pkg.core (FRAMEWORK_ROOT, load_yaml, CompassError).
# It is a leaf: it imports no command module.
from __future__ import annotations

import os

from compass_pkg.core import FRAMEWORK_ROOT, CompassError, load_yaml

#: The dimension types a justification is owed for. A `set` (labels) needs none.
JUSTIFIED_TYPES = ("enum", "ordered-enum")


def parse(pairs):
    """`{dimension: text}` from the `DIM=TEXT` flags. The text can be blank: the
    demand check names the dimension."""
    found = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise CompassError(f"--justify expects DIM=TEXT, got: {pair}")
        name, text = pair.split("=", 1)
        found[name.strip()] = text.strip()
    return found


def _dimensions(view):
    config = getattr(view, "config", None) if view is not None else None
    declared = config.get("dimensions") if isinstance(config, dict) else None
    if not isinstance(declared, dict):
        path = os.path.join(FRAMEWORK_ROOT, "governance", "presets", "default", "dimensions.yml")
        declared = (load_yaml(path) or {}).get("dimensions") or {}
    return declared


def justified_dimensions(view):
    """The dimension names that need a justification, in their declared order."""
    return [name for name, body in _dimensions(view).items()
            if isinstance(body, dict) and body.get("type") in JUSTIFIED_TYPES]


def merge(task, readings, flags, view):
    """`(merged, missing)`: the justifications the write will record, and the
    dimensions that are owed one and have none. `flags` is the output of `parse`."""
    known = justified_dimensions(view)
    unknown = [name for name in flags if name not in known]
    if unknown:
        raise CompassError("--justify names %s, which is not a dimension that needs one (%s)"
                           % (", ".join(unknown), ", ".join(known)))
    stored = task.get("justifications") if isinstance(task.get("justifications"), dict) else {}
    evaluated = task.get("evaluated_assessment")
    evaluated = evaluated if isinstance(evaluated, dict) else {}
    merged = dict(stored)
    merged.update({name: text for name, text in flags.items()
                   if text and readings.get(name) not in (None, "")})
    missing = []
    for name in known:
        value = readings.get(name)
        if value in (None, ""):
            continue
        if name in flags:
            owed = not flags[name]                  # a flag must carry text
        elif name in evaluated:
            owed = evaluated[name] != value         # a changed value needs a new line
        else:
            owed = not str(stored.get(name) or "").strip()      # a new value needs a line
        if owed:
            missing.append(name)
    return merged, missing


def refusal(missing):
    return ("compass approach evaluate: --write needs a justification for %s, whose value is "
            "new or changed. Add --justify %s." % (
                ", ".join(missing), " ".join("%s=<why>" % name for name in missing)))
