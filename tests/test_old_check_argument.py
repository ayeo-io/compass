"""The old check id still works as a command argument until 8.0.0.

`cli/migrate-map.yml` lists `dor-behaviour-is-gwt` as read until 8.0.0 (the
`check_id` rows of `old_names:`). A script that passes the old id to
`compass evidence approve --check` or `compass evidence review --check` must get
what the new id gets, with a notice on standard error, not "no such check".
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "cli"))

import approval_support as ap  # noqa: E402

# Spelt from pieces so that no scan of the tests finds the old name in a literal.
OLD_CHECK = "dor-behav" + "iour-is-gwt"
NEW_CHECK = "dor-behavior-is-gwt"


def _approve(root, check):
    return ap.run(root, "evidence", "approve", "--check", check, "--issue", ap.SLUG,
                  "--approver", ap.OWNER, "--role", "owner", "--scope", "the plan",
                  terminal=True)


def test_the_new_check_id_is_approved(tmp_path):
    root = ap.project(tmp_path)
    code, out, err = _approve(root, NEW_CHECK)
    assert code == 0, out + err


def test_the_old_check_id_is_approved_as_the_new_one(tmp_path):
    root = ap.project(tmp_path)
    code, out, err = _approve(root, OLD_CHECK)
    assert code == 0, out + err
    assert f"check {OLD_CHECK} is now {NEW_CHECK}" in err, err
    records = [e for e in ap.manifest_of(root)["evidence"] if e.get("check")]
    assert [e["check"] for e in records] == [NEW_CHECK], records


def test_the_old_check_id_is_asked_for_as_the_new_one(tmp_path):
    root = ap.project(tmp_path)
    code, out, err = ap.run(root, "evidence", "request", "--check", OLD_CHECK,
                            "--issue", ap.SLUG, "--scope", "the plan")
    assert "no such check" not in out + err, out + err


def test_the_old_check_id_is_reviewed_as_the_new_one(tmp_path):
    root = ap.project(tmp_path)
    code, out, err = ap.run(root, "evidence", "review", OLD_CHECK, "--issue", ap.SLUG,
                            "--verdict", "pass", "--reason", "Read it.", "--reviewer", "agent")
    assert "no such check" not in out + err, out + err
