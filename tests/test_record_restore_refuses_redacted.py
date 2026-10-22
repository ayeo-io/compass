"""`compass record restore` refuses a generation file that holds `[REDACTED]`.

A `record sync` before 7.0.0 redacted lines of generation files in the
delivery record. A generation's marker holds a digest of each of its files,
so a restored redacted copy makes the generation broken and `compass check`
refuses the issue. The restore must refuse before it copies anything, name
the file, and say how to repair it.

Scenario id: `RRR-1`.
"""
from __future__ import annotations

from test_delivery_record import (_cli, _commit_in_record, _configure, _git,
                                  _init_repo, _remote, project)  # noqa: F401

GENERATION = ".compass/work/one/generations/1/resolved.yml"


def _plant_redacted_generation(work):
    path = work / GENERATION
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("schema: 1\nissue: one\ngeneration: 1\ntoken: [REDACTED]\n")
    _git(work, "add", GENERATION)


def test_rrr_1_restore_refuses_a_redacted_generation_file(project, tmp_path):
    remote = _remote(tmp_path)
    _configure(project, remote)
    assert _cli(project, "record", "sync").returncode == 0
    _commit_in_record(remote, tmp_path, _plant_redacted_generation)
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    _init_repo(fresh)
    _configure(fresh, remote)
    for flags in ((), ("--force",)):
        result = _cli(fresh, "record", "restore", *flags)
        assert result.returncode != 0, result.stdout + result.stderr
        assert GENERATION in result.stderr, result.stderr
        assert "[REDACTED]" in result.stderr, result.stderr
        assert "compass approach evaluate --write" in result.stderr, result.stderr
        # Nothing is copied, not even the files that are whole.
        assert not (fresh / ".compass" / "work" / "one").exists()
        assert not (fresh / "docs" / "analysis").exists()


def test_rrr_1_a_redacted_file_outside_a_generation_still_restores(project, tmp_path):
    # The sync redacts the key in the fixture's plan; that copy restores.
    remote = _remote(tmp_path)
    _configure(project, remote)
    assert _cli(project, "record", "sync").returncode == 0
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    _init_repo(fresh)
    _configure(fresh, remote)
    result = _cli(fresh, "record", "restore")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[REDACTED]" in (fresh / "docs" / "analysis" / "plan.md").read_text()
