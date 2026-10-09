"""`compass issue migrate --apply` repoints every manifest field that names a
document it moved.

The migration moves an issue's human documents from `.compass/work/<slug>/` to
`docs/compass/<created>-<slug>/`. A stopped subtask's `stopped_reason.evidence`
names a review file beside the manifest, and the migration used to leave it
naming the old place, so `multiagent-run-recorded` failed on an issue that had
passed. These tests cover that field and every other manifest field that can
hold a path to an issue document.

Scenarios `MRS-1` (a stopped subtask), `MRS-2` (one test per field kind) and
`MRS-3` (`compass check` gives the same verdict before and after).
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
    assert "repoint" in r.stdout and MOVED in r.stdout, r.stdout


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
