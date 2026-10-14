"""Scenarios MRE-1, MRE-2, MRE-3 and MRE-5 of the issue `migrate-review-entries`.

The 6.x migrate registered review files under their filename stems (`kind: review`
with no round, `kind: review-2`, `kind: integrated-review-3`). These tests check
that `compass issue migrate` moves each such entry onto the round its file
becomes, and that the `--apply` refusal names every folder it cannot restore.

Every test builds a fixture project in a temporary folder. None of them touches
a real archive.
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
SLUG = "old-reviews"
CREATED = "2026-09-01"
HOME = f"docs/compass/{CREATED}-{SLUG}"
APPROVAL = {"approved_by": "jed72", "approved_at": "2026-09-02T09:00:00Z"}


def _env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "200",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def _migrate(root, *flags):
    run = subprocess.run([sys.executable, str(CLI), "issue", "migrate", *flags], cwd=root,
                         env=_env(root), capture_output=True, text=True, timeout=300)
    return run.returncode, run.stdout, run.stderr


def _project(tmp_path, entries, documents):
    """A project with one issue: its registry `entries` and the files in its
    documents folder."""
    root = tmp_path / "project"
    work = root / ".compass" / "work" / SLUG
    work.mkdir(parents=True)
    body = {"schema_version": "3.0", "issue": SLUG, "created": CREATED,
            "delivery_approach": "regular", "artifacts": entries}
    (work / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    docs = root / HOME
    docs.mkdir(parents=True)
    for name in documents:
        (docs / name).write_text(f"# {name}\n", encoding="utf-8")
    return root, work


def _registry(work):
    return yaml.safe_load((work / "manifest.yml").read_text(encoding="utf-8"))["artifacts"]


def _one_entry_per_file(root, entries):
    paths = [e["path"] for e in entries if e.get("path")]
    assert len(paths) == len(set(paths)), entries
    missing = [p for p in paths if not (root / p).is_file()]
    assert not missing, (missing, entries)


def _by_path(entries):
    return {os.path.basename(e["path"]): e for e in entries if e.get("path")}


def test_mre_1(tmp_path):
    root, work = _project(tmp_path, [
        {"id": "ART-REVIEW", "kind": "review", "status": "approved", **APPROVAL,
         "path": f"{HOME}/review.md"},
        {"id": "ART-REVIEW-2", "kind": "review-2", "status": "draft",
         "path": f"{HOME}/review-2.md"},
        {"id": "ART-INTEGRATED_REVIEW_3", "kind": "integrated-review-3",
         "status": "awaiting-approval", "path": f"{HOME}/integrated-review-3.md"},
    ], ["review.md", "review-2.md", "integrated-review-3.md"])
    before = (work / "manifest.yml").read_bytes()
    code, out, err = _migrate(root)
    assert code == 0, out + err
    assert (work / "manifest.yml").read_bytes() == before
    for kind in ("review-2", "integrated-review-3"):
        assert f"would re-point the registry entry {kind}" in out, out
    code, out, err = _migrate(root, "--apply", "--i-have-a-copy")
    assert code == 0, out + err
    entries = _registry(work)
    _one_entry_per_file(root, entries)
    got = _by_path(entries)
    assert set(got) == {"review-1.md", "review-2.md", "review-3.md"}, entries
    first, second, third = got["review-1.md"], got["review-2.md"], got["review-3.md"]
    assert (first["id"], first["kind"], first["round"], first["status"]) == (
        "ART-REVIEW", "review", 1, "approved"), first
    assert (first["approved_by"], first["approved_at"]) == (
        APPROVAL["approved_by"], APPROVAL["approved_at"]), first
    assert (second["id"], second["kind"], second["round"], second["status"]) == (
        "ART-REVIEW-2", "review", 2, "draft"), second
    assert (third["id"], third["kind"], third["round"], third["status"]) == (
        "ART-INTEGRATED_REVIEW_3", "review", 3, "awaiting-approval"), third
    assert len(entries) == 3, entries
    code, out, err = _migrate(root, "--apply", "--i-have-a-copy")
    assert code == 0 and "nothing to do" in out, out + err


def test_mre_2(tmp_path):
    # The registry an earlier 7.0.0 migrate left on the fixture of MRE-1's first two
    # files, with one more stem entry whose file is gone and that nothing maps to.
    root, work = _project(tmp_path, [
        {"id": "ART-REVIEW", "kind": "review", "status": "approved", **APPROVAL,
         "path": f"{HOME}/review.md"},
        {"id": "ART-REVIEW-2", "kind": "review-2", "status": "draft",
         "path": f"{HOME}/review-2.md"},
        {"id": "ART-REVIEW_CLAIMS", "kind": "review-claims", "status": "draft",
         "path": f"{HOME}/review-claims.md"},
        {"id": "ART-REVIEW-1", "kind": "review", "round": 1, "status": "draft",
         "reason": "migrated from review.md", "path": f"{HOME}/review-1.md"},
        {"id": "ART-REVIEW-2", "kind": "review", "round": 2, "status": "draft",
         "reason": "migrated from review-2.md", "path": f"{HOME}/review-2.md"},
    ], ["review-1.md", "review-2.md"])
    before = (work / "manifest.yml").read_bytes()
    code, out, err = _migrate(root)
    assert code == 0, out + err
    assert "nothing to do" not in out, out
    assert "would merge the registry entry review (ART-REVIEW) into review round 1" in out, out
    assert "would merge the registry entry review-2 (ART-REVIEW-2) into review round 2" in out, out
    assert (work / "manifest.yml").read_bytes() == before
    code, out, err = _migrate(root, "--apply", "--i-have-a-copy")
    assert code == 0, out + err
    entries = _registry(work)
    kept = [e for e in entries if e["kind"] == "review-claims"]
    assert [e["id"] for e in kept] == ["ART-REVIEW_CLAIMS"], entries
    rounds = [e for e in entries if e["kind"] == "review"]
    _one_entry_per_file(root, rounds)
    got = _by_path(rounds)
    assert set(got) == {"review-1.md", "review-2.md"} and len(rounds) == 2, entries
    first, second = got["review-1.md"], got["review-2.md"]
    assert (first["id"], first["round"], first["status"], first["approved_by"],
            first["approved_at"]) == ("ART-REVIEW", 1, "approved", "jed72",
                                      APPROVAL["approved_at"]), first
    assert (second["id"], second["round"], second["status"]) == ("ART-REVIEW-2", 2, "draft")
    # The entry nothing maps to is named, with what to do, on this run and the next.
    for text in (out, _migrate(root, "--apply", "--i-have-a-copy")[1]):
        line = next((ln for ln in text.splitlines() if "ART-REVIEW_CLAIMS" in ln), "")
        assert "review-claims.md" in line and "remove the entry" in line, text
    code, out, err = _migrate(root, "--apply", "--i-have-a-copy")
    assert code == 0 and "nothing to do" in out, out + err


def _tree(root):
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file() and ".git" not in p.parts}


def test_mre_3(tmp_path):
    root, work = _project(tmp_path, [
        {"id": "ART-REVIEW", "kind": "review", "status": "draft", "path": f"{HOME}/review.md"},
    ], ["review.md"])
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    before = _tree(root)
    code, out, err = _migrate(root, "--apply")
    assert code == 2, out + err
    assert _tree(root) == before
    text = out + err
    assert text.count("cannot be put back") == 1, text
    copies = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("cp -R")]
    assert any(".compass/work" in ln for ln in copies), text
    assert any("docs/compass" in ln for ln in copies), text
    # The upgrade guide says the refusal names every such folder, and its copy step
    # names both.
    guide = " ".join((ROOT / "docs" / "upgrade-7-0-0.md").read_text(encoding="utf-8").split())
    assert "naming every folder it cannot restore" in guide, "refusal sentence"
    step = guide.split("### What to do", 1)[1].split("2. ", 1)[0]
    assert "`.compass/work`" in step and "`docs/compass`" in step, step


OLDER = {"status": "approved", "approved_by": "jed72", "approved_at": "2026-09-02T09:00:00Z",
         "digest": "sha256:OLD"}
NEWER = {"status": "approved", "approved_by": "jed72", "approved_at": "2026-10-10T09:00:00Z",
         "digest": "sha256:NEW"}
DRAFT = {"status": "draft"}


def _merge_line(text, verb):
    lines = [ln for ln in text.splitlines()
             if f"{verb} the registry entry review (ART-REVIEW)" in ln]
    assert len(lines) == 1, text
    return lines[0]


@pytest.mark.parametrize("stem, held, kept_id, kept, dropped_id, dropped", [
    pytest.param(NEWER, OLDER, "ART-REVIEW", NEWER, "ART-REVIEW-1", OLDER, id="stem-newer"),
    pytest.param(OLDER, NEWER, "ART-REVIEW-1", NEWER, "ART-REVIEW", OLDER, id="round-newer"),
    pytest.param(DRAFT, NEWER, "ART-REVIEW-1", NEWER, "ART-REVIEW", DRAFT,
                 id="stem-draft-round-approved"),
    pytest.param(DRAFT, {"status": "awaiting-approval"}, "ART-REVIEW", DRAFT, "ART-REVIEW-1",
                 {"status": "awaiting-approval"}, id="both-draft"),
])
def test_mre_5(tmp_path, stem, held, kept_id, kept, dropped_id, dropped):
    # The registry an earlier 7.0.0 migrate left: the stem entry names the file the
    # rename moved, and the round entry that run wrote names the renamed file.
    root, work = _project(tmp_path, [
        {"id": "ART-REVIEW", "kind": "review", **stem, "path": f"{HOME}/review.md"},
        {"id": "ART-REVIEW-1", "kind": "review", "round": 1, **held,
         "reason": "migrated from review.md", "path": f"{HOME}/review-1.md"},
    ], ["review-1.md"])
    code, dry, err = _migrate(root)
    assert code == 0, dry + err
    code, out, err = _migrate(root, "--apply", "--i-have-a-copy")
    assert code == 0, out + err
    entries = _registry(work)
    assert len(entries) == 1, entries
    entry = entries[0]
    assert (entry["id"], entry["kind"], entry["round"], entry["path"]) == (
        kept_id, "review", 1, f"{HOME}/review-1.md"), entry
    for key in ("status", "approved_by", "approved_at", "digest"):
        assert entry.get(key) == kept.get(key), (key, entry)
    # The report names what was kept and what was dropped, the approval included.
    line = _merge_line(out, "merged")
    keeping, dropping = line.split(", keeping ", 1)[1].split("; dropping ", 1)
    assert f"id {kept_id} " in keeping and f"id {dropped_id} " in dropping, line
    for part, record, other in ((keeping, kept, dropped), (dropping, dropped, kept)):
        assert (record.get("approved_at") or record["status"]) in part, (part, line)
        if other.get("approved_at") != record.get("approved_at"):
            assert str(other.get("approved_at")) not in part, (part, line)
    # The dry run says what the apply does, word for word.
    assert _merge_line(dry, "would merge").replace("would merge", "merged", 1) == line, dry
