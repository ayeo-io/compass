"""`compass issue status set` names the issue it acted on.

The success line, the refusal and the `--json` result all name the issue.

The refusal matters most: it is what a person meets when shipping
is blocked, usually with several issues open, and "refusing to mark 'None'
landed" cannot tell them which one refused.

Scenario ids: SSN-A1, SSN-A2 in
set-status-does-not-name-the-issue/acceptance-criteria.md
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "cli" / "compass"

SLUG = "an-issue-with-a-name"


def _project(tmp_path, manifest):
    d = tmp_path / ".compass" / "work" / SLUG
    d.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (d / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    return tmp_path


def _set_status(root, *words):
    return subprocess.run(
        [sys.executable, str(CLI), "issue", "status", "set", "--issue", SLUG, *words],
        cwd=str(root), capture_output=True, text=True, timeout=120)


_BASE = {
    "schema_version": "2.0",
    "task": SLUG,
    "created": "2026-08-26",
    "status": "active",
    "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                   "size": "atomic", "goal": "delivery", "role": "engineer"},
}


def test_ssn_a1_the_success_line_names_the_issue(tmp_path):
    root = _project(tmp_path, dict(_BASE, gates=[]))
    run = _set_status(root, "backlog")
    out = run.stdout + run.stderr
    assert run.returncode == 0, out
    assert SLUG in out, f"the outcome does not name the issue:\n{out}"
    assert "None" not in out, f"the outcome calls the issue 'None':\n{out}"


def test_ssn_a1b_the_json_result_carries_the_issue(tmp_path):
    root = _project(tmp_path, dict(_BASE, gates=[]))
    run = _set_status(root, "backlog", "--json")
    payload = json.loads(run.stdout)
    assert payload.get("issue") == SLUG, (
        "the --json result does not carry the issue. A consumer reading this "
        f"field to learn which issue changed state gets nothing:\n{run.stdout}")


def test_ssn_a1c_the_refusal_names_the_issue(tmp_path):
    """The one a person meets when shipping is blocked."""
    root = _project(tmp_path, dict(
        _BASE, gates=[{"id": "verify.correctness", "status": "pending",
                       "evidence": []}]))
    run = _set_status(root, "done", "--close-reason", "completed")
    out = run.stdout + run.stderr
    assert run.returncode != 0, "an unmet gate did not refuse the landing"
    assert SLUG in out, (
        "the refusal does not say which issue refused, which is the whole "
        f"problem when several are in flight:\n{out}")
    assert "'None'" not in out, f"the refusal calls the issue 'None':\n{out}"


def test_ssn_a2_a_landed_by_entry_still_reads_its_own_key(tmp_path):
    """The boundary. `issue:` IS the key inside a `landed_by:` entry.

    `cli/compass_pkg/landed_by.py` reads `entry.get("issue")` and is right to.
    A find-and-replace across the package would break the pointer feature.
    """
    from importlib.machinery import SourceFileLoader
    mod = SourceFileLoader(
        "landed_by_under_test",
        str(REPO_ROOT / "cli" / "compass_pkg" / "landed_by.py")).load_module()
    src = (REPO_ROOT / "cli" / "compass_pkg" / "landed_by.py").read_text()
    assert 'entry.get("issue")' in src or "entry.get('issue')" in src, (
        "landed_by.py no longer reads `issue` from a landed_by entry - the "
        "manifest-root fix has been swept across a place where `issue:` is "
        "genuinely the key, which breaks the pointer feature from pull "
        "request #96")
    assert hasattr(mod, "LANDED_BY_RELAXES")
