"""Old words are read through field-scoped tables (issue
`vocabulary-and-cli-renames`, group D).

The read-side machinery lands before any table row is wired, so these tests
hand `word_map` the rows that a later increment ships (`ROWS`). Each test names
its scenario. A scenario that only the later increment can finish (a manifest
written in every old word, say) is tested there; here the machinery is proved
on the same fixtures.
"""
from __future__ import annotations

import copy
import io
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

# The rows a later increment wires into cli/migrate-map.yml.
ROWS = {
    "stage_mode": {"full": "thorough", "light": "lightweight",
                   "full-plus-backfill": "thorough-with-follow-up"},
    "artifact_depth": {"full": "thorough", "light": "lightweight"},
    "size": {"standard": "medium"},
    "issue_status": {"queued": "backlog", "parked": "backlog", "active": None,
                     "landed": "done", "abandoned": "done"},
    "close_reason": {"landed": "completed", "abandoned": "not-planned"},
    "run_stage": {"build": "implement"},
    "friction_keys": {"phase": "stage"},
}


def _word_map():
    try:
        from compass_pkg import word_map
    except ImportError:
        raise AssertionError("cli/compass_pkg/word_map.py does not exist") from None
    return word_map


class _Missing:
    """Stands in for `word_map` before it exists, so a test that needs it
    fails in its body (a red) and does not error in its setup."""

    def __getattr__(self, name):
        raise AssertionError("cli/compass_pkg/word_map.py does not exist")


@pytest.fixture
def rows(monkeypatch):
    try:
        from compass_pkg import word_map as wm
    except ImportError:
        return _Missing()
    monkeypatch.setattr(wm, "tables", lambda: copy.deepcopy(ROWS))
    return wm


def _base():
    """A parent layer in the old words: size has `standard`, modes are `light`
    and `full`."""
    import classifier_fixtures
    config = classifier_fixtures.base()
    config["dimensions"]["size"]["values"] = ["small", "standard", "large"]
    return {"schema": 1, **config}


# --- VR-D18: a value that is neither old nor new is still rejected ------------

def test_vr_d18_an_unknown_value_passes_through_the_mapping_unchanged(rows):
    doc = {"schema": 1, "stages": {"implement": {"set": {"mode": "bogus"}}},
           "checks": {"c": {"set": {"when": {"size": ["standard", "huge"]}}}}}
    mapped, changes = rows.map_layer(doc)
    assert mapped["stages"]["implement"]["set"]["mode"] == "bogus"
    assert mapped["checks"]["c"]["set"]["when"]["size"] == ["medium", "huge"]
    assert changes == [("checks.c.set.when.size", "standard", "medium")]
    assert doc["checks"]["c"]["set"]["when"]["size"] == ["standard", "huge"], (
        "map_layer must not change its input")


def test_vr_d18_a_rejected_layer_gives_the_same_finding_with_the_mapping_on(
        monkeypatch):
    from compass_pkg import layers
    from compass_pkg.core import CompassError
    wm = _word_map()
    doc = {"schema": 1, "checks": {"c": {"set": {
        "when": {"size": {"at_least": "bogus"}}}}}}

    def finding():
        with pytest.raises(CompassError) as err:
            layers.build_chain(parent=copy.deepcopy(_base()), issue=layers.Layer(
                "issue", "issue", copy.deepcopy(doc), "x"))
        return str(err.value)

    monkeypatch.setattr(wm, "tables", lambda: {})
    before = finding()
    monkeypatch.setattr(wm, "tables", lambda: copy.deepcopy(ROWS))
    assert finding() == before
    assert "bogus" in before


def test_vr_d18_a_manifest_value_that_is_neither_old_nor_new_is_left_alone(rows):
    manifest = {"stages": {"define": "bogus", "plan": "full"},
                "assessment": {"size": "huge"}, "status": "paused"}
    mapped = rows.map_manifest(copy.deepcopy(manifest))
    assert mapped["stages"] == {"define": "bogus", "plan": "thorough"}
    assert mapped["assessment"]["size"] == "huge"
    assert mapped["status"] == "paused"


