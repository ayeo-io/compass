#!/usr/bin/env python3
"""Print the test files of one CI shard.

Usage: ci-shard.py INDEX COUNT [--root DIR]

The `shard` job in .github/workflows/compass.yml splits the parallel test
pass by file. This command lists every file pytest would collect from
DIR/tests (DIR is the current folder by default), sorts the list by path,
and deals it round-robin: file number k goes to shard k mod COUNT. It reads
the working tree, not git, so a new or renamed test file lands in a shard
with no list to edit.

It follows pytest's rules as this project's pytest.ini sets them: file
names match `python_files` (default "test_*.py *_test.py"), and a folder is
skipped when its name matches `norecursedirs` (pytest's default patterns
when the setting is absent) or when it holds a pyvenv.cfg file.

Exit 2, with the reason on standard error and nothing on standard output,
when an argument is missing or out of range. Exit 1 when the shard holds no
file, because pytest given an empty list would run the whole of testpaths.
"""
from __future__ import annotations

import configparser
import fnmatch
import os
import sys
from pathlib import Path

DEFAULT_PYTHON_FILES = ["test_*.py", "*_test.py"]
# pytest's own default for norecursedirs.
DEFAULT_NORECURSE = ["*.egg", ".*", "_darcs", "build", "CVS", "dist",
                     "node_modules", "venv", "{arch}"]


def _ini_list(root: Path, key: str, default: list[str]) -> list[str]:
    ini = root / "pytest.ini"
    if not ini.is_file():
        return default
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(ini, encoding="utf-8")
    if not parser.has_option("pytest", key):
        return default
    return parser.get("pytest", key).split()


def test_files(root: Path) -> list[str]:
    """Every file pytest would collect from root/tests, as POSIX paths
    relative to root, sorted."""
    names = _ini_list(root, "python_files", DEFAULT_PYTHON_FILES)
    norecurse = _ini_list(root, "norecursedirs", DEFAULT_NORECURSE)
    found = []
    for folder, dirs, files in os.walk(root / "tests"):
        dirs[:] = [d for d in dirs
                   if not any(fnmatch.fnmatch(d, p) for p in norecurse)
                   and not (Path(folder) / d / "pyvenv.cfg").exists()]
        for name in files:
            if any(fnmatch.fnmatch(name, p) for p in names):
                found.append((Path(folder) / name).relative_to(root).as_posix())
    return sorted(found)


def _refuse(reason: str) -> int:
    sys.stderr.write(f"ci-shard.py: {reason}\n"
                     "usage: ci-shard.py INDEX COUNT [--root DIR]\n")
    return 2


def main(argv: list[str]) -> int:
    root = Path.cwd()
    args = list(argv)
    if "--root" in args:
        at = args.index("--root")
        if at + 1 >= len(args):
            return _refuse("--root needs a folder")
        root = Path(args[at + 1])
        del args[at:at + 2]
    if len(args) != 2:
        return _refuse("give exactly two arguments, INDEX and COUNT")
    try:
        index, count = int(args[0]), int(args[1])
    except ValueError:
        return _refuse(f"INDEX and COUNT must each be a whole number, "
                       f"not {args[0]!r} and {args[1]!r}")
    if count < 1:
        return _refuse(f"COUNT must be at least 1, not {count}")
    if index < 0:
        return _refuse(f"INDEX must not be negative, not {index}")
    if index >= count:
        return _refuse(f"INDEX {index} is not below COUNT {count}")
    mine = test_files(root)[index::count]
    if not mine:
        sys.stderr.write(f"ci-shard.py: shard {index} of {count} holds no "
                         f"test files under {root / 'tests'}\n")
        return 1
    sys.stdout.write("".join(f"{path}\n" for path in mine))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
