"""The tree id sees an edit made in the same second as the last commit.

`binding.work_tree_id` copies the real git index and asks git which tracked
files changed. Git trusts an index entry whose file looks unchanged by size
and timestamp unless the entry is as new as the index - its guard for an
edit made in the same second the index was written. The copy keeps the real
index's timestamp, so that guard still applies to it.

The test sets the timestamps itself, so the case is reproduced every time,
not by the chance of two steps falling in the same second.

Scenario id: TSE-1, in the delivery approach of issue
`tree-id-misses-a-same-second-edit`.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
import compass_pkg  # noqa: E402,F401 - puts the bundled PyYAML first
from compass_pkg.binding import work_tree_id  # noqa: E402


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, check=True)


def test_tse_1_a_same_size_edit_in_the_same_second_changes_the_tree_id(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    # A change time cannot be set, so the repository does not read it; the
    # file's size and modification time are then all git compares.
    _git(root, "config", "core.trustctime", "false")
    tool = root / "tool.sh"
    tool.write_text("echo one\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")

    # The entry and the index are both written in one second, T.
    t = int(time.time()) - 100
    os.utime(tool, (t, t))
    _git(root, "update-index", "--really-refresh")
    index = root / ".git" / "index"
    os.utime(index, (t, t))
    before = work_tree_id(str(root))

    # A same-size edit whose timestamp is still T.
    tool.write_text("echo two\n")
    os.utime(tool, (t, t))
    after = work_tree_id(str(root))

    assert before != after, "a same-size edit in the index's second was missed"
