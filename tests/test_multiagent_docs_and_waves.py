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

import os
import pathlib
import shutil
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


def _fake_python3(tmp_path, *, on_compass_call=None, log_artifact_path_to=None):
    """A `python3` stand-in placed first on PATH, so a test can watch or
    break the one process multiagent.sh cannot avoid starting: the resolver
    it runs through `compass_python`. Every other call - reading
    manifest.yml, the cap - is passed straight to the real interpreter, so
    only the behaviour under test differs from an ordinary run.

    `on_compass_call` - shell snippet run (before delegating) whenever the
    first argument is `cli/compass`; a crash is simulated by exiting there.
    `log_artifact_path_to` - a file every `issue artifact-path <kind>` call
    appends its kind to, so a test can count resolver starts.
    """
    real_python3 = shutil.which("python3")
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir(exist_ok=True)
    wrapper = fakebin / "python3"
    lines = ["#!/bin/bash", 'is_compass=0',
             'case "$(basename "$1" 2>/dev/null)" in compass) is_compass=1 ;; esac']
    if log_artifact_path_to is not None:
        lines.append(
            f'if [ "$is_compass" = "1" ] && [ "$2" = "issue" ] && '
            f'[ "$3" = "artifact-path" ]; then echo "$4" >> "{log_artifact_path_to}"; fi'
        )
    if on_compass_call is not None:
        lines.append(f'if [ "$is_compass" = "1" ]; then {on_compass_call}; fi')
    lines.append(f'exec "{real_python3}" "$@"')
    wrapper.write_text("\n".join(lines) + "\n")
    wrapper.chmod(0o755)
    return fakebin


def _env_with_fake_python3(fakebin):
    env = dict(os.environ)
    env["PATH"] = f"{fakebin}{os.pathsep}{env.get('PATH', '')}"
    return env


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


def test_dpr2_refused_registry_entry_is_not_rescued_by_the_flat_file(tmp_path):
    """A registered path that resolves outside the project is REFUSED by the
    resolver. A flat distribution-map.md sitting beside the manifest must
    not rescue it - the refusal exists for exactly this case."""
    repo = _init_repo(tmp_path)
    slug = "refused-demo"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest(artifacts=[
        {"id": "ART-1", "kind": "distribution-map", "status": "approved",
         "path": "../outside.md"},
    ]))
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - refused-demo\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |\n"
        "|---|---|---|---|\n"
        f"| subtask-1 | U1 | S1 | compass/{slug}/subtask-1 |\n"
    )
    (repo / "outside.md").write_text("# outside\n")

    result = _run_multiagent(repo, slug, "--dry-run")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "subtask-1" not in result.stdout
    out = result.stdout + result.stderr
    assert "the design stage must produce it first" not in out, (
        "a refused entry is not a missing map")


def test_dpr2_omitted_registry_entry_is_not_rescued_by_the_flat_file(tmp_path):
    """A registry entry recorded `status: omitted` is a decision, not an
    absence. A flat distribution-map.md beside the manifest must not
    override that decision."""
    repo = _init_repo(tmp_path)
    slug = "omitted-demo"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest(artifacts=[
        {"id": "ART-1", "kind": "distribution-map", "status": "omitted",
         "reason": "solo route, no parallel work"},
    ]))
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - omitted-demo\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |\n"
        "|---|---|---|---|\n"
        f"| subtask-1 | U1 | S1 | compass/{slug}/subtask-1 |\n"
    )

    result = _run_multiagent(repo, slug, "--dry-run")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "subtask-1" not in result.stdout
    out = result.stdout + result.stderr
    assert "the design stage must produce it first" not in out, (
        "an omitted entry is a recorded decision, not a missing map")


def test_dpr2_resolver_crash_shows_its_own_error(tmp_path):
    """When the resolver cannot even run - the way an interpreter too old
    to import cli/compass fails - the script must show that error, not the
    generic "the design stage must produce it first" message a genuine
    absence gets."""
    repo = _init_repo(tmp_path)
    slug = "crash-demo"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - crash-demo\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |\n"
        "|---|---|---|---|\n"
        f"| subtask-1 | U1 | S1 | compass/{slug}/subtask-1 |\n"
    )

    fakebin = _fake_python3(
        tmp_path,
        on_compass_call=(
            'echo "Traceback (most recent call last):" >&2; '
            'echo "ImportError: simulated - this interpreter cannot run '
            'cli/compass" >&2; exit 1'
        ),
    )
    env = _env_with_fake_python3(fakebin)
    result = subprocess.run(
        ["bash", str(MULTIAGENT), slug, "--dry-run"],
        cwd=str(repo), capture_output=True, text=True, timeout=120, env=env,
    )
    assert result.returncode != 0, result.stdout + result.stderr
    out = result.stdout + result.stderr
    assert "ImportError" in out
    assert "the design stage must produce it first" not in out, (
        "a crashed resolver is not a missing map")


