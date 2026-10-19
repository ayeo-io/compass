"""Refuse a check, or a whole command, built for another major (ADR-038).

A generation records the version of every check implementation it uses, the
resolver that built it and the schema of its files. When the installed major of
one implementation differs from the recorded one, `compass check` refuses only
that check: it counts as a failure, names both versions and points to `compass
issue migrate --config`, and every other check still runs. A different major of
the resolver or of the schema changes the meaning of every check at once, so
every command that reads the issue's generation refuses, and the repair
commands still run.

Scenario ids: `IR-1` to `IR-5` (issue `impl-refusal`), and `IR-13` and `IR-14`
(issue `refuse-on-major-version-mismatch`). Each test name starts with its
scenario id."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from impl_versions_support import (MANIFEST, SLUG, _run, committed, record_versions,  # noqa: E402,F401
                                   remap_check)

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
    assert "migrate --config" in checks["backfills-paid"]["detail"]
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
        assert "ADVISORY" in out, (flag, out)
        if flag:
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
    assert f"compass issue migrate --config --issue {SLUG}" in detail
    code, out, err = _run(root, "check", "--issue", SLUG)
    assert "suite-passed" in out and "migrate --config" in out, out


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
    assert "migrate --config" in err and next(iter(change)) in err, err
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


# --- IR-13: every command that reads the issue refuses -------------------------------------

#: Commands that refuse an issue whose generation was built by another resolver or schema
#: major: the stage view, the rendered documents (read through a reader that falls back
#: on any fault), the lint, the receipt, the reassess, and the red and green records.
#: `compass check` refuses in the same way, and IR-4 tests it.
READERS = (
    ("next", "--issue", SLUG),
    ("issue", "render", "--issue", SLUG),
    ("issue", "lint", "--issue", SLUG),
    ("issue", "receipt", "--issue", SLUG),
    ("approach", "evaluate", "--issue", SLUG, "--write"),
    ("tdd-red", "--issue", SLUG, "--", "false"),
    ("tdd-green", "--issue", SLUG, "--", "true"),
)
CHANGES = [{"resolver": "2.0.0"}, {"schema": 2}]


def with_approach(root):
    """Give the fixture issue a delivery approach, so `compass next` reaches the
    generation instead of stopping at the missing record."""
    folder = root / ".compass" / "work" / SLUG
    (folder / "delivery-approach.md").write_text("# Delivery approach\n", encoding="utf-8")


@pytest.mark.parametrize("change", CHANGES, ids=["resolver", "schema"])
@pytest.mark.parametrize("argv", READERS, ids=[" ".join(a[:2]) for a in READERS])
def test_ir_13_every_command_that_reads_the_issue_refuses(committed, change, argv):
    root, task_dir = committed
    with_approach(root)
    record_versions(task_dir, **change)
    before = (task_dir / "manifest.yml").read_text(encoding="utf-8")
    code, out, err = _run(root, *argv)
    assert code == 2, (argv, code, out + err)
    what, value = next(iter(change.items()))
    assert f"{what} {value}" in err and f"migrate --config --issue {SLUG}" in err, err
    assert (task_dir / "manifest.yml").read_text(encoding="utf-8") == before
    assert not (task_dir / "generations" / "2").exists()


def test_ir_13_a_command_over_every_issue_refuses_that_issue_only(committed):
    root, task_dir = committed
    record_versions(task_dir, resolver="2.0.0")
    code, out, err = _run(root, "flow")
    assert code == 0, out + err
    assert SLUG in out and "resolver 2.0.0" in out and "migrate --config" in out, out
    code, out, err = _run(root, "ci")
    assert code == 1, out + err
    assert "refused - generation 1" in out and "compass ci: FAIL" in out, out


def test_ir_14_ci_goes_on_past_a_closed_issue_across_a_major(tmp_path):
    # A closed issue is read across a major by lint, but `check` still refuses it. That
    # refusal is reported as a failure of that issue, and the sweep goes on to the next.
    _two_issues(tmp_path)
    path = tmp_path / ".compass" / "work" / "feature" / "manifest.yml"
    manifest = yaml.safe_load(path.read_text())
    manifest.update(status="done", close_reason="completed", checkpoints=[])
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    code, out, err = _run(tmp_path, "ci")
    assert code == 1, (code, out, err)
    assert "compass ci: FAIL" in out, out + err
    assert out.index("[issue] feature") < out.index("[issue] other"), out
    assert "compass issue lint: PASS - .compass/work/other/manifest.yml" in out, out


def test_ir_13_flow_and_ci_go_on_to_a_healthy_issue(tmp_path):
    _two_issues(tmp_path)
    code, out, err = _run(tmp_path, "flow")
    assert code == 0, out + err
    assert "other" in out and "feature" in out, out
    code, out, err = _run(tmp_path, "ci")
    assert code == 1, out + err
    # The refused issue is named, and the healthy one is still linted and checked after it.
    assert out.index("[issue] feature") < out.index("[issue] other"), out
    assert "refused - generation 1 of feature" in out, out
    assert "compass issue lint: PASS - .compass/work/other/manifest.yml" in out, out


def _two_issues(root, shipped=False):
    """Two issues with stored generations under `root`: `feature`, recorded at
    resolver 2.0.0, and `other`, healthy. Shipped ones hold an approval, so
    `retro --impact` reads their configuration."""
    for slug in ("feature", "other"):
        folder = root / ".compass" / "work" / slug
        folder.mkdir(parents=True)
        (folder / "manifest.yml").write_text(
            yaml.safe_dump(dict(MANIFEST, issue=slug), sort_keys=False))
        code, out, err = _run(root, "approach", "evaluate", "--issue", slug, "--write",
                              "--justify", "risk=a", "--justify", "familiarity=b",
                              "--justify", "size=c", "--justify", "goal=d")
        assert code == 0, out + err
        if shipped:
            path = folder / "manifest.yml"
            manifest = yaml.safe_load(path.read_text())
            manifest.update(status="done", close_reason="completed", checkpoints=[],
                            evidence=[{"id": "EV-1", "type": "human-approval", "check": "x",
                                       "decision": "approved", "path": "evidence/x"}])
            path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    record_versions(root / ".compass" / "work" / "feature", resolver="2.0.0")


@pytest.mark.parametrize("dry", [False, True])
def test_ir_13_render_all_refuses_that_issue_and_renders_the_rest(tmp_path, dry):
    _two_issues(tmp_path)
    code, out, err = _run(tmp_path, "issue", "render", "--all", *(["--dry-run"] if dry else []))
    assert code == 1, out + err
    assert "1 failed" in out and "feature:" in out and "resolver 2.0.0" in out, out
    assert ("1 issue(s) to render" if dry else "1 issue(s) rendered") in out, out


def test_ir_13_retro_impact_reads_a_shipped_issue_across_a_major(tmp_path):
    # A shipped issue keeps the generation it closed under, so the retro reads it and
    # reports every issue.
    _two_issues(tmp_path, shipped=True)
    code, out, err = _run(tmp_path, "retro", "--impact")
    assert code == 0, out + err
    assert "a different major" not in out + err, out + err


def test_ir_13_diagnose_refuses_an_open_issue_that_holds_an_approval(tmp_path):
    # The band count reads the configuration only for an issue that holds an approval. A
    # refusal there must reach the person, and must not read as "not counted".
    _two_issues(tmp_path)
    path = tmp_path / ".compass" / "work" / "feature" / "manifest.yml"
    manifest = yaml.safe_load(path.read_text())
    manifest["evidence"] = [{"id": "EV-1", "type": "human-approval", "check": "x",
                             "decision": "approved", "path": "evidence/x"}]
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    code, out, err = _run(tmp_path, "issue", "diagnose", "--issue", "feature")
    assert code == 2, out + err
    assert "migrate --config --issue feature" in err, out + err
    assert "not counted" not in out + err, out + err


def test_ir_13_a_version_that_is_not_one_is_named_unreadable(committed):
    root, task_dir = committed
    record_versions(task_dir, resolver="v2")
    code, out, err = _run(root, "issue", "lint", "--issue", SLUG)
    assert code == 2, out + err
    assert "resolver 'v2', which is not a version" in err, err
    assert "a different major" not in err, err
    assert f"migrate --config --issue {SLUG}" in err, err


def test_ir_13_a_versions_file_that_is_not_a_mapping_is_broken(committed):
    from compass_pkg import generation
    from compass_pkg.atomic_io import digest
    from compass_pkg.core import CompassError
    root, task_dir = committed
    folder = task_dir / "generations" / "1"
    (folder / "versions.yml").write_text("- resolver\n", encoding="utf-8")
    marker = yaml.safe_load((folder / "complete").read_text(encoding="utf-8"))
    marker["files"]["versions.yml"] = digest(["resolver"])
    (folder / "complete").write_text(yaml.safe_dump(marker), encoding="utf-8")
    with pytest.raises(CompassError, match="versions.yml is not a mapping"):
        generation.load(str(task_dir), 1)


# --- IR-13: a write command is refused for the issue it acts on, and only that one ---------

def test_ir_13_every_write_command_names_how_its_issue_is_found():
    from compass_pkg import record_triggers
    assert set(record_triggers.ISSUE_FROM) == set(record_triggers.RENDER_TRIGGERS)
    assert record_triggers.ISSUE_FROM["cmd_quick_fix_start"] == "slug"
    assert record_triggers.ISSUE_FROM["cmd_scenario_add"] == "task"


QUICK_FIX = ("quick-fix", "start", "--risk", "trivial - a test", "--familiarity",
             "greenfield - a test", "--size", "atomic - a test", "--intent", "a test",
             "--scenario", "Given a When b Then c", "--test", "tests/test_x.py")


def test_ir_13_a_new_issue_is_not_refused_for_the_current_one(committed):
    root, task_dir = committed
    (root / ".compass" / "current-task").write_text(SLUG + "\n", encoding="utf-8")
    record_versions(task_dir, resolver="2.0.0")
    code, out, err = _run(root, *QUICK_FIX[:2], "other", *QUICK_FIX[2:])
    assert "migrate --config" not in out + err, out + err
    assert (root / ".compass" / "work" / "other" / "manifest.yml").is_file(), out + err


def test_ir_13_a_quick_fix_on_the_mismatched_issue_is_refused(committed):
    root, task_dir = committed
    record_versions(task_dir, resolver="2.0.0")
    before = (task_dir / "manifest.yml").read_text(encoding="utf-8")
    code, out, err = _run(root, *QUICK_FIX[:2], SLUG, *QUICK_FIX[2:])
    assert code == 2 and f"migrate --config --issue {SLUG}" in err, out + err
    assert (task_dir / "manifest.yml").read_text(encoding="utf-8") == before


def test_ir_13_a_command_on_another_issue_is_not_refused(committed):
    root, task_dir = committed
    (root / ".compass" / "current-task").write_text(SLUG + "\n", encoding="utf-8")
    other = root / ".compass" / "work" / "other"
    other.mkdir()
    (other / "manifest.yml").write_text(
        yaml.safe_dump(dict(MANIFEST, issue="other"), sort_keys=False), encoding="utf-8")
    record_versions(task_dir, resolver="2.0.0")
    code, out, err = _run(root, "scenario", "add", "OT-1", "--issue", "other",
                          "--intent", "INT-1", "--title", "a scenario")
    assert code == 0 and "migrate --config" not in out + err, out + err


# --- IR-14: the commands that repair a mismatch still run -----------------------------------

@pytest.mark.parametrize("change", CHANGES, ids=["resolver", "schema"])
def test_ir_14_migrate_config_repairs_the_issue(committed, change):
    root, task_dir = committed
    record_versions(task_dir, **change)
    code, out, err = _run(root, "issue", "migrate", "--config", "--issue", SLUG)
    assert code == 0, out + err
    assert "generation 2" in out, out
    from compass_pkg import generation
    stored = yaml.safe_load((task_dir / "generations" / "2" / "versions.yml").read_text("utf-8"))
    assert stored["resolver"] == generation.RESOLVER_VERSION, stored
    assert stored["schema"] == generation.SCHEMA, stored
    for argv in (("check", "--issue", SLUG, "--json"), ("issue", "render", "--issue", SLUG)):
        code, out, err = _run(root, *argv)
        assert "migrate --config" not in err, (argv, err)
        assert code in (0, 1), (argv, out + err)


@pytest.mark.parametrize("argv", [("--version",), ("--help",), ("readiness",),
                                  ("policy", "update")])
def test_ir_14_the_commands_that_need_no_issue_still_run(committed, argv):
    root, task_dir = committed
    (root / ".compass" / "current-task").write_text(SLUG + "\n", encoding="utf-8")
    (root / "compass.yml").write_text("schema: 1\nextends: compass:default@6\n",
                                      encoding="utf-8")
    record_versions(task_dir, resolver="2.0.0")
    code, out, err = _run(root, *argv)
    assert "migrate --config" not in out + err, (argv, out + err)
    assert code in (0, 1), (argv, code, out + err)


def test_ir_14_the_work_root_migrate_names_the_issue_it_did_not_pin(committed):
    root, task_dir = committed
    record_versions(task_dir, resolver="2.0.0")
    code, out, err = _run(root, "issue", "migrate")
    assert code == 0, out + err
    assert f"compass issue migrate --config --issue {SLUG}" in out + err, out + err
    assert not (task_dir / "generations" / "2").exists()


# --- the refusal costs no file read ---------------------------------------------------------

def test_ir_13_the_refusal_reads_no_file_beyond_the_generation(committed, monkeypatch):
    """The refusal runs wherever a generation is loaded, `compass next` among them,
    so it compares what `load` already read and opens nothing more."""
    import builtins
    from compass_pkg import generation
    root, task_dir = committed
    opened = []
    real = builtins.open
    monkeypatch.setattr(builtins, "open",
                        lambda f, *a, **k: opened.append(str(f)) or real(f, *a, **k))
    generation.load(str(task_dir), 1)
    whole = sorted(opened)
    record_versions(task_dir, resolver="2.0.0")
    opened.clear()
    with pytest.raises(generation.MajorRefusal, match="migrate --config"):
        generation.load(str(task_dir), 1)
    assert sorted(opened) == whole


# --- the pre-tool hook does not compare the majors -------------------------------------------

def test_ir_4_a_resolver_or_schema_major_bump_is_held_until_the_hook_decision():
    """Every command that reads an issue's stored generation refuses a resolver or
    schema major that differs from the installed one. The pre-tool hook reads no
    generation, so it does not refuse, and comparing there would cost a file read
    on every edit. No released generation can differ yet. This fails at the first
    bump of either major, so the limit cannot be skipped: decide what the hook does,
    then change this test. `docs/generation-store.md` states the limit."""
    from compass_pkg import generation
    said = ("the pre-tool hook does not compare the resolver and schema majors; decide "
            "whether it must before raising this major (see docs/generation-store.md)")
    assert generation.RESOLVER_VERSION.split(".")[0] == "1", said
    assert generation.SCHEMA == 1, said


def _close(task_dir):
    path = task_dir / "manifest.yml"
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    manifest.update(status="done", close_reason="completed")
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def test_ir_14_a_closed_issue_is_read_across_a_major_by_render_lint_and_flow(committed):
    # `compass issue migrate --config` cannot pin a closed issue, so the refusal would name
    # a fix that refuses. The closed issue keeps the generation it closed under.
    root, task_dir = committed
    record_versions(task_dir, resolver="2.0.0")
    _close(task_dir)
    for argv in (("issue", "render", "--issue", SLUG), ("issue", "lint", "--issue", SLUG)):
        code, out, err = _run(root, *argv)
        assert code == 0, (argv, out + err)
        assert "a different major" not in out + err, (argv, out + err)
    code, out, err = _run(root, "flow")
    assert code == 0, out + err
    assert "UNPLACEABLE" not in out, out
    assert not (task_dir / "generations" / "2").exists()


def test_ir_14_the_work_root_migrate_says_nothing_of_a_closed_issue(committed):
    # The note names `migrate --config`, which refuses a closed issue.
    root, task_dir = committed
    record_versions(task_dir, resolver="2.0.0")
    _close(task_dir)
    code, out, err = _run(root, "issue", "migrate")
    assert code == 0, out + err
    assert "another resolver or schema major" not in out + err, out + err


def test_ir_13_a_linked_issue_that_is_refused_is_reported_after_a_write(tmp_path):
    # `depends add` changes `other` and renders the issues linked to it. `feature` is
    # refused for its generation: the write has happened, so the render is reported
    # and the command does not fail.
    _two_issues(tmp_path)
    code, out, err = _run(tmp_path, "issue", "depends", "add", "feature",
                          "--reason", "x", "--issue", "other")
    assert code == 0, out + err
    assert "1 of 2 renders failed" in out + err, out + err


def test_ir_13_a_programming_error_in_the_early_refusal_is_not_swallowed(committed, monkeypatch):
    # The early refusal leaves an unreadable file to the command. A NameError is a fault
    # in Compass, and hiding it turns the refusal off without a sign.
    from compass_pkg import generation
    root, task_dir = committed

    def broken(manifest):
        raise NameError("a name this module lost")
    monkeypatch.setattr(generation, "number", broken)
    with pytest.raises(NameError):
        generation.refuse_other_major(str(task_dir))


def test_ir_14_a_closed_issue_across_a_major_still_refuses_the_check(committed):
    root, task_dir = committed
    record_versions(task_dir, resolver="2.0.0")
    _close(task_dir)
    code, out, err = _run(root, "check", "--issue", SLUG)
    assert code == 2, out + err
