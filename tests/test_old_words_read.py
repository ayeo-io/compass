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


# Every section ships in `cli/migrate-map.yml`, and the machinery tests read
# the rows from the file. `ROWS` is the independent list the shipped rows are
# compared with (`test_the_shipped_..._rows_are_the_ones_the_tests_inject`).
SHIPPED = ("stage_mode", "artifact_depth", "size", "issue_status", "close_reason",
           "run_stage", "friction_keys")


@pytest.fixture
def rows(monkeypatch):
    try:
        from compass_pkg import word_map as wm
    except ImportError:
        return _Missing()
    shipped = wm.tables()
    handed = {name: dict(shipped[name]) for name in SHIPPED}
    monkeypatch.setattr(wm, "tables", lambda: copy.deepcopy(handed))
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


def test_vr_d25_a_backlog_hold_with_a_parked_record_returns_as_parked(rows):
    # The rollback plan promises `parked` for a hold that carries `parked_at`
    # or `parked_reason`, and `queued` for a bare backlog status.
    for held in ({"parked_at": "2026-10-01T09:00:00Z"}, {"parked_reason": "waiting"}):
        old = rows.reverse_manifest({"status": "backlog", **held})
        assert old["status"] == "parked", held
    assert rows.reverse_manifest({"status": "backlog"})["status"] == "queued"


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


def test_vr_d21_a_backup_name_that_is_a_dangling_link_is_refused(
        rows, tmp_path, capsys):
    """A repository can carry a link at `manifest.yml.v5.bak`. The backup must
    not be written through it, because the bytes are the manifest's own text."""
    from compass_pkg import core
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.txt"
    original = "schema_version: '2.0'\nstatus: queued\nassessment:\n  size: standard\n"
    path = _manifest_file(project, original)
    os.symlink(str(outside), path + ".v5.bak")
    task, _ = core.load_manifest(str(project))
    with pytest.raises(core.CompassError) as raised:
        core.save_manifest(task, path)
    assert "link" in str(raised.value)
    assert not outside.exists(), "the backup was written through the link"
    assert Path(path).read_text(encoding="utf-8") == original, "the manifest is untouched"


def test_vr_d21_the_backup_is_still_written_once_when_nothing_is_in_the_way(
        rows, tmp_path, capsys):
    from compass_pkg import core
    original = "schema_version: '2.0'\nstatus: queued\nassessment:\n  size: standard\n"
    path = _manifest_file(tmp_path, original)
    task, _ = core.load_manifest(str(tmp_path))
    core.save_manifest(task, path)
    backup = Path(path + ".v5.bak")
    assert backup.is_file() and not backup.is_symlink()
    assert backup.read_text(encoding="utf-8") == original
    core.save_manifest(task, path)
    assert backup.read_text(encoding="utf-8") == original


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


# =============================================================================
# The depth words and the size, read from the shipped tables (no injected rows)
# =============================================================================

import json
import subprocess

CLI = ROOT / "cli" / "compass"


def _cli(cwd, *argv):
    env = dict(os.environ)
    env.pop("COMPASS_ISSUE", None)
    done = subprocess.run([sys.executable, str(CLI), *argv], cwd=str(cwd), env=env,
                          capture_output=True, text=True, timeout=240)
    return done.returncode, done.stdout, done.stderr


def _project(tmp_path, name="proj", manifest=None, compass_yml=None):
    root = tmp_path / name
    task_dir = root / ".compass" / "work" / "t"
    task_dir.mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n", encoding="utf-8")
    (root / ".compass" / "current-task").write_text("t\n", encoding="utf-8")
    body = {"schema_version": "2.0", "issue": "t", "created": "2026-10-08",
            "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                           "size": "medium", "goal": "delivery", "role": "engineer",
                           "labels": []}}
    body.update(manifest or {})
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")
    if compass_yml is not None:
        (root / "compass.yml").write_text(compass_yml, encoding="utf-8")
    return root, task_dir


def test_the_shipped_depth_and_size_rows_are_the_ones_the_tests_inject():
    from compass_pkg import word_map
    shipped = word_map.tables()
    for name in SHIPPED:
        assert shipped[name] == ROWS[name], name