def test_dpr2_seeding_skips_a_destination_that_resolves_outside_the_worktree(tmp_path):
    """A branch whose checked-out tree makes a path component a symlink to
    outside the worktree must not have documents seeded through it - the
    destination is resolved and skipped, with a note, unless it lands
    inside the worktree (finding 1 of the dispatch-protocol security
    review)."""
    repo = _init_repo(tmp_path)
    slug = "evil-demo"
    created = "2026-09-25"
    docs_dir = repo / "docs" / "compass" / f"{created}-{slug}"
    docs_dir.mkdir(parents=True)
    (docs_dir / "distribution-map.md").write_text(
        "# Distribution Map - evil-demo\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |\n"
        "|---|---|---|---|\n"
        "| subtask-1 | U1 | S1 | evil |\n"
    )
    (docs_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (docs_dir / "acceptance-criteria.md").write_text("# Spec - evil-demo\n")
    # The registered docs must be TRACKED on main, or checking back to main
    # after the evil branch destroys the real docs/ directory loses them.
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add evil-demo docs")

    outside = tmp_path / "outside"
    outside.mkdir()
    _git(repo, "checkout", "-q", "-b", "evil")
    shutil.rmtree(repo / "docs")
    (repo / "docs").symlink_to(outside)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "docs is a symlink to outside the worktree")
    _git(repo, "checkout", "-q", "main")

    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest(artifacts=[
        {"id": "ART-1", "kind": "distribution-map", "status": "approved",
         "path": f"docs/compass/{created}-{slug}/distribution-map.md"},
        {"id": "ART-2", "kind": "delivery-approach", "status": "approved",
         "path": f"docs/compass/{created}-{slug}/delivery-approach.md"},
        {"id": "ART-3", "kind": "acceptance-criteria", "status": "approved",
         "path": f"docs/compass/{created}-{slug}/acceptance-criteria.md"},
    ]))

    result = _run_multiagent(repo, slug)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (outside / "compass").exists(), (
        "seeding must not create anything under a symlinked path component")


def test_dpr2_seeding_skips_a_dangling_symlink_already_at_the_destination(tmp_path):
    """A branch that tracks a registered document's exact path as a symlink
    to a file that does not exist must not have that destination written
    through - `cp` would otherwise create the missing target outside the
    worktree (finding 1, case E2, dispatch-protocol security review)."""
    repo = _init_repo(tmp_path)
    slug = "evil2-demo"
    created = "2026-09-25"
    docs_dir = repo / "docs" / "compass" / f"{created}-{slug}"
    docs_dir.mkdir(parents=True)
    (docs_dir / "distribution-map.md").write_text(
        "# Distribution Map - evil2-demo\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |\n"
        "|---|---|---|---|\n"
        "| subtask-1 | U1 | S1 | evil2 |\n"
    )
    (docs_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (docs_dir / "acceptance-criteria.md").write_text("# Spec - evil2-demo\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add evil2-demo docs")

    outside_target = tmp_path / "outside2" / "target.md"

    _git(repo, "checkout", "-q", "-b", "evil2")
    (docs_dir / "acceptance-criteria.md").unlink()
    (docs_dir / "acceptance-criteria.md").symlink_to(outside_target)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "acceptance-criteria.md is a dangling symlink")
    _git(repo, "checkout", "-q", "main")

    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest(artifacts=[
        {"id": "ART-1", "kind": "distribution-map", "status": "approved",
         "path": f"docs/compass/{created}-{slug}/distribution-map.md"},
        {"id": "ART-2", "kind": "delivery-approach", "status": "approved",
         "path": f"docs/compass/{created}-{slug}/delivery-approach.md"},
        {"id": "ART-3", "kind": "acceptance-criteria", "status": "approved",
         "path": f"docs/compass/{created}-{slug}/acceptance-criteria.md"},
    ]))

    result = _run_multiagent(repo, slug)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not outside_target.exists(), (
        "seeding must not write through a dangling symlink at the destination")


