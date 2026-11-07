"""Only a project's own `compass.yml` can hold the `language` setting.

A parent or a preset refuses the key, and the shipped default sets none. An
issue has no configuration of its own in 9.0.0 (ADR-094), so the case of an
issue layer that names it went with `compass issue configure`. The scenario number in each test name is from the
acceptance criteria of the issue `language-key-and-us-english`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from compass_pkg import layers  # noqa: E402
from compass_pkg.atomic_io import load_yaml_strict  # noqa: E402
from test_framework_compass_yml import disallowed_keys  # noqa: E402

REAL_GIT = "/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin"
PARENT_RULE = "belongs in the project's own compass.yml, never in a parent (ADR-043)"
PRESETS = ROOT / "governance" / "presets"


def _run(cwd, *argv, extra_env=None):
    env = {"PATH": os.environ.get("PATH", REAL_GIT), "HOME": str(cwd), "LANG": "C.UTF-8",
           "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "PYTHONDONTWRITEBYTECODE": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    env.update(extra_env or {})
    done = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=180)
    return done.returncode, done.stdout + done.stderr


def test_trc_011(tmp_path):
    # A local parent: the chain refuses it before anything merges.
    try:
        layers.build_chain(parent={"schema": 1, "language": "en-US"}, parent_name="local")
    except layers.CompassError as exc:
        assert "language" in str(exc) and PARENT_RULE in str(exc), str(exc)
    else:
        raise AssertionError("a local parent holding language was accepted")
    # A git parent can no longer hold it: 9.0.0 removed git parents (ADR-094),
    # so the lint and `policy show` refuse the `extends:` before any parent is
    # read, and name the code and the fix.
    root = tmp_path / "project"
    (root / ".compass").mkdir(parents=True)
    (root / "compass.yml").write_text(
        yaml.safe_dump({"schema": 1, "extends": f"github:acme/bank@1.2.0#{'a' * 40}"}),
        encoding="utf-8")
    code, out = _run(root, "policy", "lint")
    assert code == 1 and "L-PARENT-REMOVED [project] extends" in out, out
    code, out = _run(root, "policy", "show")
    assert code == 2 and "L-PARENT-REMOVED" in out and "delete extends:" in out, out


def _top_level_language(preset_dir):
    """The YAML files under `preset_dir` that hold a top-level `language` key.
    A nested key of that name, such as a parameter of a check, is not one."""
    found = []
    for path in sorted(Path(preset_dir).rglob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and "language" in doc:
            found.append(path.name)
    return found


def test_trc_013(tmp_path):
    folders = [PRESETS / "default", PRESETS / "default@6"]
    for folder in folders:
        assert list(folder.rglob("*.yml")), folder
        assert _top_level_language(folder) == [], folder
    planted = tmp_path / "default"
    shutil.copytree(PRESETS / "default", planted)
    with open(planted / "preset.yml", "a", encoding="utf-8") as fh:
        fh.write("language: en-US\n")
    assert _top_level_language(planted) == ["preset.yml"]


def test_trc_014():
    doc = load_yaml_strict(str(ROOT / "compass.yml"))
    assert doc["language"] == "en-US"
    assert disallowed_keys(doc) == []
    assert disallowed_keys(dict(doc, checks={})) == ["checks"]
    code, out = _run(ROOT, "policy", "lint")
    assert code == 0, out
