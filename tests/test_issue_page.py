"""The issue page, the related and decisions blocks (issue `documents-carry-judgement`,
groups E and F: DCJ-39 to DCJ-53).

Each test builds a temporary git repository (`pages_support`) and drives
`cli/compass` the way a person does. A few tests run in this process so they can
replace the shared detail function. Each test name starts with its scenario id. No
test reads or writes this checkout's own `.compass/work` or `docs/compass`
(DCJ-63 proves it).
"""
from __future__ import annotations

import datetime
import re
import subprocess
from pathlib import Path

import pytest
import yaml

import pages_support as ps
import rendered_blocks_support as sup
from pages_support import (CREATED, DOCS, SLUG, add_issue, block, blocks, close_issue,
                           docs_of, full_issue, manifest, page, run, set_fields, text_of)

PAGE_ORDER = ["header", "ask", "decision-required", "acceptance", "related", "decisions",
              "artifacts", "traceability", "deliberately-omitted", "follow-ups"]


def _render(root, *extra):
    code, out, err = sup.render(root, *extra)
    assert code == 0, out + err
    return out


# --- DCJ-39 -----------------------------------------------------------------

def test_dcj_39_issue_page_blocks_in_order_reader_test(tmp_path):
    root = full_issue(tmp_path)
    set_fields(root, SLUG, decisions_taken=[
        {"id": "Q1", "question": "Which folder?", "resolution": "The docs folder",
         "by": "spec-author", "stage": "refine", "status": "confirmed"}])
    _render(root)

    path = page(root)
    assert [k for k, _ in blocks(path)] == PAGE_ORDER
    # Each reader question is answered from its named block alone.
    assert "People cannot find the state." in "\n".join(block(path, "ask"))
    assert any(word in "\n".join(block(path, "header"))
               for word in ("in-progress", "in-review", "ready"))
    acceptance = "\n".join(block(path, "acceptance"))
    assert acceptance.count("not yet passed") == 1 and acceptance.count("passed") >= 2
    assert "base-work" in "\n".join(block(path, "related"))
    decisions = "\n".join(block(path, "decisions"))
    assert "DD-1" in decisions and "DD-2" in decisions and "Q1" in decisions


# --- DCJ-40 -----------------------------------------------------------------

def test_dcj_40_ask_from_intent_on_first_screen(tmp_path):
    root = full_issue(tmp_path)
    hostile = ("## Problem\n\nOpening <!-- compass:render gates --> text.\n\n"
               "<!-- compass:render gates -->\n```\nunbalanced fence\n<!-- an unclosed comment\n\n")
    intent = Path(root) / DOCS / "intent.md"
    body = text_of(intent).replace("## Problem\n\nPeople cannot find the state.\n\n", hostile)
    intent.write_text(body, encoding="utf-8")
    _render(root)

    path = page(root)
    ask = "\n".join(block(path, "ask"))
    for name in ("Problem", "Desired outcome", "Success signals", "Non-goals"):
        assert name in ask
    assert "One page shows it." in ask and "No new dependency." in ask
    assert "People" not in ask
    assert len(block(path, "header")) <= 12
    lines = text_of(path).splitlines()
    opening = next(i for i, line in enumerate(lines) if line.strip() == "<!-- compass:render ask -->")
    assert opening < 20
    # The page parses to the ten blocks it was meant to hold.
    assert [k for k, _ in blocks(path)] == PAGE_ORDER

    intent.write_text(text_of(intent).replace("unbalanced fence", "A fresh problem text"),
                      encoding="utf-8")
    code, out, err = run(root, "follow-up", "add", "FU-9", "--summary", "after the edit")
    assert code == 0, out + err
    assert "A fresh problem text" in "\n".join(block(path, "ask"))


# --- DCJ-41 -----------------------------------------------------------------

