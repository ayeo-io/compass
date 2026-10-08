"""The reassess commit of a proposal, adoption of a leftover folder, and the
records a new generation carries.

Scenario ids: `CR-5` to `CR-9` (issue `configure-and-reassess`). Each test name
starts with its scenario id. Crash injection replaces the single module-level
hook `generation._after_step`, as the store's own tests do; product code has
no switch for it.
"""
from __future__ import annotations

import shutil
import sys
import types
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import configure_fixtures as fx  # noqa: E402

MODE = ("--mode", "refine=full")
STEPS = ("resolved", "provenance", "versions", "records", "marker", "manifest", "proposal")


def _snapshot(root):
    """Every file under the project, with its bytes, so a refusal can be shown
    to have changed nothing."""
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _reassess_in_process(root, monkeypatch, capsys, boom_at=None, **extra):
    """`approach evaluate --write` in this process, interrupted after `boom_at`."""
    from compass_pkg import generation, routing
    monkeypatch.chdir(root)

    def hook(step):
        if step == boom_at:
            raise RuntimeError(f"interrupted after {step}")
    monkeypatch.setattr(generation, "_after_step", hook)
    fields = dict(reading=None, task=fx.SLUG, write=True, reason="test", kind=None,
                  _mode=None, evidence_out=None, json=False, reset_config=False, adopt=None)
    fields.update(extra)
    args = types.SimpleNamespace(**fields)
    try:
        return routing.cmd_route_evaluate(args)
    finally:
        monkeypatch.setattr(generation, "_after_step", lambda step: None)
        capsys.readouterr()


def _states(task_dir):
    from compass_pkg import generation
    return {g.number: g.state for g in generation.states(str(task_dir))}


def _proposed_project(tmp_path, *flags):
    root, task_dir = fx.committed(tmp_path)
    code, out, err = fx.configure(root, *(flags or MODE))
    assert code == 0, out + err
    return root, task_dir


# --- CR-5: adopting a complete leftover folder -----------------------------------------------

def _leftover(tmp_path, monkeypatch, capsys, step="marker"):
    root, task_dir = _proposed_project(tmp_path)
    before = (task_dir / "manifest.yml").read_bytes()
    with pytest.raises(RuntimeError):
        _reassess_in_process(root, monkeypatch, capsys, boom_at=step)
    assert (task_dir / "manifest.yml").read_bytes() == before
    return root, task_dir, before


def test_cr_5_commit_adopts_a_whole_folder_the_fresh_resolution_matches(
        tmp_path, monkeypatch, capsys):
    root, task_dir, before = _leftover(tmp_path, monkeypatch, capsys)
    files = {p.name: p.read_bytes() for p in fx.gen(task_dir, 2).iterdir()}
    assert _states(task_dir) == {1: "current", 2: "complete-unreferenced"}
    code, out, err = fx.configure(root, "--commit")
    assert code == 0, out + err
    assert "adopted generation 2" in out
    body = fx.manifest_of(task_dir)
    assert body["generation"] == 2
    assert body["config"] == {"stages": {"refine": {"set": {"mode": "full"}}}}
    assert not (fx.gen(task_dir, 2) / "proposed.yml").exists()
    for name in ("resolved.yml", "provenance.yml", "versions.yml", "records.yml", "complete"):
        assert (fx.gen(task_dir, 2) / name).read_bytes() == files[name], name
    assert _states(task_dir) == {1: "superseded", 2: "current"}


def test_cr_5_an_adopted_folder_gives_the_manifest_an_uninterrupted_reassess_would(
        tmp_path, monkeypatch, capsys):
    root, task_dir, _ = _leftover(tmp_path, monkeypatch, capsys)
    assert fx.configure(root, "--commit")[0] == 0
    other_root, other_dir = _proposed_project(tmp_path / "other")
    assert fx.reassess(other_root)[0] == 0
    adopted, direct = fx.manifest_of(task_dir), fx.manifest_of(other_dir)
    for key in ("generation", "delivery_approach", "stages", "gates", "checkpoints",
                "policy_rules_fired", "subtask_ceiling", "artifacts", "config"):
        assert adopted[key] == direct[key], key


def test_cr_5_commit_refuses_when_the_project_changed_since_the_crash(
        tmp_path, monkeypatch, capsys):
    root, task_dir, before = _leftover(tmp_path, monkeypatch, capsys)
    (root / "compass.yml").write_text(
        yaml.safe_dump({"schema": 1, "checks": {"extra": {
            "statement": "A check.", "kind": "deterministic", "impl": "suite-passed",
            "severity": "advisory", "on_skipped": "fail"}}}), encoding="utf-8")
    snapshot = _snapshot(root)
    code, out, err = fx.configure(root, "--commit")
    assert code == 2, out + err
    text = out + err
    assert "cannot be adopted" in text and "resolved.yml" in text
    assert "compass issue configure --discard 2" in text
    assert _snapshot(root) == snapshot
    assert (task_dir / "manifest.yml").read_bytes() == before


