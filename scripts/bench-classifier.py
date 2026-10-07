#!/usr/bin/env python3
# =============================================================================
# bench-classifier - how long the classifier takes on the shipped preset
# =============================================================================
# ADR-037 asks for the grouped and the raw grid to be timed at four and at
# eight named labels before the classifier ships, and for the label cap to be
# revisited only with these numbers. The pair compared is the shipped preset
# and the same preset with one check that no list names, so the result is
# `equivalent` and the whole grid is scanned. The extra labels come from one
# rule that names them and changes nothing.
#
# DEPENDENCY: standard library (argparse, copy, platform, sys, time) and
# compass_pkg.classify, and the committed default preset (read through the
# merge, as a loader will).
# =============================================================================
"""Time the classifier over the grouped and the full grid.

    scripts/bench-classifier.py                 grouped grid at 4 and 8 labels
    scripts/bench-classifier.py --raw           also the full grid
    scripts/bench-classifier.py --labels 4      one label count
"""
from __future__ import annotations

import argparse
import copy
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import catalogue_spec, classify, core, merge  # noqa: E402

DEFAULT_LABELS = (4, 8)
SHIPPED_LABELS = ("auth", "migrations", "payments", "personal-data")


def preset():
    directory = ROOT / "governance" / "presets" / "default"
    parts = []
    for name in catalogue_spec.CATALOGUES:
        # The package's reader, so the bundled YAML parser is the one used.
        part = core.load_yaml(str(directory / f"{name}.yml"))
        parts.append({k: v for k, v in part.items() if k != "schema"})
    config, _ = merge.apply({}, {"schema": 1, **merge.combine(parts)}, "parent",
                            "default")
    return config


def pair(labels):
    """The preset and a copy with one unlisted check, both naming `labels`
    labels in all (the shipped four, then extras)."""
    parent = preset()
    extra = [f"label-{i}" for i in range(labels - len(SHIPPED_LABELS))]
    if extra:
        parent["rules"]["floors"]["rules"]["BENCH-LABELS"] = {
            "order": 99, "when": {"labels_any": extra},
            "then": {"force_minimum_approach": "regular"}}
    child = copy.deepcopy(parent)
    child["checks"]["bench-unlisted"] = {
        "statement": "Nothing lists this check.", "kind": "deterministic",
        "impl": "suite-passed", "severity": "blocking", "on_skipped": "fail"}
    return parent, child


def measure(parent, child, exhaustive):
    """One scan, timed. `evaluations` counts calls to the evaluator."""
    start = time.perf_counter()
    got = classify.classify(parent, child, exhaustive=exhaustive)
    seconds = time.perf_counter() - start
    return {"mode": "full" if exhaustive else "grouped",
            "labels": got.grid.label_count, "points": got.grid.points,
            "raw_points": got.grid.raw_points, "evaluations": 2 * got.grid.evaluated,
            "seconds": seconds, "result": got.result}


def format_row(row):
    per_point = row["seconds"] / max(row["points"], 1) * 1e6
    return (f"{row['mode']:8} {row['labels']:2} labels {row['points']:>9,} points "
            f"{row['evaluations']:>9,} evaluations {row['seconds']:>8.1f} s "
            f"{per_point:>7.0f} us/point  {row['result']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--labels", type=int, nargs="+", default=list(DEFAULT_LABELS),
                    help="named labels to time at (at most the cap of eight)")
    ap.add_argument("--raw", action="store_true", help="also time the full grid")
    args = ap.parse_args(argv)
    print(f"python {platform.python_version()} on {platform.platform()}")
    for count in args.labels:
        parent, child = pair(count)
        for exhaustive in ((False, True) if args.raw else (False,)):
            print(format_row(measure(parent, child, exhaustive)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
