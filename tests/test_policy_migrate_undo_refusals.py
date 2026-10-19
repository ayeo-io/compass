"""`compass policy migrate --undo`: every refusal, and the promise to write nothing.

The undo discards a settings file only when nothing in the project changed
since the migration. A refusal names the file or the count that caused it,
has fewer than 60 words, and happens in `plan`, before any write. These tests
break a migrated scratch project in one way each, plan the undo and read the
message. They use the helpers of `test_policy_migrate_undo`.

Scenario id: `TRC-019` in policy-migrate-undo/acceptance-criteria.md. The ids
run from TRC-019 to TRC-031. Each test name starts with its scenario id.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_policy_migrate import _api, _full_project, _run, _tree  # noqa: E402
from test_policy_migrate_undo import (WRITERS, _digest, add_marker_keys,  # noqa: E402
                                      migrated, set_marker, undo, undo_api)

MIGRATED_AT = "2026-10-19T12:00:00+00:00"


# --- helpers ----------------------------------------------------------------------

def refusal(root):
    """The message of the refusal `plan` raises; fails when it does not refuse."""
    from compass_pkg.core import CompassError
    with pytest.raises(CompassError) as caught:
        undo_api().plan(str(root))
    return str(caught.value)


def append(root, rel, text="# an edit\n"):
    with open(Path(root) / rel, "a", encoding="utf-8") as fh:
        fh.write(text)


def record(root, slug, name, timestamp, signed=True, folder="evidence"):
    """An evidence record of an issue; only its signature and time matter."""
    body = {"scenario": "X-1", "passed": True}
    if timestamp is not None:
        body["timestamp"] = timestamp
    if signed:
        body["content_digest"] = "sha256:" + "0" * 64
    where = Path(root) / ".compass" / "work" / slug / folder
    where.mkdir(parents=True, exist_ok=True)
    (where / name).write_text(json.dumps(body), encoding="utf-8")


def signed_records(root, after=3):
    """`after` signed records at or after the migration, in two issues, and one before it."""
    record(root, "issue-a", "one.json", "2026-10-19T12:00:00+00:00")
    record(root, "issue-a", "two.json", "2026-10-20T08:30:00+00:00")
    for index in range(after - 2):
        record(root, "issue-b", f"later-{index}.json", "2026-11-01T00:00:00Z")
    record(root, "issue-b", "before.json", "2026-10-19T11:59:59+00:00")


def edited_old_config(root):
    (Path(root) / ".compass" / "config.yml").write_text("autonomy: controlled\n", encoding="utf-8")


# A refusal for each way of breaking a migrated project: the setup, then the
# text the message must contain.
CASES = {
    "edited compass.yml": (lambda root: append(root, "compass.yml"), "compass.yml"),
    "edited state.yml": (lambda root: append(root, ".compass/state.yml"), ".compass/state.yml"),
    "edited routing policy": (lambda root: append(root, "governance/routing-policy.yml"),
                              "governance/routing-policy.yml"),
    "edited guardrails": (lambda root: append(root, "governance/guardrails.yml"),
                          "governance/guardrails.yml"),
    "edited old settings file": (edited_old_config, ".compass/config.yml"),
    "changed legacy copy": (lambda root: append(root, ".compass/legacy/config.yml"),
                            ".compass/legacy/config.yml"),
    "missing legacy copy": (lambda root: (Path(root) / ".compass/legacy/config.yml").unlink(),
                            ".compass/legacy/config.yml"),
    "no digest": (lambda root: set_marker(root, written=None), "migration.yml"),
    "no marker": (lambda root: (Path(root) / ".compass/migration.yml").unlink(), "migration.yml"),
    "one signed record": (lambda root: record(root, "issue-a", "a.json", "not a date"),
                          "1 signed record "),
    "three signed records": (signed_records, "3 signed records"),
}


# --- TRC-019 to TRC-025 -----------------------------------------------------------

def test_TRC_019_an_edited_compass_yml_is_refused(tmp_path):
    root, _, _ = migrated(tmp_path)
    append(root, "compass.yml")
    message = refusal(root)
    assert "compass.yml" in message and "Nothing was changed" in message


def test_TRC_020_an_edited_state_yml_is_refused(tmp_path):
    root, _, _ = migrated(tmp_path)
    append(root, ".compass/state.yml")
    assert ".compass/state.yml" in refusal(root)


@pytest.mark.parametrize("name", ["governance/routing-policy.yml", "governance/guardrails.yml"])
def test_TRC_021_an_edited_governance_file_is_refused(tmp_path, name):
    root, _, _ = migrated(tmp_path)
    append(root, name)
    assert name in refusal(root)


def test_TRC_022_an_old_settings_file_edited_after_a_stop_is_refused(tmp_path, monkeypatch):
    root = _full_project(tmp_path)
    api = _api()
    monkeypatch.setattr(api, "remove_old_config",
                        lambda _root: (_ for _ in ()).throw(OSError("stopped")))
    with pytest.raises(OSError):
        api.apply(str(root), api.plan(str(root)))
    monkeypatch.undo()
    add_marker_keys(root)
    append(root, ".compass/config.yml", "autonomy: controlled\n")
    assert ".compass/config.yml" in refusal(root)


@pytest.mark.parametrize("state", ["changed", "missing"])
def test_TRC_023_a_legacy_copy_that_is_changed_or_missing_is_refused(tmp_path, state):
    root, _, _ = migrated(tmp_path)
    legacy = root / ".compass" / "legacy" / "config.yml"
    if state == "missing":
        legacy.unlink()
    else:
        append(root, ".compass/legacy/config.yml")
    assert ".compass/legacy/config.yml" in refusal(root)


def test_TRC_024_a_marker_with_no_digest_is_refused_with_the_manual_steps(tmp_path):
    root, _, _ = migrated(tmp_path)
    set_marker(root, written=None)
    message = refusal(root)
    for part in (".compass/legacy/config.yml", ".compass/config.yml", "compass.yml",
                 ".compass/migration.yml", ".compass/state.yml", "created_state"):
        assert part in message, part
    assert "by hand" in message


@pytest.mark.parametrize("written", [
    {".compass/state.yml": "sha256:abc"},   # no digest of compass.yml
    {"compass.yml": "sha256:abc"},          # created_state is true and no digest of state.yml
    {"compass.yml": 5, ".compass/state.yml": "sha256:abc"},   # a digest that is not a string
    "compass.yml",                          # not a mapping
])
def test_TRC_024_a_marker_with_a_partial_digest_list_is_refused_the_same_way(tmp_path, written):
    root, _, _ = migrated(tmp_path)
    set_marker(root, written=written)
    assert "by hand" in refusal(root)


def test_TRC_024_a_marker_without_state_made_needs_no_state_digest(tmp_path):
    root = _full_project(tmp_path)
    (root / ".compass" / "state.yml").write_text("initialised: {by: x, at: '2026-02-02'}\n",
                                                 encoding="utf-8")
    assert _run(root, "policy", "migrate", "--apply")[0] == 0
    add_marker_keys(root)
    set_marker(root, written={"compass.yml": _digest((root / "compass.yml").read_bytes())})
    assert undo_api().plan(str(root)).result == "ready"


def test_TRC_025_a_project_with_no_marker_is_refused(tmp_path):
    root = _full_project(tmp_path)
    before = _tree(root)
    message = refusal(root)
    assert "migration.yml" in message and "nothing to undo" in message
    assert _tree(root) == before


@pytest.mark.parametrize("text", ["- a\n- list\n", "{not: [valid", "just text\n", ""])
def test_TRC_025_a_marker_that_is_not_a_mapping_counts_as_no_marker(tmp_path, text):
    root, _, _ = migrated(tmp_path)
    (root / ".compass" / "migration.yml").write_text(text, encoding="utf-8")
    assert "nothing to undo" in refusal(root)


# --- TRC-026 to TRC-028: signed records --------------------------------------------

def test_TRC_026_signed_records_since_the_migration_are_refused_and_counted(tmp_path):
    root, _, _ = migrated(tmp_path)
    set_marker(root, migrated_at=MIGRATED_AT)
    signed_records(root)
    message = refusal(root)
    assert "3 signed records exist since the migration" in message


def test_TRC_027_earlier_and_unsigned_records_do_not_block(tmp_path):
    root, _, _ = migrated(tmp_path)
    set_marker(root, migrated_at=MIGRATED_AT)
    record(root, "issue-a", "early.json", "2026-10-19T11:59:59+00:00")
    record(root, "issue-a", "late.json", "2026-12-01T00:00:00+00:00", signed=False)
    undo(root)
    assert not (root / ".compass" / "migration.yml").exists()


def test_TRC_028_a_signed_record_with_no_readable_timestamp_counts(tmp_path):
    root, _, _ = migrated(tmp_path)
    record(root, "issue-a", "odd.json", "not a date")
    message = refusal(root)
    assert "1 signed record exists since the migration" in message
    assert "records" not in message.split("migration")[0]


@pytest.mark.parametrize("stamp, counts", [
    ("2026-10-19T12:00:00+00:00", True),     # at the time of the migration
    ("2026-10-19T12:00:00Z", True),          # a trailing Z is UTC
    ("2026-10-19T12:00:00", True),           # no zone is UTC
    ("2026-10-19T11:59:59", False),
    ("2026-10-19T13:59:59+02:00", False),    # 11:59:59 UTC
    ("2026-10-19T14:00:00+02:00", True),     # 12:00:00 UTC
    (None, True),                            # no timestamp at all
    (7, True),                               # not a string
])
def test_TRC_028_the_timestamp_forms_are_read_as_utc_and_the_edge_is_included(
        tmp_path, stamp, counts):
    root, _, _ = migrated(tmp_path)
    set_marker(root, migrated_at=MIGRATED_AT)
    record(root, "issue-a", "r.json", stamp)
    if counts:
        assert "1 signed record exists" in refusal(root)
    else:
        assert undo_api().plan(str(root)).result == "ready"


def test_TRC_028_only_regular_signed_json_records_in_evidence_folders_count(tmp_path):
    root, _, _ = migrated(tmp_path)
    set_marker(root, migrated_at=MIGRATED_AT)
    late = "2026-12-01T00:00:00+00:00"
    work = root / ".compass" / "work"
    record(root, "issue-a", "notes.txt", late)                       # not a .json file
    record(root, "issue-a", "elsewhere.json", late, folder="other")  # not in evidence/
    (work / "issue-a" / "evidence" / "broken.json").write_text("{not json", encoding="utf-8")
    (work / "issue-a" / "evidence" / "list.json").write_text("[1, 2]", encoding="utf-8")
    (work / "stray.json").write_text(json.dumps({"timestamp": late, "content_digest": "x"}),
                                     encoding="utf-8")
    outside = root / "outside"
    outside.mkdir()
    (outside / "linked.json").write_text(json.dumps({"timestamp": late, "content_digest": "x"}),
                                         encoding="utf-8")
    (work / "issue-a" / "evidence" / "link.json").symlink_to(outside / "linked.json")
    (work / "linked-issue").symlink_to(outside, target_is_directory=True)
    assert undo_api().plan(str(root)).result == "ready"


@pytest.mark.parametrize("value", [None, "not a date"])
def test_TRC_028_without_a_readable_migrated_at_the_markers_own_time_stands_in(tmp_path, value):
    root, _, _ = migrated(tmp_path)
    set_marker(root, migrated_at=value)
    marker = root / ".compass" / "migration.yml"
    if value is None:  # the writer does not add the key back
        assert "migrated_at" not in marker.read_text(encoding="utf-8")
    stamp = 1_792_411_200  # 2026-10-19T12:00:00Z
    os.utime(marker, (stamp, stamp))
    record(root, "issue-a", "early.json", "2026-10-19T11:59:59+00:00")
    assert undo_api().plan(str(root)).result == "ready"
    record(root, "issue-a", "late.json", "2026-10-19T12:00:01+00:00")
    assert "1 signed record exists" in refusal(root)


# --- TRC-029 to TRC-031 -----------------------------------------------------------

def broken(tmp_path, case):
    root, _, _ = migrated(tmp_path)
    CASES[case][0](root)
    return root


@pytest.mark.parametrize("case", list(CASES))
def test_TRC_029_a_refused_undo_makes_no_write_and_no_removal(tmp_path, monkeypatch, case):
    root = broken(tmp_path, case)
    api = undo_api()
    calls = []
    for name in WRITERS:
        monkeypatch.setattr(api, name, lambda *args, _name=name: calls.append(_name))
    before = _tree(root)
    from compass_pkg.core import CompassError
    with pytest.raises(CompassError):
        api.apply(str(root), api.plan(str(root)))
    assert calls == [] and _tree(root) == before


def test_TRC_029_a_dry_run_and_a_ready_plan_write_nothing(tmp_path):
    root, _, _ = migrated(tmp_path)
    before = _tree(root)
    api = undo_api()
    made = api.plan(str(root))
    api.report_json(made)
    api.report_text(made)
    assert made.result == "ready" and _tree(root) == before


def test_TRC_030_the_undo_changes_only_4_paths_whatever_the_marker_names(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    root, originals, _ = migrated(project)
    outside = tmp_path / "outside.txt"
    outside.write_text("the file next to the project\n", encoding="utf-8")
    legacy = root / ".compass" / "legacy" / "outside.txt"
    legacy.write_text("a different text, with a different digest\n", encoding="utf-8")
    marker = (root / ".compass" / "migration.yml")
    import yaml
    data = yaml.safe_load(marker.read_text(encoding="utf-8"))
    data["sources"]["../outside.txt"] = _digest(legacy.read_bytes())
    data["sources"]["/etc/hosts"] = "sha256:" + "0" * 64
    marker.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    before = _tree(tmp_path)
    made = undo(root)
    after = _tree(tmp_path)
    changed = {rel for rel in set(before) | set(after) if before.get(rel) != after.get(rel)}
    assert changed == {"project/.compass/config.yml", "project/compass.yml",
                       "project/.compass/state.yml", "project/.compass/migration.yml"}
    assert after["outside.txt"] == b"the file next to the project\n"
    assert [s["path"] for s in made.sources] == list(originals)


def test_TRC_031_every_refusal_message_has_fewer_than_60_words(tmp_path):
    for index, case in enumerate(CASES):
        (tmp_path / str(index)).mkdir()
        message = refusal(broken(tmp_path / str(index), case))
        assert CASES[case][1] in message, case
        assert len(message.split()) < 60, (case, len(message.split()), message)