def test_cr_5_commit_refuses_an_incomplete_folder_and_a_folder_that_does_not_match_its_marker(
        tmp_path, monkeypatch, capsys):
    root, task_dir, before = _leftover(tmp_path, monkeypatch, capsys, step="records")
    snapshot = _snapshot(root)
    code, out, err = fx.configure(root, "--commit")
    assert code == 2, out + err
    assert "complete marker" in out + err and "--discard 2" in out + err
    assert _snapshot(root) == snapshot
    root2, task2, _ = _leftover(tmp_path / "two", monkeypatch, capsys)
    target = fx.gen(task2, 2) / "versions.yml"
    target.write_text(target.read_text(encoding="utf-8") + "tampered: true\n", encoding="utf-8")
    snapshot = _snapshot(root2)
    code, out, err = fx.configure(root2, "--commit")
    assert code == 2, out + err
    assert "digest" in out + err
    assert _snapshot(root2) == snapshot


def test_cr_5_commit_refuses_a_folder_that_is_not_the_next_generation(
        tmp_path, monkeypatch, capsys):
    root, task_dir, before = _leftover(tmp_path, monkeypatch, capsys)
    shutil.copytree(fx.gen(task_dir, 2), fx.gen(task_dir, 3))
    snapshot = _snapshot(root)
    code, out, err = fx.configure(root, "--commit", "3")
    assert code == 2, out + err
    assert "feature is at generation 1, so the generation to adopt is 2, not 3" in out + err
    assert _snapshot(root) == snapshot


