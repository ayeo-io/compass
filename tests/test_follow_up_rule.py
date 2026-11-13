"""The one follow-up rule of a path issue, and the older rules an old issue keeps
(ADR-093 decisions 9 and 10).

On a path issue (a manifest with `evidence_required`, ADR-092) an open
Definition of Done item is met only by a follow-up that links to a GitHub
issue. `compass follow-up add` needs `--github` there, `--defers` names an item
of the build exit list, and the check that owed follow-ups are resolved has
nothing to check, because the linked issue tracks the work.

An issue assessed before 9.0.0 keeps every rule it had: an outstanding
follow-up carries an item to ship, the check that owed follow-ups are resolved
fails until `compass follow-up resolve` resolves it, a `target_task` entry
blocks the issue it names, and a page tag resolves against the follow-ups.

The path tests drive `cli/compass` in a temporary git repository
(`rendered_blocks_support`); the old-issue tests call the readers on a
manifest, as the archive holds them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

import rendered_blocks_support as sup
from rendered_blocks_support import SLUG, manifest, manifest_file, run

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_dod_from_manifest import ITEMS, ON, _issue, _record_all, _row  # noqa: E402
from test_path_checks import _old_task, _path_task  # noqa: E402

from compass_pkg import checks, item_records  # noqa: E402
from compass_pkg.check_results import NOTHING_TO_CHECK  # noqa: E402

LINK = "ayeo-io/compass#9"
#: The item each path test carries to a follow-up.
CARRIED = "dod-living-docs-updated"


def _ok(result):
    code, out, err = result
    assert code == 0, out + err
    return out


def _refused(root, *argv):
    """The output of a `follow-up add` that exits 2 and leaves the manifest as it was."""
    before = manifest_file(root).read_bytes()
    code, out, err = run(root, "follow-up", "add", *argv, "--issue", SLUG)
    assert code == 2, out + err
    assert manifest_file(root).read_bytes() == before
    return out + err


def _path_issue(tmp_path, layer=None):
    """A path issue whose gates have passed and whose Definition of Done items are
    all recorded except `CARRIED`. With `layer=ON` the stage lists run too."""
    root = _issue(tmp_path, layer=layer, gates_passed=True)
    assert "evidence_required" in manifest(root)
    _record_all(root, skip=(CARRIED,))
    return root


def _write_follow_up(root, **entry):
    """A follow-up written to the manifest as it is on disk, with no command, the
    way an earlier `follow-up add` left one."""
    body = manifest(root)
    body.setdefault("follow_ups", []).append(
        {"id": "FU-7", "status": "outstanding", "summary": "later", "defers": CARRIED, **entry})
    sup.base.write_manifest(root, body)


def _check(root):
    code, out, err = run(root, "check", "--issue", SLUG, "--json")
    return json.loads(out)


# --- a path issue -------------------------------------------------------------------

def test_a_linked_follow_up_meets_an_open_definition_of_done_item(tmp_path):
    root = _path_issue(tmp_path, layer=ON)
    sup.base.edit(root, current_phase="ship")
    _ok(run(root, "follow-up", "add", "FU-7", "--defers", CARRIED, "--github", LINK,
            "--summary", "Update the living docs", "--issue", SLUG))
    entry = manifest(root)["follow_ups"][-1]
    assert entry["github"] == {"repo": "ayeo-io/compass", "number": 9}, entry
    assert entry["status"] == "outstanding", entry
    report = _check(root)
    row = _row(report, "dod-evidence-typed")
    assert row["status"] == "pass", row
    listed = {c["name"]: c for c in report["checks"] if c["guardrail"] == "stage:build:exit"}
    assert listed[CARRIED]["status"] == "pass", listed[CARRIED]
    assert "GitHub issue" in listed[CARRIED]["detail"], listed[CARRIED]


def test_an_unlinked_follow_up_meets_nothing_and_the_hint_names_the_command(tmp_path):
    root = _path_issue(tmp_path)
    _write_follow_up(root)
    row = _row(_check(root), "dod-evidence-typed")
    assert row["status"] == "fail", row
    assert f"{CARRIED} is open" in row["detail"], row
    assert "--github owner/repo#N" in row["detail"], row
    assert "FU-7" in row["detail"] and "links to no GitHub issue" in row["detail"], row


def test_a_follow_up_whose_link_was_edited_out_of_shape_meets_nothing(tmp_path):
    root = _path_issue(tmp_path)
    _write_follow_up(root, github={"repo": "not a repo", "number": 9})
    assert _row(_check(root), "dod-evidence-typed")["status"] == "fail"


def test_github_is_required_on_a_path_issue(tmp_path):
    root = _path_issue(tmp_path)
    text = _refused(root, "FU-7", "--defers", CARRIED, "--summary", "later")
    assert "--github owner/repo#number" in text, text
    text = _refused(root, "FU-8", "--summary", "later")
    assert "--github" in text, text


def test_github_is_parsed_as_issue_link_set_parses_it(tmp_path):
    root = _path_issue(tmp_path)
    text = _refused(root, "FU-7", "--defers", CARRIED, "--github", "compass#9",
                    "--summary", "later")
    assert "is not a GitHub issue" in text, text
    _ok(run(root, "follow-up", "add", "FU-7", "--defers", CARRIED, "--github",
            "https://github.com/ayeo-io/compass-delivery/issues/354", "--summary", "later",
            "--issue", SLUG))
    assert manifest(root)["follow_ups"][-1]["github"] == {"repo": "ayeo-io/compass-delivery",
                                                         "number": 354}


def test_defers_names_an_item_of_the_build_exit_list(tmp_path):
    root = _path_issue(tmp_path)
    text = _refused(root, "FU-7", "--defers", "dor-summary-filled", "--github", LINK,
                    "--summary", "later")
    assert "dor-summary-filled" in text and "build exit list" in text, text
    assert all(item in text for item in ITEMS), text


def test_backfills_paid_has_nothing_to_check_on_a_path_issue(tmp_path):
    root = _path_issue(tmp_path)
    _ok(run(root, "follow-up", "add", "FU-7", "--defers", CARRIED, "--github", LINK,
            "--summary", "later", "--issue", SLUG))
    row = _row(_check(root), "backfills-paid")
    assert row["status"] == "nothing-to-check", row
    passed, detail = checks._check_backfills_paid(
        _path_task(follow_ups=[{"id": "FU-1", "status": "outstanding"}]), "")
    assert passed is NOTHING_TO_CHECK, detail


def test_target_is_removed_with_a_line_naming_adr_093(tmp_path):
    root = _path_issue(tmp_path)
    before = manifest_file(root).read_bytes()
    code, out, err = run(root, "follow-up", "add", "FU-7", "--github", LINK, "--summary",
                         "later", "--target", "other", "--issue", SLUG)
    assert code == 2, out + err
    assert "'compass follow-up add --target' was removed in 9.0.0 (ADR-093)" in err, err
    assert "--github" in err, err
    assert manifest_file(root).read_bytes() == before


def test_the_manifest_schema_takes_a_follow_up_link():
    import jsonschema
    schema = json.loads((sup.ROOT / "schemas" / "manifest.schema.json").read_text("utf-8"))
    item = schema["properties"]["follow_ups"]["items"]
    good = {"id": "FU-1", "status": "outstanding", "github": {"repo": "o/r", "number": 3}}
    jsonschema.validate(good, item)
    bad = dict(good, github={"repo": "o/r"})
    assert list(jsonschema.Draft202012Validator(item).iter_errors(bad))


# --- an issue assessed before 9.0.0 ----------------------------------------------------

def _old(**follow_up):
    return _old_task(follow_ups=[{"id": "FU-1", "status": "outstanding",
                                  "defers": CARRIED, **follow_up}])


def test_an_old_follow_up_carries_its_item_to_ship_without_a_link():
    accepted = item_records.accepted_types()
    assert item_records.state_of(_old(), CARRIED, accepted) == (item_records.CARRIED, ("FU-1",))
    assert item_records.state_of(_old(status="resolved"), CARRIED, accepted) == (
        item_records.MET_CARRIED, ("FU-1",))


def test_an_old_open_item_keeps_its_hint():
    hint = item_records.open_hint(CARRIED, _old_task())
    assert hint == item_records.open_hint(CARRIED)
    assert "--github" not in hint and f"--defers {CARRIED}" in hint, hint


def test_backfills_paid_still_fails_an_old_issue_until_it_is_resolved():
    passed, detail = checks._check_backfills_paid(_old(), "")
    assert passed is False and "FU-1" in detail, detail
    passed, detail = checks._check_backfills_paid(_old(github={"repo": "o/r", "number": 1}), "")
    assert passed is False, detail
    passed, detail = checks._check_backfills_paid(_old(status="resolved"), "")
    assert passed is True, detail


def test_a_target_task_still_blocks_the_issue_it_names(tmp_path):
    work = tmp_path / ".compass" / "work"
    for slug, body in (("older", _old(target_task="shipping")), ("shipping", _old_task())):
        (work / slug).mkdir(parents=True)
        (work / slug / "manifest.yml").write_text(yaml.safe_dump(dict(body, issue=slug)),
                                                  encoding="utf-8")
    problems = checks._check_inbound_backfills(str(work / "shipping"), "shipping")
    assert len(problems) == 1 and "compass follow-up resolve --issue older FU-1" in problems[0]


def test_a_page_tag_still_resolves_against_the_follow_ups():
    assert checks.dod_tag_problems("(follow-up: FU-1) docs", {},
                                   {"FU-1": {"status": "outstanding"}}) == []
    assert checks.dod_tag_problems("(follow-up: FU-2) docs", {}, {})


def test_an_old_issue_records_a_follow_up_without_a_link_and_resolves_it(tmp_path):
    root = sup.project(tmp_path, evaluate=False)
    sup.base.write_manifest(root, dict(_old_task(), issue=SLUG))
    _ok(run(root, "follow-up", "add", "FU-1", "--defers", CARRIED, "--summary", "later",
            "--issue", SLUG))
    entry = manifest(root)["follow_ups"][-1]
    assert "github" not in entry and entry["defers"] == CARRIED, entry
    assert _row(_check(root), "backfills-paid")["status"] == "fail"
    _ok(run(root, "follow-up", "resolve", "--issue", SLUG, "FU-1"))
    assert manifest(root)["follow_ups"][-1]["status"] == "resolved"
    assert _row(_check(root), "backfills-paid")["status"] == "pass"
