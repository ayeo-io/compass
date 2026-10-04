"""`make test-clean` runs the suite where CI does: a clean clone.

`.compass/work/` and other local state are gitignored, so a test that reads
them passes on the author's machine and fails on every other one, and the
signal arrives in CI after the push (#122). The target clones the committed
HEAD into a temporary folder and runs the suite there. `CLEAN_TARGET` names
the target to run in the clone; it is `test` unless a caller sets it.

Scenario id: CC-1 (issue `suite-from-a-clean-clone`).
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _recipe():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    m = re.search(r"^test-clean:.*\n((?:\t.*\n?)+)", text, re.M)
    assert m, "the Makefile has no test-clean target"
    return m.group(0)


def test_cc_1_the_target_clones_head_and_runs_the_suite_there():
    recipe = _recipe()
    assert "git clone" in recipe
    assert "mktemp -d" in recipe and "rm -rf" in recipe
    assert "$(CLEAN_TARGET)" in recipe
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert re.search(r"^CLEAN_TARGET \?= test$", text, re.M)


def test_cc_1_make_runs_inside_a_clone_that_is_then_removed(tmp_path):
    # `help` stands in for the suite: it proves the clone is made and make
    # runs inside it, in seconds rather than the suite's minutes.
    r = subprocess.run(["make", "-s", "test-clean", "CLEAN_TARGET=help"],
                       cwd=ROOT, capture_output=True, text=True, timeout=300,
                       env={**os.environ, "TMPDIR": str(tmp_path)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "test-clean" in r.stdout, r.stdout
    assert "running in a clean clone" in r.stdout
    assert list(tmp_path.iterdir()) == [], "the clone was not removed"


def test_cc_1_contributing_names_the_command():
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "make test-clean" in text