# --- VR-D5 and VR-D6: a manifest in the old words ------------------------------

def test_vr_d5_old_modes_and_depths_read_as_the_new_words_and_the_approach_stays(tmp_path):
    from compass_pkg import core
    (tmp_path / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": "t", "delivery_approach": "full",
        "stages": {"assess": "full", "define": "light", "ship": "full-plus-backfill",
                   "breakdown": "multiagent", "refine": "collapsed", "plan": "skipped"},
        "artifacts": [{"id": "A1", "kind": "technical-design", "depth": "full"},
                      {"id": "A2", "kind": "distribution-map", "depth": "light"}]}),
        encoding="utf-8")
    task, _ = core.load_manifest(str(tmp_path))
    assert task["stages"] == {"assess": "thorough", "define": "lightweight",
                              "ship": "thorough-with-follow-up",
                              "breakdown": "multiagent", "refine": "collapsed",
                              "plan": "skipped"}
    assert [a["depth"] for a in task["artifacts"]] == ["thorough", "lightweight"]
    assert task["delivery_approach"] == "full"


def test_vr_d6_size_standard_reads_as_medium_in_both_assessments(tmp_path):
    from compass_pkg import core
    (tmp_path / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": "t",
        "assessment": {"risk": "contained", "size": "standard"},
        "evaluated_assessment": {"risk": "contained", "size": "standard"}}),
        encoding="utf-8")
    task, _ = core.load_manifest(str(tmp_path))
    assert task["assessment"]["size"] == "medium"
    assert task["evaluated_assessment"]["size"] == "medium"


# --- VR-D10: a project layer in the old words ----------------------------------

OLD_PROJECT = ("schema: 1\nstages:\n  implement:\n    set:\n"
               "      modes: {full: {rank: 3}, expedited: {}, explore: {}}\n")


def test_vr_d10_policy_show_reads_a_project_stage_mode_full_as_thorough(tmp_path):
    root, _ = _project(tmp_path, compass_yml=OLD_PROJECT)
    code, out, err = _cli(root, "policy", "show", "--json")
    assert code == 0, (out, err)
    row = next(r for r in json.loads(out)["fields"] if r["path"] == "stages.implement.modes")
    assert sorted(row["value"]) == ["expedited", "explore", "thorough"], row
    assert row["source"] == "project" and row["op"] == "set"


# --- VR-D11, VR-D15: ranking reads both sides in the new words ------------------

def _old_parent_doc(define):
    """A parent written before the rename: it sets the regular approach's
    define stage."""
    return {"schema": 1, "approaches": {"regular": {"set": {"stages": {
        "assess": "full", "define": define, "refine": "light", "plan": "full",
        "breakdown": "multiagent", "implement": "full", "verify": "full",
        "ship": "full"}}}}}


def _classify_chain(doc):
    from compass_pkg import chain_class, layers, policy_lint
    shipped, _ = policy_lint.load_parent()
    layer = layers.Layer("git-parent#abc1234", "parent", doc,
                         layers.layer_digest(doc, "parent"))
    return chain_class.classify_chain(shipped, [layer], "compass:default@6")[0]


def _new_words(doc):
    table = {"full": "thorough", "light": "lightweight"}
    doc = copy.deepcopy(doc)
    stages = doc["approaches"]["regular"]["set"]["stages"]
    doc["approaches"]["regular"]["set"]["stages"] = {s: table.get(m, m)
                                                    for s, m in stages.items()}
    return doc


def test_vr_d11_a_parent_pinned_before_the_rename_classifies_as_its_new_words_do():
    old = _classify_chain(_old_parent_doc("light"))
    new = _classify_chain(_new_words(_old_parent_doc("light")))
    assert old["result"] == new["result"] and old["result"] != "incomparable", (old, new)
    assert old["result"] == "loosening", old["result"]
    assert old["first_looser"] is not None


PROJECT_LIGHTENS = {"schema": 1, "approaches": {"regular": {"set": {"stages": {
    "define": "lightweight", "implement": "full", "verify": "full"}}}}}


