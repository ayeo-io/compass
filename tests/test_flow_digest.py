"""Flow digest tests - `TRC-F4`.

- `TRC-F4`: Flow advises, never gates. Snapshot SHA256 of every manifest.yml
  before/after running `compass flow --digest`; assert byte-identity.
- The digest lists the backlog and nothing else: 9.0.0 removed its rework and
  calibration sections with `compass rework-scan` and `compass retro`
  (ADR-093). `TRC-D5` and `TRC-C6` were those sections.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict

import yaml

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = FRAMEWORK_ROOT / "cli" / "compass"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_of_file(path: Path) -> str:
    """Return the hex SHA256 digest of a file's contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_task_ymls(compass_work_dir: Path) -> Dict[str, str]:
    """Return {relative_path: sha256} for every manifest.yml under compass_work_dir."""
    snapshots: Dict[str, str] = {}
    if not compass_work_dir.is_dir():
        return snapshots
    for task_yml in sorted(compass_work_dir.rglob("manifest.yml")):
        rel = str(task_yml.relative_to(compass_work_dir))
        snapshots[rel] = _sha256_of_file(task_yml)
    return snapshots


def write_task_yml(directory: Path, slug: str, changed_files: list,
                   created: str = "2026-05-01") -> None:
    """Write a minimal manifest.yml for testing."""
    directory.mkdir(parents=True, exist_ok=True)
    data = {
        "slug": slug,
        "delivery_approach": "standard",
        "status": "landed",
        "created": created,
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "standard",
            "intent": "delivery",
            "role": "engineer",
        },
        "changed_files": changed_files,
    }
    with (directory / "manifest.yml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def run_subprocess_cli(*args, cwd=None, env_extra=None) -> subprocess.CompletedProcess:
    """Run the compass CLI via subprocess in an isolated cwd."""
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or FRAMEWORK_ROOT),
        env=env,
    )


# ---------------------------------------------------------------------------
# `TRC-F4` - Advisory commands must not mutate manifest.yml
# ---------------------------------------------------------------------------

def test_does_not_mutate_tasks(run_cli, make_task, project):
    """`TRC-F4`: Flow still advises, never gates.

    Given multiple issues exist in .compass/work/
    When compass flow --digest runs (the advisory digest)
    Then no manifest.yml under .compass/work/ is changed (byte-identical after)
    And no issue is automatically reassessed, downgraded, or blocked.

    This tests `Inv-4` (Flow advises; it never gates or mutates): Flow reads
    disk and reports; it does not write issue state, does not block, does
    not reassess.
    """
    compass_work = project / ".compass" / "work"

    # --- Given: set up multiple issues with varying reassessment states -----
    # Issue with no reassessments - the digest must report and not change it.
    make_task("alpha-task", {
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "standard",
            "intent": "delivery",
        },
        "delivery_approach": "standard",
        "scenarios": [{"id": "SCN-001", "intent": "INT-1", "tests": ["tests/t.py::t"]}],
        "reassessments": [],
        "changed_files": [],
    }, set_current=False)

    # Issue with a reassessment - the digest must not change it.
    make_task("beta-task", {
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
            "intent": "delivery",
        },
        "delivery_approach": "standard",
        "scenarios": [{"id": "SCN-002", "intent": "INT-1", "tests": ["tests/t.py::t"]}],
        "reassessments": [
            {"from_route": "express", "to_route": "standard",
             "reason": "needed more ceremony", "date": "2026-05-23"},
        ],
        "changed_files": [],
    }, set_current=False)

    # --- Snapshot before advisory command -----------------------------------
    before = _snapshot_task_ymls(compass_work)
    assert before, "No manifest.yml found before the digest - test setup failed"

    # --- When: run the advisory command -------------------------------------
    r = run_cli("flow", "--digest")
    # the digest always exits 0 (it is advisory, not a gate)
    assert r.returncode == 0, (
        f"compass flow --digest should exit 0 (advisory). Got {r.returncode}.\n"
        f"stdout: {r.stdout}\nstderr: {r.stderr}"
    )

    # --- Then: manifests must be byte-identical after -----------------------
    after = _snapshot_task_ymls(compass_work)

    assert before == after, (
        "Advisory command 'compass flow --digest' mutated manifest.yml files - "
        "this violates Inv-4 (Flow advises, never gates). "
        "Changed files:\n" + "\n".join(
            f"  {k}: before={before[k][:8]}... after={after[k][:8]}..."
            for k in set(before) | set(after)
            if before.get(k) != after.get(k)
        )
    )


def test_digest_does_not_write_to_work_dir(run_cli, make_task, project):
    """`TRC-F4` (supplementary): the digest must not create NEW files in
    .compass/work/ - any output must go to .compass/flow/ or stdout only.
    """
    compass_work = project / ".compass" / "work"

    make_task("gamma-task", {
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "standard",
            "intent": "delivery",
        },
        "delivery_approach": "standard",
        "reassessments": [],
        "changed_files": [],
    }, set_current=False)

    def _all_files_in(d: Path):
        return {str(p.relative_to(d)) for p in d.rglob("*") if p.is_file()}

    before_files = _all_files_in(compass_work)

    r = run_cli("flow", "--digest")
    assert r.returncode == 0, r

    after_files = _all_files_in(compass_work)
    new_files = after_files - before_files
    assert not new_files, (
        "compass flow --digest created new files under .compass/work/ - "
        "advisory output must go to stdout or .compass/flow/, not work/.\n"
        f"New files: {sorted(new_files)}"
    )


# ---------------------------------------------------------------------------
# The digest holds the backlog and no rework or calibration section
# ---------------------------------------------------------------------------

def test_digest_holds_the_backlog_and_no_removed_section(tmp_path):
    work_root = tmp_path / "work"
    write_task_yml(work_root / "task-adds", "task-adds", [
        {"path": "services/foo/handler.go", "action": "added"},
    ], created="2026-05-01")
    write_task_yml(work_root / "task-removes", "task-removes", [
        {"path": "services/foo/handler.go", "action": "deleted"},
    ], created="2026-05-05")

    proc = run_subprocess_cli("flow", "--digest", "--work-root", str(work_root),
                              cwd=tmp_path)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    output = proc.stdout
    assert output.startswith("# Flow digest - "), output
    assert "Advisory only" in output, output
    for removed in ("rework", "calibration", "compass retro"):
        assert removed not in output.lower(), (removed, output)