def test_dpr2_registered_document_that_is_a_symlink_is_not_seeded(tmp_path):
    """A registered document that is itself a symlink is not copied in - its
    target was never vetted and can sit outside the project (finding 7 of
    the dispatch-protocol security review)."""
    repo = _init_repo(tmp_path)
    slug = "symlink-doc"
    created = "2026-09-25"
    docs_dir = repo / "docs" / "compass" / f"{created}-{slug}"
    docs_dir.mkdir(parents=True)
    (docs_dir / "distribution-map.md").write_text(
        "# Distribution Map - symlink-doc\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |\n"
        "|---|---|---|---|\n"
        f"| subtask-1 | U1 | S1 | compass/{slug}/subtask-1 |\n"
    )
    (docs_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    outside = tmp_path / "outside-secret.md"
    outside.write_text("TOP SECRET\n")
    (docs_dir / "notes.md").symlink_to(outside)

    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest(artifacts=[
        {"id": "ART-1", "kind": "distribution-map", "status": "approved",
         "path": f"docs/compass/{created}-{slug}/distribution-map.md"},
        {"id": "ART-2", "kind": "delivery-approach", "status": "approved",
         "path": f"docs/compass/{created}-{slug}/delivery-approach.md"},
        {"id": "ART-3", "kind": "notes", "status": "approved",
         "path": f"docs/compass/{created}-{slug}/notes.md"},
    ]))

    result = _run_multiagent(repo, slug)
    assert result.returncode == 0, result.stdout + result.stderr

    wt = tmp_path / "wt" / f"{slug}-subtask-1"
    seeded = wt / "docs" / "compass" / f"{created}-{slug}" / "notes.md"
    assert not seeded.exists(), "a symlinked source must not be copied in"


def test_dpr2_artifact_kind_that_is_not_lower_case_letters_and_hyphens_is_skipped(tmp_path):
    """A document kind from manifest.yml's artifacts: list that is not made
    of lower-case letters and hyphens is skipped, not resolved and not used
    to build a worktree path (finding 8 of the dispatch-protocol security
    review)."""
    repo = _init_repo(tmp_path)
    slug = "bad-kind-demo"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest(artifacts=[
        {"id": "ART-1", "kind": "../../../../outside", "status": "approved",
         "path": "../../../../outside.md"},
    ]))
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - bad-kind-demo\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |\n"
        "|---|---|---|---|\n"
        f"| subtask-1 | U1 | S1 | compass/{slug}/subtask-1 |\n"
    )
    (repo / "outside.md").write_text("# outside\n")

    result = _run_multiagent(repo, slug)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "not lower-case letters and hyphens" in (result.stdout + result.stderr)

    wt = tmp_path / "wt" / f"{slug}-subtask-1"
    assert not (wt / "outside.md").exists()


def test_dpr2_resolves_each_kind_once_not_once_per_worktree(tmp_path):
    """Every registered document kind is resolved once for the whole run,
    not once per worktree - two subtasks must not start the resolver twice
    for the same kind."""
    repo = _init_repo(tmp_path)
    slug = "resolve-once"
    docs_dir = repo / "docs" / "compass" / "2026-09-25-resolve-once"
    docs_dir.mkdir(parents=True)
    (docs_dir / "distribution-map.md").write_text(
        "# Distribution Map - resolve-once\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |\n"
        "|---|---|---|---|\n"
        f"| subtask-1 | U1 | S1 | compass/{slug}/subtask-1 |\n"
        f"| subtask-2 | U2 | S2 | compass/{slug}/subtask-2 |\n"
    )
    (docs_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (docs_dir / "threat-model.md").write_text("# Threat model\n")

    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest(artifacts=[
        {"id": "ART-1", "kind": "distribution-map", "status": "approved",
         "path": "docs/compass/2026-09-25-resolve-once/distribution-map.md"},
        {"id": "ART-2", "kind": "delivery-approach", "status": "approved",
         "path": "docs/compass/2026-09-25-resolve-once/delivery-approach.md"},
        {"id": "ART-3", "kind": "threat-model", "status": "approved",
         "path": "docs/compass/2026-09-25-resolve-once/threat-model.md"},
    ]))

    log_file = tmp_path / "resolver-calls.log"
    fakebin = _fake_python3(tmp_path, log_artifact_path_to=log_file)
    env = _env_with_fake_python3(fakebin)
    result = subprocess.run(
        ["bash", str(MULTIAGENT), slug],
        cwd=str(repo), capture_output=True, text=True, timeout=120, env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    calls = log_file.read_text().splitlines() if log_file.exists() else []
    assert calls.count("threat-model") == 1, calls


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


def test_dpr3_wave_cell_too_long_is_refused_naming_the_row(tmp_path):
    """A Wave cell of more than a few digits is refused, naming the row -
    not left to hang the wave-counting arithmetic or silently overflow it
    (finding 2 of the dispatch-protocol security review)."""
    repo = _init_repo(tmp_path)
    slug = "wave-too-long"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - wave-too-long\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name | Wave |\n"
        "|---|---|---|---|---|\n"
        f"| subtask-1 | U1 | S1 | compass/{slug}/subtask-1 | 1 |\n"
        f"| subtask-2 | U2 | S2 | compass/{slug}/subtask-2 | 20000 |\n"
    )

    result = _run_multiagent(repo, slug, "--dry-run")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "subtask-2" in (result.stdout + result.stderr)