def _in_new_words(parent):
    """The parent layer with its depth words spelt the new way. Only the mode
    names and the stage weights change: `full` is also an approach name."""
    parent = copy.deepcopy(parent)
    table = {"full": "thorough", "light": "lightweight"}
    for body in parent["stages"].values():
        body["modes"] = {table.get(mode, mode): spec for mode, spec in body["modes"].items()}
    for body in parent["approaches"].values():
        body["stages"] = {stage: table.get(mode, mode) for stage, mode in body["stages"].items()}
    return parent


def _chain_classification(parent, project):
    from compass_pkg import classify, layers, merge
    above = merge.resolve(layers.build_chain(parent=copy.deepcopy(parent)))[0]
    layer = layers.Layer("project", "project", copy.deepcopy(project), "")
    below = merge.resolve(layers.build_chain(parent=copy.deepcopy(parent), project=layer))[0]
    return classify.classify(above, below)


def test_vr_d15_a_project_that_says_lightweight_is_looser_than_a_parent_that_says_full(rows):
    old_parent = _base()                    # modes light and full; every stage full
    mixed = _chain_classification(old_parent, PROJECT_LIGHTENS)
    same = _chain_classification(_in_new_words(old_parent), PROJECT_LIGHTENS)
    assert mixed.result == "loosening" == same.result, (mixed.result, same.result)


# --- VR-D14: an issue layer in the old words ------------------------------------

def test_vr_d14_an_issue_layer_in_the_old_words_evaluates_as_the_new_words_do(tmp_path):
    results = {}
    for name, word in (("old", "full"), ("new", "thorough")):
        root, task_dir = _project(tmp_path, name)
        for argv in (("approach", "evaluate", "--issue", "t", "--write"),
                     ("issue", "configure", "--issue", "t", "--mode", f"refine={word}"),
                     ("approach", "evaluate", "--issue", "t", "--write", "--reason", "wider")):
            code, out, err = _cli(root, *argv)
            assert code == 0, (name, argv, out, err)
        # The reassess stores the issue's layer; a read-only evaluation applies it.
        code, out, err = _cli(root, "approach", "evaluate", "--issue", "t", "--json")
        assert code == 0, (name, out, err)
        results[name] = json.loads(out)
    assert results["old"] == results["new"]
    assert results["old"]["stages"]["refine"] == "thorough"
    assert results["old"]["issue_overrides"]["applied"] == {"refine": "thorough"}


# --- VR-D19: the advisory for a layer in the old words -------------------------

def test_vr_d19_policy_lint_advises_and_keeps_its_exit_status(tmp_path):
    old_root, _ = _project(tmp_path, "old", compass_yml=OLD_PROJECT)
    new_root, _ = _project(tmp_path, "new", compass_yml=OLD_PROJECT.replace("full", "thorough"))
    old = _cli(old_root, "policy", "lint")
    new = _cli(new_root, "policy", "lint")
    assert old[0] == new[0] == 0, (old, new)
    assert old[1] == new[1], "the report on standard output is the same"
    assert "stages.implement.set.modes" in old[2] and "thorough" in old[2], old[2]
    assert "7.0.0" in old[2] and "project" in old[2], old[2]
    assert new[2] == "", "a layer in the new words gets no advisory"


def test_vr_d19_the_advisory_names_the_layer_and_a_git_parent_by_its_sha():
    from compass_pkg import layers, policy_lint
    shipped, _ = policy_lint.load_parent()
    doc = _old_parent_doc("light")
    git = layers.Layer("github:acme/team@1.0.0#abc1234", "parent", doc,
                       layers.layer_digest(doc, "parent"))
    report = policy_lint.lint_chain(shipped, None, extra_parents=[git])
    lines = report.advisories
    assert lines and all("github:acme/team@1.0.0#abc1234" in line for line in lines), lines
    assert any("approaches.regular.set.stages" in line and "lightweight" in line
               and "7.0.0" in line for line in lines), lines


