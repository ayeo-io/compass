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
# DEPENDENCY: standard library (copy, os, sys), compass_pkg.atomic_io,
# compass_pkg.catalogue_spec and the bundled PyYAML; imports nothing else from
# Compass.
from __future__ import annotations

import copy
import os
import sys

import yaml

from compass_pkg.atomic_io import load_yaml_strict
from compass_pkg.catalogue_spec import SETTINGS_KEYS


class CompassError(Exception):
    """A user-facing error: printed without a traceback, exits non-zero.

    Defined here, and imported by `core`, because `core` imports this module
    and this module must raise the error every caller already catches
    without importing `core` back."""


class SettingsConflict(CompassError):
    """Both settings files exist and the old one still holds settings keys.

    The wording lives in `CONFLICT_WHY` and `CONFLICT_FIX`. The CLI prints
    them after `settings-conflict: `, and the registry's refusal for the hook
    is built from the same two strings, so the two never differ."""

    def __init__(self, keys):
        self.keys = keys
        # Five keys at most, so a long list cannot push the fix off the screen.
        self.shown = ", ".join(keys[:5])
        if len(keys) > 5:
            self.shown += f" and {len(keys) - 5} more"
        self.body = conflict_body(self.shown)
        super().__init__("settings-conflict: " + self.body)


#: What the refusal says. It names no command that does not exist yet: a
#: refusal must not send anyone to a command that fails.
CONFLICT_WHY = (".compass/config.yml sets {keys}, but compass.yml is read, so "
                "those keys guard nothing.")
CONFLICT_FIX = ("Move them into compass.yml (write mode as adoption) and "
                "delete them from .compass/config.yml, then retry.")


def conflict_body(shown):
    """The one sentence pair, for the keys as text (`a, b and 2 more`)."""
    return CONFLICT_WHY.format(keys=shown) + " " + CONFLICT_FIX


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


#: `compass.yml` parsed once while the file is unchanged, so a call that asks
#: whether it is recognised and then reads it parses it once. Keyed by path,
#: modification time and size.
_PARSED = {}


def _compass_yml(path):
    """`(data, None)` for `compass.yml`, or `(None, message)` when it cannot
    be read or is not a mapping."""
    try:
        stat = os.stat(path)
    except OSError:
        return None, f"cannot read {path}"
    key = (path, stat.st_mtime_ns, stat.st_size)
    if key not in _PARSED:
        try:
            _PARSED[key] = (_load(path, strict=True), None)
        except CompassError as exc:
            _PARSED[key] = (None, str(exc))
    return _PARSED[key]


def _recognised(path):
    """Whether `compass.yml` is Compass's file: it has a top-level `schema:`.

    Any other product's file of that name has no reason to carry the key, so
    without it the old file keeps its settings. A file that cannot be read
    counts as recognised so that `settings` reads it and the error names it;
    the old file must not hide a broken `compass.yml`."""
    data, error = _compass_yml(path)
    return error is not None or "schema" in data


def _compass_yml_counts(project_root):
    """Whether `compass.yml` is the file to read: it is the only settings
    file, or it is recognised."""
    path = os.path.join(project_root, COMPASS_YML)
    return os.path.isfile(path) and (
        not os.path.isfile(os.path.join(project_root, OLD_CONFIG))
        or _recognised(path))


def lenient(project_root):
    """`settings`, or `{}` when a file cannot be read, for a caller whose
    broken-file behaviour is to carry on with defaults. A conflict still
    raises: defaults would drop the very settings it names."""
    try:
        return settings(project_root)
    except SettingsConflict:
        raise
    except CompassError:
        return {}


def settings_source(project_root):
    """The path of the file `settings` reads, or None when the project has
    neither file. For error and advice text that names the file read."""
    if _compass_yml_counts(project_root):
        return os.path.join(project_root, COMPASS_YML)
    old = os.path.join(project_root, OLD_CONFIG)
    return old if os.path.isfile(old) else None


#: Keys only the old file is read for. `mode` is its name for `adoption`. A
#: union with `SETTINGS_KEYS`, so listing one there later counts it once.
OLD_FILE_EXTRA_KEYS = ("mode",)


def _old_settings_keys(project_root):
    """The keys the old file holds that something reads, in file order.

    That is the catalogue's settings keys without `adoption`, which the old
    file never read, plus `OLD_FILE_EXTRA_KEYS`, plus the script settings found
    outside `multiagent:` and `project:`."""
    try:
        old = _load(os.path.join(project_root, OLD_CONFIG), strict=False)
    except CompassError as exc:
        # The hook names the file that failed, and here it is not the one
        # `settings_source` reports.
        exc.file = OLD_CONFIG
        raise
    counted = (set(SETTINGS_KEYS) | set(OLD_FILE_EXTRA_KEYS)) - {"adoption"}
    keys = []
    for key, value in old.items():
        if key in counted:
            keys.append(key)
        # The scripts find these at any depth, so one outside the two headings
        # that already count is a setting too. The same lookup the scripts use.
        if key not in ("multiagent", "project"):
            keys += [name for name in SCRIPT_SETTINGS
                     if name not in keys and _first_text({key: value}, name)]
    return keys


