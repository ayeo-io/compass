# compass_pkg.json_shape - check a JSON document against a documented shape
"""Check a document against the shape its `--json` output documents.

The classifier (`classify.JSON_SHAPE`) and `compass policy diff`
(`replay.DIFF_JSON_SHAPE`) describe their output the same way, so one
function checks both. A string names a JSON type; `("one of", ...)` is a
closed set of strings; `("or null", shape)` is a shape or null; a dictionary
is an object with exactly these keys in this order; a one-item list is a list
of that shape; `"any"` is any JSON value.
"""
# DEPENDENCY: none. compass_pkg.classify and compass_pkg.replay import
# `shape_errors`.
from __future__ import annotations

_TYPES = {"string": str, "boolean": bool, "object": dict}


def shape_errors(value, shape, path, errors):
    """Append to `errors` one line for each place `value` differs from `shape`;
    `path` names `value` in each line."""
    if shape == "any":
        return
    if isinstance(shape, tuple) and shape[0] == "or null":
        if value is not None:
            shape_errors(value, shape[1], path, errors)
    elif isinstance(shape, tuple):
        if value not in shape[1]:
            errors.append(f"{path}: {value!r} is not one of {', '.join(shape[1])}")
    elif isinstance(shape, dict):
        if not isinstance(value, dict):
            errors.append(f"{path}: expected an object")
        elif list(value) != list(shape):
            errors.append(f"{path}: keys are {list(value)}, expected {list(shape)}")
        else:
            for key, sub in shape.items():
                shape_errors(value[key], sub, f"{path}.{key}", errors)
    elif isinstance(shape, list):
        if not isinstance(value, list):
            errors.append(f"{path}: expected a list")
        else:
            for i, item in enumerate(value):
                shape_errors(item, shape[0], f"{path}[{i}]", errors)
    elif shape == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"{path}: expected an integer")
    elif not isinstance(value, _TYPES[shape]):
        errors.append(f"{path}: expected {shape}")