# --- VR-D24: a field is mapped, a parameter that shares a name is not ---------

def test_vr_d24_a_when_condition_is_mapped_and_a_check_parameter_is_not(rows):
    doc = {"schema": 1, "checks": {"big": {
        "statement": "s", "kind": "deterministic", "impl": "suite-passed",
        "severity": "blocking", "on_skipped": "fail",
        "params": {"size": "standard"},
        "when": {"size": "standard"},
        "blocking_when": {"any_of": [{"size": {"at_least": "standard"}}]}}}}
    mapped, changes = rows.map_layer(doc)
    check = mapped["checks"]["big"]
    assert check["when"] == {"size": "medium"}
    assert check["blocking_when"] == {"any_of": [{"size": {"at_least": "medium"}}]}
    assert check["params"] == {"size": "standard"}
    assert sorted(path for path, _, _ in changes) == [
        "checks.big.blocking_when.any_of[0].size.at_least", "checks.big.when.size"]


def test_vr_d24_a_generation_file_read_on_the_way_is_not_rewritten(rows, tmp_path):
    from compass_pkg import generation
    folder = _write_generation(tmp_path)
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    stored = generation.load(str(tmp_path), 1)
    assert stored["resolved"]["checks"]["big"]["when"] == {"size": "medium"}
    assert stored["resolved"]["checks"]["big"]["params"] == {"size": "standard"}
    after = {p.name: p.read_bytes() for p in folder.iterdir()}
    assert after == before


# --- VR-D12 and VR-D13: a parent rule keyed on size standard ------------------

GATE_BY_SIZE = {"schema": 1, "gates": {"G-STD": {
    "kind": "guardrail", "stage": "verify", "applies_to": {"ships": True},
    "when": {"size": "standard"}, "checks": ["tests-pass"], "accepts": ["test-run"]}}}

ASSESSMENT = {"risk": "contained", "familiarity": "greenfield", "size": "medium",
              "labels": []}


def _resolve(*parents, layer_kind="parent"):
    from compass_pkg import layers, merge
    git = [layers.Layer(f"git-{n}", "parent", copy.deepcopy(doc), f"sha-{n}")
           for n, doc in enumerate(parents)]
    chain = layers.build_chain(parent=copy.deepcopy(_base()), extra_parents=git)
    return merge.resolve(chain)[0]


def test_vr_d12_a_parent_gate_keyed_on_size_standard_is_in_force_for_medium(rows):
    from compass_pkg import obligations
    config = _resolve(GATE_BY_SIZE)
    owed = obligations.obligations(config, dict(ASSESSMENT))
    assert "G-STD" in owed.gate_set, owed.gate_set
    small = obligations.obligations(config, {**ASSESSMENT, "size": "small"})
    assert "G-STD" not in small.gate_set


def test_vr_d13_a_parent_rule_keyed_on_size_standard_is_still_a_tightening(rows):
    from compass_pkg import classify
    base = _resolve()
    tighter = _resolve(GATE_BY_SIZE)
    old_words = classify.classify(base, tighter)
    new_words = classify.classify(base, _resolve(
        {"schema": 1, "gates": {"G-STD": {
            **GATE_BY_SIZE["gates"]["G-STD"], "when": {"size": "medium"}}}}))
    assert old_words.result == new_words.result
    assert old_words.result != "equivalent", old_words.result


# --- VR-D16: a policy-test fixture in old words -------------------------------

