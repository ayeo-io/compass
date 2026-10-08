"""The artifacts catalogue is checked as a graph by `compass policy lint`.

Four rules: each `depends_on` names an artifact that exists, the graph has no
cycle, a bookkeeping artifact is never an input, and no artifact depends on a
directory. Each is a finding with a code, a level, a path and the group it
belongs to. The engine is pure, so these tests hand it layer documents.

The scenarios of issue `artifact-graph-lint` are a bookkeeping input
(`TRC-001`), a directory dependency (`TRC-002`), a missing name or a cycle
(`TRC-003`) and the shipped preset with the schema text (`TRC-004`). Each
test name starts with its scenario id.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

TODAY = date(2026, 10, 8)


def _lint(artifacts):
    import classifier_fixtures
    from compass_pkg import policy_lint
    from compass_pkg.layers import Layer
    parent = Layer("default", "parent", {"schema": 1, **classifier_fixtures.base()}, "digest")
    project = Layer("project", "project", {"schema": 1, "artifacts": artifacts}, "digest")
    return policy_lint.lint_chain(parent, project, None, today=TODAY, cache={})


def _only(report, code):
    found = [f for f in report.findings if f.code == code]
    assert len(found) == 1, [(f.code, f.path) for f in report.findings]
    return found[0]


def _doc(name, **fields):
    return {"file": name, **fields}


# --- a bookkeeping artifact is never an input (TRC-001) -------------------------------

def test_trc_001_a_bookkeeping_artifact_as_an_input_is_reported():
    report = _lint({
        "dashboard": _doc("dashboard.md", bookkeeping=True),
        "summary": _doc("summary.md", depends_on=["dashboard"])})
    found = _only(report, "M-BOOKKEEPING-INPUT")
    assert (found.level, found.layer, found.group) == ("error", "project", "resolved")
    assert found.path == "artifacts.summary.depends_on"
    assert "dashboard" in found.message and "summary" in found.message


def test_trc_001_a_bookkeeping_artifact_may_depend_on_others():
    report = _lint({
        "intent": _doc("intent.md"),
        "receipt": _doc("receipt.md", bookkeeping=True, depends_on=["intent"])})
    assert report.findings == []


def test_trc_001_every_bookkeeping_input_is_reported_once_per_artifact():
    report = _lint({
        "dashboard": _doc("dashboard.md", bookkeeping=True),
        "receipt": _doc("receipt.md", bookkeeping=True),
        "summary": _doc("summary.md", depends_on=["dashboard", "receipt"])})
    found = _only(report, "M-BOOKKEEPING-INPUT")
    assert "dashboard" in found.message and "receipt" in found.message


def test_trc_001_a_bookkeeping_input_is_a_finding_in_the_json_view():
    from compass_pkg import policy_lint
    report = _lint({
        "dashboard": _doc("dashboard.md", bookkeeping=True),
        "summary": _doc("summary.md", depends_on=["dashboard"])})
    finding = policy_lint.lint_json(report)["findings"][0]
    assert {k: finding[k] for k in ("code", "level", "path", "group")} == {
        "code": "M-BOOKKEEPING-INPUT", "level": "error",
        "path": "artifacts.summary.depends_on", "group": "resolved"}


# --- no artifact depends on a directory (TRC-002) --------------------------------------

def test_trc_002_a_dependency_on_a_directory_is_reported():
    report = _lint({
        "evidence": _doc("evidence/"),
        "verification-report": _doc("verification-report.md", depends_on=["evidence"])})
    found = _only(report, "M-DIRECTORY-DEPENDENCY")
    assert (found.level, found.layer, found.group) == ("error", "project", "resolved")
    assert found.path == "artifacts.verification-report.depends_on"
    assert "evidence" in found.message


def test_trc_002_a_directory_may_itself_depend_on_a_file():
    report = _lint({
        "intent": _doc("intent.md"),
        "evidence": _doc("evidence/", depends_on=["intent"])})
    assert report.findings == []


def test_trc_002_a_dependency_on_a_file_is_not_reported():
    report = _lint({
        "intent": _doc("intent.md"),
        "verification-report": _doc("verification-report.md", depends_on=["intent"])})
    assert report.findings == []


# --- a dangling name and a cycle (TRC-003) ---------------------------------------------

def test_trc_003_a_dependency_on_an_artifact_nobody_defines_is_reported():
    report = _lint({"summary": _doc("summary.md", depends_on=["nothing"])})
    found = _only(report, "M-REF-UNKNOWN")
    assert (found.level, found.group) == ("error", "resolved")
    assert found.path == "artifacts.summary.depends_on" and "nothing" in found.message


def test_trc_003_a_cycle_is_reported_with_its_path():
    report = _lint({
        "a": _doc("a.md", depends_on=["b"]),
        "b": _doc("b.md", depends_on=["c"]),
        "c": _doc("c.md", depends_on=["a"])})
    found = _only(report, "M-CYCLE")
    assert (found.level, found.group) == ("error", "resolved")
    assert found.path == "artifacts.a.depends_on"
    assert "a -> b -> c -> a" in found.message


def test_trc_003_an_artifact_that_depends_on_itself_is_a_cycle():
    report = _lint({"a": _doc("a.md", depends_on=["a"])})
    assert "a -> a" in _only(report, "M-CYCLE").message


def test_trc_003_a_bookkeeping_input_inside_a_cycle_reports_both():
    report = _lint({
        "a": _doc("a.md", bookkeeping=True, depends_on=["b"]),
        "b": _doc("b.md", depends_on=["a"])})
    assert sorted(f.code for f in report.findings) == ["M-BOOKKEEPING-INPUT", "M-CYCLE"]


def test_trc_003_two_cycles_that_share_an_artifact_are_each_reported():
    report = _lint({
        "a": _doc("a.md", depends_on=["b"]),
        "b": _doc("b.md", depends_on=["a", "c"]),
        "c": _doc("c.md", depends_on=["b"])})
    paths = sorted(f.path for f in report.findings if f.code == "M-CYCLE")
    assert paths == ["artifacts.a.depends_on", "artifacts.b.depends_on"]


def test_trc_003_an_artifact_that_leads_into_a_cycle_is_not_part_of_it():
    report = _lint({
        "x": _doc("x.md", depends_on=["a"]),
        "a": _doc("a.md", depends_on=["b"]),
        "b": _doc("b.md", depends_on=["a"])})
    assert "a -> b -> a" in _only(report, "M-CYCLE").message


# --- the shipped preset and the schema text (TRC-004) ----------------------------------

def test_trc_004_the_shipped_preset_has_no_graph_finding():
    from compass_pkg import policy_lint
    parent, _ = policy_lint.load_parent()
    report = policy_lint.lint_chain(parent, None, today=TODAY)
    assert report.findings == []


def test_trc_004_the_bookkeeping_description_names_the_records_the_design_gives():
    from compass_pkg import catalogue_spec as spec
    text = spec.FIELD_DESCRIPTIONS["artifacts"]["bookkeeping"]
    assert "never an input" in text
    for record in ("dashboard", "receipt", "verification report"):
        assert record in text


def test_trc_004_the_published_schema_carries_the_same_description():
    from compass_pkg import catalogue_spec as spec
    schema = json.loads((ROOT / "schemas" / "compass.schema.json").read_text(encoding="utf-8"))
    text = json.dumps(schema)
    assert json.dumps(spec.FIELD_DESCRIPTIONS["artifacts"]["bookkeeping"]) in text
