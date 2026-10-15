"""`compass issue template show` and the checklists of the document templates.

The requirements review holds the Definition of Ready and the verification
report holds the Definition of Done as rendered blocks (`dor` and `dod`).
`compass issue render` writes them from the issue's configured lists, so the
templates carry no checkbox to follow a list, and the verb prints each block
marker and each checkbox line of the template as the file holds them. A page
tick counts for nothing (`documents-carry-judgement`). The verb prints a
catalogue kind as a skeleton, with a header the catalogue gives
(`artifact-catalogue-fields`).

Scenario ids: `TR-1` to `TR-9` (issue `templates-render-lists`); TR-2 to TR-6, which
rendered and read checkboxes, ended with the move to blocks. Each test name starts
with its scenario id.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_generation_store import SLUG, _evaluate_write, _project, _run  # noqa: E402
from test_ready_and_done_data import DONE_TEMPLATE, READY_TEMPLATE  # noqa: E402

TEMPLATES = ROOT / "templates"
KINDS = {"requirements-review": READY_TEMPLATE, "verification-report": DONE_TEMPLATE}


@pytest.fixture(autouse=True)
def _inside_the_scratch_project(tmp_path, monkeypatch):
    """Readers find the project from the working directory; keep that the
    scratch project, never the repository the tests run from."""
    monkeypatch.chdir(tmp_path)


def _contract(text):
    """The lines of a template that a configured list could change: each render
    marker and each checkbox. The skeleton adds a header and keeps these."""
    return [line for line in text.splitlines()
            if line.startswith(("<!-- compass:render", "<!-- /compass:render"))
            or "- [ ]" in line or "- [x]" in line]


def _render(root, kind, *extra):
    return _run(root, "issue", "template", "show", kind, "--issue", SLUG, *extra)


def _issue(tmp_path, compass_yml=None):
    """A project with one issue whose stored configuration is generation 1."""
    root, task_dir = _project(tmp_path, compass_yml=compass_yml or {"schema": 1})
    assert _evaluate_write(root)[0] == 0
    return root, task_dir


def _manifest_body():
    from test_generation_store import MANIFEST
    return dict(MANIFEST)


# --- TR-1: the shipped default renders the template file --------------------------------------

@pytest.mark.parametrize("kind", sorted(KINDS))
def test_tr_1_the_default_renders_each_template_marker_for_marker(tmp_path, kind):
    root, _ = _issue(tmp_path)
    code, out, err = _render(root, kind)
    assert code == 0, out + err
    assert _contract(out) == _contract(KINDS[kind].read_text(encoding="utf-8"))


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_tr_1_a_project_with_no_configuration_renders_the_template_markers(tmp_path, kind):
    (tmp_path / ".compass").mkdir()
    task_dir = tmp_path / ".compass" / "work" / SLUG
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(_manifest_body()), encoding="utf-8")
    code, out, err = _render(tmp_path, kind)
    assert code == 0, out + err
    assert _contract(out) == _contract(KINDS[kind].read_text(encoding="utf-8"))


# --- TR-7: the verb and the commands that use it ---------------------------------------------------------------

def test_tr_7_the_verb_renders_for_the_current_issue(tmp_path):
    cfg = {"schema": 1, "stages": {"plan": {"set": {"entry": {"remove": ["dor-no-open-questions"]}}}}}
    root, _ = _issue(tmp_path, cfg)
    (root / ".compass" / "current-task").write_text(SLUG + "\n", encoding="utf-8")
    code, out, err = _run(root, "issue", "template", "show", "requirements-review")
    assert code == 0, out + err
    # The Definition of Ready is a block that `compass issue render` writes from the list, so
    # the verb prints the template's markers whatever the list holds.
    assert _contract(out) == _contract(READY_TEMPLATE.read_text(encoding="utf-8"))


def test_tr_7_json_gives_the_kind_the_issue_the_source_and_the_text(tmp_path):
    cfg = {"schema": 1, "stages": {"plan": {"set": {"entry": {"remove": ["dor-no-open-questions"]}}}}}
    root, _ = _issue(tmp_path, cfg)
    plain = _render(root, "requirements-review")[1]
    code, out, err = _render(root, "requirements-review", "--json")
    assert code == 0, out + err
    doc = json.loads(out)
    assert sorted(doc) == ["depth", "issue", "kind", "source", "text"]
    assert doc["kind"] == "requirements-review" and doc["issue"] == SLUG
    assert doc["source"] == "generation" and doc["text"] == plain


def test_tr_7_json_names_the_issue_from_the_current_pointer(tmp_path):
    root, _ = _issue(tmp_path)
    (root / ".compass" / "current-task").write_text(SLUG + "\n", encoding="utf-8")
    code, out, err = _run(root, "issue", "template", "show", "verification-report", "--json")
    assert code == 0, out + err
    assert json.loads(out)["issue"] == SLUG


def test_tr_7_json_says_none_when_no_configuration_is_read(tmp_path):
    (tmp_path / ".compass").mkdir()
    task_dir = tmp_path / ".compass" / "work" / SLUG
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(_manifest_body()), encoding="utf-8")
    doc = json.loads(_render(tmp_path, "verification-report", "--json")[1])
    assert doc["source"] == "none"
    assert _contract(doc["text"]) == _contract(DONE_TEMPLATE.read_text(encoding="utf-8"))


def test_tr_7_an_unknown_kind_is_refused_and_names_the_kinds(tmp_path):
    root, _ = _issue(tmp_path)
    code, out, err = _render(root, "no-such-template")
    assert code != 0 and out == ""
    assert "no-such-template" in err and "requirements-review" in err


def test_tr_7_an_issue_that_does_not_exist_is_refused(tmp_path):
    root, _ = _issue(tmp_path)
    code, out, err = _run(root, "issue", "template", "show", "requirements-review", "--issue", "nope")
    assert code == 2 and out == ""
    assert "no issue directory" in err


def test_tr_7_the_verb_is_public_and_says_what_it_does(tmp_path):
    root, _ = _issue(tmp_path)
    code, out, err = _run(root, "issue", "--help")
    assert code == 0 and "template" in out
    code, out, err = _run(root, "issue", "template", "show", "--help")
    assert code == 0
    flat = " ".join(out.split())
    assert "skeleton" in flat and "--depth" in flat and "--issue" in flat and "--json" in flat
    code, out, err = _run(root, "--help")
    assert "_render-template" not in out


COMMANDS = {"refine": "requirements-review", "verify": "verification-report"}


@pytest.mark.parametrize("command, kind", sorted(COMMANDS.items()))
def test_tr_7_the_command_that_writes_a_checklist_document_takes_it_from_the_verb(command, kind):
    text = (ROOT / "commands" / f"{command}.md").read_text(encoding="utf-8")
    assert f"compass issue template show {kind}" in text
    assert f"templates/{kind}.md" not in text
    allowed = re.search(r"^allowed-tools: (.*)$", text, re.M).group(1)
    assert "Bash" in allowed, "the command runs a compass verb, so it needs Bash"


def test_tr_7_no_skill_or_agent_copies_a_list_template_by_path():
    for folder in ("skills", "agents", "commands", "approaches"):
        for path in (ROOT / folder).rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for kind in COMMANDS.values():
                assert f"templates/{kind}.md" not in text, path


# --- TR-8: nothing else changes, and the cap holds --------------------------------------------------------------

NOT_KINDS = ("devlog", "incident", "pull-request-body")
CATALOGUE_KINDS = sorted(p.stem for p in TEMPLATES.glob("*.md")
                         if p.stem not in KINDS and p.stem not in NOT_KINDS)


def test_tr_8_other_templates_render_unchanged_and_the_cap_holds(tmp_path):
    from test_borrowed_document_shapes import TEMPLATE_LINE_CAP
    root, _ = _issue(tmp_path)
    assert len(CATALOGUE_KINDS) >= 10
    for kind in NOT_KINDS:
        code, out, err = _render(root, kind)
        assert code == 0, (kind, out + err)
        assert out == (TEMPLATES / f"{kind}.md").read_text(encoding="utf-8"), kind
    for kind in CATALOGUE_KINDS:
        # A regular issue registers the intent at lightweight, whose four sections hold
        # no checkbox; the thorough depth prints the whole template.
        code, out, err = _render(root, kind, *(("--depth", "thorough") if kind == "intent"
                                                else ()))
        assert code == 0, (kind, out + err)
        assert _contract(out) == _contract((TEMPLATES / f"{kind}.md").read_text(encoding="utf-8")), kind
    # The cap in test_borrowed_document_shapes.py covers these two templates.
    for kind in ("threat-model", "rollback-plan"):
        assert len(_render(root, kind)[1].splitlines()) <= TEMPLATE_LINE_CAP, kind


def test_tr_8_the_default_render_adds_no_checkbox_to_a_list_template(tmp_path):
    root, _ = _issue(tmp_path)
    for kind, path in KINDS.items():
        out = _render(root, kind)[1]
        assert out.count("- [ ]") == path.read_text(encoding="utf-8").count("- [ ]")


# --- TR-9: the owning doc ---------------------------------------------------------------------------------------

def test_tr_9_the_owning_doc_says_what_renders_and_the_router_names_the_module():
    doc = (ROOT / "docs" / "entry-exit-evaluation.md").read_text(encoding="utf-8")
    flat = " ".join(doc.split())
    for phrase in ("cli/compass_pkg/template_lists.py", "compass issue template show",
                   "Definition of Ready", "rendered block", "counts for nothing",
                   "compass follow-up add", "cli/compass_pkg/item_records.py"):
        assert phrase in flat, phrase
    router = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    # The module's owning doc is the artifact catalogue, which owns the skeleton the verb prints.
    assert re.search(r"`cli/compass_pkg/template_lists\.py`[^\n]*\| `docs/artifact-catalogue\.md` \|",
                     router)