def test_dcj_41_ask_without_intent(tmp_path):
    root = sup.rich_issue(tmp_path)
    (Path(root) / DOCS / "delivery-approach.md").write_text(
        "# Delivery approach\n\n> **Issue:** Make the greeting say hello.\n", encoding="utf-8")
    _render(root)
    ask = "\n".join(block(page(root), "ask"))
    assert "Make the greeting say hello." in ask
    assert "First scenario" in ask

    add_issue(root, "bare")
    code, out, err = sup.run(root, "issue", "render", "--issue", "bare")
    assert code == 0, out + err
    assert block(page(root, "bare"), "ask") == ["No statement of the ask is recorded."]


# --- DCJ-42 -----------------------------------------------------------------

def test_dcj_42_header_current_state_words(tmp_path):
    root = sup.project(tmp_path)
    body = manifest(root)
    body["delivery_approach"] = "standard"       # a retired approach name
    body["status"] = "landed"                    # a retired done status word
    body["land_timestamp"] = "2026-10-12T09:30:00+00:00"
    body["owner"] = "jed72"
    body["gates"] = [{"id": f"verify.g{n}", "status": "pass", "evidence": []} for n in range(9)]
    sup.base.write_manifest(root, body)
    _render(root)

    head = "\n".join(block(page(root), "header"))
    assert SLUG in head
    assert "regular" in head
    assert "done (completed)" in head
    assert "gates 9/9" in head
    assert "jed72" in head
    assert "2026-10-10" in head and "2026-10-12" in head
    assert re.search(r"\bstage\b", head, re.I)
    for word in ("landed", "standard", "active", "queued", "parked", "abandoned"):
        assert not re.search(rf"\b{word}\b", head), (word, head)

    body = manifest(root)
    del body["owner"]
    sup.base.write_manifest(root, body)
    _render(root)
    assert "not recorded" in "\n".join(block(page(root), "header"))


# --- DCJ-43 -----------------------------------------------------------------

def test_dcj_43_acceptance_and_traceability_blocks(tmp_path):
    root = sup.rich_issue(tmp_path)
    sup.add_records(root, **{"acceptance-TRC-2": "TRC-2"})
    # The first scenario has a green record, the second an acceptance record, the third a red one.
    (ps.work_of(root, SLUG) / "evidence" / "red-TRC-2.json").unlink()
    sup.add_records(root, **{"red-TRC-3": "TRC-3"})
    _render(root)

    path = page(root)
    acceptance = block(path, "acceptance")
    rows = {sid: next(x for x in acceptance if sid in x) for sid in ("TRC-1", "TRC-2", "TRC-3")}
    assert "First scenario" in rows["TRC-1"] and "not yet passed" not in rows["TRC-1"]
    assert "passed" in rows["TRC-2"] and "not yet passed" not in rows["TRC-2"]
    assert "not yet passed" in rows["TRC-3"]
    chart = "\n".join(block(path, "traceability"))
    assert "```mermaid" in chart and "flowchart LR" in chart
    assert any("TRC-3" in line and ":::open" in line for line in chart.splitlines())
    assert not any("TRC-1" in line and ":::open" in line for line in chart.splitlines())
    assert "INT-1" in chart

    # More than 25 scenarios: one summary node per intent.
    body = manifest(root)
    body["scenarios"] = [{"id": f"S-{n}", "title": f"Case {n}", "intent": "INT-1", "tests": []}
                         for n in range(26)]
    sup.base.write_manifest(root, body)
    _render(root)
    chart = "\n".join(block(path, "traceability"))
    assert "S-17" not in chart.split("```mermaid", 1)[1]
    assert "26 scenarios" in chart


# --- DCJ-44 -----------------------------------------------------------------