def test_vr_d16_a_fixture_with_size_standard_and_old_modes_passes(rows, tmp_path):
    from compass_pkg import preset_test
    folder = tmp_path / "preset"
    (folder / "compass-fixtures").mkdir(parents=True)
    (folder / "compass-fixtures" / "std.yml").write_text(yaml.safe_dump({
        "name": "standard size",
        "assessment": {"size": "standard", "risk": "contained",
                       "familiarity": "greenfield"},
        "expect": {"stages": {"define": "full", "verify": "light"}}}),
        encoding="utf-8")
    seen = {}

    def evaluate(config, capabilities, assessment):
        seen.update(assessment)
        return "runs", SimpleNamespace(
            approach="regular", gate_set=(), gate_checks={},
            stage_mode={"define": "thorough", "verify": "lightweight"})

    config = {"dimensions": {"size": {}, "risk": {}, "familiarity": {}}}
    result = preset_test._run_fixture(str(folder), "std.yml", config, (), evaluate)
    assert result.status == "pass", (result.status, result.message, result.mismatches)
    assert seen["size"] == "medium"


# --- VR-D17: digests are of the raw text; stored generations read mapped ------

def _write_generation(tmp_path):
    """Generation 1 as an older Compass wrote it: old words in `resolved`."""
    from compass_pkg import generation
    from compass_pkg.atomic_io import digest
    folder = tmp_path / "generations" / "1"
    folder.mkdir(parents=True)
    resolved = {"schema": 1, "generation": 1, "checks": {"big": {
        "params": {"size": "standard"}, "when": {"size": "standard"}}},
        "stages": {"define": {"order": 1, "modes": {"light": {"rank": 2},
                                                    "full": {"rank": 3}}}}}
    documents = {"resolved.yml": resolved,
                 "provenance.yml": {"schema": 1},
                 "versions.yml": {"schema": 1, "issue_overlay_digest": "d"},
                 "records.yml": {"schema": 1, "records": []}}
    for name, doc in documents.items():
        (folder / name).write_text(yaml.safe_dump(doc), encoding="utf-8")
    (folder / generation.MARKER).write_text(yaml.safe_dump({
        "schema": 1, "written": "2026-10-01T00:00:00Z",
        "files": {n: digest(d) for n, d in documents.items()}}), encoding="utf-8")
    return folder


def test_vr_d17_a_stored_generation_is_read_mapped_and_never_rewritten(rows, tmp_path):
    from compass_pkg import generation
    folder = _write_generation(tmp_path)
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    assert generation.is_whole(str(tmp_path), 1) == (True, ""), (
        "the marker digest is of the raw content")
    stored = generation.load(str(tmp_path), 1)
    modes = stored["resolved"]["stages"]["define"]["modes"]
    assert set(modes) == {"lightweight", "thorough"}
    fresh = copy.deepcopy(stored["resolved"])
    assert generation._same_configuration(
        stored, {"resolved.yml": fresh, "versions.yml": {"issue_overlay_digest": "d"}})
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before


def test_vr_d17_a_layer_digest_is_taken_before_the_old_words_are_mapped(
        monkeypatch, tmp_path):
    from compass_pkg import layers
    wm = _word_map()
    (tmp_path / ".compass").mkdir()
    raw = {"schema": 1, "stages": {"implement": {"set": {"modes": {
        "full": {"rank": 3}}}}}, "checks": {"c": {"set": {"when": {"size": "standard"}}}}}
    (tmp_path / "compass.yml").write_text(yaml.safe_dump(raw), encoding="utf-8")

    monkeypatch.setattr(wm, "tables", lambda: {})
    unmapped, _ = layers.load_project_layer(tmp_path)
    monkeypatch.setattr(wm, "tables", lambda: copy.deepcopy(ROWS))
    mapped, _ = layers.load_project_layer(tmp_path)

    assert mapped.digest == unmapped.digest, "the rename alone must change no digest"
    assert mapped.doc["stages"]["implement"]["set"]["modes"] == {"thorough": {"rank": 3}}
    assert unmapped.doc["stages"]["implement"]["set"]["modes"] == {"full": {"rank": 3}}
    assert mapped.doc["checks"]["c"]["set"]["when"] == {"size": "medium"}


