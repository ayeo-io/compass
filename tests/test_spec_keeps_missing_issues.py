"""Deriving the living spec refuses, and names the issue, when the committed
spec names an issue that is missing from the local archive, instead of
dropping its scenarios: GitHub issue #289.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"


def _derive(root: Path):
    return subprocess.run([sys.executable, str(CLI), "_derive-system-spec", "--internal"],
                          cwd=root, capture_output=True, text=True)


def _landed(root: Path, slug: str, sid: str, when: str) -> None:
    work = root / ".compass" / "work" / slug
    work.mkdir(parents=True)
    (work / "manifest.yml").write_text(
        f"schema_version: '2.0'\nissue: {slug}\ncreated: '2026-10-01'\nstatus: landed\n"
        f"land_timestamp: '{when}'\nscenarios:\n- id: {sid}\n"
        f"  title: Given {slug}, then it works\n  intent: INT-{sid}\n", encoding="utf-8")


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / ".compass").mkdir()
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    _landed(root, "first-issue", "A1", "2026-10-01T10:00:00+00:00")
    _landed(root, "second-issue", "B1", "2026-10-01T11:00:00+00:00")
    return root


def _spec_text(root: Path) -> str:
    return "".join((root / "docs" / name).read_text(encoding="utf-8")
                   for name in ("system-spec.md", "system-spec-archive.md")
                   if (root / "docs" / name).is_file())


def test_a_first_derivation_writes_the_spec(tmp_path):
    root = _project(tmp_path)
    r = _derive(root)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "### second-issue (completed" in _spec_text(root)


def test_a_missing_issue_is_refused_and_named(tmp_path):
    root = _project(tmp_path)
    assert _derive(root).returncode == 0
    before = _spec_text(root)
    import shutil
    shutil.rmtree(root / ".compass" / "work" / "second-issue")
    r = _derive(root)
    assert r.returncode != 0
    assert "second-issue" in r.stdout + r.stderr
    assert _spec_text(root) == before, "the spec files are left as they were"


def test_an_unchanged_archive_derives_again(tmp_path):
    root = _project(tmp_path)
    assert _derive(root).returncode == 0
    r = _derive(root)
    assert r.returncode == 0, r.stdout + r.stderr
