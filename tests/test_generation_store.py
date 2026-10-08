"""The generation store and `effective_for` (ADR-036, ADR-043).

A generation is a stored, numbered copy of the configuration an issue runs
against. These tests build a scratch project, run the real functions or the
real CLI against the committed preset, and read the files back.

Scenario ids: `GS-1` to `GS-16` (issue `generation-store`). Each test name
starts with its scenario id.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

CLI = ROOT / "cli" / "compass"
SLUG = "feature"

MANIFEST = {
    "schema_version": "2.0", "issue": SLUG, "created": "2026-10-07", "status": "active",
    "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                   "size": "medium", "goal": "delivery", "role": "engineer",
                   "labels": []},
    "evidence": [],
}


def _env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1",
            "COLUMNS": "100", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def _run(cwd, *argv):
    r = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=_env(cwd),
                       capture_output=True, text=True, timeout=180)
    return r.returncode, r.stdout, r.stderr


def _project(tmp_path, manifest=None, compass_yml=None, slug=SLUG):
    """A scratch project with one issue, and the issue's directory."""
    (tmp_path / ".compass").mkdir(exist_ok=True)
    task_dir = tmp_path / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    body = dict(MANIFEST, issue=slug) if manifest is None else manifest
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")
    if compass_yml is not None:
        (tmp_path / "compass.yml").write_text(
            compass_yml if isinstance(compass_yml, str) else yaml.safe_dump(compass_yml),
            encoding="utf-8")
    return tmp_path, task_dir


def _manifest(task_dir):
    return yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))


def _write_manifest(task_dir, **changes):
    body = _manifest(task_dir)
    body.update(changes)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")


# --- GS-1: effective_for with no generation, generation 0, and no issue ----------------

def test_gs_1_no_generation_key_gives_a_live_view_and_writes_nothing(tmp_path, monkeypatch):
    from compass_pkg import effective
    root, task_dir = _project(tmp_path)
    monkeypatch.chdir(root)
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    view = effective.effective_for(str(task_dir))
    assert view is not None
    assert view.source == "live"
    assert view.generation is None
    assert "approaches" in view.config
    after = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    assert after == before


def test_gs_1_generation_zero_refuses_and_names_the_fix(tmp_path, monkeypatch):
    from compass_pkg import effective
    from compass_pkg.core import CompassError
    root, task_dir = _project(tmp_path)
    _write_manifest(task_dir, generation=0)
    monkeypatch.chdir(root)
    with pytest.raises(CompassError) as caught:
        effective.effective_for(str(task_dir))
    assert "compass approach evaluate --write" in str(caught.value)
    assert "no stored configuration" in str(caught.value)


def test_gs_1_no_issue_resolves_the_project_layers_live(tmp_path, monkeypatch):
    from compass_pkg import effective
    root, _ = _project(tmp_path, compass_yml={"schema": 1})
    monkeypatch.chdir(root)
    view = effective.effective_for(None)
    assert view is not None
    assert (view.source, view.generation, view.issue) == ("live", None, None)
    assert "stages" in view.config


# --- helpers for the store ---------------------------------------------------------------

OUTCOME = {
    "delivery_approach": "regular",
    "stages": {"assess": "thorough", "implement": "thorough"},
    "gates": [{"id": "verify.correctness", "status": "pending", "evidence": []}],
    "checkpoints": [],
    "policy_rules_fired": [],
    "subtask_ceiling": 1,
    "artifacts": [],
}
FILE_NAMES = ("resolved.yml", "provenance.yml", "versions.yml", "records.yml")


def _new_check(**over):
    body = {"statement": "A check.", "kind": "deterministic", "impl": "suite-passed",
            "severity": "advisory", "on_skipped": "fail"}
    body.update(over)
    return body


def _commit(root, task_dir, invalidated=None, **changes):
    """Resolve the chain now and commit it, as `approach evaluate --write` does."""
    from compass_pkg import effective, generation
    manifest = _manifest(task_dir)
    manifest.update(OUTCOME)
    manifest.update(changes)
    resolution = effective.resolve_live(str(root), manifest, task_dir.name, str(task_dir),
                                        validate=True)
    return generation.commit(str(task_dir), resolution, manifest, invalidated=invalidated)


def _gen(task_dir, n):
    return task_dir / "generations" / str(n)


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture
def project(tmp_path, monkeypatch):
    root, task_dir = _project(tmp_path)
    monkeypatch.chdir(root)
    return root, task_dir


# --- GS-2: the contents of a generation --------------------------------------------------

def test_gs_2_a_commit_writes_the_four_files_and_the_marker(project):
    root, task_dir = project
    result = _commit(root, task_dir)
    assert (result.number, result.committed) == (1, True)
    folder = _gen(task_dir, 1)
    assert sorted(p.name for p in folder.iterdir()) == sorted((*FILE_NAMES, "complete"))
    for name in (*FILE_NAMES, "complete"):
        assert _load(folder / name)["schema"] == 1, name


def test_gs_2_resolved_holds_the_catalogues_and_the_issue_inputs(project):
    root, task_dir = project
    _commit(root, task_dir)
    resolved = _load(_gen(task_dir, 1) / "resolved.yml")
    assert (resolved["issue"], resolved["generation"]) == (SLUG, 1)
    assert resolved["autonomy"] == "balanced"
    assert resolved["approach"] is None
    assert resolved["conformance"] == {"status": "conformant", "unlocked": []}
    assert set(resolved["capabilities"]) >= {"entry-exit-evaluation", "artifact-freshness"}
    for name in ("dimensions", "stages", "approaches", "rules", "checks", "gates",
                 "artifacts", "vocabulary", "evidence_types"):
        assert resolved[name], name


def test_gs_2_versions_record_the_resolver_the_parent_and_the_implementations(project):
    from compass_pkg import check_registry
    from compass_pkg.core import COMPASS_VERSION
    root, task_dir = project
    _commit(root, task_dir)
    versions = _load(_gen(task_dir, 1) / "versions.yml")
    assert versions["resolver"] == "1.0.0"
    assert versions["cli"] == COMPASS_VERSION
    parent = versions["parents"][0]
    assert (parent["ref"], parent["source"]) == ("compass:default@6", "shipped")
    assert parent["version"].startswith("6.") and parent["digest"].startswith("sha256:")
    assert versions["project"] is None and versions["issue_overlay_digest"] is None
    used = versions["implementations"]
    assert used["suite-passed"] == check_registry.installed_version("suite-passed")
    assert set(used) <= set(check_registry.REGISTRY)


def test_gs_2_the_marker_holds_the_digest_of_each_file(project):
    from compass_pkg.atomic_io import digest
    root, task_dir = project
    _commit(root, task_dir)
    marker = _load(_gen(task_dir, 1) / "complete")
    assert set(marker["files"]) == set(FILE_NAMES)
    for name, held in marker["files"].items():
        assert held == digest(_load(_gen(task_dir, 1) / name)), name
    assert marker["written"]