def test_vr_d17_an_issue_layer_digest_is_taken_before_mapping(monkeypatch):
    from compass_pkg import layers
    wm = _word_map()
    manifest = {"config": {"stages": {"implement": {"set": {"mode": "full"}}}}}

    monkeypatch.setattr(wm, "tables", lambda: {})
    unmapped = layers.load_issue_layer(copy.deepcopy(manifest))
    monkeypatch.setattr(wm, "tables", lambda: copy.deepcopy(ROWS))
    mapped = layers.load_issue_layer(copy.deepcopy(manifest))
    assert mapped.digest == unmapped.digest
    assert mapped.doc["stages"]["implement"]["set"]["mode"] == "thorough"


def test_vr_d17_merge_apply_maps_a_layer_that_arrives_unmapped(rows):
    from compass_pkg import merge
    parent = rows.map_layer(_base())[0]
    child = {"schema": 1, "stages": {"verify": {"set": {"modes": {
        "full": {"rank": 3}, "light": {"rank": 2}, "reproduce-first": {}}}}}}
    config, _ = merge.apply({}, parent, "parent", "p", {})
    config, _ = merge.apply(config, child, "project", "c", {})
    assert set(config["stages"]["verify"]["modes"]) == {
        "thorough", "lightweight", "reproduce-first"}


# --- VR-D25: the reverse table ------------------------------------------------

def test_vr_d25_each_new_word_maps_back_and_forward_to_itself(rows):
    manifests = [
        {"status": "backlog", "stages": {"define": "thorough", "refine": "lightweight",
                                         "plan": "thorough-with-follow-up"},
         "artifacts": [{"depth": "lightweight"}, {"depth": "thorough"}],
         "assessment": {"size": "medium"}, "evaluated_assessment": {"size": "medium"},
         "runs": [{"stage": "implement"}], "friction": [{"stage": "plan"}]},
        {"status": "done", "close_reason": "completed"},
        {"status": "done", "close_reason": "not-planned"},
        {"stages": {}},
    ]
    for new in manifests:
        old = rows.reverse_manifest(copy.deepcopy(new))
        again = rows.map_manifest(copy.deepcopy(old))
        assert again == new, (new, old, again)
    reversed_ = rows.reverse_manifest(copy.deepcopy(manifests[0]))
    assert reversed_["stages"]["define"] == "full"
    assert reversed_["artifacts"][0]["depth"] == "light"
    assert reversed_["assessment"]["size"] == "standard"
    assert reversed_["runs"][0]["stage"] == "build"
    assert "phase" in reversed_["friction"][0]
    assert reversed_["status"] == "queued"
    assert rows.reverse_manifest({"stages": {}})["status"] == "active"
    landed = rows.reverse_manifest({"status": "done", "close_reason": "completed"})
    assert landed["status"] == "landed"


def test_vr_d25_done_with_close_reason_duplicate_returns_as_not_planned(rows):
    duplicate = {"status": "done", "close_reason": "duplicate", "duplicate_of": "x"}
    old = rows.reverse_manifest(copy.deepcopy(duplicate))
    assert old["status"] == "abandoned"
    again = rows.map_manifest(copy.deepcopy(old))
    assert (again["status"], again["close_reason"]) == ("done", "not-planned")


# --- VR-D19: the layer changes are kept for the lint advisory -----------------

def test_vr_d19_each_layer_keeps_the_changes_the_mapping_made(rows):
    from compass_pkg import layers
    chain = layers.build_chain(parent=copy.deepcopy(_base()))
    parent = chain[0]
    assert ("dimensions.size.values", "standard", "medium") in parent.changes
    lines = rows.advisory_lines(parent)
    assert any("dimensions.size.values" in line and "medium" in line
               and "7.0.0" in line for line in lines), lines


