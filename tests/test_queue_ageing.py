"""The flow digest shows how long queued issues have waited, and flags the
old ones that carry a written recommendation or a guarded label: GitHub
issue #288.
"""
from __future__ import annotations

import datetime
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"


def _days_ago(n: int) -> str:
    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()


def _queued(root: Path, slug: str, age: int, labels=(), heading=None, status="queued"):
    work = root / ".compass" / "work" / slug
    work.mkdir(parents=True)
    created = _days_ago(age)
    (work / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": slug, "created": created, "status": status,
        "assessment": {"labels": list(labels)}, "artifacts": []}), encoding="utf-8")
    if heading:
        docs = root / "docs" / "compass" / f"{created}-{slug}"
        docs.mkdir(parents=True)
        (docs / "bug-report.md").write_text(f"# {slug}\n\n## {heading}\n\nText.\n")


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    _queued(root, "old-with-a-recommendation", 40, heading="Recommendation")
    _queued(root, "old-with-a-guarded-label", 30, labels=["auth"])
    _queued(root, "old-and-plain", 50)
    _queued(root, "young-with-a-recommendation", 3, heading="Proposed fix")
    _queued(root, "active-one", 60, heading="Recommendation", status="active")
    return root


def _digest(root: Path) -> str:
    r = subprocess.run([sys.executable, str(CLI), "flow", "--digest"], cwd=root,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def test_the_digest_lists_queued_issues_by_age(project):
    out = _digest(project)
    table = out.split("## Queue age", 1)[1].split("\n## ", 1)[0]
    order = [s for s in ("old-and-plain", "old-with-a-recommendation",
                         "old-with-a-guarded-label", "young-with-a-recommendation")
             if s in table]
    assert order == ["old-and-plain", "old-with-a-recommendation",
                     "old-with-a-guarded-label", "young-with-a-recommendation"]
    assert "| 40 |" in table and "| 3 |" in table
    assert "active-one" not in table, "only queued issues"


def test_the_top_line_flags_old_issues_with_a_signal(project):
    out = _digest(project)
    top = out.split("## ", 1)[0]
    assert "old-with-a-recommendation (40 days, recommendation)" in top
    assert "old-with-a-guarded-label (30 days, label auth)" in top
    assert "old-and-plain" not in top, "no signal, no flag"
    assert "young-with-a-recommendation" not in top, "under the threshold"


def test_an_empty_queue_says_so(tmp_path):
    root = tmp_path / "proj"
    (root / ".compass" / "work").mkdir(parents=True)
    out = _digest(root)
    assert "No queued issues." in out


def test_the_release_guide_asks_about_the_queue():
    text = (ROOT / "docs" / "releasing.md").read_text(encoding="utf-8")
    assert "Queued against this release" in text
    assert "compass flow --digest" in text