def test_gs_2_provenance_names_the_layer_and_operation_behind_a_field(tmp_path, monkeypatch):
    root, task_dir = _project(tmp_path, compass_yml={
        "schema": 1, "checks": {"extra": _new_check()}})
    monkeypatch.chdir(root)
    _commit(root, task_dir)
    fields = _load(_gen(task_dir, 1) / "provenance.yml")["fields"]
    assert fields["checks.extra"]["steps"] == [{"layer": "project", "op": "add"}]
    assert fields["checks.suite-passed"]["steps"][0] == {"layer": "default", "op": "add"}
    versions = _load(_gen(task_dir, 1) / "versions.yml")
    assert versions["project"]["path"] == "compass.yml"
    assert versions["project"]["digest"].startswith("sha256:")


def test_gs_2_an_issue_overlay_is_recorded_by_digest(tmp_path, monkeypatch):
    manifest = dict(MANIFEST, config={"checks": {"extra": _new_check()}})
    root, task_dir = _project(tmp_path, manifest=manifest)
    monkeypatch.chdir(root)
    _commit(root, task_dir)
    versions = _load(_gen(task_dir, 1) / "versions.yml")
    assert versions["issue_overlay_digest"].startswith("sha256:")
    fields = _load(_gen(task_dir, 1) / "provenance.yml")["fields"]
    assert fields["checks.extra"]["steps"] == [{"layer": "issue", "op": "add"}]


def test_gs_2_records_start_empty_and_carry_an_invalidation(project):
    root, task_dir = project
    _commit(root, task_dir)
    assert _load(_gen(task_dir, 1) / "records.yml")["records"] == []
    _commit(root, task_dir, invalidated={"result:suite-passed": "implementation changed"},
            delivery_approach="full")
    records = _load(_gen(task_dir, 2) / "records.yml")["records"]
    assert records == [{"id": "result:suite-passed", "kind": "check-result",
                        "status": "invalidated", "reason": "implementation changed"}]
    _commit(root, task_dir, delivery_approach="regular")
    assert _load(_gen(task_dir, 3) / "records.yml")["records"] == records


# --- GS-3: the order of a commit and the lock --------------------------------------------

def _spy_steps(monkeypatch, task_dir, boom_at=None):
    from compass_pkg import generation
    seen = []

    def hook(step):
        seen.append((step, (_manifest(task_dir)).get("generation"),
                     sorted(p.name for p in _gen(task_dir, 1).glob("*"))))
        if step == boom_at:
            raise RuntimeError("interrupted")
    monkeypatch.setattr(generation, "_after_step", hook)
    return seen


def test_gs_3_files_then_marker_then_manifest(project, monkeypatch):
    root, task_dir = project
    seen = _spy_steps(monkeypatch, task_dir)
    _commit(root, task_dir)
    assert [s for s, _, _ in seen] == ["resolved", "provenance", "versions", "records",
                                       "marker", "manifest"]
    assert [g for _, g, _ in seen] == [None] * 5 + [1]
    names = [n for _, _, n in seen]
    assert names[0] == ["resolved.yml"]
    assert "complete" not in names[3] and "complete" in names[4]


def test_gs_3_the_manifest_keeps_its_other_keys_and_gains_the_generation(project):
    root, task_dir = project
    _commit(root, task_dir)
    manifest = _manifest(task_dir)
    assert manifest["generation"] == 1
    assert manifest["delivery_approach"] == "regular"
    assert manifest["assessment"]["risk"] == "contained"


