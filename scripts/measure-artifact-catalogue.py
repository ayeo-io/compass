#!/usr/bin/env python3
"""Measure the archive for the artifact-catalogue-fields issue (ACF-52, ACF-57).

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

`--after` gives the figures for a copy the 7.0.0 migrate has run on, read
with the shipped catalogue and the shipped not-an-artifact list:

- `unregistered_files`: documents-folder files `compass issue lint` reports
  as matching no kind;
- `regular_issues`, `regular_with_record`: regular issues, and those whose
  documents folder holds `delivery-approach.md` registered at that path;
- `regular_without_record`: regular issues that held a record before the
  migrate (on disk in either folder, or registered with a path) and lack it;
- `regular_never_had_record`: regular issues that never had a record. The
  migrate writes no judgement, so they are counted apart and not as a fault;
- `other_without_record`: issues of any other approach that hold a record
  somewhere but not registered in the documents folder;
- `regular_small_with_map`: regular issues with fewer than two subtasks whose
  map is registered at lightweight depth and sits in the documents folder or
  is an entry the check treats as owed. An issue with no subtasks list whose
  map names two or more subtasks is left out, as the migrate leaves it;
- `regular_small_adopted_map`: the same issues whose map the migrate adopted
  with no depth. It is a person's map and is kept;
- `review_not_numbered`: review filenames, registered or sent to review by
  the mapping table, that are not `review-<n>.md`;
- `review_round_clashes`: issues holding two `review-<n>.md` files with the
  same n.

`issues` names the issues behind each figure that is not zero.
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


PLAIN_REVIEW = re.compile(r"^review-([1-9]\d*)\.md$")


#: The lightweight artifact depth in today's word and the 5.x one.
LIGHTWEIGHT = ("lightweight", "light")


def _markdown(folder: Path) -> list:
    return sorted(n for n in os.listdir(folder)
                  if n.endswith(".md") and (folder / n).is_file()) if folder.is_dir() else []


def measure_after(root: Path) -> dict:
    from compass_pkg import artifact_kinds, artifact_owed, migrate_kinds
    catalogue = migrate_kinds.shipped_catalogue()
    work = root / ".compass" / "work"
    issues = {"unregistered_files": [], "regular_without_record": [],
              "regular_never_had_record": [], "other_without_record": [],
              "regular_small_with_map": [], "regular_small_adopted_map": [],
              "review_not_numbered": [], "review_round_clashes": []}
    regular = with_record = 0
    tasks = sorted(p for p in work.iterdir() if p.is_dir()) if work.is_dir() else []
    for task in tasks:
        data = _manifest(task)
        if data is None:
            continue
        docs = root / docs_dir_for(str(data.get("created") or "").strip(), task.name)
        entries = [e for e in data.get("artifacts") or [] if isinstance(e, dict)]
        in_docs, beside = _markdown(docs), _markdown(task)
        issues["unregistered_files"] += ["%s: %s" % (task.name, n) for n in
                                         artifact_kinds.unmatched_documents(None, str(task))]
        home = "%s/delivery-approach.md" % docs.relative_to(root).as_posix()
        held = "delivery-approach.md" in in_docs and any(
            e.get("kind") == "delivery-approach" and e.get("path") == home for e in entries)
        is_regular = data.get("delivery_approach") == "regular"
        # An issue held a record before the migrate when a record is on disk in either
        # folder, or registered with a path. The migrate moves and registers judgement;
        # it writes none, so an issue that never had a record is counted apart.
        had = "delivery-approach.md" in in_docs or any(
            e.get("kind") == "delivery-approach" and e.get("path") for e in entries) or (
            "delivery-approach.md" in beside and not _is_pointer(task / "delivery-approach.md"))
        if is_regular:
            regular += 1
            with_record += held
            if not held:
                key = "regular_without_record" if had else "regular_never_had_record"
                issues[key].append(task.name)
        elif not held and ("delivery-approach.md" in in_docs
                           or ("delivery-approach.md" in beside
                               and not _is_pointer(task / "delivery-approach.md"))):
            issues["other_without_record"].append(task.name)
        if is_regular and artifact_owed.subtask_count(data) < 2:
            wide = not isinstance(data.get("subtasks"), list) and \
                migrate_kinds._map_rows(str(docs / "distribution-map.md")) >= 2
            maps = [e for e in entries if e.get("kind") == "distribution-map"
                    and e.get("status") not in ("superseded", "omitted")]
            # Only a map registered at lightweight depth is a stub the migrate judges. A
            # map it adopted with no depth is a person's map, kept and counted apart.
            light = [e for e in maps if e.get("depth") in LIGHTWEIGHT]
            owed = [e for e in light if artifact_owed.owed(data, None, "distribution-map", e).owed]
            if not wide and light and ("distribution-map.md" in in_docs or owed):
                issues["regular_small_with_map"].append(task.name)
            elif not wide and "distribution-map.md" in in_docs \
                    and any(not e.get("depth") for e in maps):
                issues["regular_small_adopted_map"].append(task.name)
        names = {n for n in (*beside, *in_docs)
                 if migrate_kinds.lookup(n, catalogue).kind == migrate_kinds.REVIEW}
        names |= {str(e.get("path")).rsplit("/", 1)[-1] for e in entries
                  if e.get("kind") == migrate_kinds.REVIEW and e.get("path")}
        issues["review_not_numbered"] += ["%s: %s" % (task.name, n) for n in sorted(names)
                                          if not PLAIN_REVIEW.match(n)]
        numbers = [int(PLAIN_REVIEW.match(n).group(1)) for n in (*beside, *in_docs)
                   if PLAIN_REVIEW.match(n)]
        issues["review_round_clashes"] += ["%s: round %d" % (task.name, n)
                                           for n in sorted(set(numbers)) if numbers.count(n) > 1]
    result = {key: len(value) for key, value in issues.items()}
    result.update(regular_issues=regular, regular_with_record=with_record,
                  issues={key: value for key, value in issues.items() if value})
    return result


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
    parser.add_argument("--after", action="store_true",
                        help="the after figures, for a copy the 7.0.0 migrate has run on")
    args = parser.parse_args(argv)
    if args.after:
        result = measure_after(Path(args.root))
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        print(f"unregistered files: {result['unregistered_files']}")
        print(f"regular issues with delivery-approach.md registered in the documents folder: "
              f"{result['regular_with_record']} of {result['regular_issues']}")
        print(f"regular issues that held a record before the migrate and lack it: "
              f"{result['regular_without_record']}")
        print(f"regular issues that never had a record: {result['regular_never_had_record']}")
        print(f"other issues holding a record that is not registered in the documents folder: "
              f"{result['other_without_record']}")
        print(f"regular issues with fewer than two subtasks carrying a lightweight distribution "
              f"map: {result['regular_small_with_map']}")
        print(f"of those issues, maps adopted with no depth: {result['regular_small_adopted_map']}")
        print(f"review filenames that are not review-<n>.md: {result['review_not_numbered']}")
        print(f"issues with two review files of one round: {result['review_round_clashes']}")
        for key, names in result["issues"].items():
            print(f"  {key}: {', '.join(names)}")
        return 0
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
