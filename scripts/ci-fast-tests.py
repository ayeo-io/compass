#!/usr/bin/env python3
"""Print the test files the `fast-tests` job runs on a pull request.

Usage: ci-fast-tests.py --base SHA --head SHA [--root DIR]

On a pull request, .github/workflows/compass.yml runs a few test files, not
the whole suite: the merge queue runs the whole suite once, on the tree that
would merge. This command lists those files, one per line, sorted:

- every file in HOUSE_RULES. Each guards a rule every change must meet, and
  together they take about two minutes of test time;
- every test file that `git diff --name-only BASE...HEAD` lists and that is
  in the working tree. A test file is one that pytest collects from
  DIR/tests, by the rule scripts/ci-shard.py follows. A deleted or renamed
  file is listed only under the name it has now.

It prints the count of each kind and their seconds, from
tests/ci-durations.json, on standard error.

Exit 2, with the reason on standard error and nothing on standard output,
when BASE is empty or all zeros, BASE or HEAD is not a commit here, git
fails, or a file in HOUSE_RULES is missing. Running fewer tests than asked
is the one wrong answer, so this command fails instead of guessing.
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

# The house rules in CLAUDE.md that a test enforces, plus the test that keeps
# CLAUDE.md equal to compass-contract.md and the one that keeps every action
# pinned by SHA. tests/test_writing_style.py is left out: it takes about 500
# seconds of test time, so it runs in the merge queue only.
HOUSE_RULES = (
    "tests/test_house_style.py",
    "tests/test_terminology.py",
    "tests/test_rival_names_never_committed.py",
    "tests/test_us_english_guard.py",
    "tests/test_contract_claude_md_drift.py",
    "tests/test_workflow_pins.py",
)


def _shard_module():
    path = Path(__file__).resolve().parent / "ci-shard.py"
    spec = importlib.util.spec_from_file_location("ci_shard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Refused(Exception):
    pass


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True,
                          text=True, timeout=120)


def changed(root: Path, base: str, head: str) -> list[str]:
    if not base or not base.strip("0"):
        raise Refused("there is no base commit to compare with")
    for name, sha in (("base", base), ("head", head)):
        if not sha or sha.startswith("-") or \
                _git(root, "cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
            raise Refused(f"the {name} commit {sha!r} is not in this checkout")
    r = _git(root, "diff", "--name-only", f"{base}...{head}", "--")
    if r.returncode != 0:
        raise Refused(f"git diff failed: {' '.join(r.stderr.split())[:200]}")
    return [line for line in r.stdout.splitlines() if line]


def select(root: Path, base: str, head: str) -> tuple[list[str], list[str]]:
    """The house-rule files and the changed test files, each sorted."""
    collected = set(_shard_module().test_files(root))
    missing = [f for f in HOUSE_RULES if f not in collected]
    if missing:
        raise Refused("a house-rule test file is not in this checkout: "
                      + ", ".join(missing))
    touched = sorted(f for f in set(changed(root, base, head)) & collected
                     if f not in HOUSE_RULES)
    return sorted(HOUSE_RULES), touched


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="ci-fast-tests.py")
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        house, touched = select(root, args.base, args.head)
    except Refused as exc:
        sys.stderr.write(f"ci-fast-tests.py: {exc}.\n")
        return 2
    try:
        seconds = _shard_module().recorded_seconds(root)
    except Exception:  # the table only adds the estimate below
        seconds = {}

    def load(files):
        return sum(seconds.get(f, 0.0) for f in files)

    sys.stderr.write(
        f"House-rule test files: {len(house)}, {load(house):.0f} seconds recorded.\n"
        f"Test files this change edits: {len(touched)}, "
        f"{load(touched):.0f} seconds recorded.\n")
    for path in touched:
        sys.stderr.write(f"  {path}\n")
    sys.stdout.write("".join(f"{path}\n" for path in sorted(house + touched)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
