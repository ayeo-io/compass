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
    out = result.stdout + result.stderr
    assert result.returncode != 0, out
    assert (repo / "feature.txt").read_text() == "local, uncommitted, in the way\n"
    # The merge never started, so there is nothing to abort and no conflict
    # to name - the report must say so, name the file git refused over, and
    # must not claim a conflict happened or try (and fail) to abort one.
    assert "feature.txt" in out, out
    assert "no merge to abort" not in out.lower(), out
    assert "Conflicted files:\n    - \n" not in out, out


def test_dpr4_base_deleted_record_file_still_completes_merge(tmp_path):
    """The base branch deletes a record file that a later subtask still
    changes - a delete/modify conflict. It is confined to Compass's own
    records, so the merge must still complete: the base's side (the
    deletion) wins, and the file is named as removed."""
    repo = _init_repo(tmp_path)
    slug = "delete-modify-demo"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text("status: created\n")
    (task_dir / "notes.md").write_text("subtask-1 will delete this\n")
    branch1 = f"compass/{slug}/subtask-1"
    branch2 = f"compass/{slug}/subtask-2"
    (task_dir / "distribution-map.md").write_text(
        _map_text([("subtask-1", branch1), ("subtask-2", branch2)]))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add manifest, notes and map")

    _git(repo, "checkout", "-q", "-b", branch2)
    (task_dir / "notes.md").write_text("subtask-2 still edits notes\n")
    _git(repo, "commit", "-q", "-am", "subtask-2 edits notes.md")

    _git(repo, "checkout", "-q", "main")
    _git(repo, "checkout", "-q", "-b", branch1)
    _git(repo, "rm", "-q", str((task_dir / "notes.md").relative_to(repo)))
    _git(repo, "commit", "-q", "-m", "subtask-1 removes notes.md")

    _git(repo, "checkout", "-q", "main")

    result = _run_integrate(repo, slug)
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    rel = f".compass/work/{slug}/notes.md"
    assert rel in out, out
    assert "removed" in out.lower(), out
    assert not (task_dir / "notes.md").exists()
    log = _git(repo, "log", "--oneline", "main").stdout
    assert "subtask-1" in log and "subtask-2" in log, log


def test_dpr4_resolve_failure_aborts_and_leaves_repo_clean(tmp_path):
    """If any step of resolving a records-only conflict fails - here, a
    commit hook rejects the resolving commit - integrate.sh must abort the
    merge, leave the repository clean, and exit non-zero saying so, instead
    of leaving the merge half done."""
    repo = _init_repo(tmp_path)
    slug = "resolve-failure-demo"
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

    hooks_dir = repo / ".githooks"
    hooks_dir.mkdir()
    hook = hooks_dir / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'pre-commit: refused' >&2\nexit 1\n")
    hook.chmod(0o755)
    _git(repo, "config", "core.hooksPath", ".githooks")

    result = _run_integrate(repo, slug)
    out = result.stdout + result.stderr
    assert result.returncode != 0, out
    assert (repo / ".git" / "MERGE_HEAD").exists() is False
    status = _git(repo, "status", "--porcelain", "--untracked-files=no").stdout
    assert status == "", status


# ---------------------------------------------------------------------------
# DPR-4 - the two rules that matter most, pinned directly
# ---------------------------------------------------------------------------

def test_dpr4_mixed_conflict_one_record_one_code_file_still_aborts(tmp_path):
    """A conflict spanning one record file and one code file must abort as a
    whole - resolving the record and silently discarding the code file's
    conflict would be the most dangerous way this script could break."""
    repo = _init_repo(tmp_path)
    slug = "mixed-demo"
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
    _git(repo, "commit", "-q", "-m", "add manifest, app and map")

    _git(repo, "checkout", "-q", "-b", branch1)
    (task_dir / "manifest.yml").write_text("status: subtask-1-done\n")
    app.write_text("value = 2\n")
    _git(repo, "commit", "-q", "-am", "subtask-1 changes manifest and app")

    _git(repo, "checkout", "-q", "main")
    _git(repo, "checkout", "-q", "-b", branch2)
    (task_dir / "manifest.yml").write_text("status: subtask-2-done\n")
    app.write_text("value = 3\n")
    _git(repo, "commit", "-q", "-am", "subtask-2 changes manifest and app")

    _git(repo, "checkout", "-q", "main")

    result = _run_integrate(repo, slug)
    out = result.stdout + result.stderr
    assert result.returncode == 2, out
    assert "app.py" in out, out
    assert f".compass/work/{slug}/manifest.yml" in out, out
    status = _git(repo, "status", "--porcelain").stdout
    assert status == "", status


