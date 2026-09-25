"""`scripts/integrate.sh` reads an issue's distribution map through the
artifact registry and keeps a merge going when a conflict is confined to
Compass's own records.

DPR-2's integration half: integrate.sh reads the map from the path the
registry names, under `docs/compass/<created>-<slug>/`, and an issue whose
map is still flat under `.compass/work/<slug>/` works as before.

DPR-4: a merge conflict confined to `.compass/` or `docs/compass/` keeps the
base branch's copy of the conflicted file, completes the merge, and names
the file it kept. A conflict anywhere else still aborts the merge and
leaves the repository clean, as before. integrate.sh also refuses to start
only for changes to tracked files - an untracked file no merge touches must
not stop it, even though git itself still refuses a merge that would
overwrite one.

Spec: dispatch-protocol/acceptance-criteria.md (`DPR-2`, `DPR-4`).
"""
from __future__ import annotations

import pathlib
import subprocess

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
INTEGRATE = ROOT / "scripts" / "integrate.sh"


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True, check=True)


def _init_repo(tmp_path, name="proj"):
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    (repo / ".compass").mkdir()
    (repo / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\nworktree_root: ../wt\nmax_worktrees: 4\n")
    (repo / "README.md").write_text("# demo\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _manifest_yaml(*, artifacts=None):
    body = {
        "task": "placeholder",
        "assessment": {"risk": "contained"},
        "fired_guardrails": [],
    }
    if artifacts:
        body["artifacts"] = artifacts
    return yaml.safe_dump(body, sort_keys=False)


def _map_text(rows):
    lines = [
        "# Distribution Map",
        "",
        "## 3. Scenario-group -> subtask mapping",
        "",
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |",
        "|---|---|---|---|",
    ]
    for sid, branch in rows:
        lines.append(f"| {sid} | U1 | S1 | {branch} |")
    return "\n".join(lines) + "\n"


def _run_integrate(repo, slug, *extra_args):
    return subprocess.run(
        ["bash", str(INTEGRATE), slug, *extra_args],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
    )


# ---------------------------------------------------------------------------
# DPR-4 - a conflict confined to Compass's own records does not stop
# integration
# ---------------------------------------------------------------------------

def test_dpr4_conflict_confined_to_manifest_completes_merge_and_names_it(tmp_path):
    """Two subtask branches both change manifest.yml. Merging the second
    conflicts only on that file; integrate.sh keeps the base branch's copy,
    completes the merge, and names the file it kept."""
    repo = _init_repo(tmp_path)
    slug = "confined-demo"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text("status: created\n")
    branch1 = f"compass/{slug}/subtask-1"
    branch2 = f"compass/{slug}/subtask-2"
    (task_dir / "distribution-map.md").write_text(
        _map_text([("subtask-1", branch1), ("subtask-2", branch2)]))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add manifest and map")

    _git(repo, "checkout", "-q", "-b", branch1)
    (task_dir / "manifest.yml").write_text("status: subtask-1-done\n")
    _git(repo, "commit", "-q", "-am", "subtask-1 updates manifest")

    _git(repo, "checkout", "-q", "main")
    _git(repo, "checkout", "-q", "-b", branch2)
    (task_dir / "manifest.yml").write_text("status: subtask-2-done\n")
    _git(repo, "commit", "-q", "-am", "subtask-2 updates manifest")

    _git(repo, "checkout", "-q", "main")

    result = _run_integrate(repo, slug)
    assert result.returncode == 0, result.stdout + result.stderr
    out = result.stdout + result.stderr
    rel = f".compass/work/{slug}/manifest.yml"
    assert rel in out, out
    assert "kept" in out.lower(), out

    # The merge commit itself, not the working tree (a later, uncommitted
    # step rewrites manifest.yml's status to "landed"), shows which side won.
    committed = _git(repo, "show", f"HEAD:{rel}").stdout
    assert committed == "status: subtask-1-done\n", committed


def test_dpr4_conflict_outside_compass_records_still_aborts(tmp_path):
    """A conflict in a file outside .compass/ and docs/compass/ still aborts
    the merge and leaves the repository clean, as before."""
    repo = _init_repo(tmp_path)
    slug = "abort-demo"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text("status: created\n")
    app = repo / "app.py"
    app.write_text("value = 1\n")
    branch1 = f"compass/{slug}/subtask-1"
    branch2 = f"compass/{slug}/subtask-2"
    (task_dir / "distribution-map.md").write_text(
        _map_text([("subtask-1", branch1), ("subtask-2", branch2)]))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add app and map")

    _git(repo, "checkout", "-q", "-b", branch1)
    app.write_text("value = 2\n")
    _git(repo, "commit", "-q", "-am", "subtask-1 changes app")

    _git(repo, "checkout", "-q", "main")
    _git(repo, "checkout", "-q", "-b", branch2)
    app.write_text("value = 3\n")
    _git(repo, "commit", "-q", "-am", "subtask-2 changes app")

    _git(repo, "checkout", "-q", "main")

    result = _run_integrate(repo, slug)
    assert result.returncode == 2, result.stdout + result.stderr
    out = result.stdout + result.stderr
    assert "app.py" in out
    assert "CONFLICT" in out

    status = _git(repo, "status", "--porcelain").stdout
    assert status == "", status
    # subtask-1 merged cleanly before subtask-2 conflicted.
    log = _git(repo, "log", "--oneline", "main").stdout
    assert "subtask-1" in log


def test_dpr4_untracked_file_not_touched_does_not_stop_integration(tmp_path):
    """integrate.sh refuses to start only for changes to tracked files. An
    untracked file that no merge touches must not stop it, even though it
    would have tripped the old blanket dirty check."""
    repo = _init_repo(tmp_path)
    slug = "untracked-demo"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text("status: created\n")
    branch1 = f"compass/{slug}/subtask-1"
    (task_dir / "distribution-map.md").write_text(
        _map_text([("subtask-1", branch1)]))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add manifest and map")

    _git(repo, "checkout", "-q", "-b", branch1)
    (repo / "feature.txt").write_text("feature work\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "subtask-1 adds feature.txt")

    _git(repo, "checkout", "-q", "main")

    scratch = repo / "scratch-notes.txt"
    scratch.write_text("not part of any branch\n")

    result = _run_integrate(repo, slug)
    assert result.returncode == 0, result.stdout + result.stderr
    out = result.stdout + result.stderr
    assert "dirty" not in out.lower(), out
    assert scratch.read_text() == "not part of any branch\n"


def test_dpr4_untracked_file_a_merge_would_overwrite_still_stops_git(tmp_path):
    """An untracked file a merge would overwrite still stops integration -
    git's own protection, which integrate.sh relies on rather than
    duplicating."""
    repo = _init_repo(tmp_path)
    slug = "overwrite-demo"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text("status: created\n")
    branch1 = f"compass/{slug}/subtask-1"
    (task_dir / "distribution-map.md").write_text(
        _map_text([("subtask-1", branch1)]))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add manifest and map")

    _git(repo, "checkout", "-q", "-b", branch1)
    (repo / "feature.txt").write_text("feature work\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "subtask-1 adds feature.txt")

    _git(repo, "checkout", "-q", "main")
    # An untracked file at the exact path the merge would create.
    (repo / "feature.txt").write_text("local, uncommitted, in the way\n")

    result = _run_integrate(repo, slug)
    assert result.returncode != 0, result.stdout + result.stderr
    assert (repo / "feature.txt").read_text() == "local, uncommitted, in the way\n"


# ---------------------------------------------------------------------------
# DPR-2 - integrate.sh reads the map through the artifact registry
# ---------------------------------------------------------------------------

def test_dpr2_integrate_reads_map_from_registered_path(tmp_path):
    """A map registered under docs/compass/<created>-<slug>/ - with no flat
    copy beside the manifest at all - is read from the registered path."""
    repo = _init_repo(tmp_path)
    slug = "reg-integrate"
    docs_dir = repo / "docs" / "compass" / "2026-09-25-reg-integrate"
    docs_dir.mkdir(parents=True)
    branch1 = f"compass/{slug}/subtask-1"
    (docs_dir / "distribution-map.md").write_text(
        _map_text([("subtask-1", branch1)]))

    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest_yaml(artifacts=[
        {"id": "ART-1", "kind": "distribution-map", "status": "approved",
         "path": f"docs/compass/2026-09-25-{slug}/distribution-map.md"},
    ]))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "register map")

    _git(repo, "checkout", "-q", "-b", branch1)
    (repo / "feature.txt").write_text("feature work\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "subtask-1 work")
    _git(repo, "checkout", "-q", "main")

    result = _run_integrate(repo, slug)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (repo / "feature.txt").is_file()
    log = _git(repo, "log", "--oneline", "main").stdout
    assert "subtask-1" in log


def test_dpr2_integrate_flat_map_still_works(tmp_path):
    """An issue whose map is still under .compass/work/<slug>/, with no
    artifacts: registry entry at all, works as before."""
    repo = _init_repo(tmp_path)
    slug = "flat-integrate"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest_yaml())
    branch1 = f"compass/{slug}/subtask-1"
    (task_dir / "distribution-map.md").write_text(
        _map_text([("subtask-1", branch1)]))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "flat map")

    _git(repo, "checkout", "-q", "-b", branch1)
    (repo / "feature.txt").write_text("feature work\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "subtask-1 work")
    _git(repo, "checkout", "-q", "main")

    result = _run_integrate(repo, slug)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (repo / "feature.txt").is_file()
