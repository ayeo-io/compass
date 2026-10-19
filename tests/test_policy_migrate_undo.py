"""`compass policy migrate --undo`: going back, the order of the steps and the stops.

The tests migrate a small scratch project with the real CLI, then plan and
apply the undo through `compass_pkg.policy_migrate_undo`. Stop tests replace
one undo writer by name with a function that raises `OSError`, as the tests
for the migration do, and run the undo again.

Scenario id: `TRC-007` in policy-migrate-undo/acceptance-criteria.md. The ids
run from TRC-007 to TRC-018. Each test name starts with its scenario id.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_policy_migrate import (OLD_CONFIG, _api, _full_project, _run,  # noqa: E402
                                 _settings_view, _tree)

SOURCES = ("governance/routing-policy.yml", "governance/guardrails.yml", ".compass/config.yml")
WRITERS = ("restore_source", "remove_compass_yml", "remove_state", "remove_marker")


# --- helpers (the refusal tests use them too) ---------------------------------------

def undo_api():
    from compass_pkg import policy_migrate_undo
    return policy_migrate_undo


def _digest(data):
    import hashlib
    return "sha256:" + hashlib.sha256(data).hexdigest()


def add_marker_keys(root, compass_yml_text=None):
    """Add `written` and `migrated_at` to the marker when the migration did not.

    It does nothing once the keys exist, so the tests hold before and after
    the migration writes them itself. `compass_yml_text` is the text of a
    `compass.yml` the migration stopped before it wrote.
    """
    path = Path(root) / ".compass" / "migration.yml"
    marker = yaml.safe_load(path.read_text(encoding="utf-8"))
    before = dict(marker)
    if "written" not in marker:
        compass_yml = Path(root) / "compass.yml"
        data = compass_yml.read_bytes() if compass_yml.exists() else compass_yml_text.encode("utf-8")
        marker["written"] = {"compass.yml": _digest(data)}
        if marker.get("created_state") is True:
            state = (Path(root) / ".compass" / "state.yml").read_bytes()
            marker["written"][".compass/state.yml"] = _digest(state)
    if "migrated_at" not in marker:
        marker["migrated_at"] = "2026-10-19T12:00:00+00:00"
    if marker != before:
        path.write_text(yaml.safe_dump(marker, sort_keys=False), encoding="utf-8")


def set_marker(root, **keys):
    """Change keys of the marker; a value of None removes the key."""
    path = Path(root) / ".compass" / "migration.yml"
    marker = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key, value in keys.items():
        if value is None:
            marker.pop(key, None)
        else:
            marker[key] = value
    path.write_text(yaml.safe_dump(marker, sort_keys=False), encoding="utf-8")


def _crlf(path):
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))


def migrated(tmp_path, crlf=False):
    """A project after a real `compass policy migrate --apply`.

    Returns the root, the bytes of the three sources before the migration and
    the settings the readers returned before it.
    """
    root = _full_project(tmp_path)
    if crlf:
        _crlf(root / "governance" / "routing-policy.yml")
        _crlf(root / ".compass" / "config.yml")
    originals = {rel: (root / rel).read_bytes() for rel in SOURCES}
    settings = _settings_view(root)
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 0, out + err
    add_marker_keys(root)
    return root, originals, settings


def undo(root):
    api = undo_api()
    made = api.plan(str(root))
    api.apply(str(root), made)
    return made


def without_legacy(tree):
    return {rel: data for rel, data in tree.items() if not rel.startswith(".compass/legacy/")}


def stop_before(monkeypatch, name):
    """Make one undo writer raise OSError, as a full disk or a kill would."""
    def stop(*_args, **_kwargs):
        raise OSError(f"stopped before {name}")
    monkeypatch.setattr(undo_api(), name, stop)


# --- TRC-007 to TRC-013 -----------------------------------------------------------

def test_TRC_007_apply_restores_the_three_sources_byte_for_byte(tmp_path):
    root, originals, _ = migrated(tmp_path, crlf=True)
    assert b"\r\n" in originals[".compass/config.yml"]
    undo(root)
    for rel in SOURCES:
        assert (root / rel).read_bytes() == originals[rel], rel


def test_TRC_008_apply_removes_the_three_files_the_migration_wrote(tmp_path):
    root, _, _ = migrated(tmp_path)
    for rel in ("compass.yml", ".compass/state.yml", ".compass/migration.yml"):
        assert (root / rel).exists(), rel
    undo(root)
    for rel in ("compass.yml", ".compass/state.yml", ".compass/migration.yml"):
        assert not (root / rel).exists(), rel


def test_TRC_009_the_steps_run_in_a_fixed_order_with_the_marker_last(tmp_path, monkeypatch):
    root, _, _ = migrated(tmp_path)
    api = undo_api()
    calls = []
    monkeypatch.setattr(api, "restore_source", lambda r, rel: calls.append(("restore", rel)))
    monkeypatch.setattr(api, "remove_compass_yml", lambda r: calls.append(("remove", "compass.yml")))
    monkeypatch.setattr(api, "remove_state", lambda r: calls.append(("remove", "state.yml")))
    monkeypatch.setattr(api, "remove_marker", lambda r: calls.append(("remove", "migration.yml")))
    undo(root)
    assert calls == [("restore", ".compass/config.yml"), ("remove", "compass.yml"),
                     ("remove", "state.yml"), ("remove", "migration.yml")]


def test_TRC_010_the_settings_readers_see_what_they_saw_before_the_migration(tmp_path):
    root, _, before = migrated(tmp_path)
    assert _settings_view(root) == before  # the migration kept the readers' view too
    undo(root)
    assert _settings_view(root) == before
    assert not (root / "compass.yml").exists()


def test_TRC_011_a_state_file_the_migration_did_not_create_is_kept(tmp_path):
    root = _full_project(tmp_path)
    state = root / ".compass" / "state.yml"
    state.write_text("initialised: {by: someone, at: '2026-02-02'}\n", encoding="utf-8")
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 0, out + err
    add_marker_keys(root)
    kept = state.read_bytes()
    made = undo(root)
    assert state.read_bytes() == kept
    assert {"action": "keep", "path": ".compass/state.yml", "to": None} in made.files
    assert not (root / "compass.yml").exists()


def test_TRC_012_the_legacy_folder_is_kept(tmp_path):
    root, originals, _ = migrated(tmp_path)
    undo(root)
    for rel, data in originals.items():
        assert (root / ".compass" / "legacy" / Path(rel).name).read_bytes() == data


def test_TRC_013_a_governance_file_deleted_since_the_migration_is_restored(tmp_path):
    root, originals, _ = migrated(tmp_path)
    (root / "governance" / "guardrails.yml").unlink()
    made = undo(root)
    assert (root / "governance" / "guardrails.yml").read_bytes() == originals[
        "governance/guardrails.yml"]
    restores = [f["path"] for f in made.files if f["action"] == "restore"]
    assert restores == [".compass/config.yml", "governance/guardrails.yml"]


# --- TRC-014 to TRC-018 -----------------------------------------------------------

def _project_state(root):
    """The files a migration leaves, with the marker minus its time."""
    tree = _tree(root)
    marker = yaml.safe_load(tree[".compass/migration.yml"].decode("utf-8"))
    marker.pop("migrated_at", None)
    tree[".compass/migration.yml"] = yaml.safe_dump(marker, sort_keys=False).encode("utf-8")
    return tree


def test_TRC_014_migrate_undo_migrate_gives_the_same_project(tmp_path):
    root, _, _ = migrated(tmp_path)
    first = _project_state(root)
    undo(root)
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 0, out + err
    add_marker_keys(root)
    assert _project_state(root) == first


@pytest.mark.parametrize("step", WRITERS)
def test_TRC_015_a_stop_before_any_undo_step_is_finished_by_a_rerun(tmp_path, monkeypatch, step):
    (tmp_path / "stopped").mkdir()
    (tmp_path / "whole").mkdir()
    reference, _, _ = migrated(tmp_path / "whole")
    undo(reference)
    root, _, _ = migrated(tmp_path / "stopped")
    stop_before(monkeypatch, step)
    with pytest.raises(OSError):
        undo(root)
    monkeypatch.undo()
    undo(root)
    assert _tree(root) == _tree(reference)


def test_TRC_016_an_undo_finishes_a_migration_stopped_before_removing_the_old_file(
        tmp_path, monkeypatch):
    root = _full_project(tmp_path)
    before = _tree(root)
    api = _api()
    monkeypatch.setattr(api, "remove_old_config",
                        lambda _root: (_ for _ in ()).throw(OSError("stopped")))
    with pytest.raises(OSError):
        api.apply(str(root), api.plan(str(root)))
    monkeypatch.undo()
    add_marker_keys(root)
    assert (root / "compass.yml").is_file() and (root / ".compass" / "config.yml").is_file()
    undo(root)
    assert without_legacy(_tree(root)) == before


def test_TRC_017_an_undo_finishes_a_migration_stopped_before_writing_compass_yml(
        tmp_path, monkeypatch):
    root = _full_project(tmp_path)
    before = _tree(root)
    api = _api()
    made = api.plan(str(root))
    real = api.atomic_write_text

    def stop_at_compass_yml(path, text, **kwargs):
        if os.path.basename(path) == "compass.yml":
            raise OSError("stopped")
        return real(path, text, **kwargs)

    monkeypatch.setattr(api, "atomic_write_text", stop_at_compass_yml)
    with pytest.raises(OSError):
        api.apply(str(root), made)
    monkeypatch.undo()
    add_marker_keys(root, compass_yml_text=made.compass_yml)
    assert (root / ".compass" / "state.yml").is_file() and not (root / "compass.yml").exists()
    undo(root)
    assert without_legacy(_tree(root)) == before


def test_TRC_018_a_source_equal_to_its_legacy_copy_counts_as_done(tmp_path, monkeypatch):
    root, originals, _ = migrated(tmp_path)
    stop_before(monkeypatch, "remove_compass_yml")
    with pytest.raises(OSError):
        undo(root)
    monkeypatch.undo()
    made = undo_api().plan(str(root))
    assert made.result == "ready"
    assert not [f for f in made.files if f["action"] == "restore"]
    assert [f["path"] for f in made.files if f["action"] == "keep"] == list(SOURCES)
    assert [s["path"] for s in made.sources] == list(SOURCES)
    assert (root / "compass.yml").exists()


# --- the report -------------------------------------------------------------------

def test_the_json_report_has_fixed_keys_and_the_text_report_ends_with_the_way_to_apply(tmp_path):
    root, _, _ = migrated(tmp_path)
    api = undo_api()
    made = api.plan(str(root))
    document = api.report_json(made)
    assert list(document) == ["schema", "mode", "result", "sources", "files"]
    assert document["schema"] == 1 and document["mode"] == "undo" and document["result"] == "ready"
    lines = api.report_text(made)
    assert lines[0] == "compass policy migrate --undo: dry run - nothing was written"
    assert lines[-1] == "Run with --apply to make these changes."
    assert any(".compass/legacy" in line for line in lines)
    api.apply(str(root), made)
    assert api.report_json(made)["result"] == "undone"
    done = api.report_text(made)
    assert done[0] == "compass policy migrate --undo: undone"
    assert not any("--apply" in line for line in done)