def test_gs_3_the_commit_holds_an_exclusive_lock_on_the_issue(project, monkeypatch):
    import fcntl
    from compass_pkg import generation
    root, task_dir = project
    blocked = []

    def hook(step):
        with open(task_dir / ".generation.lock", "a") as other:
            try:
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(other, fcntl.LOCK_UN)
                blocked.append(False)
            except BlockingIOError:
                blocked.append(True)
    monkeypatch.setattr(generation, "_after_step", hook)
    _commit(root, task_dir)
    assert blocked == [True] * 6
    with open(task_dir / ".generation.lock", "a") as free:
        fcntl.flock(free, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_gs_3_a_manifest_changed_since_it_was_read_is_refused(project):
    from compass_pkg import effective, generation
    from compass_pkg.core import CompassError
    root, task_dir = project
    manifest = _manifest(task_dir)
    manifest.update(OUTCOME)
    resolution = effective.resolve_live(str(root), manifest, SLUG, str(task_dir))
    _write_manifest(task_dir, generation=3)
    with pytest.raises(CompassError) as caught:
        generation.commit(str(task_dir), resolution, manifest)
    assert "changed" in str(caught.value)
    assert _manifest(task_dir)["generation"] == 3


# --- GS-4: an interrupted commit ---------------------------------------------------------

@pytest.mark.parametrize("step,state,named", [
    ("resolved", "incomplete", None), ("provenance", "incomplete", None),
    ("versions", "incomplete", None), ("records", "incomplete", None),
    ("marker", "complete-unreferenced", None), ("manifest", "current", 1)])
def test_gs_4_an_interruption_leaves_a_named_state(project, monkeypatch, step, state, named):
    from compass_pkg import generation
    root, task_dir = project
    _spy_steps(monkeypatch, task_dir, boom_at=step)
    with pytest.raises(RuntimeError):
        _commit(root, task_dir)
    assert _manifest(task_dir).get("generation") == named
    found = {g.number: g.state for g in generation.states(str(task_dir))}
    assert found == {1: state}


def test_gs_4_the_cli_never_adopts_a_leftover_on_its_own(project, monkeypatch):
    from compass_pkg import effective
    from compass_pkg.core import CompassError
    root, task_dir = project
    _write_manifest(task_dir, generation=0)
    _spy_steps(monkeypatch, task_dir, boom_at="marker")
    with pytest.raises(RuntimeError):
        _commit(root, task_dir)
    with pytest.raises(CompassError):
        effective.effective_for(str(task_dir))
    assert _manifest(task_dir)["generation"] == 0


# --- GS-5: nothing changed ---------------------------------------------------------------

def test_gs_5_an_equal_commit_commits_nothing_and_says_no_change(project):
    root, task_dir = project
    _commit(root, task_dir)
    again = _commit(root, task_dir)
    assert (again.number, again.committed) == (1, False)
    assert "no change" in again.message
    assert not _gen(task_dir, 2).exists()
    assert _manifest(task_dir)["generation"] == 1


def test_gs_5_a_different_outcome_commits_the_next_generation(project):
    root, task_dir = project
    _commit(root, task_dir)
    changed = _commit(root, task_dir, delivery_approach="full")
    assert (changed.number, changed.committed) == (2, True)
    assert _manifest(task_dir)["generation"] == 2
    assert _gen(task_dir, 1).is_dir()


def test_gs_5_a_different_project_layer_commits_the_next_generation(project):
    root, task_dir = project
    _commit(root, task_dir)
    (root / "compass.yml").write_text(
        yaml.safe_dump({"schema": 1, "checks": {"extra": _new_check()}}), encoding="utf-8")
    assert _commit(root, task_dir).number == 2
    assert _commit(root, task_dir).committed is False


def test_gs_5_a_different_issue_overlay_commits_the_next_generation(project):
    root, task_dir = project
    _commit(root, task_dir)
    _write_manifest(task_dir, config={"checks": {"extra": _new_check()}})
    assert _commit(root, task_dir).number == 2


def test_gs_5_an_overlay_that_restates_a_default_is_still_a_different_overlay(project):
    root, task_dir = project
    _commit(root, task_dir)
    _write_manifest(task_dir, config={"autonomy": "balanced"})
    again = _commit(root, task_dir)
    assert (again.number, again.committed) == (2, True)
    assert _load(_gen(task_dir, 2) / "resolved.yml")["autonomy"] == "balanced"


def test_gs_5_a_commit_with_no_change_does_not_run_the_lint(project, monkeypatch):
    """The lint is slow on a project layer, and a stored generation was linted
    when it was committed, so the lint runs only when a write follows."""
    from compass_pkg import effective, policy_lint
    root, task_dir = project
    manifest = _manifest(task_dir)
    manifest.update(OUTCOME)
    assert effective.commit_generation(str(task_dir), manifest).committed
    calls = []
    real = policy_lint.lint_loaded
    monkeypatch.setattr(policy_lint, "lint_loaded",
                        lambda *a, **k: calls.append(1) or real(*a, **k))
    again = effective.commit_generation(str(task_dir), _manifest(task_dir))
    assert (again.number, again.committed) == (1, False)
    assert calls == []
    manifest = _manifest(task_dir)
    manifest["delivery_approach"] = "full"
    assert effective.commit_generation(str(task_dir), manifest).committed
    assert calls == [1]


# --- GS-6: the target folder -------------------------------------------------------------

def test_gs_6_a_complete_unreferenced_target_is_refused(project, monkeypatch):
    from compass_pkg import generation
    from compass_pkg.core import CompassError
    root, task_dir = project
    _write_manifest(task_dir, generation=0)
    monkeypatch.setattr(generation, "_after_step",
                        lambda step: (_ for _ in ()).throw(RuntimeError("x"))
                        if step == "marker" else None)
    with pytest.raises(RuntimeError):
        _commit(root, task_dir)
    monkeypatch.undo()
    monkeypatch.chdir(root)
    with pytest.raises(CompassError) as caught:
        _commit(root, task_dir)
    assert "complete" in str(caught.value) and "delete" not in str(caught.value).lower()
    assert (_gen(task_dir, 1) / "complete").is_file()


def test_gs_6_an_incomplete_target_is_overwritten(project, monkeypatch):
    from compass_pkg import generation
    root, task_dir = project
    folder = _gen(task_dir, 1)
    folder.mkdir(parents=True)
    (folder / "resolved.yml").write_text("garbage: true\n", encoding="utf-8")
    (folder / "stray.yml").write_text("x: 1\n", encoding="utf-8")
    result = _commit(root, task_dir)
    assert result.committed
    assert not (folder / "stray.yml").exists()
    assert _load(folder / "resolved.yml")["schema"] == 1
    assert {g.number: g.state for g in generation.states(str(task_dir))} == {1: "current"}


def test_gs_6_a_proposal_is_kept(project):
    root, task_dir = project
    _commit(root, task_dir)
    folder = _gen(task_dir, 2)
    folder.mkdir()
    (folder / "proposed.yml").write_text("schema: 1\nbase_generation: 1\noverlay: {}\n",
                                         encoding="utf-8")
    assert _commit(root, task_dir, delivery_approach="full").number == 2
    assert _load(folder / "proposed.yml")["base_generation"] == 1
    assert (folder / "complete").is_file()


# --- GS-7: atomic writes -----------------------------------------------------------------

def test_gs_7_every_file_goes_through_atomic_write_text(project, monkeypatch):
    from compass_pkg import generation
    from compass_pkg.atomic_io import atomic_write_text
    root, task_dir = project
    written = []

    def spy(path, text, *args, **kwargs):
        written.append(Path(path).name)
        return atomic_write_text(path, text, *args, **kwargs)
    monkeypatch.setattr(generation, "atomic_write_text", spy)
    _commit(root, task_dir)
    assert written == [*FILE_NAMES, "complete", "manifest.yml"]


def test_gs_7_a_failed_write_leaves_no_temporary_file(project, monkeypatch):
    root, task_dir = project
    real = os.replace

    def refuse(src, dst, *args, **kwargs):
        if str(dst).endswith("provenance.yml"):
            raise OSError("disk full")
        return real(src, dst, *args, **kwargs)
    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError):
        _commit(root, task_dir)
    monkeypatch.undo()
    leftovers = [p.name for p in task_dir.rglob(".*") if p.is_file() and p.name != ".generation.lock"]
    assert leftovers == []
    assert _manifest(task_dir).get("generation") is None
    assert not (_gen(task_dir, 1) / "provenance.yml").exists()


# --- GS-8: a generation is read, and the project file is not ------------------------------

def test_gs_8_effective_for_returns_the_stored_generation_offline(tmp_path, monkeypatch):
    from compass_pkg import effective
    root, task_dir = _project(tmp_path, compass_yml={
        "schema": 1, "checks": {"extra": _new_check()}})
    monkeypatch.chdir(root)
    _commit(root, task_dir)
    (root / "compass.yml").unlink()
    view = effective.effective_for(str(task_dir))
    assert (view.source, view.generation, view.issue) == ("generation", 1, SLUG)
    assert "extra" in view.config["checks"]
    assert view.versions["resolver"] == "1.0.0"
    assert view.autonomy == "balanced"


def test_gs_8_a_later_project_change_does_not_reach_the_issue(tmp_path, monkeypatch):
    from compass_pkg import effective
    root, task_dir = _project(tmp_path, compass_yml={"schema": 1})
    monkeypatch.chdir(root)
    _commit(root, task_dir)
    (root / "compass.yml").write_text(
        yaml.safe_dump({"schema": 1, "checks": {"later": _new_check()}}), encoding="utf-8")
    assert "later" not in effective.effective_for(str(task_dir)).config["checks"]
    assert "later" in effective.effective_for(None).config["checks"]


