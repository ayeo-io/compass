"""`multiagent.sh` refuses a map whose two subtask counts disagree.

A distribution map lists one row per subtask in its §3 table and states
the final count again in §5. On one issue the two disagreed and nothing
noticed: the dry run planned a worktree the document said should not
exist (#101). The script now compares them before creating anything.

Scenario id: MC-1 (issue `map-counts-agree`).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from test_multiagent_docs_and_waves import (  # noqa: E402
    _init_repo, _manifest, _run_multiagent)


def _issue(tmp_path, rows, final):
    repo = _init_repo(tmp_path)
    slug = "count-demo"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    table = "".join(f"| subtask-{n} | U{n} | MC-1 | compass/{slug}/subtask-{n} |\n"
                    for n in range(1, rows + 1))
    final_line = f"- **Final subtask count after caps:** {final}\n" if final else ""
    (task_dir / "distribution-map.md").write_text(
        f"# Distribution Map - {slug}\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |\n"
        "|---|---|---|---|\n" + table + "\n"
        "## 5. The cap that applies\n\n" + final_line)
    return repo, slug


def test_mc_1_disagreeing_counts_are_refused(tmp_path):
    repo, slug = _issue(tmp_path, rows=3, final="2")
    result = _run_multiagent(repo, slug, "--dry-run")
    assert result.returncode != 0, result.stdout
    assert "3" in result.stderr and "2" in result.stderr
    assert "Final subtask count" in result.stderr
    assert not (tmp_path / "wt").exists()


def test_mc_1_agreeing_counts_are_provisioned(tmp_path):
    repo, slug = _issue(tmp_path, rows=2, final="2")
    result = _run_multiagent(repo, slug, "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr


def test_mc_1_a_map_that_states_no_count_is_provisioned(tmp_path):
    repo, slug = _issue(tmp_path, rows=2, final=None)
    result = _run_multiagent(repo, slug, "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
