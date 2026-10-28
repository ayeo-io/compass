"""Build a PATH folder that holds the system's programs, minus some.

Tests that run a hook without jq or without python3 link every program of
/usr/bin and /bin into one folder, leaving those out, and use the folder as
PATH.
"""
from __future__ import annotations

import os
from pathlib import Path

SYSTEM_FOLDERS = ("/usr/bin", "/bin")


def link_programs(dest, skip, sources=SYSTEM_FOLDERS):
    """Link each program in `sources` into `dest`, unless `skip(name)` is
    true. A name in an earlier source wins over the same name in a later one.
    Returns `dest` as a string, ready to use as PATH.

    `lexists`, not `exists`: a broken link does not exist, so a name both
    sources hold as a broken link would be linked twice and raise
    FileExistsError (GitHub's Ubuntu runner image, October 2026)."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for source in sources:
        for name in sorted(os.listdir(source)):
            if skip(name) or os.path.lexists(dest / name):
                continue
            (dest / name).symlink_to(os.path.join(source, name))
    return str(dest)