def test_vr_d19_preset_test_advises_and_keeps_its_exit_status(tmp_path):
    results = {}
    for name, text in (("old", OLD_PROJECT),
                       ("new", OLD_PROJECT.replace("full", "thorough"))):
        folder = tmp_path / name
        (folder / "compass-fixtures").mkdir(parents=True)
        (folder / "compass.yml").write_text(text, encoding="utf-8")
        (folder / "compass-fixtures" / "one.yml").write_text(yaml.safe_dump({
            "name": "one", "assessment": {"risk": "contained", "familiarity": "greenfield",
                                          "size": "small"},
            "expect": {"approach": "regular"}}), encoding="utf-8")
        results[name] = _cli(tmp_path, "preset", "test", str(folder))
    assert results["old"][0] == results["new"][0], results
    assert "7.0.0" in results["old"][2] and "thorough" in results["old"][2], results["old"]
    assert results["new"][2] == ""


def test_vr_d19_compass_check_prints_no_such_advisory(tmp_path):
    root, _ = _project(tmp_path, compass_yml=OLD_PROJECT)
    code, out, err = _cli(root, "check", "--issue", "t")
    assert "7.0.0" not in out + err, (out, err)


# --- VR-D21: the backup, from the shipped rows ----------------------------------

def test_vr_d21_a_manifest_in_old_depth_words_is_backed_up_once_and_the_backup_is_ignored(
        tmp_path):
    from compass_pkg import core
    root, task_dir = _project(tmp_path, manifest={
        "stages": {"define": "full"}, "assessment": {"risk": "contained", "size": "standard"}})
    path = task_dir / "manifest.yml"
    original = path.read_text(encoding="utf-8")
    task, _ = core.load_manifest(str(task_dir))
    core.save_manifest(task, str(path))
    backup = task_dir / "manifest.yml.v5.bak"
    assert backup.read_text(encoding="utf-8") == original
    saved = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert saved["stages"] == {"define": "thorough"} and saved["assessment"]["size"] == "medium"
    task["stages"]["define"] = "lightweight"
    core.save_manifest(task, str(path))
    assert backup.read_text(encoding="utf-8") == original, "the second save kept the first"
    # A copy of the old file put back in place (a restore, a merge) is rewritten
    # again, and the backup of the first original is still not overwritten.
    path.write_text(original.replace("full", "light"), encoding="utf-8")
    task, _ = core.load_manifest(str(task_dir))
    core.save_manifest(task, str(path))
    assert backup.read_text(encoding="utf-8") == original, "a later rewrite kept the first backup"
    backup.write_text("stages: [this is not\n  valid: yaml\n", encoding="utf-8")
    for argv in (("issue", "lint", "--issue", "t"), ("check", "--issue", "t"),
                 ("issue", "dashboard", "render", "--issue", "t")):
        code, out, err = _cli(root, *argv)
        assert "v5.bak" not in out + err and "Traceback" not in err, (argv, out, err)


# --- VR-D22: the notice is on standard error only -------------------------------

def test_vr_d22_a_save_in_old_words_prints_the_same_json_and_a_notice_on_stderr(tmp_path):
    old_root, _ = _project(tmp_path, "old", manifest={
        "assessment": {"risk": "contained", "familiarity": "greenfield", "size": "standard",
                       "goal": "delivery", "role": "engineer", "labels": []},
        "stages": {"define": "full"}})
    new_root, _ = _project(tmp_path, "new", manifest={
        "assessment": {"risk": "contained", "familiarity": "greenfield", "size": "medium",
                       "goal": "delivery", "role": "engineer", "labels": []},
        "stages": {"define": "thorough"}})
    old = _cli(old_root, "approach", "evaluate", "--issue", "t", "--write", "--json")
    new = _cli(new_root, "approach", "evaluate", "--issue", "t", "--write", "--json")
    assert old[0] == new[0] == 0, (old, new)
    assert (old[1].replace(str(old_root.resolve()), "ROOT")
            == new[1].replace(str(new_root.resolve()), "ROOT")), "standard output is the same"
    assert "standard" in old[2] and "medium" in old[2] and "manifest.yml.v5.bak" in old[2], old[2]
    assert new[2] == "", new[2]


# --- VR-D1 to VR-D4: the status words, from the shipped rows ---------------------

def _loaded(tmp_path, manifest):
    from compass_pkg import core
    _, task_dir = _project(tmp_path, manifest=manifest)
    task, _ = core.load_manifest(str(task_dir))
    return task, task_dir


def _design():
    return {"artifacts": [{"kind": "technical-design", "path": "technical-design.md",
                           "status": "draft"}]}


