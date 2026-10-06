#!/usr/bin/env python3
"""Capture the routing compatibility baseline (contracts 1 and 2) once.

The configuration rewrite must route a project with no configuration
exactly as the release it started from. This writes what that release does:
the evaluator's result for every closed assessment, a digest for every
assessment with every subset of the labels a routing predicate names, the
full result for each assessment the archive sample records, and what each
delivery approach owes.

Run it on the release commit, never on new code: a baseline captured from
the code under test records its regressions as expected. It refuses to
overwrite an existing baseline unless given --force, which a person uses
only when the shipped defaults change on purpose in a new major version.
"""
from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from archive import sample_root  # noqa: E402
from compat_baseline import (DIMENSIONS, FIXTURES, OWED, ROUTING, compact,  # noqa: E402
                             digest, grid, label_subsets, named_labels,
                             owed_by_approach, shipped_policy)
from compass_pkg.core import CompassError, load_yaml  # noqa: E402


def _archive_assessments():
    """Each distinct full assessment the archive sample's issues recorded."""
    seen, found = set(), []
    for manifest in sorted((sample_root() / ".compass" / "work").glob("*/manifest.yml")):
        try:
            data = load_yaml(str(manifest))
        except CompassError:
            continue
        reading = (data or {}).get("assessment") if isinstance(data, dict) else None
        if not isinstance(reading, dict) or not all(d in reading for d in DIMENSIONS[:3]):
            continue
        reading = {k: reading[k] for k in (*DIMENSIONS, "labels") if k in reading}
        reading["labels"] = sorted(reading.get("labels") or [])
        key = json.dumps(reading, sort_keys=True)
        if key not in seen:
            seen.add(key)
            found.append(reading)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing baseline (a new major only)")
    args = parser.parse_args()
    if ROUTING.exists() and not args.force:
        sys.exit(f"{ROUTING.relative_to(ROOT)} exists. A baseline is captured once; "
                 f"pass --force only for a new major version's defaults.")
    policy = shipped_policy()
    vocabulary = {d: policy["assessment_vocabulary"][d] for d in DIMENSIONS}
    labels = named_labels(policy)
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    version = (ROOT / "VERSION").read_text().strip()
    header = {"kind": "header", "version": version, "captured_from": commit,
              "vocabulary": vocabulary, "labels": labels}
    rows = []
    for readings in grid(vocabulary):
        rows.append({"kind": "grid", "assessment": readings,
                     "result": compact(readings, policy)})
        rows.append({"kind": "label-digests", "assessment": readings,
                     "digests": [digest(compact(dict(readings, labels=s), policy))
                                 for s in label_subsets(labels)]})
    for readings in _archive_assessments():
        rows.append({"kind": "archive", "assessment": readings,
                     "result": compact(readings, policy)})
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(ROUTING, "wb", mtime=0) as fh:
        for row in [header, *rows]:
            fh.write((json.dumps(row, sort_keys=True) + "\n").encode("utf-8"))
    owed = owed_by_approach(rows)
    OWED.write_text(
        "# Contract 2: what each delivery approach owes across the label-free\n"
        "# grid, projected from contract 1. Captured once by\n"
        "# scripts/capture-compat-baseline.py; never regenerate it from new code.\n"
        + json.dumps({"captured_from": commit, "version": version, "owed": owed},
                     indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"captured {sum(r['kind'] == 'grid' for r in rows)} grid points, "
          f"{len(labels)} labels, {sum(r['kind'] == 'archive' for r in rows)} "
          f"archive assessments from {version} at {commit[:12]}")


if __name__ == "__main__":
    main()
