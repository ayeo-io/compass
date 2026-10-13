#!/usr/bin/env python3
"""Decide whether a job's work is needed for this change.

Usage: ci-changed.py --base SHA --head SHA --output FILE PATH...

A required check must report on every pull request, so a job that only
matters when some files change cannot be skipped with a paths filter or a
job condition: a skipped required check counts as passed, and a filtered
workflow never reports. Such a job runs on every pull request and skips its
own steps instead, gated on the `run` output this command writes.

A PATH ending in "/" matches every file under that folder; any other PATH
matches that one file. Appends "run=true" to FILE when
`git diff --name-only BASE...HEAD` lists a matching file, or when the
change cannot be computed (BASE empty or all zeros, as on a push with no
base or a manual run, BASE or HEAD not a commit here, or git failing).
Appends "run=false" otherwise. Prints the reason and the matching files.
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def _is_commit(sha: str) -> bool:
    r = subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                       capture_output=True, text=True)
    return r.returncode == 0


def decide(base: str, head: str, paths: list[str]) -> tuple[bool, str, list[str]]:
    if not base or not base.strip("0"):
        return True, "there is no base commit to compare with", []
    for name, sha in (("base", base), ("head", head)):
        if not sha or sha.startswith("-") or not _is_commit(sha):
            return True, f"the {name} commit {sha!r} is not in this checkout", []
    r = subprocess.run(["git", "diff", "--name-only", f"{base}...{head}", "--"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return True, f"git diff failed: {' '.join(r.stderr.split())[:200]}", []
    changed = [line for line in r.stdout.splitlines() if line]
    matching = [f for f in changed
                if any(f.startswith(p) if p.endswith("/") else f == p for p in paths)]
    if matching:
        return True, f"{len(matching)} of {len(changed)} changed files match", matching
    return False, f"none of the {len(changed)} changed files match", []


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="ci-changed.py")
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args(argv)
    run, reason, matching = decide(args.base, args.head, args.paths)
    print(f"Watched paths: {' '.join(args.paths)}")
    print(f"{'Run' if run else 'Skip'}: {reason}.")
    for path in matching:
        print(f"  {path}")
    with open(args.output, "a", encoding="utf-8") as out:
        out.write(f"run={'true' if run else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
