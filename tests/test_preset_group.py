"""The `compass preset` group: `preset init` and `preset test` (scenario group F).

Neither old spelling, `policy test` or `policy init-preset`, is in a release,
so neither has an alias. Each is an unknown command whose error names the new
spelling, and each new verb does what the old one did.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

FOUR_FILES = {"compass.yml", "compass-fixtures/example.yml", "README.md", ".gitignore"}


def _run(args, cwd):
    env = dict(os.environ)
    env.pop("COMPASS_ISSUE", None)
    proc = subprocess.run([sys.executable, str(CLI), *args], cwd=str(cwd),
                          capture_output=True, text=True, env=env, timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


def _files(folder):
    return {p.relative_to(folder).as_posix() for p in folder.rglob("*")
            if p.is_file() and ".git" not in p.parts}


@pytest.fixture
def preset(tmp_path):
    folder = tmp_path / "team-preset"
    _run(["preset", "init", str(folder), "--owner", "acme-team"], tmp_path)
    return folder


def _scaffolded(folder):
    """Checked in the test body, so a failed scaffold is a failed test and not
    a setup error."""
    assert (folder / "compass.yml").is_file(), "preset init wrote no compass.yml"


# --- VR-F1 -----------------------------------------------------------------

def test_vr_f1_preset_init_writes_the_four_files_in_an_empty_folder(tmp_path):
    folder = tmp_path / "team-preset"
    folder.mkdir()
    rc, out, err = _run(["preset", "init", str(folder), "--owner", "acme-team"], tmp_path)
    assert rc == 0, (out, err)
    assert _files(folder) == FOUR_FILES
    assert "acme-team" in (folder / "compass.yml").read_text(encoding="utf-8")


def test_vr_f1_the_scaffold_holds_no_retired_word(preset):
    from compass_pkg import word_map
    text = "\n".join((preset / name).read_text(encoding="utf-8")
                     for name in sorted(_files(preset)))
    words = {old for _field, old, _new in word_map.retired_triples()}
    found = sorted(w for w in words if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", text))
    assert not found, f"the scaffold uses retired words: {found}"


def test_vr_f1_the_scaffold_passes_preset_test_where_it_stands(preset, tmp_path):
    rc, out, err = _run(["preset", "test", str(preset)], tmp_path)
    assert rc == 0, (out, err)


def test_vr_f1_preset_init_refuses_to_overwrite_and_writes_nothing(preset, tmp_path):
    before = {name: (preset / name).read_text(encoding="utf-8") for name in _files(preset)}
    rc, out, err = _run(["preset", "init", str(preset), "--owner", "acme-team"], tmp_path)
    assert rc == 1, (out, err)
    assert before == {name: (preset / name).read_text(encoding="utf-8")
                      for name in _files(preset)}


# --- VR-F2 -----------------------------------------------------------------

def test_vr_f2_preset_test_json_equals_the_report_the_module_builds(preset, tmp_path):
    from compass_pkg import preset_test, replay
    _scaffolded(preset)
    rc, out, err = _run(["preset", "test", str(preset), "--json", "--offline"], tmp_path)
    assert rc == 0, (out, err)
    expected = preset_test.report_json(
        preset_test.run(str(preset), replay.evaluate, fetch=False))
    assert json.loads(out) == expected


def test_vr_f2_preset_test_text_equals_the_report_the_module_builds(preset, tmp_path):
    from compass_pkg import preset_test, replay
    _scaffolded(preset)
    rc, out, err = _run(["preset", "test", str(preset), "--offline"], tmp_path)
    expected = preset_test.text(preset_test.run(str(preset), replay.evaluate, fetch=False))
    assert rc == 0 and out.strip() == "\n".join(expected).strip(), (out, expected)


def test_vr_f2_exit_codes_are_the_old_ones(preset, tmp_path):
    _scaffolded(preset)
    fixture = preset / "compass-fixtures" / "example.yml"
    data = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    data["expect"]["approach"] = "full-delivery"
    fixture.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert _run(["preset", "test", str(preset), "--offline"], tmp_path)[0] == 1
    assert _run(["preset", "test", str(tmp_path / "missing"), "--offline"], tmp_path)[0] == 2


# --- VR-F3 -----------------------------------------------------------------

@pytest.mark.parametrize("old,new", [
    (["policy", "test"], "preset test"),
    (["policy", "init-preset", "somewhere", "--owner", "acme-team"], "preset init"),
])
def test_vr_f3_the_old_spelling_is_unknown_and_names_the_new_one(tmp_path, old, new):
    rc, out, err = _run(old, tmp_path)
    assert rc == 2, (out, err)
    assert out == ""
    assert f"is now '{new}'" in err, err
    assert "works until 7.0.0" not in err
    assert not (tmp_path / "somewhere").exists()


# --- VR-F4 -----------------------------------------------------------------

def test_vr_f4_preset_help_lists_init_and_test(tmp_path):
    rc, out, err = _run(["preset", "--help"], tmp_path)
    assert rc == 0, err
    match = re.search(r"\{([a-z,\-]+)\}", out)
    assert match and set(match.group(1).split(",")) == {"init", "test"}, out


def test_vr_f4_the_policy_group_no_longer_lists_the_old_verbs(tmp_path):
    rc, out, err = _run(["policy", "--help"], tmp_path)
    assert rc == 0, err
    listed = set(re.search(r"\{([a-z,\-]+)\}", out).group(1).split(","))
    assert not listed & {"test", "init-preset"}, listed
    assert "preset" in _run(["--help"], tmp_path)[1]
