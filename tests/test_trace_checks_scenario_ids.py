"""A trace records only scenarios the issue defines.

`compass changed-file add` wrote any `--scenario` value into the manifest,
so a shell quoting slip stored six ids as one string, and nothing said so
until `compass check` ran later (#119). `compass evidence add` did the
same. Both now check each id, as `compass tdd-red` does.

Scenario id: TS-1 (issue `trace-checks-scenario-ids`).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from test_quick_fix_verbs import _manifest_path, _run, _start, repo  # noqa: E402,F401

SLUG = "greeting-fix"


def _manifest_text(root):
    return _manifest_path(root, SLUG).read_text(encoding="utf-8")


def test_ts_1_changed_file_add_refuses_an_unknown_id(repo):
    assert _start(repo, SLUG).returncode == 0
    before = _manifest_text(repo)
    result = _run(repo, "changed-file", "add", "README.md", "--issue", SLUG,
                  "--scenario", "TRC-NOPE")
    assert result.returncode != 0, result.stdout
    assert "TRC-NOPE" in result.stderr and "TRC-001" in result.stderr
    assert _manifest_text(repo) == before


def test_ts_1_several_ids_in_one_string_are_refused(repo):
    assert _start(repo, SLUG).returncode == 0
    before = _manifest_text(repo)
    result = _run(repo, "changed-file", "add", "README.md", "--issue", SLUG,
                  "--scenario", "TRC-001 TRC-002")
    assert result.returncode != 0, result.stdout
    assert "--scenario" in result.stderr
    assert _manifest_text(repo) == before


def test_ts_1_a_known_id_is_still_traced(repo):
    assert _start(repo, SLUG).returncode == 0
    result = _run(repo, "changed-file", "add", "README.md", "--issue", SLUG,
                  "--scenario", "TRC-001")
    assert result.returncode == 0, result.stderr


def test_ts_1_evidence_add_refuses_an_unknown_id(repo):
    assert _start(repo, SLUG).returncode == 0
    work = _manifest_path(repo, SLUG).parent
    (work / "note.md").write_text("a manual review\n", encoding="utf-8")
    before = _manifest_text(repo)
    result = _run(repo, "evidence", "add", "EV-9", "--issue", SLUG,
                  "--type", "manual-review", "--path", "note.md",
                  "--scenario", "TRC-NOPE")
    assert result.returncode != 0, result.stdout
    assert "TRC-NOPE" in result.stderr
    assert _manifest_text(repo) == before