@pytest.mark.parametrize("damage", ["no-marker", "edited-file", "no-folder"])
def test_gs_8_a_broken_generation_is_refused(project, damage):
    from compass_pkg import effective
    from compass_pkg.core import CompassError
    root, task_dir = project
    _commit(root, task_dir)
    folder = _gen(task_dir, 1)
    if damage == "no-marker":
        (folder / "complete").unlink()
    elif damage == "edited-file":
        text = (folder / "resolved.yml").read_text(encoding="utf-8")
        (folder / "resolved.yml").write_text(text.replace("balanced", "autonomous"),
                                             encoding="utf-8")
    else:
        import shutil
        shutil.rmtree(folder)
    with pytest.raises(CompassError) as caught:
        effective.effective_for(str(task_dir))
    assert "broken" in str(caught.value)


# --- GS-9: the states of a generation folder ----------------------------------------------

def test_gs_9_every_state_is_recognised(project):
    import shutil
    from compass_pkg import generation
    root, task_dir = project
    _commit(root, task_dir)
    _commit(root, task_dir, delivery_approach="full")
    shutil.copytree(_gen(task_dir, 2), _gen(task_dir, 3))          # complete, above current
    _gen(task_dir, 4).mkdir()
    (_gen(task_dir, 4) / "proposed.yml").write_text("schema: 1\n", encoding="utf-8")
    _gen(task_dir, 5).mkdir()
    (_gen(task_dir, 5) / "resolved.yml").write_text("schema: 1\n", encoding="utf-8")
    found = {g.number: g.state for g in generation.states(str(task_dir))}
    assert found == {1: "superseded", 2: "current", 3: "complete-unreferenced",
                     4: "proposal", 5: "incomplete"}


def test_gs_9_a_marker_that_does_not_match_above_current_is_incomplete(project):
    import shutil
    from compass_pkg import generation
    root, task_dir = project
    _commit(root, task_dir)
    shutil.copytree(_gen(task_dir, 1), _gen(task_dir, 2))
    text = (_gen(task_dir, 2) / "resolved.yml").read_text(encoding="utf-8")
    (_gen(task_dir, 2) / "resolved.yml").write_text(text + "extra: 1\n", encoding="utf-8")
    found = {g.number: g.state for g in generation.states(str(task_dir))}
    assert found == {1: "current", 2: "incomplete"}


def test_gs_9_the_generation_the_manifest_names_is_broken_without_its_marker_or_folder(project):
    import shutil
    from compass_pkg import generation
    root, task_dir = project
    _commit(root, task_dir)
    (_gen(task_dir, 1) / "complete").unlink()
    found = generation.states(str(task_dir))
    assert [(g.number, g.state) for g in found] == [(1, "broken")]
    shutil.rmtree(_gen(task_dir, 1))
    assert [(g.number, g.state) for g in generation.states(str(task_dir))] == [(1, "broken")]


def test_gs_9_an_issue_with_no_generation_has_no_states(project):
    from compass_pkg import generation
    _, task_dir = project
    assert generation.states(str(task_dir)) == []


# --- GS-10: the manifest schema and the template ------------------------------------------

def _lint(tmp_path, **manifest_changes):
    root, task_dir = _project(tmp_path)
    _write_manifest(task_dir, **manifest_changes)
    return _run(root, "issue", "lint", "--issue", SLUG)


@pytest.mark.parametrize("changes", [
    {}, {"generation": 0}, {"generation": 3},
    {"config": {"checks": {"extra": _new_check()}}}, {"generation": 1, "config": {}}])
def test_gs_10_generation_and_config_are_accepted(tmp_path, changes):
    code, out, err = _lint(tmp_path, **changes)
    assert code == 0, out + err


@pytest.mark.parametrize("changes", [
    {"generation": -1}, {"generation": "one"}, {"generation": 1.5},
    {"generation": True}, {"config": "text"}])
def test_gs_10_a_bad_generation_or_config_is_refused(tmp_path, changes):
    code, out, err = _lint(tmp_path, **changes)
    assert code != 0, out + err
    assert ("generation" in out + err) or ("config" in out + err)


def test_gs_10_the_template_ships_generation_zero():
    text = (ROOT / "templates" / "manifest.yml").read_text(encoding="utf-8")
    lines = [l for l in text.splitlines() if l.startswith("generation:")]
    assert len(lines) == 1 and lines[0].split("#")[0].split(":")[1].strip() == "0"


def test_gs_10_the_reference_manifest_documents_both_keys():
    text = (ROOT / "schemas" / "manifest.reference.yml").read_text(encoding="utf-8")
    assert "generation:" in text and "config:" in text


# --- GS-11: approach evaluate --write commits ---------------------------------------------

def _evaluate_write(root, *extra):
    return _run(root, "approach", "evaluate", "--issue", SLUG, "--write", *extra)


def test_gs_11_write_commits_generation_one_for_an_issue_with_none(tmp_path):
    root, task_dir = _project(tmp_path)
    code, out, err = _evaluate_write(root)
    assert code == 0, out + err
    assert "committed generation 1" in out
    assert _manifest(task_dir)["generation"] == 1
    assert (_gen(task_dir, 1) / "complete").is_file()
    assert _manifest(task_dir)["delivery_approach"] == "regular"


def test_gs_11_write_commits_generation_one_for_generation_zero(tmp_path):
    root, task_dir = _project(tmp_path)
    _write_manifest(task_dir, generation=0)
    code, out, err = _evaluate_write(root)
    assert code == 0, out + err
    assert _manifest(task_dir)["generation"] == 1


def test_gs_11_a_repeat_says_no_change_and_a_new_assessment_commits_two(tmp_path):
    root, task_dir = _project(tmp_path)
    _evaluate_write(root)
    code, out, err = _evaluate_write(root)
    assert code == 0, out + err
    assert "no change" in out and "generation 1" in out
    assert _manifest(task_dir)["generation"] == 1 and not _gen(task_dir, 2).exists()
    body = _manifest(task_dir)
    body["assessment"]["size"] = "large"
    _write_manifest(task_dir, assessment=body["assessment"])
    code, out, err = _evaluate_write(root, "--reason", "larger than thought")
    assert code == 0, out + err
    assert "committed generation 2" in out
    assert _manifest(task_dir)["generation"] == 2


def test_gs_11_a_configuration_that_does_not_resolve_refuses_before_writing(tmp_path):
    root, task_dir = _project(tmp_path, compass_yml="schema: 1\nstages: oops\n")
    before = (task_dir / "manifest.yml").read_bytes()
    code, out, err = _evaluate_write(root)
    assert code == 2, out + err
    assert (task_dir / "manifest.yml").read_bytes() == before
    assert not (task_dir / "generations").exists()


def test_gs_11_a_chain_the_lint_refuses_is_not_stored(tmp_path):
    """A project layer that loosens a locked check without a waiver resolves,
    so only the lint stands between it and a stored generation."""
    root, task_dir = _project(tmp_path, compass_yml={
        "schema": 1, "checks": {"suite-passed": {"set": {"severity": "advisory"}}}})
    before = (task_dir / "manifest.yml").read_bytes()
    code, out, err = _evaluate_write(root)
    assert code == 2, out + err
    assert "nothing was written" in out + err
    assert (task_dir / "manifest.yml").read_bytes() == before
    assert not (task_dir / "generations").exists()


