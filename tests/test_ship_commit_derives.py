"""`ship-commit` lands an issue (`DPR-7`).

`ship-commit` is the one step that marks an issue landed. Before 9.0.0 it
also re-derived the living spec (ADR-026); 9.0.0
derives none (ADR-091). `integrate.sh`, which only merged a wave and ran the
combined regression, was removed in 9.0.0 (ADR-090).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd),
                          capture_output=True, text=True)


def _init_repo(d: Path) -> None:
    _git(d, "init", "-q")
    _git(d, "config", "user.email", "t@example.com")
    _git(d, "config", "user.name", "Test")
    _git(d, "config", "commit.gpgsign", "false")
    (d / "README.md").write_text("hello\n", encoding="utf-8")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "init")


def _head(d: Path) -> str:
    return _git(d, "rev-parse", "HEAD").stdout.strip()


def _completed(manifest: dict) -> bool:
    """ship-commit records an issue as done with close reason completed."""
    return manifest.get("status") == "done" and manifest.get("close_reason") == "completed"


def _log_subjects(d: Path, since: str | None = None, count: int = 5) -> list[str]:
    """Commit subjects, newest first: since `since` (exclusive), or the last
    `count` on HEAD when no `since` is given."""
    if since:
        args = ["log", "--format=%s", f"{since}..HEAD"]
    else:
        args = ["log", "--format=%s", f"-{count}"]
    out = _git(d, *args).stdout
    return [line for line in out.splitlines() if line]


def _task(slug: str, *, gates_pass: bool = True, topology: str = "solo",
          scenarios=None, changed_files=None) -> dict:
    if scenarios is None:
        scenarios = [{"id": "DPR-7", "title": "Only ship-commit marks an "
                      "issue landed", "intent": "INT-5"}]
    if changed_files is None:
        changed_files = [{"path": "feature.txt", "scenarios": ["DPR-7"]}]
    return {
        "schema_version": "1.1", "task": slug, "created": "2026-09-25",
        "assessment": {"risk": "contained", "familiarity": "greenfield",
                        "size": "small", "intent": "delivery",
                        "urgency": "none", "role": "engineer", "labels": []},
        "delivery_approach": "standard", "topology": topology,
        "policy_rules_fired": [], "stages": {}, "evidence": [],
        "gates": [{"id": "verify.correctness",
                    "status": "pass" if gates_pass else "pending",
                    "evidence": []}],
        "scenarios": scenarios,
        "changed_files": changed_files,
        "claims": [], "follow_ups": [], "reassessments": [], "friction": [],
    }


def _open_issue(repo: Path, slug: str, *, gates_pass: bool = True,
                 topology: str = "solo", scenarios=None, changed_files=None,
                 file_name: str = "feature.txt") -> Path:
    """Stage a fresh issue's manifest and its one declared file - the
    minimum ship-commit needs to have something of the issue's own to land."""
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    if changed_files is None:
        changed_files = [{"path": file_name, "scenarios": ["DPR-7"]}]
    body = _task(slug, gates_pass=gates_pass, topology=topology,
                 scenarios=scenarios, changed_files=changed_files)
    (task_dir / "manifest.yml").write_text(
        yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    (repo / file_name).write_text("issue work\n", encoding="utf-8")
    (repo / ".compass" / "current-task").write_text(slug, encoding="utf-8")
    _git(repo, "add", "--", file_name, f".compass/work/{slug}/manifest.yml",
         ".compass/current-task")
    return task_dir


def _run_ship_commit(cli_path: Path, repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(cli_path), "ship-commit", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=30)


# ---------------------------------------------------------------------------
# ship-commit lands (DPR-7)
# ---------------------------------------------------------------------------


def test_ship_commit_lands_the_issue_in_one_commit(cli_path, tmp_path):
    """After a successful commit with every gate passed, ship-commit marks
    the issue landed and records its land commit. It makes no second
    commit: no landing derives a living spec (ADR-091)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    slug = "ship-commit-lands"
    task_dir = _open_issue(repo, slug)
    h0 = _head(repo)

    r = _run_ship_commit(cli_path, repo, "-m", "land it", "--issue", slug)
    assert r.returncode == 0, r.stdout + r.stderr

    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert _completed(manifest), manifest
    assert manifest["land_commit"] == _head(repo), manifest
    assert _log_subjects(repo, since=h0) == ["land it"]


def test_rwp_5_ship_commit_says_the_issue_is_marked_done(cli_path, tmp_path):
    """The stored state is `done` (ADR-044), so the message names it, and
    the refusal over a pending gate names it too."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _open_issue(repo, "solo-issue", topology="solo")
    r = _run_ship_commit(cli_path, repo, "-m", "land solo", "--issue", "solo-issue")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "issue marked done." in r.stdout, r.stdout
    assert "marked landed" not in r.stdout, r.stdout

    _open_issue(repo, "gate-pending", gates_pass=False, file_name="other.txt")
    r = _run_ship_commit(cli_path, repo, "-m", "attempt", "--issue", "gate-pending")
    assert r.returncode == 0, r.stdout + r.stderr
    assert re.search(r"NOT marked done: \d+ gate\(s\) have not passed", r.stdout), r.stdout
    assert "marked landed" not in r.stdout, r.stdout


def _commit_issue_at_head(repo: Path, slug: str, *, gates_pass: bool = True,
                          changed_files=None, file_name: str = "feature.txt",
                          scenarios=None) -> Path:
    """Commit an issue's manifest and declared file straight to HEAD, so
    nothing is staged afterwards - the shape a multiagent wave left behind
    before 9.0.0, once every subtask branch was merged."""
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    if changed_files is None:
        changed_files = [{"path": file_name, "scenarios": ["DPR-7"]}]
    body = _task(slug, gates_pass=gates_pass, scenarios=scenarios,
                 changed_files=changed_files)
    (task_dir / "manifest.yml").write_text(
        yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    (repo / file_name).write_text("issue work\n", encoding="utf-8")
    _git(repo, "add", "--", file_name, f".compass/work/{slug}/manifest.yml")
    _git(repo, "commit", "-q", "-m", "integrate: merge " + slug)
    return task_dir


def test_ship_commit_lands_work_already_committed_at_head(cli_path, tmp_path):
    """DPR-7's last line: when every file the issue changed is already
    committed and nothing is staged, ship-commit lands the issue at HEAD -
    no new commit, HEAD itself recorded as land_commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    slug = "already-committed"
    task_dir = _commit_issue_at_head(repo, slug)
    head = _head(repo)
    assert _git(repo, "diff", "--cached", "--quiet").returncode == 0, (
        "nothing should be staged before ship-commit runs")

    r = _run_ship_commit(cli_path, repo, "-m", "land it", "--issue", slug)
    assert r.returncode == 0, r.stdout + r.stderr

    # The land adds no commit.
    assert _head(repo) == head

    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert _completed(manifest), manifest
    assert manifest["land_commit"] == head, manifest
    assert "land_timestamp" in manifest, manifest


def test_ship_commit_refuses_when_a_gate_has_not_passed_and_nothing_is_staged(cli_path, tmp_path):
    """The already-committed path only fires once every gate has passed -
    otherwise ship-commit refuses and names the gate."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    slug = "gate-pending-at-head"
    task_dir = _commit_issue_at_head(repo, slug, gates_pass=False)
    head = _head(repo)

    r = _run_ship_commit(cli_path, repo, "-m", "land it", "--issue", slug)
    assert r.returncode != 0, r.stdout + r.stderr
    combined = (r.stdout + r.stderr).lower()
    assert "nothing staged" in combined, r
    assert "gate" in combined and "verify.correctness" in combined, r

    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert manifest.get("status") != "done", manifest
    assert _head(repo) == head, r


def test_ship_commit_refuses_a_changed_file_with_an_uncommitted_edit(cli_path, tmp_path):
    """A changed file the issue declares must actually be at HEAD, clean -
    an unstaged edit to it refuses the land and names the file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    slug = "dirty-changed-file"
    task_dir = _commit_issue_at_head(repo, slug)
    head = _head(repo)
    (repo / "feature.txt").write_text("edited after the commit\n", encoding="utf-8")

    r = _run_ship_commit(cli_path, repo, "-m", "land it", "--issue", slug)
    assert r.returncode != 0, r.stdout + r.stderr
    combined = (r.stdout + r.stderr).lower()
    assert "nothing staged" in combined, r
    assert "feature.txt" in combined, r

    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert manifest.get("status") != "done", manifest
    assert _head(repo) == head, r


def test_ship_commit_still_refuses_nothing_staged_with_no_issue(run_cli, tmp_path):
    """No `--issue` at all: refuse exactly as before - unchanged behaviour."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    h0 = _head(repo)

    r = run_cli("ship-commit", "-m", "nothing", cwd=repo)
    assert r.returncode != 0, r
    combined = (r.stdout + r.stderr).lower()
    assert "nothing staged" in combined, r
    assert "no issue" in combined or "--issue" in combined, r
    assert _head(repo) == h0, r
