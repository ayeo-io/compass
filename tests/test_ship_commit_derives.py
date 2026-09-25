"""`ship-commit` lands an issue and derives the living spec (`DPR-7`).

ADR-026: `ship-commit` is the one step that marks an issue landed and
re-derives `docs/system-spec.md`, whether the issue was built solo or
through the multiagent protocol. `integrate.sh` only merges a wave and runs
the combined regression - `tests/derive/test_integrate_sh_status.py` and
`tests/test_zero_install_cli.py` pin that half.
"""
from __future__ import annotations

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
# ship-commit lands and derives (DPR-7)
# ---------------------------------------------------------------------------


def test_ship_commit_lands_and_derives_the_spec(cli_path, tmp_path):
    """After a successful commit with every gate passed, ship-commit marks
    the issue landed, derives docs/system-spec.md, and commits the derived
    file on its own, in a commit named after the issue that landed."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    slug = "ship-commit-derives"
    task_dir = _open_issue(repo, slug)
    h0 = _head(repo)

    r = _run_ship_commit(cli_path, repo, "-m", "land it", "--issue", slug)
    assert r.returncode == 0, r.stdout + r.stderr

    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert manifest["status"] == "landed", manifest
    assert "land_commit" in manifest, manifest

    spec_path = repo / "docs" / "system-spec.md"
    assert spec_path.is_file(), "docs/system-spec.md was not derived"
    spec = spec_path.read_text(encoding="utf-8")
    assert slug in spec, spec
    assert "DPR-7" in spec, spec

    subjects = _log_subjects(repo, since=h0)
    assert subjects == [f"Re-derive the living spec after {slug} landed",
                         "land it"], subjects
    # The spec commit itself leaves docs/system-spec.md clean. (The land
    # commit's own manifest.yml gets its status/land_commit written to disk
    # only after that commit exists, since the commit id is not known
    # beforehand - ADR-026's alternatives - so it is not part of this check.)
    assert _git(repo, "status", "--porcelain", "--",
                "docs/system-spec.md").stdout.strip() == "", (
        "the spec commit must leave docs/system-spec.md clean")


def test_ship_commit_derives_for_a_solo_issue(cli_path, tmp_path):
    """Under ADR-008 alone, only integrate.sh derived - so a solo issue,
    which never runs it, left the spec out of date. ship-commit must derive
    for a solo issue exactly as it does for a multiagent one."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    slug = "solo-issue"
    task_dir = _open_issue(repo, slug, topology="solo")
    manifest_before = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert manifest_before["topology"] == "solo"

    r = _run_ship_commit(cli_path, repo, "-m", "land solo", "--issue", slug)
    assert r.returncode == 0, r.stdout + r.stderr

    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert manifest["status"] == "landed", manifest

    spec_path = repo / "docs" / "system-spec.md"
    assert spec_path.is_file(), "docs/system-spec.md was not derived for a solo issue"
    assert slug in spec_path.read_text(encoding="utf-8")


def test_ship_commit_does_not_derive_when_a_gate_has_not_passed(cli_path, tmp_path):
    """The commit still stands, but a gate that has not passed keeps the
    issue off 'landed' - and an issue not marked landed is not derived."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    slug = "gate-pending"
    task_dir = _open_issue(repo, slug, gates_pass=False)
    h0 = _head(repo)

    r = _run_ship_commit(cli_path, repo, "-m", "attempt land", "--issue", slug)
    assert r.returncode == 0, r.stdout + r.stderr  # the commit itself still lands

    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert manifest.get("status") != "landed", manifest

    assert not (repo / "docs" / "system-spec.md").exists(), (
        "docs/system-spec.md must not be derived for an issue that was "
        "not marked landed")
    subjects = _log_subjects(repo, since=h0)
    assert not any(s.startswith("Re-derive the living spec") for s in subjects), subjects


def test_ship_commit_skips_the_spec_commit_when_derivation_is_unchanged(cli_path, tmp_path):
    """A second land whose scenarios add nothing new derives an unchanged
    file - and an unchanged file gets no commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    slug_a = "first-issue"
    _open_issue(repo, slug_a, file_name="feature-a.txt")
    r1 = _run_ship_commit(cli_path, repo, "-m", "land first", "--issue", slug_a)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    spec_after_a = (repo / "docs" / "system-spec.md").read_text(encoding="utf-8")

    slug_b = "second-issue"
    _open_issue(repo, slug_b, file_name="feature-b.txt", scenarios=[],
                changed_files=[{"path": "feature-b.txt", "scenarios": []}])
    h_before = _head(repo)

    r2 = _run_ship_commit(cli_path, repo, "-m", "land second", "--issue", slug_b)
    assert r2.returncode == 0, r2.stdout + r2.stderr

    subjects = _log_subjects(repo, since=h_before)
    assert subjects == ["land second"], (
        "an unchanged derivation must not add a spec commit: " + repr(subjects))
    assert (repo / "docs" / "system-spec.md").read_text(encoding="utf-8") == spec_after_a
