"""Scenarios ACF-1 to ACF-65 of the issue `artifact-catalogue-fields`.

Each test is named for its scenario id, as the manifest declares
(`tests/test_artifact_catalogue_fields.py::test_acf_<n>`). The scenarios are
in `artifact-catalogue-fields/acceptance-criteria.md`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

#: The catalogue as it was before this issue changed it: twelve kinds.
#: The undeclared kind names the 6.x migrate lists on the archive copy.
AD_HOC_KINDS = ROOT / "tests" / "fixtures" / "ad-hoc-kinds.txt"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --- group A and F: the catalogue fields, their lint and the classifier ------------

CLI = ROOT / "cli" / "compass"

#: The stage, owner and traditional name of each shipped kind. Written out here
#: from the issue's requirements review, as jed72 accepted it, and the design, so
#: the tests do not read the answer from the file they check.
SHIPPED_KINDS = {
    "intent": ("assess", "product-owner", "prd"),
    "delivery-approach": ("assess", "router", "project-plan"),
    "bug-report": ("assess", "spec-author", "bug-report"),
    "acceptance-criteria": ("define", "spec-author", "requirements"),
    "ui-contract": ("define", "designer", "ui-specification"),
    "architecture-notes": ("define", "architect", "architecture-review"),
    "positioning": ("define", "product-marketer", "positioning-statement"),
    "requirements-review": ("refine", "spec-author", "requirements-review"),
    "technical-design": ("plan", "planner", "hld"),
    "low-level-design": ("plan", "planner", "lld"),
    "threat-model": ("plan", "planner", "threat-model"),
    "rollback-plan": ("plan", "planner", "rollback-plan"),
    "product-owner-review": ("plan", "product-owner", "stakeholder-review"),
    "distribution-map": ("breakdown", "planner", "work-breakdown"),
    "verification-report": ("verify", "verifier", "test-report"),
    "verification-note": ("verify", "verifier", "test-summary"),
    "launch-readiness": ("verify", "product-marketer", "release-readiness-review"),
    "review": ("verify", "reviewer", "review-record"),
    "spike-conclusion": ("verify", "builder", "spike-report"),
}
SIX_FIELDS = ("stage", "owner", "audience", "stands_for", "sections", "depends_on")

#: The live default declares no document kind since 9.0.0 (ADR-091), and nothing can
#: change the catalogue since 9.0.0 (ADR-094). The 7.0.0 preset, kept as a test
#: fixture (VD-055), holds the catalogue these scenarios checked, and a stored
#: generation is filled from the same catalogue, so it is read from that preset. The scenarios of a parent's change to it
#: (the lint of a team parent, the merge and the classifier) went with the layers.
FROZEN = ROOT / "tests" / "fixtures" / "presets" / "default@7"


def _frozen_doc():
    """The frozen 7.0.0 preset as one document: each file holds one catalogue."""
    from compass_pkg import catalogue_spec
    doc = {"schema": 1}
    for name in catalogue_spec.CATALOGUES:
        part = yaml.safe_load((FROZEN / f"{name}.yml").read_text(encoding="utf-8"))
        doc.update({k: v for k, v in part.items() if k != "schema"})
    return doc


def _env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "200",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def _cli(cwd, *argv):
    run = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=_env(cwd),
                         capture_output=True, text=True, timeout=300)
    return run.returncode, run.stdout, run.stderr


def _scratch(tmp_path, layer=None):
    """A project root with no issue, and a `compass.yml` when `layer` is given."""
    root = tmp_path / "project"
    (root / ".compass").mkdir(parents=True)
    if layer is not None:
        (root / "compass.yml").write_text(yaml.safe_dump(layer, sort_keys=False),
                                          encoding="utf-8")
    return root


def _live(root):
    """The configuration the project at `root` resolves to now: the check set
    with its settings applied (ADR-094). `compass policy show` lists no fields
    since 9.0.0, so the resolved mapping is read directly."""
    from compass_pkg import effective
    return effective.resolve_live(str(root)).resolved


def _lint(root):
    code, out, err = _cli(root, "policy", "lint", "--json")
    return code, json.loads(out), out + err


def _words(report):
    """Each lint finding as one line: its level, path and message."""
    return [f"{f['level']} {f['path']} {f['message']}" for f in report["findings"]]


def _charter(**over):
    entry = {"file": "test-charter.md", "stage": "plan", "owner": "planner",
             "audience": "A tester reads it to agree what to probe before testing starts.",
             "stands_for": "test-charter", "sections": {"thorough": ["Mission", "Areas"]},
             "depends_on": []}
    entry.update(over)
    return entry


def test_acf_1(tmp_path):
    from types import SimpleNamespace

    from compass_pkg import artifact_kinds

    root = _scratch(tmp_path)
    live = _live(root)
    assert not live.get("artifacts")
    catalogue = _frozen_doc()["artifacts"]
    # The frozen catalogue names the legacy stages its own preset declares; the
    # shipped default shows the four path stages since 9.0.0 (ADR-092).
    assert set(live["stages"]) == {"assess", "specify", "build", "ship"}
    stages = set(_frozen_doc()["stages"])
    assert set(SHIPPED_KINDS) <= set(catalogue)
    for kind, entry in catalogue.items():
        for field in SIX_FIELDS:
            assert field in entry, (kind, field)
            if field != "depends_on":
                assert entry[field] not in ("", None), (kind, field)
        assert entry["stage"] in stages, (kind, entry["stage"])
        assert entry["stands_for"] == SHIPPED_KINDS[kind][2], kind
        assert entry["sections"], kind
        assert set(entry["sections"]) <= {"lightweight", "thorough"}, kind
    # Each kind has sections for every depth an approach registers it at.
    for name, approach in _frozen_doc()["approaches"].items():
        for kind, depth in (approach.get("artifacts") or {}).items():
            assert depth in catalogue[kind]["sections"], (name, kind, depth)
    assert _lint(root)[0] == 0

    # A stored generation holds entries from before the fields existed. Reading
    # one fills each absent field from the shipped default, and a project's own
    # kind is left as stored.
    stored = SimpleNamespace(config={"artifacts": {
        "technical-design": {"file": "technical-design.md", "stage": "plan"},
        "test-charter": {"file": "test-charter.md", "stage": "plan"}}})
    filled = artifact_kinds.entry(stored, "technical-design")
    for field in SIX_FIELDS:
        assert filled[field] == catalogue["technical-design"][field], field
    assert artifact_kinds.entry(stored, "test-charter") == {
        "file": "test-charter.md", "stage": "plan"}
    assert artifact_kinds.entry(stored, "no-such-kind") is None


def test_acf_2(tmp_path):
    entry = _charter()
    # A project file that declares a kind is left out and named (ADR-091).
    root = _scratch(tmp_path, {"schema": 1, "artifacts": {"test-charter": entry}})
    code, report, text = _lint(root)
    assert code == 0, text
    assert [f["path"] for f in report["findings"] if f["code"] == "L-SETTING-REMOVED"] \
        == ["artifacts"], text


def test_acf_12(tmp_path):
    catalogue = _frozen_doc()["artifacts"]
    for kind, stage, owner in (("review", "verify", "reviewer"),
                               ("bug-report", "assess", "spec-author"),
                               ("architecture-notes", "define", "architect"),
                               ("product-owner-review", "plan", "product-owner"),
                               ("spike-conclusion", "verify", "builder"),
                               ("positioning", "define", "product-marketer")):
        entry = catalogue[kind]
        assert (entry["stage"], entry["owner"]) == (stage, owner), kind
        for field in SIX_FIELDS:
            assert field in entry, (kind, field)
        # Its home is the documents folder: a bare filename, no path.
        assert "/" not in entry["file"] and entry["file"].endswith(".md"), kind


def test_acf_23(tmp_path):
    assert _frozen_doc()["artifacts"]["distribution-map"]["required_when"] == {
        "subtasks": {"min": 2}}


# --- group B: the skeleton, the templates and the generated documents --------------

PRESET = FROZEN / "artifacts.yml"
TEMPLATES = ROOT / "templates"
OPTIONAL = "<!-- compass:optional -->"
#: Templates that are not catalogue kinds (ACF-61).


def _preset():
    return yaml.safe_load(PRESET.read_text(encoding="utf-8"))["artifacts"]


def _canon(heading):
    """A heading with each `{{...}}` token of a template and each `<...>` token
    of the catalogue read as one placeholder (ACF-8)."""
    import re
    return re.sub(r"\{\{.*?\}\}|<[^<>]*>", "<>", heading).strip()


def _template_headings(text):
    """`(heading, optional)` for each `## ` heading of a template, outside code
    fences. A heading is optional when the line under it is the marker."""
    lines = text.splitlines()
    found, fence = [], False
    for n, line in enumerate(lines):
        if line.startswith("```"):
            fence = not fence
        elif not fence and line.startswith("## "):
            under = lines[n + 1].strip() if n + 1 < len(lines) else ""
            found.append((line[3:].strip(), under == OPTIONAL))
    return found


def _heading_problems(templates, catalogue):
    """What is wrong between each catalogue kind's template and its sections,
    one line per fault. Written here, not in the product, so a fault in the
    skeleton builder cannot change what the test expects."""
    problems = []
    for kind, entry in sorted(catalogue.items()):
        path = Path(templates) / f"{kind}.md"
        if not path.is_file():
            problems.append(f"{kind}: no template")
            continue
        heads = _template_headings(path.read_text(encoding="utf-8"))
        required = [h for h, optional in heads if not optional]
        sections = entry["sections"]
        marked = {_canon(h) for h, optional in heads if optional}
        for depth, listed in sorted(sections.items()):
            for heading in listed:
                if _canon(heading) in marked:
                    problems.append(f"{kind} {depth}: {heading!r} is optional and listed")
        thorough = sections.get("thorough")
        if thorough is not None:
            want = [_canon(h) for h in thorough]
            have = [_canon(h) for h in required]
            for h in have:
                if h not in want:
                    problems.append(f"{kind} thorough: extra heading {h!r}")
            for h in want:
                if h not in have:
                    problems.append(f"{kind} thorough: missing heading {h!r}")
            if not [p for p in problems if p.startswith(f"{kind} thorough")] and want != have:
                problems.append(f"{kind} thorough: headings out of order {have!r}")
        if "lightweight" in sections and thorough is not None:
            light = [_canon(h) for h in sections["lightweight"]]
            rest = iter(_canon(h) for h in thorough)
            if not all(h in rest for h in light):
                problems.append(f"{kind} lightweight: not an ordered subset of thorough")
    return problems


#: The kinds of the frozen catalogue whose template still ships: the acceptance
#: criteria. 9.0.0 deleted thirteen others (ADR-091) and the five role templates
#: with their entry points (ADR-093).
KEPT_TEMPLATE_KINDS = {"acceptance-criteria"}


def _shipped_catalogue():
    """The frozen entries of the kinds that still ship a template. The coverage
    block went with rendered blocks (ADR-091), so the acceptance criteria hold no
    Coverage ledger heading."""
    import copy
    kept = {k: copy.deepcopy(v) for k, v in _preset().items() if k in KEPT_TEMPLATE_KINDS}
    sections = kept["acceptance-criteria"]["sections"]
    for depth, listed in sections.items():
        sections[depth] = [h for h in listed if h != "Coverage ledger"]
    return kept


def test_acf_7():
    assert {k for k in _preset() if (TEMPLATES / f"{k}.md").is_file()} == KEPT_TEMPLATE_KINDS
    stale = []
    for kind in KEPT_TEMPLATE_KINDS:
        text = (TEMPLATES / f"{kind}.md").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("Produced by:") or line.startswith("Lives at:"):
                stale.append(f"templates/{kind}.md: {line[:50]}")
    assert not stale, stale


def test_acf_8(tmp_path):
    catalogue = _shipped_catalogue()
    assert _heading_problems(TEMPLATES, catalogue) == []
    copy = tmp_path / "templates"
    shutil.copytree(TEMPLATES, copy)
    spec = copy / "acceptance-criteria.md"
    original = spec.read_text(encoding="utf-8")
    spec.write_text(original.replace("## Non-functional requirements\n",
                                     "## An extra heading\n\n## Non-functional requirements\n", 1),
                    encoding="utf-8")
    found = _heading_problems(copy, catalogue)
    assert any("acceptance-criteria thorough" in p and "An extra heading" in p
               for p in found), found
    spec.write_text(original.replace("## Failure-mode scenarios\n", "", 1), encoding="utf-8")
    found = _heading_problems(copy, catalogue)
    assert any("acceptance-criteria thorough" in p and "Failure-mode scenarios" in p
               for p in found), found
    lines = original.split("\n")
    a = lines.index("## Failure-mode scenarios")
    b = lines.index("## Non-functional requirements")
    lines[a], lines[b] = lines[b], lines[a]
    spec.write_text("\n".join(lines), encoding="utf-8")
    found = _heading_problems(copy, catalogue)
    assert any("acceptance-criteria thorough" in p and "out of order" in p
               for p in found), found


# --- group C: the registry, rounds, the home of a document and issue lint ----------

CREATED = "2026-10-07"
SLUG = "feature"
HOME = f"docs/compass/{CREATED}-{SLUG}"


def _registry_project(tmp_path, goal="delivery"):
    """A scratch project with one issue that has been assessed (generation 1).
    The assessment is the default regular one, or an exploration for a spike."""
    from test_generation_store import MANIFEST, _evaluate_write, _project
    body = dict(MANIFEST)
    body["assessment"] = dict(body["assessment"], goal=goal)
    root, task_dir = _project(tmp_path, manifest=body, compass_yml={"schema": 1})
    assert _evaluate_write(root)[0] == 0
    return root, task_dir


def _manifest_of(task_dir):
    return yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))


def _doc(root, name, text="# a document\n"):
    _write(root / HOME / name, text)
    return f"{HOME}/{name}"


def _set(root, kind, *argv):
    return _cli(root, "issue", "artifact", "set", kind, "--issue", SLUG, *argv)


def _pass_every_gate(task_dir):
    body = _manifest_of(task_dir)
    for gate in body.get("gates") or []:
        gate["status"] = "pass"
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")


def test_acf_15(tmp_path):
    root, task_dir = _registry_project(tmp_path)
    code, out, err = _cli(root, "issue", "lint", "--issue", SLUG)
    assert code == 0, out + err
    for name in ("review-1.md", "technical-design.md", "notes-on-cache.md", "review-brief.md",
                 "README.md", "distribution-map.md.v6.bak"):
        _doc(root, name)
    code, out, err = _cli(root, "issue", "lint", "--issue", SLUG)
    assert code == 0, out + err
    lines = [line for line in (out + err).splitlines() if "notes-on-cache.md" in line]
    assert len(lines) == 1 and "matches no kind" in lines[0], out + err
    for name in ("review-1.md", "technical-design.md", "review-brief.md", "README.md",
                 "distribution-map.md.v6.bak"):
        assert name not in out + err, name


# --- group E: conditional artifacts ------------------------------------------------

def _with_subtasks(task_dir, count):
    body = _manifest_of(task_dir)
    if count is None:
        body.pop("subtasks", None)
    else:
        body["subtasks"] = [{"id": f"subtask-{i}", "status": "dispatched"}
                            for i in range(1, count + 1)]
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")


def _approve_others(root, task_dir, leave=("distribution-map",)):
    """Write and approve every other earned document, so the map is the only open one."""
    for entry in _manifest_of(task_dir)["artifacts"]:
        if entry["kind"] in leave:
            continue
        path = _doc(root, f"{entry['kind']}.md")
        assert _set(root, entry["kind"], "--status", "approved", "--path", path)[0] == 0


def _check_row(root, name="artifacts-approved"):
    code, out, err = _cli(root, "check", "--issue", SLUG, "--json")
    return {r["name"]: r for r in json.loads(out)["checks"]}[name]


def _shown_everywhere(root, task_dir, tmp_path, text):
    """The issue page and the board panel each carry `text` for the map."""
    code, out, err = _cli(root, "issue", "render", "--issue", SLUG)
    assert code == 0, out + err
    page = (root / HOME / "README.md").read_text(encoding="utf-8")
    page_lines = [line for line in page.splitlines() if "distribution-map" in line]
    assert len(page_lines) == 1 and text in page_lines[0], page_lines
    board = tmp_path / "board.html"
    code, out, err = _cli(root, "flow", "--html", str(board))
    assert code == 0, out + err
    html = board.read_text(encoding="utf-8")
    panel = [line for line in html.splitlines() if "distribution-map" in line]
    assert len(panel) == 1 and text in panel[0], panel
    return page, html


# --- group D: the delivery-approach record on every approach -----------------------

DIMENSIONS = ("risk", "familiarity", "size", "goal", "urgency")


def _justify_all(assessment, *skip):
    """`--justify` for each dimension of `assessment` that has a value."""
    found = []
    for name in DIMENSIONS:
        if name in assessment and name not in skip:
            found += ["--justify", f"{name}=Because the {name} is {assessment[name]}."]
    return found


def _fixture(tmp_path, name, layer=None, **assessment):
    """A scratch project with one issue (slug `feature`) assessed with `assessment` over
    the default regular one. No `evaluate --write` has run."""
    from test_generation_store import MANIFEST, _project
    body = dict(MANIFEST)
    body["assessment"] = dict(body["assessment"], **assessment)
    (tmp_path / name).mkdir()
    return _project(tmp_path / name, manifest=body, compass_yml=layer or {"schema": 1})


def _evaluate(root, *extra):
    return _cli(root, "approach", "evaluate", "--issue", SLUG, "--write", *extra)


#: Words that send a writer to the old home, beside the manifest.


def _hook_issue(tmp_path, name, *, register, documents, beside):
    """An issue for the hook tests of `test_hook_artifact_paths`, with the record in
    the documents folder (`documents`), beside the manifest (`beside`), or both."""
    from test_hook_artifact_paths import DOCS_REL, SLUG as HSLUG, _project as hook_project
    (tmp_path / name).mkdir()
    project = hook_project(tmp_path / name, documents=False, register=register)
    if documents:
        _write(project / DOCS_REL / "delivery-approach.md", "# Delivery approach\n")
    if beside:
        _write(project / ".compass" / "work" / HSLUG / "delivery-approach.md",
               "# Delivery approach\n")
    return project


def test_acf_20(tmp_path):
    from test_hook_artifact_paths import _pre_tool, _stop
    for name, register, documents, beside in (
            ("first", False, False, True), ("second", True, False, True),
            ("third", True, True, False)):
        project = _hook_issue(tmp_path, name, register=register, documents=documents,
                              beside=beside)
        ran = _pre_tool(project)
        assert ran.returncode == 0 and "delivery-approach" not in ran.stderr, (name, ran.stderr)
        assert "MISSING" not in _stop(project).stderr, name


def _tree_state(root, task_dir):
    """The bytes the refusal must leave alone: manifest, generations, documents folder."""
    state = {"manifest": (task_dir / "manifest.yml").read_bytes()}
    for folder in (task_dir / "generations", root / "docs"):
        state[folder.name] = sorted(str(p.relative_to(folder)) for p in folder.rglob("*")) \
            if folder.exists() else None
    return state


@pytest.mark.raw_justify
def test_acf_21(tmp_path):
    root, task_dir = _fixture(tmp_path, "one")
    values = _manifest_of(task_dir)["assessment"]
    before = _tree_state(root, task_dir)
    flags = _justify_all(values, "size", "risk")
    for blank in ("", "   "):
        code, out, err = _evaluate(root, *flags, "--justify", f"size={blank}",
                                   "--justify", "risk=ok")
        assert code == 2 and "size" in err and "risk" not in err.split("size", 1)[0], out + err
        assert _tree_state(root, task_dir) == before
    code, out, err = _evaluate(root, *flags, "--justify", "size=", "--justify", "risk=")
    assert code == 2 and "size" in err and "risk" in err, out + err
    assert _tree_state(root, task_dir) == before
    # Every dimension with a value has one: the key holds them and the assessment does not.
    code, out, err = _evaluate(root, *_justify_all(values))
    assert code == 0, out + err
    body = _manifest_of(task_dir)
    assert set(body["justifications"]) == {"risk", "familiarity", "size", "goal"}
    assert all(isinstance(v, str) and v.strip() for v in body["justifications"].values())
    assert body["assessment"] == values and "labels" in body["assessment"]
    # An unchanged assessment needs no flag, and leaves the key as it was.
    held = body["justifications"]
    code, out, err = _evaluate(root)
    assert code == 0, out + err
    assert _manifest_of(task_dir)["justifications"] == held
    # A changed value needs a new line, although the key holds one for the old value.
    body["assessment"]["risk"] = "critical"
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    before = _tree_state(root, task_dir)
    code, out, err = _evaluate(root)
    assert code == 2 and "risk" in err, out + err
    assert _tree_state(root, task_dir) == before
    code, out, err = _evaluate(root, "--justify", "risk=It touches stored folders.",
                               "--reason", "bigger than assessed")
    assert code == 0, out + err
    assert _manifest_of(task_dir)["justifications"]["risk"] == "It touches stored folders."
    assert _manifest_of(task_dir)["justifications"]["size"] == held["size"]
    # An archived issue with no key is not refused for an unchanged assessment.
    body = _manifest_of(task_dir)
    body.pop("justifications")
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    code, out, err = _evaluate(root)
    assert code == 0, out + err
    assert "justifications" not in _manifest_of(task_dir)
    # A dimension the assessment leaves without a value needs none.
    root2, task_dir2 = _fixture(tmp_path, "two")
    body = _manifest_of(task_dir2)
    del body["assessment"]["goal"], body["assessment"]["role"]
    (task_dir2 / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                            encoding="utf-8")
    code, out, err = _evaluate(root2, *_justify_all(body["assessment"]))
    assert code == 0, out + err
    assert set(_manifest_of(task_dir2)["justifications"]) == {"risk", "familiarity", "size"}


# --- group G: the delivery-approach record's rendered blocks (FU-1) ---------------

def _template(name):
    return (ROOT / "templates" / name).read_text(encoding="utf-8")


def _approach_issue(tmp_path, name, *, reasons=None, **assessment):
    """A fixture issue evaluated and written, with its delivery-approach record copied
    from the template into the documents folder and registered. Returns (root, task_dir,
    path of the record). Nothing is rendered."""
    root, task_dir = _fixture(tmp_path, name, **assessment)
    values = _manifest_of(task_dir)["assessment"]
    flags = []
    for dim in DIMENSIONS:
        if dim in values:
            text = (reasons or {}).get(dim) or f"Because the {dim} is {values[dim]}."
            flags += ["--justify", f"{dim}={text}"]
    code, out, err = _evaluate(root, *flags)
    assert code == 0, out + err
    path = _doc(root, "delivery-approach.md", _template("delivery-approach.md"))
    code, out, err = _set(root, "delivery-approach", "--status", "draft", "--path", path)
    assert code == 0, out + err
    return root, task_dir, root / path


def _render(root, *extra):
    code, out, err = _cli(root, "issue", "render", "--issue", SLUG, *extra)
    assert code == 0, out + err
    return out + err


def _block(text, kind):
    from compass_pkg import rendered_blocks
    parsed = rendered_blocks.parse(text)
    block = next(b for b in parsed.blocks if b.kind == kind)
    return "".join(parsed.lines[block.start + 1:block.end])


def _rewrite_manifest(task_dir, **changes):
    body = _manifest_of(task_dir)
    body.update(changes)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")


def _check_rows(root):
    code, out, err = _cli(root, "check", "--issue", SLUG, "--json")
    assert out.strip().startswith("{"), out + err
    return {c["name"]: c for c in json.loads(out)["checks"]}


GATE_TEMPLATES = ("distribution-map.md", "requirements-review.md", "technical-design.md",
                  "verification-report.md")
PLAN_CHECK = "plan-reviewed"
PLAN_LAYER = {"schema": 1,
              "checks": {PLAN_CHECK: {"statement": "The design was read by a second engineer.",
                                      "kind": "human", "severity": "blocking",
                                      "on_skipped": "not-applicable"}},
              "stages": {"plan": {"set": {"exit": {"add": [PLAN_CHECK]}}}}}


ASSESS_TEXTS = ("approaches/assess-procedure.md", "commands/assess.md",
                "skills/adaptive-routing/SKILL.md")


def test_acf_64():
    # A re-assessment changes values, and evaluate --write refuses a changed value with
    # no justification (ACF-21). A text that tells the reader to run it bare sends them
    # into that refusal.
    import re
    named = []
    for name in ASSESS_TEXTS:
        text = " ".join((ROOT / name).read_text(encoding="utf-8").split())
        spans = re.findall(r"`compass approach evaluate --write[^`]*`", text)
        named += spans
        bare = [s for s in spans if "--justify" not in s]
        assert not bare, f"{name} shows approach evaluate --write without --justify: {bare}"
    # ADR-099: `commands/assess.md` teaches `compass quick-fix start`, which writes
    # the assessment itself, so only the procedure and the routing skill name the
    # command that re-assesses.
    assert named, "no text names `approach evaluate --write`"
    assert any("--justify" in s for s in named)


# --- group H: the migrate maps the ad-hoc kinds ------------------------------------

#: The number of names in tests/fixtures/ad-hoc-kinds.txt, fixed by a dry run of the
#: 6.x migrate on the archive copy and recorded in requirements-review.md.
AD_HOC_COUNT = 78


def test_acf_41():
    from compass_pkg import migrate_kinds as mk
    names = [n for n in AD_HOC_KINDS.read_text(encoding="utf-8").splitlines() if n]
    assert len(names) == len(set(names)) == AD_HOC_COUNT
    catalogue = mk.shipped_catalogue()
    targets = {n: mk.lookup(n + ".md", catalogue) for n in names}
    for name, target in targets.items():
        assert target.how != mk.UNMAPPED, f"{name} has no target"
        if target.how != mk.SKIP:
            assert target.kind in catalogue, (name, target)
            assert target.kind != name or name in catalogue, (name, target)
    # Review rounds are rounds of review; review briefs are not artifacts.
    rounds = [n for n, t in targets.items() if t.how in (mk.PLAIN, mk.FAMILY)]
    briefs = [n for n in names if "review-brief" in n]
    assert all(targets[n].kind == "review" for n in rounds)
    assert all(targets[n].how == mk.SKIP for n in briefs)
    assert (len(rounds), len(briefs)) == (29, 26)       # 55 names; the spec said 57
    assert all(("review" in n or n.startswith("verify-")) for n in rounds)
    expected = {"design": ("alias", "technical-design"), "prd": ("alias", "intent"),
                "positioning": ("kind", "positioning")}
    for name, (how, kind) in expected.items():
        assert (targets[name].how, targets[name].kind) == (how, kind), name
    for name in ("recommendation", "compare", "report"):
        assert mk.lookup(name + ".md", catalogue).how == mk.SKIP, name
    # The test can fail: remove the row that decides a name and the name loses its target.
    for name, row in (("design", 3), ("verify-security", 5), ("recommendation", 1)):
        rules = tuple(r for r in mk.KIND_RULES if r.order != row)
        assert mk.lookup(name + ".md", catalogue, rules).how == mk.UNMAPPED, name
    assert mk.lookup("notes-on-cache.md", catalogue).how == mk.UNMAPPED


MARKER = "<!-- compass: moved -->"
STAMP = "2026-09-01"


class _Stopped(Exception):
    """Raised by a test's step hook to stop the migrate where the test wants it."""