# --- VR-D21 and VR-D8: the one manifest write path ----------------------------

def _manifest_file(tmp_path, text):
    path = tmp_path / "manifest.yml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_vr_d21_the_first_write_over_old_words_keeps_one_backup_and_says_so(
        rows, tmp_path, capsys):
    from compass_pkg import core
    original = "schema_version: '2.0'\nstatus: queued\nassessment:\n  size: standard\n"
    path = _manifest_file(tmp_path, original)
    task, _ = core.load_manifest(str(tmp_path))
    assert task["assessment"]["size"] == "medium", "the loader maps on read"
    core.save_manifest(task, path)
    err = capsys.readouterr().err
    assert "standard" in err and "medium" in err and "manifest.yml.v5.bak" in err
    backup = Path(path + ".v5.bak")
    assert backup.read_text(encoding="utf-8") == original
    saved = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    assert saved["assessment"]["size"] == "medium" and saved["status"] == "backlog"
    core.save_manifest(task, path)
    assert backup.read_text(encoding="utf-8") == original, "a second save keeps the first"
    assert capsys.readouterr().err == "", "a manifest with no old word says nothing"


def test_vr_d21_a_write_that_finds_no_old_word_leaves_no_backup(
        rows, tmp_path, capsys):
    from compass_pkg import core
    path = _manifest_file(tmp_path, "schema_version: '2.0'\nstatus: backlog\n")
    task, _ = core.load_manifest(str(tmp_path))
    core.save_manifest(task, path)
    assert not Path(path + ".v5.bak").exists()
    assert capsys.readouterr().err == ""


def test_vr_d21_a_backup_ending_hides_the_file_from_manifest_readers(rows, tmp_path):
    from compass_pkg import core
    assert core.manifest_path(str(tmp_path)).endswith("manifest.yml")
    (tmp_path / "manifest.yml.v5.bak").write_text("status: queued\n", encoding="utf-8")
    assert os.path.basename(core.manifest_path(str(tmp_path))) == "manifest.yml"
    assert not "manifest.yml.v5.bak".endswith(".yml"), (
        "the ending keeps every *.yml reader away from the backup")


def test_vr_d9_every_manifest_writer_goes_through_the_one_write_path():
    """A writer that dumps a manifest without `prepare_manifest_write` would
    write old words with no backup and no notice."""
    package = ROOT / "cli" / "compass_pkg"
    needs = {"core.py": "def save_manifest", "generation.py": "atomic_write_text(path",
             "migrate.py": "safe_dump(migrated"}
    for name, marker in needs.items():
        text = (package / name).read_text(encoding="utf-8")
        assert marker in text, f"{name} no longer has {marker}"
        assert "prepare_manifest_write" in text, (
            f"{name} writes a manifest and does not call prepare_manifest_write")
    generation_text = (package / "generation.py").read_text(encoding="utf-8")
    assert generation_text.count("prepare_manifest_write(") >= 2, (
        "generation.commit writes the manifest in two places")
    migrate_text = (package / "migrate.py").read_text(encoding="utf-8")
    assert migrate_text.count("prepare_manifest_write(") >= 3, (
        "migrate.py rewrites a manifest in three places")


def test_vr_d9_generation_commit_writes_through_the_same_path(rows, tmp_path, capsys):
    """The commit writes the manifest itself; with an old word on disk it makes
    the backup too."""
    from compass_pkg import core
    path = tmp_path / "manifest.yml"
    path.write_text("schema_version: '2.0'\nstatus: parked\nparked_reason: waiting\n",
                    encoding="utf-8")
    task = core.prepare_manifest_write(
        yaml.safe_load(path.read_text(encoding="utf-8")), str(path))
    assert task["status"] == "backlog" and task["parked_reason"] == "waiting"
    assert Path(str(path) + ".v5.bak").is_file()
    assert "parked" in capsys.readouterr().err
