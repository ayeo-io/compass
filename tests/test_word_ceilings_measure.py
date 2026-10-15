"""The regular design size measure of scripts/measure-artifact-catalogue.py.

`--design-size` reports, per delivery approach, how many technical designs an
archive copy holds and their median size in bytes. The tests run it on a
tracked fixture archive, because CI has no archive of its own.

Scenario ids: see docs/system-spec.md.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "measure-artifact-catalogue.py"
FIXTURE = ROOT / "tests" / "fixtures" / "design-size-archive"
REGULAR_LIMIT = 3865
ISSUE = "word-ceilings-and-lld"

# The designs of the fixture, by issue: (approach, size in bytes, on a catalogue
# that lists Data and interfaces). reg-b registers its design at a path of its own.
EXPECTED = {
    "reg-a": ("regular", False),
    "reg-b": ("regular", False),
    "reg-c": ("regular", False),
    "reg-d": ("regular", True),
    "reg-e": ("regular", True),
    "full-a": ("full", False),
    "full-b": ("full", False),
}
DESIGN_FILES = {
    "reg-b": "design-alt.md",
}


def _median(sizes):
    ordered = sorted(sizes)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) // 2


def _design_size(copy: pathlib.Path, slug: str) -> int:
    folder = next((copy / "docs" / "compass").glob("*-%s" % slug))
    return (folder / DESIGN_FILES.get(slug, "technical-design.md")).stat().st_size


def _digest(tree: pathlib.Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in tree.rglob("*") if p.is_file()):
        h.update(str(path.relative_to(tree)).encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def _run(root: pathlib.Path, *extra: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--design-size", "--json", *extra],
        capture_output=True, text=True)


def test_wcl_21_measure_script_fixture(tmp_path):
    copy = tmp_path / "archive"
    shutil.copytree(FIXTURE, copy)
    before = _digest(copy)

    first, second = _run(copy), _run(copy)
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.stdout == second.stdout
    out = json.loads(first.stdout)

    sizes = {slug: _design_size(copy, slug) for slug in EXPECTED}
    regular = [sizes[s] for s, (a, _) in EXPECTED.items() if a == "regular"]
    full = [sizes[s] for s, (a, _) in EXPECTED.items() if a == "full"]
    new = [sizes[s] for s, (a, n) in EXPECTED.items() if a == "regular" and n]
    assert len(regular) == 5 and len(full) == 2 and len(new) == 2

    assert out["approaches"]["regular"] == {"count": 5, "median_bytes": _median(regular)}
    assert out["approaches"]["full"] == {"count": 2, "median_bytes": _median(full)}
    assert out["approaches"]["full"]["median_bytes"] == 6000  # the mean 6000.5, rounded down
    assert out["regular_limit"] == REGULAR_LIMIT
    assert out["regular_within_limit"] is (_median(regular) <= REGULAR_LIMIT)
    assert out["regular_new_catalogue"] == {"count": 2, "median_bytes": _median(new)}
    assert out["issues"]["regular"] == sorted(s for s, (a, _) in EXPECTED.items() if a == "regular")
    assert out["issues"]["full"] == ["full-a", "full-b"]

    assert _digest(copy) == before, "the measure changed the copy"

    # A root that holds .git is a working checkout: refuse it and say to use a copy.
    (copy / ".git").mkdir()
    refused = _run(copy)
    assert refused.returncode == 2
    assert "copy" in refused.stderr
    assert refused.stdout == ""


def _measure_evidence():
    manifest = ROOT / ".compass" / "work" / ISSUE / "manifest.yml"
    if not manifest.is_file():
        return None, None
    from compass_pkg.core import load_yaml
    data = load_yaml(str(manifest))
    for item in data.get("evidence") or []:
        if not isinstance(item, dict) or item.get("type") != "command-output":
            continue
        path = (manifest.parent / str(item.get("path") or "")).resolve()
        try:
            figures = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(figures, dict) and "regular_limit" in figures:
            return data, figures
    return data, None


def test_wcl_22_regular_median_reported():
    sys.path.insert(0, str(ROOT / "cli"))
    data, figures = _measure_evidence()
    if figures is None:
        pytest.skip("no command-output evidence of the size measure here: CI has no archive")
    regular = figures["approaches"]["regular"]
    assert regular["median_bytes"] <= REGULAR_LIMIT
    report = ROOT / "docs" / "compass" / ("%s-%s" % (data["created"], ISSUE)) / "verification-report.md"
    assert str(regular["count"]) in report.read_text(encoding="utf-8")
