"""One tested place for the configuration code's file writes and reads.

The configuration rewrite stores each issue's resolved configuration as a
generation that must never be half written, and reads layer files where a
duplicated key would silently keep only its last value. `atomic_io` gives
it an atomic write, a lock, a strict YAML load that names the line of a
duplicate key, and canonical digests.

Scenario id: `TRC-001` (issue `atomic-io`).
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import atomic_io  # noqa: E402


def test_trc_001_a_write_replaces_the_file_whole(tmp_path):
    target = tmp_path / "resolved.yml"
    atomic_io.atomic_write_text(target, "a: 1\n")
    atomic_io.atomic_write_text(target, "a: 2\n")
    assert target.read_text(encoding="utf-8") == "a: 2\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["resolved.yml"]


def test_trc_001_a_failure_before_the_rename_leaves_the_old_file(tmp_path, monkeypatch):
    target = tmp_path / "resolved.yml"
    target.write_text("old\n", encoding="utf-8")

    def fail(*args, **kwargs):
        raise OSError("disk went away")

    monkeypatch.setattr(atomic_io.os, "replace", fail)
    with pytest.raises(OSError):
        atomic_io.atomic_write_text(target, "new\n")
    assert target.read_text(encoding="utf-8") == "old\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["resolved.yml"]


def test_trc_001_the_lock_lets_one_holder_in_at_a_time(tmp_path):
    lock = tmp_path / ".lock"
    inside, overlap = [], []

    def worker():
        with atomic_io.locked(lock):
            if inside:
                overlap.append(True)
            inside.append(True)
            threading.Event().wait(0.05)
            inside.pop()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert overlap == []


def test_trc_001_a_duplicate_key_is_refused_with_its_line(tmp_path):
    path = tmp_path / "compass.yml"
    path.write_text("extends: compass:default@6\nchecks:\n  a: 1\n  a: 2\n", encoding="utf-8")
    with pytest.raises(atomic_io.StrictYamlError) as raised:
        atomic_io.load_yaml_strict(path)
    message = str(raised.value)
    assert "duplicate key" in message and "'a'" in message and ":4" in message, message


def test_trc_001_strict_loading_reads_ordinary_yaml(tmp_path):
    path = tmp_path / "compass.yml"
    path.write_text("a: 1\nb: [x, y]\nc: {d: true}\n", encoding="utf-8")
    assert atomic_io.load_yaml_strict(path) == {"a": 1, "b": ["x", "y"], "c": {"d": True}}
    path.write_text("a: [unclosed\n", encoding="utf-8")
    with pytest.raises(atomic_io.StrictYamlError) as raised:
        atomic_io.load_yaml_strict(path)
    assert str(path) in str(raised.value)


def test_trc_001_equal_data_digests_alike():
    one = {"b": [1, 2], "a": {"y": None, "x": "é"}}
    two = {"a": {"x": "é", "y": None}, "b": [1, 2]}
    assert atomic_io.canonical_json(one) == atomic_io.canonical_json(two)
    assert atomic_io.digest(one) == atomic_io.digest(two)
    assert atomic_io.digest(one).startswith("sha256:") and len(atomic_io.digest(one)) == 71
    assert atomic_io.digest({"a": 1}) != atomic_io.digest({"a": 2})


def test_trc_001_the_module_imports_nothing_from_compass():
    # Every configuration module sits above it, and core will use it to save
    # manifests, so it must not import them back.
    source = (ROOT / "cli" / "compass_pkg" / "atomic_io.py").read_text(encoding="utf-8")
    assert "compass_pkg" not in source.replace("compass_pkg.atomic_io", "")
    assert os.path.basename(atomic_io.__file__) == "atomic_io.py"


def test_lm_1_a_date_digests_as_its_iso_string():
    import datetime
    assert atomic_io.canonical_json({"d": datetime.date(2026, 10, 5)}) == \
        atomic_io.canonical_json({"d": "2026-10-05"})
    stamp = datetime.datetime(2026, 10, 5, 12, 0, 0)
    assert atomic_io.canonical_json([stamp]) == atomic_io.canonical_json([stamp.isoformat()])


def test_lm_1_a_value_json_cannot_hold_is_refused_naming_its_type():
    with pytest.raises(TypeError, match="set"):
        atomic_io.canonical_json({"x": {1, 2}})
