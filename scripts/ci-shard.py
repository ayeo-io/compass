#!/usr/bin/env python3
"""Print the test files of one CI shard.

Usage: ci-shard.py INDEX COUNT [--root DIR] [--loads]

The `shard` job in .github/workflows/compass.yml splits the parallel test
pass by file. This command lists every file pytest would collect from
DIR/tests (DIR is the current folder by default) and splits the list by
weight, so each shard takes about the same time:

- a file's weight is its entry in the table tests/ci-durations.json under
  DIR, the sum of the durations a CI run recorded for its tests
  (scripts/ci-durations.py writes the table);
- a file the table does not hold, such as a new one, weighs the median of
  the table's entries, so it still lands in a shard;
- files go heaviest first, ties by path, each to the shard with the least
  weight so far, ties to the lower index. The split is the same on every
  run for the same files and table.

It reads the working tree, not git, so a new or renamed test file lands in
a shard with no list to edit. With no table, every file weighs the same.

It follows pytest's rules as this project's pytest.ini sets them: file
names match `python_files` (default "test_*.py *_test.py"), and a folder is
skipped when its name matches `norecursedirs` (pytest's default patterns
when the setting is absent) or when it holds a pyvenv.cfg file.

With --loads it prints one line, the shard's file count and the seconds
the table gives it, instead of the files.

Exit 2, with the reason on standard error and nothing on standard output,
when an argument is missing or out of range, or when the table cannot be
read. Exit 1 when the shard holds no file, because pytest given an empty
list would run the whole of testpaths.
"""
from __future__ import annotations

import configparser
import fnmatch
import json
import os
import statistics
import sys
from pathlib import Path

DEFAULT_PYTHON_FILES = ["test_*.py", "*_test.py"]
# pytest's own default for norecursedirs.
DEFAULT_NORECURSE = ["*.egg", ".*", "_darcs", "build", "CVS", "dist",
                     "node_modules", "venv", "{arch}"]
TABLE = "tests/ci-durations.json"
USAGE = "usage: ci-shard.py INDEX COUNT [--root DIR] [--loads]\n"


class TableError(Exception):
    pass


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


def recorded_seconds(root: Path) -> dict[str, float]:
    """The table's seconds per file; empty when there is no table."""
    path = root / TABLE
    if not path.is_file():
        return {}
    try:
        seconds = json.loads(path.read_text(encoding="utf-8"))["seconds"]
    except (ValueError, KeyError, TypeError) as exc:
        raise TableError(f"{TABLE} cannot be read: {exc}") from exc
    if not isinstance(seconds, dict) or not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0
            for v in seconds.values()):
        raise TableError(f"{TABLE}: 'seconds' must map each file to a "
                         "number of seconds, not below 0")
    return {str(k): float(v) for k, v in seconds.items()}


def split(files: list[str], seconds: dict[str, float],
          count: int) -> list[tuple[list[str], float]]:
    """The files of each shard, sorted, and the seconds they weigh."""
    default = statistics.median(seconds.values()) if seconds else 1.0
    weight = {f: seconds.get(f, default) for f in files}
    shards: list[list[str]] = [[] for _ in range(count)]
    loads = [0.0] * count
    for f in sorted(files, key=lambda f: (-weight[f], f)):
        lightest = min(range(count), key=lambda i: (loads[i], i))
        shards[lightest].append(f)
        loads[lightest] += weight[f]
    return [(sorted(s), load) for s, load in zip(shards, loads)]


def _refuse(reason: str) -> int:
    sys.stderr.write(f"ci-shard.py: {reason}\n{USAGE}")
    return 2


def main(argv: list[str]) -> int:
    root = Path.cwd()
    args = list(argv)
    loads = "--loads" in args
    if loads:
        args.remove("--loads")
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
    try:
        seconds = recorded_seconds(root)
    except TableError as exc:
        return _refuse(str(exc))
    mine, load = split(test_files(root), seconds, count)[index]
    if not mine:
        sys.stderr.write(f"ci-shard.py: shard {index} of {count} holds no "
                         f"test files under {root / 'tests'}\n")
        return 1
    if loads:
        noun = "file" if len(mine) == 1 else "files"
        sys.stdout.write(f"shard {index} of {count} holds {len(mine)} {noun}, "
                         f"{load:.2f} seconds\n")
        return 0
    sys.stdout.write("".join(f"{path}\n" for path in mine))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
