"""`compass record sync` never recommends or runs a destructive prune blind.

After a sync, the hint about earlier record files that still name a rival
product used to recommend `compass record sync --prune`. That prune deletes
every record file the local checkout does not hold, then pushes: run from
the main checkout it would have deleted thousands of files to clean 70
(ayeo-io/compass-delivery#339).

These tests plant an invented product, "Zorblax Kit" under the code `R0`,
and use a local bare repository as the record, never a real remote.

The tests cover the three scenarios of the issue `record-prune-hint`: the
hint names the files and a fix that deletes nothing; `--redact-existing`
rewrites earlier files in place; and `--prune` lists what it would delete
and pushes nothing until `--apply` confirms it.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from test_rival_names_never_committed import FAKE_KEY, _cli, _record_project


def _key(tmp_path):
    key = tmp_path / "key.yml"
    key.write_text(yaml.safe_dump(FAKE_KEY), encoding="utf-8")
    return key


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=True).stdout


def _seed(remote, tmp_path, files):
    """Commit `files` (path -> text) straight into the record, as an
    earlier sync, or a sync from another checkout, left them."""
    clone = tmp_path / "seed"
    _git(tmp_path, "clone", "-q", "-b", "main", str(remote), str(clone))
    for rel, text in files.items():
        path = clone / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _git(clone, "add", "-A")
    _git(clone, "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "commit", "-q", "-m", "earlier record")
    _git(clone, "push", "-q", "origin", "HEAD:main")


def _record(remote, tmp_path, name):
    """`{path: text}` of every file in the record."""
    clone = tmp_path / name
    _git(tmp_path, "clone", "-q", "-b", "main", str(remote), str(clone))
    return {str(p.relative_to(clone)): p.read_text(encoding="utf-8")
            for p in clone.rglob("*") if p.is_file() and ".git" not in p.parts}


def _head(remote):
    return _git(remote, "rev-parse", "main").strip()


def _synced(tmp_path, monkeypatch, earlier):
    root, remote = _record_project(tmp_path, monkeypatch, _key(tmp_path))
    first = _cli(root, "record", "sync")
    assert first.returncode == 0, first.stdout + first.stderr
    if earlier:
        _seed(remote, tmp_path, earlier)
    return root, remote


# --- The hint after a sync ---

def test_trc_001_the_hint_names_masked_files_and_a_fix_that_deletes_nothing(
        tmp_path, monkeypatch):
    root, _ = _synced(tmp_path, monkeypatch, {
        "docs/analysis/old-zorblax-kit.md": "Old Zorblax Kit notes.\n"})
    (root / "docs" / "analysis" / "new.md").write_text("new\n", encoding="utf-8")
    result = _cli(root, "record", "sync")
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert "1 earlier record file(s) still name a rival product" in out, out
    assert "docs/analysis/old-[name].md" in out, out
    assert "--redact-existing" in out and "deletes nothing" in out, out
    assert "--prune" not in out, out
    assert "zorblax" not in out.lower()


# --- Rewriting earlier files with --redact-existing ---

def test_trc_002_redact_existing_rewrites_in_place_and_deletes_nothing(
        tmp_path, monkeypatch):
    _, remote = _synced(tmp_path, monkeypatch, {
        "docs/analysis/old-zorblax-kit.md": "Old Zorblax Kit notes.\n",
        "docs/analysis/history.md": "We tried acme/zorblax once.\n",
        "docs/analysis/elsewhere.md": "Landed from another worktree.\n"})
    before = _record(remote, tmp_path, "before")
    root = tmp_path / "project"
    result = _cli(root, "record", "sync", "--redact-existing")
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert "rewrote 2 earlier record file(s)" in out, out
    assert "still name a rival" not in out, out
    assert "zorblax" not in out.lower()
    after = _record(remote, tmp_path, "after")
    assert len(after) == len(before), (sorted(before), sorted(after))
    for rel, text in after.items():
        assert "zorblax" not in rel.lower() and "zorblax" not in text.lower(), rel
    assert after["docs/analysis/elsewhere.md"] == "Landed from another worktree.\n"
    assert after["docs/analysis/history.md"] == "We tried R0 once.\n"
    assert after["docs/analysis/old-R0.md"] == "Old R0 notes.\n"


def test_trc_002_a_taken_coded_path_is_left_and_reported(tmp_path, monkeypatch):
    # The project's own file syncs to its coded path, so an older copy
    # under the named path cannot move there.
    _, remote = _synced(tmp_path, monkeypatch, {
        "docs/analysis/zorblax-kit-notes.md": "An older copy.\n"})
    root = tmp_path / "project"
    result = _cli(root, "record", "sync", "--redact-existing")
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert "could not be rewritten in place" in out, out
    assert "docs/analysis/[name]-notes.md" in out, out
    assert "zorblax" not in out.lower()
    after = _record(remote, tmp_path, "after")
    assert after["docs/analysis/zorblax-kit-notes.md"] == "An older copy.\n"
    assert "R0" in after["docs/analysis/R0-notes.md"]


def test_trc_002_a_file_holding_the_coded_folder_name_is_left(
        tmp_path, monkeypatch):
    # A named folder moves to its coded folder, unless a file already holds
    # that name: then its files are left and listed, not a traceback.
    _, remote = _synced(tmp_path, monkeypatch, {
        "docs/analysis/zorblax-kit/a.md": "plain\n",
        "docs/analysis/R0": "a file, not a folder\n"})
    root = tmp_path / "project"
    result = _cli(root, "record", "sync", "--redact-existing")
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert "could not be rewritten in place" in out, out
    assert "docs/analysis/[name]/a.md" in out, out
    assert "zorblax" not in out.lower()
    after = _record(remote, tmp_path, "after")
    assert after["docs/analysis/zorblax-kit/a.md"] == "plain\n"
    assert after["docs/analysis/R0"] == "a file, not a folder\n"


# --- A prune lists and refuses until --apply ---

def test_trc_003_prune_lists_deletions_and_pushes_nothing_without_apply(
        tmp_path, monkeypatch):
    root, remote = _synced(tmp_path, monkeypatch, {
        "docs/analysis/zorblax-kit-elsewhere.md": "Landed from another worktree.\n"})
    head = _head(remote)
    refused = _cli(root, "record", "sync", "--prune")
    out = refused.stdout + refused.stderr
    assert refused.returncode == 2, out
    assert "would remove 1 file(s) from the record" in out, out
    assert "docs/analysis/[name]-elsewhere.md" in out, out
    assert "--apply" in out, out
    assert "zorblax" not in out.lower()
    assert _head(remote) == head, "a refused prune still pushed"

    # The refused prune leaves nothing behind that a plain sync would push.
    (root / "docs" / "analysis" / "later.md").write_text("later\n", encoding="utf-8")
    plain = _cli(root, "record", "sync")
    assert plain.returncode == 0, plain.stdout + plain.stderr
    kept = _record(remote, tmp_path, "kept")
    assert "docs/analysis/zorblax-kit-elsewhere.md" in kept, sorted(kept)
    assert "docs/analysis/later.md" in kept, sorted(kept)

    applied = _cli(root, "record", "sync", "--prune", "--apply")
    out = applied.stdout + applied.stderr
    assert applied.returncode == 0, out
    # Every deleted file is named, in the output and in the record's commit,
    # so a file that reached the record after the listing is not lost unseen.
    assert "deleted 1 record file(s)" in out, out
    assert "docs/analysis/[name]-elsewhere.md" in out, out
    assert "zorblax" not in out.lower()
    after = _record(remote, tmp_path, "after")
    assert not any("elsewhere" in rel for rel in after), sorted(after)
    body = _git(tmp_path / "after", "log", "-1", "--format=%B")
    assert "docs/analysis/[name]-elsewhere.md" in body, body
    assert "zorblax" not in body.lower()


def test_trc_003_apply_without_prune_is_refused(tmp_path, monkeypatch):
    root, remote = _synced(tmp_path, monkeypatch, {})
    result = _cli(root, "record", "sync", "--apply")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "--apply confirms a prune's deletions" in result.stderr, result.stderr