def test_dcj_44_artifacts_block_links_status_approver(tmp_path):
    root = sup.rich_issue(tmp_path)
    for name in ("technical-design", "acceptance-criteria"):
        sup.write_doc(root, name, f"# {name}\n")
    body = manifest(root)
    for entry in body["artifacts"]:
        if entry["kind"] == "technical-design":
            entry.update(status="approved", approved_by="jed72", approved_at="2026-10-10",
                         traditional_name="Design document")
        if entry["kind"] == "acceptance-criteria":
            entry.update(status="approved", approved_by="compass issue artifact set",
                         approved_at="2026-10-10")
        if entry["kind"] == "rollback-plan":
            entry["path"] = f"{DOCS}/rollback-plan.md"
        if entry["kind"] == "distribution-map":
            entry.update(status="omitted", reason="one builder, nothing to distribute")
    if not any(e["kind"] == "rollback-plan" for e in body["artifacts"]):
        body["artifacts"].append({"id": "ART-ROLLBACK_PLAN", "kind": "rollback-plan",
                                  "status": "draft", "depth": "thorough", "reason": "fixture",
                                  "path": f"{DOCS}/rollback-plan.md"})
    sup.base.write_manifest(root, body)
    (Path(root) / DOCS / "rollback-plan.md").unlink(missing_ok=True)
    _render(root)

    path = page(root)
    artifacts = block(path, "artifacts")
    rows = {kind: next((x for x in artifacts if kind in x), "") for kind in
            ("technical-design", "acceptance-criteria", "rollback-plan", "distribution-map")}
    assert "(technical-design.md)" in rows["technical-design"]
    assert "approved" in rows["technical-design"] and "jed72" in rows["technical-design"]
    assert "Design document" in rows["technical-design"]
    assert "(acceptance-criteria.md)" in rows["acceptance-criteria"]
    assert "compass issue artifact set" in rows["acceptance-criteria"]
    assert "traditional" not in rows["acceptance-criteria"]
    assert "not written yet" in rows["rollback-plan"] and "](" not in rows["rollback-plan"]
    assert rows["distribution-map"] == ""
    omitted = "\n".join(block(path, "deliberately-omitted"))
    assert "distribution-map" in omitted and "one builder, nothing to distribute" in omitted


# --- DCJ-45 -----------------------------------------------------------------

def _three_of_nine(tmp_path):
    root = sup.rich_issue(tmp_path)
    body = manifest(root)
    ids = ["verify.correctness", "verify.governance", "verify.traceability", "verify.regression",
           "verify.clarity", "verify.security", "verify.analyze", "verify.architecture",
           "ship.confirm"]
    body["gates"] = [{"id": g, "status": "pass" if n < 3 else "pending", "evidence": []}
                     for n, g in enumerate(ids)]
    sup.base.write_manifest(root, body)
    return root


def _board(root, out):
    code, o, e = run(root, "board", "render", "--no-open", "--out", str(out))
    assert code == 0, o + e
    return Path(out).read_text(encoding="utf-8")


def test_dcj_45_board_panel_and_issue_page_share_one_function(tmp_path, monkeypatch):
    root = _three_of_nine(tmp_path)
    _render(root)
    board_file = tmp_path / "board.html"
    html = _board(root, board_file)
    head = "\n".join(block(page(root), "header"))
    assert "gates 3/9" in head and "Gates 3/9" in html

    sup.base.add_evidence(root, "EV-T")
    code, out, err = run(root, "gate", "pass", "verify.regression", "--evidence", "EV-T")
    assert code == 0, out + err
    html = _board(root, board_file)
    assert "gates 4/9" in "\n".join(block(page(root), "header")) and "Gates 4/9" in html

    # One function: replace it and both surfaces follow.
    from compass_pkg import board_cmd, issue_detail, issue_page, render_cmd  # noqa: F401
    # The modules that draw the header and the panel are imported before the function is
    # replaced, so a module that bound the function by name keeps the original and shows it.
    real = issue_detail.detail

    def stage_plan(manifest_, task_dir):
        made = real(manifest_, task_dir)
        return issue_detail.IssueDetail(made.approach, made.state, "breakdown", made.gates_passed,
                                        made.gates_total, made.stage_problem)

    monkeypatch.setattr(issue_detail, "detail", stage_plan)
    code, out, err = sup.inproc(root, monkeypatch)
    assert code == 0, out + err
    assert re.search(r"stage\W+breakdown", "\n".join(block(page(root), "header")), re.I)
    html = board_cmd.build_page(str(root), str(Path(root) / ".compass" / "work"), False,
                                datetime.datetime.now())
    assert "stage breakdown" in html.lower()

    # `compass flow --json` keeps its keys.
    monkeypatch.undo()
    code, out, err = run(root, "flow", "--json")
    assert code == 0, out + err
    import json
    data = json.loads(out)
    assert sorted(data) == ["board", "counts", "friction", "sections", "summary", "title"]
    rows = [r for section in data["sections"].values() for r in section]
    mine = next(r for r in rows if r["slug"] == SLUG)
    assert sorted(mine) == ["also_in", "assessment", "created", "delivery_approach", "evidence",
                            "gate_list", "gates", "lane", "manifest_path", "policy_rules_fired",
                            "readiness", "recommendation", "set_aside", "slug", "stage",
                            "stage_depths", "state", "tree", "unplaceable"]
    assert mine["gates"] == "4/9"


