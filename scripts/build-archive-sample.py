#!/usr/bin/env python3
"""Build the tracked archive sample the archive tests read.

Compass keeps each issue's records out of git (`.compass/work/<slug>/` and
`docs/compass/<created>-<slug>/`), so a test that reads them skipped in CI
and gave a result that depended on which ignored folders a machine held.
This copies a fixed list of real issues, with the same layout, into one
archive file, `tests/fixtures/archive-sample.tar.gz`, scrubbed so it can be
tracked. `tests/archive.py` unpacks it for the tests. It is one file and not
a folder because the issues are historical records: they keep the retired
names and older wording the repository's own prose scans refuse, and a scan
should not judge a record of what was written then. The scrub:

- local absolute paths become `<project>`, `<tmp>` or `~`;
- paths into the private planning folders, and the ids of the private
  specs in them, become a plain description;
- email addresses become `<email>`, and the name git records for the
  person building the sample becomes the GitHub username;
- anything shaped like a credential is redacted;
- em dashes become hyphens, as the house rule asks of every file;
- a file that quotes another product is replaced by a note saying what was
  there (WITHHELD): Compass never quotes a competitor product in anything
  it commits.

The maintainer approved publishing this sample on 2026-10-03. That narrows,
for these scrubbed records only, the earlier decision to keep `.compass/`
private, which the `publish-the-archive` issue in the sample records.

A landed issue's `land_commit` names a commit of this repository, whose
root is the project root the issue's changed files are relative to. The
sample unpacks into a folder of its own, so the comparison
`evidence-matches-tree` makes against that commit can never hold there.
The builder drops `land_commit`, and the check declines on the sample; the
full-archive opt-in still runs it on the real records.

Each evidence record carries a digest over its own content, which
`compass check` recomputes. A record the scrub changed gets its digest
recomputed with the same function the check uses, and the manifest's copy
of that digest is updated to match. Nothing else about a record changes.

Run it from the repository root, after changing SLUGS:

    python3 scripts/build-archive-sample.py

It replaces the archive file and is deterministic: two runs over the same
issues give the same bytes. `tests/test_archive_sample.py` fails if
anything private is left in the sample.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.core import load_yaml, save_manifest  # noqa: E402
from compass_pkg.red_first import content_digest  # noqa: E402
from compass_pkg.redact import redact  # noqa: E402

#: The name the sample uses for the person who did the work.
GITHUB_USER = "jed72"

#: The issues in the sample, and why each is there. Every one has landed or
#: was abandoned: an issue in flight records the tree of the moment, which
#: a tracked copy can never match.
SLUGS = {
    # Named by tests/test_landed_by.py: delivered by other issues or commits.
    "the-human-review-pack": "landed_by names three issues",
    "the-human-front-door": "named by the-human-review-pack's landed_by",
    "the-terminal-output-contract": "named by the-human-review-pack's landed_by",
    "adaptive-artifact-composition": "named by the-human-review-pack's landed_by",
    "evaluator-prints-code-before-meaning": "landed_by names a commit",
    "tdd-green-scenario-overwrites-the-record": "landed_by names a commit",
    "landed-issues-trace-rot-is-unchecked": "landed_by names a commit",
    "publish-the-archive": "abandoned on purpose, with no landed_by",
    # Named by tests/test_self_architecture.py.
    "compass-self-architecture": "Compass's own architecture, loaded",
    # Shapes the sweeps must cover.
    "assess-before-edit-under-conflict": "a spike",
    "ci-lints-every-issue": "records a pre-rename routing id",
    "issue-overview": "a feature, one subtask, two review rounds",
    "loop-ceilings": "a multiagent feature under the loop ceilings",
    "headless-runner": "an initiative with intent and requirements review",
    "run-record-edges": "a quick fix",
    "accept-adr-030": "a quick fix from the newest CLI",
}

_SUBS = (
    # Worktrees first: they sit beside the project, under the same home.
    (re.compile(r"/Users/[^/\s\"'`]+/dev/\.compass-worktrees/[A-Za-z0-9._-]+"),
     "<project>"),
    (re.compile(r"/Users/[^/\s\"'`]+/dev/compass\b"), "<project>"),
    (re.compile(r"/(?:private/)?(?:tmp|var/folders)/[^\s\"'`]*"), "<tmp>"),
    (re.compile(r"/Users/[^/\s\"'`]+"), "~"),
    (re.compile(r"/home/[^/\s\"'`]+"), "~"),
    (re.compile(r"docs/(?:analysis|proposals)/[^\s\"'`)\]>,;]*"),
     "a private planning document"),
    (re.compile(r"\b(?:spec|Spec|PRD)\s[ABD]?\d{1,3}[a-z]?\b"), "a planning spec"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "<email>"),
    (re.compile(r"the R9 analysis"), "a private analysis"),
    (re.compile("\u2014"), "-"),
    (re.compile(r"\\u2014"), "-"),
)

#: Files that quote another product, replaced by a note. Each was a bug
#: report written from the companion proposal to an outside review of
#: Compass 3.2.0, and quotes its rules and examples.
WITHHELD = {
    f"docs/compass/{name}/bug-report.md": "it quoted the companion proposal "
    "to an outside review of Compass 3.2.0"
    for name in ("2026-08-21-the-human-review-pack",
                 "2026-08-23-the-terminal-output-contract",
                 "2026-08-23-the-human-front-door",
                 "2026-08-23-adaptive-artifact-composition")
}

_TEXT = {".md", ".yml", ".yaml", ".json", ".log", ".txt", ".feature", ".diff",
         ".py", ".sh", ""}


def scrub(text, name):
    if name:
        text = text.replace(name, GITHUB_USER)
    for pattern, replacement in _SUBS:
        text = pattern.sub(replacement, text)
    return redact(text, env={})


def _docs_dir(source, slug):
    manifest = load_yaml(str(source / ".compass" / "work" / slug / "manifest.yml"))
    created = str((manifest or {}).get("created") or "")[:10]
    found = source / "docs" / "compass" / f"{created}-{slug}"
    return found if found.is_dir() else None


def _copy(src, dst, name):
    for base, dirs, files in os.walk(src):
        dirs.sort()
        rel = Path(base).relative_to(src)
        for file_name in sorted(files):
            if file_name == ".DS_Store" or file_name.endswith(".pyc"):
                continue
            source = Path(base) / file_name
            target = dst / rel / file_name
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix in _TEXT:
                try:
                    text = source.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    shutil.copyfile(source, target)
                    continue
                target.write_text(scrub(text, name), encoding="utf-8")
            else:
                shutil.copyfile(source, target)


def _withhold(dest):
    for rel, why in sorted(WITHHELD.items()):
        path = dest / rel
        if path.is_file():
            path.write_text(f"# Withheld\n\nThis document is not in the "
                            f"archive sample: {why}. Compass does not quote "
                            f"another product in anything it commits.\n",
                            encoding="utf-8")


def _drop_land_commit(task_dir):
    path = task_dir / "manifest.yml"
    manifest = load_yaml(str(path))
    if isinstance(manifest, dict) and "land_commit" in manifest:
        del manifest["land_commit"]
        save_manifest(manifest, str(path))


def _valid_before(source_record_path):
    """Was the record's digest right before the scrub? Only such a record is
    restamped: one already wrong must stay wrong, so the check catches it."""
    try:
        record = json.loads(source_record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(record, dict) and \
        record.get("content_digest") == content_digest(record)


def _restamp(task_dir, source_dir):
    """Recompute the digest of every evidence record the scrub changed, and
    the manifest's copy of it."""
    evidence = task_dir / "evidence"
    changed = {}
    for record_path in sorted(evidence.glob("*.json")) if evidence.is_dir() else []:
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not isinstance(record, dict) or "content_digest" not in record:
            continue
        if not _valid_before(source_dir / "evidence" / record_path.name):
            continue
        digest = content_digest(record)
        if digest != record["content_digest"]:
            record["content_digest"] = digest
            record_path.write_text(json.dumps(record, indent=2) + "\n",
                                   encoding="utf-8")
            changed[f"evidence/{record_path.name}"] = digest
    if not changed:
        return
    path = task_dir / "manifest.yml"
    manifest = load_yaml(str(path))
    for entry in manifest.get("evidence") or []:
        if isinstance(entry, dict) and entry.get("path") in changed \
                and "content_digest" in entry:
            entry["content_digest"] = changed[entry["path"]]
    save_manifest(manifest, str(path))


