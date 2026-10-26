"""One DSL per scenario and per client, in a folder of its own.

The folder is made outside pytest's temporary root, whose path holds
"test": the hook exempts a path that holds "test", so a scenario under it
would test the exemption, not the check.

A scenario a client is known to fail is marked here, with the issue that
tracks it, and not in the specification. The mark is strict: when the issue
is fixed the scenario passes, the mark fails, and it must be removed.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from tests.acceptance.hooks.drivers import clients
from tests.acceptance.hooks.dsl import Dsl

KNOWN_FAILURES = {
    ("codex", "test_hfm_2_with_no_python3_the_refusal_says_so"):
        "ayeo-io/compass-delivery#308: the Codex hook command exits 127 without python3",
}


@pytest.fixture(params=clients())
def dsl(request):
    client = request.param
    reason = KNOWN_FAILURES.get((client, request.node.originalname))
    if reason:
        request.node.add_marker(pytest.mark.xfail(reason=reason, strict=True))
    workspace = Path(tempfile.mkdtemp(prefix="compass-acc-"))
    yield Dsl(workspace, client)
    for path in workspace.rglob("*"):
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() else 0o644)
    shutil.rmtree(workspace, ignore_errors=True)