def test_gs_11_without_write_nothing_is_committed(tmp_path):
    root, task_dir = _project(tmp_path)
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG)
    assert code == 0, out + err
    assert not (task_dir / "generations").exists()
    assert "generation" not in _manifest(task_dir)


def test_gs_11_a_project_with_copied_governance_is_stored_against_its_copies(tmp_path):
    import shutil
    root, task_dir = _project(tmp_path)
    (root / "governance").mkdir()
    for name in ("routing-policy.yml", "guardrails.yml"):
        shutil.copyfile(ROOT / "governance" / name, root / "governance" / name)
    code, out, err = _evaluate_write(root)
    assert code == 0, out + err
    versions = _load(_gen(task_dir, 1) / "versions.yml")
    assert (versions["parents"][0]["ref"], versions["parents"][0]["source"]) == (
        "legacy", "legacy")


def test_gs_11_the_compat_regular_issue_state_gains_a_generation(tmp_path):
    root, task_dir = _project(tmp_path, compass_yml="schema: 1\n")
    code, out, err = _evaluate_write(root)
    assert code == 0, out + err
    assert _load(_gen(task_dir, 1) / "versions.yml")["project"]["path"] == "compass.yml"


# --- GS-12: results.yml and the broken refusal --------------------------------------------

def _committed_project(tmp_path):
    root, task_dir = _project(tmp_path)
    code, out, err = _evaluate_write(root)
    assert code == 0, out + err
    return root, task_dir


def test_gs_12_check_writes_the_latest_verdict_per_check(tmp_path):
    root, task_dir = _committed_project(tmp_path)
    _run(root, "check", "--issue", SLUG)
    results = _load(task_dir / "generations" / "1" / "results.yml")
    assert results["schema"] == 1 and results["generation"] == 1
    runs = results["runs"]
    assert runs
    for name, run in runs.items():
        assert run["verdict"] in ("pass", "fail", "nothing-to-check"), name
        assert run["at"] and run["status"] == "valid", name
    named = runs["scenarios-have-tests"]
    assert named["impl"] == {"id": "scenarios-have-tests", "version": "1.0.0"}
    assert named["definition_digest"].startswith("sha256:")
    assert runs["assessment-keys"]["impl"] is None


def test_gs_12_results_are_not_covered_by_the_marker(tmp_path):
    from compass_pkg import generation
    root, task_dir = _committed_project(tmp_path)
    _run(root, "check", "--issue", SLUG)
    marker = _load(_gen(task_dir, 1) / "complete")
    assert "results.yml" not in marker["files"]
    assert [(g.number, g.state) for g in generation.states(str(task_dir))] == [(1, "current")]


def test_gs_12_a_second_run_replaces_the_first(tmp_path):
    root, task_dir = _committed_project(tmp_path)
    _run(root, "check", "--issue", SLUG)
    first = _load(_gen(task_dir, 1) / "results.yml")
    _run(root, "check", "--issue", SLUG)
    second = _load(_gen(task_dir, 1) / "results.yml")
    assert set(second["runs"]) == set(first["runs"])
    assert second["runs"]["assessment-keys"]["at"] >= first["runs"]["assessment-keys"]["at"]


def test_gs_12_a_broken_generation_makes_check_refuse(tmp_path):
    root, task_dir = _committed_project(tmp_path)
    (_gen(task_dir, 1) / "complete").unlink()
    code, out, err = _run(root, "check", "--issue", SLUG)
    assert code == 2, out + err
    assert "broken" in out + err
    # It refuses before running any check: no verdict is printed and no failure is
    # counted as an interruption.
    assert "check(s)" not in out
    assert not (root / ".compass" / "interruptions.log").exists()


def test_gs_12_an_issue_with_no_generation_gets_no_results_file(tmp_path):
    root, task_dir = _project(tmp_path)
    _run(root, "check", "--issue", SLUG)
    assert not list(root.rglob("results.yml"))


# --- GS-13: compass ci --------------------------------------------------------------------

def test_gs_13_ci_reports_the_state_of_an_issue_with_a_generation(tmp_path):
    root, task_dir = _committed_project(tmp_path)
    code, out, err = _run(root, "ci")
    assert "generation 1 (current)" in out, out + err


def test_gs_13_ci_reports_generation_zero_without_failing_on_it(tmp_path):
    root, task_dir = _project(tmp_path)
    _write_manifest(task_dir, generation=0)
    code, out, err = _run(root, "ci")
    assert "generation 0" in out and "compass approach evaluate --write" in out


def test_gs_13_ci_reports_a_leftover_and_fails_on_a_broken_generation(tmp_path):
    import shutil
    root, task_dir = _committed_project(tmp_path)
    shutil.copytree(_gen(task_dir, 1), _gen(task_dir, 2))
    code, out, err = _run(root, "ci")
    assert "generation 2 (complete-unreferenced)" in out, out + err
    (_gen(task_dir, 1) / "complete").unlink()
    code, out, err = _run(root, "ci")
    assert code == 1, out + err
    assert "generation 1 (broken)" in out


def test_gs_13_ci_prints_nothing_new_for_an_issue_with_no_generation(tmp_path):
    root, task_dir = _project(tmp_path)
    code, out, err = _run(root, "ci")
    assert "generation" not in out.lower(), out


# --- GS-14: import direction --------------------------------------------------------------

import ast  # noqa: E402

PACKAGE = ROOT / "cli" / "compass_pkg"
READERS = ("checks", "check_cmd", "routing", "receipt", "manifest", "calibration", "flow",
           "quick_fix_cmd", "loop_ceilings", "lessons", "review_rules", "approach_diagram",
           "subtasks", "run_cmd", "multiagent_check")
RESOLVER_MODULES = {"merge", "obligations", "classify", "waivers", "policy_lint",
                    "generation"}


