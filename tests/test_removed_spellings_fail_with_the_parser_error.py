"""A removed spelling is refused by the parser (release-7-0-0-prep, group A).

Each of the 7 alias spellings that 7.0.0 removed exits 2 and prints no alias
notice. Each of the 9 spellings no release held prints no `is now '` hint.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"

MANIFEST = (
    "schema_version: '3.0'\n"
    "issue: sample\n"
    "created: '2026-10-08'\n"
    "assessment:\n"
    "  risk: contained\n"
    "  familiarity: brownfield-mapped\n"
    "  size: atomic\n"
    "  goal: delivery\n"
    "  urgency: none\n"
    "  role: engineer\n"
    "  labels: []\n"
    "evidence: []\ngates: []\nscenarios: []\nchanged_files: []\n"
    "claims: []\nfollow_ups: []\nreassessments: []\n")

# The arguments a 6.x script gave each removed alias spelling.
REMOVED = [
    ["approach", "summary"],
    ["issue", "set-status", "active", "--issue", "sample"],
    ["policy", "review-rules", "--changed-files", "cli/compass"],
    ["issue", "artifact", "intent", "--status", "draft"],
    ["migrate"],
    ["issue", "subtask", "update", "s1", "--status", "done"],
    ["run", "multi", "--stage", "build", "--stop-file", "S"],
]

# Spellings no release held; each had a hint row before 7.0.0.
UNRELEASED = [
    ["policy", "effective"],
    ["policy", "test"],
    ["policy", "init-preset"],
    ["approach", "diagram"],
    ["issue", "refresh-spec"],
    ["issue", "migrate-config"],
    ["issue", "template", "requirements-review"],
    ["scenario", "tests", "SCN-1", "--test", "tests/x.py::t"],
    ["issue", "friction", "--category", "tooling", "--phase", "assess", "--observed",
     "evidence/red.log", "--fix", "Run the suite once"],
]


def _project(path: Path) -> Path:
    work = path / ".compass" / "work" / "sample"
    work.mkdir(parents=True)
    shutil.copytree(ROOT / "governance", path / "governance")
    shutil.copytree(ROOT / "schemas", path / "schemas")
    (path / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n", encoding="utf-8")
    (work / "manifest.yml").write_text(MANIFEST, encoding="utf-8")
    (path / ".compass" / "current-task").write_text("sample", encoding="utf-8")
    return path


def _run(args, cwd):
    env = dict(os.environ)
    env.pop("COMPASS_ISSUE", None)
    proc = subprocess.run([sys.executable, str(CLI), *args], cwd=str(cwd),
                          capture_output=True, text=True, env=env, timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


@pytest.mark.parametrize("argv", REMOVED, ids=[" ".join(a[:3]) for a in REMOVED])
def test_a_removed_spelling_exits_2(tmp_path, argv):
    """Scenario id: `TRC-006` in release-7-0-0-prep/acceptance-criteria.md"""
    project = _project(tmp_path / "p")
    rc, out, err = _run(argv, project)
    assert rc == 2, (rc, out, err)
    # The parser refuses a removed verb. `run` takes the stage as a free
    # word, so its own check refuses `build`, with the same exit code.
    assert "invalid choice" in err or "cannot run unattended" in err, err
    assert out == "", out


@pytest.mark.parametrize("argv", REMOVED, ids=[" ".join(a[:3]) for a in REMOVED])
def test_a_removed_spelling_prints_no_alias_notice(tmp_path, argv):
    """Scenario id: `TRC-007` in release-7-0-0-prep/acceptance-criteria.md"""
    project = _project(tmp_path / "p")
    rc, out, err = _run(argv, project)
    assert rc == 2, (rc, out, err)
    assert not [l for l in err.splitlines() if "works until 7.0.0" in l], err
    assert "is now '" not in err, err


@pytest.mark.parametrize("argv", UNRELEASED, ids=[" ".join(a[:3]) for a in UNRELEASED])
def test_an_unreleased_spelling_prints_no_is_now_line(tmp_path, argv):
    """Scenario id: `TRC-011` in release-7-0-0-prep/acceptance-criteria.md"""
    project = _project(tmp_path / "p")
    rc, out, err = _run(argv, project)
    assert rc == 2, (rc, out, err)
    assert "is now '" not in err, err
