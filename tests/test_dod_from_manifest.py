"""The Definition of Done and Ready from the manifest (issue
`documents-carry-judgement`, group C: DCJ-24 to DCJ-34).

An item of the configured `verify` exit list or `plan` entry list is met by a
record in the manifest: an evidence entry with `meets`, a person's approval, or
a follow-up that defers it. A tick on a page counts for nothing. Each test
builds a temporary git repository (`rendered_blocks_support`) and drives
`cli/compass`; the approval commands run on a pseudo-terminal, as a person has.

Each test name starts with its scenario id.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import yaml

import rendered_blocks_support as sup
from rendered_blocks_support import (DOCS, ROOT, SLUG, WORK, block, manifest, manifest_file,
                                     render, run, write_doc)

ITEMS = ["dod-every-scenario-passes", "dod-suite-green", "dod-coverage-floor",
         "dod-no-lint-errors", "dod-traceability-intact", "dod-living-docs-updated",
         "dod-follow-ups-settled"]
READY = ["dor-summary-filled", "dor-problem-traces-up", "dor-behaviour-is-gwt",
         "dor-traceability-ids", "dor-affected-surface-named", "dor-no-open-questions",
         "dor-approach-still-fits"]
#: A project that declares jed72 as owner and as an approver.
LAYER = dict(sup.base.HUMAN_DESIGN)
ON = {**LAYER, "capabilities": {"entry-exit-evaluation": True}}
SPEC = {"risk": "critical", "familiarity": "brownfield-mapped", "size": "large",
        "goal": "delivery", "role": "engineer", "labels": []}


def _issue(tmp_path, layer=None, **project):
    root = sup.project(tmp_path, compass_yml=layer or LAYER, **project)
    write_doc(root, "verification-report", "# VR\n\n" + block("dod"))
    return root


def _file(root, name, text="ok\n"):
    folder = Path(root) / WORK / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")
    return f"evidence/{name}"


def _ok(result):
    code, out, err = result
    assert code == 0, out + err
    return out


def _evidence(root, evidence_id, kind, *meets, gate=None):
    ext = "json" if kind == "test-run" else "txt"
    body = '{"command": "pytest", "exit_code": 0, "passed": true}\n' if kind == "test-run" else "ok\n"
    path = _file(root, f"{evidence_id}.{ext}", body)
    flags = [x for item in meets for x in ("--meets", item)] if not gate else []
    _ok(run(root, "evidence", "add", evidence_id, "--type", kind, "--path", path,
            "--issue", SLUG, *flags))
    if gate:
        _ok(run(root, "gate", "pass", gate, "--evidence", evidence_id, "--issue", SLUG,
                *[x for item in meets for x in ("--meets", item)]))


def _record_all(root, skip=()):
    """The seven items of DCJ-24, each by the command that records it."""
    if "dod-every-scenario-passes" not in skip:
        _evidence(root, "EV-ACC", "command-output", "dod-every-scenario-passes")
    if "dod-suite-green" not in skip:
        _evidence(root, "EV-T", "test-run", "dod-suite-green", gate="verify.correctness")
    if "dod-coverage-floor" not in skip:
        _evidence(root, "EV-COV", "command-output", "dod-coverage-floor")
    if "dod-traceability-intact" not in skip:
        _evidence(root, "EV-TRACE", "command-output", "dod-traceability-intact",
                  gate="verify.traceability")
    if "dod-no-lint-errors" not in skip:
        _ok(sup.base.approve(root, "--check", "dod-no-lint-errors", approver="jed72",
                             role="maintainer", scope="lint"))
    for fu, item in (("FU-3", "dod-living-docs-updated"), ("FU-4", "dod-follow-ups-settled")):
        if item not in skip:
            _ok(run(root, "follow-up", "add", fu, "--defers", item, "--summary",
                    f"Settle {item} at ship", "--issue", SLUG))


def _dod_block(root, kind="dod", doc="verification-report"):
    text = (Path(root) / DOCS / f"{doc}.md").read_text(encoding="utf-8").split("\n")
    start = text.index(sup.OPEN.format(kind=kind))
    end = text.index(sup.CLOSE, start)
    return text[start + 1:end]


def _report(root):
    code, out, err = run(root, "check", "--issue", SLUG, "--json")
    return code, json.loads(out)


def _row(report, name, guardrail=None):
    rows = [c for c in report["checks"] if c["name"] == name
            and (guardrail is None or c["guardrail"] == guardrail)]
    assert rows, [(c["guardrail"], c["name"]) for c in report["checks"]]
    return rows[0]


# --- DCJ-24 -----------------------------------------------------------------

def test_dcj_24_dod_block_reads_as_a_result(tmp_path):
    root = _issue(tmp_path)
    _record_all(root)
    _ok(render(root))
    lines = _dod_block(root)
    assert lines[0] == "Definition of Done: 5 of 7 met, 2 carried to ship (FU-3, FU-4)", lines
    items = [x for x in lines[1:] if x.strip()]
    assert len(items) == 7
    for item, line in zip(ITEMS, items):
        assert item in line, (item, line)
    joined = "\n".join(items)
    assert "met by EV-T" in joined and "ticked by jed72" in joined
    assert "carried to ship, FU-3" in joined and "carried to ship, FU-4" in joined
    assert not [x for x in lines if re.search(r"\[[ xX]\]", x)], lines
    _, report = _report(root)
    assert _row(report, "dod-evidence-typed")["status"] == "pass", _row(report, "dod-evidence-typed")


# --- DCJ-25 -----------------------------------------------------------------

def test_dcj_25_item_without_record_open_and_fails(tmp_path):
    root = _issue(tmp_path)
    _record_all(root, skip=("dod-coverage-floor",))
    _ok(render(root))
    lines = _dod_block(root)
    assert lines[0] == ("Definition of Done: 4 of 7 met, 2 carried to ship (FU-3, FU-4), "
                        "1 open"), lines[0]
    floor = [x for x in lines if "dod-coverage-floor" in x]
    assert floor and "open" in floor[0], floor
    _, report = _report(root)
    row = _row(report, "dod-evidence-typed")
    assert row["status"] == "fail", row
    assert "dod-coverage-floor" in row["detail"]
    for command in ("--meets", "--defers", "--check"):
        assert command in row["detail"], row["detail"]


# --- DCJ-26 -----------------------------------------------------------------

def _ticked_page(root):
    from compass_pkg import effective
    config = yaml.safe_load((Path(root) / WORK / "generations" / "1" / "resolved.yml")
                            .read_text("utf-8"))["checks"]
    boxes = "".join("- [x] %s\n" % config[i]["statement"] for i in ITEMS)
    write_doc(root, "verification-report",
              "# VR\n\n" + block("dod") + "\n### Definition of Done\n\n" + boxes)


def test_dcj_26_page_ticks_count_for_nothing(tmp_path):
    root = _issue(tmp_path, layer=ON)
    _ticked_page(root)
    sup.base.edit(root, current_phase="ship")
    _ok(render(root))
    assert _dod_block(root)[0] == "Definition of Done: 0 of 7 met, 7 open"
    _, report = _report(root)
    row = _row(report, "dod-evidence-typed")
    assert row["status"] == "fail" and all(i in row["detail"] for i in ITEMS), row
    listed = [c for c in report["checks"] if c["guardrail"] == "stage:verify:exit"]
    assert [c["name"] for c in listed] == ITEMS
    assert all(c["status"] == "fail" and "not recorded" in c["detail"] for c in listed), listed
    # Neither reads the checklist section reader, and only migrate reads page tags.
    pkg = ROOT / "cli" / "compass_pkg"
    stage_lists = ast.parse((pkg / "stage_lists.py").read_text("utf-8"))
    imported = {a.name for n in ast.walk(stage_lists) if isinstance(n, ast.ImportFrom)
                and n.module == "compass_pkg.doc_sections" for a in n.names}
    assert not imported & {"section", "sections", "visible", "list_heading", "normal"}, imported
    checks = ast.parse((pkg / "checks.py").read_text("utf-8"))
    fn = next(n for n in ast.walk(checks) if isinstance(n, ast.FunctionDef)
              and n.name == "_check_dod_evidence_typed")
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)} | \
        {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    assert not names & {"_parse_dod_lines", "doc_sections", "dod_tag_problems"}, names
    readers = []
    for path in sorted(pkg.glob("*.py")):
        if path.name == "checks.py":
            continue
        text = path.read_text("utf-8")
        if "_parse_dod_lines" in text or "dod_tag_problems" in text:
            readers.append(path.name)
    assert set(readers) <= {"migrate.py"}, readers


# --- DCJ-27 -----------------------------------------------------------------

def test_dcj_27_recording_unlisted_item_or_wrong_evidence_refused(tmp_path):
    root = _issue(tmp_path)
    _evidence(root, "EV-T", "test-run")
    path = _file(root, "c.txt")

    def refused(*argv, names):
        before = manifest_file(root).read_bytes()
        code, out, err = run(root, *argv, "--issue", SLUG)
        assert code == 2, out + err
        for name in names:
            assert name in out + err, (name, out + err)
        assert manifest_file(root).read_bytes() == before
        return out + err

    text = refused("gate", "pass", "verify.correctness", "--evidence", "EV-T",
                   "--meets", "dod-perf-budget", names=["dod-perf-budget", *ITEMS])
    assert manifest(root)["gates"][0]["status"] == "pending", text
    refused("evidence", "add", "EV-C", "--type", "consistency-check", "--path", path,
            "--meets", "dod-suite-green", names=["consistency-check", "test-run"])
    refused("follow-up", "add", "FU-9", "--defers", "dod-perf-budget", "--summary", "later",
            names=["dod-perf-budget"])
    refused("follow-up", "add", "FU-9", "--summary", "  ", names=["summary"])


# --- DCJ-28 -----------------------------------------------------------------

def _approve_check(root, approver, check="dod-no-lint-errors"):
    return sup.base.approve(root, "--check", check, approver=approver, role="maintainer",
                            scope="lint")


def test_dcj_28_person_ticks_item_from_declared_approvers(tmp_path):
    root = _issue(tmp_path / "declared")
    before = manifest_file(root).read_bytes()
    for refused in ("alex", "agent"):
        code, out, err = _approve_check(root, refused)
        assert code == 2, out + err
        assert manifest_file(root).read_bytes() == before
    _ok(_approve_check(root, "jed72"))
    _ok(render(root))
    assert any("ticked by jed72" in x and "dod-no-lint-errors" in x for x in _dod_block(root))
    # A project that declares no approvers: its owner may tick the item.
    owner_only = _issue(tmp_path / "owner", layer={"schema": 1, "owner": "jed72"})
    code, out, err = _approve_check(owner_only, "alex")
    assert code == 2, out + err
    _ok(_approve_check(owner_only, "jed72"))


# --- DCJ-29 -----------------------------------------------------------------

def test_dcj_29_resolved_follow_up_counts_as_met(tmp_path):
    root = _issue(tmp_path)
    _record_all(root)
    for fu in ("FU-3", "FU-4"):
        _ok(run(root, "follow-up", "resolve", "--issue", SLUG, fu))
    lines = _dod_block(root)
    assert lines[0] == "Definition of Done: 7 of 7 met", lines[0]
    joined = "\n".join(lines)
    assert "met, FU-3 resolved" in joined and "met, FU-4 resolved" in joined


# --- DCJ-30 -----------------------------------------------------------------

def test_dcj_30_nothing_to_check_before_report_written(tmp_path):
    root = sup.project(tmp_path / "regular")
    (Path(root) / DOCS / "verification-report.md").unlink()     # not written at implement
    sup.base.edit(root, current_phase="implement")
    entry = next(a for a in manifest(root)["artifacts"] if a["kind"] == "verification-report")
    assert not entry.get("path")
    _, report = _report(root)
    assert _row(report, "dod-evidence-typed")["status"] == "nothing-to-check"
    quick = sup.project(tmp_path / "quick", assessment={"size": "small", "risk": "contained"})
    (Path(quick) / DOCS / "verification-report.md").unlink(missing_ok=True)
    kinds = {a["kind"] for a in manifest(quick).get("artifacts") or []}
    assert "verification-report" not in kinds, kinds
    _, report = _report(quick)
    assert _row(report, "dod-evidence-typed")["status"] == "nothing-to-check"


# --- DCJ-31 -----------------------------------------------------------------

def test_dcj_31_cross_issue_follow_up_still_blocks(tmp_path):
    root = _issue(tmp_path)
    body = manifest(root)
    body["evidence"] = [{"id": f"EV-M{n}", "type": "manual-review", "path": "evidence/x.txt",
                         "meets": [item]} for n, item in enumerate(ITEMS)]
    sup.base.write_manifest(root, body)
    other = Path(root) / ".compass" / "work" / "issue-b"
    other.mkdir(parents=True)
    (other / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": "issue-b", "created": "2026-10-09",
        "follow_ups": [{"id": "FU-7", "status": "outstanding", "summary": "later",
                        "target_task": SLUG}]}), encoding="utf-8")
    _, report = _report(root)
    row = _row(report, "dod-evidence-typed")
    assert row["status"] == "fail" and "issue-b" in row["detail"] and "FU-7" in row["detail"], row
    _ok(run(root, "follow-up", "resolve", "--issue", "issue-b", "FU-7"))
    _, report = _report(root)
    assert _row(report, "dod-evidence-typed")["status"] == "pass"


# --- DCJ-32 -----------------------------------------------------------------

def test_dcj_32_dor_block_and_stage_lists_read_records(tmp_path):
    root = sup.project(tmp_path, compass_yml=ON, assessment=SPEC)
    assert manifest(root)["delivery_approach"] == "full"
    write_doc(root, "requirements-review", "# RR\n\n" + block("dor"))
    sup.base.edit(root, current_phase="plan")
    for item in READY[:-1]:
        _ok(sup.base.approve(root, "--check", item, approver="jed72", role="maintainer",
                             scope="ready"))
    _ok(render(root))
    lines = _dod_block(root, "dor", "requirements-review")
    assert lines[0] == "Definition of Ready: 6 of 7 met, 1 open", lines[0]
    assert len([x for x in lines[1:] if x.strip()]) == 7
    _, report = _report(root)
    rows = {c["name"]: c for c in report["checks"] if c["guardrail"] == "stage:plan:entry"}
    assert rows["dor-approach-still-fits"]["status"] == "fail"
    assert "not recorded" in rows["dor-approach-still-fits"]["detail"]
    assert all(rows[i]["status"] == "pass" for i in READY[:-1]), rows


# --- DCJ-33 -----------------------------------------------------------------

def test_dcj_33_blocks_list_configured_items(tmp_path):
    # `stages.verify` is locked, so removing an item needs a waiver on the entry. A project
    # waiver stands in for the issue layer: the issue layer's waiver needs an approval record
    # that names it, and the blocks read the same resolved list either way.
    layer = {**LAYER,
             "checks": {**LAYER["checks"],
                        "dod-perf-budget": {"statement": "Performance stays within budget.",
                                            "kind": "human", "severity": "blocking",
                                            "on_skipped": "not-applicable"}},
             "stages": {"verify": {
                 "set": {"exit": {"add": ["dod-perf-budget"], "remove": ["dod-coverage-floor"]}},
                 "waiver": {"reason": "Coverage is judged elsewhere in this project.",
                            "approved_by": "jed72", "approved_on": "2026-10-09"}}}}
    for capability in (True, False):
        folder = tmp_path / ("on" if capability else "off")
        root = _issue(folder, layer={**layer, "capabilities": {"entry-exit-evaluation": capability}})
        _ok(render(root))
        lines = _dod_block(root)
        listed = [i for i in ITEMS + ["dod-perf-budget"] if any(i in x for x in lines[1:])]
        assert len(listed) == 7 and "dod-perf-budget" in listed, listed
        assert "dod-coverage-floor" not in listed
        assert lines[0] == "Definition of Done: 0 of 7 met, 7 open"


# --- DCJ-34 -----------------------------------------------------------------

STATE_TABLES = {
    "acceptance-criteria": ["| Traceability id | Serves intent | Has a failing test"],
    "verification-report": ["| Scenario id | Title | Result |", "| Record | What it covers |",
                            "| Gate | Required by | Status |", "| Failure mode | Why no scenario",
                            "**Every scenario passes**", "**TDD suite green**"],
    "requirements-review": ["**Summary is filled**", "**Delivery approach still fits**"],
}
BLOCKS = {
    "acceptance-criteria": ["coverage"],
    "verification-report": ["coverage", "evidence", "gates", "decisions-taken", "dod"],
    "requirements-review": ["dor"],
}


def test_dcj_34_templates_carry_blocks_not_state_tables(tmp_path):
    root = sup.project(tmp_path, assessment=SPEC)
    for kind, kinds in BLOCKS.items():
        out = _ok(run(root, "issue", "template", "show", kind, "--issue", SLUG))
        from compass_pkg import rendered_blocks as rb
        found = rb.parse(out, kind)
        assert [b.kind for b in found.blocks] == kinds or set(kinds) <= {b.kind for b in found.blocks}, \
            (kind, [b.kind for b in found.blocks])
        for block_ in found.blocks:
            assert block_.end == block_.start + 1, "a block is empty between its markers"
        for table in STATE_TABLES[kind]:
            assert table not in out, (kind, table)
        assert "(evidence: EV-" not in out and "(follow-up: FU-" not in out, kind
