"""Two interfaces a team layer relies on, kept after 9.0.0 removed the preset verbs.

The classification of a git parent chain against the shipped default, stored in
`versions.yml` (PI-3), and the map form of `extends:` with the reserved
`preset:` key (PI-5). `compass preset test` and `compass policy diff`, which
PI-1, PI-2 and PI-4 covered, were removed in 9.0.0 (ADR-094). These tests run
the CLI in a temporary folder and, for a git parent, point
`COMPASS_PARENT_REMOTE_BASE` at a local repository, so nothing reaches the
network.

Scenario ids: `PI-3`, `PI-5` and `PI-6`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))


def _parent(doc, **over):
    return {"schema": 1, "owner": "acme-team", **doc, **over}


def test_pi_3_the_shipped_default_has_no_classification_and_a_project_without_a_parent_none(
        tmp_path, monkeypatch):
    from parent_fixtures import commit, issue_project
    root, task_dir = issue_project(tmp_path, "compass:default@6")
    monkeypatch.chdir(root)
    assert commit(task_dir).committed
    stored = yaml.safe_load((task_dir / "generations" / "1" / "versions.yml")
                            .read_text(encoding="utf-8"))
    assert all("classification" not in p for p in stored["parents"])


def test_pi_3_more_than_eight_named_labels_give_an_incomplete_incomparable_block():
    # A commit refuses such a chain at the lint (it cannot prove the locks), so the
    # function is called directly: the block must still say the grid was not run.
    from compass_pkg import chain_class, layers, policy_lint
    shipped, _ = policy_lint.load_parent()
    names = [f"label{i}" for i in range(6)]
    doc = _parent({"rules": {"mine": {"kind": "floors", "hit": {"force_minimum_approach": "max"},
                                      "rules": {"R1": {
                                          "order": 1, "when": {"labels_any": names},
                                          "then": {"force_minimum_approach": "full"}}}}}})
    layer = layers.Layer("p", "parent", doc, layers.layer_digest(doc, "parent"))
    found = chain_class.classify_chain(shipped, [layer], "compass:default@6")[0]
    assert found["complete"] is False
    assert found["result"] == "incomparable"
    assert found["points"] == 0


def test_pi_5_the_schema_marks_approved_on_as_a_date():
    schema = json.loads((ROOT / "schemas" / "compass.schema.json").read_text(encoding="utf-8"))
    option = schema["properties"]["extends"]["oneOf"][1]
    assert option["properties"]["approved_on"]["format"] == "date"


def test_pi_6_no_merge_conflict_marker_is_left_in_the_tracked_sources():
    import subprocess
    files = subprocess.run(["git", "ls-files", "cli", "docs", "schemas", "tests"], cwd=ROOT,
                           capture_output=True, text=True).stdout.split()
    left = []
    for name in files:
        path = ROOT / name
        if path.suffix not in (".py", ".md", ".yml", ".json") or not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith(("<<<<<<< ", ">>>>>>>> ")) or line == "=======":
                left.append(f"{name}:{number}")
    assert left == []


# Moved from the tests of `compass policy update`, which 9.0.0 removed: the
# spelling of `extends: compass:default@<n>` is still read by
# `acceptance_strategy.pinned_below` and the resolver.

def test_up_9_extends_is_read_and_written_by_one_pair_of_functions():
    from compass_pkg import layers
    from compass_pkg.core import CompassError
    parse, write = layers.parse_extends, layers.default_extends
    assert parse("compass:default@6") == ("default", 6)
    assert write(7) == "compass:default@7"
    assert parse(write(12)) == ("default", 12)
    for bad in ("compass:default@6.0.0", "compass:default", "default@6", "compass:default@x",
                "github:a/b@main#abc", None, 6):
        with pytest.raises(CompassError):
            parse(bad)