def test_cr_5_commit_with_nothing_to_adopt_is_an_error_and_creates_nothing(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    snapshot = _snapshot(root)
    code, out, err = fx.configure(root, "--commit")
    assert code == 2, out + err
    assert "nothing to adopt" in out + err
    assert "FINAL APPROACH" not in out and "wrote the delivery" not in out
    assert _snapshot(root) == snapshot
    assert not fx.gen(task_dir, 2).exists()


def test_cr_5_commit_refuses_a_folder_that_adds_nothing(tmp_path, monkeypatch, capsys):
    """A leftover equal to the generation in force is no reason to commit."""
    root, task_dir = fx.committed(tmp_path)
    shutil.copytree(fx.gen(task_dir, 1), fx.gen(task_dir, 2))
    code, out, err = fx.configure(root, "--commit")
    assert code == 2, out + err
    assert "already holds this configuration" in out + err
    assert fx.manifest_of(task_dir)["generation"] == 1


def _commit_adopting(root, task_dir, adopt):
    """The store's own refusal, below the command's early checks."""
    from compass_pkg import effective
    manifest = fx.manifest_of(task_dir)
    manifest["config"] = {"stages": {"refine": {"set": {"mode": "full"}}}}   # the proposal
    return effective.commit_generation(str(task_dir), manifest, adopt=adopt)


def test_cr_5_the_store_refuses_an_incomplete_folder_even_when_asked_directly(
        tmp_path, monkeypatch, capsys):
    from compass_pkg.core import CompassError
    root, task_dir, before = _leftover(tmp_path, monkeypatch, capsys, step="records")
    snapshot = _snapshot(root)
    with pytest.raises(CompassError, match="cannot be adopted"):
        _commit_adopting(root, task_dir, 2)
    assert _snapshot(root) == snapshot


def test_cr_5_the_store_refuses_a_number_that_is_not_the_next_generation(
        tmp_path, monkeypatch, capsys):
    from compass_pkg.core import CompassError
    root, task_dir, before = _leftover(tmp_path, monkeypatch, capsys)
    snapshot = _snapshot(root)
    with pytest.raises(CompassError, match="generation to adopt is 2, not 5"):
        _commit_adopting(root, task_dir, 5)
    assert _snapshot(root) == snapshot


def test_cr_5_the_store_refuses_when_the_resolution_no_longer_matches_the_folder(
        tmp_path, monkeypatch, capsys):
    from compass_pkg.core import CompassError
    root, task_dir, before = _leftover(tmp_path, monkeypatch, capsys)
    (root / "compass.yml").write_text("schema: 1\nowner: someone\n", encoding="utf-8")
    with pytest.raises(CompassError, match="no longer match"):
        _commit_adopting(root, task_dir, 2)
    assert fx.manifest_of(task_dir)["generation"] == 1


def test_cr_5_commit_and_discard_are_two_ways_not_one_call(tmp_path):
    root, task_dir = _proposed_project(tmp_path)
    code, out, err = fx.configure(root, "--commit", "--discard")
    assert code == 2, out + err
    assert "give one" in out + err
    assert (fx.gen(task_dir, 2) / "proposed.yml").is_file()
    code, out, err = fx.configure(root, "--commit", "--autonomy", "controlled")
    assert code == 2, out + err
    code, out, err = fx.configure(root, "--commit", "--json")
    assert code == 2, out + err


def test_cr_5_a_first_generation_left_behind_is_adopted_from_generation_zero(
        tmp_path, monkeypatch, capsys):
    root, task_dir = fx.project(tmp_path)
    fx.write_manifest(task_dir, generation=0)
    with pytest.raises(RuntimeError):
        _reassess_in_process(root, monkeypatch, capsys, boom_at="marker")
    assert fx.manifest_of(task_dir)["generation"] == 0
    code, out, err = fx.configure(root, "--commit")
    assert code == 0, out + err
    assert fx.manifest_of(task_dir)["generation"] == 1
    assert _states(task_dir) == {1: "current"}


# --- CR-6: a reassess interrupted after each step ---------------------------------------------

@pytest.mark.parametrize("step", STEPS)
def test_cr_6_the_manifest_names_the_previous_generation_until_its_replace(
        tmp_path, monkeypatch, capsys, step):
    root, task_dir = _proposed_project(tmp_path)
    before = (task_dir / "manifest.yml").read_bytes()
    with pytest.raises(RuntimeError, match=step):
        _reassess_in_process(root, monkeypatch, capsys, boom_at=step)
    body = fx.manifest_of(task_dir)
    if step in ("manifest", "proposal"):
        assert body["generation"] == 2
        assert _states(task_dir)[2] == "current"
    else:
        assert (task_dir / "manifest.yml").read_bytes() == before
        assert body["generation"] == 1
        assert _states(task_dir)[2] == (
            "complete-unreferenced" if step == "marker" else "incomplete")
    assert fx.load(fx.gen(task_dir, 1) / "resolved.yml")["generation"] == 1


@pytest.mark.parametrize("step", ["resolved", "provenance", "versions", "records"])
def test_cr_6_an_incomplete_folder_is_discarded_or_written_again(
        tmp_path, monkeypatch, capsys, step):
    root, task_dir = _proposed_project(tmp_path)
    with pytest.raises(RuntimeError):
        _reassess_in_process(root, monkeypatch, capsys, boom_at=step)
    assert fx.configure(root, "--commit")[0] == 2
    assert fx.manifest_of(task_dir)["generation"] == 1
    code, out, err = fx.configure(root, "--discard")
    assert code == 0, out + err
    assert not fx.gen(task_dir, 2).exists()
    assert fx.manifest_of(task_dir)["generation"] == 1


@pytest.mark.parametrize("step", ["resolved", "provenance", "versions", "records"])
def test_cr_6_the_next_reassess_overwrites_an_incomplete_folder_and_applies_the_proposal(
        tmp_path, monkeypatch, capsys, step):
    root, task_dir = _proposed_project(tmp_path)
    with pytest.raises(RuntimeError):
        _reassess_in_process(root, monkeypatch, capsys, boom_at=step)
    assert (fx.gen(task_dir, 2) / "proposed.yml").is_file()
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    body = fx.manifest_of(task_dir)
    assert body["generation"] == 2
    assert body["config"]["stages"]["refine"]["set"]["mode"] == "full"
    assert not (fx.gen(task_dir, 2) / "proposed.yml").exists()
    assert _states(task_dir)[2] == "current"


def test_cr_6_a_complete_unreferenced_folder_is_adopted_or_discarded(
        tmp_path, monkeypatch, capsys):
    root, task_dir, before = _leftover(tmp_path, monkeypatch, capsys)
    code, out, err = fx.reassess(root)
    assert code == 2, out + err
    assert "compass issue configure --commit 2" in out + err
    assert "compass issue configure --discard 2" in out + err
    assert (task_dir / "manifest.yml").read_bytes() == before
    code, out, err = fx.configure(root, "--discard")
    assert code == 0, out + err
    assert not fx.gen(task_dir, 2).exists()
    assert (task_dir / "manifest.yml").read_bytes() == before


@pytest.mark.parametrize("step", ["manifest", "proposal"])
def test_cr_6_after_the_manifest_replace_the_new_generation_is_in_force(
        tmp_path, monkeypatch, capsys, step):
    root, task_dir = _proposed_project(tmp_path)
    with pytest.raises(RuntimeError):
        _reassess_in_process(root, monkeypatch, capsys, boom_at=step)
    assert fx.manifest_of(task_dir)["config"]["stages"]["refine"]["set"]["mode"] == "full"
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert "no change" in out
    assert fx.manifest_of(task_dir)["generation"] == 2
    assert fx.configure(root, "--discard")[0] == 2     # nothing above generation 2
    code, out, err = fx.configure(root, "--autonomy", "controlled")
    assert code == 0, out + err
    assert (fx.gen(task_dir, 3) / "proposed.yml").is_file()


# --- CR-7: the reassess commit of a proposal ---------------------------------------------------

def test_cr_7_reassess_commits_the_proposal_as_the_config_and_consumes_it(tmp_path):
    from compass_pkg import layers
    root, task_dir = _proposed_project(tmp_path)
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    overlay = {"stages": {"refine": {"set": {"mode": "full"}}}}
    body = fx.manifest_of(task_dir)
    assert body["generation"] == 2 and body["config"] == overlay
    assert not (fx.gen(task_dir, 2) / "proposed.yml").exists()
    assert fx.load(fx.gen(task_dir, 2) / "resolved.yml")["stages"]["refine"]["mode"] == "full"
    assert fx.load(fx.gen(task_dir, 2) / "versions.yml")["issue_overlay_digest"] == (
        layers.layer_digest(overlay, "issue"))
    assert "applied the proposed configuration" in out
    assert (fx.gen(task_dir, 2) / "complete").is_file()


def test_cr_7_a_proposal_built_on_another_config_is_refused_before_anything_prints(tmp_path):
    root, task_dir = _proposed_project(tmp_path)
    fx.write_manifest(task_dir, config={"autonomy": "controlled"})
    snapshot = _snapshot(root)
    code, out, err = fx.reassess(root)
    assert code == 2, out + err
    assert "stale" in out + err and "compass issue configure --discard" in out + err
    assert "FINAL APPROACH" not in out and "wrote the delivery approach" not in out
    assert out.strip() == ""
    assert _snapshot(root) == snapshot


def test_cr_7_a_proposal_built_on_another_generation_is_refused(tmp_path):
    root, task_dir = _proposed_project(tmp_path)
    path = fx.gen(task_dir, 2) / "proposed.yml"
    body = fx.load(path)
    body["base_generation"] = 0
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    snapshot = _snapshot(root)
    code, out, err = fx.reassess(root)
    assert code == 2, out + err
    assert "stale" in out + err and "generation 0" in out + err
    assert _snapshot(root) == snapshot


def test_cr_7_a_proposal_the_lint_refuses_is_kept_and_nothing_is_written(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    assert fx.configure(root, "--mode", "define=collapsed")[0] == 1
    snapshot = _snapshot(root)
    code, out, err = fx.reassess(root)
    assert code == 2, out + err
    assert "nothing was written" in out + err
    assert _snapshot(root) == snapshot
    assert (fx.gen(task_dir, 2) / "proposed.yml").is_file()


def test_cr_7_reset_config_drops_the_overlay_and_commits_a_generation_without_it(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    fx.write_manifest(task_dir, config={"stages": {"refine": {"set": {"mode": "full"}}}})
    assert fx.reassess(root)[0] == 0
    assert fx.manifest_of(task_dir)["generation"] == 2
    code, out, err = fx.reassess(root, "--reset-config")
    assert code == 0, out + err
    body = fx.manifest_of(task_dir)
    assert "config" not in body and body["generation"] == 3
    assert fx.load(fx.gen(task_dir, 3) / "versions.yml")["issue_overlay_digest"] is None
    assert "dropped the issue's config: layer" in out


def test_cr_7_reset_config_with_a_pending_proposal_is_refused(tmp_path):
    root, task_dir = _proposed_project(tmp_path)
    snapshot = _snapshot(root)
    code, out, err = fx.reassess(root, "--reset-config")
    assert code == 2, out + err
    assert "--reset-config" in out + err and "compass issue configure --discard" in out + err
    assert _snapshot(root) == snapshot


def test_cr_7_a_proposal_that_asks_for_what_is_held_commits_nothing_and_is_removed(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    fx.write_manifest(task_dir, config={"autonomy": "controlled"})
    assert fx.reassess(root)[0] == 0
    code, out, err = fx.configure(root, "--from-file", _file(tmp_path, "autonomy: controlled\n"))
    assert code == 0, out + err
    assert (fx.gen(task_dir, 3) / "proposed.yml").is_file()
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert "no change" in out
    assert fx.manifest_of(task_dir)["generation"] == 2
    assert not fx.gen(task_dir, 3).exists() or not (fx.gen(task_dir, 3) / "proposed.yml").exists()


def test_cr_7_a_proposal_replaced_while_the_reassess_runs_is_not_committed(
        tmp_path, monkeypatch, capsys):
    """The plan reads the proposal before it prints; the commit checks, under
    the lock, that the file is still the one that was applied."""
    from compass_pkg import effective
    root, task_dir = _proposed_project(tmp_path)
    real = effective.commit_generation

    def replaced(*args, **kwargs):
        path = fx.gen(task_dir, 2) / "proposed.yml"
        body = fx.load(path)
        body["overlay"] = {"autonomy": "controlled"}
        path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
        return real(*args, **kwargs)
    monkeypatch.setattr(effective, "commit_generation", replaced)
    before = (task_dir / "manifest.yml").read_bytes()
    with pytest.raises(Exception, match="changed while the command ran"):
        _reassess_in_process(root, monkeypatch, capsys)
    assert (task_dir / "manifest.yml").read_bytes() == before
    assert sorted(p.name for p in fx.gen(task_dir, 2).iterdir()) == ["proposed.yml"]


def _file(tmp_path, text):
    path = tmp_path / "overlay-input.yml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_cr_7_reset_config_without_write_is_refused(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    code, out, err = fx.run(root, "approach", "evaluate", "--issue", fx.SLUG, "--reset-config")
    assert code == 2, out + err
    assert "--write" in out + err


# --- CR-8: the generation a reassessment moved from and to ----------------------------------------

def test_cr_8_a_reassessment_records_the_generation_it_moved_from_and_to(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    body = fx.manifest_of(task_dir)
    body["assessment"]["size"] = "large"
    fx.write_manifest(task_dir, assessment=body["assessment"])
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    entry = fx.manifest_of(task_dir)["reassessments"][-1]
    assert entry["generation"] == {"from": 1, "to": 2}
    assert list(entry)[-1] == "generation"
    assert fx.run(root, "issue", "lint", "--issue", fx.SLUG)[0] == 0


def test_cr_8_a_reassessment_that_commits_nothing_names_the_same_generation_twice(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    body = fx.manifest_of(task_dir)
    body["assessment"]["labels"] = ["docs"]
    fx.write_manifest(task_dir, assessment=body["assessment"])
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert "no change" in out
    assert fx.manifest_of(task_dir)["reassessments"][-1]["generation"] == {"from": 1, "to": 1}


def test_cr_8_a_reassess_that_changes_only_the_config_records_a_configuration_entry(tmp_path):
    root, task_dir = _proposed_project(tmp_path)
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    entry = fx.manifest_of(task_dir)["reassessments"][-1]
    assert entry["kind"] == "configuration"
    assert entry["reason"] == "test"
    assert entry["generation"] == {"from": 1, "to": 2}
    assert entry["from_route"] == entry["to_route"] == "regular"
    assert "was NOT recorded" not in out
    assert "RE-ASSESSMENT recorded (configuration)" in out
    assert fx.run(root, "issue", "lint", "--issue", fx.SLUG)[0] == 0


def test_cr_8_reset_config_records_a_configuration_entry_too(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    fx.write_manifest(task_dir, config={"autonomy": "controlled"})
    assert fx.reassess(root)[0] == 0
    code, out, err = fx.reassess(root, "--reset-config")
    assert code == 0, out + err
    entry = fx.manifest_of(task_dir)["reassessments"][-1]
    assert (entry["kind"], entry["generation"]) == ("configuration", {"from": 2, "to": 3})


def test_cr_8_a_change_to_the_approach_keeps_its_own_kind_when_the_config_moves_too(tmp_path):
    root, task_dir = _proposed_project(tmp_path)
    body = fx.manifest_of(task_dir)
    body["assessment"]["size"] = "large"
    fx.write_manifest(task_dir, assessment=body["assessment"])
    assert fx.reassess(root)[0] == 0
    entries = fx.manifest_of(task_dir)["reassessments"]
    assert len(entries) == 1 and entries[0]["kind"] == "judgement"
    assert entries[0]["generation"] == {"from": 1, "to": 2}


def test_cr_8_a_proposal_that_commits_nothing_adds_no_entry(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    fx.write_manifest(task_dir, config={"autonomy": "controlled"})
    assert fx.reassess(root)[0] == 0
    before = len(fx.manifest_of(task_dir)["reassessments"])
    assert fx.configure(root, "--autonomy", "controlled")[0] == 0
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert "no change" in out
    assert len(fx.manifest_of(task_dir)["reassessments"]) == before


def test_cr_8_a_configuration_entry_without_a_reason_is_flagged(tmp_path):
    root, task_dir = _proposed_project(tmp_path)
    code, out, err = fx.run(root, "approach", "evaluate", "--issue", fx.SLUG, "--write")
    assert code == 0, out + err
    assert fx.manifest_of(task_dir)["reassessments"][-1]["reason"].startswith("(reason not given")
    assert "no reason" in err


def test_cr_8_the_schema_and_the_cli_list_the_configuration_kind():
    import json
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    kinds = schema["properties"]["reassessments"]["items"]["properties"]["kind"]["enum"]
    assert kinds == ["judgement", "policy-correction", "scope-change", "configuration"]
    code, out, err = fx.run(ROOT, "approach", "evaluate", "--help")
    assert "configuration" in out


def test_cr_8_the_schema_accepts_the_key_and_refuses_a_malformed_one():
    import json
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    item = schema["properties"]["reassessments"]["items"]
    assert "generation" in item["properties"]
    shape = item["properties"]["generation"]
    assert shape["required"] == ["from", "to"] and shape["additionalProperties"] is False
    assert shape["properties"]["from"]["minimum"] == 0


def test_cr_8_a_malformed_generation_in_an_entry_fails_the_issue_lint(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    entry = {"from_route": "regular", "to_route": "full", "reason": "r",
             "generation": {"from": "one", "to": 2}}
    fx.write_manifest(task_dir, reassessments=[entry])
    code, out, err = fx.run(root, "issue", "lint", "--issue", fx.SLUG)
    assert code != 0, out + err


# --- CR-9: records carry forward; a waiver whose parent value changed is invalidated ----------------

def _team(severity):
    return {"schema": 1, "owner": "jed72", "checks": {"team-check": {
        "statement": "A team check.", "kind": "deterministic", "impl": "suite-passed",
        "severity": severity, "on_skipped": "fail"}}}


def _waived_project(tmp_path):
    body = dict(fx.MANIFEST)
    body["config"] = {"checks": {"team-check": {
        "set": {"severity": "advisory"},
        "waiver": {"reason": "A one-line fix.", "approved_by": "EV-1"}}}}
    body["evidence"] = [{
        "id": "EV-1", "type": "human-approval", "decision": "approved",
        "approver": "jed72", "role": "owner", "scope": "waiver",
        "timestamp": "2026-10-07T09:00:00Z",
        "waiver": {"scope": "issue", "entry": "checks.team-check",
                   "fields": {"severity": {"from": "blocking", "to": "advisory"}}}}]
    root, task_dir = fx.project(tmp_path, compass_yml=_team("blocking"), manifest=body)
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    return root, task_dir


def _records(task_dir, n):
    return {r["id"]: r for r in fx.load(fx.gen(task_dir, n) / "records.yml")["records"]}


def test_cr_9_a_waiver_is_valid_while_its_parent_value_is_unchanged(tmp_path):
    root, task_dir = _waived_project(tmp_path)
    assert {k: v["status"] for k, v in _records(task_dir, 1).items()} == {
        "waiver:issue:checks.team-check": "valid", "EV-1": "valid"}
    assert fx.load(fx.gen(task_dir, 1) / "resolved.yml")["checks"]["team-check"][
        "severity"] == "advisory"
    fx.configure(root, "--autonomy", "controlled")
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert {k: v["status"] for k, v in _records(task_dir, 2).items()} == {
        "waiver:issue:checks.team-check": "valid", "EV-1": "valid"}


def test_cr_9_a_changed_parent_value_invalidates_the_waiver_and_its_approval(tmp_path):
    root, task_dir = _waived_project(tmp_path)
    (root / "compass.yml").write_text(yaml.safe_dump(_team("advisory")), encoding="utf-8")
    code, out, err = fx.configure(root, "--autonomy", "controlled", "--json")
    assert code == 0, out + err
    import json
    listed = {r["id"]: r for r in json.loads(out)["invalidates"]}
    assert set(listed) == {"waiver:issue:checks.team-check", "EV-1"}
    assert listed["waiver:issue:checks.team-check"]["kind"] == "waiver"
    assert listed["EV-1"]["kind"] == "approval"
    assert "parent value changed from 'blocking' to 'advisory'" in (
        listed["waiver:issue:checks.team-check"]["reason"])
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    records = _records(task_dir, 2)
    assert {k: v["status"] for k, v in records.items()} == {
        "waiver:issue:checks.team-check": "invalidated", "EV-1": "invalidated"}
    assert all(v["reason"] for v in records.values())
    resolved = fx.load(fx.gen(task_dir, 2) / "resolved.yml")["checks"]["team-check"]
    assert resolved["severity"] == "advisory"
    assert "waiver:issue:checks.team-check" not in fx.load(
        fx.gen(task_dir, 2) / "provenance.yml")["waivers"]
    body = fx.manifest_of(task_dir)
    assert "waiver" in body["config"]["checks"]["team-check"]       # the input is not rewritten
    assert "invalidated waiver:issue:checks.team-check" in out


def test_cr_9_a_parent_change_to_another_field_keeps_the_waiver_valid(tmp_path):
    root, task_dir = _waived_project(tmp_path)
    other = _team("blocking")
    other["checks"]["team-check"]["on_skipped"] = "pass"
    (root / "compass.yml").write_text(yaml.safe_dump(other), encoding="utf-8")
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    # The waived field is `severity`, whose parent value did not change: the
    # waiver stays valid and the issue's value stays in force.
    assert _records(task_dir, 2)["waiver:issue:checks.team-check"]["status"] == "valid"
    assert fx.load(fx.gen(task_dir, 2) / "resolved.yml")["checks"]["team-check"][
        "severity"] == "advisory"


def test_cr_9_a_changed_issue_value_invalidates_the_approval_that_named_the_old_one(tmp_path):
    root, task_dir = _waived_project(tmp_path)
    body = fx.manifest_of(task_dir)
    body["config"]["checks"]["team-check"]["set"]["severity"] = "blocking"
    fx.write_manifest(task_dir, config=body["config"])
    code, out, err = fx.configure(root, "--autonomy", "controlled", "--json")
    assert code in (0, 1), out + err
    import json
    listed = {r["id"] for r in json.loads(out)["invalidates"]}
    assert "waiver:issue:checks.team-check" in listed


def test_cr_9_a_second_reassess_refuses_the_waiver_until_it_is_approved_again(tmp_path):
    root, task_dir = _waived_project(tmp_path)
    (root / "compass.yml").write_text(yaml.safe_dump(_team("advisory")), encoding="utf-8")
    assert fx.reassess(root)[0] == 0
    code, out, err = fx.reassess(root)
    assert code == 2, out + err
    assert "W-APPROVAL-WAIVER" in out + err
    assert "nothing was written" in out + err
    assert fx.manifest_of(task_dir)["generation"] == 2
    # Removing the entry from config: settles it.
    body = fx.manifest_of(task_dir)
    body["config"]["checks"].pop("team-check")
    fx.write_manifest(task_dir, config={"autonomy": "balanced"})
    code, out, err = fx.reassess(root)
    assert code == 0, out + err


def test_cr_9_superseded_and_invalidated_statuses_carry_into_later_generations(tmp_path):
    root, task_dir = _waived_project(tmp_path)
    (root / "compass.yml").write_text(yaml.safe_dump(_team("advisory")), encoding="utf-8")
    assert fx.reassess(root)[0] == 0
    fx.write_manifest(task_dir, config={"autonomy": "balanced"})
    assert fx.reassess(root)[0] == 0
    assert fx.manifest_of(task_dir)["generation"] == 3
    assert {k: v["status"] for k, v in _records(task_dir, 3).items()} == {
        "waiver:issue:checks.team-check": "invalidated", "EV-1": "invalidated"}


def test_cr_9_a_generation_is_not_rewritten_when_a_waiver_is_stale_but_unreferenced(tmp_path):
    """A stale waiver for an entry the overlay no longer holds invalidates
    nothing: the entry is gone and there is nothing left to excuse."""
    root, task_dir = _waived_project(tmp_path)
    (root / "compass.yml").write_text(yaml.safe_dump(_team("advisory")), encoding="utf-8")
    fx.write_manifest(task_dir, config={"autonomy": "balanced"})
    code, out, err = fx.configure(root, "--autonomy", "controlled", "--json")
    assert code == 0, out + err
    import json
    assert json.loads(out)["invalidates"] == []


# --- a refusal never follows a printed result -------------------------------------------------

def test_cr_6_a_stale_waiver_is_refused_before_anything_prints(tmp_path):
    root, task_dir = _waived_project(tmp_path)
    (root / "compass.yml").write_text(yaml.safe_dump(_team("advisory")), encoding="utf-8")
    assert fx.reassess(root)[0] == 0
    snapshot = _snapshot(root)
    code, out, err = fx.reassess(root)
    assert code == 2, out + err
    assert out.strip() == ""
    assert _snapshot(root) == snapshot


def test_cr_6_an_adoption_that_no_longer_matches_is_refused_before_anything_prints(
        tmp_path, monkeypatch, capsys):
    root, task_dir, _ = _leftover(tmp_path, monkeypatch, capsys)
    (root / "compass.yml").write_text("schema: 1\nowner: someone\n", encoding="utf-8")
    code, out, err = fx.configure(root, "--commit")
    assert code == 2, out + err
    assert out.strip() == ""
    assert "cannot be adopted" in err


def test_cr_6_a_landed_issue_is_refused_before_anything_prints(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    fx.write_manifest(task_dir, config={"autonomy": "controlled"}, status="landed")
    code, out, err = fx.reassess(root)
    assert code == 2, out + err
    assert out.strip() == "" and "landed" in err


# --- the reason a stale waiver gives, and the two ways out -------------------------------------

def test_cr_9_the_invalidation_note_says_why_and_names_both_fixes(tmp_path):
    root, task_dir = _waived_project(tmp_path)
    (root / "compass.yml").write_text(yaml.safe_dump(_team("advisory")), encoding="utf-8")
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert "invalidated waiver:issue:checks.team-check" in out
    assert "the parent value changed from 'blocking' to 'advisory'" in out
    assert "approve it again" in out and "remove the entry" in out
    assert "valid again if the parent value returns" in out


def test_cr_9_the_second_refusal_says_why_and_names_both_fixes(tmp_path):
    root, task_dir = _waived_project(tmp_path)
    (root / "compass.yml").write_text(yaml.safe_dump(_team("advisory")), encoding="utf-8")
    assert fx.reassess(root)[0] == 0
    code, out, err = fx.reassess(root)
    assert code == 2, out + err
    text = err
    assert "waiver:issue:checks.team-check was invalidated in generation 2" in text
    assert "the parent value changed from 'blocking' to 'advisory'" in text
    assert "approve it again" in text and "remove the entry from config:" in text
    assert "valid again if the parent value returns to 'blocking'" in text


def test_cr_9_a_waiver_is_valid_again_when_the_parent_value_returns(tmp_path):
    root, task_dir = _waived_project(tmp_path)
    (root / "compass.yml").write_text(yaml.safe_dump(_team("advisory")), encoding="utf-8")
    assert fx.reassess(root)[0] == 0
    (root / "compass.yml").write_text(yaml.safe_dump(_team("blocking")), encoding="utf-8")
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert fx.manifest_of(task_dir)["generation"] == 3
    assert {k: v["status"] for k, v in _records(task_dir, 3).items()} == {
        "waiver:issue:checks.team-check": "valid", "EV-1": "valid"}
    assert fx.load(fx.gen(task_dir, 3) / "resolved.yml")["checks"]["team-check"][
        "severity"] == "advisory"


# --- --commit after an interrupted --reset-config ---------------------------------------------------

def test_cr_5_commit_adopts_the_folder_an_interrupted_reset_config_left(
        tmp_path, monkeypatch, capsys):
    root, task_dir = fx.committed(tmp_path)
    fx.write_manifest(task_dir, config={"stages": {"refine": {"set": {"mode": "full"}}}})
    assert fx.reassess(root)[0] == 0
    with pytest.raises(RuntimeError):
        _reassess_in_process(root, monkeypatch, capsys, boom_at="marker", reset_config=True)
    assert fx.manifest_of(task_dir)["generation"] == 2
    assert "config" in fx.manifest_of(task_dir)
    assert _states(task_dir)[3] == "complete-unreferenced"
    code, out, err = fx.configure(root, "--commit")
    assert code == 0, out + err
    body = fx.manifest_of(task_dir)
    assert body["generation"] == 3 and "config" not in body
    assert fx.load(fx.gen(task_dir, 3) / "versions.yml")["issue_overlay_digest"] is None


def test_cr_5_commit_keeps_the_reason_it_is_given(tmp_path, monkeypatch, capsys):
    root, task_dir = fx.committed(tmp_path)
    body = fx.manifest_of(task_dir)
    body["assessment"]["size"] = "large"
    fx.write_manifest(task_dir, assessment=body["assessment"])
    with pytest.raises(RuntimeError):
        _reassess_in_process(root, monkeypatch, capsys, boom_at="marker", reason=None)
    code, out, err = fx.configure(root, "--commit", "--reason", "larger than thought")
    assert code == 0, out + err
    entry = fx.manifest_of(task_dir)["reassessments"][-1]
    assert entry["reason"] == "larger than thought"
    assert entry["generation"] == {"from": 1, "to": 2}


def test_cr_5_commit_names_a_folder_that_holds_only_a_proposal(tmp_path):
    root, task_dir = _proposed_project(tmp_path)
    code, out, err = fx.configure(root, "--commit")
    assert code == 2, out + err
    assert out.strip() == "" and "holds only a proposal" in err
    assert (fx.gen(task_dir, 2) / "proposed.yml").is_file()


def test_cr_7_an_empty_proposal_drops_the_config_layer(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    fx.write_manifest(task_dir, config={"autonomy": "controlled"})
    assert fx.reassess(root)[0] == 0
    empty = tmp_path / "empty-overlay.yml"
    empty.write_text("{}\n", encoding="utf-8")
    code, out, err = fx.configure(root, "--from-file", str(empty))
    assert code == 0, out + err
    assert fx.load(fx.gen(task_dir, 3) / "proposed.yml")["overlay"] == {}
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    body = fx.manifest_of(task_dir)
    assert body["generation"] == 3 and "config" not in body
    assert fx.load(fx.gen(task_dir, 3) / "versions.yml")["issue_overlay_digest"] is None