def _git_user_name():
    found = subprocess.run(["git", "config", "user.name"], cwd=ROOT,
                           capture_output=True, text=True)
    return found.stdout.strip()


def _pack(folder, dest):
    """`folder` as a gzipped tar with fixed times and owners, so the same
    files always give the same bytes."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            info = tarfile.TarInfo(str(path.relative_to(folder)))
            data = path.read_bytes()
            info.size, info.mtime, info.mode = len(data), 0, 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename="") as gz:
            gz.write(raw.getvalue())


def build(source, dest, slugs, name):
    with tempfile.TemporaryDirectory() as work_dir:
        folder = Path(work_dir) / "sample"
        _build_folder(source, folder, slugs, name)
        _pack(folder, dest)
    print(f"build-archive-sample: {len(slugs)} issue(s) written to {dest}")


def _build_folder(source, dest, slugs, name):
    for slug in sorted(slugs):
        work = source / ".compass" / "work" / slug
        if not (work / "manifest.yml").is_file():
            raise SystemExit(f"build-archive-sample: no issue {slug} in "
                             f"{work.parent} - run it from a checkout that "
                             f"holds the archive.")
        target = dest / ".compass" / "work" / slug
        _copy(work, target, name)
        docs = _docs_dir(source, slug)
        if docs is not None:
            _copy(docs, dest / "docs" / "compass" / docs.name, name)
        _restamp(target, work)
        _drop_land_commit(target)
    _withhold(dest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=ROOT,
                        help="the project whose archive is copied (default: this one)")
    parser.add_argument("--dest", type=Path,
                        default=ROOT / "tests" / "fixtures" / "archive-sample.tar.gz",
                        help="the archive file written; replaced if present")
    parser.add_argument("--only", action="append",
                        help="copy only this issue (repeatable); default: SLUGS")
    parser.add_argument("--name", help="the name to replace with the GitHub "
                                       "username (default: git config user.name)")
    args = parser.parse_args(argv)
    name = args.name if args.name is not None else _git_user_name()
    build(args.source, args.dest, args.only or list(SLUGS), name)


if __name__ == "__main__":
    main()
