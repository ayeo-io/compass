"""`compass issue migrate` settles the artifact status of done issues (issue
`artifact-status-written-by-stages`, group B, ASW-22 to ASW-25).

Every test builds a fixture work root in a temporary folder. None of them
touches a real archive.

Scenario ids: `ASW-22` to `ASW-25`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
REASON = "migrated from a 6.0.0 record"


def _entry(kind, status, **more):
    return {"id": "ART-" + kind.upper().replace("-", "_"), "kind": kind,
            "status": status, "depth": "thorough", **more}


def _issue(root, slug, status=None, close_reason=None, artifacts=None):
    folder = Path(root) / slug
    folder.mkdir(parents=True)
    body = {"schema_version": "3.0", "issue": slug, "created": "2026-10-01",
            "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                           "size": "medium", "goal": "delivery", "role": "engineer",
                           "labels": []},
            "evidence": []}
    if status:
        body["status"] = status
    if close_reason:
        body["close_reason"] = close_reason
    body["artifacts"] = artifacts if artifacts is not None else [
        _entry("acceptance-criteria", "draft"),
        _entry("technical-design", "awaiting-approval"),
        _entry("delivery-approach", "approved", approved_by="jed72",
               approved_at="2026-10-02T09:00:00Z")]
    (folder / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                         encoding="utf-8")
    return folder / "manifest.yml"


def _work_root(tmp_path):
    root = tmp_path / "work"
    paths = {
        "finished": _issue(root, "finished", "done", "completed"),
        "dropped": _issue(root, "dropped", "done", "not-planned"),
        "twin": _issue(root, "twin", "done", "duplicate"),
        "open": _issue(root, "open"),
    }
    return root, paths


def _migrate(root, *flags, cwd=None):
    r = subprocess.run([sys.executable, str(CLI), "issue", "migrate", str(root), *flags],
                       cwd=cwd or root.parent, capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


def _entries(path):
    body = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {a["kind"]: a for a in body["artifacts"]}


def _snapshot(paths):
    return {k: Path(p).read_bytes() for k, p in paths.items()}


def test_asw_22_migrate_approves_or_supersedes_done_drafts(tmp_path):
    root, paths = _work_root(tmp_path)
    open_before = Path(paths["open"]).read_bytes()
    code, out, err = _migrate(root, "--apply", "--i-have-a-copy")
    assert code == 0, out + err
    done = _entries(paths["finished"])
    assert done["acceptance-criteria"]["status"] == "approved"
    assert done["acceptance-criteria"]["approved_by"] == "compass issue migrate"
    assert done["acceptance-criteria"]["approved_at"]
    assert done["technical-design"]["status"] == "approved"
    for name in ("dropped", "twin"):
        for entry in _entries(paths[name]).values():
            if entry["kind"] != "delivery-approach":
                assert entry["status"] == "superseded"
                assert "approved_by" not in entry
    changed = [e for n in ("finished", "dropped", "twin")
               for e in _entries(paths[n]).values() if e["kind"] != "delivery-approach"]
    assert len(changed) == 6 and all(e["reason"] == REASON for e in changed)
    assert Path(paths["open"]).read_bytes() == open_before
    for name in ("finished", "dropped", "twin"):
        assert not [e for e in _entries(paths[name]).values()
                    if e["status"] in ("draft", "awaiting-approval")]


def test_asw_23_migrate_dry_run_writes_nothing(tmp_path):
    root, paths = _work_root(tmp_path)
    before = _snapshot(paths)
    code, out, err = _migrate(root)
    assert code == 0, out + err
    assert _snapshot(paths) == before
    assert "finished" in out and "would mark 2 artifact entries approved and 0 superseded" in out
    assert "dropped" in out and "would mark 0 artifact entries approved and 2 superseded" in out
    assert "twin" in out
    assert "\n  open\n" not in out


def test_asw_24_migrate_keeps_decisions_and_is_idempotent(tmp_path):
    root = tmp_path / "work"
    path = _issue(root, "kept", "done", "completed", artifacts=[
        _entry("delivery-approach", "approved", approved_by="jed72",
               approved_at="2026-10-02T09:00:00Z"),
        _entry("threat-model", "omitted", reason="no new trust boundary"),
        _entry("technical-design", "draft")])
    code, out, err = _migrate(root, "--apply", "--i-have-a-copy")
    assert code == 0, out + err
    got = _entries(path)
    assert got["delivery-approach"]["approved_by"] == "jed72"
    assert got["delivery-approach"]["approved_at"] == "2026-10-02T09:00:00Z"
    assert got["threat-model"] == {"id": "ART-THREAT_MODEL", "kind": "threat-model",
                                   "status": "omitted", "depth": "thorough",
                                   "reason": "no new trust boundary"}
    assert got["technical-design"]["status"] == "approved"
    settled = Path(path).read_bytes()
    code, out, err = _migrate(root, "--apply", "--i-have-a-copy")
    assert code == 0, out + err
    assert "nothing to do" in out
    assert Path(path).read_bytes() == settled


def test_asw_25_migrate_apply_needs_a_copy_on_untracked_root(tmp_path):
    repo = tmp_path / "repo"
    root = repo / "work"
    path = _issue(root, "kept", "done", "completed")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    before = Path(path).read_bytes()
    code, out, err = _migrate(root, "--apply", cwd=repo)
    assert code == 2, out + err
    assert "--i-have-a-copy" in out + err
    assert "change records that cannot be put back" in out + err
    assert Path(path).read_bytes() == before
    assert _entries(path)["acceptance-criteria"]["status"] == "draft"
