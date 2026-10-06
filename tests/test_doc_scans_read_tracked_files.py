"""The document scans read what git distributes, not what is on disk.

Three scans listed every Markdown file on disk, so the maintainer's private,
untracked planning files under `docs/specs/` failed them locally while CI
passed, and every local run had to leave them out by hand. They now list
only files git tracks, as the style scans already do.

Scenario id: DS-1 (issue `doc-scans-read-tracked-files`).
"""
from __future__ import annotations

import subprocess

import test_documented_commands_exist as commands
import test_public_surface_truth as surface


def _repo(tmp_path):
    root = tmp_path / "repo"
    (root / "docs" / "specs").mkdir(parents=True)
    (root / "docs" / "guide.md").write_text("tracked\n")
    (root / "docs" / "specs" / "draft.md").write_text("untracked\n")
    (root / "README.md").write_text("tracked\n")
    for args in (["init", "-q"], ["add", "docs/guide.md", "README.md"]):
        subprocess.run(["git", *args], cwd=root, check=True)
    return root


def test_ds_1_the_surface_scan_lists_only_tracked_documents(tmp_path):
    root = _repo(tmp_path)
    listed = {p.relative_to(root).as_posix() for p in surface._prose_files(root)}
    assert "docs/guide.md" in listed
    assert "docs/specs/draft.md" not in listed


def test_ds_1_the_command_scan_lists_only_tracked_documents(tmp_path):
    root = _repo(tmp_path)
    listed = {p.relative_to(root).as_posix() for p in commands._markdown_files(root)}
    assert "docs/guide.md" in listed
    assert "docs/specs/draft.md" not in listed
