"""`compass check` refuses a check whose implementation major differs (ADR-038).

A generation records the version of every check implementation it uses. When
the installed major differs from the recorded one, only that check is refused:
it counts as a failure, names both versions and points to `compass issue
migrate-config`, and every other check still runs. A different major of the
resolver or of the generation schema changes the meaning of every check at
once, so it refuses the whole run.

Scenario ids: `IR-1` to `IR-5` (issue `impl-refusal`). Each test name starts
with its scenario id.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from impl_versions_support import SLUG, _run, committed, record_versions, remap_check  # noqa: E402,F401

def check_json(root):
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    return code, {c["name"]: c for c in json.loads(out)["checks"]}, json.loads(out)


# --- IR-1: only that check is refused ------------------------------------------------------

def test_ir_1_a_major_difference_refuses_only_that_check(committed):
    root, task_dir = committed
    _, before, _ = check_json(root)
    record_versions(task_dir, implementations={"suite-passed": "0.9.0"})
    _, checks, whole = check_json(root)
    assert checks["suite-passed"]["status"] == "refused"
    others = {n: (c["status"], c["detail"]) for n, c in checks.items() if n != "suite-passed"}
    assert others == {n: (c["status"], c["detail"]) for n, c in before.items()
                      if n != "suite-passed"}
    assert "fail" in {status for status, _ in others.values()}
    # A refused blocking check counts as a failure (ADR-038).
    rows = [c["status"] for c in whole["checks"] if c["name"] != "assessment-keys"]
    assert whole["failed"] >= rows.count("refused") >= 1
    assert whole["failed"] == sum(1 for c in whole["checks"] if c["status"] in ("fail", "refused"))


def test_ir_1_the_follow_up_check_is_refused_like_any_other(committed):
    root, task_dir = committed
    record_versions(task_dir, implementations={"backfills-paid": "0.1.0"})
    _, checks, whole = check_json(root)
    assert checks["backfills-paid"]["status"] == "refused"
    assert "migrate-config" in checks["backfills-paid"]["detail"]
    _run(root, "check", "--issue", SLUG)
    results = yaml.safe_load((task_dir / "generations" / "1" / "results.yml")
                             .read_text(encoding="utf-8"))["runs"]
    assert "backfills-paid" not in results


def test_ir_1_an_advisory_refused_check_is_not_counted_but_every_view_shows_it(committed):
    root, task_dir = committed
    _, _, before = check_json(root)
    record_versions(task_dir, implementations={"scenarios-are-executable": "0.1.0"})
    _, checks, whole = check_json(root)
    assert checks["scenarios-are-executable"]["status"] == "refused"
    assert whole["failed"] == before["failed"]
    for flag in ([], ["--verbose"]):
        code, out, err = _run(root, "check", "--issue", SLUG, *flag)
        assert "scenarios-are-executable" in out and "refused" in out, (flag, out)
        assert "0.1.0" in out, (flag, out)


def test_ir_1_a_check_is_refused_by_the_implementation_it_runs_not_by_its_id(committed):
    root, task_dir = committed
    remap_check(task_dir, "scenarios-have-tests", "suite-passed")
    record_versions(task_dir, implementations={"suite-passed": "0.9.0"})
    _, checks, _ = check_json(root)
    assert checks["scenarios-have-tests"]["status"] == "refused"
    assert "suite-passed" in checks["scenarios-have-tests"]["detail"]


# --- IR-2: the finding says what to do -----------------------------------------------------

def test_ir_2_the_refusal_names_both_versions_and_the_fix(committed):
    root, task_dir = committed
    record_versions(task_dir, implementations={"suite-passed": "0.9.0"})
    _, checks, _ = check_json(root)
    detail = checks["suite-passed"]["detail"]
    assert "suite-passed" in detail
    assert "0.9.0" in detail and "1.0.0" in detail
    assert f"compass issue migrate-config --issue {SLUG}" in detail
    code, out, err = _run(root, "check", "--issue", SLUG)
    assert "suite-passed" in out and "migrate-config" in out, out


# --- IR-3: the same major runs ------------------------------------------------------------

def test_ir_3_a_minor_or_patch_difference_is_not_refused(committed):
    root, task_dir = committed
    record_versions(task_dir, implementations={"suite-passed": "1.7.3"})
    _, checks, _ = check_json(root)
    assert checks["suite-passed"]["status"] == "fail"
    assert "no test-run evidence" in checks["suite-passed"]["detail"]


# --- IR-4: a schema or resolver major refuses the run -------------------------------------

@pytest.mark.parametrize("change", [{"resolver": "2.0.0"}, {"schema": 2}])
def test_ir_4_a_resolver_or_schema_major_difference_refuses_the_run(committed, change):
    root, task_dir = committed
    record_versions(task_dir, **change)
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    assert code == 2, out + err
    assert "migrate-config" in err and next(iter(change)) in err, err
    assert "checks" not in out


# --- IR-5: the JSON view and the recorded results ------------------------------------------

def test_ir_5_a_refused_check_records_no_result(committed):
    root, task_dir = committed
    record_versions(task_dir, implementations={"suite-passed": "0.9.0"})
    _run(root, "check", "--issue", SLUG)
    results = yaml.safe_load((task_dir / "generations" / "1" / "results.yml")
                             .read_text(encoding="utf-8"))["runs"]
    assert "suite-passed" not in results
    assert results["scenarios-have-tests"]["verdict"] == "fail"


def test_ir_5_the_json_row_of_a_refused_check_is_the_documented_example(committed):
    import re
    root, task_dir = committed
    record_versions(task_dir, implementations={"suite-passed": "0.9.0"})
    _, checks, _ = check_json(root)
    text = (ROOT / "docs" / "generation-store.md").read_text(encoding="utf-8")
    blocks = [json.loads(b) for b in re.findall(r"```json\n(.*?)```", text, re.S)]
    assert checks["suite-passed"] in blocks
    assert list(checks["suite-passed"]) == ["guardrail", "name", "status", "detail"]


# --- the refusal of a resolver or schema major covers `compass check` only -----------------

def test_ir_4_a_resolver_or_schema_major_bump_is_held_until_every_reader_refuses():
    """`compass check` is the only command that compares the resolver and schema
    majors. No released generation can differ yet, so that is enough for 6.0.0.
    This fails at the first bump of either major, so the limit cannot be skipped:
    extend the refusal, then change this test. `docs/generation-store.md` states
    the limit."""
    from compass_pkg import generation
    said = ("the resolver and schema refusal covers compass check only; extend it to "
            "every reader that resolves the effective view before raising this major "
            "(see docs/generation-store.md)")
    assert generation.RESOLVER_VERSION.split(".")[0] == "1", said
    assert generation.SCHEMA == 1, said
