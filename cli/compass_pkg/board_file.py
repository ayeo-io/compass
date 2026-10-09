# compass_pkg.board_file - where the board page is written, and how
"""The default path of the board file and the safe write of any board page.

The default file is one stable file per checkout in the system temp folder.
A shared temp folder lets another user plant a link or a file at a name that
is easy to predict, so the default file is checked before every write and the
page goes through a new temporary file with an unpredictable name.

- `default_board_path`: the stable path for a project root;
- `check_default_target`: refuse a link, a non-regular file or another
  user's file at the default path;
- `check_target`: the guard every target passes first, default or `--out`;
- `write_page`: write through `atomic_io.atomic_write_text`.
"""
# DEPENDENCY: standard library (hashlib, os, re, stat, tempfile); compass_pkg.atomic_io, compass_pkg.core.
from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile

from compass_pkg import atomic_io
from compass_pkg.core import CompassError

# Not formed from the board file's name, so a name planted beside the board
# file cannot be the temporary file (the rest of the name is random).
TEMP_PREFIX = ".compass-tmp-"
PRIVATE_MODE = 0o600
OUT_MODE = 0o644


def default_board_path(project_root):
    """`compass-board-<folder>-<8 hex>.html` in the system temp folder. The
    folder is the root's folder name with each character outside
    `[A-Za-z0-9._-]` replaced by `-`; the hex is the start of the SHA-256 of
    the resolved root, so two checkouts with one folder name differ."""
    root = os.path.realpath(os.fspath(project_root))
    folder = re.sub(r"[^A-Za-z0-9._-]", "-", os.path.basename(root.rstrip(os.sep)))
    digest = hashlib.sha256(root.encode("utf-8", "surrogateescape")).hexdigest()[:8]
    return os.path.join(tempfile.gettempdir(), f"compass-board-{folder}-{digest}.html")


def check_default_target(path, command):
    """Refuse a link, a non-regular file, or a file owned by another user at
    `path`. A missing path passes. Uses `os.lstat`, which does not follow a
    link. Where the system has no `os.getuid` the owner check is skipped and
    the link and file-type checks still run."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(st.st_mode):
        what = "a link"
    elif not stat.S_ISREG(st.st_mode):
        what = "not a regular file"
    elif hasattr(os, "getuid") and st.st_uid != os.getuid():
        what = "owned by another user"
    else:
        return
    raise CompassError(f"{command}: {path} is {what}, so the board is not written there; "
                       f"name another file with --out")


def check_target(target, command, project_root):
    """Refuse a missing folder, a directory, and a path inside `.compass/` or
    `docs/compass/`, which hold issue state. Returns the resolved path. Checked
    before the board is read."""
    path = os.path.abspath(target)
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        raise CompassError(f"{command}: the folder for {target} does not exist")
    # Resolve links and compare without case: a link, or `.COMPASS` on a file
    # system that ignores case, must not reach issue state.
    path = os.path.join(os.path.realpath(parent), os.path.basename(path))
    if os.path.isdir(path):
        raise CompassError(f"{command}: {target} is a directory; "
                           f"name a file, such as board.html")
    folded = path.casefold()
    for guarded, label in ((os.path.join(project_root, ".compass"), ".compass"),
                           (os.path.join(project_root, "docs", "compass"), "docs/compass")):
        g = os.path.realpath(guarded).casefold()
        if folded == g or folded.startswith(g + os.sep):
            raise CompassError(
                f"{command}: {target} is inside {label}/, "
                f"which holds issue state; write the page somewhere else")
    return path


def write_page(path, text, mode):
    """Write `text` to `path` through a new temporary file made exclusively in
    the same folder, then move it into place. `mode` is the file's permission
    bits (0600 for the default file, 0644 for an `--out` file). Returns
    "created" or "refreshed". The caller runs the guards first."""
    existed = os.path.lexists(path)
    atomic_io.atomic_write_text(path, text, mode=mode, temp_prefix=TEMP_PREFIX)
    return "refreshed" if existed else "created"
