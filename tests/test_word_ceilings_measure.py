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
import re
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "measure-artifact-catalogue.py"
FIXTURE = ROOT / "tests" / "fixtures" / "design-size-archive"
REGULAR_LIMIT = 3865
ISSUE = "word-ceilings-and-lld"

# The designs of the fixture, by issue: (approach, on a catalogue that lists
# Data and interfaces). reg-b registers its design at a path of its own.
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
    shutil.rmtree(copy / ".git")

    # Regular designs past the limit read as not within it.
    for slug, (approach, _) in EXPECTED.items():
        if approach == "regular":
            folder = next((copy / "docs" / "compass").glob("*-%s" % slug))
            design = folder / DESIGN_FILES.get(slug, "technical-design.md")
            design.write_text(design.read_text(encoding="utf-8") + "x" * REGULAR_LIMIT,
                              encoding="utf-8")
    grown = json.loads(_run(copy).stdout)
    assert grown["regular_within_limit"] is False

    # A registered design that is missing on disk leaves its issue out: there is
    # no fall back to the default filename.
    folder = next((copy / "docs" / "compass").glob("*-reg-b"))
    (folder / "design-alt.md").unlink()
    (folder / "technical-design.md").write_text("# not the registered design\n", encoding="utf-8")
    missing = json.loads(_run(copy).stdout)
    assert "reg-b" not in missing["issues"]["regular"]
    assert missing["approaches"]["regular"]["count"] == 4


#: The regular count the size limit was set on, on 10 October 2026.
BASELINE_COUNT = 38


def _measure_evidence():
    """The manifest and the figures of the latest command-output record that holds
    the measure's output, so that a later re-run is the one judged."""
    manifest = ROOT / ".compass" / "work" / ISSUE / "manifest.yml"
    if not manifest.is_file():
        return None, None
    from compass_pkg.core import load_yaml
    data = load_yaml(str(manifest))
    for item in reversed(data.get("evidence") or []):
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


def test_wcl_22_regular_median_reported(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "cli"))
    data, figures = _measure_evidence()
    if figures is None:
        pytest.skip("no command-output evidence of the size measure here: CI has no archive")
    regular = figures["approaches"]["regular"]
    assert regular["median_bytes"] <= REGULAR_LIMIT
    report = ROOT / "docs" / "compass" / ("%s-%s" % (data["created"], ISSUE)) / "verification-report.md"
    text = report.read_text(encoding="utf-8")
    # The count must be stated as a count of regular issues, not found as a digit
    # run inside another figure such as the limit 3865.
    stated = re.compile(r"(?<![\d,])%d(?![\d,])\s+regular\s+(?:issues|designs)" % regular["count"])
    assert stated.search(text), "the report does not state the count of regular issues"
    if regular["count"] != BASELINE_COUNT:
        # The report must name the issues that explain the difference.
        assert "since 10 October 2026" in text, (
            "the count differs from %d and the report names no issue added or removed"
            % BASELINE_COUNT)