def test_dpr3_distinct_waves_built_from_values_present_not_by_counting_up(tmp_path):
    """The waves a staged map has are read from the values themselves - via
    `sort -nu` - not by counting from 1 up to the highest value, which would
    take as long as the highest wave number names (finding 2)."""
    repo = _init_repo(tmp_path)
    slug = "wave-big-gap"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - wave-big-gap\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name | Wave |\n"
        "|---|---|---|---|---|\n"
        f"| subtask-1 | U1 | S1 | compass/{slug}/subtask-1 | 1 |\n"
        f"| subtask-2 | U2 | S2 | compass/{slug}/subtask-2 | 999 |\n"
    )

    result = subprocess.run(
        ["bash", str(MULTIAGENT), slug, "--wave", "999", "--dry-run"],
        cwd=str(repo), capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "subtask-2" in result.stdout


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


def test_dpr3_wave_with_no_matching_rows_is_refused_naming_the_maps_waves(tmp_path):
    """--wave 2 on a map whose waves are 1 and 3 must be refused, the same
    way on bash 3.2 and bash 5, naming the waves the map actually has."""
    repo = _init_repo(tmp_path)
    slug = "wave-gap"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - wave-gap\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name | Wave |\n"
        "|---|---|---|---|---|\n"
        f"| subtask-1 | U1 | S1 | compass/{slug}/subtask-1 | 1 |\n"
        f"| subtask-2 | U2 | S2 | compass/{slug}/subtask-2 | 3 |\n"
    )

    result = _run_multiagent(repo, slug, "--wave", "2", "--dry-run")
    assert result.returncode != 0, result.stdout + result.stderr
    out = result.stdout + result.stderr
    assert "unbound variable" not in out, "a crash is not a refusal"
    assert "has no rows" in out
    assert "1, 3" in out


def test_dpr3_wave_zero_is_refused(tmp_path):
    """--wave 0 is refused the same way on bash 3.2 and bash 5, with a clear
    message - not an unbound-variable crash on 3.2 or an empty launch plan
    on 5."""
    repo = _init_repo(tmp_path)
    slug = "wave-zero"
    _staged_task(repo, slug)

    result = _run_multiagent(repo, slug, "--wave", "0", "--dry-run")
    assert result.returncode != 0, result.stdout + result.stderr
    out = result.stdout + result.stderr
    assert "unbound variable" not in out, "a crash is not a refusal"
    assert "has no rows" in out


def test_dpr3_blank_or_non_numeric_wave_cell_is_refused_naming_the_row(tmp_path):
    """A row whose Wave cell is blank or not a number must refuse the whole
    map, naming the row - not silently drop it from every wave."""
    repo = _init_repo(tmp_path)
    slug = "wave-bad-cell"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - wave-bad-cell\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name | Wave |\n"
        "|---|---|---|---|---|\n"
        f"| subtask-1 | U1 | S1 | compass/{slug}/subtask-1 | 1 |\n"
        f"| subtask-2 | U2 | S2 | compass/{slug}/subtask-2 |  |\n"
        f"| subtask-3 | U3 | S3 | compass/{slug}/subtask-3 | x |\n"
        f"| subtask-4 | U4 | S4 | compass/{slug}/subtask-4 | 2 |\n"
    )

    result = _run_multiagent(repo, slug, "--wave", "1", "--dry-run")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "subtask-2" in (result.stdout + result.stderr)