def _body(slug, name):
    return f"# {name} of {slug}\n\nBody of {name}.\n"


def _m_issue(root, slug, *, created=STAMP, beside=(), docs=(), artifacts=(), approach="regular",
             texts=None, stages=None, **extra):
    """An archived issue for the migrate: a manifest, the files beside it and the
    files in its documents folder, each with bytes of its own."""
    work = root / ".compass" / "work" / slug
    docs_home = root / "docs" / "compass" / f"{created}-{slug}"
    manifest = {"schema_version": "3.0", "issue": slug, "created": created, "status": "active",
                "delivery_approach": approach, "artifacts": list(artifacts), "evidence": [],
                "gates": [], "scenarios": [], "changed_files": [], "claims": [],
                "follow_ups": []}
    if stages:
        manifest["stages"] = stages
    manifest.update(extra)
    _write(work / "manifest.yml", yaml.safe_dump(manifest, sort_keys=False))
    for folder, names in ((work, beside), (docs_home, docs)):
        for name in names:
            text = (texts or {}).get((folder is work, name)) or _body(slug, name)
            _write(folder / name, text)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n", encoding="utf-8")
    return work, docs_home


def _entry(kind, slug, name=None, *, created=STAMP, **over):
    entry = {"id": "ART-" + kind.upper().replace("-", "_"), "kind": kind, "status": "draft"}
    if name:
        entry["path"] = f"docs/compass/{created}-{slug}/{name}"
    entry.update(over)
    return entry


