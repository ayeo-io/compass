"""The `policy:` block each generation commit writes into the manifest (ADR-094).

A generation (`generations/<n>/`) is the stored copy of the policy an issue runs
against. #356 keeps the generation folders out of the commit, so the manifest
also names the policy: the check set's id and version, the sha256 of the check
set file and of `compass.yml`, the tighten-only settings applied, and the
digest of the stored `resolved.yml`. These tests run the real CLI on a scratch
project and read the files back:

- assess (`approach evaluate --write`) writes the block, and a re-assess writes
  it again, for a new generation and for one that did not move;
- the two `*_sha256` values equal what `sha256sum` prints for the two files;
- `resolved` equals the digest the generation's `complete` marker holds;
- a manifest written before 9.0.0, with no block, still checks and lints.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
CHECK_SET = ROOT / "governance" / "check-set.yml"
SLUG = "feature"

MANIFEST = {
    "schema_version": "2.0", "issue": SLUG, "created": "2026-10-07", "status": "active",
    "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                   "size": "medium", "goal": "delivery", "urgency": "none",
                   "labels": []},
    "evidence": [],
}


def _env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "100",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def _run(cwd, *argv):
    r = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=_env(cwd),
                       capture_output=True, text=True, timeout=180)
    return r.returncode, r.stdout, r.stderr


def _project(tmp_path, compass_yml=None):
    (tmp_path / ".compass").mkdir()
    task_dir = tmp_path / ".compass" / "work" / SLUG
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(MANIFEST, sort_keys=False),
                                           encoding="utf-8")
    if compass_yml is not None:
        (tmp_path / "compass.yml").write_text(compass_yml, encoding="utf-8")
    return tmp_path, task_dir


def _manifest(task_dir):
    return yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))


def _sha256sum(path):
    """What `sha256sum` prints for the file, or hashlib's digest where the tool is
    missing."""
    tool = shutil.which("sha256sum")
    if tool:
        out = subprocess.run([tool, str(path)], capture_output=True, text=True, check=True)
        return out.stdout.split()[0]
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _marker_digest(task_dir, n):
    marker = yaml.safe_load((task_dir / "generations" / str(n) / "complete")
                            .read_text(encoding="utf-8"))
    return marker["files"]["resolved.yml"]


def _assess(root):
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write",
                          "--reason", "a test")
    assert code == 0, out + err


def test_assess_writes_the_block_with_the_digests_of_both_files(tmp_path):
    root, task_dir = _project(tmp_path, "schema: 1\nsignoff_labels: [billing]\n")
    _assess(root)
    manifest = _manifest(task_dir)
    block = manifest["policy"]
    assert block["check_set"] == "compass-checks@9.0.0"
    assert block["check_set_sha256"] == _sha256sum(CHECK_SET)
    assert block["settings_sha256"] == _sha256sum(root / "compass.yml")
    assert block["tightened"] == {"signoff_labels": ["billing"]}
    assert block["resolved"] == _marker_digest(task_dir, manifest["generation"])


def test_without_a_compass_yml_the_settings_digest_is_null(tmp_path):
    root, task_dir = _project(tmp_path)
    _assess(root)
    block = _manifest(task_dir)["policy"]
    assert block["settings_sha256"] is None
    assert block["tightened"] == {}
    assert block["check_set_sha256"] == _sha256sum(CHECK_SET)


def test_a_reassess_writes_the_block_for_the_new_generation(tmp_path):
    root, task_dir = _project(tmp_path, "schema: 1\n")
    _assess(root)
    first = _manifest(task_dir)
    (root / "compass.yml").write_text("schema: 1\nsignoff_labels: [billing]\n",
                                      encoding="utf-8")
    _assess(root)
    second = _manifest(task_dir)
    assert second["generation"] == first["generation"] + 1
    assert second["policy"]["resolved"] == _marker_digest(task_dir, second["generation"])
    assert second["policy"]["resolved"] != first["policy"]["resolved"]
    assert second["policy"]["settings_sha256"] == _sha256sum(root / "compass.yml")
    assert second["policy"]["tightened"] == {"signoff_labels": ["billing"]}


def test_a_reassess_that_commits_nothing_still_names_the_generation_in_force(tmp_path):
    root, task_dir = _project(tmp_path, "schema: 1\n")
    _assess(root)
    first = _manifest(task_dir)
    manifest = _manifest(task_dir)
    del manifest["policy"]
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False),
                                           encoding="utf-8")
    _assess(root)
    second = _manifest(task_dir)
    assert second["generation"] == first["generation"]
    assert second["policy"] == first["policy"]


def test_compass_check_names_the_policy(tmp_path):
    root, task_dir = _project(tmp_path, "schema: 1\nsignoff_labels: [billing]\n")
    _assess(root)
    _, out, err = _run(root, "check", "--issue", SLUG, "--verbose")
    assert f"Policy: compass-checks@9.0.0 (sha256 {_sha256sum(CHECK_SET)})" in out, out + err
    assert "Tightened: signoff_labels" in out


def test_a_manifest_without_the_block_still_checks_and_lints(tmp_path):
    """A manifest written before 9.0.0 has no `policy:`; it reads as before."""
    root, task_dir = _project(tmp_path)
    _assess(root)
    manifest = _manifest(task_dir)
    del manifest["policy"]
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False),
                                           encoding="utf-8")
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    assert code in (0, 1), out + err
    assert "policy" not in (err or "").lower()
    code, out, err = _run(root, "issue", "lint", "--issue", SLUG)
    assert "policy" not in out + err, out + err


def test_the_schema_accepts_the_block_and_its_absence():
    import json
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    node = schema["properties"]["policy"]
    assert "policy" not in schema.get("required", [])
    assert set(node["required"]) == {"check_set", "check_set_sha256", "settings_sha256",
                                     "tightened", "resolved"}