def test_dpr3_branch_is_read_by_header_when_wave_is_not_the_last_column(tmp_path):
    """Q3 says Wave can sit anywhere in the table. The branch must be read
    by its own header, not by position 4."""
    repo = _init_repo(tmp_path)
    slug = "wave-mid"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - wave-mid\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Wave | Owns work unit(s) | Owns scenario ids | Branch name |\n"
        "|---|---|---|---|---|\n"
        f"| subtask-1 | 1 | U1 | S1 | compass/{slug}/subtask-1 |\n"
    )

    result = _run_multiagent(repo, slug, "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"compass/{slug}/subtask-1" in result.stdout
    assert "on branch S1" not in result.stdout


def test_dpr3_wave_flag_with_no_value_reports_why(tmp_path):
    """A trailing --wave with nothing after it must say why it refused, not
    exit silently."""
    repo = _init_repo(tmp_path)
    slug = "wave-trailing"
    _staged_task(repo, slug)

    result = _run_multiagent(repo, slug, "--dry-run", "--wave")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert out.strip() != ""
    assert "--wave" in out


def test_dpr3_wave_number_compares_numerically_not_as_a_string(tmp_path):
    """--wave 02 must match a row whose Wave cell is 2."""
    repo = _init_repo(tmp_path)
    slug = "wave-leading-zero"
    _staged_task(repo, slug)

    result = _run_multiagent(repo, slug, "--wave", "02", "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    for i in (4, 5):
        assert f"subtask-{i}" in result.stdout


def test_dpr3_wave_header_in_another_table_is_ignored(tmp_path):
    """A `Wave` header in some other table in the map must not turn on wave
    mode for a subtask table that has no Wave column of its own."""
    repo = _init_repo(tmp_path)
    slug = "wave-elsewhere"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - wave-elsewhere\n\n"
        "## 2. Independence analysis\n\n"
        "| Unit | Wave |\n"
        "|---|---|\n"
        "| U1 | 1 |\n\n"
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


def test_dpr3_wave_over_the_worktree_ceiling_is_refused_naming_the_wave(tmp_path):
    """The scenario's ceiling is the worktree cap (4, from _init_repo), not
    the map's highest wave. Wave 1 here has 5 rows - over the cap - while
    the map's highest wave (2) is well under it, so only the chosen wave's
    row count can be what refuses this. The message names the wave, not the
    map's total."""
    repo = _init_repo(tmp_path)
    slug = "wave-cap"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    waves = [1, 1, 1, 1, 1, 2]
    (task_dir / "distribution-map.md").write_text(_staged_map(slug, 6, waves))

    result = _run_multiagent(repo, slug, "--dry-run")
    assert result.returncode != 0, result.stdout + result.stderr
    out = (result.stdout + result.stderr).lower()
    assert "wave 1" in out
    assert "cap is 4" in out


def test_dpr3_subtask_id_in_an_earlier_table_does_not_steal_the_wave_header(tmp_path):
    """A staged map's independence table (section 2) may mention a subtask
    id in prose - "subtask-3 waits for subtask-1" - without being the
    subtask table. Only a row whose FIRST cell is a subtask id names the
    subtask table's own header, so the real Wave column downstream must
    still be found and still govern provisioning."""
    repo = _init_repo(tmp_path)
    slug = "wave-mentioned-earlier"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - wave-mentioned-earlier\n\n"
        "## 2. Independence analysis\n\n"
        "| Unit pair | Verdict |\n"
        "|---|---|\n"
        "| U1 and U3 | shared surface - subtask-3 waits for subtask-1 |\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name | Wave |\n"
        "|---|---|---|---|---|\n"
        f"| subtask-1 | U1 | S1 | compass/{slug}/subtask-1 | 1 |\n"
        f"| subtask-2 | U2 | S2 | compass/{slug}/subtask-2 | 1 |\n"
        f"| subtask-3 | U3 | S3 | compass/{slug}/subtask-3 | 2 |\n"
    )

    result = _run_multiagent(repo, slug, "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "subtask-1" in result.stdout
    assert "subtask-2" in result.stdout
    assert "subtask-3:" not in result.stdout, (
        "wave 1 only - subtask-3 is wave 2 and must not be planned yet")
    assert "next wave: 2" in result.stdout.lower()


def test_dpr3_wave_header_in_an_earlier_table_with_a_subtask_id_is_still_ignored(tmp_path):
    """The reverse of the case above: an earlier table has its own Wave
    column and a row that mentions a subtask id in prose. The real subtask
    table has no Wave column of its own, so waves stay off - the map is
    not refused for a Wave cell that belongs to the wrong table."""
    repo = _init_repo(tmp_path)
    slug = "wave-elsewhere-with-id"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - wave-elsewhere-with-id\n\n"
        "## 2. Independence analysis\n\n"
        "| Unit | Wave | Notes |\n"
        "|---|---|---|\n"
        "| U1 | 1 | feeds subtask-2 |\n\n"
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


def test_dpr3_next_wave_named_is_one_the_map_actually_has(tmp_path):
    """Waves 1 and 3, with a gap at 2: without --wave, wave 1 is
    provisioned and the next wave named must be 3, the wave the map has -
    not 2, which would then be refused for having no rows."""
    repo = _init_repo(tmp_path)
    slug = "wave-gap-next"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map - wave-gap-next\n\n"
        "## 3. Scenario-group -> subtask mapping\n\n"
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name | Wave |\n"
        "|---|---|---|---|---|\n"
        f"| subtask-1 | U1 | S1 | compass/{slug}/subtask-1 | 1 |\n"
        f"| subtask-2 | U2 | S2 | compass/{slug}/subtask-2 | 3 |\n"
    )

    result = _run_multiagent(repo, slug, "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    out = result.stdout.lower()
    assert "next wave: 3" in out
    assert "next wave: 2" not in out

    # The named wave is not itself refused when run.
    result2 = _run_multiagent(repo, slug, "--wave", "3", "--dry-run")
    assert result2.returncode == 0, result2.stdout + result2.stderr
    assert "subtask-2" in result2.stdout


# ---------------------------------------------------------------------------
# DPR-5 - the orchestrator message agrees with the protocol
# ---------------------------------------------------------------------------

def _plain_map(slug, n_subtasks):
    rows = [
        f"# Distribution Map - {slug}",
        "",
        "## 3. Scenario-group -> subtask mapping",
        "",
        "| Subtask | Owns work unit(s) | Owns scenario ids | Branch name |",
        "|---|---|---|---|",
    ]
    for i in range(1, n_subtasks + 1):
        rows.append(f"| subtask-{i} | U{i} | S{i} | compass/{slug}/subtask-{i} |")
    return "\n".join(rows) + "\n"


def _plain_task(repo, slug, n_subtasks):
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(_manifest())
    (task_dir / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    (task_dir / "distribution-map.md").write_text(_plain_map(slug, n_subtasks))
    return task_dir


def test_dpr5_two_to_three_subtasks_orchestrator_line_agrees_with_the_protocol(tmp_path):
    """docs/multiagent-protocol.md says the session that owns the issue
    orchestrates, whatever the number of subtasks, and that integration
    runs before /compass:verify. The old "no dedicated orchestrator - the
    lead builder integrates at ship" line contradicted both: it denied an
    orchestrator exists at all on a 2-3 subtask map, and it pointed
    integration at ship rather than before verify."""
    repo = _init_repo(tmp_path)
    slug = "pair-demo"
    _plain_task(repo, slug, 2)

    result = _run_multiagent(repo, slug, "--dry-run")
    out = result.stdout + result.stderr
    assert result.returncode == 0, out

    assert "no dedicated orchestrator" not in out.lower(), out
    assert "integrates at ship" not in out.lower(), out
    assert "the session that owns the issue orchestrates" in out, out
    assert "/compass:verify" in out, out


def test_dpr5_four_plus_subtasks_orchestrator_line_agrees_with_the_protocol(tmp_path):
    """The same protocol statement must hold on a 4+ subtask map: the old
    "owns integration at ship" wording pointed integration at ship, when
    ADR-026 moved it to before /compass:verify."""
    repo = _init_repo(tmp_path)
    slug = "multiagent-demo"
    _plain_task(repo, slug, 4)

    result = _run_multiagent(repo, slug, "--dry-run")
    out = result.stdout + result.stderr
    assert result.returncode == 0, out

    assert "owns integration at ship" not in out.lower(), out
    assert "the session that owns the issue orchestrates" in out, out
    assert "/compass:verify" in out, out
