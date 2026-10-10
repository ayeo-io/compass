"""`compass issue migrate --apply` repoints every manifest field that names a
document it moved.

The migration moves an issue's human documents from `.compass/work/<slug>/` to
`docs/compass/<created>-<slug>/`. A stopped subtask's `stopped_reason.evidence`
names a review file beside the manifest, and the migration used to leave it
naming the old place, so `multiagent-run-recorded` failed on an issue that had
passed. These tests cover that field and every other manifest field that can
hold a path to an issue document.

The scenarios are:

  * a stopped subtask keeps its stop evidence (`MRS-1`);
  * one test per field kind that names a moved file (`MRS-2`);
  * `compass check` gives the same verdict before and after (`MRS-3`);
  * an archive that an earlier release already migrated is repaired from the
    state of the tree (`MRS-4`);
  * every path-like schema field is handled or excluded with a reason
    (`MRS-5`).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPASS_CLI = ROOT / "cli" / "compass"

sys.path.insert(0, str(ROOT / "cli"))
from compass_pkg.multiagent_check import _check_multiagent_run_recorded  # noqa: E402

SLUG = "a-stopped-run"
CREATED = "2026-10-01"
MOVED = "review-1.md"
NEW_REL = f"docs/compass/{CREATED}-{SLUG}/{MOVED}"
OLD_REL = f".compass/work/{SLUG}/{MOVED}"

#: Fields that a reader measures from the project root.
FROM_PROJECT = "project root"
#: Fields that a reader measures from the issue folder.
FROM_ISSUE = "issue folder"


def _issue(tmp_path, manifest_over=None):
    """A landed multiagent issue with one stopped subtask whose stop evidence
    is a review file beside the manifest."""
    work = tmp_path / ".compass" / "work" / SLUG
    (work / "evidence").mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text(
        "version: 1.0.0\n", encoding="utf-8")
    (work / MOVED).write_text("# review\n", encoding="utf-8")
    (work / "delivery-approach.md").write_text("# approach\n", encoding="utf-8")
    (work / "devlog.md").write_text("# devlog\n", encoding="utf-8")
    manifest = {
        "schema_version": "3.0", "issue": SLUG, "created": CREATED,
        "status": "landed",
        "stages": {"breakdown": "multiagent"},
        "gates": [{"id": "verify.correctness", "status": "pass",
                   "evidence": []}],
        "artifacts": [
            {"id": "ART-DELIVERY_APPROACH", "kind": "delivery-approach",
             "status": "draft", "reason": "earned"},
            {"id": "ART-REVIEW-1", "kind": "review-1", "status": "draft",
             "reason": "earned"},
        ],
        "subtasks": [{
            "id": "subtask-1", "brief": OLD_REL, "base_sha": "a" * 40,
            "status": "reviewing", "attempts": 1,
            "stopped_reason": {"reason": "the review ceiling was reached",
                               "evidence": OLD_REL},
        }],
        "evidence": [], "scenarios": [], "changed_files": [], "claims": [],
        "follow_ups": [],
    }
    manifest.update(manifest_over or {})
    (work / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return work


def _migrate(project, *args):
    return subprocess.run(
        [sys.executable, str(COMPASS_CLI), "migrate", "--apply",
         "--i-have-a-copy", *args],
        capture_output=True, text=True, timeout=300, cwd=str(project))


def _read(work):
    return yaml.safe_load((work / "manifest.yml").read_text())


def _resolve(base, value):
    return (base / value).resolve()


def _stop_run_record(task_dir_path, manifest):
    return _check_multiagent_run_recorded(manifest, str(task_dir_path))


# --- MRS-1 -------------------------------------------------------------------

def test_mrs_1_a_stopped_subtask_still_passes_after_migration(tmp_path):
    work = _issue(tmp_path)
    passed, detail = _stop_run_record(work, _read(work))
    assert passed is True, f"the fixture must pass before migrating: {detail}"

    r = _migrate(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (work / MOVED).exists(), "the review file should have moved"

    passed, detail = _stop_run_record(work, _read(work))
    assert passed is True, (
        f"multiagent-run-recorded fails after migration: {detail}")


# --- MRS-2: one case per field kind -------------------------------------------
#
# Each case: where the field is, its anchor, and how to put a value in and
# read it back.

def _set_subtask(key):
    def put(manifest, value):
        manifest["subtasks"][0][key] = value
    return put


def _get_subtask(key):
    return lambda manifest: manifest["subtasks"][0][key]


def _put_earlier_briefs(manifest, value):
    manifest["subtasks"][0]["earlier_briefs"] = ["elsewhere.md", value]


def _put_stop(manifest, value):
    manifest["subtasks"][0]["stopped_reason"]["evidence"] = value


def _put_run_stop(manifest, value):
    manifest["runs"] = [{"n": 1, "stage": "implement", "outcome": "stopped",
                         "stopped_reason": {"reason": "stopped",
                                            "evidence": value}}]


def _put_evidence(manifest, value):
    manifest["evidence"] = [{"id": "EV-R", "type": "manual-review",
                             "path": value}]


def _put_friction(manifest, value):
    manifest["friction"] = [{"category": "other", "source": "agent",
                             "observation": "x", "evidence": value}]


FIELDS = [
    ("subtask brief", FROM_PROJECT, _set_subtask("brief"),
     _get_subtask("brief")),
    ("subtask earlier_briefs", FROM_PROJECT, _put_earlier_briefs,
     lambda m: m["subtasks"][0]["earlier_briefs"][1]),
    ("subtask report", FROM_PROJECT, _set_subtask("report"),
     _get_subtask("report")),
    ("subtask review_brief", FROM_PROJECT, _set_subtask("review_brief"),
     _get_subtask("review_brief")),
    ("subtask package", FROM_PROJECT, _set_subtask("package"),
     _get_subtask("package")),
    ("subtask stopped_reason.evidence", FROM_PROJECT, _put_stop,
     lambda m: m["subtasks"][0]["stopped_reason"]["evidence"]),
    ("run stopped_reason.evidence", FROM_PROJECT, _put_run_stop,
     lambda m: m["runs"][0]["stopped_reason"]["evidence"]),
    ("evidence path", FROM_ISSUE, _put_evidence,
     lambda m: m["evidence"][0]["path"]),
    ("friction evidence", FROM_ISSUE, _put_friction,
     lambda m: m["friction"][0]["evidence"]),
]

#: How each anchor may spell the old location.
SPELLINGS = {
    FROM_PROJECT: [OLD_REL],
    FROM_ISSUE: [MOVED, OLD_REL],
}


def _cases():
    for name, anchor, put, get in FIELDS:
        for spelling in SPELLINGS[anchor]:
            yield pytest.param(anchor, put, get, spelling,
                               id=f"{name}-{'bare' if spelling == MOVED else 'prefixed'}")


@pytest.mark.parametrize("anchor,put,get,spelling", list(_cases()))
def test_mrs_2_a_field_naming_a_moved_file_is_repointed(
        tmp_path, anchor, put, get, spelling):
    work = _issue(tmp_path)
    manifest = _read(work)
    put(manifest, spelling)
    (work / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    r = _migrate(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr

    got = get(_read(work))
    base = tmp_path if anchor == FROM_PROJECT else work
    expected = (tmp_path / NEW_REL).resolve()
    assert _resolve(base, got) == expected, (
        f"the field was {spelling!r} and is now {got!r}, which resolves to "
        f"{_resolve(base, got)} from the {anchor}, not to {expected}")


@pytest.mark.parametrize("spelling", [
    "../../../" + NEW_REL,
    NEW_REL,
])
def test_mrs_2_a_value_already_naming_the_new_home_is_left_alone(
        tmp_path, spelling):
    work = _issue(tmp_path)
    manifest = _read(work)
    _put_evidence(manifest, spelling)
    (work / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    _migrate(tmp_path)
    assert _read(work)["evidence"][0]["path"] == spelling


def test_mrs_2_a_value_that_names_a_file_that_stays_is_left_alone(tmp_path):
    work = _issue(tmp_path)
    manifest = _read(work)
    kept = f".compass/work/{SLUG}/devlog.md"
    manifest["subtasks"][0]["stopped_reason"]["evidence"] = kept
    (work / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    _migrate(tmp_path)
    assert _read(work)["subtasks"][0]["stopped_reason"]["evidence"] == kept


def test_mrs_2_the_dry_run_reports_a_repoint_it_will_make(tmp_path):
    _issue(tmp_path)
    r = subprocess.run(
        [sys.executable, str(COMPASS_CLI), "migrate"],
        capture_output=True, text=True, timeout=300, cwd=str(tmp_path))
    # The exact line, because `would move review-1.md` already names the file
    # and a loose match passes on a dry run that promises the wrong repoint.
    lines = [ln.strip() for ln in r.stdout.splitlines()]
    expected = f"would repoint the manifest fields that cite {MOVED}"
    assert any(expected in ln for ln in lines), r.stdout
    assert not any("would repoint" in ln and "delivery-approach.md" in ln
                   for ln in lines), (
        "the dry run promises a repoint for a file nothing cites:\n" + r.stdout)


# --- MRS-3 -------------------------------------------------------------------

def _verdicts(project):
    r = subprocess.run(
        [sys.executable, str(COMPASS_CLI), "check", "--issue", SLUG, "--json"],
        capture_output=True, text=True, timeout=300, cwd=str(project))
    data = json.loads(r.stdout)
    return {(c["guardrail"], c["name"]): c["status"] for c in data["checks"]}


def test_mrs_3_compass_check_gives_the_same_verdict_after_migration(tmp_path):
    work = _issue(tmp_path)
    manifest = _read(work)
    _put_evidence(manifest, OLD_REL)
    manifest["subtasks"][0]["report"] = OLD_REL
    (work / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    before = _verdicts(tmp_path)
    recorded = [v for (_g, n), v in before.items()
                if n == "multiagent-run-recorded"]
    assert recorded and recorded != ["fail"], before

    r = _migrate(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    after = _verdicts(tmp_path)

    changed = {k: (before.get(k), after.get(k))
               for k in set(before) | set(after)
               if before.get(k) != after.get(k)}
    assert not changed, f"checks that moved across the migration: {changed}"


# --- MRS-2: spellings the reader accepts ---------------------------------------

def test_mrs_2_friction_evidence_with_a_line_number_keeps_its_suffix(tmp_path):
    work = _issue(tmp_path)
    manifest = _read(work)
    _put_friction(manifest, f"{MOVED}:1")
    (work / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    _migrate(tmp_path)
    got = _read(work)["friction"][0]["evidence"]
    assert got.endswith(":1"), got
    assert _resolve(work, got[:-2]) == (tmp_path / NEW_REL).resolve(), got


def test_mrs_2_a_bare_name_in_a_project_root_field_is_read_from_the_root(
        tmp_path):
    """`review_brief: review-1.md` resolves, for its reader, to the project
    root's own file. It does not name this issue's document, so it stays."""
    work = _issue(tmp_path)
    (tmp_path / MOVED).write_text("# the project's own file\n",
                                  encoding="utf-8")
    manifest = _read(work)
    manifest["subtasks"][0]["review_brief"] = MOVED
    (work / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    _migrate(tmp_path)
    assert _read(work)["subtasks"][0]["review_brief"] == MOVED


# --- MRS-4: an archive that an earlier release already migrated --------------

def _relocated_issue(tmp_path):
    """An issue an earlier release migrated: the review file is already under
    docs/compass/ and the registry names it, but the fields still name the
    old place."""
    work = _issue(tmp_path)
    dest = tmp_path / NEW_REL
    dest.parent.mkdir(parents=True)
    os.replace(work / MOVED, dest)
    manifest = _read(work)
    for art in manifest["artifacts"]:
        if art["kind"] == "review-1":
            art["path"] = NEW_REL
    (work / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return work


@pytest.mark.parametrize("anchor,put,get,spelling", list(_cases()))
def test_mrs_4_a_stale_field_in_a_relocated_issue_is_repaired(
        tmp_path, anchor, put, get, spelling):
    work = _relocated_issue(tmp_path)
    manifest = _read(work)
    put(manifest, spelling)
    (work / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    assert not (work / MOVED).exists()

    r = _migrate(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr

    got = get(_read(work))
    base = tmp_path if anchor == FROM_PROJECT else work
    assert _resolve(base, got) == (tmp_path / NEW_REL).resolve(), (
        f"{spelling!r} was left as {got!r} in an issue whose file had "
        f"already moved")


def test_mrs_4_a_relocated_issue_passes_multiagent_run_recorded(tmp_path):
    work = _relocated_issue(tmp_path)
    passed, _detail = _stop_run_record(work, _read(work))
    assert passed is False, "the fixture must start stale"

    _migrate(tmp_path)
    passed, detail = _stop_run_record(work, _read(work))
    assert passed is True, detail


def test_mrs_4_the_dry_run_reports_the_repair_and_changes_nothing(tmp_path):
    work = _relocated_issue(tmp_path)
    before = (work / "manifest.yml").read_text()
    r = subprocess.run(
        [sys.executable, str(COMPASS_CLI), "migrate"],
        capture_output=True, text=True, timeout=300, cwd=str(tmp_path))
    expected = f"would repoint the manifest fields that cite {MOVED}"
    assert any(expected in ln for ln in r.stdout.splitlines()), r.stdout
    assert (work / "manifest.yml").read_text() == before


def test_mrs_4_a_second_run_changes_nothing(tmp_path):
    work = _relocated_issue(tmp_path)
    _migrate(tmp_path)
    once = (work / "manifest.yml").read_text()
    r = _migrate(tmp_path)
    assert (work / "manifest.yml").read_text() == once, r.stdout


def test_mrs_4_a_value_that_resolves_is_not_rewritten(tmp_path):
    """The file is at the old name and at the new home: the old name still
    resolves, so nothing is stale."""
    work = _relocated_issue(tmp_path)
    (work / MOVED).write_text("# a second copy\n", encoding="utf-8")
    manifest = _read(work)
    _put_stop(manifest, OLD_REL)
    (work / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    _migrate(tmp_path)
    assert (_read(work)["subtasks"][0]["stopped_reason"]["evidence"]
            == OLD_REL)


# --- MRS-5: no path field is forgotten -----------------------------------------

SCHEMA = ROOT / "schemas" / "manifest.schema.json"

#: A schema property is path-like when its name or description says it holds
#: a path or names a document. The match is wide on purpose: a field that is
#: caught wrongly needs an exclusion with a reason, and a field that is missed
#: is the defect this test exists to stop.
_PATHISH = ("path", "file", "folder", "directory", "brief", "evidence",
            "report", "package", "document")

#: Path-like schema fields `_reference_slots` reads, by dotted schema path.
HANDLED = {
    "subtasks[].brief",
    "subtasks[].earlier_briefs",
    "subtasks[].report",
    "subtasks[].review_brief",
    "subtasks[].package",
    "subtasks[].stopped_reason.evidence",
    "runs[].stopped_reason.evidence",
    "evidence[].path",
    "friction[].evidence",
}

#: Path-like schema fields that are not repointed, each with the reason.
EXCLUDED = {
    "schema_version": "a version string, not a path",
    "issue": "the issue slug, not a path",
    "artifacts[].kind": "a document kind, not a path",
    "artifacts[].path": "rewritten by _register as each document moves",
    "artifacts[].reason": "prose",
    "artifacts[].digest": "a digest of a document, not a path",
    "changed_files[].path": "a repository file the issue changed, not an "
                            "issue document; rewriting it would falsify history",
    "evidence[].next_task": "the schema describes it as the path to the new "
                            "issue, and every archive value is a slug; it "
                            "names an issue, not a document this migration "
                            "moves",
    "evidence[].record_id": "an identity, not a path",
    "evidence[].scenario": "a scenario id",
    "evidence[].check": "a judged check id",
    "gates[].evidence": "evidence ids, not paths",
    "landed_by[].issue": "an issue slug",
    "land_commit": "a commit id",
    "repairs": "an issue slug",
    "scenarios[].verifiable": "a scenario taxonomy label",
    "subtasks[].last_error_digest": "a digest of an error message",
}


def _stringy(node):
    if not isinstance(node, dict):
        return False
    kinds = node.get("type")
    kinds = kinds if isinstance(kinds, list) else [kinds]
    if "string" in kinds:
        return True
    items = node.get("items")
    if "array" in kinds and isinstance(items, dict) and _stringy(items):
        return True
    return any(_stringy(o) for o in node.get("oneOf", []))


def _path_like_fields(schema):
    found = []

    def walk(node, prefix):
        props = node.get("properties") if isinstance(node, dict) else None
        for name, sub in (props or {}).items():
            dotted = f"{prefix}.{name}" if prefix else name
            text = (name + " " + sub.get("description", "")).lower()
            if _stringy(sub) and "enum" not in sub \
                    and any(w in text for w in _PATHISH):
                found.append(dotted)
            walk(sub, dotted)
            items = sub.get("items")
            if isinstance(items, dict):
                walk(items, dotted + "[]")

    walk(schema, "")
    return found


def _unaccounted(schema):
    return [f for f in _path_like_fields(schema)
            if f not in HANDLED and f not in EXCLUDED]


def test_mrs_5_every_path_like_schema_field_is_handled_or_excluded():
    schema = json.loads(SCHEMA.read_text())
    assert _unaccounted(schema) == [], (
        "a schema field looks like a path to a document and is neither "
        "repointed in migrate._reference_slots nor excluded with a reason "
        "in this test")


def test_mrs_5_a_new_path_field_in_the_schema_is_reported():
    """The guard can fail: plant a field in a copy of the schema."""
    schema = json.loads(SCHEMA.read_text())
    schema["properties"]["subtasks"]["items"]["properties"]["notes_file"] = {
        "type": "string", "description": "A file the builder wrote."}
    assert _unaccounted(schema) == ["subtasks[].notes_file"]


def test_mrs_5_a_nullable_path_field_is_reported():
    """The schema also types a field `["string", "null"]`."""
    schema = json.loads(SCHEMA.read_text())
    schema["properties"]["subtasks"]["items"]["properties"]["summary"] = {
        "type": ["string", "null"], "description": "Path to the summary file."}
    assert _unaccounted(schema) == ["subtasks[].summary"]


def test_mrs_5_the_handled_list_matches_what_the_migration_reads():
    from compass_pkg.migrate import _reference_slots

    manifest = {
        "subtasks": [{"brief": "b", "earlier_briefs": ["e"], "report": "r",
                      "review_brief": "v", "package": "p",
                      "stopped_reason": {"reason": "x", "evidence": "s"}}],
        "runs": [{"stopped_reason": {"reason": "x", "evidence": "u"}}],
        "evidence": [{"path": "w"}],
        "friction": [{"evidence": "f"}],
    }
    read = sorted(c[k] for c, k, _a in _reference_slots(manifest))
    assert read == sorted("b e r v p s u w f".split())
    assert len(HANDLED) == 9, "update the manifest above with this list"