def _imported(path, whole=None):
    """The `compass_pkg` modules a file imports, at any depth."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "compass_pkg":
                names |= {a.name for a in node.names}
            elif node.module.startswith("compass_pkg."):
                names.add(node.module.split(".")[1])
        elif isinstance(node, ast.Import):
            names |= {a.name.split(".")[1] for a in node.names if a.name.startswith("compass_pkg.")}
    return names


def test_gs_14_only_effective_imports_generation():
    importers = sorted(p.stem for p in PACKAGE.glob("*.py")
                       if "generation" in _imported(p) and p.stem != "generation")
    assert importers == ["effective"]


def test_gs_14_the_reader_modules_import_no_resolver_module():
    found = {m: sorted(_imported(PACKAGE / f"{m}.py") & RESOLVER_MODULES) for m in READERS}
    assert {m: v for m, v in found.items() if v} == {}


def test_gs_14_the_guard_can_fail(tmp_path):
    planted = tmp_path / "reader.py"
    planted.write_text("def f():\n    from compass_pkg import generation\n", encoding="utf-8")
    assert "generation" in _imported(planted)
    planted.write_text("from compass_pkg.merge import apply\n", encoding="utf-8")
    assert _imported(planted) & RESOLVER_MODULES == {"merge"}


# --- GS-15: an issue with no generation ----------------------------------------------------

def test_gs_15_check_and_evaluate_create_no_generation_files(tmp_path):
    root, task_dir = _project(tmp_path)
    _run(root, "check", "--issue", SLUG)
    _run(root, "approach", "evaluate", "--issue", SLUG)
    _run(root, "policy", "show", "--issue", SLUG)
    assert not list(root.rglob("generations"))
    assert not list(root.rglob("results.yml"))
    assert "generation" not in _manifest(task_dir)


def test_gs_15_effective_for_reads_the_same_live_configuration_as_lint_resolves(tmp_path, monkeypatch):
    from compass_pkg import effective, policy_lint
    root, task_dir = _project(tmp_path, compass_yml={"schema": 1, "checks": {"extra": _new_check()}})
    monkeypatch.chdir(root)
    view = effective.effective_for(str(task_dir))
    loaded = policy_lint.load_layers(str(root), manifest=_manifest(task_dir))
    eff = policy_lint.resolve_effective(loaded.parent, loaded.project, loaded.issue,
                                        meta=loaded.meta, slug=SLUG)
    paths = {r.path for r in eff.rows
             if r.path.startswith("checks.") and not r.path.endswith(".locked")}
    held = {f"checks.{c}.{f}" for c, body in view.config["checks"].items() for f in body}
    assert paths <= held


# --- GS-16: the bench, headers, owning doc and line cap -------------------------------------

def test_gs_16_the_bench_script_times_evaluate_with_and_without_write(tmp_path):
    script = ROOT / "scripts" / "bench-evaluate.py"
    r = subprocess.run([sys.executable, str(script), "--runs", "1"], capture_output=True,
                       text=True, env=_env(tmp_path), timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    for label in ("evaluate", "evaluate --write (first commit)",
                  "evaluate --write (no change)"):
        assert label in r.stdout, r.stdout


def test_gs_16_new_modules_carry_a_dependency_header_and_an_owning_doc_row():
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    for name in ("generation", "effective"):
        head = (PACKAGE / f"{name}.py").read_text(encoding="utf-8").split('"""')[2][:600]
        assert "# DEPENDENCY:" in head, name
        assert f"{name}.py" in readme, name
    assert (ROOT / "docs" / "generation-store.md").is_file()


def test_gs_16_core_stays_within_its_line_cap():
    assert len((PACKAGE / "core.py").read_text(encoding="utf-8").splitlines()) <= 1200


# --- GS-17: links, landed issues, rejected files and message wording ----------------------

def _link(target, source):
    target.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(source, target)


def test_gs_17_a_symlinked_target_folder_is_refused_and_its_files_are_kept(project, tmp_path):
    from compass_pkg.core import CompassError
    root, task_dir = project
    _commit(root, task_dir)
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "keep.txt").write_text("mine\n", encoding="utf-8")
    _link(_gen(task_dir, 2), victim)
    with pytest.raises(CompassError) as caught:
        _commit(root, task_dir, delivery_approach="full")
    assert "symbolic link" in str(caught.value) and str(_gen(task_dir, 2)) in str(caught.value)
    assert (victim / "keep.txt").read_text(encoding="utf-8") == "mine\n"
    assert sorted(p.name for p in victim.iterdir()) == ["keep.txt"]


def test_gs_17_the_command_refuses_a_symlinked_folder_with_exit_2(tmp_path):
    (tmp_path / "p").mkdir()
    root, task_dir = _project(tmp_path / "p")
    _evaluate_write(root)
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "keep.txt").write_text("mine\n", encoding="utf-8")
    _link(_gen(task_dir, 2), victim)
    body = _manifest(task_dir)
    body["assessment"]["size"] = "large"
    _write_manifest(task_dir, assessment=body["assessment"])
    code, out, err = _evaluate_write(root)
    assert code == 2, out + err
    assert (victim / "keep.txt").exists() and len(list(victim.iterdir())) == 1


def test_gs_17_a_symlinked_generations_folder_is_refused(project, tmp_path):
    from compass_pkg.core import CompassError
    root, task_dir = project
    victim = tmp_path / "victim"
    victim.mkdir()
    os.symlink(victim, task_dir / "generations")
    with pytest.raises(CompassError) as caught:
        _commit(root, task_dir)
    assert "symbolic link" in str(caught.value)
    assert list(victim.iterdir()) == []


def test_gs_17_a_symlinked_file_inside_an_incomplete_folder_is_refused(project, tmp_path):
    from compass_pkg.core import CompassError
    root, task_dir = project
    outside = tmp_path / "outside.txt"
    outside.write_text("mine\n", encoding="utf-8")
    folder = _gen(task_dir, 1)
    folder.mkdir(parents=True)
    (folder / "resolved.yml").write_text("schema: 1\n", encoding="utf-8")
    os.symlink(outside, folder / "link.yml")
    with pytest.raises(CompassError) as caught:
        _commit(root, task_dir)
    assert "symbolic link" in str(caught.value) and "link.yml" in str(caught.value)
    assert outside.read_text(encoding="utf-8") == "mine\n"
    assert (folder / "resolved.yml").read_text(encoding="utf-8") == "schema: 1\n"


def test_gs_17_a_landed_issue_cannot_store_a_new_generation(project):
    from compass_pkg.core import CompassError
    root, task_dir = project
    _commit(root, task_dir)
    _write_manifest(task_dir, status="landed")
    before = {p.relative_to(task_dir).as_posix(): p.read_bytes()
              for p in task_dir.rglob("*") if p.is_file() and p.name != ".generation.lock"}
    with pytest.raises(CompassError) as caught:
        _commit(root, task_dir, delivery_approach="full")
    assert "landed" in str(caught.value) and SLUG in str(caught.value)
    after = {p.relative_to(task_dir).as_posix(): p.read_bytes()
             for p in task_dir.rglob("*") if p.is_file() and p.name != ".generation.lock"}
    assert after == before


def test_gs_17_a_landed_issue_may_still_report_no_change(project):
    root, task_dir = project
    _commit(root, task_dir)
    _write_manifest(task_dir, status="landed")
    again = _commit(root, task_dir)
    assert (again.number, again.committed) == (1, False)


