"""Concurrent manifest saves keep both changes, and a reader never sees part
of a manifest.

Scenario ids `TRC-A1` to `TRC-A13` and `TRC-B1` to `TRC-B3` (issue `manifest-writes-atomic-and-locked`).
Each test name starts with its scenario id.

The writers in group A are threads. Each loads the manifest, then all meet at
a barrier, so every writer holds the same version before any of them saves.
The saves then run in a fixed order, so each test is deterministic.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
CLI_DIR = HERE.parent / "cli"
sys.path.insert(0, str(CLI_DIR))
import compass_pkg  # noqa: E402,F401  (puts the bundled PyYAML first)
import yaml  # noqa: E402
from compass_pkg import atomic_io, core, manifest_store, session_record  # noqa: E402

MANIFEST = """\
schema_version: '3.0'
issue: probe
gates:
- id: verify.correctness
  status: pending
  evidence: []
evidence:
- id: EV-1
  type: test-run
  path: evidence/one.txt
follow_ups: []
"""


@pytest.fixture
def task_dir(tmp_path):
    folder = tmp_path / ".compass" / "work" / "probe"
    folder.mkdir(parents=True)
    (folder / "manifest.yml").write_text(MANIFEST, encoding="utf-8")
    return str(folder)


def on_disk(task_dir):
    with open(os.path.join(task_dir, "manifest.yml"), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def run_writers(task_dir, *changes):
    """Run one thread per change. Every thread loads the manifest, waits until
    all have loaded, then applies its change and saves, in the order given.
    Returns the exception each writer raised, or None."""
    loaded = threading.Barrier(len(changes))
    turns = [threading.Event() for _ in changes]
    turns[0].set()
    errors = [None] * len(changes)

    def writer(n, change):
        task, path = core.load_manifest(task_dir)
        loaded.wait(timeout=10)
        turns[n].wait(timeout=10)
        try:
            change(task)
            core.save_manifest(task, path)
        except Exception as exc:                        # noqa: BLE001 - reported to the test
            errors[n] = exc
        finally:
            if n + 1 < len(turns):
                turns[n + 1].set()

    threads = [threading.Thread(target=writer, args=(n, c)) for n, c in enumerate(changes)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    assert not any(t.is_alive() for t in threads), "a writer did not finish"
    return errors


def test_trc_a1_two_writers_keep_both_changes(task_dir):
    def first(task):
        task["release_note"] = "Set by the first writer."

    def second(task):
        task["follow_ups"] = [{"id": "FU-1", "summary": "set by the second writer"}]

    assert run_writers(task_dir, first, second) == [None, None]
    body = on_disk(task_dir)
    assert body["release_note"] == "Set by the first writer."
    assert body["follow_ups"] == [{"id": "FU-1", "summary": "set by the second writer"}]


def test_trc_a2_hook_session_kept(task_dir):
    task, path = core.load_manifest(task_dir)
    session_record.record(task_dir, "session-from-the-hook", via="env")
    assert on_disk(task_dir)["usage"]["sessions"] == ["session-from-the-hook"]
    task["release_note"] = "Set by the command."
    core.save_manifest(task, path)
    body = on_disk(task_dir)
    assert body["usage"]["sessions"] == ["session-from-the-hook"]
    assert body["release_note"] == "Set by the command."


def test_trc_a3_both_list_additions_kept(task_dir):
    def first(task):
        task["evidence"].append({"id": "EV-2", "type": "test-run", "path": "evidence/two.txt"})

    def second(task):
        task["evidence"].append({"id": "EV-3", "type": "test-run", "path": "evidence/three.txt"})

    assert run_writers(task_dir, first, second) == [None, None]
    assert [e["id"] for e in on_disk(task_dir)["evidence"]] == ["EV-1", "EV-2", "EV-3"]


def test_trc_a4_same_value_refused(task_dir):
    def first(task):
        task["gates"][0]["status"] = "pass"

    def second(task):
        task["gates"][0]["status"] = "fail"

    errors = run_writers(task_dir, first, second)
    assert errors[0] is None
    assert isinstance(errors[1], manifest_store.ManifestConflict), errors
    assert "gates" in str(errors[1]) and "status" in str(errors[1]), errors[1]
    assert "nothing was written" in str(errors[1])
    assert on_disk(task_dir)["gates"][0]["status"] == "pass"


def test_trc_a5_unchanged_file_written_as_given(task_dir):
    task, path = core.load_manifest(task_dir)
    del task["follow_ups"]
    core.save_manifest(task, path)
    task["gates"][0]["status"] = "pass"
    core.save_manifest(task, path)
    body = on_disk(task_dir)
    assert "follow_ups" not in body
    assert body["gates"][0]["status"] == "pass"
    assert body == task


#: Reads the manifest named by argv[1] from a second process and prints its
#: length and whether it parses to the issue's mapping.
READER = r"""
import sys
sys.path.insert(0, sys.argv[2])
import compass_pkg  # noqa: F401
import yaml
text = open(sys.argv[1], encoding="utf-8").read()
body = yaml.safe_load(text)
print(len(text), isinstance(body, dict) and body.get("issue") == "probe")
"""


def test_trc_b1_reader_sees_whole_manifest(task_dir, monkeypatch):
    path = os.path.join(task_dir, "manifest.yml")
    size = os.path.getsize(path)
    seen = []
    real_dump = yaml.safe_dump

    def dump_with_a_reader(*args, **kwargs):
        # Every manifest save calls safe_dump. A second process reads the
        # file at that moment, while the save is under way.
        done = subprocess.run([sys.executable, "-c", READER, path, str(CLI_DIR)],
                              capture_output=True, text=True, timeout=60)
        seen.append(done.stdout.strip() or done.stderr)
        return real_dump(*args, **kwargs)

    task, _ = core.load_manifest(task_dir)
    task["release_note"] = "A new line."
    monkeypatch.setattr(yaml, "safe_dump", dump_with_a_reader)
    core.save_manifest(task, path)
    monkeypatch.undo()
    assert seen, "the save did not dump the manifest"
    assert all(line == f"{size} True" for line in seen), seen
    assert on_disk(task_dir)["release_note"] == "A new line."


def test_trc_b2_read_takes_no_lock(task_dir):
    result = []
    lock = os.path.join(task_dir, core.MANIFEST_LOCK)
    with atomic_io.locked(lock):
        reader = threading.Thread(target=lambda: result.append(core.load_manifest(task_dir)))
        reader.start()
        reader.join(timeout=5)
        finished = not reader.is_alive()
    reader.join(timeout=5)
    assert finished, "load_manifest waited for the manifest lock"
    assert result[0][0]["issue"] == "probe"


def other_writer(task_dir, change):
    """Load, change and save the manifest, as a second command would."""
    task, path = core.load_manifest(task_dir)
    change(task)
    core.save_manifest(task, path)


def test_trc_a6_records_with_an_id_merge_by_id(task_dir):
    # The other writer puts a record in front, so every position moves; this
    # writer changes EV-1. Matched by position, the change would land on EV-0.
    task, path = core.load_manifest(task_dir)
    other_writer(task_dir, lambda t: t["evidence"].insert(
        0, {"id": "EV-0", "type": "test-run", "path": "evidence/zero.txt"}))
    task["evidence"][0]["path"] = "evidence/one-again.txt"
    core.save_manifest(task, path)
    assert on_disk(task_dir)["evidence"] == [
        {"id": "EV-0", "type": "test-run", "path": "evidence/zero.txt"},
        {"id": "EV-1", "type": "test-run", "path": "evidence/one-again.txt"}]


def test_trc_a6_a_record_removed_and_changed_is_refused(task_dir):
    # This writer replaces the gate set while the other passes the old gate.
    # Dropping the pass would lose an update, and keeping it on the new gate
    # would make a record nobody wrote, so the save stops and writes nothing.
    task, path = core.load_manifest(task_dir)
    other_writer(task_dir, lambda t: t["gates"][0].update(status="pass"))
    before = open(path, "rb").read()
    task["gates"] = [{"id": "verify.security", "status": "pending", "evidence": []}]
    with pytest.raises(manifest_store.ManifestConflict) as raised:
        core.save_manifest(task, path)
    assert "verify.correctness" in str(raised.value)
    assert open(path, "rb").read() == before


def test_trc_a6_a_record_removed_and_left_alone_stays_removed(task_dir):
    task, path = core.load_manifest(task_dir)
    other_writer(task_dir, lambda t: t["evidence"].append(
        {"id": "EV-2", "type": "test-run", "path": "evidence/two.txt"}))
    task["evidence"] = [e for e in task["evidence"] if e["id"] != "EV-1"]
    core.save_manifest(task, path)
    assert on_disk(task_dir)["evidence"] == [
        {"id": "EV-2", "type": "test-run", "path": "evidence/two.txt"}]


def test_trc_a6_a_position_both_changed_without_an_id_is_refused(task_dir):
    base = {"notes": [{"text": "a"}, {"text": "b"}]}
    ours = {"notes": [{"text": "a", "by": "x"}, {"text": "b"}]}
    theirs = {"notes": [{"text": "z"}, {"text": "b"}]}
    with pytest.raises(manifest_store.ManifestConflict):
        manifest_store.merge_manifest(base, ours, theirs)


def test_trc_a7_saves_after_a_merged_save_keep_this_writers_changes(task_dir):
    task, path = core.load_manifest(task_dir)
    session_record.record(task_dir, "session-from-the-hook", via="env")
    task["gates"][0]["status"] = "pass"
    task["release_note"] = "draft"
    task["evidence"].append({"id": "EV-2", "type": "test-run", "path": "a"})
    core.save_manifest(task, path)                      # merges the hook's write
    task["gates"][0]["status"] = "fail"
    del task["release_note"]
    task["evidence"][1]["path"] = "b"
    core.save_manifest(task, path)                      # no other write since
    body = on_disk(task_dir)
    assert body["gates"][0]["status"] == "fail"
    assert "release_note" not in body
    assert body["evidence"] == [MANIFEST_EV1, {"id": "EV-2", "type": "test-run", "path": "b"}]
    assert body["usage"]["sessions"] == ["session-from-the-hook"]


MANIFEST_EV1 = {"id": "EV-1", "type": "test-run", "path": "evidence/one.txt"}


def test_trc_a8_a_copy_of_a_loaded_manifest_merges(task_dir):
    import copy
    task, path = core.load_manifest(task_dir)
    session_record.record(task_dir, "session-from-the-hook", via="env")
    task = copy.deepcopy(task)
    task["release_note"] = "Set on a copy."
    core.save_manifest(task, path)
    body = on_disk(task_dir)
    assert body["usage"]["sessions"] == ["session-from-the-hook"]
    assert body["release_note"] == "Set on a copy."


def test_trc_a8_analyze_keeps_a_change_saved_while_it_runs(task_dir, monkeypatch):
    from compass_pkg import analyze

    def save_after_the_hook(task, path):
        session_record.record(task_dir, "session-from-the-hook", via="env")
        core.save_manifest(task, path)

    monkeypatch.setattr(analyze, "save_manifest", save_after_the_hook)
    analyze._upsert_analyze_evidence_registry(task_dir, "EV-AN", "consistency-check",
                                              "evidence/an.json")
    body = on_disk(task_dir)
    assert body["usage"]["sessions"] == ["session-from-the-hook"]
    assert [e["id"] for e in body["evidence"]] == ["EV-1", "EV-AN"]


def test_trc_a9_every_save_gets_a_manifest_a_load_returned():
    """Each `save_manifest` call in the package saves a mapping that
    `load_manifest`, `manifest_store.load_file` or a caller passed in, never
    one read with `load_yaml`, whose save would overwrite."""
    import ast
    package = CLI_DIR / "compass_pkg"
    found = []
    for source in sorted(package.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            saved = {ast.unparse(c.args[0]) for c in ast.walk(fn)
                     if isinstance(c, ast.Call) and c.args
                     and getattr(c.func, "id", getattr(c.func, "attr", None)) == "save_manifest"}
            for node in ast.walk(fn):
                if not isinstance(node, ast.Assign):
                    continue
                names = {ast.unparse(e) for t in node.targets
                         for e in (t.elts if isinstance(t, ast.Tuple) else [t])}
                if names & saved and "load_yaml(" in ast.unparse(node.value):
                    found.append(f"{source.name}:{node.lineno}")
    assert not found, found


def test_trc_a10_a_value_of_another_type_is_a_change():
    merged = manifest_store.merge_manifest({"a": 1}, {"a": True}, {"a": 1, "b": 2})
    assert merged["a"] is True and merged["b"] == 2


def test_trc_b3_a_manifest_no_one_holds_is_released(task_dir):
    import gc
    gc.collect()
    held = len(manifest_store._READ_BY_OBJECT)
    for _ in range(200):
        core.load_manifest(task_dir)
    gc.collect()
    assert len(manifest_store._READ_BY_OBJECT) <= held + 1
    task, _ = core.load_manifest(task_dir)
    assert isinstance(task, dict)
    assert yaml.safe_load(yaml.safe_dump(task, sort_keys=False)) == yaml.safe_load(MANIFEST)


def test_trc_a11_a_record_held_across_a_merged_save_stays_in_the_manifest(task_dir):
    # The shape of `compass issue artifact set`: hold the record, save, then
    # stamp the held record and save again. The merged save must keep the
    # held record part of the manifest, or the stamp is lost.
    path = os.path.join(task_dir, "manifest.yml")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("artifacts:\n- id: ART-SPEC\n  kind: spec\n  status: draft\n")
    task = manifest_store.load_file(path)
    arts = list(task["artifacts"])
    entry = arts[0]
    other_writer(task_dir, lambda t: t["artifacts"][0].update(approved_by="someone"))
    entry["status"] = "awaiting-approval"
    task["artifacts"] = arts
    core.save_manifest(task, path)                      # merged save
    entry["digest"] = "sha256:abc"
    core.save_manifest(task, path)
    assert on_disk(task_dir)["artifacts"] == [
        {"id": "ART-SPEC", "kind": "spec", "status": "awaiting-approval",
         "approved_by": "someone", "digest": "sha256:abc"}]


def test_trc_a11_a_nested_mapping_held_across_a_merged_save_stays_in_the_manifest(task_dir):
    task, path = core.load_manifest(task_dir)
    gate = task["gates"][0]
    other_writer(task_dir, lambda t: t["gates"][0].update(note="theirs"))
    gate["status"] = "pass"
    core.save_manifest(task, path)                      # merged save
    gate["evidence"].append("EV-1")
    core.save_manifest(task, path)
    assert on_disk(task_dir)["gates"][0] == {
        "id": "verify.correctness", "status": "pass", "evidence": ["EV-1"], "note": "theirs"}


def test_trc_a12_a_record_merge_keeps_this_writers_order():
    base = [{"id": "a"}, {"id": "b"}]
    merged = manifest_store.merge_manifest(
        {"l": base}, {"l": [{"id": "b"}, {"id": "a"}]}, {"l": base + [{"id": "c"}]})
    assert [r["id"] for r in merged["l"]] == ["b", "c", "a"]


def test_trc_a13_both_writers_append_a_record_without_an_id(task_dir):
    # Both append a run. The merged list keeps this writer's own run object
    # at the end; filling the list in place must not rewrite that object to
    # equal the other writer's run, or the next save writes the other run
    # twice and loses this one.
    task, path = core.load_manifest(task_dir)
    other_writer(task_dir, lambda t: t.setdefault("runs", []).append({"n": 2, "outcome": "theirs"}))
    task.setdefault("runs", []).append({"n": 3, "outcome": "ours"})
    core.save_manifest(task, path)
    assert task["runs"] == on_disk(task_dir)["runs"]
    task["release_note"] = "Set after the merged save."
    core.save_manifest(task, path)
    assert on_disk(task_dir)["runs"] == [{"n": 2, "outcome": "theirs"}, {"n": 3, "outcome": "ours"}]
