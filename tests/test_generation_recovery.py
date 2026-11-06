"""A reassess interrupted after each step of its commit, and the generation a
reassessment records it moved from and to.

Scenario ids: `CR-6` and `CR-8` (issue `configure-and-reassess`). Each test
name starts with its scenario id. Crash injection replaces the single
module-level hook `generation._after_step`, as the store's own tests do;
product code has no switch for it. 9.0.0 has no issue layer (ADR-094), so a
reassess commits a new generation here because the assessment changed.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import reassess_fixtures as fx  # noqa: E402

STEPS = ("resolved", "provenance", "versions", "records", "marker", "manifest")

#: A size whose evidence differs from the fixture's. On the path a medium and a
#: large change owe the same evidence (ADR-092 decision 3), so a reassessment
#: that must commit a new generation moves the size to small, the light row.
SMALLER = "small"


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
    from conftest import needed_justifications
    fields = dict(reading=None, task=fx.SLUG, write=True, reason="test", kind=None,
                  _mode=None, evidence_out=None, json=False,
                  justify=needed_justifications(root / ".compass" / "work" / fx.SLUG))
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


def _changed_project(tmp_path):
    """An issue at generation 1 whose assessment changed since, so the next
    reassess commits generation 2."""
    root, task_dir = fx.committed(tmp_path)
    body = fx.manifest_of(task_dir)
    body["assessment"]["size"] = SMALLER
    fx.write_manifest(task_dir, assessment=body["assessment"])
    return root, task_dir


def _interrupted(tmp_path, monkeypatch, capsys, step):
    root, task_dir = _changed_project(tmp_path)
    before = (task_dir / "manifest.yml").read_bytes()
    with pytest.raises(RuntimeError, match=step):
        _reassess_in_process(root, monkeypatch, capsys, boom_at=step)
    return root, task_dir, before


# --- CR-6: a reassess interrupted after each step ---------------------------------------------

@pytest.mark.parametrize("step", STEPS)
def test_cr_6_the_manifest_names_the_previous_generation_until_its_replace(
        tmp_path, monkeypatch, capsys, step):
    root, task_dir, before = _interrupted(tmp_path, monkeypatch, capsys, step)
    body = fx.manifest_of(task_dir)
    if step == "manifest":
        assert body["generation"] == 2
        assert _states(task_dir)[2] == "current"
    else:
        assert (task_dir / "manifest.yml").read_bytes() == before
        assert body["generation"] == 1
        assert _states(task_dir)[2] == (
            "complete-unreferenced" if step == "marker" else "incomplete")
    assert fx.load(fx.gen(task_dir, 1) / "resolved.yml")["generation"] == 1


@pytest.mark.parametrize("step", ["resolved", "provenance", "versions", "records", "marker"])
def test_cr_6_the_next_reassess_writes_the_leftover_folder_again(
        tmp_path, monkeypatch, capsys, step):
    """An incomplete folder, and a complete one the manifest does not name, hold
    only files a commit writes, so the next reassess writes them again."""
    root, task_dir, _ = _interrupted(tmp_path, monkeypatch, capsys, step)
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert "committed generation 2" in out
    assert fx.manifest_of(task_dir)["generation"] == 2
    assert _states(task_dir) == {1: "superseded", 2: "current"}


def test_cr_6_a_leftover_folder_with_a_file_a_commit_does_not_write_is_kept(
        tmp_path, monkeypatch, capsys):
    root, task_dir, before = _interrupted(tmp_path, monkeypatch, capsys, "marker")
    (fx.gen(task_dir, 2) / "notes.md").write_text("mine\n", encoding="utf-8")
    snapshot = _snapshot(root)
    code, out, err = fx.reassess(root)
    assert code == 2, out + err
    assert "notes.md" in err and ".compass/work/feature/generations/2" in err
    assert "compass issue configure" not in out + err
    assert _snapshot(root) == snapshot


def test_cr_6_after_the_manifest_replace_the_new_generation_is_in_force(
        tmp_path, monkeypatch, capsys):
    root, task_dir, _ = _interrupted(tmp_path, monkeypatch, capsys, "manifest")
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert "no change" in out
    assert fx.manifest_of(task_dir)["generation"] == 2


# --- a refusal never follows a printed result -------------------------------------------------

def test_cr_6_a_landed_issue_is_refused_before_anything_prints(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    # The project's configuration changed, so the commit would store a new
    # generation, which a closed issue refuses.
    (root / "compass.yml").write_text("schema: 1\nautonomy: controlled\n", encoding="utf-8")
    fx.write_manifest(task_dir, status="landed")
    code, out, err = fx.reassess(root)
    assert code == 2, out + err
    assert out.strip() == "" and "is closed and keeps" in err


# --- CR-8: the generation a reassessment moved from and to ----------------------------------------

def test_cr_8_a_reassessment_records_the_generation_it_moved_from_and_to(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    body = fx.manifest_of(task_dir)
    body["assessment"]["size"] = SMALLER
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


def test_cr_8_the_schema_and_the_cli_list_the_configuration_kind():
    import json
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    kinds = schema["properties"]["reassessments"]["items"]["properties"]["kind"]["enum"]
    # The old spelling stays in the enum until 8.0.0, so an archived manifest still validates.
    assert kinds == ["judgment", "judgement", "policy-correction", "scope-change",  # us-english-scan: allow - old name read until 8.0.0
                     "configuration", "unchanged"]
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
