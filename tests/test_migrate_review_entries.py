"""Scenarios MRE-1, MRE-2, MRE-3 and MRE-5 to MRE-8 of the issue `migrate-review-entries`.

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
    # The upgrade guide says the refusal names each root it cannot restore, and its copy
    # step names both.
    guide = " ".join((ROOT / "docs" / "upgrade-7-0-0.md").read_text(encoding="utf-8").split())
    assert "naming each root it cannot restore, with a count and the first five folders" \
        in guide, "refusal sentence"
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


def _said(record):
    """The words the report uses for a record's approval, or for its status when it
    is not approved."""
    if record.get("approved_by"):
        return "approval by %s at %s" % (record["approved_by"],
                                         record.get("approved_at") or "no recorded time")
    return "status %s, not approved" % record["status"]


def _check_merge(tmp_path, stem, held, kept_id, kept, dropped_id, dropped):
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
    # The report names what was kept and what was dropped, the approval or status
    # included, and neither half carries the other entry's approval or status.
    line = _merge_line(out, "merged")
    keeping, dropping = line.split(", keeping ", 1)[1].split("; dropping ", 1)
    assert f"id {kept_id} " in keeping and f"id {dropped_id} " in dropping, line
    for part, record, other in ((keeping, kept, dropped), (dropping, dropped, kept)):
        assert _said(record) in part, (part, line)
        if _said(other) != _said(record):
            assert _said(other) not in part, (part, line)
    # The dry run says what the apply does, word for word.
    assert _merge_line(dry, "would merge").replace("would merge", "merged", 1) == line, dry


@pytest.mark.parametrize("stem, held, kept_id, kept, dropped_id, dropped", [
    pytest.param(NEWER, OLDER, "ART-REVIEW", NEWER, "ART-REVIEW-1", OLDER, id="stem-newer"),
    pytest.param(OLDER, NEWER, "ART-REVIEW-1", NEWER, "ART-REVIEW", OLDER, id="round-newer"),
    pytest.param(DRAFT, NEWER, "ART-REVIEW-1", NEWER, "ART-REVIEW", DRAFT,
                 id="stem-draft-round-approved"),
])
def test_mre_5(tmp_path, stem, held, kept_id, kept, dropped_id, dropped):
    _check_merge(tmp_path, stem, held, kept_id, kept, dropped_id, dropped)


def _round_absent_project(tmp_path, stem, held, documents):
    return _project(tmp_path, [
        {"id": "ART-REVIEW", "kind": "review", **stem, "path": f"{HOME}/review.md"},
        {"id": "ART-REVIEW-1", "kind": "review", "round": 1, **held,
         "path": f"{HOME}/review-1.md"},
    ], documents)


@pytest.mark.parametrize("stem, held, kept_id, kept", [
    pytest.param(NEWER, OLDER, "ART-REVIEW", NEWER, id="stem-newer"),
    pytest.param(OLDER, NEWER, "ART-REVIEW-1", NEWER, id="round-newer"),
])
def test_mre_6_round_file_absent(tmp_path, stem, held, kept_id, kept):
    # Both entries are approved and only the stem entry's file exists. The rename of
    # review.md to review-1.md settles it, so the two merge.
    root, work = _round_absent_project(tmp_path, stem, held, ["review.md"])
    before = (work / "manifest.yml").read_bytes()
    code, dry, err = _migrate(root)
    assert code == 0, dry + err
    assert "both exist" not in dry + err, dry + err
    assert (work / "manifest.yml").read_bytes() == before
    code, out, err = _migrate(root, "--apply", "--i-have-a-copy")
    assert code == 0, out + err
    assert "both exist" not in out + err, out + err
    entries = _registry(work)
    assert len(entries) == 1, entries
    _one_entry_per_file(root, entries)
    entry = entries[0]
    assert (entry["id"], entry["round"], entry["path"]) == (
        kept_id, 1, f"{HOME}/review-1.md"), entry
    for key in ("status", "approved_by", "approved_at", "digest"):
        assert entry.get(key) == kept.get(key), (key, entry)
    assert not (root / HOME / "review.md").exists()
    assert _merge_line(dry, "would merge").replace("would merge", "merged", 1) == \
        _merge_line(out, "merged"), dry


def test_mre_6_both_files_exist(tmp_path):
    # Both files exist, so the two entries name two documents: a person settles it.
    # Here review.md and review-1.md both claim round 1, and the plan refuses the issue.
    root, work = _round_absent_project(tmp_path, NEWER, OLDER, ["review.md", "review-1.md"])
    before = _tree(root)
    for flags in ((), ("--apply", "--i-have-a-copy")):
        code, out, err = _migrate(root, *flags)
        text = out + err
        assert any("review.md" in ln and "review-1.md" in ln and "both claim" in ln
                   for ln in text.splitlines()), text
        assert "the registry entry review (ART-REVIEW) into" not in text, text
        assert _tree(root) == before, (flags, text)


def test_mre_6_both_files_exist_elsewhere(tmp_path):
    # The round entry names a file outside the documents folder, so no rename
    # collides and the merge step itself must refuse.
    elsewhere = "notes/review-2.md"
    root, work = _project(tmp_path, [
        {"id": "ART-REVIEW-2", "kind": "review-2", **NEWER, "path": f"{HOME}/review-2.md"},
        {"id": "ART-ROUND-2", "kind": "review", "round": 2, **OLDER, "path": elsewhere},
    ], ["review-2.md"])
    (root / "notes").mkdir()
    (root / elsewhere).write_text("# elsewhere\n", encoding="utf-8")
    for flags in ((), ("--apply", "--i-have-a-copy")):
        code, out, err = _migrate(root, *flags)
        text = out + err
        line = next((ln for ln in text.splitlines() if "both exist" in ln), "")
        assert f"{HOME}/review-2.md" in line and elsewhere in line, text
        assert "the registry entry review-2 (ART-REVIEW-2) into" not in text, text
        entries = {e["id"]: e for e in _registry(work)}
        assert set(entries) == {"ART-REVIEW-2", "ART-ROUND-2"}, entries
        assert entries["ART-REVIEW-2"]["approved_at"] == NEWER["approved_at"], entries
        assert entries["ART-ROUND-2"]["approved_at"] == OLDER["approved_at"], entries
        assert (root / HOME / "review-2.md").is_file() and (root / elsewhere).is_file()


@pytest.mark.parametrize("stem, held", [
    pytest.param(DRAFT, {"status": "awaiting-approval", "digest": "sha256:ROUND"},
                 id="round-awaiting"),
    pytest.param({"status": "awaiting-approval", "digest": "sha256:STEM"}, DRAFT,
                 id="round-draft"),
])
def test_mre_7(tmp_path, stem, held):
    # Neither entry is approved. Stage exits write status, so the round entry's is the
    # more current: its id and status are kept, and the report names the stem
    # entry's id and status as dropped.
    _check_merge(tmp_path, stem, held, "ART-REVIEW-1", held, "ART-REVIEW", stem)


def _approval(by, at=None, digest=None):
    record = {"status": "approved", "approved_by": by}
    if at:
        record["approved_at"] = at
    if digest:
        record["digest"] = digest
    return record


SAME_TIME = "2026-09-02T09:00:00Z"
STEM_TIMED = _approval("jed72", SAME_TIME, "sha256:STEM")
ROUND_TIMED = _approval("alice", SAME_TIME, "sha256:ROUND")
STEM_UNTIMED = _approval("jed72", digest="sha256:STEM")
ROUND_UNTIMED = _approval("alice", digest="sha256:ROUND")


@pytest.mark.parametrize("stem, held, kept_id, kept, dropped_id, dropped", [
    # A tie keeps the stem entry: equal times carry the same weight.
    pytest.param(STEM_TIMED, ROUND_TIMED, "ART-REVIEW", STEM_TIMED, "ART-REVIEW-1",
                 ROUND_TIMED, id="equal-times"),
    pytest.param(STEM_UNTIMED, ROUND_UNTIMED, "ART-REVIEW", STEM_UNTIMED, "ART-REVIEW-1",
                 ROUND_UNTIMED, id="both-times-missing"),
    # A missing time sorts before any recorded time.
    pytest.param(STEM_UNTIMED, ROUND_TIMED, "ART-REVIEW-1", ROUND_TIMED, "ART-REVIEW",
                 STEM_UNTIMED, id="stem-time-missing"),
    pytest.param(STEM_TIMED, ROUND_UNTIMED, "ART-REVIEW", STEM_TIMED, "ART-REVIEW-1",
                 ROUND_UNTIMED, id="round-time-missing"),
])
def test_mre_8(tmp_path, stem, held, kept_id, kept, dropped_id, dropped):
    _check_merge(tmp_path, stem, held, kept_id, kept, dropped_id, dropped)
