"""The checklists of the document templates render from the effective view.

The requirements review holds the entry lists and the verification report holds
the exit lists. A project that changes a stage's `entry` or `exit` list gets a
document whose checklist matches: a listed check the template already words
keeps the template's own text, a listed check it does not word becomes a
generated line, a check the list drops disappears, and a list on another stage
becomes its own section. The shipped default renders the template file byte for
byte. The typed tag rule of `dod-evidence-typed` reads every exit list's
section, and a human check is ticked under its own list's heading.

Scenario ids: `TR-1` to `TR-8` (issue `templates-render-lists`). Each test name
starts with its scenario id.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_generation_store import SLUG, _evaluate_write, _manifest, _project, _run, _write_manifest  # noqa: E402
from test_ready_and_done_data import (DONE_IDS, DONE_TEMPLATE, READY_IDS,  # noqa: E402
                                      READY_TEMPLATE, template_items)

TEMPLATES = ROOT / "templates"
READY = template_items(READY_TEMPLATE, "### Definition of Ready")
DONE = template_items(DONE_TEMPLATE, "### Definition of Done")
KINDS = {"requirements-review": READY_TEMPLATE, "verification-report": DONE_TEMPLATE}


@pytest.fixture(autouse=True)
def _inside_the_scratch_project(tmp_path, monkeypatch):
    """Readers find the project from the working directory; keep that the
    scratch project, never the repository the tests run from."""
    monkeypatch.chdir(tmp_path)


def _render(root, kind, *extra):
    return _run(root, "issue", "template", kind, "--issue", SLUG, *extra)


def _issue(tmp_path, compass_yml=None):
    """A project with one issue whose stored configuration is generation 1."""
    root, task_dir = _project(tmp_path, compass_yml=compass_yml or {"schema": 1})
    assert _evaluate_write(root)[0] == 0
    return root, task_dir


def _rendered_items(tmp_path, text, heading):
    path = tmp_path / "rendered.md"
    path.write_text(text, encoding="utf-8")
    return template_items(path, heading)


_HUMAN = {"kind": "human", "severity": "blocking", "on_skipped": "fail"}


# --- TR-1: the shipped default renders the template file --------------------------------------

@pytest.mark.parametrize("kind", sorted(KINDS))
def test_tr_1_the_default_renders_each_template_byte_for_byte(tmp_path, kind):
    root, _ = _issue(tmp_path)
    code, out, err = _render(root, kind)
    assert code == 0, out + err
    assert out == KINDS[kind].read_text(encoding="utf-8")


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_tr_1_a_project_with_no_configuration_renders_the_template_file(tmp_path, kind):
    (tmp_path / ".compass").mkdir()
    task_dir = tmp_path / ".compass" / "work" / SLUG
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(_manifest_body()), encoding="utf-8")
    code, out, err = _render(tmp_path, kind)
    assert code == 0, out + err
    assert out == KINDS[kind].read_text(encoding="utf-8")


def _manifest_body():
    from test_generation_store import MANIFEST
    return dict(MANIFEST)


# --- TR-2: a changed list renders the changed checklist ---------------------------------------

def test_tr_2_a_check_removed_from_the_ready_list_leaves_the_template(tmp_path):
    cfg = {"schema": 1, "stages": {"plan": {"set": {"entry": {"remove": ["dor-no-open-questions"]}}}}}
    root, _ = _issue(tmp_path, cfg)
    code, out, err = _render(root, "requirements-review")
    assert code == 0, out + err
    kept = [t for t in READY if not t.startswith("No open questions")]
    assert len(kept) == 6
    assert _rendered_items(tmp_path, out, "### Definition of Ready") == kept
    # What the template words for the kept items is unchanged, emphasis included.
    template = READY_TEMPLATE.read_text(encoding="utf-8")
    assert out == re.sub(r"- \[ \] \*\*No open questions\*\*[^\n]*\n", "", template)


def test_tr_2_a_reordered_done_list_renders_in_the_listed_order(tmp_path):
    cfg = {"schema": 1, "stages": {"verify": {"set": {"exit": list(reversed(DONE_IDS))}}}}
    root, _ = _issue(tmp_path, cfg)
    code, out, err = _render(root, "verification-report")
    assert code == 0, out + err
    assert _rendered_items(tmp_path, out, "### Definition of Done") == list(reversed(DONE))
    assert "- [ ] (follow-up: {{FU-id}}) *(carried to ship)* Every outstanding follow-up" in out


def test_tr_2_the_rest_of_the_document_is_untouched(tmp_path):
    cfg = {"schema": 1, "stages": {"verify": {"set": {"exit": {"remove": ["dod-suite-green"]}}}}}
    root, _ = _issue(tmp_path, cfg)
    out = _render(root, "verification-report")[1]
    template = DONE_TEMPLATE.read_text(encoding="utf-8")
    before, _, after = template.partition("- [ ] (evidence: {{EV-id}}) **Every scenario passes**")
    assert out.startswith(before) and out.endswith(template[template.index("\nNext stage:"):])


# --- TR-3: an added check renders a generated line -----------------------------------------------

def _added(stage, side, check_id):
    return {"checks": {check_id: dict(_HUMAN, statement=f"{check_id} statement.")},
            "stages": {stage: {"set": {side: {"add": [check_id]}}}}}


def test_tr_3_an_added_ready_check_renders_a_plain_generated_line(tmp_path):
    cfg = {"schema": 1, **_added("plan", "entry", "release-notes-drafted")}
    root, _ = _issue(tmp_path, cfg)
    out = _render(root, "requirements-review")[1]
    assert _rendered_items(tmp_path, out, "### Definition of Ready") == \
        READY + ["release-notes-drafted statement."]
    assert "\n- [ ] release-notes-drafted statement.\n\nNext stage:" in out


def test_tr_3_an_added_done_check_renders_a_line_that_can_be_deferred(tmp_path):
    cfg = {"schema": 1, **_added("verify", "exit", "release-notes-checked")}
    root, _ = _issue(tmp_path, cfg)
    out = _render(root, "verification-report")[1]
    assert "\n- [ ] (evidence: {{EV-id}}) release-notes-checked statement.\n\nNext stage:" in out
    assert _rendered_items(tmp_path, out, "### Definition of Done") == \
        DONE + ["release-notes-checked statement."]


def test_tr_3_a_check_that_is_not_a_tick_renders_no_box(tmp_path):
    cfg = {"schema": 1,
           "checks": {"list-scenarios-have-tests": {
               "statement": "Every scenario has a test.", "kind": "deterministic",
               "impl": "scenarios-have-tests", "severity": "blocking", "on_skipped": "fail"}},
           "stages": {"plan": {"set": {"entry": {"add": ["list-scenarios-have-tests"]}}}}}
    root, _ = _issue(tmp_path, cfg)
    code, out, err = _render(root, "requirements-review")
    assert code == 0, err
    assert out == READY_TEMPLATE.read_text(encoding="utf-8")


class _View:
    """Just enough of an EffectiveView for the renderer."""

    def __init__(self, config):
        self.config = config

    def stage_order(self):
        return tuple(self.config["stages"])


def test_tr_3_a_box_or_heading_inside_a_comment_is_not_read():
    from compass_pkg import template_lists
    text = ("# Report\n\n<!-- example:\n### Definition of Done\n- [ ] quoted box\n-->\n\n"
            "### Definition of Done\n\n<!-- more\n- [ ] another quoted box\n-->\n\n"
            "- [ ] **Real** - first line\n      second line\n\nNext stage: x\n")
    view = _View({"checks": {"c": dict(_HUMAN, statement="Real - first line second line"),
                             "d": dict(_HUMAN, statement="Added.")},
                  "stages": {"verify": {"exit": ["c", "d"]}}})
    out = template_lists.render(text, view, "verification-report")
    assert out == text.replace("\nNext stage:", "- [ ] (evidence: {{EV-id}}) Added.\n\nNext stage:")


def test_tr_3_the_headings_the_renderer_writes_are_the_ones_the_tag_rule_reads():
    from compass_pkg import checks, stage_lists
    for stage in ("verify", "implement", "ship", "my-stage", "plan"):
        assert checks._EXIT_HEADING_RE.match(stage_lists.list_heading(stage, "exit")), stage
    for stage in ("plan", "define", "verify"):
        assert not checks._EXIT_HEADING_RE.match(stage_lists.list_heading(stage, "entry")), stage
    assert stage_lists.list_heading("verify", "exit") == "Definition of Done"
    assert stage_lists.list_heading("plan", "entry") == "Definition of Ready"


# --- TR-4: a list on another stage becomes its own section ----------------------------------------

def test_tr_4_an_exit_list_on_implement_renders_before_next_stage(tmp_path):
    cfg = {"schema": 1, **_added("implement", "exit", "build-is-clean")}
    root, _ = _issue(tmp_path, cfg)
    out = _render(root, "verification-report")[1]
    assert ("\n### Implement exit list\n\n"
            "- [ ] (evidence: {{EV-id}}) build-is-clean statement.\n\nNext stage:") in out
    # Definition of Done is unchanged and still comes first.
    assert out.index("### Definition of Done") < out.index("### Implement exit list")
    assert _rendered_items(tmp_path, out, "### Definition of Done") == DONE


def test_tr_4_an_entry_list_on_define_renders_in_the_requirements_review(tmp_path):
    cfg = {"schema": 1, **_added("define", "entry", "brief-exists")}
    root, _ = _issue(tmp_path, cfg)
    out = _render(root, "requirements-review")[1]
    assert "\n### Define entry list\n\n- [ ] brief-exists statement.\n\nNext stage:" in out
    assert "(evidence:" not in out.split("### Define entry list")[1]


def test_tr_4_a_list_no_one_wrote_adds_no_section(tmp_path):
    root, _ = _issue(tmp_path)
    for kind in KINDS:
        out = _render(root, kind)
        assert out[0] == 0, out
        assert not re.findall(r"^#+ \S+ (?:entry|exit) list$", out[1], re.M), kind


# --- TR-5: the tag rule reads every exit list's section ----------------------------------------------

def _report(task_dir, *sections):
    body = "# Verification report\n\n"
    for heading, lines in sections:
        body += f"### {heading}\n\n" + "\n".join(lines) + "\n\n"
    (task_dir / "verification-report.md").write_text(body + "Next stage: x\n", encoding="utf-8")


def _tag_rule(task_dir, **manifest):
    from compass_pkg import checks
    task = dict(_manifest_body(), evidence=[], follow_ups=[])
    task.update(manifest)
    return checks._check_dod_evidence_typed(task, str(task_dir))


def test_tr_5_a_bare_box_in_another_exit_list_fails_the_tag_rule(tmp_path):
    root, task_dir = _project(tmp_path)
    _report(task_dir, ("Definition of Done", ["- [x] done"]),
            ("Implement exit list", ["- [ ] built cleanly"]))
    ok, detail = _tag_rule(task_dir)
    assert not ok and "built cleanly" in detail and "bare unchecked" in detail


def test_tr_5_a_tag_that_resolves_in_another_exit_list_passes(tmp_path):
    root, task_dir = _project(tmp_path)
    _report(task_dir, ("Definition of Done", ["- [x] done"]),
            ("Implement exit list", ["- [ ] (evidence: EV-1) built cleanly"]))
    ok, detail = _tag_rule(task_dir, evidence=[{"id": "EV-1", "type": "test-run", "path": "e"}])
    assert ok, detail
    ok, detail = _tag_rule(task_dir)
    assert not ok and "EV-1" in detail


def test_tr_5_an_entry_list_and_other_sections_are_not_read(tmp_path):
    root, task_dir = _project(tmp_path)
    _report(task_dir, ("Definition of Done", ["- [x] done"]),
            ("Define entry list", ["- [ ] brief exists"]),
            ("Notes", ["- [ ] a loose box"]))
    ok, detail = _tag_rule(task_dir)
    assert ok, detail


def test_tr_5_the_item_count_covers_every_exit_section(tmp_path):
    root, task_dir = _project(tmp_path)
    _report(task_dir, ("Definition of Done", ["- [x] one", "- [x] two"]),
            ("Ship exit list", ["- [x] three"]))
    ok, detail = _tag_rule(task_dir)
    assert ok and "all 3 DoD item(s)" in detail


# --- TR-6: a tick is judged under its own list's heading ------------------------------------------------

def _implement_exit_rows(tmp_path, monkeypatch, report_sections):
    from test_entry_exit_evaluation import _by_check, _config_project, _rows, _view
    root, task_dir = _config_project(tmp_path)
    _write_manifest(task_dir, current_phase="ship")
    _report(task_dir, *report_sections)

    def mutate(resolved):
        resolved["checks"]["build-is-clean"] = dict(_HUMAN, statement="build-is-clean statement.")
        resolved["stages"]["implement"]["exit"] = ["build-is-clean"]

    rows = _rows(_view(root, monkeypatch, mutate), task_dir)
    return _by_check(r for r in rows if r.stage == "implement")


def test_tr_6_a_tick_under_the_lists_own_heading_passes(tmp_path, monkeypatch):
    rows = _implement_exit_rows(tmp_path, monkeypatch, [
        ("Implement exit list", ["- [x] build-is-clean statement."])])
    assert rows["build-is-clean"].status == "pass", rows["build-is-clean"].detail


def test_tr_6_a_tick_under_the_done_heading_does_not_count_for_it(tmp_path, monkeypatch):
    rows = _implement_exit_rows(tmp_path, monkeypatch, [
        ("Definition of Done", ["- [x] build-is-clean statement."])])
    row = rows["build-is-clean"]
    assert row.status == "fail" and "'Implement exit list'" in row.detail


def test_tr_6_an_unticked_box_with_a_tag_that_does_not_resolve_fails(tmp_path, monkeypatch):
    rows = _implement_exit_rows(tmp_path, monkeypatch, [
        ("Implement exit list", ["- [ ] (evidence: EV-NOPE) build-is-clean statement."])])
    row = rows["build-is-clean"]
    assert row.status == "fail" and "EV-NOPE" in row.detail


# --- TR-7: the private verb ------------------------------------------------------------------------------------

def test_tr_7_the_verb_renders_for_the_current_issue(tmp_path):
    cfg = {"schema": 1, "stages": {"plan": {"set": {"entry": {"remove": ["dor-no-open-questions"]}}}}}
    root, _ = _issue(tmp_path, cfg)
    (root / ".compass" / "current-task").write_text(SLUG + "\n", encoding="utf-8")
    code, out, err = _run(root, "issue", "template", "requirements-review")
    assert code == 0, out + err
    assert "No open questions" not in out and "Summary is filled" in out


def test_tr_7_json_gives_the_kind_the_issue_the_source_and_the_text(tmp_path):
    import json
    cfg = {"schema": 1, "stages": {"plan": {"set": {"entry": {"remove": ["dor-no-open-questions"]}}}}}
    root, _ = _issue(tmp_path, cfg)
    plain = _render(root, "requirements-review")[1]
    code, out, err = _render(root, "requirements-review", "--json")
    assert code == 0, out + err
    doc = json.loads(out)
    assert sorted(doc) == ["issue", "kind", "source", "text"]
    assert doc["kind"] == "requirements-review" and doc["issue"] == SLUG
    assert doc["source"] == "generation" and doc["text"] == plain


def test_tr_7_json_says_none_when_no_configuration_is_read(tmp_path):
    import json
    (tmp_path / ".compass").mkdir()
    task_dir = tmp_path / ".compass" / "work" / SLUG
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(_manifest_body()), encoding="utf-8")
    doc = json.loads(_render(tmp_path, "verification-report", "--json")[1])
    assert doc["source"] == "none" and doc["text"] == DONE_TEMPLATE.read_text(encoding="utf-8")


def test_tr_7_an_unknown_kind_is_refused_and_names_the_kinds(tmp_path):
    root, _ = _issue(tmp_path)
    code, out, err = _render(root, "no-such-template")
    assert code != 0 and out == ""
    assert "no-such-template" in err and "requirements-review" in err


def test_tr_7_the_verb_is_public_and_says_what_it_does(tmp_path):
    root, _ = _issue(tmp_path)
    code, out, err = _run(root, "issue", "--help")
    assert code == 0 and "template" in out
    code, out, err = _run(root, "issue", "template", "--help")
    assert code == 0
    flat = " ".join(out.split())
    assert "stage lists" in flat and "--issue" in flat and "--json" in flat
    code, out, err = _run(root, "--help")
    assert "_render-template" not in out
    assert _run(root, "_render-template", "intent")[0] == 2


COMMANDS = {"refine": "requirements-review", "verify": "verification-report"}


@pytest.mark.parametrize("command, kind", sorted(COMMANDS.items()))
def test_tr_7_the_command_that_writes_a_checklist_document_takes_it_from_the_verb(command, kind):
    text = (ROOT / "commands" / f"{command}.md").read_text(encoding="utf-8")
    assert f"compass issue template {kind}" in text
    assert f"templates/{kind}.md" not in text


def test_tr_7_no_skill_or_agent_copies_a_list_template_by_path():
    for folder in ("skills", "agents", "commands", "approaches"):
        for path in (ROOT / folder).rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for kind in COMMANDS.values():
                assert f"templates/{kind}.md" not in text, path


# --- TR-8: nothing else changes, and the cap holds --------------------------------------------------------------

OTHER = sorted(p.stem for p in TEMPLATES.glob("*.md") if p.stem not in KINDS)


def test_tr_8_every_other_template_renders_unchanged(tmp_path):
    root, _ = _issue(tmp_path, {"schema": 1, **_added("plan", "entry", "release-notes-drafted")})
    assert len(OTHER) >= 10
    for kind in OTHER:
        code, out, err = _render(root, kind)
        assert code == 0, (kind, out + err)
        assert out == (TEMPLATES / f"{kind}.md").read_text(encoding="utf-8"), kind


def test_tr_8_the_borrowed_templates_stay_under_the_cap(tmp_path):
    root, _ = _issue(tmp_path)
    from test_borrowed_document_shapes import TEMPLATE_LINE_CAP
    for kind in ("threat-model", "rollback-plan"):
        code, out, err = _render(root, kind)
        assert code == 0, err
        assert len(out.splitlines()) <= TEMPLATE_LINE_CAP, kind


def test_tr_9_the_owning_doc_says_what_renders_and_the_router_names_the_module():
    doc = (ROOT / "docs" / "entry-exit-evaluation.md").read_text(encoding="utf-8")
    flat = " ".join(doc.split())
    for phrase in ("cli/compass_pkg/template_lists.py", "compass issue template",
                   "Definition of Ready", "Implement exit list",
                   "keeps the template's own text", "(evidence: {{EV-id}})",
                   "every exit list"):
        assert phrase in flat, phrase
    assert "templates do not render from the lists" not in flat
    assert "reads only the `Definition of Done` section" not in flat
    router = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert re.search(r"`cli/compass_pkg/template_lists\.py`[^\n]*\| `docs/entry-exit-evaluation\.md` \|",
                     router)


def test_tr_8_the_default_render_adds_no_line_to_a_list_template(tmp_path):
    root, _ = _issue(tmp_path)
    for kind, path in KINDS.items():
        out = _render(root, kind)[1]
        assert len(out.splitlines()) == len(path.read_text(encoding="utf-8").splitlines())
