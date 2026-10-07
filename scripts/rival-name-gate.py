#!/usr/bin/env python3
"""Fail when committed text names a rival product, without naming it.

The maintainer's rule (governance/decisions/2026-10-04-rival-names-never-
committed.md): committed text refers to rival products by the codes R1 to
R9. This gate checks tracked files and paths, commit messages and pull
request text against `scripts/rival-name-hashes.txt`, which holds hashes of
the names, never the names. The key that maps codes to names is held by the
maintainer and is only needed to write or check the hash file.

Usage:
  rival-name-gate.py --tree                 tracked files and paths
  rival-name-gate.py --text FILE|-          any text, such as commit messages
  rival-name-gate.py --github-event FILE    a pull request's title and body
  rival-name-gate.py --write-hashes KEY     write the hash file from the key
  rival-name-gate.py --check-hashes KEY     fail if the hash file is stale
Add --hashes FILE to use another hash file, and --pins FILE another pin
file (by default `rival-name-binary-pins.txt` beside the hash file).

A pin line, a git blob hash and a path, exempts that one non-UTF-8 file from
the content scan of --tree. It never exempts a path or a UTF-8 file, and a
pin whose hash or path no longer matches is reported as stale.

Exit 0 when nothing is found, 1 on a finding, 2 on a usage or input error.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))

from compass_pkg import rival_names  # noqa: E402
from compass_pkg.core import CompassError  # noqa: E402

ADVICE = "a rival product name; use its code (the maintainer holds the key)"


def _read(path):
    with open(path, "rb") as fh:
        return rival_names.readable_text(fh.read())


def _scan_tree(hashes, pins=()):
    listed = subprocess.run(["git", "ls-files", "-z"], capture_output=True,
                            check=True).stdout.decode("utf-8")
    findings = []
    tracked = sorted(p for p in listed.split("\0") if p)
    current = {}                      # path -> blob hash of a scanned file
    for rel in tracked:
        if rival_names.scan(rel, hashes):
            findings.append(f"{rival_names.mask(rel, hashes)}: path: {ADVICE}")
        if not os.path.isfile(rel) or os.path.islink(rel):
            continue
        with open(rel, "rb") as fh:
            data = fh.read()
        current[rel] = rival_names.blob_hash(data)
        if rival_names.is_pinned(rel, data, pins):
            continue
        for line in rival_names.scan(rival_names.readable_text(data), hashes):
            findings.append(f"{rival_names.mask(rel, hashes)}:{line}: {ADVICE}")
    for digest, rel in pins:
        if current.get(rel) != digest:
            why = ("no longer tracked" if rel not in current
                   else "the file's hash has changed")
            findings.append(f"{rival_names.mask(rel, hashes)}: stale pin, "
                            f"{why}: check the file, then re-pin or remove "
                            f"the line")
    return findings


def _scan_text(label, text, hashes):
    return [f"{label}:{line}: {ADVICE}"
            for line in rival_names.scan(text, hashes)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--tree", action="store_true")
    mode.add_argument("--text")
    mode.add_argument("--github-event")
    mode.add_argument("--write-hashes", metavar="KEY")
    mode.add_argument("--check-hashes", metavar="KEY")
    parser.add_argument("--hashes",
                        default=os.path.join(ROOT, rival_names.HASHES_PATH))
    parser.add_argument("--pins")
    args = parser.parse_args(argv)

    try:
        if args.write_hashes:
            rival_names.write_hash_file(rival_names.load_key(args.write_hashes),
                                        args.hashes)
            return 0
        if args.check_hashes:
            expected = rival_names.hash_lines(
                rival_names.load_key(args.check_hashes))
            with open(args.hashes, encoding="utf-8") as fh:
                actual = sorted(line.strip() for line in fh
                                if line.strip() and not line.startswith("#"))
            if actual != expected:
                print(f"{args.hashes} does not match the key: run "
                      f"--write-hashes with it and commit the result")
                return 1
            return 0
        hashes = rival_names.load_hashes(args.hashes)
        if args.tree:
            pins = rival_names.load_pins(args.pins or os.path.join(
                os.path.dirname(os.path.abspath(args.hashes)),
                rival_names.PINS_NAME))
            findings = _scan_tree(hashes, pins)
        elif args.text:
            text = sys.stdin.read() if args.text == "-" else _read(args.text)
            findings = _scan_text("text", text, hashes)
        else:
            with open(args.github_event, encoding="utf-8") as fh:
                pull = (json.load(fh) or {}).get("pull_request") or {}
            branch = (pull.get("head") or {}).get("ref") or ""
            findings = (_scan_text("branch name", branch, hashes)
                        + _scan_text("pull request title", pull.get("title") or "",
                                     hashes)
                        + _scan_text("pull request body", pull.get("body") or "",
                                     hashes))
    except subprocess.CalledProcessError:
        print("rival-name-gate: --tree needs a git checkout, to list tracked "
              "files", file=sys.stderr)
        return 2
    except (CompassError, OSError, ValueError) as exc:
        print(f"rival-name-gate: {exc}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
