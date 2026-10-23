"""`compass quick-fix start` recovers when it cannot write its start record.

`start` keeps a record of what was already changed inside the git directory
(the worktree's own, in a linked worktree). When that folder could not be
written, `start` had already written the manifest and moved the issue
pointer, then stopped with a traceback. The half-made issue could not be
resumed: `next` refused the missing approach record, and a new `start`
refused the existing issue folder.

The test makes `.git/compass` a folder the process cannot write to, as a
linked worktree outside the writable checkout does.

Scenario id: `QSM-1`.
"""
from __future__ import annotations

import os
import stat

import pytest

from test_quick_fix_verbs import _start, repo  # noqa: F401

SLUG = "greet"


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                    reason="root can write to a folder without write permission")
def test_qsm_1_start_refuses_cleanly_and_a_retry_works(repo):
    metadata = repo / ".git" / "compass"
    metadata.mkdir()
    metadata.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        refused = _start(repo, SLUG)
    finally:
        metadata.chmod(stat.S_IRWXU)
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert "Traceback" not in refused.stderr, refused.stderr
    # The output names a path under the project relative to it.
    assert ".git/compass/start-state" in refused.stderr, refused.stderr
    assert "write access" in refused.stderr, refused.stderr
    # Nothing of the issue is left, so the same slug can start again.
    assert not (repo / ".compass" / "work" / SLUG).exists()
    pointer = repo / ".compass" / "current-task"
    assert not pointer.exists() or pointer.read_text().strip() != SLUG

    retried = _start(repo, SLUG)
    assert retried.returncode == 0, retried.stdout + retried.stderr
    assert (repo / ".compass" / "work" / SLUG / "manifest.yml").is_file()
    assert pointer.read_text().strip() == SLUG