def settings_conflict(project_root):
    """The settings keys the old file would lose to `compass.yml`, or `[]`.

    Both files must exist. A key left in the old file would guard nothing
    once `compass.yml` is read, and a guard that stops without a word is
    the failure the safety contract rules out."""
    if not os.path.isfile(os.path.join(project_root, OLD_CONFIG)) \
            or not _compass_yml_counts(project_root):
        return []
    return _old_settings_keys(project_root)


#: Roots already warned about, so a command that reads settings many times
#: warns once.
WARNED = set()


def _warn_ignored(project_root):
    if project_root in WARNED:
        return
    WARNED.add(project_root)
    print("warning: .compass/config.yml and compass.yml both exist and "
          "compass.yml has no `schema:`, so the old file is read and "
          "compass.yml is not. Add `schema:` to compass.yml if it is "
          "Compass's file.", file=sys.stderr)


def settings(project_root):
    """The project's settings keys as a dict, `{}` when it has no file."""
    path = settings_source(project_root)
    if path is None:
        return {}
    # `compass.yml` is read first so that a file that cannot be read is named
    # even when the old file also holds settings.
    if os.path.basename(path) == COMPASS_YML:
        data, error = _compass_yml(path)
        if error is not None:
            raise CompassError(error)
        data = copy.deepcopy(data)
    else:
        data = _load(path, strict=False)
    keys = settings_conflict(project_root)
    if keys:
        raise SettingsConflict(keys)
    if os.path.basename(path) != COMPASS_YML \
            and os.path.isfile(os.path.join(project_root, COMPASS_YML)):
        _warn_ignored(project_root)
    if os.path.basename(path) != COMPASS_YML:
        # Only `mode` is the adoption setting in the old file, as at 5.6.0.
        # An `adoption` key there was never read, so it stays unread.
        data = {k: v for k, v in data.items() if k != "adoption"}
        if "mode" in data:
            data["adoption"] = data["mode"]
    return data


# Where `compass.yml` keeps each setting the shell scripts read, by the key the
# scripts ask for. `compass.yml` is read only at these paths, so a key of the
# same name in a check's parameters or elsewhere is never taken for a setting.
SCRIPT_SETTINGS = {
    "worktree_root": ("multiagent", "worktree_root"),
    "max_worktrees": ("multiagent", "max_worktrees"),
    "test_command": ("project", "test_command"),
}


_MISSING = object()


def _text(value):
    """A setting as the scripts see it: "" unless it is a scalar."""
    if value is _MISSING or value is None or isinstance(value, (dict, list)):
        return ""
    return str(value).lower() if isinstance(value, bool) else str(value)


def _first_text(data, key):
    """The first `key:` at any depth of `data`, in document order, as text.
    This is the old file's lookup for the scripts, and the conflict check uses
    it so the two cannot disagree about where a key is found."""
    seen = set()

    def first(node):
        # An anchor can make a mapping contain itself, so a node is visited once.
        if isinstance(node, dict) and id(node) not in seen:
            seen.add(id(node))
            if key in node:
                return node[key]
            for child in node.values():
                found = first(child)
                if found is not _MISSING:
                    return found
        return _MISSING

    return _text(first(data))


def scalar(project_root, key):
    """One setting the shell scripts read, as text.

    It is "" when the setting is absent, empty or holds a mapping or a list. A
    file that cannot be read raises `CompassError`; the script decides what
    that means.

    - In `compass.yml` the setting is read at its documented path in
      `SCRIPT_SETTINGS`, and a key with no documented path is "".
    - In `.compass/config.yml` the first `key:` at any depth, in document
      order, is read. The scripts once matched an indented or top-level line
      with `grep`, so a key under `multiagent:`, under an older heading and at
      the top level all gave the same answer, and old projects rely on it.
    """
    def documented(node):
        for step in SCRIPT_SETTINGS.get(key, ()):
            if not isinstance(node, dict) or step not in node:
                return _MISSING
            node = node[step]
        return node if key in SCRIPT_SETTINGS else _MISSING

    data = settings(project_root)
    if settings_file(project_root) == COMPASS_YML:
        return _text(documented(data))
    return _first_text(data, key)


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