# --- DCJ-46 -----------------------------------------------------------------

def test_dcj_46_issue_page_names_board_command_no_path(tmp_path):
    root = full_issue(tmp_path)
    board_file = tmp_path / "board.html"
    _render(root)
    before = text_of(page(root))
    _board(root, board_file)
    assert board_file.exists()
    add_issue(root, "done-one")
    close_issue(root, "done-one")
    code, out, err = ps.render_all(root)
    assert code == 0, out + err

    assert "compass board render" in "\n".join(block(page(root), "header"))
    absolute = re.compile(r"(?<![\w.])(/(?:Users|home|private|tmp|var)/|[A-Za-z]:\\)")
    documents = [p for p in (Path(root) / "docs" / "compass").rglob("*.md")]
    assert documents
    for document in documents:
        for kind, lines in blocks(document):
            for line in lines:
                assert not absolute.search(line), (document, kind, line)
    board_file.unlink()
    _render(root)
    assert text_of(page(root)) == before or "compass board render" in text_of(page(root))
    _board(root, board_file)
    after = text_of(page(root))
    board_file.unlink()
    _render(root)
    assert text_of(page(root)) == after


# --- DCJ-47 -----------------------------------------------------------------

def test_dcj_47_no_git_name_in_any_block(tmp_path):
    root = full_issue(tmp_path)
    sup.git(root, "config", "user.name", "Jane Q Example")
    (Path(root) / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@6\nowner: jed72\n"
        "checks: {}\n", encoding="utf-8")
    entry = ("# gov-decision\n\n## Decided by\n\nJane Q Example\n\n## Date\n\n2026-10-09\n\n"
             "## Supersedes\n\nNothing.\n\n## Decision\n\nKeep the name out.\n\n## Why\n\nPrivacy.\n\n"
             f"## Evidence\n\nIssue `{SLUG}`.\n")
    ledger = Path(root) / "governance" / "decisions"
    ledger.mkdir(parents=True)
    (ledger / "2026-10-09-gov-decision.md").write_text(entry, encoding="utf-8")
    body = manifest(root)
    body["owner"] = "jed72"
    for entry in body["artifacts"]:
        if entry["kind"] == "technical-design":
            entry.update(status="approved", approved_by="jed72", approved_at="2026-10-09")
    body["evidence"].append({"id": "EV-AP", "type": "human-approval", "check": "design-review",
                             "approver": "jed72", "role": "maintainer", "scope": "design",
                             "decision": "approved", "timestamp": "2026-10-09T10:00:00+00:00"})
    sup.base.write_manifest(root, body)
    code, out, err = ps.render_all(root)
    assert code == 0, out + err

    for document in (Path(root) / "docs" / "compass").rglob("*.md"):
        assert "Jane Q Example" not in text_of(document), document
    decisions = "\n".join(block(page(root), "decisions"))
    assert "gov-decision" in decisions and "Decided by" not in decisions
    assert "jed72" in "\n".join(block(page(root), "header"))


# --- DCJ-48 -----------------------------------------------------------------

