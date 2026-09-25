"""`scripts/multiagent.sh` finds an issue's documents through the artifact
registry and provisions a staged distribution map one wave at a time.

DPR-2's provisioning half: the map and the other documents an issue registers
under `docs/compass/<created>-<slug>/` are read from there, and every
registered document a worktree needs arrives at the same path relative to
the project root. An issue whose documents are still flat under
`.compass/work/<slug>/` - the layout every issue had before the registry -
keeps working unchanged.

DPR-3: a distribution map whose subtask table carries a `Wave` column is
provisioned one wave at a time - `--wave N` scopes both which worktrees get
created and which row count the cap is measured against, so a large map
staged over several waves is never refused for its total. A map with no
`Wave` column behaves exactly as it did before this issue.

Spec: dispatch-protocol/acceptance-criteria.md (`DPR-2`, `DPR-3`).
"""
from __future__ import annotations

import pathlib
import subprocess

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
MULTIAGENT = ROOT / "scripts" / "multiagent.sh"


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True, check=True)


def _init_repo(tmp_path):
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    (repo / ".gitignore").write_text("/.compass/work/\n/.compass/current-task\n")
    (repo / ".compass").mkdir()
    (repo / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\nworktree_root: ../wt\nmax_worktrees: 4\n")
    (repo / "README.md").write_text("# demo\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _run_multiagent(repo, slug, *extra_args):
    return subprocess.run(
        ["bash", str(MULTIAGENT), slug, *extra_args],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
    )


def _manifest(*, artifacts=None):
    body = {
        "task": "placeholder",
        "assessment": {"risk": "contained"},
        "fired_guardrails": [],
    }
    if artifacts:
        body["artifacts"] = artifacts
    return yaml.safe_dump(body, sort_keys=False)


# ---------------------------------------------------------------------------
# DPR-2 (provisioning half) - documents found through the artifact registry
# ---------------------------------------------------------------------------

def test_dpr2_reads_the_map_from_the_registered_path_and_seeds_it(tmp_path):
    """Given an issue whose distribution map and acceptance criteria are
    registered under docs/compass/<created>-<slug>/, when multiagent.sh
    provisions it, it reads the map from the registered path and each
    worktree receives every registered document at the same relative path."""
    repo = _init_repo(tmp_path)
    slug = "reg-demo"
    docs_dir = repo / "docs" / "compass" / "2026-09-25-reg-demo"
    docs_dir.mkdir(parents=True)
    (docs_dir / "distribution-map.md").write_text(
        "# Distribution Map - reg-demo\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |\n"
        "|---|---|---|---|\n"
        f"| subtask-1 | U1 | DPR-2 | compass/{slug}/subtask-1 |\n"
    )
    (docs_dir / "acceptance-criteria.md").write_text("# Spec - reg-demo\n")
    (docs_dir / "delivery-approach.md").write_text("# Delivery approach - reg-demo\n")

    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest(artifacts=[
        {"id": "ART-1", "kind": "distribution-map", "status": "approved",
         "path": "docs/compass/2026-09-25-reg-demo/distribution-map.md"},
        {"id": "ART-2", "kind": "acceptance-criteria", "status": "approved",
         "path": "docs/compass/2026-09-25-reg-demo/acceptance-criteria.md"},
        {"id": "ART-3", "kind": "delivery-approach", "status": "approved",
         "path": "docs/compass/2026-09-25-reg-demo/delivery-approach.md"},
    ]))
    # No flat copy of the map or the approach record beside the manifest -
    # the only way multiagent.sh can find either is through the registry.

    result = _run_multiagent(repo, slug, "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "subtask-1" in result.stdout

    result = _run_multiagent(repo, slug)
    assert result.returncode == 0, result.stdout + result.stderr

    wt = tmp_path / "wt" / f"{slug}-subtask-1"
    for rel in (
        "docs/compass/2026-09-25-reg-demo/distribution-map.md",
        "docs/compass/2026-09-25-reg-demo/acceptance-criteria.md",
        "docs/compass/2026-09-25-reg-demo/delivery-approach.md",
    ):
        seeded = wt / rel
        assert seeded.is_file(), f"{rel} did not reach the worktree at its registered path"


def test_dpr2_legacy_flat_layout_still_works(tmp_path):
    """An issue whose map is still under .compass/work/<slug>/, with no
    `artifacts:` registry entry at all, works as before."""
    repo = _init_repo(tmp_path)
    slug = "flat-demo"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text("# Delivery approach - flat-demo\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - flat-demo\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |\n"
        "|---|---|---|---|\n"
        f"| subtask-1 | U1 | DPR-2 | compass/{slug}/subtask-1 |\n"
    )

    result = _run_multiagent(repo, slug)
    assert result.returncode == 0, result.stdout + result.stderr

    wt = tmp_path / "wt" / f"{slug}-subtask-1"
    assert (wt / ".compass" / "work" / slug / "distribution-map.md").is_file()
    assert (wt / ".compass" / "work" / slug / "delivery-approach.md").is_file()


# ---------------------------------------------------------------------------
# DPR-3 - a staged map is provisioned one wave at a time
# ---------------------------------------------------------------------------

def _staged_map(slug, n_subtasks, waves):
    rows = [
        "# Distribution Map - staged",
        "",
        "## 3. Scenario-group -> subtask mapping",
        "",
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name | Wave |",
        "|---|---|---|---|---|",
    ]
    for i in range(1, n_subtasks + 1):
        rows.append(
            f"| subtask-{i} | U{i} | S{i} | compass/{slug}/subtask-{i} | {waves[i - 1]} |")
    return "\n".join(rows) + "\n"


def _staged_task(repo, slug):
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    # 7 subtasks over 3 waves of at most 3: wave 1 has 3, wave 2 has 2, wave 3
    # has 2 - the worktree ceiling (4, from _init_repo's config.yml) is below
    # the map's total (7) but above every individual wave.
    waves = [1, 1, 1, 2, 2, 3, 3]
    (task_dir / "distribution-map.md").write_text(_staged_map(slug, 7, waves))
    return task_dir


def test_dpr3_wave_flag_provisions_only_that_wave(tmp_path):
    """--wave 2 creates the worktrees for wave 2 only, and is not refused for
    the map's total even though the total (7) is over the ceiling (4)."""
    repo = _init_repo(tmp_path)
    slug = "wave-demo"
    _staged_task(repo, slug)

    result = _run_multiagent(repo, slug, "--wave", "2", "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "but the cap is" not in result.stdout + result.stderr
    for i in (4, 5):
        assert f"subtask-{i}" in result.stdout
    for i in (1, 2, 3, 6, 7):
        assert f"subtask-{i}:" not in result.stdout


def test_dpr3_default_wave_is_one_and_names_the_next(tmp_path):
    """Without --wave, multiagent.sh provisions wave 1 and names the next
    wave."""
    repo = _init_repo(tmp_path)
    slug = "wave-default"
    _staged_task(repo, slug)

    result = _run_multiagent(repo, slug, "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    for i in (1, 2, 3):
        assert f"subtask-{i}" in result.stdout
    for i in (4, 5, 6, 7):
        assert f"subtask-{i}:" not in result.stdout
    assert "wave 2" in result.stdout.lower()


def test_dpr3_wave_above_the_maps_highest_is_refused(tmp_path):
    """A wave number above the map's highest staged wave is refused."""
    repo = _init_repo(tmp_path)
    slug = "wave-over"
    _staged_task(repo, slug)

    result = _run_multiagent(repo, slug, "--wave", "4", "--dry-run")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "wave 4" in (result.stdout + result.stderr).lower()


def test_dpr3_map_without_wave_column_behaves_as_before(tmp_path):
    """A map with no Wave column ignores waves entirely and provisions every
    subtask, exactly as multiagent.sh did before this issue."""
    repo = _init_repo(tmp_path)
    slug = "no-wave-column"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - no-wave-column\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |\n"
        "|---|---|---|---|\n"
        f"| subtask-1 | U1 | S1 | compass/{slug}/subtask-1 |\n"
        f"| subtask-2 | U2 | S2 | compass/{slug}/subtask-2 |\n"
    )

    result = _run_multiagent(repo, slug, "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "subtask-1" in result.stdout
    assert "subtask-2" in result.stdout