def test_gs_17_a_concurrent_change_says_no_generation_not_none(project):
    from compass_pkg import effective, generation
    from compass_pkg.core import CompassError
    root, task_dir = project
    manifest = _manifest(task_dir)
    manifest.update(OUTCOME)
    resolution = effective.resolve_live(str(root), manifest, SLUG, str(task_dir))
    _write_manifest(task_dir, generation=3)
    with pytest.raises(CompassError) as caught:
        generation.commit(str(task_dir), resolution, manifest)
    text = str(caught.value)
    assert "None" not in text and "no generation" in text and "generation 3" in text


REJECTED = {"schema": 1, "checks": {"suite-passed": {"set": {"severity": "advisory"}}}}


def test_gs_17_a_rejected_compass_yml_names_the_file_the_first_error_and_the_lint(tmp_path):
    root, task_dir = _project(tmp_path, compass_yml=REJECTED)
    code, out, err = _evaluate_write(root)
    text = out + err
    assert code == 2, text
    assert "compass.yml" in text
    assert "K-LOCK-REFUSED" in text
    assert "`compass policy lint --issue feature`" in text


def test_gs_17_evaluate_without_write_still_works_on_a_rejected_compass_yml(tmp_path):
    root, task_dir = _project(tmp_path, compass_yml=REJECTED)
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG)
    assert code == 0, out + err


def _commands_in(text):
    """The `compass ...` commands a message puts in backticks, cut at the first
    option, placeholder or number."""
    import re
    found = []
    for quoted in re.findall(r"`(compass [^`]+)`", text):
        words = []
        for word in quoted.split()[1:]:
            if word.startswith(("-", "<", "[")) or word.isdigit():
                break
            words.append(word)
        found.append(words)
    return found


def _exists(words):
    return _run(ROOT, *words, "--help")[0] == 0


def test_gs_17_messages_name_only_commands_the_cli_has(project, tmp_path):
    import shutil
    from compass_pkg import generation
    from compass_pkg.core import CompassError
    root, task_dir = project
    messages = []
    _commit(root, task_dir)
    (_gen(task_dir, 1) / "complete").unlink()
    with pytest.raises(CompassError) as broken:
        generation.load(str(task_dir), 1)
    messages.append(str(broken.value))
    shutil.rmtree(_gen(task_dir, 1))
    _write_manifest(task_dir, generation=0)
    _commit(root, task_dir)
    shutil.copytree(_gen(task_dir, 1), _gen(task_dir, 2))
    with pytest.raises(CompassError) as unreferenced:
        _commit(root, task_dir, delivery_approach="full")
    messages.append(str(unreferenced.value))
    with pytest.raises(CompassError) as zero:
        from compass_pkg import effective
        _write_manifest(task_dir, generation=0)
        effective.effective_for(str(task_dir))
    messages.append(str(zero.value))
    named = [words for text in messages for words in _commands_in(text)]
    assert named, "the messages should name the command that fixes the fault"
    assert [w for w in named if not _exists(w)] == []
    assert ["issue", "configure"] in named
    assert not [m for m in messages if "migrate-config" in m]


def test_cr_10_the_unreferenced_folder_message_gives_the_path_then_both_commands(project):
    """Scenario CR-10 (issue configure-and-reassess). The ruling for a complete,
    unreferenced folder: the path first, then the two commands. The fallback
    of deleting the folder is gone now the commands exist."""
    from compass_pkg import generation
    from compass_pkg.core import CompassError
    root, task_dir = project
    _commit(root, task_dir)
    import shutil
    shutil.copytree(_gen(task_dir, 1), _gen(task_dir, 2))
    with pytest.raises(CompassError) as caught:
        _commit(root, task_dir, delivery_approach="full")
    text = str(caught.value)
    folder = str(_gen(task_dir, 2))
    assert text.startswith(folder)
    assert "compass issue configure --commit" in text
    assert "compass issue configure --discard" in text
    assert text.index("compass issue configure --commit") < text.index(
        "compass issue configure --discard")
    assert "delete the folder" not in text and "delete" not in text.lower()
    assert "--reason" in text          # a reason given to the interrupted reassess is kept


def test_gs_17_the_wording_check_can_fail():
    assert _commands_in("run `compass issue no-such-verb` to repair") == [
        ["issue", "no-such-verb"]]
    assert not _exists(["issue", "no-such-verb"])
    assert _exists(["approach", "evaluate"])


def test_gs_17_a_broken_generation_message_starts_with_the_folder_path(project):
    from compass_pkg import generation
    from compass_pkg.core import CompassError
    root, task_dir = project
    _commit(root, task_dir)
    (_gen(task_dir, 1) / "complete").unlink()
    with pytest.raises(CompassError) as caught:
        generation.load(str(task_dir), 1)
    text = str(caught.value)
    assert str(_gen(task_dir, 1)) in text
    assert "remove the folder" in text and "`generation:`" in text


# --- GS-18: the command writes the manifest atomically, and modes are kept -------------------

def _umask():
    old = os.umask(0)
    os.umask(old)
    return old


def _evaluate_in_process(root, monkeypatch, capsys):
    import types
    from compass_pkg import routing
    monkeypatch.chdir(root)
    args = types.SimpleNamespace(reading=None, task=SLUG, write=True, reason=None,
                                 kind=None, _mode=None, evidence_out=None)
    code = routing.cmd_route_evaluate(args)
    capsys.readouterr()
    return code


def test_gs_18_the_command_never_opens_the_manifest_for_writing(tmp_path, monkeypatch, capsys):
    import builtins
    root, task_dir = _project(tmp_path)
    opened = []
    real = builtins.open

    def spy(file, mode="r", *args, **kwargs):
        if str(file).endswith("manifest.yml") and any(c in str(mode) for c in "wa+x"):
            opened.append((str(file), mode))
        return real(file, mode, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", spy)
    assert _evaluate_in_process(root, monkeypatch, capsys) == 0
    assert opened == []
    assert _manifest(task_dir)["generation"] == 1
    text = (task_dir / "manifest.yml").read_text(encoding="utf-8")
    assert "# accepts:" in text


def test_gs_18_the_gate_comments_are_written_inside_the_commit(tmp_path, monkeypatch, capsys):
    """A crash after the manifest is replaced must not lose the comments, and
    the commit's no-change path must keep them."""
    root, task_dir = _project(tmp_path)
    _evaluate_in_process(root, monkeypatch, capsys)
    first = (task_dir / "manifest.yml").read_text(encoding="utf-8")
    _evaluate_in_process(root, monkeypatch, capsys)
    assert (task_dir / "manifest.yml").read_text(encoding="utf-8") == first


def test_gs_18_a_manifest_keeps_its_mode_across_a_commit(project):
    root, task_dir = project
    os.chmod(task_dir / "manifest.yml", 0o640)
    _commit(root, task_dir)
    assert (task_dir / "manifest.yml").stat().st_mode & 0o777 == 0o640
    _commit(root, task_dir, delivery_approach="full")
    assert (task_dir / "manifest.yml").stat().st_mode & 0o777 == 0o640


def test_gs_18_new_generation_files_get_the_umask_mode(project):
    root, task_dir = project
    _commit(root, task_dir)
    expected = 0o666 & ~_umask()
    for name in (*FILE_NAMES, "complete"):
        assert (_gen(task_dir, 1) / name).stat().st_mode & 0o777 == expected, name


def test_gs_18_atomic_write_text_keeps_the_mode_of_the_file_it_replaces(tmp_path):
    from compass_pkg.atomic_io import atomic_write_text
    path = tmp_path / "f.txt"
    path.write_text("a", encoding="utf-8")
    os.chmod(path, 0o604)
    atomic_write_text(path, "b")
    assert path.stat().st_mode & 0o777 == 0o604
    fresh = tmp_path / "g.txt"
    atomic_write_text(fresh, "c")
    assert fresh.stat().st_mode & 0o777 == 0o666 & ~_umask()


# --- GS-19: quick-fix start with a rejected compass.yml leaves nothing behind ----------------

QUICK_START = ("quick-fix", "start", "greet",
               "--risk", "trivial - a one-line text change",
               "--familiarity", "brownfield-mapped - the file and its test exist",
               "--size", "atomic - one line",
               "--intent", "the greeting reads correctly",
               "--scenario", "Given the greeting, when read, then it says hello",
               "--test", "tests/test_greeting.py")


def _git_project(tmp_path):
    env = dict(_env(tmp_path), GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    for argv in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "base"]):
        subprocess.run(["git", *argv], cwd=tmp_path, env=env, check=True, capture_output=True)
    return tmp_path