def test_the_shipped_status_rows_are_the_ones_the_tests_inject():
    from compass_pkg import word_map
    shipped = word_map.tables()
    assert shipped["issue_status"] == ROWS["issue_status"]
    assert shipped["close_reason"] == ROWS["close_reason"]


@pytest.mark.parametrize("old,status,reason", [
    ("queued", "backlog", None), ("landed", "done", "completed"),
    ("abandoned", "done", "not-planned")])
def test_vr_d1_a_retired_status_reads_as_a_hold_or_a_close_with_its_reason(
        tmp_path, old, status, reason):
    task, _ = _loaded(tmp_path, {"status": old})
    assert task["status"] == status
    assert task.get("close_reason") == reason


@pytest.mark.parametrize("moved,state", [(False, "in-progress"), (True, "in-review")])
def test_vr_d2_d3_active_is_not_stored_and_the_state_follows_the_records(
        tmp_path, capsys, moved, state):
    from compass_pkg import core, lifecycle
    fields = {"status": "active", **_design(),
              "gates": [{"id": "verify.correctness", "status": "pass" if moved else "pending"}]}
    task, task_dir = _loaded(tmp_path, fields)
    assert "status" not in task
    assert lifecycle.state_of(task, str(task_dir)) == state
    capsys.readouterr()
    core.save_manifest(task, str(task_dir / "manifest.yml"))
    saved = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert "status" not in saved
    err = capsys.readouterr().err
    assert "active" in err and state in err and "records" in err, err
    assert (task_dir / "manifest.yml.v5.bak").is_file()


def test_vr_d4_parked_reads_as_a_hold_and_keeps_its_reason_and_time(tmp_path, capsys):
    from compass_pkg import core
    task, task_dir = _loaded(tmp_path, {"status": "parked", "parked_reason": "waiting",
                                        "parked_at": "2026-10-01T09:00:00Z"})
    assert task["status"] == "backlog"
    capsys.readouterr()
    core.save_manifest(task, str(task_dir / "manifest.yml"))
    saved = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert saved["status"] == "backlog"
    assert saved["parked_reason"] == "waiting" and saved["parked_at"] == "2026-10-01T09:00:00Z"
    err = capsys.readouterr().err
    assert "parked" in err and "backlog" in err, err


# --- VR-D20: old and new words in one manifest -----------------------------------

def test_vr_d20_an_explicit_close_reason_wins_over_landed_and_lint_reports_it(tmp_path):
    task, task_dir = _loaded(tmp_path, {"status": "landed", "close_reason": "not-planned"})
    assert task["status"] == "done" and task["close_reason"] == "not-planned"
    code, out, _ = _cli(tmp_path / "proj", "issue", "lint", "--issue", "t")
    assert code == 1 and "landed" in out and "not-planned" in out, out


def test_vr_d20_done_with_no_close_reason_is_not_read_as_completed(tmp_path):
    from compass_pkg import status_words
    task, _ = _loaded(tmp_path, {"status": "done"})
    assert task["status"] == "done" and "close_reason" not in task
    assert status_words.is_closed(task) and not status_words.is_completed(task)


def test_vr_d20_a_stage_key_wins_over_a_phase_key_and_the_mapping_is_idempotent(rows):
    entry = {"phase": "build", "stage": "plan", "category": "tooling", "observation": "x"}
    once = rows.map_manifest({"friction": [dict(entry)], "status": "landed"})
    assert once["friction"][0] == {"stage": "plan", "category": "tooling", "observation": "x"}
    assert rows.map_manifest(copy.deepcopy(once)) == once


def test_vr_d20_lint_reports_a_close_reason_that_contradicts_the_old_status_word(tmp_path):
    _, task_dir = _loaded(tmp_path, {"status": "abandoned", "close_reason": "completed"})
    code, out, _ = _cli(tmp_path / "proj", "issue", "lint", "--issue", "t")
    assert code == 1 and "abandoned" in out and "completed" in out, out


def test_vr_d20_lint_reports_a_duplicate_of_without_the_duplicate_reason(tmp_path):
    _loaded(tmp_path, {"status": "done", "close_reason": "completed", "duplicate_of": "other"})
    code, out, _ = _cli(tmp_path / "proj", "issue", "lint", "--issue", "t")
    assert code == 1 and "duplicate_of" in out, out