def _digests(root, *only):
    """The sha256 of every file under .compass/work and docs/compass (or under `only`)."""
    import hashlib
    found = {}
    for sub in only or (".compass/work", "docs/compass"):
        base = root / sub
        for path in sorted(base.rglob("*")) if base.is_dir() else []:
            if path.is_file():
                found[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def _migrate(root, *flags):
    return _cli(root, "issue", "migrate", *flags)


def _timeless_digests(root):
    """`_digests` with each ISO timestamp masked. The migrate stamps the approval of a
    done issue's documents with the time it ran, so two runs differ in that text and
    nowhere else."""
    import hashlib
    import re
    stamp = re.compile(rb"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:[+-]\d\d:\d\d|Z)?")
    found = {}
    for sub in (".compass/work", "docs/compass"):
        for path in sorted((root / sub).rglob("*")):
            if path.is_file():
                found[str(path.relative_to(root))] = hashlib.sha256(
                    stamp.sub(b"<time>", path.read_bytes())).hexdigest()
    return found


def _registry(work):
    return yaml.safe_load((work / "manifest.yml").read_text(encoding="utf-8")).get("artifacts") or []


def test_acf_42(tmp_path):
    root = tmp_path / "a"
    work, docs = _m_issue(root, "rounds", docs=["review.md", "review-2.md", "integrated-review-3.md"],
                          beside=["verify-security-4.md"])
    sources = {n: (docs / n).read_bytes() for n in ("review.md", "review-2.md", "integrated-review-3.md")}
    sources["verify-security-4.md"] = (work / "verify-security-4.md").read_bytes()
    code, out, err = _migrate(root, "--apply")
    assert code == 0, out + err
    held = sorted(p.name for p in docs.glob("review*.md"))
    assert held == ["review-1.md", "review-2.md", "review-3.md", "review-4.md"], held
    for number, old in ((1, "review.md"), (2, "review-2.md"), (3, "integrated-review-3.md"),
                        (4, "verify-security-4.md")):
        assert (docs / f"review-{number}.md").read_bytes() == sources[old], old
    reviews = {e["round"]: e for e in _registry(work) if e["kind"] == "review"}
    assert sorted(reviews) == [1, 2, 3, 4]
    for number, old in ((1, "review.md"), (2, "review-2.md"), (3, "integrated-review-3.md"),
                        (4, "verify-security-4.md")):
        assert reviews[number]["path"] == f"docs/compass/{STAMP}-rounds/review-{number}.md"
        assert old in reviews[number]["reason"], reviews[number]
    for gone in ("review.md", "integrated-review-3.md"):
        assert not (docs / gone).exists()
    assert not (work / "verify-security-4.md").exists()
    # A plain round keeps its number; another family takes the next free one.
    second = tmp_path / "b"
    work2, docs2 = _m_issue(second, "keeps", docs=["review-2.md", "verify-security-2.md"])
    code, out, err = _migrate(second, "--apply")
    assert code == 0, out + err
    assert sorted(p.name for p in docs2.glob("review*.md")) == ["review-2.md", "review-3.md"]
    assert "verify-security-2.md" in out and "review-3.md" in out and "review-2.md" in out, out


def test_acf_43(tmp_path):
    root = tmp_path / "a"
    bad, bad_docs = _m_issue(root, "collides", docs=["review.md", "review-1.md"], beside=["devlog.md"])
    good, good_docs = _m_issue(root, "fine", docs=["review.md"])
    before = _digests(root, ".compass/work/collides", "docs/compass/2026-09-01-collides")
    code, out, err = _migrate(root, "--apply")
    assert code != 0, out + err
    text = out + err
    assert "review.md" in text and "review-1.md" in text and "collides" in text, text
    assert "round 1" in text and "re-run" in text, text
    assert _digests(root, ".compass/work/collides", "docs/compass/2026-09-01-collides") == before
    assert (good_docs / "review-1.md").is_file() and not (good_docs / "review.md").exists()
    # The dry run names the same pair and writes nothing.
    code, out, err = _migrate(root)
    assert code != 0 and "review-1.md" in out + err


def test_acf_44(tmp_path):
    root = tmp_path / "a"
    names = ["bug-report.md", "architecture-notes.md", "spike-conclusion.md", "positioning.md",
             "design.md", "recommendation.md"]
    slug = "repointed"
    arts = [_entry(k, slug, f"{k}.md", status="approved", approved_by="jed72", approved_at="2026-09-02")
            for k in ("bug-report", "architecture-notes", "spike-conclusion", "positioning", "recommendation")]
    arts.append(_entry("design", slug, "design.md", status="approved", approved_by="jed72",
                       approved_at="2026-09-02"))
    arts.append(_entry("prd", slug))
    work, docs = _m_issue(root, slug, docs=names, artifacts=arts)
    recommendation = (docs / "recommendation.md").read_bytes()
    code, out, err = _migrate(root, "--apply")
    assert code == 0, out + err
    found = {e["id"]: e for e in _registry(work)}
    for kind in ("bug-report", "architecture-notes", "spike-conclusion", "positioning"):
        assert found[f"ART-{kind.upper().replace('-', '_')}"]["kind"] == kind
    design = found["ART-DESIGN"]
    assert design["kind"] == "technical-design" and design["status"] == "approved"
    assert design["approved_by"] == "jed72"
    assert design["path"] == f"docs/compass/{STAMP}-{slug}/technical-design.md"   # the table moved the file
    assert (docs / "technical-design.md").is_file() and not (docs / "design.md").exists()
    assert found["ART-PRD"]["kind"] == "intent" and found["ART-PRD"]["status"] == "draft"
    assert "ART-RECOMMENDATION" not in found
    assert (docs / "recommendation.md").read_bytes() == recommendation
    # Both old and new kind registered: both stay, and the report names the issue.
    second = tmp_path / "b"
    arts = [_entry("design", "both", "design.md"), _entry("technical-design", "both", "technical-design.md")]
    work2, docs2 = _m_issue(second, "both", docs=["design.md", "technical-design.md"], artifacts=arts)
    code, out, err = _migrate(second, "--apply")
    assert code == 0, out + err
    assert sorted(e["kind"] for e in _registry(work2)) == ["design", "technical-design"]
    assert (docs2 / "design.md").is_file() and (docs2 / "technical-design.md").is_file()
    assert "both" in out and "design" in out, out


def test_acf_45(tmp_path, monkeypatch):
    from compass_pkg import artifact_kinds, migrate_kinds, stable_ids
    root = tmp_path / "a"
    slug = "leftalone"
    names = ["devlog.md", "README.md", "assignment-subtask-1.md", "brief-subtask-1.md",
             "review-brief-2.md", "result.md", "result-subtask-2.md",
             "integrated-review-brief-3.md", "architect-ruling.md",
             "released-verbs-v5.6.0.md", "compare.md", "report.md"]
    work, docs = _m_issue(root, slug, beside=names[:7], docs=["technical-design.md"] + names[7:],
                          artifacts=[_entry("technical-design", slug, "technical-design.md")])
    before = _digests(root)
    code, out, err = _migrate(root, "--apply")
    assert code == 0, out + err
    after = _digests(root)
    for name in names:
        folder = ".compass/work" if name in names[:7] else "docs/compass"
        key = [k for k in before if k.endswith("/" + name) and k.startswith(folder)]
        assert key and all(after.get(k) == before[k] for k in key), name
    kinds = {e["kind"] for e in _registry(work)}
    assert kinds == {"technical-design"}, kinds
    code, out, err = _cli(root, "issue", "lint", "--issue", slug)
    assert not any(n in out + err for n in names[7:]), out + err
    # One list, read by both commands.
    assert migrate_kinds.NOT_AN_ARTIFACT is stable_ids.NOT_AN_ARTIFACT is artifact_kinds.NOT_AN_ARTIFACT
    # Adding a name to the one list changes what both the migrate and issue lint do.
    longer = stable_ids.NOT_AN_ARTIFACT + ("notes-on-cache.md",)
    catalogue = migrate_kinds.shipped_catalogue()
    assert migrate_kinds.lookup("notes-on-cache.md", catalogue).how == migrate_kinds.UNMAPPED
    _write(docs / "notes-on-cache.md", "# notes\n")
    assert artifact_kinds.unmatched_documents(None, str(work)) == ["notes-on-cache.md"]
    monkeypatch.setattr(migrate_kinds, "NOT_AN_ARTIFACT", longer)
    monkeypatch.setattr(artifact_kinds, "NOT_AN_ARTIFACT", longer)
    assert migrate_kinds.lookup("notes-on-cache.md", catalogue).how == migrate_kinds.SKIP
    assert artifact_kinds.unmatched_documents(None, str(work)) == []


def test_acf_65(tmp_path):
    # A multiagent builder hands back result.md or result-subtask-<n>.md beside the
    # manifest, the same class of file as brief-subtask-<n>.md. No reader needs it
    # registered, so the migrate must not report it as unmapped.
    from compass_pkg import artifact_kinds, migrate_kinds
    catalogue = migrate_kinds.shipped_catalogue()
    for name in ("result.md", "result-subtask-1.md", "result-subtask-12.md"):
        assert migrate_kinds.lookup(name, catalogue).how == migrate_kinds.SKIP, name
    root = tmp_path / "a"
    slug = "handedback"
    names = ["result.md", "result-subtask-3.md"]
    work, docs = _m_issue(root, slug, beside=names, docs=["technical-design.md"] + names,
                          artifacts=[_entry("technical-design", slug, "technical-design.md")])
    before = _digests(root)
    code, out, err = _migrate(root, "--apply")
    assert code == 0, out + err
    assert "unmapped files: 0" in out, out
    after = _digests(root)
    held = [k for k in before if k.rsplit("/", 1)[-1] in names]
    assert len(held) == 4 and all(after.get(k) == before[k] for k in held), held
    assert {e["kind"] for e in _registry(work)} == {"technical-design"}
    assert artifact_kinds.unmatched_documents(None, str(work)) == []
    code, out, err = _cli(root, "issue", "lint", "--issue", slug)
    assert not any(n in out + err for n in names), out + err


def test_acf_66(tmp_path):
    # A person registered the report at a file outside the documents folder. The migrate
    # must not re-point the entry at the copy in the documents folder, or a later step
    # edits that copy (DCJ-98 of documents-carry-judgement).
    root = tmp_path / "a"
    slug = "elsewhere"
    entry = _entry("verification-report", slug, status="approved")
    entry["path"] = "notes/report.md"
    work, docs = _m_issue(root, slug, docs=["verification-report.md"], artifacts=[entry])
    _write(root / "notes" / "report.md", "# the registered report\n")
    before = (docs / "verification-report.md").read_bytes()
    code, out, err = _migrate(root, "--apply")
    assert code == 0, out + err
    reports = [e for e in _registry(work) if e["kind"] == "verification-report"]
    assert [e["path"] for e in reports] == ["notes/report.md"], reports
    assert (docs / "verification-report.md").read_bytes() == before
    assert "verification-report.md" in out and "notes/report.md" in out, out
    # A registered path whose file is gone does not hold the document back.
    root = tmp_path / "b"
    entry = dict(entry, path="notes/gone.md")
    work, docs = _m_issue(root, slug, docs=["verification-report.md"], artifacts=[entry])
    code, out, err = _migrate(root, "--apply")
    assert code == 0, out + err
    reports = [e for e in _registry(work) if e["kind"] == "verification-report"]
    assert [e["path"] for e in reports] == [f"docs/compass/{STAMP}-{slug}/verification-report.md"], reports


def test_acf_46(tmp_path):
    root = tmp_path / "a"
    slug = "unknown"
    work, docs = _m_issue(root, slug, docs=["notes-on-cache.md", "technical-design.md"],
                          beside=["scratch-pad.md"],
                          artifacts=[_entry("technical-design", slug, "technical-design.md")])
    before = _digests(root)
    code, out, err = _migrate(root, "--apply")
    assert code == 0, out + err
    assert (docs / "notes-on-cache.md").read_bytes() == _body(slug, "notes-on-cache.md").encode()
    assert (work / "scratch-pad.md").is_file()
    assert {e["kind"] for e in _registry(work)} == {"technical-design"}
    assert "unmapped" in out and slug in out and "notes-on-cache.md" in out and "scratch-pad.md" in out, out
    assert _digests(root, "docs/compass") == {k: v for k, v in before.items() if k.startswith("docs/")}
    code, out, err = _cli(root, "issue", "lint", "--issue", slug)
    lines = [line for line in (out + err).splitlines() if "notes-on-cache.md" in line]
    assert len(lines) == 1 and "matches no kind" in lines[0], out + err


def test_acf_47(tmp_path):
    root = tmp_path / "a"
    slug = "cited"
    work, docs = _m_issue(
        root, slug, beside=["review.md"],
        subtasks=[{"id": "subtask-1", "review_brief": f".compass/work/{slug}/review.md"}],
        gates=[{"id": "verify.clarity", "status": "pass",
                "evidence": {"type": "command-output", "path": "review.md"}}])
    manifest = yaml.safe_load((work / "manifest.yml").read_text(encoding="utf-8"))
    manifest["evidence"] = [{"id": "EV-REVIEW", "type": "command-output", "path": "review.md"}]
    _write(work / "manifest.yml", yaml.safe_dump(manifest, sort_keys=False))
    code, out, err = _migrate(root, "--apply")
    assert code == 0, out + err
    after = yaml.safe_load((work / "manifest.yml").read_text(encoding="utf-8"))
    new = f"docs/compass/{STAMP}-{slug}/review-1.md"
    assert after["subtasks"][0]["review_brief"] == new
    for found in (after["evidence"][0]["path"], after["gates"][0]["evidence"]["path"]):
        assert found.endswith("review-1.md") and (work / found).resolve().is_file(), found
    assert (root / new).is_file()
    code, out, err = _cli(root, "check", "--issue", slug, "--verbose")
    assert "does not resolve" not in out + err, out + err


def _totals(text):
    """The count lines at the end of the report, as `{label: [numbers]}`."""
    found = {}
    for line in text.splitlines():
        for label in ("documents by target kind", "left on the not-an-artifact list",
                      "unmapped files", "compatibility pointers", "distribution maps"):
            if line.strip().startswith(label):
                found[label] = [int(n) for n in __import__("re").findall(r"\d+", line.split(":", 1)[1])]
    return found


def test_acf_48(tmp_path):
    from archive import sample_root
    root = tmp_path / "sample"
    shutil.copytree(sample_root(), root)
    before = _digests(root)
    code, out, err = _migrate(root)
    assert code == 0, out + err
    assert _digests(root) == before
    assert "would" in out and "register" in out, out
    totals = _totals(out)
    assert set(totals) == {"documents by target kind", "left on the not-an-artifact list",
                           "unmapped files", "compatibility pointers", "distribution maps"}, out
    assert out.strip().splitlines()[-1].startswith("This was a dry run"), out
    # A fixture with a known answer for every count; the apply reports the same ones.
    known = tmp_path / "known"
    slug = "counted"
    record = _body(slug, "delivery-approach.md")
    _m_issue(known, slug, docs=["review.md", "verify-final.md", "distribution-map.md", "notes.md"],
             beside=["delivery-approach.md", "devlog.md", "review-brief.md"],
             artifacts=[_entry("distribution-map", slug, "distribution-map.md", depth="lightweight")],
             subtasks=[{"id": "subtask-1"}])
    snapshot = _digests(known)
    code, dry, err = _migrate(known)
    assert code == 0, dry + err
    assert _digests(known) == snapshot
    counts = _totals(dry)
    assert counts["left on the not-an-artifact list"] == [1]
    assert counts["unmapped files"] == [1]
    assert counts["compatibility pointers"] == [0]
    assert counts["distribution maps"] == [1]
    assert "delivery-approach 1" in dry and "review 2" in dry, dry
    code, applied, err = _migrate(known, "--apply")
    assert code == 0, applied + err
    assert _totals(applied) == counts, (counts, _totals(applied))
    assert (known / "docs/compass" / f"{STAMP}-{slug}" / "distribution-map.md.v6.bak").is_file()


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                   env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"})


def test_acf_63(tmp_path):
    def project(name, tracked, ignored):
        root = tmp_path / name
        _m_issue(root, "guarded", docs=["review.md"])
        _git(root, "init", "-q")
        (root / ".gitignore").write_text("".join(f"{p}\n" for p in ignored), encoding="utf-8")
        for folder in tracked:
            _git(root, "add", "-f", folder)
        return root
    root = project("a", [".compass/work"], ["docs/compass/"])
    before = _digests(root)
    code, out, err = _migrate(root, "--apply")
    assert code != 0 and "docs/compass" in out + err and "copy" in out + err, out + err
    assert _digests(root) == before
    _git(root, "add", "-f", "docs/compass")
    # Staged is not enough: `git reset --hard` deletes a staged file nobody committed.
    _git(root, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "base")
    code, out, err = _migrate(root, "--apply")
    assert code == 0, out + err
    assert (root / "docs/compass" / f"{STAMP}-guarded" / "review-1.md").is_file()
    again = project("b", [".compass/work"], ["docs/compass/"])
    code, out, err = _migrate(again, "--apply", "--i-have-a-copy")
    assert code == 0, out + err
    inverse = project("c", ["docs/compass"], [".compass/work/"])
    before = _digests(inverse)
    code, out, err = _migrate(inverse, "--apply")
    assert code != 0 and ".compass/work" in out + err, out + err
    assert _digests(inverse) == before


def test_acf_49(tmp_path):
    root = tmp_path / "a"
    slug = "beside"
    work, docs = _m_issue(root, slug, beside=["delivery-approach.md"],
                          stages={"assess": "thorough"})
    record = (work / "delivery-approach.md").read_bytes()
    code, out, err = _migrate(root, "--apply")
    assert code == 0, out + err
    assert (docs / "delivery-approach.md").read_bytes() == record
    entry = next(e for e in _registry(work) if e["kind"] == "delivery-approach")
    assert entry["path"] == f"docs/compass/{STAMP}-{slug}/delivery-approach.md"
    assert entry["depth"] == "thorough"
    assert not (work / "delivery-approach.md").exists()
    # A record at its registered path and a pointer of an earlier run: the pointer goes.
    second = tmp_path / "b"
    work2, docs2 = _m_issue(second, "pointed", docs=["delivery-approach.md"],
                            beside=["delivery-approach.md"],
                            artifacts=[_entry("delivery-approach", "pointed", "delivery-approach.md")],
                            texts={(True, "delivery-approach.md"): f"{MARKER}\n# Moved\n"})
    code, out, err = _migrate(second, "--apply")
    assert code == 0, out + err
    assert not (work2 / "delivery-approach.md").exists()
    assert (docs2 / "delivery-approach.md").read_bytes() == _body("pointed", "delivery-approach.md").encode()
    # A file beside the manifest without the marker is left, and the report names it.
    third = tmp_path / "c"
    work3, docs3 = _m_issue(third, "unmarked", docs=["delivery-approach.md"],
                            beside=["delivery-approach.md"],
                            artifacts=[_entry("delivery-approach", "unmarked", "delivery-approach.md")])
    kept = (work3 / "delivery-approach.md").read_bytes()
    code, out, err = _migrate(third, "--apply")
    assert code == 0, out + err
    assert (work3 / "delivery-approach.md").read_bytes() == kept
    assert "unmarked" in out and "delivery-approach.md" in out and "left" in out, out


def _copy_sample(tmp_path, name):
    from archive import sample_root
    root = tmp_path / name
    shutil.copytree(sample_root(), root)
    return root


def test_acf_50(tmp_path):
    root = _copy_sample(tmp_path, "sample")
    code, out, err = _migrate(root, "--apply")
    assert code == 0, out + err
    after = _digests(root)
    code, out, err = _migrate(root, "--apply")
    assert code == 0, out + err
    assert "nothing to do" in out, out
    assert _digests(root) == after


def _stopped_issue(tmp_path, name, *, step):
    """A hook-test project whose delivery-approach record is beside the manifest and
    unregistered, with an evidence path that names it, migrated until `step` has run."""
    from compass_pkg import migrate, migrate_kinds
    from test_hook_artifact_paths import SLUG as HSLUG
    project = _hook_issue(tmp_path, name, register=False, documents=False, beside=True)
    work = project / ".compass" / "work" / HSLUG
    manifest = yaml.safe_load((work / "manifest.yml").read_text(encoding="utf-8"))
    manifest["evidence"] = [{"id": "EV-RECORD", "type": "command-output", "path": "delivery-approach.md"}]
    _write(work / "manifest.yml", yaml.safe_dump(manifest, sort_keys=False))
    seen = []

    def hook(slug, name_of_step):
        seen.append(name_of_step)
        if name_of_step == step:
            raise _Stopped(step)
    migrate_kinds.STEP_HOOK = hook
    try:
        with pytest.raises(_Stopped):
            migrate.migrate_issue_dir(str(work))
    finally:
        migrate_kinds.STEP_HOOK = lambda slug, name_of_step: None
    return project, work


def _hook_is_content(project):
    from test_hook_artifact_paths import _pre_tool, _stop
    ran = _pre_tool(project)
    assert "no-delivery-approach" not in ran.stderr, ran.stderr
    assert "MISSING" not in _stop(project).stderr


def test_acf_59(tmp_path):
    from test_hook_artifact_paths import DOCS_REL
    moved = f"{DOCS_REL}/delivery-approach.md"
    states = {}
    for number, step in enumerate(("register", "move", "rewrite", "pointer"), start=1):
        project, work = _stopped_issue(tmp_path, step, step=step)
        _hook_is_content(project)
        manifest = yaml.safe_load((work / "manifest.yml").read_text(encoding="utf-8"))
        entry = next(e for e in manifest["artifacts"] if e["kind"] == "delivery-approach")
        states[step] = (entry["path"], (work / "delivery-approach.md").exists(),
                        (project / moved).exists(), manifest["evidence"][0]["path"])
    assert all(state[0] == moved for state in states.values()), states
    assert states["register"][1:3] == (True, False)         # registered, not moved yet
    assert states["move"][1:3] == (False, True)             # moved, paths not rewritten yet
    assert states["move"][3] == "delivery-approach.md"
    assert states["rewrite"][3].endswith("a-moved-issue/delivery-approach.md") \
        and states["rewrite"][3] != "delivery-approach.md"
    assert states["pointer"][1:3] == (False, True)
    # Before 9.0.0 the hook refused an issue whose record moved before it was
    # registered. The hook reads the manifest now (ADR-091), so nothing is refused.


def test_acf_51(tmp_path):
    from compass_pkg import migrate, migrate_kinds
    from test_hook_artifact_paths import _pre_tool, _stop
    stopped = _copy_sample(tmp_path, "stopped")
    whole = _copy_sample(tmp_path, "whole")
    work_root = stopped / ".compass" / "work"
    victim = next(slug for slug in sorted(os.listdir(work_root))
                  if (work_root / slug / "delivery-approach.md").is_file()
                  and not list((stopped / "docs/compass").glob(f"*-{slug}/delivery-approach.md")))
    seen = []

    def hook(slug, step):
        seen.append((slug, step))
        if (slug, step) == (victim, "register"):
            raise _Stopped(slug)
    migrate_kinds.STEP_HOOK = hook
    try:
        with pytest.raises(_Stopped):
            migrate.migrate_tree(str(work_root))
    finally:
        migrate_kinds.STEP_HOOK = lambda slug, step: None
    manifest = yaml.safe_load((work_root / victim / "manifest.yml").read_text(encoding="utf-8"))
    entry = next(e for e in manifest["artifacts"] if e["kind"] == "delivery-approach")
    assert (stopped / entry["path"]).exists() is False and (work_root / victim / "delivery-approach.md").is_file()
    (stopped / ".compass" / "current-task").write_text(victim, encoding="utf-8")
    from test_hook_artifact_paths import _env
    import json as _json
    ran = subprocess.run(["bash", str(ROOT / "hooks" / "pre-tool.sh")], cwd=str(stopped), env=_env(stopped),
                         input=_json.dumps({"tool_name": "Edit",
                                            "tool_input": {"file_path": str(stopped / "src" / "thing.py")}}),
                         capture_output=True, text=True, timeout=120)
    assert "no-delivery-approach" not in ran.stderr, ran.stderr
    code, out, err = _migrate(stopped, "--apply")
    assert code == 0, out + err
    code, out, err = _migrate(whole, "--apply")
    assert code == 0, out + err
    assert _timeless_digests(stopped) == _timeless_digests(whole)


def test_acf_40():
    from archive import sample_root
    import re as _re
    root = sample_root()
    work_root = root / ".compass" / "work"

    def find(slug, name):
        for folder in [work_root / slug, *sorted((root / "docs" / "compass").glob(f"*-{slug}"))]:
            path = folder / name
            if path.is_file() and MARKER not in path.read_text(encoding="utf-8")[:400]:
                return path
        return None
    held, tables, ticks = {}, 0, 0
    for slug in sorted(os.listdir(work_root)):
        for name in ("delivery-approach.md", "technical-design.md"):
            path = find(slug, name)
            if path is not None:
                lines = path.read_text(encoding="utf-8").splitlines()
                held[(slug, name)] = lines
                tables += any(line.startswith("|") for line in lines)
                ticks += any(_re.match(r"\s*- \[x\]", line) for line in lines)
    assert tables >= 3 and ticks >= 3, (tables, ticks)
    import tempfile
    with tempfile.TemporaryDirectory() as scratch:
        copy = Path(scratch) / "copy"
        shutil.copytree(root, copy)
        code, out, err = _migrate(copy, "--apply")
        assert code == 0, out + err
        for (slug, name), lines in held.items():
            after = next((p for p in sorted((copy / "docs" / "compass").glob(f"*-{slug}/{name}"))), None)
            assert after is not None, (slug, name)
            text = after.read_text(encoding="utf-8").splitlines()
            assert text == lines, (slug, name)
            assert "compass:render" not in "\n".join(text) or "compass:render" in "\n".join(lines)


# --- group M: the after measures -----------------------------------------------------
#
# The archive sample holds no review round and no stub map, so a walk of it alone
# would pass on an empty set. Each test adds four issues with a known answer to a
# copy of the sample, and first shows that its walk reports them before the migrate.

WIDE_MAP = ("# Distribution map\n\n| Subtask | Owns |\n|---|---|\n"
            "| subtask-1 | the reader |\n| subtask-2 | the writer |\n")


def _planted_sample(tmp_path):
    """A copy of the archive sample with four planted issues, not yet migrated."""
    from archive import sample_root
    root = tmp_path / "sample"
    shutil.copytree(sample_root(), root)
    record = ["delivery-approach.md"]
    _m_issue(root, "planted-stub", beside=record, docs=["distribution-map.md"],
             subtasks=[{"id": "subtask-1"}],
             artifacts=[_entry("distribution-map", "planted-stub", "distribution-map.md",
                               depth="lightweight")])
    _m_issue(root, "planted-wide-map", beside=record, docs=["distribution-map.md"],
             texts={(False, "distribution-map.md"): WIDE_MAP},
             artifacts=[_entry("distribution-map", "planted-wide-map", "distribution-map.md",
                               depth="lightweight")])
    _m_issue(root, "planted-rounds", beside=record + ["verify-final.md", "security-review.md"],
             docs=["review.md", "review-2.md", "integrated-review-3.md"])
    _m_issue(root, "planted-quick", approach="quick-fix", beside=record)
    # The sample has no configuration file; the planted issues must not add one.
    (root / ".compass" / "config.yml").unlink()
    return root


def _issues_of(root):
    """{slug: (manifest, work folder, documents folder)} for every issue under `root`."""
    found = {}
    work_root = root / ".compass" / "work"
    for work in sorted(p for p in work_root.iterdir() if (p / "manifest.yml").is_file()):
        data = yaml.safe_load((work / "manifest.yml").read_text(encoding="utf-8")) or {}
        docs = root / "docs" / "compass" / f"{data.get('created')}-{work.name}"
        found[work.name] = (data, work, docs)
    return found


def _md(folder):
    return sorted(p.name for p in folder.glob("*.md")) if folder.is_dir() else []


def _migrated(root):
    code, out, err = _migrate(root, "--apply", "--i-have-a-copy")
    assert code == 0, out + err
    return out


def _unregistered(root):
    """Each documents-folder file `issue lint` reports as matching no kind, as `slug: line`."""
    found = []
    for slug in _issues_of(root):
        code, out, err = _cli(root, "issue", "lint", "--issue", slug)
        found += ["%s: %s" % (slug, line) for line in (out + err).splitlines()
                  if "matches no kind" in line]
    return found


def _issue_on_an_older_generation(tmp_path, root):
    """An issue whose stored generation was written before the catalogue declared
    review, architecture-notes, product-owner-review and verification-note, as every
    issue assessed under 6.x is, put into the project at `root` with a review.md and
    an architecture-notes.md in its documents folder."""
    from test_rendered_blocks_check import _rewrite_generation
    (tmp_path / "older").mkdir()
    _, task = _registry_project(tmp_path / "older")
    later = ("review", "architecture-notes", "product-owner-review", "verification-note")
    _rewrite_generation(task, edit_resolved=lambda d: [d["artifacts"].pop(k, None) for k in later])
    data = yaml.safe_load((task / "manifest.yml").read_text(encoding="utf-8"))
    shutil.copytree(task, root / ".compass" / "work" / task.name)
    docs = root / "docs" / "compass" / f"{data['created']}-{task.name}"
    for name in ("review.md", "architecture-notes.md", "delivery-approach.md"):
        _write(docs / name, f"# {name}\n")
    return task.name


def _with_a_record(root):
    """The issues, of any approach, that hold delivery-approach.md in either folder."""
    return {slug for slug, (data, work, docs) in _issues_of(root).items()
            if (work / "delivery-approach.md").is_file() or (docs / "delivery-approach.md").is_file()}


def _without_record(root, had):
    """The issues in `had` whose documents folder does not hold delivery-approach.md
    registered at that path."""
    missing = []
    for slug, (data, work, docs) in _issues_of(root).items():
        home = f"docs/compass/{docs.name}/delivery-approach.md"
        registered = any(e.get("kind") == "delivery-approach" and e.get("path") == home
                         for e in data.get("artifacts") or [] if isinstance(e, dict))
        if slug in had and not ((docs / "delivery-approach.md").is_file() and registered):
            missing.append(slug)
    return missing


def test_acf_54(tmp_path):
    # Each issue that held a record before the migrate holds it in its documents folder
    # after. An issue that never had one gets none: the migrate writes no judgement
    # (architect ruling on the archive measures).
    root = _planted_sample(tmp_path)
    _m_issue(root, "planted-none")
    (root / ".compass" / "config.yml").unlink()
    had = _with_a_record(root)
    assert {"planted-stub", "planted-rounds", "planted-quick"} <= had and "planted-none" not in had
    assert {"planted-stub", "planted-rounds", "planted-quick"} <= set(_without_record(root, had))
    _migrated(root)
    assert _without_record(root, had) == []
    data, work, docs = _issues_of(root)["planted-none"]
    assert not (docs / "delivery-approach.md").exists()
    data, work, docs = _issues_of(root)["planted-quick"]
    assert (docs / "delivery-approach.md").read_bytes() == _body("planted-quick", "delivery-approach.md").encode()


LIGHTWEIGHT = ("lightweight", "light")       # today's word and the 5.x one


def _maps_on_small_regular_issues(root):
    """Each regular issue with fewer than two subtasks whose distribution map is
    registered at lightweight depth and either sits in its documents folder or is an
    entry the check treats as owed. An issue with no subtasks list whose map names two
    or more subtasks is left out. A map registered with no depth is a person's map the
    migrate adopted. The stub rule keys on lightweight depth and this map has none,
    so it is kept."""
    from compass_pkg import migrate_kinds
    found = []
    for slug, (data, work, docs) in _issues_of(root).items():
        listed = data.get("subtasks")
        if data.get("delivery_approach") != "regular" or (
                isinstance(listed, list) and len(listed) >= 2):
            continue
        if not isinstance(data.get("subtasks"), list) and \
                migrate_kinds._map_rows(str(docs / "distribution-map.md")) >= 2:
            continue
        entries = [e for e in data.get("artifacts") or [] if isinstance(e, dict)
                   and e.get("kind") == "distribution-map" and e.get("depth") in LIGHTWEIGHT
                   and e.get("status") not in ("superseded", "omitted")]
        # The shipped catalogue owed a map only from two subtasks, and these issues have
        # fewer, so only a map on disk counts (9.0.0 removed the owed rule, ADR-091).
        if entries and (docs / "distribution-map.md").is_file():
            found.append(slug)
    return found


def _plant_adopted_map(root):
    """A regular issue with one subtask whose map was never registered and sits beside
    the manifest, as eval-judge-gaps does in the maintainer's archive."""
    _m_issue(root, "planted-adopted", beside=["delivery-approach.md", "distribution-map.md"],
             subtasks=[{"id": "subtask-1"}])
    (root / ".compass" / "config.yml").unlink()


def test_acf_55(tmp_path):
    root = _planted_sample(tmp_path)
    _plant_adopted_map(root)
    assert _maps_on_small_regular_issues(root) == ["planted-stub"]
    stub = (root / "docs" / "compass" / f"{STAMP}-planted-stub" / "distribution-map.md").read_bytes()
    wide = (root / "docs" / "compass" / f"{STAMP}-planted-wide-map" / "distribution-map.md").read_bytes()
    out = _migrated(root)
    assert _maps_on_small_regular_issues(root) == []
    # The adopted map is kept, registered with no depth, and the report lists it.
    data, work, docs = _issues_of(root)["planted-adopted"]
    assert (docs / "distribution-map.md").read_bytes() == _body("planted-adopted", "distribution-map.md").encode()
    entry = next(e for e in data["artifacts"] if e["kind"] == "distribution-map")
    assert not entry.get("depth") and entry["status"] != "superseded", entry
    lines = [line for line in out.splitlines() if "planted-adopted" in line and "distribution-map.md" in line
             and "no depth" in line]
    assert len(lines) == 1, out
    data, work, docs = _issues_of(root)["planted-stub"]
    assert (docs / "distribution-map.md.v6.bak").read_bytes() == stub
    entry = next(e for e in data["artifacts"] if e["kind"] == "distribution-map")
    assert entry["status"] == "superseded" and not entry.get("path"), entry
    assert "distribution-map.md.v6.bak" in entry["reason"], entry
    data, work, docs = _issues_of(root)["planted-wide-map"]
    assert (docs / "distribution-map.md").read_bytes() == wide
    assert not (docs / "distribution-map.md.v6.bak").exists()


def _review_names(root):
    """Each review filename that is not review-<n>.md, and each issue holding two
    review files with the same n, from the registry and from every file the mapping
    table sends to review."""
    import re as _re
    from compass_pkg import migrate_kinds
    catalogue = migrate_kinds.shipped_catalogue()
    plain = _re.compile(r"^review-([1-9]\d*)\.md$")
    found = []
    for slug, (data, work, docs) in _issues_of(root).items():
        names = [n for folder in (work, docs) for n in _md(folder)
                 if migrate_kinds.lookup(n, catalogue).kind == "review"]
        names += [str(e.get("path") or "").rsplit("/", 1)[-1] for e in data.get("artifacts") or []
                  if isinstance(e, dict) and e.get("kind") == "review" and e.get("path")]
        found += ["%s: %s" % (slug, n) for n in sorted(set(names)) if not plain.match(n)]
        numbers = [int(plain.match(n).group(1)) for folder in (work, docs) for n in _md(folder)
                   if plain.match(n)]
        found += ["%s: two files are round %d" % (slug, n) for n in sorted(set(numbers))
                  if numbers.count(n) > 1]
    return found


def test_acf_56(tmp_path):
    root = _planted_sample(tmp_path)
    before = _review_names(root)
    assert {"planted-rounds: review.md", "planted-rounds: verify-final.md",
            "planted-rounds: security-review.md"} <= set(before), before
    _migrated(root)
    assert _review_names(root) == []
    data, work, docs = _issues_of(root)["planted-rounds"]
    assert _md(docs) == ["delivery-approach.md"] + ["review-%d.md" % n for n in range(1, 6)]


#: Ids that live only in one issue's documents: design decisions (DD-), architect
#: and builder decisions (AD-, BD-) and requirements-review questions (Q<n>). The
#: issue documents are not tracked, so a reader of the repository cannot look
#: one up.
_ISSUE_LOCAL_ID = re.compile(r"\b(?:AD|BD|DD)-\d+\b|\(Q\d+\)|\bQ\d+ of\b")
#: Citations on main before this rule existed; each is to be put into words.
_KNOWN_CITATIONS = {
    "cli/compass_pkg/checks.py": 2,
    "scripts/compare-behaviour.py": 2,
}


def _issue_local_citations(root):
    found = {}
    for folder in ("cli/compass_pkg", "hooks", "scripts"):
        for path in sorted((Path(root) / folder).rglob("*")):
            if path.suffix not in (".py", ".sh") or "__pycache__" in path.parts:
                continue
            hits = _ISSUE_LOCAL_ID.findall(path.read_text(encoding="utf-8", errors="replace"))
            if hits:
                found[path.relative_to(root).as_posix()] = len(hits)
    return found


def test_acf_68(tmp_path):
    """ACF-68: production code cites no id that lives only in an issue's documents."""
    found = _issue_local_citations(ROOT)
    assert found == _KNOWN_CITATIONS, found
    planted = tmp_path / "cli" / "compass_pkg"
    planted.mkdir(parents=True)
    (planted / "planted.py").write_text('"""Kept as written (DD-3)."""\n', encoding="utf-8")
    assert _issue_local_citations(tmp_path) == {"cli/compass_pkg/planted.py": 1}