def test_dpr4_conflict_only_under_docs_compass_completes_merge(tmp_path):
    """A conflict confined to docs/compass/ - the moved-document half of
    Compass's records, not just .compass/ - must also complete the merge."""
    repo = _init_repo(tmp_path)
    slug = "docs-compass-demo"
    docs_dir = repo / "docs" / "compass" / f"2026-09-25-{slug}"
    docs_dir.mkdir(parents=True)
    (docs_dir / "notes.md").write_text("created\n")
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    branch1 = f"compass/{slug}/subtask-1"
    branch2 = f"compass/{slug}/subtask-2"
    (task_dir / "distribution-map.md").write_text(
        _map_text([("subtask-1", branch1), ("subtask-2", branch2)]))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add docs note and map")

    _git(repo, "checkout", "-q", "-b", branch1)
    (docs_dir / "notes.md").write_text("subtask-1 notes\n")
    _git(repo, "commit", "-q", "-am", "subtask-1 edits notes")

    _git(repo, "checkout", "-q", "main")
    _git(repo, "checkout", "-q", "-b", branch2)
    (docs_dir / "notes.md").write_text("subtask-2 notes\n")
    _git(repo, "commit", "-q", "-am", "subtask-2 edits notes")

    _git(repo, "checkout", "-q", "main")

    result = _run_integrate(repo, slug)
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    rel = f"docs/compass/2026-09-25-{slug}/notes.md"
    assert rel in out, out
    status = _git(repo, "status", "--porcelain", "--untracked-files=no").stdout
    assert status == "", status


def test_integrate_does_not_mark_the_issue_landed_or_derive_the_living_spec(tmp_path):
    """integrate.sh runs before the verify stage, and on a staged
    (multi-wave) map it can run more than once for the same issue - it
    must not write status: landed or land_timestamp into manifest.yml, and
    must not derive docs/system-spec.md (which only ever reads landed
    issues). Only `ship-commit` marks an issue landed, once the verify stage
    has passed - integrate.sh must name that as the next step instead."""
    repo = _init_repo(tmp_path)
    slug = "no-early-landed-demo"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    manifest_before = "status: created\nassessment:\n  risk: contained\n"
    (task_dir / "manifest.yml").write_text(manifest_before)
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

    result = _run_integrate(repo, slug)
    out = result.stdout + result.stderr
    assert result.returncode == 0, out

    assert (task_dir / "manifest.yml").read_text() == manifest_before
    assert not (repo / "docs" / "system-spec.md").exists()
    assert "status: landed" not in out
    assert "land_timestamp" not in out

    # The next step is named explicitly, in order: /compass:verify, then
    # ship-commit.
    verify_at = out.lower().index("verify")
    ship_commit_at = out.lower().index("ship-commit")
    assert verify_at < ship_commit_at, out


def test_integrate_closing_message_names_the_next_wave_and_the_last_wave(tmp_path):
    """DPR-5: since ADR-026, integrate.sh runs before /compass:verify and
    never lands the issue - a wave's worktrees are what get provisioned or
    reviewed next, not a return to a ship stage that no longer follows it.
    integrate.sh cannot tell a wave before the last from the last wave (it
    reads no Wave column), so its closing message must name both next
    steps: provisioning the next wave, and reviewing the integrated result
    before /compass:verify. The old "Back in /compass:ship, finish by"
    wording - which sent the reader to steps ship no longer owns - must be
    gone."""
    repo = _init_repo(tmp_path)
    slug = "closing-message-demo"
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

    result = _run_integrate(repo, slug)
    out = result.stdout + result.stderr
    assert result.returncode == 0, out

    assert "Back in /compass:ship, finish by" not in out, out
    assert "multiagent.sh" in out and "--wave" in out, out
    assert "review" in out.lower(), out
    assert "/compass:verify" in out, out
    assert f"only ship-commit marks '{slug}' landed" in out, out