# --- VR-D23: the schema stamp ----------------------------------------------------

def test_vr_d23_a_save_stamps_schema_version_3_0(tmp_path):
    from compass_pkg import core
    task, task_dir = _loaded(tmp_path, {})
    core.save_manifest(task, str(task_dir / "manifest.yml"))
    saved = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert saved["schema_version"] == "3.0"


@pytest.mark.parametrize("version,accepted", [("1.0", True), ("2.0", True), ("3.0", True),
                                              ("4.0", False)])
def test_vr_d23_the_reader_accepts_majors_1_to_3_and_refuses_4(tmp_path, version, accepted):
    from compass_pkg import core
    _, task_dir = _project(tmp_path, manifest={"schema_version": version})
    if accepted:
        core.load_manifest(str(task_dir))
        return
    with pytest.raises(core.CompassError) as caught:
        core.load_manifest(str(task_dir))
    assert "Update Compass" in str(caught.value)


def test_vr_d23_a_stamped_manifest_is_not_reported_as_legacy_by_the_receipt():
    from compass_pkg import receipt
    text = receipt._receipt_render({"issue": "t", "schema_version": "3.0"}, "t", {})
    assert "(legacy)" not in text.splitlines()[1]


# --- VR-D7 and VR-D8: the run stage and the friction key, from the shipped rows ---

def test_the_shipped_run_stage_and_friction_rows_are_the_ones_the_tests_inject():
    from compass_pkg import word_map
    shipped = word_map.tables()
    assert {name: shipped[name] for name in SHIPPED} == ROWS


def test_vr_d7_a_run_at_stage_build_and_friction_keyed_phase_read_as_implement_and_stage(
        tmp_path):
    task, _ = _loaded(tmp_path, {
        "runs": [{"n": 1, "stage": "build", "outcome": "done"},
                 {"n": 2, "stage": "verify", "outcome": "stopped"}],
        "friction": [
            {"phase": "build", "category": "tooling", "source": "human", "observation": "a"},
            {"phase": "plan", "category": "docs", "source": "human", "observation": "b"}]})
    assert [r["stage"] for r in task["runs"]] == ["implement", "verify"]
    assert [f["stage"] for f in task["friction"]] == ["implement", "plan"]
    assert all("phase" not in f for f in task["friction"]), task["friction"]


def test_vr_d7_a_friction_entry_already_keyed_stage_keeps_its_stage_mapped(tmp_path):
    task, _ = _loaded(tmp_path, {"friction": [
        {"stage": "build", "category": "tooling", "source": "human", "observation": "a"}]})
    assert task["friction"][0]["stage"] == "implement"


EVERY_OLD_WORD = {
    "status": "landed",
    "stages": {"define": "full", "refine": "light", "ship": "full-plus-backfill"},
    "artifacts": [{"id": "A1", "kind": "technical-design", "depth": "full"}],
    "assessment": {"risk": "contained", "familiarity": "greenfield", "size": "standard",
                   "goal": "delivery", "role": "engineer", "labels": []},
    "evaluated_assessment": {"risk": "contained", "size": "standard"},
    "runs": [{"n": 1, "stage": "build", "outcome": "done"}],
    "friction": [{"phase": "build", "category": "tooling", "source": "human",
                  "observation": "a"}],
}


def test_vr_d8_a_save_over_a_manifest_in_every_old_word_writes_none_and_keeps_the_original(
        tmp_path, capsys):
    from compass_pkg import core, word_map
    task, task_dir = _loaded(tmp_path, copy.deepcopy(EVERY_OLD_WORD))
    path = task_dir / "manifest.yml"
    original = path.read_text(encoding="utf-8")
    assert {field for field, _, _ in word_map.old_words(yaml.safe_load(original))} >= {
        "status", "runs[0].stage", "friction[0].phase", "assessment.size"}
    capsys.readouterr()
    core.save_manifest(task, str(path))
    saved = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert word_map.old_words(saved) == [], word_map.old_words(saved)
    assert saved["runs"][0]["stage"] == "implement"
    assert saved["friction"][0] == {"stage": "implement", "category": "tooling",
                                    "source": "human", "observation": "a"}
    assert (task_dir / "manifest.yml.v5.bak").read_text(encoding="utf-8") == original
    err = capsys.readouterr().err
    assert "build" in err and "implement" in err and "phase" in err and "stage" in err, err


