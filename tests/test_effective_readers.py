"""The readers of configuration read the stored generation.

An issue with a generation is judged by its generation, not by the live
configuration. These tests build a scratch project, commit a generation
with the real command and run the real functions or CLI against it.

Scenario ids: `EF-1` to `EF-12` (issue `effective-readers`). Each test name
starts with its scenario id.
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

from test_generation_store import (SLUG, _committed_project, _manifest, _project,  # noqa: E402
                                   _run, _write_manifest)

from check_set_files import view as _shipped  # noqa: E402


# --- EF-1: the reader helper ---------------------------------------------------------------

def test_ef_1_no_generation_and_no_compass_yml_reads_the_check_set(tmp_path, monkeypatch):
    """Since 9.0.0 every project reads the check set (ADR-094). A project with
    its own copy of the governance files and no `compass.yml` is refused
    (`governance-copy-removed`, ADR-098)."""
    from compass_pkg import check_set, effective
    from compass_pkg.core import CompassError
    root, task_dir = _project(tmp_path)
    monkeypatch.chdir(root)
    for view in (effective.effective_for(str(task_dir)), effective.effective_for(None)):
        assert view is not None and view.source == "live"
        assert view.config["checks"] == check_set.resolved()["checks"]
    _copy_governance(root)
    for task in (str(task_dir), None):
        with pytest.raises(CompassError) as refused:
            effective.effective_for(task)
        assert "[governance-copy-removed]" in str(refused.value)


@pytest.mark.parametrize("only", ["routing-policy.yml", "guardrails.yml", None])
def test_ef_1_a_governance_copy_is_refused_by_the_commands(tmp_path, only):
    """Either copied file alone is refused too: a declared guardrail never
    becomes silent. A `compass.yml` makes the copy a file nothing reads."""
    root, task_dir = _project(tmp_path)
    folder = _copy_governance(root)
    if only:
        (folder / only).unlink()
    for argv in (("check", "--issue", SLUG), ("approach", "evaluate", "--issue", SLUG),
                 ("policy", "lint"), ("policy", "show")):
        code, out, err = _run(root, *argv)
        assert code == 2 and "[governance-copy-removed]" in err, (argv, out + err)
    (root / "compass.yml").write_text("schema: 1\n", encoding="utf-8")
    code, out, err = _run(root, "check", "--issue", SLUG)
    assert "governance-copy-removed" not in err, out + err


def test_ef_1_a_generation_gives_the_stored_view(tmp_path, monkeypatch):
    from compass_pkg import effective
    root, task_dir = _committed_project(tmp_path)
    monkeypatch.chdir(root)
    view = effective.effective_for(str(task_dir))
    assert (view.source, view.generation) == ("generation", 1)


def test_ef_1_generation_zero_refuses_and_names_the_fix(tmp_path, monkeypatch):
    from compass_pkg import effective
    from compass_pkg.core import CompassError
    root, task_dir = _project(tmp_path)
    _write_manifest(task_dir, generation=0)
    monkeypatch.chdir(root)
    with pytest.raises(CompassError) as caught:
        effective.effective_for(str(task_dir))
    assert "compass approach evaluate --write" in str(caught.value)


def test_ef_1_a_compass_yml_gives_a_live_view_with_or_without_an_issue(tmp_path, monkeypatch):
    from compass_pkg import effective
    root, task_dir = _project(tmp_path, compass_yml={"schema": 1})
    monkeypatch.chdir(root)
    assert effective.effective_for(str(task_dir)).source == "live"
    assert effective.effective_for(None).source == "live"


def test_ef_1_the_governance_readme_says_a_copy_is_refused():
    """An adopter can find out what happens to a 5.x copy: the section that
    answered it before 9.0.0 now says the copy is refused, and how to move."""
    body = (ROOT / "governance" / "README.md").read_text(encoding="utf-8")
    marker = "## A project that copied governance under 5.x"
    assert marker in body
    section = " ".join(body.split(marker, 1)[1].split("\n## ", 1)[0].split())
    assert "governance-copy-removed" in section and "compass policy migrate" in section


# --- EF-2: the accessors of a stored generation equal those of the check set ---------------

ASSESSMENTS = (
    {"risk": "contained", "size": "small", "labels": []},
    {"risk": "critical", "size": "large", "labels": ["auth"]},
    {"risk": "trivial", "size": "atomic", "labels": ["payments"]},
)


def _stored(tmp_path, monkeypatch):
    """The view of a committed generation of the shipped default."""
    root, task_dir = _committed_project(tmp_path)
    monkeypatch.chdir(root)
    from compass_pkg import effective
    return effective.effective_for(str(task_dir))


def test_ef_2_guardrail_gates_equal_the_guardrails_file(tmp_path, monkeypatch):
    stored = _stored(tmp_path, monkeypatch)
    legacy = _shipped("guardrails.yml")
    from compass_pkg.core import reading_matches
    got = stored.guardrail_gates()
    for group in ("defaults", "spike_guardrails"):
        want = [(g["id"], g["name"], list(g["checks"])) for g in legacy[group]]
        have = [(g["id"], g["name"], list(g["checks"])) for g in got[group]]
        assert have == want, group
    assert got["project"] == []
    for old, new in zip(legacy["defaults"], got["defaults"]):
        for assessment in ASSESSMENTS:
            old_applies = reading_matches(old.get("applies_when"), assessment)
            assert stored.matches(new.get("applies_when"), assessment) == old_applies, old["id"]
    for name, body in (legacy.get("checks") or {}).items():
        assert ("blocking_when" in body) == ("blocking_when" in got["checks"].get(name, {})), name
        if "blocking_when" in body:
            for assessment in ASSESSMENTS:
                assert (stored.matches(got["checks"][name]["blocking_when"], assessment)
                        == reading_matches(body["blocking_when"], assessment)), name


def test_ef_2_gate_requirements_equal_the_guardrails_file(tmp_path, monkeypatch):
    stored = _stored(tmp_path, monkeypatch)
    legacy = _shipped("guardrails.yml")
    requirements, known = stored.gate_requirements()
    assert requirements == {k: list(v) for k, v in legacy["gate_evidence_requirements"].items()}
    assert known == set(legacy["evidence_types"])


def test_ef_2_loop_ceiling_rules_equal_the_policy_file(tmp_path, monkeypatch):
    stored = _stored(tmp_path, monkeypatch)
    legacy = _shipped("routing-policy.yml")["routing_guardrails"]["loop_ceilings"]
    got = stored.loop_ceiling_rules()
    assert [(r["id"], r["ceiling"], r["limit"]) for r in got] == [
        (r["id"], r["ceiling"], r["limit"]) for r in legacy]
    from compass_pkg.core import reading_matches
    for old, new in zip(legacy, got):
        for assessment in ASSESSMENTS:
            assert stored.matches(new.get("when"), assessment) == reading_matches(
                old.get("when"), assessment), old["id"]


def test_ef_2_the_shipped_default_holds_no_command_check(tmp_path, monkeypatch):
    stored = _stored(tmp_path, monkeypatch)
    assert stored.command_checks() == []


# --- helpers for the commands ---------------------------------------------------------------

def _check_json(root, *extra):
    code, out, err = _run(root, "check", "--issue", SLUG, "--json", *extra)
    return code, json.loads(out), err


def _guardrail_ids(report):
    return {c["guardrail"] for c in report["checks"]}


def _copy_governance(root):
    """The project keeps its own copies of the two 8.x governance files."""
    import compat_baseline as cb
    cb.add_governance_copy(root, source=cb.GOVERNANCE_8_0_4)
    return root / "governance"


# --- EF-3: check judges an issue by its generation ------------------------------------------

def test_ef_3_changing_the_live_configuration_does_not_change_the_verdict(tmp_path):
    root, task_dir = _project(tmp_path)
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    _, before, _ = _check_json(root)
    assert {"G1", "G2", "G3", "G4"} <= _guardrail_ids(before)
    (root / "compass.yml").write_text(yaml.safe_dump(LAYERED), encoding="utf-8")
    _, after, _ = _check_json(root)
    assert "PX" not in _guardrail_ids(after)
    assert _guardrail_ids(after) == _guardrail_ids(before)
    assert after["checks"] == before["checks"]


# --- EF-4: a command check from the generation ------------------------------------------------

#: A project check (ADR-094): one `command-passes` check and one guardrail gate,
#: both under the entry's id.
COMMAND_PROJECT = {
    "schema": 1, "allow_project_commands": True,
    "project_checks": [{"id": "arch-rule", "name": "Project rule",
                        "command": "touch ran.flag", "stage": "ship"}],
}


def test_ef_4_a_check_with_its_own_id_runs_its_command_from_the_generation(tmp_path):
    root, task_dir = _project(tmp_path, compass_yml=COMMAND_PROJECT)
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    (root / "compass.yml").unlink()
    (root / ".compass" / "config.yml").write_text("allow_project_commands: true\n",
                                                  encoding="utf-8")
    _, report, _ = _check_json(root)
    rows = [c for c in report["checks"] if c["guardrail"] == "arch-rule"]
    assert [c["name"] for c in rows] == ["arch-rule"], report
    assert rows[0]["status"] == "pass", rows
    assert (root / "ran.flag").exists()
    assert not any(c["detail"].endswith("NO CLI implementation") for c in report["checks"])


# --- EF-9: the verdict header and the pending change ------------------------------------------

def test_ef_9_check_names_the_generation_and_the_parent_version(tmp_path):
    root, task_dir = _committed_project(tmp_path)
    versions = yaml.safe_load((task_dir / "generations" / "1" / "versions.yml")
                              .read_text(encoding="utf-8"))
    parent = versions["parents"][0]["version"]
    code, out, err = _run(root, "check", "--issue", SLUG)
    assert f"generation 1 (parent {parent})" in out, out + err
    code, out, err = _run(root, "check", "--issue", SLUG, "--verbose")
    assert f"generation 1 (parent {parent})" in out, out + err
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    document = json.loads(out)
    assert (document["generation"], document["parent_version"]) == (1, parent)


def test_ef_9_a_changed_config_is_named_as_not_read_and_does_not_fail(tmp_path):
    """9.0.0 has no issue layer (ADR-094): a `config:` the generation was not
    committed with is named as not read, and changes nothing."""
    root, task_dir = _committed_project(tmp_path)
    code, clean, _ = _run(root, "check", "--issue", SLUG)
    assert "config: differs" not in clean
    _write_manifest(task_dir, config={"checks": {"extra": {
        "statement": "A check.", "kind": "deterministic", "impl": "suite-passed",
        "severity": "advisory", "on_skipped": "fail"}}})
    code2, out, err = _run(root, "check", "--issue", SLUG)
    assert "config: differs from the generation in force and is not read" in out, out + err
    assert "ADR-094" in out
    assert code2 == code


def test_ef_9_an_issue_with_no_generation_prints_neither_line(tmp_path):
    root, task_dir = _project(tmp_path)
    for flags in ((), ("--verbose",), ("--json",)):
        code, out, err = _run(root, "check", "--issue", SLUG, *flags)
        assert "generation" not in out and "pending" not in out, out + err


# --- EF-10: compass ci carries on past an issue at generation 0 -------------------------------

def test_ef_10_ci_reports_an_issue_at_generation_zero_and_checks_the_next(tmp_path):
    root, first = _project(tmp_path, slug="a-waiting")
    _, second = _project(tmp_path, slug="b-healthy")
    _write_manifest(first, generation=0)
    code, out, err = _run(root, "ci")
    assert code == 1, out + err
    waiting, healthy = out.split("[issue] b-healthy")
    assert "generation 0" in waiting and "compass approach evaluate --write" in waiting, out
    assert "compass check" in healthy or "check(s)" in healthy, out
    assert "compass ci: FAIL" in out


# --- EF-10: no generation, same output ----------------------------------------------------------

def test_ef_10_check_on_an_issue_with_no_generation_matches_the_legacy_reading(tmp_path):
    root, task_dir = _project(tmp_path)
    _, report, _ = _check_json(root)
    guardrails = _shipped("guardrails.yml")
    expected = {g["id"] for g in guardrails["defaults"]}
    assert _guardrail_ids(report) - {""} <= expected
    assert "G1" in _guardrail_ids(report)
    assert "generations" not in {p.name for p in task_dir.iterdir()}


# --- EF-5: evidence requirements from the generation ------------------------------------------

def test_ef_5_the_accepts_comments_come_from_the_configuration_committed(tmp_path, monkeypatch):
    """The commit writes each gate's `# accepts` comment from the configuration it
    stores, not from the governance files. Since 9.0.0 `compass.yml` cannot change
    what a gate accepts (ADR-094), so the commit is given a resolution that does,
    as a generation stored before 9.0.0 could."""
    import dataclasses

    from compass_pkg import effective
    from compass_pkg.manifest import annotate_gate_accepts_text
    # The security review is owed only where the project's settings add it
    # (ADR-099 decision 9), so the gate `verify.security` exists here by a rule.
    root, task_dir = _project(tmp_path, compass_yml={
        "schema": 1, "require_evidence": [
            {"when": {"size": ["medium"]}, "add": ["security"]}]})
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    monkeypatch.chdir(root)
    manifest = _manifest(task_dir)
    resolution = effective.resolve_live(str(root), manifest, SLUG, str(task_dir))
    resolved = dict(resolution.resolved)
    resolved["gates"] = dict(resolved["gates"])
    resolved["gates"]["verify.security"] = dict(resolved["gates"]["verify.security"],
                                                accepts=["security-review"])
    done = effective.commit_generation(
        str(task_dir), manifest, render=annotate_gate_accepts_text,
        resolution=dataclasses.replace(resolution, resolved=resolved))
    assert done.committed, done.message
    manifest_text = (task_dir / "manifest.yml").read_text(encoding="utf-8")
    stored = yaml.safe_load((task_dir / "generations" / str(done.number) / "resolved.yml")
                            .read_text(encoding="utf-8"))
    assert stored["gates"]["verify.security"]["accepts"] == ["security-review"]
    comments = [l.strip() for l in manifest_text.splitlines() if "# accepts" in l]
    assert "# accepts: ['security-review']" in comments, comments


# --- EF-6: approach evaluate from the generation ------------------------------------------------

def _evaluate_json(root, slug=SLUG):
    code, out, err = _run(root, "approach", "evaluate", "--issue", slug, "--json")
    assert code == 0, out + err
    return json.loads(out)


def test_ef_6_the_result_matches_the_one_the_governance_files_give(tmp_path):
    root, task_dir = _project(tmp_path)
    _project(tmp_path, slug="other")
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    stored, live = _evaluate_json(root), _evaluate_json(root, "other")
    # The stored generation also carries the delivery-approach record every approach owes
    # (the catalogue flag `every_approach`); the governance files do not declare the flag.
    stored["artifacts"] = [a for a in stored["artifacts"] if a["kind"] != "delivery-approach"]
    # On the four-stage path the preview owes what a write would store (ADR-092).
    # No record of `S17` is owed unless a setting adds it (ADR-099 decision 9).
    assert stored["acceptance_strategy"]["applies"] is False
    assert not {"outer-loop", "isolation", "layering"} & set(live["evidence_required"])
    assert stored == live


def test_ef_6_the_autonomy_is_the_one_the_generation_stored(tmp_path):
    root, task_dir = _project(tmp_path)
    _project(tmp_path, slug="other")
    # On the path balanced autonomy lists no checkpoint on this change (ADR-092 open
    # question 7), so the issue is assessed under controlled autonomy, which does.
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\nautonomy: controlled\n",
                                                  encoding="utf-8")
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    before = _evaluate_json(root)
    assert before["checkpoints"], before
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\nautonomy: autonomous\n",
                                                  encoding="utf-8")
    assert _evaluate_json(root) == before
    assert _evaluate_json(root, "other")["checkpoints"] != before["checkpoints"]


# --- EF-8: readers with no issue ------------------------------------------------------------------

#: Two tighten-only settings (ADR-094): a project check, which adds the guardrail
#: gate `PX`, and evidence owed for the label `zzz-label`.
LAYERED = {
    "schema": 1,
    "project_checks": [{"id": "PX", "name": "Project rule", "command": "true",
                        "stage": "ship"}],
    "require_evidence": [{"when": {"labels_any": ["zzz-label"]}, "add": ["architecture"]}],
}


def test_ef_8_lessons_refuse_a_guardrail_the_compass_yml_adds(tmp_path, monkeypatch):
    from compass_pkg import lessons
    root, _ = _project(tmp_path, compass_yml=LAYERED)
    monkeypatch.chdir(root)
    assert "PX" in lessons._refusal("never skip PX", "user")
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / ".compass").mkdir()
    monkeypatch.chdir(plain)
    assert lessons._refusal("never skip PX", "user") is None


def test_ef_8_review_rules_know_the_guardrail_the_compass_yml_adds(tmp_path):
    from compass_pkg import review_rules
    root, _ = _project(tmp_path, compass_yml=LAYERED)
    gov = root / "governance"
    gov.mkdir()
    rule = {"id": "RR-001", "blocking": True, "file_patterns": ["cli/*.py"], "enforces": "PX",
            "rule": "Keep it.", "incident": "An incident."}
    (gov / "review-rules.yml").write_text(yaml.safe_dump({"rules": [rule]}), encoding="utf-8")
    assert review_rules.lint_errors(str(gov)) == []
    plain = tmp_path / "plain"
    (plain / "governance").mkdir(parents=True)
    (plain / ".compass").mkdir()
    (plain / "governance" / "review-rules.yml").write_text(
        yaml.safe_dump({"rules": [rule]}), encoding="utf-8")
    assert any("PX" in e for e in review_rules.lint_errors(str(plain / "governance")))


def test_ef_8_flow_knows_the_label_the_compass_yml_names(tmp_path, monkeypatch):
    from compass_pkg import flow
    root, _ = _project(tmp_path, compass_yml=LAYERED)
    monkeypatch.chdir(root)
    assert "zzz-label" in flow._routing_labels()
    plain = tmp_path / "plain"
    (plain / ".compass").mkdir(parents=True)
    monkeypatch.chdir(plain)
    assert "zzz-label" not in flow._routing_labels()
    assert "auth" in flow._routing_labels()


def test_ef_8_quick_fix_blockers_read_the_policy_through_effective(tmp_path, monkeypatch):
    # The shipped default has no quick-fix shape since 9.0.0 (ADR-092), so the view's
    # policy is the 8.0.4 governance copy's, and the plain project carries that copy.
    import compat_baseline as cb
    from compass_pkg import effective, quick_fix_cmd
    root, _ = _project(tmp_path, compass_yml=LAYERED)
    monkeypatch.chdir(root)
    readings = {"risk": "critical", "familiarity": "brownfield-mapped", "size": "standard",
                "labels": []}
    asked = []
    real = effective.effective_for
    monkeypatch.setattr(effective, "effective_for",
                        lambda *a, **k: asked.append(a) or real(*a, **k))
    v8 = cb.policy_8_0_4()
    monkeypatch.setattr(effective.EffectiveView, "evaluator_policy", lambda self: v8)
    layered = quick_fix_cmd._quick_fix_blockers(readings, {})
    assert asked, "the blockers did not ask the effective view"
    assert any(line.startswith("blocked: risk is critical") for line in layered), layered
    plain = tmp_path / "plain"
    (plain / ".compass").mkdir(parents=True)
    monkeypatch.chdir(plain)
    assert quick_fix_cmd._quick_fix_blockers(readings, {}) == layered


# --- EF-11: every read of a governance policy file is in a function that asks effective ----

import ast  # noqa: E402
import re  # noqa: E402

PACKAGE = ROOT / "cli" / "compass_pkg"
POLICY_READ = re.compile(r"os\.path\.join\([^\n]*[\"'](routing-policy|guardrails)\.yml[\"']")

#: Modules that may name a policy file without reading it: `effective`, which
#: names the two files of a governance copy to refuse it, and the text of help
#: messages.
POLICY_FILE_OWNERS = frozenset({"effective", "project_commands", "verb_help"})


def _reads(name, text):
    """`{function: [line, ...]}` for each read of a policy file in `text`."""
    tree = ast.parse(text)
    lines = text.splitlines()
    functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    found = {}
    for number, line in enumerate(lines, 1):
        if not POLICY_READ.search(line):
            continue
        enclosing = sorted((n for n in functions if n.lineno <= number <= n.end_lineno),
                           key=lambda n: n.end_lineno - n.lineno)
        found.setdefault(enclosing[0].name if enclosing else "<module>", []).append(number)
    return found


def _all_reads():
    out = {}
    for path in PACKAGE.glob("*.py"):
        if path.stem in POLICY_FILE_OWNERS:
            continue
        for function, hits in _reads(path.stem, path.read_text(encoding="utf-8")).items():
            out[(path.stem, function)] = len(hits)
    return out


def test_ef_11_no_module_reads_a_governance_policy_file():
    """9.0.0 reads no copy of `routing-policy.yml` or `guardrails.yml` (ADR-098):
    every reader asks `effective.effective_for`."""
    assert _all_reads() == {}


def test_ef_11_the_scan_can_fail():
    direct = 'policy = load_yaml(os.path.join(gov, "routing-policy.yml"))\n'
    planted = "def planted():\n    " + direct
    assert _reads("m", planted) == {"planted": [2]}
    text = (PACKAGE / "lessons.py").read_text(encoding="utf-8")
    assert _reads("lessons", text) == {}
    doubled = text.replace("def _guardrail_ids():\n",
                           "def _guardrail_ids():\n    " + direct + "    " + direct)
    assert len(_reads("lessons", doubled)["_guardrail_ids"]) == 2


# --- EF-11 (continued): the header comments name what a module imports -----------------------

def _compass_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "compass_pkg":
                names |= {a.name for a in node.names}
            elif node.module.startswith("compass_pkg."):
                names.add(node.module.split(".")[1])
    return names


def test_ef_11_a_dependency_header_that_lists_modules_lists_every_one_imported():
    for name in ("loop_ceilings", "approach_diagram"):
        path = PACKAGE / f"{name}.py"
        header = next(line for line in path.read_text(encoding="utf-8").splitlines()
                      if "DEPENDENCY" in line)
        missing = [m for m in _compass_imports(path) if m not in header]
        assert missing == [], f"{name} imports {missing}, which its DEPENDENCY line omits"


def test_ef_11_the_obligations_header_names_every_module_that_imports_it():
    importers = sorted(p.stem for p in PACKAGE.glob("*.py")
                       if "obligations" in _compass_imports(p) and p.stem != "obligations")
    header = (PACKAGE / "obligations.py").read_text(encoding="utf-8")
    sentence = next(line for line in header.splitlines() if "import this module" in line)
    assert [m for m in importers if f"compass_pkg.{m}" not in sentence] == [], (
        importers, sentence)


# --- the 8.x copy reader refuses a malformed field value ------------------------------
#
# The contracts read the 8.0.4 and 5.6.0 copies through `tests/legacy_copy.py`, the
# reader 8.x ran. A field value of the wrong type or outside its closed set is refused
# by name, as the 8.x layer check refused it, so a planted fault is never read
# silently.

def _copy_8_0_4(tmp_path):
    import compat_baseline as cb
    root = tmp_path / "copy"
    (root / ".compass" / "work").mkdir(parents=True)
    cb.add_governance_copy(root, source=cb.GOVERNANCE_8_0_4)
    return root


def test_a_governance_copy_with_a_wrong_type_field_is_refused_by_path(tmp_path):
    import legacy_copy
    from compass_pkg.core import CompassError
    root = _copy_8_0_4(tmp_path)
    legacy_copy.resolved_from_copy(str(root))      # the copy as shipped resolves
    path = root / "governance" / "guardrails.yml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["checks"]["scenarios-are-executable"]["blocking_when"] = 7
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    with pytest.raises(CompassError) as raised:
        legacy_copy.resolved_from_copy(str(root))
    assert str(raised.value) == ("legacy: checks.scenarios-are-executable.blocking_when: "
                                 "expected map, found 7")


@pytest.mark.parametrize("catalogue, field, value", [
    ("checks", "severity", "sometimes"),
    ("checks", "kind", "magic"),
])
def test_a_governance_copy_with_a_value_outside_its_set_is_refused_by_path(
        catalogue, field, value):
    import legacy_copy
    from compass_pkg.core import CompassError
    entry = {"statement": "x", "kind": "deterministic", "severity": "blocking",
             "on_skipped": "fail", field: value}
    with pytest.raises(CompassError) as raised:
        legacy_copy._legacy_config({catalogue: {"c-1": entry}})
    message = str(raised.value)
    assert message.startswith(f"legacy: {catalogue}.c-1.{field}: '{value}' is not one of "), \
        message
