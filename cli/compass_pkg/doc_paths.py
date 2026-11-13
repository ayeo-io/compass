# compass_pkg.doc_paths - where an issue document may be written
"""The path checks a command runs before it writes an issue document.

They moved out of `render_cmd.py` when 9.0.0 removed `compass issue render`
(ADR-091): the quick-fix record and the 7.0.0 migrate still write a document.
"""
# DEPENDENCY: standard library (os); compass_pkg.core.
from __future__ import annotations

import os

from compass_pkg.core import CompassError, _registered_path, find_upwards


def _project_root(task_dir):
    root = find_upwards(task_dir, ".compass")
    if root is None:
        raise CompassError(f"compass: no .compass folder above {task_dir}.")
    return os.path.abspath(root)


def project_of(task_dir):
    """The project root above an issue's work folder."""
    return _project_root(os.path.abspath(task_dir))


def _link_problem(project, resolved):
    """Why `resolved` cannot be written, or None: it is, or sits under, a
    symbolic link. Only the parts below the project are checked."""
    rel = os.path.relpath(resolved, project)
    cur = project
    for part in rel.split(os.sep):
        cur = os.path.join(cur, part)
        if os.path.islink(cur):
            return f"{rel} is, or sits under, a symbolic link ({part})"
    return None


def unsafe_document_path(task_dir, rel, project, allow_work=False):
    """Why a path built from a manifest cannot be written, or None: it leaves the project, is
    not under docs/compass (or, with `allow_work`, the issue's own folder), or is, or sits
    under, a symbolic link. A caller that writes a document checks it before any change."""
    resolved, refused = _registered_path(task_dir, rel)
    if refused:
        return "it resolves outside the project"
    resolved = os.path.abspath(resolved)
    folders = [os.path.join(project, "docs", "compass") + os.sep]
    if allow_work:
        folders.append(os.path.abspath(task_dir) + os.sep)
    if not resolved.startswith(tuple(folders)):
        return "it is not under docs/compass"
    return _link_problem(project, resolved)
