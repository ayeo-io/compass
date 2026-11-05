"""A removed `compass.yml` key is named as removed, and its value is not checked (ADR-091).

9.0.0 removed the keys `living_spec` and `artifacts`. Nothing reads them, so a value
the old schema refused, such as `living_spec: on-ship`, must not make the project
file invalid: an invalid file stops every command with "nothing can be resolved".
`compass policy lint` gives only the `L-SETTING-REMOVED` warning.

Issue: ayeo-io/compass-delivery#353.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"


def _lint(tmp_path, body):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
    subprocess.run([sys.executable, str(CLI), "init"], cwd=tmp_path, env=env,
                   capture_output=True, text=True)
    (tmp_path / "compass.yml").write_text("schema: 1\nowner: jed\n" + body, encoding="utf-8")
    result = subprocess.run([sys.executable, str(CLI), "policy", "lint"], cwd=tmp_path,
                            env=env, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


@pytest.mark.parametrize("body, key", [
    ("living_spec: on-ship\n", "living_spec"),
    ("artifacts: 5\n", "artifacts"),
    ("artifacts:\n  intent: {sections: 4}\n", "artifacts"),
])
def test_a_removed_key_with_a_bad_value_gives_only_the_removed_warning(tmp_path, body, key):
    code, out = _lint(tmp_path, body)
    assert code == 0, out
    assert "L-SCHEMA" not in out, out
    assert f"L-SETTING-REMOVED [project] {key}" in out, out