# --- VR-D9: each writer leaves no old word in a fresh project --------------------

def _git(cwd, *argv):
    done = subprocess.run(["git", *argv], cwd=str(cwd), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


def _no_old_word(path):
    from compass_pkg import word_map
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return word_map.old_words(raw)


def test_vr_d9_the_manifest_template_holds_no_old_word():
    from compass_pkg import word_map
    text = (ROOT / "templates" / "manifest.yml").read_text(encoding="utf-8")
    assert word_map.old_words(yaml.safe_load(text)) == []
    assert "- phase:" not in text, "the friction example is keyed phase"
    assert "- stage:" in text, "the friction example shows the stage key"


def test_vr_d9_no_script_writes_a_manifest_literal_in_an_old_word():
    """A script that holds a manifest as text writes it as it is, so an old
    word in the text is an old word on disk."""
    import re
    old = re.compile(r"^\s*(?:status: (?:active|queued|parked|landed|abandoned)"
                     r"|size: standard|phase: \w+)\s*$", re.M)
    found = []
    for path in sorted((ROOT / "scripts").glob("*")):
        if path.suffix not in (".py", ".sh") or not path.is_file():
            continue
        for match in old.finditer(path.read_text(encoding="utf-8")):
            found.append(f"{path.name}: {match.group(0).strip()}")
    assert not found, found


def test_vr_d9_the_scan_for_a_manifest_literal_finds_a_planted_word():
    import re
    old = re.compile(r"^\s*(?:status: (?:active|queued|parked|landed|abandoned)"
                     r"|size: standard|phase: \w+)\s*$", re.M)
    assert old.search("issue: x\nstatus: active\nassessment:\n")
    assert not old.search("issue: x\nstatus: backlog\n  size: medium\n")


def test_vr_d9_friction_and_capture_write_the_new_keys(tmp_path):
    root, task_dir = _project(tmp_path)
    (task_dir / "evidence").mkdir()
    (task_dir / "evidence" / "red.log").write_text("1 failed\n", encoding="utf-8")
    note = _cli(root, "issue", "friction", "--issue", "t", "--category", "tooling",
                "--stage", "implement", "--observed", "evidence/red.log",
                "--fix", "Run the suite once")
    assert note[0] == 0, note
    after_note = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert [e["stage"] for e in after_note["friction"]] == ["implement"], after_note
    assert _no_old_word(task_dir / "manifest.yml") == []
    capture = _cli(root, "_friction-capture", "--internal", "--issue", "t",
                   "--note", "slow", "--note-category", "tooling", "--note-stage", "ship")
    assert capture[0] == 0, capture
    saved = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert {e["source"] for e in saved["friction"]} == {"agent", "human"}
    for entry in saved["friction"]:
        assert "phase" not in entry and "stage" in entry, entry
    assert _no_old_word(task_dir / "manifest.yml") == []
    assert not (task_dir / "manifest.yml.v5.bak").exists(), "nothing old was on disk"


def test_vr_d9_a_quick_fix_start_writes_no_old_word(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    started = _cli(repo, "quick-fix", "start", "fresh-fix",
                   "--risk", "trivial - a one-line text change",
                   "--familiarity", "brownfield-mapped - the file and its test already exist",
                   "--size", "atomic - one file, one obvious change",
                   "--intent", "A quick fix ships with the same three gates.",
                   "--scenario", "Given the greeting, when it is read, then it says hello.",
                   "--scenario-id", "TRC-001",
                   "--test", "tests/test_greeting.py::test_greeting_says_hello")
    assert started[0] == 0, started
    manifest = repo / ".compass" / "work" / "fresh-fix" / "manifest.yml"
    assert _no_old_word(manifest) == []
    saved = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    assert "status" not in saved, "work in flight stores no status"
    assert not (manifest.parent / "manifest.yml.v5.bak").exists()
