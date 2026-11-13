"""A reassess that leaves the approach unchanged keeps the reason it was given.

`compass approach evaluate --write --reason "..."` printed that the reason was
NOT recorded when nothing computed had changed, so a reassess made for a reason
(a fixed configuration, a new catalogue) left no evidence in the manifest. It
now appends a `reassessments` entry of kind `unchanged`: no one misread the
work.

Scenario id: `TRC-001` in unchanged-reassess-records-reason/acceptance-criteria.md
"""
from __future__ import annotations

import datetime
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "cli" / "compass"

BASE = """schema_version: "2.0"
issue: sample
created: "2026-08-30"
status: active
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: small
  goal: delivery
  urgency: none
  role: engineer
  labels: []
evidence: []
gates: []
scenarios: []
changed_files: []
claims: []
follow_ups: []
reassessments: []
"""


def _project(tmp: Path) -> Path:
    work = tmp / ".compass" / "work" / "sample"
    work.mkdir(parents=True)
    (tmp / ".compass" / "config.yml").write_text("version: 1.0.0\n", encoding="utf-8")
    (work / "manifest.yml").write_text(BASE, encoding="utf-8")
    return tmp


def _run(project: Path, *args):
    r = subprocess.run([sys.executable, str(CLI), *args], cwd=str(project),
                       capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout, r.stderr


def _manifest(project: Path) -> dict:
    path = project / ".compass" / "work" / "sample" / "manifest.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _evaluated(project: Path) -> None:
    code, out, err = _run(project, "approach", "evaluate", "--issue", "sample", "--write")
    assert code == 0, out + err


def test_trc_001_an_unchanged_reassess_with_a_reason_is_recorded():
    with tempfile.TemporaryDirectory() as raw:
        project = _project(Path(raw))
        _evaluated(project)
        code, out, err = _run(project, "approach", "evaluate", "--issue", "sample",
                              "--write", "--reason", "the catalogue was fixed")
        assert code == 0, out + err
        entries = _manifest(project)["reassessments"]
    assert "RE-ASSESSMENT recorded (unchanged)" in out, out
    assert "was NOT recorded" not in out, out
    assert "no reason" not in err, err
    assert len(entries) == 1, entries
    entry = entries[0]
    assert entry["kind"] == "unchanged"
    assert entry["from_route"] == entry["to_route"] and entry["from_route"]
    assert entry["changed"] == {}
    assert entry["reason"] == "the catalogue was fixed"
    assert entry["date"] == datetime.date.today().isoformat()
    assert entry["generation"]["from"] == entry["generation"]["to"]


def test_trc_001_an_unchanged_reassess_without_a_reason_writes_nothing():
    with tempfile.TemporaryDirectory() as raw:
        project = _project(Path(raw))
        _evaluated(project)
        code, out, err = _run(project, "approach", "evaluate", "--issue", "sample",
                              "--write")
        assert code == 0, out + err
        entries = _manifest(project)["reassessments"]
    assert entries == [], entries
    assert "no reason" not in err, err
    assert "RE-ASSESSMENT" not in out, out


def test_trc_001_a_manifest_with_the_entry_passes_lint():
    with tempfile.TemporaryDirectory() as raw:
        project = _project(Path(raw))
        _evaluated(project)
        _run(project, "approach", "evaluate", "--issue", "sample", "--write",
             "--reason", "the catalogue was fixed")
        code, out, err = _run(project, "issue", "lint", "--issue", "sample")
    assert code == 0, out + err


def test_a_person_cannot_label_a_real_change_unchanged():
    """The CLI assigns `unchanged` itself, so `--kind unchanged` is refused.

    A real route change labelled `unchanged` would read as no one having
    misread the work, hiding a true re-assessment.

    Scenario id: `TRC-001` in unchanged-reassess-records-reason/acceptance-criteria.md
    """
    with tempfile.TemporaryDirectory() as raw:
        project = _project(Path(raw))
        _evaluated(project)
        path = project / ".compass" / "work" / "sample" / "manifest.yml"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "size: small", "size: large"), encoding="utf-8")
        code, out, err = _run(project, "approach", "evaluate", "--issue", "sample",
                              "--write", "--reason", "grew", "--kind", "unchanged")
        entries = _manifest(project)["reassessments"]
    assert code != 0, out + err
    assert "unchanged" in err, err
    assert entries == [], entries
