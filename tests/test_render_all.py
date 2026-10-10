"""Whole-archive render, and the guard that no test touches this checkout's archive
(issue `documents-carry-judgement`, DCJ-63).

`NEW_TEST_MODULES` lists the test modules the issue adds. Each later unit adds
its own to the list, so the guard runs every module that renders or migrates.
This module is not in the list: it would run itself.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from rendered_blocks_support import tracked_digest  # noqa: E402

#: The modules this issue adds that render or migrate. Later units extend it.
NEW_TEST_MODULES = ["tests/test_render_blocks.py", "tests/test_rendered_blocks_check.py",
                    "tests/test_dod_from_manifest.py"]


def _archive_digest():
    return tracked_digest(*[p for p in (ROOT / ".compass" / "work", ROOT / "docs" / "compass")
                            if p.is_dir()])


@pytest.mark.serial
def test_dcj_63_no_test_touches_own_archive():
    before = _archive_digest()
    env = dict(os.environ, PYTEST_ADDOPTS="", PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-x",
         "-o", "addopts=", *NEW_TEST_MODULES],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=1500)
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
    assert _archive_digest() == before
    # Every render and migrate those tests run targets a temporary folder: no
    # module builds a path from this checkout's archive.
    for name in NEW_TEST_MODULES + ["tests/rendered_blocks_support.py"]:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert 'ROOT / ".compass"' not in text and "ROOT / 'docs'" not in text, name
        assert 'ROOT / "docs" / "compass"' not in text, name
