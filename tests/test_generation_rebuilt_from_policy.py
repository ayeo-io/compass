"""A missing generation folder is rebuilt from the manifest's `policy:` block
(#356, ADR-096 decision 5, plan section 6).

#356 keeps the generation folders (`generations/<n>/`) out of the commit, so a
fresh clone of a committed issue has the manifest and no folder. The manifest's
`policy:` block names what the folder was resolved from: the check set and its
sha256, the tighten-only settings applied, the autonomy and the digest of
`resolved.yml`. These tests make real issues with the CLI, delete the folder,
change `compass.yml` so a rebuild that read it would differ, and check that:

- each of the 13 shapes measured for #356 step 1 rebuilds to the same digest,
  with the same bytes in `resolved.yml`, and the folder is written back;
- `compass check` gives the same rows after the rebuild as before;
- a tampered `policy.tightened` and a check set whose sha256 differs are
  refused as broken, with the reason;
- a block without `autonomy` (written on v9 before #356 step 8) is rebuilt by
  trying the three values;
- a partial folder and a manifest with no `policy:` block are refused as
  before.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
CLI = ROOT / "cli" / "compass"
SLUG = "demo"

ALL_FIVE = """signoff_labels: [billing]
require_evidence:
  - when: {risk: [cross-cutting, critical]}
    add: [reproduce-first]
agent_review: on
project_checks:
  - id: arch-fitness
    name: Architecture fitness
    command: python3 scripts/arch-fitness.py
    stage: build
capabilities:
  entry-exit-evaluation: true
