"""`compass check` refuses an issue whose settings or open waivers name a deleted check.

#359 step 5 (plan section 6.2, open question 14). 9.0.0 deleted checks
(`check_registry.DELETED_CHECKS`). A setting or a waiver that still names one asks
for a check that never runs, so `compass check` exits 2 with `names-deleted-check`
before it runs any row, and names each item with the command or edit that clears
it. The three cases:

- a `project_checks` entry of `compass.yml` whose `id` is a deleted check;
- a list of checks in `compass.yml` (`gates.<id>.checks`, `stages.<id>.entry` or
  `exit`) that names one;
- a waiver of the issue that is not withdrawn and names one.

A withdrawn waiver does not refuse, `compass waiver add` refuses a deleted check,
and the settings lint refuses a project check of a deleted id.

The template project of `approval_support` names the owner `jed72`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "cli"))

from approval_support import SLUG, manifest_of, project, run, save_manifest  # noqa: E402
from compass_pkg import settings_lint  # noqa: E402
from compass_pkg.check_registry import DELETED_CHECKS, REMOVED  # noqa: E402
from compass_pkg.removed_parts import READY_CHECKS  # noqa: E402

CODE = "[names-deleted-check]"
READY = "dor-summary-filled"
REMOVED_CHECK = "contracts-declared"


def _settings(root, **keys):
    path = root / "compass.yml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc.update(keys)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _waiver(root, check, waiver_id="W-1", **extra):
    body = manifest_of(root)
    body.setdefault("waivers", []).append(
        {"id": waiver_id, "check": check, "reason": "the check went in 9.0.0",
         "requested_at": "2026-11-01T00:00:00Z", "requested_by": "agent", **extra})
    save_manifest(root, body)


def _check(root):
    return run(root, "check", "--issue", SLUG)


def _refused(root):
    code, out, err = _check(root)
    assert code == 2, (code, out, err)
    assert CODE in err, err
    assert "Blocked: compass check of issue" in err, err
    assert f"then rerun compass check --issue {SLUG}." in err, err
    # Refused before any row: nothing was judged.
    assert out == "", out
    return err


def test_deleted_checks_are_the_removed_and_the_ready_checks():
    assert DELETED_CHECKS == set(REMOVED) | set(READY_CHECKS)
    assert {READY, REMOVED_CHECK, "dashboard-current"} <= DELETED_CHECKS


def test_a_project_without_one_is_not_refused(tmp_path):
    root = project(tmp_path)
    code, out, err = _check(root)
    assert CODE not in err, err
    assert code in (0, 1), (code, out, err)


@pytest.mark.parametrize("check", [READY, REMOVED_CHECK])
def test_a_project_check_of_a_deleted_id_is_refused(tmp_path, check):
    root = project(tmp_path)
    _settings(root, project_checks=[{"id": check, "name": "Old", "command": "true",
                                     "stage": "ship"}])
    err = _refused(root)
    assert f"project check {check} in compass.yml" in err, err
    assert f"delete project check {check} from compass.yml" in err, err


@pytest.mark.parametrize("catalogue, field", [("gates", "checks"), ("stages", "exit")])
def test_a_list_of_checks_in_compass_yml_that_names_one_is_refused(tmp_path, catalogue,
                                                                    field):
    root = project(tmp_path)
    _settings(root, **{catalogue: {"X1": {field: [READY]}}})
    err = _refused(root)
    assert f"{READY} in {catalogue}.X1.{field} of compass.yml" in err, err
    assert f"delete {READY} from {catalogue}.X1.{field} in compass.yml" in err, err


def test_a_change_to_a_list_of_checks_is_named_by_its_set_path(tmp_path):
    root = project(tmp_path)
    _settings(root, gates={"G2": {"set": {"checks": {"add": [REMOVED_CHECK]}}}})
    err = _refused(root)
    assert f"delete {REMOVED_CHECK} from gates.G2.set.checks in compass.yml" in err, err


def test_an_open_waiver_is_refused_and_its_fix_clears_it(tmp_path):
    root = project(tmp_path)
    _waiver(root, REMOVED_CHECK)
    err = _refused(root)
    assert f"waiver W-1 of {REMOVED_CHECK}" in err, err
    fix = f"run compass waiver withdraw W-1 --issue {SLUG}"
    assert fix in err, err
    # The fix line's command runs as written and clears the refusal.
    code, out, werr = run(root, *fix.split()[2:])
    assert code == 0, out + werr
    code, out, err = _check(root)
    assert CODE not in err, err
    assert code in (0, 1), (code, out, err)


def test_a_withdrawn_waiver_is_not_refused(tmp_path):
    root = project(tmp_path)
    _waiver(root, REMOVED_CHECK, withdrawn_at="2026-11-02T00:00:00Z")
    code, out, err = _check(root)
    assert CODE not in err, err
    assert code in (0, 1), (code, out, err)


def test_each_item_is_named_once_in_one_refusal(tmp_path):
    root = project(tmp_path)
    _settings(root, project_checks=[{"id": READY, "name": "Old", "command": "true",
                                     "stage": "ship"}])
    _waiver(root, REMOVED_CHECK)
    err = _refused(root)
    assert err.index(f"project check {READY}") < err.index("waiver W-1"), err
    assert err.count(CODE) == 1, err
    refusal = err[err.index("Blocked:"):]
    assert len(refusal.split()) < 60, refusal


def test_waiver_add_refuses_a_deleted_check(tmp_path):
    root = project(tmp_path)
    before = manifest_of(root)
    code, out, err = run(root, "waiver", "add", "--check", REMOVED_CHECK, "--reason",
                         "gone", "--issue", SLUG)
    assert code == 2, out + err
    assert "no longer has" in err and "Nothing was written" in err, err
    assert manifest_of(root) == before


@pytest.mark.parametrize("check", [READY, REMOVED_CHECK])
def test_the_settings_lint_refuses_a_project_check_of_a_deleted_id(check):
    doc = {"project_checks": [{"id": check, "name": "n", "command": "c", "stage": "ship"}]}
    found = [(f.code, f.path) for f in settings_lint.lint(doc)]
    assert ("L-SETTING-INVALID", "project_checks[0].id") in found, found