def test_dcj_48_hand_written_readme_left_alone(tmp_path):
    root = sup.rich_issue(tmp_path)
    readme = page(root)
    written = b"# My page\n\nWritten by a person, no block.\n"
    readme.write_bytes(written)
    code, out, err = sup.render(root)
    assert code == 0, out + err
    assert readme.read_bytes() == written
    assert "hand-written" in out and "not rendered" in out

    set_fields(root, SLUG, gates=[{"id": "verify.correctness", "status": "pass", "evidence": []}])
    code, out, err = run(root, "check", "--issue", SLUG, "--verbose")
    line = next(x for x in out.splitlines() if "FAIL rendered-blocks-current" in x)
    assert "holds no rendered block" in out, out
    assert "README.md" in out and line


# --- DCJ-49 -----------------------------------------------------------------

def _related_fixture(tmp_path):
    root = sup.rich_issue(tmp_path)
    for slug in ("old-work", "next-work", "carrier", "origin", "later-fix", "side-work",
                 "spin-off"):
        add_issue(root, slug)
    set_fields(root, "next-work")
    body = manifest(root)
    body["repairs"] = "old-work"
    body["follow_ups"] = [{"id": "FU-1", "status": "outstanding", "summary": "next",
                           "target_task": "next-work"}]
    body["landed_by"] = [{"issue": "carrier"}]
    body["raised_by"] = {"issue": "origin", "found_at": "verify"}
    sup.base.write_manifest(root, body)
    set_fields(root, "later-fix", repairs=SLUG)
    set_fields(root, "side-work", follow_ups=[
        {"id": "FU-1", "status": "outstanding", "summary": "x", "target_task": SLUG}])
    set_fields(root, "spin-off", raised_by={"issue": SLUG, "found_at": "verify"})
    close_issue(root, "old-work")
    return root


def test_dcj_49_related_block_both_directions(tmp_path):
    root = _related_fixture(tmp_path)
    code, out, err = sup.render(root)
    assert code == 0, out + err
    related = block(page(root), "related")
    text = "\n".join(related)
    for slug, word in (("old-work", "repairs"), ("next-work", "follow-up target"),
                       ("carrier", "delivered by"), ("origin", "raised from"),
                       ("later-fix", "repaired by"), ("side-work", "follow-up from"),
                       ("spin-off", "raised here")):
        line = next((x for x in related if slug in x), None)
        assert line is not None, (slug, text)
        assert word in line, (slug, word, line)
        assert f"(../{CREATED}-{slug}/README.md)" in line, line
    assert "done (completed)" in next(x for x in related if "old-work" in x)


# --- DCJ-50 -----------------------------------------------------------------

def test_dcj_50_depends_on_and_parent_only_when_present(tmp_path):
    root = sup.project(tmp_path)
    for slug in ("schema-work", "epic-one", "plain-work", "api-work", "ui-work"):
        add_issue(root, slug)
    set_fields(root, "api-work", depends_on=["schema-work"], parent="epic-one")
    set_fields(root, "ui-work", depends_on=["api-work"])
    code, out, err = ps.render_all(root)
    assert code == 0, out + err
    api = "\n".join(block(page(root, "api-work"), "related"))
    assert "schema-work" in api and "depends on" in api
    assert "ui-work" in api and "depended on by" in api
    assert "epic-one" in api and "parent" in api
    assert "api-work" in "\n".join(block(page(root, "epic-one"), "related"))
    assert "child" in "\n".join(block(page(root, "epic-one"), "related"))
    plain = "\n".join(block(page(root, "plain-work"), "related"))
    for word in ("depends on", "depended on by", "parent", "child"):
        assert word not in plain


# --- DCJ-51 -----------------------------------------------------------------

def test_dcj_51_no_links_none_and_missing_issue_unlinked(tmp_path):
    root = sup.project(tmp_path)
    add_issue(root, "alone")
    add_issue(root, "broken", repairs="no-such-issue")
    code, out, err = ps.render_all(root)
    assert code == 0, out + err
    assert block(page(root, "alone"), "related") == ["None"]
    broken = "\n".join(block(page(root, "broken"), "related"))
    assert "no-such-issue" in broken and "not found" in broken
    assert "](" not in broken


# --- DCJ-52 -----------------------------------------------------------------