def test_dpr4_rename_from_outside_records_into_docs_compass_still_aborts(tmp_path):
    """The security review found that a builder renames source code into
    docs/compass/ and edits it, while the base branch edits the original
    path differently. The conflicted path git reports is the rename's
    destination, inside docs/compass/ - but the conflicting work began
    outside the record directories, so this must abort like any other
    cross-subtask conflict, not resolve as records-only and drop the
    builder's edit."""
    repo = _init_repo(tmp_path)
    slug = "rename-escape-demo"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text("status: created\n")
    src = repo / "src"
    src.mkdir()
    app = src / "app.py"
    # 40 lines: git's default rename-detection similarity threshold needs
    # enough content to tell a one-line edit from an unrelated new file.
    original = "\n".join(f"line{i}" for i in range(1, 41)) + "\n"
    app.write_text(original)
    branch1 = f"compass/{slug}/subtask-1"
    (task_dir / "distribution-map.md").write_text(
        _map_text([("subtask-1", branch1)]))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add app.py and map")

    _git(repo, "checkout", "-q", "-b", branch1)
    dest_dir = repo / "docs" / "compass"
    dest_dir.mkdir(parents=True)
    dest = dest_dir / "app.py"
    _git(repo, "mv", "src/app.py", "docs/compass/app.py")
    lines = original.splitlines()
    lines[19] = "line20-subtask"
    dest.write_text("\n".join(lines) + "\n")
    _git(repo, "commit", "-q", "-am", "subtask-1 renames app.py into docs/compass and edits it")

    _git(repo, "checkout", "-q", "main")
    lines = original.splitlines()
    lines[19] = "line20-base"
    app.write_text("\n".join(lines) + "\n")
    _git(repo, "commit", "-q", "-am", "base edits src/app.py differently")

    result = _run_integrate(repo, slug)
    out = result.stdout + result.stderr
    assert result.returncode == 2, out
    assert "kept" not in out.lower(), out
    status = _git(repo, "status", "--porcelain").stdout
    assert status == "", status
    # The merge must not have landed - neither app.py's content is chosen
    # silently, and MERGE_HEAD is gone (the abort left the repo clean).
    assert not (repo / ".git" / "MERGE_HEAD").exists()


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


def test_dpr2_integrate_reads_branch_column_by_header_not_position(tmp_path):
    """A Wave column placed before Branch name must not shift which cell
    integrate.sh reads as the branch - it reads the subtask table's own
    header, as scripts/multiagent.sh does, not a fixed cell position. A map
    with no Wave column (the fixture default in _map_text) already covers
    the plain, unstaged case; this covers a staged map."""
    repo = _init_repo(tmp_path)
    slug = "wave-header-demo"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text("status: created\n")
    branch1 = f"compass/{slug}/subtask-1"
    map_text = "\n".join([
        "# Distribution Map",
        "",
        "## 3. Scenario-group -> subtask mapping",
        "",
        "| Subtask | Wave | Owns work unit(s) | Owns scenario ids | Branch name |",
        "|---|---|---|---|---|",
        f"| subtask-1 | 1 | U1 | S1 | {branch1} |",
    ]) + "\n"
    (task_dir / "distribution-map.md").write_text(map_text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add manifest and staged map")

    _git(repo, "checkout", "-q", "-b", branch1)
    (repo / "feature.txt").write_text("feature work\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "subtask-1 work")
    _git(repo, "checkout", "-q", "main")

    result = _run_integrate(repo, slug)
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert "skipping" not in out.lower(), out
    assert (repo / "feature.txt").is_file()
    log = _git(repo, "log", "--oneline", "main").stdout
    assert "subtask-1" in log, log
