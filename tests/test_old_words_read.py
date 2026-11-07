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
import os
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

# The rows a later increment wires into cli/migrate-map.yml.
ROWS = {
    "stage_mode": {"full": "thorough", "light": "lightweight",
                   "full-plus-backfill": "thorough-with-follow-up",
                   "swarm": "multiagent"},  # vocabulary-scan: allow - the retired breakdown mode archived manifests store (ADR-006)
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


# --- VR-D17: stored generations are read mapped ------------------------------

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


def test_vr_d22_each_rewrite_notice_names_the_issue(rows, tmp_path, capsys):
    """`issue migrate --apply` prints these for many issues in a row, so a
    line must say which issue it is about."""
    from compass_pkg import core
    issue_dir = tmp_path / "my-old-issue"
    issue_dir.mkdir()
    path = _manifest_file(issue_dir, "schema_version: '2.0'\nstatus: queued\n"
                                     "assessment:\n  size: standard\n")
    task, _ = core.load_manifest(str(issue_dir))
    core.save_manifest(task, path)
    lines = [ln for ln in capsys.readouterr().err.splitlines() if ln.startswith("compass:")]
    assert len(lines) == 2, lines
    assert all(ln.startswith("compass: my-old-issue: ") for ln in lines), lines


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

#: A project change to a path stage in the old words. A legacy stage such as
#: `implement` is not read since 9.0.0 (ADR-092), so the change is to `ship`.
OLD_PROJECT = ("schema: 1\nstages:\n  ship:\n    set:\n"
               "      modes: {full: {rank: 3}, expedited: {}, explore: {}}\n")


#: A project stage in the old words. A project's change to a legacy stage such as
#: `implement` is left out since 9.0.0 (ADR-092), so the project adds a stage of its own.
OLD_PROJECT_STAGE = ("schema: 1\nstages:\n  review:\n    order: 9\n"
                     "    modes: {full: {rank: 3}, expedited: {}, explore: {}}\n")


def test_vr_d10_a_stored_stage_mode_full_is_read_as_thorough(tmp_path):
    """Since 9.0.0 `stages:` in `compass.yml` is a removed setting (ADR-094), so a
    stage in the old words reaches an issue only from a generation stored before
    the rename; it is read in the new words."""
    import stored_generation
    from compass_pkg import effective
    root, task_dir = _project(tmp_path, compass_yml="schema: 1\n")
    code, out, err = _cli(root, "approach", "evaluate", "--issue", "t", "--write")
    assert code == 0, (out, err)
    review = yaml.safe_load(OLD_PROJECT_STAGE)["stages"]["review"]

    def add(resolved):
        resolved["stages"]["review"] = review

    stored_generation.commit(root, task_dir, add)
    modes = effective.effective_for(str(task_dir))
    assert sorted(modes.config["stages"]["review"]["modes"]) == [
        "expedited", "explore", "thorough"], modes.config["stages"]["review"]


# --- VR-D14: an issue layer in the old words ------------------------------------

def _stored_with_mode(root, task_dir, word):
    """Store generation 2 as an 8.x reassess stored it when the issue's layer set
    the mode of assess to `word`: the generation keeps the word as it was written."""
    from compass_pkg import generation
    from compass_pkg.atomic_io import digest
    stored = generation.load(str(task_dir), 1)
    body = {name: {k: v for k, v in stored[name].items()
                   if k not in ("schema", "issue", "generation")}
            for name in ("resolved", "provenance", "versions")}
    resolved = copy.deepcopy(body["resolved"])
    resolved["stages"]["assess"]["mode"] = word
    overlay = {"stages": {"assess": {"set": {"mode": word}}}}
    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    manifest["config"] = overlay
    versions = dict(body["versions"], issue_overlay_digest=digest(overlay))
    generation.commit(str(task_dir), generation.Resolution(
        resolved=resolved, provenance=body["provenance"], versions=versions), manifest)


def test_vr_d14_an_issue_layer_in_the_old_words_evaluates_as_the_new_words_do(
        tmp_path):
    """9.0.0 writes no issue layer (ADR-094), but a generation an 8.x reassess
    stored with one keeps the word it was written in, and is read in the new one."""
    results = {}
    for name, word in (("old", "full"), ("new", "thorough")):
        root, task_dir = _project(tmp_path, name)
        code, out, err = _cli(root, "approach", "evaluate", "--issue", "t", "--write")
        assert code == 0, (name, out, err)
        _stored_with_mode(root, task_dir, word)
        # A read-only evaluation applies the stored layer.
        code, out, err = _cli(root, "approach", "evaluate", "--issue", "t", "--json")
        assert code == 0, (name, out, err)
        results[name] = json.loads(out)
    assert results["old"] == results["new"]
    # ADR-092 decision: no stage modes. On the path the evaluation has no stage
    # map to carry the mode; the issue layer still records it, in the new word. The
    # issue sets assess, a stage the path keeps: a legacy stage would be left out.
    assert "stages" not in results["old"] and results["old"]["evidence_required"]
    assert results["old"]["issue_overrides"]["applied"] == {"assess": "thorough"}


# --- VR-D19: the advisory for a layer in the old words -------------------------

def test_vr_d19_policy_lint_advises_and_keeps_its_exit_status(tmp_path):
    old_root, _ = _project(tmp_path, "old", compass_yml=OLD_PROJECT)
    new_root, _ = _project(tmp_path, "new", compass_yml=OLD_PROJECT.replace("full", "thorough"))
    old = _cli(old_root, "policy", "lint")
    new = _cli(new_root, "policy", "lint")
    assert old[0] == new[0] == 0, (old, new)
    assert old[1] == new[1], "the report on standard output is the same"
    # Since 9.0.0 `stages:` is a removed setting (ADR-094) and is not read, so its
    # words need no advisory: the lint warns about the key in either spelling.
    assert "L-SETTING-REMOVED [project] stages:" in old[1], old[1]
    assert old[2] == new[2] == "", (old[2], new[2])


def test_vr_d19_compass_check_prints_no_such_advisory(tmp_path):
    root, _ = _project(tmp_path, compass_yml=OLD_PROJECT)
    code, out, err = _cli(root, "check", "--issue", "t")
    # The `Policy:` line names the check set, `compass-checks@9.0.0` (ADR-094);
    # it is not an advisory about old words.
    text = "\n".join(line for line in (out + err).splitlines()
                     if not line.strip().startswith("Policy: compass-checks@"))
    assert "7.0.0" not in text, (out, err)
    assert "8.0.0" not in text, (out, err)
    assert "9.0.0" not in text, (out, err)


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
                       "goal": "delivery", "labels": []},
        "stages": {"define": "full"}})
    new_root, _ = _project(tmp_path, "new", manifest={
        "assessment": {"risk": "contained", "familiarity": "greenfield", "size": "medium",
                       "goal": "delivery", "labels": []},
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
    # Under `stage`, only a v1-only name maps. `build` is also a stage of the
    # four-stage path (ADR-092), so an entry keyed `stage` keeps it; the v1
    # key `phase` above still reads `build` as implement.
    task, _ = _loaded(tmp_path, {"friction": [
        {"stage": "land", "category": "tooling", "source": "human", "observation": "a"},
        {"stage": "build", "category": "tooling", "source": "human", "observation": "b"}]})
    assert [f["stage"] for f in task["friction"]] == ["ship", "build"]


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
    # The template held a `friction:` example until 9.0.0 stopped writing the
    # key (ADR-093); no example may come back keyed phase.
    assert "- phase:" not in text, "an example is keyed phase"


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
