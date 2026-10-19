"""`compass policy migrate --undo`: the guards that a bad marker or a mode must not slip past.

Each test breaks a migrated scratch project in one way, runs the real command and
checks that it refuses cleanly (exit 2, no traceback) and writes nothing, or that
a restored file keeps its mode. They use the helpers of `test_policy_migrate_undo`.

Scenario ids: `TRC-042` to `TRC-046` in policy-migrate-undo/acceptance-criteria.md.
Each test name starts with its scenario id.
"""
from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_policy_migrate import _full_project, _run, _tree  # noqa: E402
from test_policy_migrate_undo import migrated, set_marker, undo  # noqa: E402

MARKER = ".compass/migration.yml"


def _refuses_clean(root, *argv):
    """Run the command, check it refuses with no traceback and no write; return stderr."""
    before = _tree(root)
    code, out, err = _run(root, "policy", "migrate", *argv)
    assert code == 2, out + err
    assert "Traceback" not in err, err
    assert _tree(root) == before
    return err


@pytest.mark.parametrize("sources", [{}, {"somewhere/else.yml": "sha256:abc"}])
def test_TRC_042_a_marker_without_source_digests_refuses_and_writes_nothing(tmp_path, sources):
    root, _, _ = migrated(tmp_path)
    set_marker(root, sources=sources)
    _refuses_clean(root, "--undo", "--apply")
    assert (root / "compass.yml").exists() and (root / MARKER).exists()


def test_TRC_043_a_binary_marker_gives_a_clean_refusal_of_the_undo(tmp_path):
    root, _, _ = migrated(tmp_path)
    (root / MARKER).write_bytes(bytes(range(256)))
    assert "nothing to undo" in _refuses_clean(root, "--undo", "--apply")


@pytest.mark.parametrize("schema", [2, 0, "1", None])
def test_TRC_044_a_marker_of_another_schema_is_refused_and_names_the_schema(tmp_path, schema):
    root, _, _ = migrated(tmp_path)
    set_marker(root, schema=schema)   # None removes the key
    err = _refuses_clean(root, "--undo", "--apply")
    assert "schema" in err
    assert len(err.split()) < 60


def test_TRC_045_a_binary_marker_gives_a_clean_refusal_of_the_plain_migrate(tmp_path):
    root, _, _ = migrated(tmp_path)
    (root / MARKER).write_bytes(bytes(range(256)))
    _refuses_clean(root, "--apply")


def test_TRC_045_the_undo_reads_the_marker_with_the_migrations_reader():
    from compass_pkg import policy_migrate, policy_migrate_undo
    assert policy_migrate_undo.pm.read_marker is policy_migrate.read_marker
    assert not hasattr(policy_migrate_undo, "_marker")


def test_TRC_046_a_restored_file_keeps_the_mode_it_had(tmp_path):
    root = _full_project(tmp_path)
    for rel in (".compass/config.yml", "governance/guardrails.yml"):
        (root / rel).chmod(0o600)
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 0, out + err
    for rel in ("config.yml", "guardrails.yml"):
        assert stat.S_IMODE((root / ".compass" / "legacy" / rel).stat().st_mode) == 0o600
    (root / "governance" / "guardrails.yml").unlink()
    undo(root)
    for rel in (".compass/config.yml", "governance/guardrails.yml"):
        assert stat.S_IMODE((root / rel).stat().st_mode) == 0o600, rel
    assert stat.S_IMODE((root / "governance" / "routing-policy.yml").stat().st_mode) != 0o600
