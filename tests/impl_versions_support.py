"""Shared set-up for the tests of implementation versions (`impl-refusal`).

A scratch project whose issue holds generation 1, and a way to rewrite what
that generation recorded, as a release with older versions would have stored
it.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
SLUG = "feature"

MANIFEST = {
    "schema_version": "2.0", "issue": SLUG, "created": "2026-10-07", "status": "active",
    "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                   "size": "standard", "goal": "delivery", "role": "engineer",
                   "labels": []},
    "evidence": [],
}


def _run(cwd, *argv):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(cwd),
           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "100",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    r = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=env,
                       capture_output=True, text=True, timeout=180)
    return r.returncode, r.stdout, r.stderr


@pytest.fixture
def committed(tmp_path):
    """A scratch project whose issue holds generation 1, and the issue's directory."""
    task_dir = tmp_path / ".compass" / "work" / SLUG
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(MANIFEST, sort_keys=False),
                                           encoding="utf-8")
    code, out, err = _run(tmp_path, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    return tmp_path, task_dir


def record_versions(task_dir, n=1, implementations=None, **top):
    """Rewrite what generation n recorded in `versions.yml`, and the marker's
    digest of it, so the generation is still whole."""
    from compass_pkg.atomic_io import digest
    folder = task_dir / "generations" / str(n)
    path = folder / "versions.yml"
    versions = yaml.safe_load(path.read_text(encoding="utf-8"))
    versions.update(top)
    versions["implementations"].update(implementations or {})
    path.write_text(yaml.safe_dump(versions, sort_keys=False), encoding="utf-8")
    marker = yaml.safe_load((folder / "complete").read_text(encoding="utf-8"))
    marker["files"]["versions.yml"] = digest(versions)
    (folder / "complete").write_text(yaml.safe_dump(marker, sort_keys=False),
                                     encoding="utf-8")
