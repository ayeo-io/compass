"""The reports across issues that 9.0.0 removed, and what stays (ADR-093).

`compass retro` and its views, `compass rework-scan`, `compass issue friction`
and the private `_friction-capture` are gone. A command line that names one
fails to parse, exits 2 and names the removal; the private verb gets no line.
`compass follow-up resolve` moved with its function and still resolves a
follow-up, and a manifest that holds `friction:` still lints.

Issue: #354 [Remove role entry points, the board, retro reporting, evals and the
Codex adapter].
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))


def _run(args, cwd):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=60)


REMOVED = {
    ("retro",): "compass retro",
    ("retro", "--impact"): "compass retro",
    ("retro", "--lineage"): "compass retro",
    ("rework-scan", "--format", "json"): "compass rework-scan",
    ("issue", "friction", "--category", "tooling"): "compass issue friction",
}


@pytest.mark.parametrize("argv", sorted(REMOVED), ids=" ".join)
def test_a_removed_report_names_its_removal(tmp_path, argv):
    proc = _run(list(argv), tmp_path)
    assert proc.returncode == 2, proc.stderr
    assert proc.stdout == "", proc.stdout
    assert f"'{REMOVED[argv]}' was removed in 9.0.0 (ADR-093)" in proc.stderr, proc.stderr
    assert "Compass keeps only what a reviewer of one change needs" in proc.stderr


def test_retro_models_keeps_its_own_removal_line(tmp_path):
    proc = _run(["retro", "--models"], tmp_path)
    assert proc.returncode == 2
    assert "'compass retro --models' was removed in 9.0.0 (ADR-090)" in proc.stderr


def test_the_private_friction_capture_gets_no_removal_line(tmp_path):
    proc = _run(["_friction-capture", "--internal"], tmp_path)
    assert proc.returncode == 2
    assert "removed in 9.0.0" not in proc.stderr, proc.stderr


def _project(tmp_path):
    work = tmp_path / ".compass" / "work" / "t"
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n", encoding="utf-8")
    manifest = {
        "schema_version": "2.0", "issue": "t", "created": "2026-10-01", "status": "active",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "small", "goal": "delivery"},
        "evidence": [], "gates": [], "scenarios": [],
        "follow_ups": [{"id": "FU-1", "status": "outstanding", "summary": "owed"}],
        "friction": [{"stage": "build", "category": "tooling", "source": "human",
                      "observation": "the fixture was slow"}],
    }
    (work / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False),
                                       encoding="utf-8")
    return tmp_path, work / "manifest.yml"


def test_follow_up_resolve_still_resolves_a_follow_up(tmp_path):
    root, path = _project(tmp_path)
    proc = _run(["follow-up", "resolve", "--issue", "t", "FU-1"], root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "'FU-1' in issue 't' marked resolved" in proc.stdout, proc.stdout
    [entry] = yaml.safe_load(path.read_text(encoding="utf-8"))["follow_ups"]
    assert entry["status"] == "resolved"
    from compass_pkg import follow_up_cmd, record_triggers
    assert "cmd_backfill_pay" in record_triggers.RECORD_TRIGGERS
    assert callable(follow_up_cmd.cmd_backfill_pay)


def test_an_old_friction_key_still_lints_and_nothing_writes_one(tmp_path):
    root, path = _project(tmp_path)
    proc = _run(["issue", "lint", "--issue", "t"], root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    template = yaml.safe_load((ROOT / "templates" / "manifest.yml").read_text(encoding="utf-8"))
    assert "friction" not in template
    import json
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    assert "friction" in schema["properties"]
