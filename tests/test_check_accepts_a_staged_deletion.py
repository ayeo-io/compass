"""Check accepts a traced file whose deletion is staged.

Before ship, `compass check` told an issue to drop a deleted file from
`changed_files`, while `ship-commit` refused the staged deletion unless it
was traced (#368). A staged deletion is now the change, the same as a
committed one.

Scenario id: SD-1 (issue `check-accepts-a-staged-deletion`).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.checks import _path_was_deleted  # noqa: E402


def _repo(root):
    root.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "t@example.invalid"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=str(root), check=True)
    (root / "old.yml").write_text("a: 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "old.yml"], cwd=str(root), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add"], cwd=str(root),
                   check=True)
    return root


def test_sd_1_a_staged_deletion_is_the_change(tmp_path):
    root = _repo(tmp_path / "r")
    subprocess.run(["git", "rm", "-q", "old.yml"], cwd=str(root), check=True)
    assert _path_was_deleted("old.yml", str(root))


def test_sd_1_a_file_missing_with_nothing_staged_is_still_reported(tmp_path):
    root = _repo(tmp_path / "r")
    (root / "old.yml").unlink()
    assert not _path_was_deleted("old.yml", str(root))
