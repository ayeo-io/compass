#!/usr/bin/env python3
"""Measure the archive for the artifact-catalogue-fields issue (ACF-52).

Run it on a throwaway copy of the archive. It only reads, but the copy keeps
the maintainer's records safe from every later step that writes.

The "before" figures come from a project root that holds `.compass/work/`
and `docs/compass/`:

- `kinds_declared`: the kinds the catalogue declares;
- `undeclared_kinds`: the kind names in use that the catalogue does not
  declare. A name is in use when a manifest registers it, when a document
  sits beside a manifest, or when a document sits in the issue's documents
  folder and no registry entry holds a path for it. This is the listing the
  6.x migrate makes (`migrate._relocations`), written out again here so the
  number does not change when the migrate does;
- `regular_issues`: issues whose delivery approach is regular;
- `regular_with_record`: regular issues whose documents folder holds
  `delivery-approach.md`;
- `regular_with_stub_map`: regular issues with fewer than two subtasks that
  carry a `distribution-map.md`, in either folder;
- `review_filenames`: distinct filenames that hold a review round.

`--catalogue` reads the kinds from a copy of an `artifacts.yml`, so the
baseline is taken against the catalogue as it was before the change.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.core import CompassError, load_yaml  # noqa: E402
from compass_pkg.issue_layout import docs_dir_for  # noqa: E402

DEFAULT_CATALOGUE = ROOT / "governance" / "presets" / "default" / "artifacts.yml"

#: The markdown files that stay beside a manifest and are never a kind
#: (`migrate.STAYS_BESIDE_THE_MANIFEST`).
BESIDE_THE_MANIFEST = {"devlog.md", "README.md"}

#: A filename that holds a review round, under any name the archive gave one:
#: `review`, `review-<n>`, `review-claims`, `security-review`,
#: `integrated-review-<n>` and `verify-<word>`.
REVIEW_NAME = re.compile(
    r"^(review|review-claims|security-review|integrated-review|verify-[a-z]+)"
    r"(-\d+)?\.md$")

#: What the migrate writes at the old path of a moved record.
POINTER_MARKER = "<!-- compass: moved -->"


def _is_pointer(path: Path) -> bool:
    try:
        return POINTER_MARKER in path.read_text(encoding="utf-8")[:400]
    except OSError:
        return False


def _manifest(task: Path):
    try:
        data = load_yaml(str(task / "manifest.yml"))
    except CompassError:
        return None
    return data if isinstance(data, dict) else None


def declared_kinds(catalogue: Path) -> set:
    doc = load_yaml(str(catalogue))
    body = doc.get("artifacts") if isinstance(doc, dict) else None
    return set(body) if isinstance(body, dict) else set()


def measure(root: Path, catalogue: Path) -> dict:
    declared = declared_kinds(catalogue)
    work = root / ".compass" / "work"
    undeclared: set = set()
    review_files: set = set()
    regular = with_record = stubs = 0
    tasks = sorted(p for p in work.iterdir() if p.is_dir()) if work.is_dir() else []
    for task in tasks:
        data = _manifest(task)
        if data is None:
            continue
        docs = root / docs_dir_for(str(data.get("created") or "").strip(), task.name)
        registered = {str(e["kind"]): e for e in data.get("artifacts") or []
                      if isinstance(e, dict) and e.get("kind")}
        undeclared |= set(registered)
        beside = [n for n in sorted(os.listdir(task))
                  if n.endswith(".md") and n not in BESIDE_THE_MANIFEST
                  and (task / n).is_file() and not _is_pointer(task / n)]
        in_docs = [n for n in (sorted(os.listdir(docs)) if docs.is_dir() else [])
                   if n.endswith(".md") and (docs / n).is_file()]
        undeclared |= {n[:-3] for n in beside}
        for name in in_docs:
            entry = registered.get(name[:-3])
            if name not in beside and not (entry is not None and entry.get("path")):
                undeclared.add(name[:-3])
        review_files |= {n for n in (*beside, *in_docs) if REVIEW_NAME.match(n)}
        if data.get("delivery_approach") != "regular":
            continue
        regular += 1
        with_record += "delivery-approach.md" in in_docs
        subtasks = data.get("subtasks")
        count = len(subtasks) if isinstance(subtasks, list) else 0
        if count < 2 and ("distribution-map.md" in in_docs
                          or "distribution-map.md" in beside):
            stubs += 1
    undeclared -= declared
    return {
        "kinds_declared": len(declared),
        "undeclared_kinds": len(undeclared),
        "regular_issues": regular,
        "regular_with_record": with_record,
        "regular_with_stub_map": stubs,
        "review_filenames": len(review_files),
        "_undeclared": sorted(undeclared),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=str(ROOT),
                        help="a project root holding .compass/work and docs/compass; "
                             "pass a copy of the archive")
    parser.add_argument("--catalogue", default=str(DEFAULT_CATALOGUE),
                        help="the artifacts.yml to count declared kinds from")
    parser.add_argument("--json", action="store_true", help="print the figures as JSON")
    parser.add_argument("--list-kinds", metavar="FILE",
                        help="write the undeclared kind names, one per line, to FILE")
    args = parser.parse_args(argv)
    result = measure(Path(args.root), Path(args.catalogue))
    names = result.pop("_undeclared")
    if args.list_kinds:
        Path(args.list_kinds).write_text("\n".join(names) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    print(f"kinds declared: {result['kinds_declared']}")
    print(f"undeclared kinds in use: {result['undeclared_kinds']}")
    print(f"regular issues with delivery-approach.md in the documents folder: "
          f"{result['regular_with_record']} of {result['regular_issues']}")
    print(f"regular issues whose distribution map is a stub: "
          f"{result['regular_with_stub_map']} of {result['regular_issues']}")
    print(f"distinct review filenames: {result['review_filenames']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
