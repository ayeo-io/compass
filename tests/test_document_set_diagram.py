"""The document-set diagram is rendered from `scripts/render-document-set.py`
and the committed copy cannot go stale.

`architecture/document-set-7-0-0.svg` is the picture of the documents each
stage writes. It is generated, so a change to the picture is a change to the
script, and a test fails when the two differ. The render is deterministic:
two runs give the same bytes.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "render-document-set.py"
COMMITTED = ROOT / "architecture" / "document-set-7-0-0.svg"


def _module():
    spec = importlib.util.spec_from_file_location("render_document_set", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_committed_diagram_matches_a_fresh_render():
    assert COMMITTED.is_file(), "architecture/document-set-7-0-0.svg is missing"
    assert COMMITTED.read_text(encoding="utf-8") == _module().render(), (
        "architecture/document-set-7-0-0.svg is stale: run scripts/render-document-set.py")


def test_two_renders_are_identical_and_name_every_stage():
    mod = _module()
    first, second = mod.render(), mod.render()
    assert first == second
    for stage in mod.STAGES:
        assert f">{stage}<" in first, f"the diagram has no {stage} column"
    assert "\u2014" not in first, "no em dash, in the diagram either"


def test_check_mode_passes_on_the_committed_file_and_fails_on_a_changed_one(tmp_path):
    ok = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
    stale = tmp_path / "stale.svg"
    stale.write_text("<svg/>", encoding="utf-8")
    bad = subprocess.run([sys.executable, str(SCRIPT), "--check", "--out", str(stale)],
                         capture_output=True, text=True)
    assert bad.returncode == 1
    assert "is stale" in bad.stderr
