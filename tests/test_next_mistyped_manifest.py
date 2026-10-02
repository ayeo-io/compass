"""`compass next` names a stage when `gates` or `stages` has the wrong type
(issue #236).

A hand-edited manifest can hold anything. A `gates` that is not a list, a
`stages` that is not a mapping, or a stage weight that is not a string must
still give a stage from `compass next`, with exit 0 and nothing on stderr,
and a line from the status line. `tests/test_next_stage.py` covers the
other manifest lists.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
SHIM = ROOT / "bin" / "compass-statusline"

SHAPES = {
    "gates is a number": "gates: 4\n",
    "gates is a mapping": "gates: {verify.correctness: pass}\n",
    "stages is a list": "stages: [assess, define]\n",
    "a stage weight is a number": "stages: {assess: full, define: 3, implement: full}\n",
}


def _env():
    return {k: v for k, v in os.environ.items()
            if k not in ("CLAUDECODE", "NO_COLOR", "COMPASS_COLOR", "COLUMNS")}


def _project(root: Path, line: str) -> None:
    task = root / ".compass" / "work" / "x"
    task.mkdir(parents=True)
    (root / ".compass" / "current-task").write_text("x\n")
    (task / "manifest.yml").write_text(
        "schema_version: '2.0'\nissue: x\nstatus: active\n" + line)
    (task / "delivery-approach.md").write_text("# Delivery approach - x\n")


@pytest.mark.parametrize("shape", list(SHAPES))
def test_next_names_a_stage_on_a_mistyped_manifest(tmp_path, shape):
    """A stage on stdout, exit 0 and nothing on stderr (TRC-001)."""
    _project(tmp_path, SHAPES[shape])
    r = subprocess.run([sys.executable, str(CLI), "next"], cwd=tmp_path,
                       capture_output=True, text=True, env=_env())
    assert (r.returncode, r.stderr) == (0, ""), (shape, r.stdout, r.stderr)
    assert r.stdout.strip(), shape


@pytest.mark.parametrize("shape", list(SHAPES))
def test_the_status_line_keeps_its_line(tmp_path, shape):
    """The status line prints its line rather than going blank (TRC-001)."""
    _project(tmp_path, SHAPES[shape])
    r = subprocess.run([str(SHIM)], input=json.dumps({"cwd": str(tmp_path)}),
                       capture_output=True, text=True, env=_env(), timeout=30)
    assert r.stdout.startswith("compass · x"), (shape, r.stdout)
