"""Scenarios ACF-1 to ACF-63 of the issue `artifact-catalogue-fields`.

Each test is named for its scenario id, as the manifest declares
(`tests/test_artifact_catalogue_fields.py::test_acf_<n>`). The scenarios are
in `docs/compass/2026-10-12-artifact-catalogue-fields/acceptance-criteria.md`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

FIXTURES = ROOT / "tests" / "fixtures" / "artifact-catalogue-fields"
MEASURE = ROOT / "scripts" / "measure-artifact-catalogue.py"
#: The catalogue as it was before this issue changed it: twelve kinds.
CATALOGUE_BEFORE = FIXTURES / "artifacts-before.yml"
#: The undeclared kind names the 6.x migrate lists on the archive copy.
AD_HOC_KINDS = ROOT / "tests" / "fixtures" / "ad-hoc-kinds.txt"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _issue(root, slug, created, approach, subtasks=None, registered=(), beside=(),
           documents=()):
    """One issue in a scratch archive: its manifest, the files beside it and
    the files in its documents folder."""
    manifest = {"schema_version": "3.0", "issue": slug, "created": created,
                "delivery_approach": approach}
    if subtasks is not None:
        manifest["subtasks"] = [{"id": f"subtask-{i}"} for i in range(1, subtasks + 1)]
    if registered:
        manifest["artifacts"] = [{"id": f"ART-{k.upper()}", "kind": k, "status": "draft",
                                  "path": f"docs/compass/{created}-{slug}/{k}.md"}
                                 for k in registered]
    work = root / ".compass" / "work" / slug
    _write(work / "manifest.yml", yaml.safe_dump(manifest))
    for name in beside:
        _write(work / name, f"# {name}\n")
    for name in documents:
        _write(root / "docs" / "compass" / f"{created}-{slug}" / name, f"# {name}\n")


def _measure(root, *extra):
    run = subprocess.run(
        [sys.executable, str(MEASURE), "--root", str(root),
         "--catalogue", str(CATALOGUE_BEFORE), "--json", *extra],
        capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_acf_52(tmp_path):
    # A small archive with a known answer for every figure.
    scratch = tmp_path / "scratch"
    _issue(scratch, "alpha", "2026-10-01", "regular", subtasks=0, beside=["design.md"],
           documents=["delivery-approach.md", "distribution-map.md", "review-1.md"])
    _issue(scratch, "beta", "2026-10-02", "regular", subtasks=2,
           registered=["bug-report"], documents=["distribution-map.md", "review-claims.md"])
    _issue(scratch, "gamma", "2026-10-03", "quick-fix", beside=["security-review.md"])
    found = _measure(scratch)
    assert found == {
        "kinds_declared": 12,
        "undeclared_kinds": 5,           # design, review-1, review-claims,
        "regular_issues": 2,             # security-review and bug-report
        "regular_with_record": 1,
        "regular_with_stub_map": 1,
        "review_filenames": 3,
    }
    # The measure only reads: nothing under the scratch archive changed.
    assert not list(scratch.rglob("*.v6.bak"))

    # The maintainer's archive copy, read only with the switch on, from a
    # throwaway copy so the run cannot touch the real folders.
    if os.environ.get("COMPASS_FULL_ARCHIVE") != "1":
        return
    copy = tmp_path / "archive-copy"
    shutil.copytree(ROOT / ".compass" / "work", copy / ".compass" / "work")
    shutil.copytree(ROOT / "docs" / "compass", copy / "docs" / "compass")
    names = [n for n in AD_HOC_KINDS.read_text(encoding="utf-8").splitlines() if n]
    listed = tmp_path / "kinds.txt"
    full = _measure(copy, "--list-kinds", str(listed))
    assert listed.read_text(encoding="utf-8").splitlines() == sorted(names)
    assert (full["kinds_declared"], full["undeclared_kinds"]) == (12, len(names))
    # 1 and 34 are the figures recorded on 2026-10-12. The copy holds one more
    # regular issue than the 40 the spec counted that day; it adds to neither.
    assert (full["regular_with_record"], full["regular_with_stub_map"],
            full["regular_issues"]) == (1, 34, 41)
    assert full["review_filenames"] > 25
