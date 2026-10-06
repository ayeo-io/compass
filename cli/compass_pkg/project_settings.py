# compass_pkg.project_settings - the one reader of a project's settings
"""Where a project's settings and CLI-written state are read from (ADR-043).

Two readers, both given the project root directory. Neither walks upward
and neither imports `core`, so `core` can use them.

- `settings(project_root)`: the settings keys. `compass.yml` at the project
  root when it exists, loaded strictly so a duplicated key is refused;
  otherwise `.compass/config.yml`, loaded as it always was. The adoption
  setting is `adoption` in `compass.yml` and `mode` in the old file; the
  returned mapping holds it under `adoption` either way.
- `state(project_root)`: the values the CLI writes, `initialised` and
  `records_signed_since`. The state file in `.compass/` when it exists, otherwise
  `.compass/config.yml`, where a project created before ADR-043 keeps them.

A missing file is an empty mapping. A file that cannot be read, or does not
hold a mapping, raises `CompassError` naming it. Each caller decides what
that means, so a broken file behaves in each place exactly as it did before
there was one reader.
"""
# DEPENDENCY: standard library (os), compass_pkg.atomic_io and the bundled
# PyYAML; imports nothing else from Compass.
from __future__ import annotations

import os

import yaml

from compass_pkg.atomic_io import load_yaml_strict



class CompassError(Exception):
    """A user-facing error: printed without a traceback, exits non-zero.

    Defined here, and imported by `core`, because `core` imports this module
    and this module must raise the error every caller already catches
    without importing `core` back."""


COMPASS_YML = "compass.yml"
OLD_CONFIG = os.path.join(".compass", "config.yml")
STATE_YML = os.path.join(".compass", "state.yml")


def _load(path, strict):
    """The mapping in `path`; empty when the file is empty."""
    try:
        if strict:
            data = load_yaml_strict(path)
        else:
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise CompassError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CompassError(f"{path}: expected a mapping of settings")
    return data


def settings_source(project_root):
    """The path of the file `settings` reads, or None when the project has
    neither file. For error and advice text that names the file read."""
    for rel in (COMPASS_YML, OLD_CONFIG):
        path = os.path.join(project_root, rel)
        if os.path.isfile(path):
            return path
    return None


def settings(project_root):
    """The project's settings keys as a dict, `{}` when it has no file."""
    path = settings_source(project_root)
    if path is None:
        return {}
    data = _load(path, strict=os.path.basename(path) == COMPASS_YML)
    if os.path.basename(path) != COMPASS_YML:
        # Only `mode` is the adoption setting in the old file, as at 5.6.0.
        # An `adoption` key there was never read, so it stays unread.
        data = {k: v for k, v in data.items() if k != "adoption"}
        if "mode" in data:
            data["adoption"] = data["mode"]
    return data


def settings_file(project_root):
    """The file name to show a person: the one `settings` reads, or
    `compass.yml` when the project has neither, because that is where a
    setting goes now."""
    path = settings_source(project_root)
    if path is None or os.path.basename(path) == COMPASS_YML:
        return COMPASS_YML
    return OLD_CONFIG


def settings_key(project_root, key):
    """`key` as the file `settings_file` names calls it: the adoption setting
    is `adoption` in `compass.yml` and `mode` in the old file."""
    if key == "adoption" and settings_file(project_root) == OLD_CONFIG:
        return "mode"
    return key


def named(project_root, key, value=None):
    """A setting as advice text shows it: `key: value` (or `key:`) in the file
    read, as in "`mode: enforced` in .compass/config.yml"."""
    shown = settings_key(project_root, key) + ":" + (f" {value}" if value else "")
    return f"`{shown}` in {settings_file(project_root)}"


def state_source(project_root):
    """The path of the file `state` reads, or None when there is none."""
    for rel in (STATE_YML, OLD_CONFIG):
        path = os.path.join(project_root, rel)
        if os.path.exists(path):
            return path
    return None


def state(project_root):
    """`initialised` and `records_signed_since` as a dict, `{}` when neither
    file exists. A state file that exists is the whole answer."""
    path = state_source(project_root)
    if path is None:
        return {}
    data = _load(path, strict=False)
    return {k: data[k] for k in ("initialised", "records_signed_since")
            if k in data}
