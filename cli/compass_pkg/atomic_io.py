# compass_pkg.atomic_io - atomic writes, a lock, strict YAML and digests
"""The configuration code's one place to write and read its files safely.

An issue's stored configuration (ADR-036) must never be half written, and a
layer file with a duplicated key must not silently keep only the last value.
This module holds what that needs:

- `atomic_write_text`: write to a temporary file in the same folder, flush
  and sync it, rename it over the target, then sync the folder;
- `locked`: an exclusive lock held while a block runs;
- `load_yaml_strict`: load YAML and refuse a duplicate key, naming its line;
- `canonical_json` and `digest`: one byte form, and one digest, for equal
  data however its keys were ordered.

It imports nothing from Compass, so every module, core included, can use it.
"""
# DEPENDENCY: standard library (contextlib, datetime, hashlib, json, os, stat, tempfile);
# the bundled PyYAML.
from __future__ import annotations

import contextlib
import datetime
import hashlib
import json
import os
import stat
import tempfile

import yaml

try:
    import fcntl
except ImportError:  # no file locks on this system
    fcntl = None


class StrictYamlError(ValueError):
    """A YAML file that does not load strictly; the message names the file
    and, where it can, the line."""


def atomic_write_text(path, text, encoding="utf-8", *, mode=None, temp_prefix=None):
    """Replace `path` with `text` in one step. A reader sees the old file or
    the new one, never part of either; a failure leaves the old file and no
    temporary file behind.

    `mode`, when given, is the permission bits of the new file whatever the
    old file or the umask had. `temp_prefix`, when given, replaces the prefix
    of the temporary file's name, which is otherwise formed from the target's
    name; the rest of the name stays unpredictable."""
    path = os.fspath(path)
    folder = os.path.dirname(os.path.abspath(path))
    if temp_prefix is None:
        temp_prefix = "." + os.path.basename(path) + "-"
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=temp_prefix)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        # mkstemp makes the file private (0600). Keep the mode of the file being
        # replaced, or give a new file the mode `open` would have given it.
        if mode is None:
            try:
                mode = stat.S_IMODE(os.stat(path).st_mode)
            except FileNotFoundError:
                mode = 0o666 & ~_umask()
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    _sync_folder(folder)


def _umask():
    old = os.umask(0)
    os.umask(old)
    return old


def _sync_folder(folder):
    """Make the rename itself durable. Not every system can open a folder
    to sync it; where it cannot, the rename stands without it."""
    try:
        fd = os.open(folder, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


@contextlib.contextmanager
def locked(lock_path):
    """Hold an exclusive lock on `lock_path` while the block runs. Where the
    system has no file locks, run the block without one."""
    if fcntl is None:
        yield
        return
    with open(lock_path, "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


class _StrictLoader(yaml.SafeLoader):
    """A safe loader that refuses a mapping holding the same key twice."""

    def construct_mapping(self, node, deep=False):
        seen = {}
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            line = key_node.start_mark.line + 1
            if key in seen:
                raise StrictYamlError(
                    f"duplicate key {key!r} at line {line}, first at line {seen[key]}")
            seen[key] = line
        return super().construct_mapping(node, deep=deep)


def load_yaml_strict(path):
    """Load `path` as YAML, refusing a duplicate key. An empty file is an
    empty mapping. Every error names the file, and the line where known."""
    path = os.fspath(path)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise StrictYamlError(f"{path}: cannot read: {exc}") from exc
    try:
        data = yaml.load(text, Loader=_StrictLoader)
    except StrictYamlError as exc:
        line = str(exc).split(" at line ", 1)[1].split(",", 1)[0]
        raise StrictYamlError(f"{path}:{line}: {exc}") from None
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"{path}:{mark.line + 1}" if mark is not None else path
        raise StrictYamlError(f"{where}: invalid YAML: {exc}") from None
    return {} if data is None else data


def _json_default(value):
    """YAML reads an unquoted `2026-10-05` as a date, so a parsed layer can
    hold one. Write it as its ISO string; anything else JSON cannot hold is
    refused by type, not silently coerced."""
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    raise TypeError(f"cannot digest a value of type {type(value).__name__}: {value!r}")


def canonical_json(obj):
    """One byte form for equal data: sorted keys, no spaces, ASCII only."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      default=_json_default)


def digest(obj):
    """`sha256:` and the hex digest of `canonical_json(obj)`."""
    return "sha256:" + hashlib.sha256(canonical_json(obj).encode("ascii")).hexdigest()
