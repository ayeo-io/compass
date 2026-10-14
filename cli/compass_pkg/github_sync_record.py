# compass_pkg.github_sync_record - the one writer of an issue's github-sync.yml
"""What the last GitHub sync of an issue did, kept in `github-sync.yml` in the
issue's work folder.

The file has two sections, one per write:

- `labels`: `at`, `state` (the labels Compass wanted) and `error`;
- `page`: `at`, `digest` (of the comment text as posted), `comment_id`,
  `body` (`set` when Compass wrote the issue body, `kept` when a person's body
  was left alone, absent until it is decided) and `error`.

Each write changes only its own section and keeps the other, so a label
result never erases a page result. Nothing taken from GitHub is stored except
the comment id. A record written by 6.x, with `at`, `state` and `error` at the
top level, reads as the `labels` section.
"""
# DEPENDENCY: compass_pkg.atomic_io, compass_pkg.core (now_iso), yaml. Imported by
# github_labels and github_page; it imports neither.
from __future__ import annotations

import os

import yaml

from compass_pkg.atomic_io import atomic_write_text
from compass_pkg.core import now_iso

FILE = "github-sync.yml"
PARTS = ("labels", "page")
#: The top-level keys of a 6.x record, which held the label result only.
_FLAT = ("at", "state", "error")


def path_of(task_dir):
    return os.path.join(task_dir, FILE)


def read(task_dir):
    """`{"labels": {...}, "page": {...}}`; both empty when there is no readable record."""
    try:
        with open(path_of(task_dir), "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError):
        data = None
    if not isinstance(data, dict):
        return {part: {} for part in PARTS}
    if not any(part in data for part in PARTS):
        return {"labels": {k: data[k] for k in _FLAT if k in data}, "page": {}}
    return {part: dict(data.get(part)) if isinstance(data.get(part), dict) else {}
            for part in PARTS}


def update(task_dir, part, **fields):
    """Merge `fields` into one section, stamp its `at`, and keep the other section."""
    if part not in PARTS:
        raise ValueError(f"unknown section {part!r}")
    data = read(task_dir)
    section = {k: v for k, v in data[part].items() if k != "at"}
    section.update(fields)
    data[part] = {"at": now_iso(), **section}
    text = yaml.safe_dump({p: data[p] for p in PARTS if data[p]}, sort_keys=False)
    atomic_write_text(path_of(task_dir), text)
