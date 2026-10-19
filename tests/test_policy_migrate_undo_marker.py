"""The migration marker records what `compass policy migrate --undo` needs
(issue `policy-migrate-undo`, unit U1).

`migration.yml` in the `.compass` folder gains `written` (a digest for each file the
migration wrote) and `migrated_at` (a UTC time), and stays at schema 1. Each
test runs the CLI over a temporary project, as `tests/test_policy_migrate.py`
does, and reads the marker and the files back from disk.

Scenario id: `TRC-001` in policy-migrate-undo/acceptance-criteria.md. The
other five scenarios of the group sit beside it in the same file.
"""
from __future__ import annotations

import datetime
import hashlib

import yaml

from test_policy_migrate import _full_project, _run


def _digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _migrate(root):
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 0, out + err
    return yaml.safe_load((root / ".compass" / "migration.yml").read_text(encoding="utf-8"))


def test_TRC_001_the_marker_records_the_digest_of_compass_yml(tmp_path):
    root = _full_project(tmp_path)
    marker = _migrate(root)
    assert marker["written"]["compass.yml"] == _digest(root / "compass.yml")


def test_TRC_002_the_marker_records_the_digest_of_state_yml_when_created(tmp_path):
    root = _full_project(tmp_path)
    marker = _migrate(root)
    assert marker["created_state"] is True
    assert marker["written"][".compass/state.yml"] == _digest(root / ".compass" / "state.yml")


def test_TRC_003_the_marker_records_no_state_digest_for_an_existing_state_yml(tmp_path):
    root = _full_project(tmp_path)
    (root / ".compass" / "state.yml").write_text(
        "initialised: {by: someone, at: '2026-02-02'}\n", encoding="utf-8")
    marker = _migrate(root)
    assert marker["created_state"] is False
    assert list(marker["written"]) == ["compass.yml"]


def test_TRC_004_the_marker_stays_at_schema_1_and_keeps_its_earlier_keys(tmp_path):
    root = _full_project(tmp_path)
    marker = _migrate(root)
    assert marker["schema"] == 1
    assert list(marker)[:5] == ["schema", "tool", "sources", "created_state", "written"]
    assert list(marker["sources"]) == [
        "governance/routing-policy.yml", "governance/guardrails.yml", ".compass/config.yml"]
    for rel, digest in marker["sources"].items():
        assert digest == _digest(root / ".compass" / "legacy" / rel.rsplit("/", 1)[-1])


def _whole_seconds():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def test_TRC_005_the_marker_records_the_time_of_the_migration(tmp_path):
    root = _full_project(tmp_path)
    before = _whole_seconds()
    marker = _migrate(root)
    after = _whole_seconds()
    stamp = datetime.datetime.fromisoformat(marker["migrated_at"])
    assert stamp.utcoffset() == datetime.timedelta(0)
    assert before <= stamp <= after


def test_TRC_006_a_migrated_projects_plain_migrate_refusal_names_undo(tmp_path):
    root = _full_project(tmp_path)
    _migrate(root)
    code, out, err = _run(root, "policy", "migrate")
    assert code == 2 and out == ""
    assert "compass policy migrate --undo" in err
    assert "legacy" in err and "migration.yml" in err
    assert len(err.split()) < 60