def test_gs_19_a_rejected_compass_yml_leaves_no_issue_folder_and_the_slug_stays_free(tmp_path):
    root = _git_project(tmp_path)
    (root / "compass.yml").write_text(yaml.safe_dump(REJECTED), encoding="utf-8")
    code, out, err = _run(root, *QUICK_START)
    assert code == 2, out + err
    assert "compass policy lint" in out + err
    assert not (root / ".compass" / "work" / "greet").exists()
    (root / "compass.yml").write_text("schema: 1\n", encoding="utf-8")
    code, out, err = _run(root, *QUICK_START)
    assert code == 0, out + err
    assert (root / ".compass" / "work" / "greet" / "generations" / "1" / "complete").is_file()


# --- GS-20: edge cases of states, verdicts and overwriting -----------------------------------

def test_gs_20_a_check_that_any_gate_failed_keeps_the_verdict_fail():
    from compass_pkg import check_cmd
    from compass_pkg.checks import NOTHING_TO_CHECK
    rows = [("G1", "x", True, ""), ("G2", "x", False, ""), ("G1", "y", False, ""),
            ("G2", "y", True, ""), ("G1", "z", NOTHING_TO_CHECK, ""), ("G1", "w", True, "")]
    assert check_cmd._verdicts(rows) == {"x": "fail", "y": "fail",
                                         "z": "nothing-to-check", "w": "pass"}


def test_gs_20_a_lower_folder_without_a_marker_is_incomplete(project):
    from compass_pkg import generation
    root, task_dir = project
    _commit(root, task_dir)
    _commit(root, task_dir, delivery_approach="full")
    (_gen(task_dir, 1) / "complete").unlink()
    found = {g.number: g.state for g in generation.states(str(task_dir))}
    assert found == {1: "incomplete", 2: "current"}


def test_gs_20_a_folder_with_proposed_yml_and_leftovers_is_incomplete_not_a_proposal(project):
    from compass_pkg import generation
    root, task_dir = project
    _commit(root, task_dir)
    folder = _gen(task_dir, 2)
    folder.mkdir()
    (folder / "proposed.yml").write_text("schema: 1\n", encoding="utf-8")
    (folder / "resolved.yml").write_text("schema: 1\n", encoding="utf-8")
    found = {g.number: g.state for g in generation.states(str(task_dir))}
    assert found == {1: "current", 2: "incomplete"}


def test_gs_20_a_folder_named_with_a_non_ascii_digit_is_ignored(project):
    from compass_pkg import generation
    root, task_dir = project
    _commit(root, task_dir)
    (task_dir / "generations" / "²").mkdir()
    assert [(g.number, g.state) for g in generation.states(str(task_dir))] == [(1, "current")]
    code, out, err = _run(root, "ci")
    assert "Traceback" not in out + err


def test_gs_20_overwriting_an_incomplete_folder_keeps_proposed_yml(project):
    root, task_dir = project
    folder = _gen(task_dir, 1)
    folder.mkdir(parents=True)
    (folder / "proposed.yml").write_text("schema: 1\nbase_generation: 0\noverlay: {}\n",
                                         encoding="utf-8")
    (folder / "resolved.yml").write_text("garbage: true\n", encoding="utf-8")
    assert _commit(root, task_dir).committed
    assert _load(folder / "proposed.yml")["base_generation"] == 0
    assert _load(folder / "resolved.yml")["schema"] == 1


def test_gs_20_a_folder_whose_marker_does_not_match_is_overwritten_as_incomplete(project):
    import shutil
    root, task_dir = project
    _commit(root, task_dir)
    shutil.copytree(_gen(task_dir, 1), _gen(task_dir, 2))
    text = (_gen(task_dir, 2) / "resolved.yml").read_text(encoding="utf-8")
    (_gen(task_dir, 2) / "resolved.yml").write_text(text + "extra: 1\n", encoding="utf-8")
    result = _commit(root, task_dir, delivery_approach="full")
    assert (result.number, result.committed) == (2, True)
    assert "extra" not in _load(_gen(task_dir, 2) / "resolved.yml")


# --- GS-22: the evaluator's policy from the effective view -----------------------------------

def test_gs_22_evaluator_policy_is_the_adapter_over_the_resolved_configuration(
        tmp_path, monkeypatch):
    from compass_pkg import effective, obligations
    root, task_dir = _project(tmp_path)
    monkeypatch.chdir(root)
    live = effective.effective_for(str(task_dir))
    _commit(root, task_dir)
    stored = effective.effective_for(str(task_dir))
    for view in (live, stored):
        policy = view.evaluator_policy()
        assert policy == obligations.policy_adapter(view.config)
        assert {"route_shapes", "assessment_vocabulary", "routing_strategies"} <= set(policy)
    assert live.evaluator_policy() == stored.evaluator_policy()


def test_gs_12_check_records_results_from_the_manifest_it_already_loaded(tmp_path, monkeypatch):
    # compass check holds the manifest; reading it again from disk is a second
    # source of truth, and fails a summary built without a file on disk.
    import inspect
    from compass_pkg import effective
    assert "manifest" in inspect.signature(effective.record_check_results).parameters
    calls = []
    monkeypatch.setattr(effective, "load_manifest", lambda *a, **k: calls.append(a))
    assert effective.record_check_results(tmp_path, {}, manifest={"status": "active"}) is None
    assert calls == []