def test_dcj_52_decisions_block_lists_all_three_kinds(tmp_path):
    root = sup.rich_issue(tmp_path)
    (Path(root) / "architecture" / "decisions").mkdir(parents=True)
    (Path(root) / "architecture" / "decisions" / "ADR-049-the-cache.md").write_text(
        "---\nid: ADR-049\n---\n", encoding="utf-8")
    ledger = Path(root) / "governance" / "decisions"
    ledger.mkdir(parents=True)
    (ledger / "2026-10-09-cache-rule.md").write_text(
        "# cache-rule\n\n## Decided by\n\nsomeone\n\n## Decision\n\nThe cache rule holds.\n\n"
        f"## Evidence\n\nIssue `{SLUG}`.\n", encoding="utf-8")
    sup.write_doc(root, "technical-design",
                  "# TD\n\n### DD-1 - First choice\n\nSee ADR-049 for why.\n\n"
                  "### DD-2 - Second choice\n\nScope: project\n\nNothing else.\n")
    set_fields(root, SLUG, decisions_taken=[
        {"id": "Q1", "question": "Which?", "resolution": "This one", "by": "spec-author",
         "stage": "refine", "status": "confirmed"},
        {"id": "Q2", "question": "Which flag?", "resolution": "Neither", "by": "planner",
         "stage": "plan", "status": "reopened", "reason": "the flag came back"}])
    _render(root)
    lines = block(page(root), "decisions")
    text = "\n".join(lines)
    dd1 = next(x for x in lines if "DD-1" in x)
    assert "First choice" in dd1 and "ADR-049-the-cache.md" in dd1
    dd2 = next(x for x in lines if "DD-2" in x)
    assert "Second choice" in dd2 and "project" in dd2 and "ADR" not in dd2
    gov = next(x for x in lines if "cache-rule" in x)
    assert "The cache rule holds." in gov and "governance/decisions/2026-10-09-cache-rule.md" in gov
    q1 = next(x for x in lines if "Q1" in x)
    assert "This one" in q1 and "confirmed" in q1
    q2 = next(x for x in lines if "Q2" in x)
    assert "reopened" in q2 and "the flag came back" in q2
    del text

    add_issue(root, "quiet")
    code, out, err = sup.run(root, "issue", "render", "--issue", "quiet")
    assert code == 0, out + err
    assert block(page(root, "quiet"), "decisions") == ["None"]


# --- DCJ-53 -----------------------------------------------------------------

def test_dcj_53_longer_slug_decision_not_listed(tmp_path):
    root = sup.project(tmp_path)
    add_issue(root, "board")
    add_issue(root, "board-colours")
    ledger = Path(root) / "governance" / "decisions"
    ledger.mkdir(parents=True)
    (ledger / "2026-10-09-colours.md").write_text(
        "# colours\n\n## Decided by\n\nsomeone\n\n## Decision\n\nUse two colours.\n\n"
        "## Evidence\n\nIssue board-colours.\n", encoding="utf-8")
    docs = Path(root) / docs_of("board")
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "technical-design.md").write_text(
        "# TD\n\n### DD-1 - A choice\n\nSee ADR-999.\n", encoding="utf-8")
    body = yaml.safe_load((ps.work_of(root, "board") / "manifest.yml").read_text())
    body["artifacts"] = [{"id": "ART-TD", "kind": "technical-design", "status": "draft",
                          "depth": "thorough", "reason": "x",
                          "path": f"{docs_of('board')}/technical-design.md"}]
    (ps.work_of(root, "board") / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False))
    code, out, err = run(root, "issue", "render", "--issue", "board")
    assert code == 0, out + err
    text = "\n".join(block(page(root, "board"), "decisions"))
    assert "colours" not in text
    dd = next(x for x in text.splitlines() if "DD-1" in x)
    assert "ADR-999" not in dd or "](" not in dd
    code, out, err = run(root, "issue", "render", "--issue", "board-colours")
    assert code == 0, out + err
    assert "colours" in "\n".join(block(page(root, "board-colours"), "decisions"))
