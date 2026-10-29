"""The helper that builds a PATH folder for a test links each program once.

Tests that run a hook without jq or without python3 link every program of
/usr/bin and /bin into one folder, leaving those out. A runner image can hold
the same broken link in both folders (`grub-ntldr-img` on GitHub's Ubuntu
image, October 2026). A broken link does not `exist()`, so the second folder
tried to link the name again and the test failed with FileExistsError before
it ran.

Scenario id: `TRC-001` in issue `path-helpers-broken-links`.
"""
from __future__ import annotations

import os

from tests.path_folder import link_programs


def test_trc_001_a_broken_link_in_both_folders_is_linked_once(tmp_path):
    first, second, dest = tmp_path / "first", tmp_path / "second", tmp_path / "bin"
    for folder in (first, second):
        folder.mkdir()
        (folder / "dangling").symlink_to(folder / "missing")
        (folder / "tool").write_text("#!/bin/sh\n")
        (folder / "python3").write_text("#!/bin/sh\n")
    link_programs(dest, skip=lambda name: name.startswith("python"), sources=(first, second))
    assert sorted(os.listdir(dest)) == ["dangling", "tool"]
    assert os.readlink(dest / "dangling") == str(first / "dangling")
    assert os.readlink(dest / "tool") == str(first / "tool")


def test_trc_001_the_folder_can_already_exist(tmp_path):
    source, dest = tmp_path / "source", tmp_path / "bin"
    source.mkdir()
    dest.mkdir()
    (source / "tool").write_text("#!/bin/sh\n")
    link_programs(dest, skip=lambda name: False, sources=(source,))
    link_programs(dest, skip=lambda name: False, sources=(source,))
    assert os.listdir(dest) == ["tool"]