"""

# (name, compass.yml at start, labels, compass.yml for a reassess). The 13 shapes
# the #356 step 1 measurement ran.
SHAPES = [
    ("no-compass-yml", None, [], None),
    ("no-tightening", "schema: 1\n", [], None),
    ("signoff-labels", "schema: 1\nsignoff_labels: [billing]\n", ["billing"], None),
    ("require-evidence", "schema: 1\nrequire_evidence:\n  - when: {risk: [contained]}\n"
                         "    add: [reproduce-first]\n", [], None),
    ("agent-review", "schema: 1\nagent_review: on\n", [], None),
    ("project-checks", "schema: 1\nproject_checks:\n  - id: arch-fitness\n"
                       "    name: Architecture fitness\n    command: python3 x.py\n"
                       "    stage: build\n", [], None),
    ("capabilities", "schema: 1\ncapabilities:\n  entry-exit-evaluation: true\n", [], None),
    ("two-settings-labelled", "schema: 1\nsignoff_labels: [billing]\nrequire_evidence:\n"
                              "  - when: {risk: [contained]}\n    add: [reproduce-first]\n",
     ["billing"], None),
    ("all-five-settings", "schema: 1\n" + ALL_FIVE, ["billing"], None),
    ("shipped-label", None, ["auth"], None),
    ("reassess-to-generation-2", "schema: 1\n", [],
     "schema: 1\nagent_review: on\nsignoff_labels: [billing]\n"),
    ("autonomy-controlled", "schema: 1\nautonomy: controlled\n", [], None),
    ("autonomy-autonomous", "schema: 1\nautonomy: autonomous\n", [], None),
]


def _env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "100",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def _run(cwd, *argv):
    r = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=_env(cwd),
                       capture_output=True, text=True, timeout=180)
    return r.returncode, r.stdout, r.stderr


def _issue(root, compass_yml=None, labels=(), reassess_yml=None):
    """A real path issue made with `quick-fix start`, and its directory."""
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    if compass_yml is not None:
        (root / "compass.yml").write_text(compass_yml, encoding="utf-8")
    argv = ["quick-fix", "start", "--risk", "contained - a test",
            "--familiarity", "brownfield-mapped - a test", "--size", "small - a test",
            "--goal", "delivery - a test", "--intent", "Add a thing",
            "--scenario", "Given x When y Then z", "--test", "tests/test_x.py"]
    if labels:
        argv += ["--labels", ",".join(labels)]
    code, out, err = _run(root, *argv, SLUG)
    assert code == 0, out + err
    if reassess_yml is not None:
        (root / "compass.yml").write_text(reassess_yml, encoding="utf-8")
        code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write",
                              "--reason", "a test")
        assert code == 0, out + err
    return root / ".compass" / "work" / SLUG


def _manifest(task_dir):
    return yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))


def _write_manifest(task_dir, manifest):
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False),
                                           encoding="utf-8")


def _as_a_fresh_clone_has_it(root, task_dir):
    """Delete the generation folders, as a clone of a committed issue has none, and
    change `compass.yml`, so a rebuild that read it would not match."""
    shutil.rmtree(task_dir / "generations")
    (root / "compass.yml").write_text("schema: 1\nsignoff_labels: [unrelated]\n",
                                      encoding="utf-8")


def _folder(task_dir, n):
    return task_dir / "generations" / str(n)


def _marker(task_dir, n):
    return yaml.safe_load((_folder(task_dir, n) / "complete").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name,compass_yml,labels,reassess_yml", SHAPES,
                         ids=[s[0] for s in SHAPES])
def test_each_measured_shape_rebuilds_to_the_same_digest(tmp_path, name, compass_yml,
                                                         labels, reassess_yml):
    from compass_pkg import effective
    task_dir = _issue(tmp_path, compass_yml, labels, reassess_yml)
    manifest = _manifest(task_dir)
    n = manifest["generation"]
    original = (_folder(task_dir, n) / "resolved.yml").read_bytes()
    _as_a_fresh_clone_has_it(tmp_path, task_dir)

    view = effective.effective_for(str(task_dir))

    assert (view.source, view.generation) == ("generation", n)
    assert _marker(task_dir, n)["files"]["resolved.yml"] == manifest["policy"]["resolved"]
    assert (_folder(task_dir, n) / "resolved.yml").read_bytes() == original
    provenance = yaml.safe_load((_folder(task_dir, n) / "provenance.yml")
                                .read_text(encoding="utf-8"))
    assert provenance["restored_from"] == "policy"
    # The manifest is not changed by a rebuild.
    assert _manifest(task_dir) == manifest


def test_the_policy_block_names_the_autonomy(tmp_path):
    task_dir = _issue(tmp_path, "schema: 1\nautonomy: controlled\n")
    assert _manifest(task_dir)["policy"]["autonomy"] == "controlled"


def _rows(out):
    data = json.loads(out)
    return sorted((c["guardrail"], c["name"], c["status"]) for c in data["checks"])


def test_compass_check_gives_the_same_rows_after_the_rebuild(tmp_path):
    task_dir = _issue(tmp_path, "schema: 1\nsignoff_labels: [billing]\n", ["billing"])
    before = _run(tmp_path, "check", "--issue", SLUG, "--json")
    _as_a_fresh_clone_has_it(tmp_path, task_dir)
    after = _run(tmp_path, "check", "--issue", SLUG, "--json")
    assert after[0] == before[0], after[1] + after[2]
    assert _rows(after[1]) == _rows(before[1])
    assert (_folder(task_dir, 1) / "complete").is_file()
    # The rebuilt folder takes the verdicts, as the original did.
    assert (_folder(task_dir, 1) / "results.yml").is_file()


def _refused(task_dir):
    from compass_pkg import effective
    from compass_pkg.core import CompassError
    with pytest.raises(CompassError) as caught:
        effective.effective_for(str(task_dir))
    return str(caught.value)


def test_a_tampered_tightened_is_refused_with_both_digests(tmp_path):
    task_dir = _issue(tmp_path, "schema: 1\nsignoff_labels: [billing]\n", ["billing"])
    manifest = _manifest(task_dir)
    manifest["policy"]["tightened"] = {"signoff_labels": ["other"]}
    _write_manifest(task_dir, manifest)
    _as_a_fresh_clone_has_it(tmp_path, task_dir)
    message = _refused(task_dir)
    assert "broken: its folder is missing" in message
    assert manifest["policy"]["resolved"] in message
    assert "could not be rebuilt" in message
    assert not _folder(task_dir, 1).exists()


def test_a_check_set_whose_sha256_differs_is_refused(tmp_path):
    task_dir = _issue(tmp_path)
    manifest = _manifest(task_dir)
    manifest["policy"]["check_set_sha256"] = "0" * 64
    _write_manifest(task_dir, manifest)
    _as_a_fresh_clone_has_it(tmp_path, task_dir)
    message = _refused(task_dir)
    assert "broken: its folder is missing" in message
    assert f"does not hold {manifest['policy']['check_set']} (sha256 000000000000)" in message
    assert not _folder(task_dir, 1).exists()


def test_a_check_set_this_compass_does_not_hold_is_refused(tmp_path):
    task_dir = _issue(tmp_path)
    manifest = _manifest(task_dir)
    manifest["policy"]["check_set"] = "compass-checks@8.9.9"
    _write_manifest(task_dir, manifest)
    _as_a_fresh_clone_has_it(tmp_path, task_dir)
    message = _refused(task_dir)
    assert "does not hold compass-checks@8.9.9" in message


@pytest.mark.parametrize("autonomy", ["controlled", "balanced", "autonomous"])
def test_a_block_without_autonomy_is_rebuilt_by_trying_the_three_values(tmp_path, autonomy):
    from compass_pkg import effective
    task_dir = _issue(tmp_path, f"schema: 1\nautonomy: {autonomy}\n")
    manifest = _manifest(task_dir)
    del manifest["policy"]["autonomy"]
    _write_manifest(task_dir, manifest)
    _as_a_fresh_clone_has_it(tmp_path, task_dir)
    view = effective.effective_for(str(task_dir))
    assert view.autonomy == autonomy
    assert _marker(task_dir, 1)["files"]["resolved.yml"] == manifest["policy"]["resolved"]


def test_a_recorded_autonomy_that_is_wrong_is_refused(tmp_path):
    task_dir = _issue(tmp_path, "schema: 1\nautonomy: controlled\n")
    manifest = _manifest(task_dir)
    manifest["policy"]["autonomy"] = "autonomous"
    _write_manifest(task_dir, manifest)
    _as_a_fresh_clone_has_it(tmp_path, task_dir)
    assert "could not be rebuilt" in _refused(task_dir)


def test_a_partial_folder_is_refused_as_before(tmp_path):
    task_dir = _issue(tmp_path)
    (_folder(task_dir, 1) / "complete").unlink()
    message = _refused(task_dir)
    assert "broken: its complete marker is missing" in message
    assert not (_folder(task_dir, 1) / "complete").exists()


def test_no_policy_block_is_refused_as_before(tmp_path):
    task_dir = _issue(tmp_path)
    manifest = _manifest(task_dir)
    del manifest["policy"]
    _write_manifest(task_dir, manifest)
    _as_a_fresh_clone_has_it(tmp_path, task_dir)
    message = _refused(task_dir)
    assert "broken: its folder is missing" in message
    assert "could not be rebuilt" not in message
    assert not _folder(task_dir, 1).exists()


def test_check_set_held_finds_an_earlier_release_under_governance_check_sets(tmp_path):
    from compass_pkg import check_set
    shipped = check_set.path()
    earlier = tmp_path / "governance" / "check-sets" / "compass-checks@8.9.9.yml"
    earlier.parent.mkdir(parents=True)
    earlier.write_text(Path(shipped).read_text(encoding="utf-8")
                       .replace("version: 9.0.0", "version: 8.9.9", 1)
                       .replace("version: \"9.0.0\"", "version: \"8.9.9\"", 1),
                       encoding="utf-8")
    sha = check_set.sha256(str(earlier))
    doc, reason = check_set.held("compass-checks@8.9.9", sha, root=str(tmp_path))
    assert reason == "" and doc["version"] == "8.9.9"
    doc, reason = check_set.held("compass-checks@8.9.9", "0" * 64, root=str(tmp_path))
    assert doc is None and "does not hold compass-checks@8.9.9" in reason
