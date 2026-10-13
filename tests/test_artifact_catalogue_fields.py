"""Scenarios ACF-1 to ACF-65 of the issue `artifact-catalogue-fields`.

Each test is named for its scenario id, as the manifest declares
(`tests/test_artifact_catalogue_fields.py::test_acf_<n>`). The scenarios are
in `artifact-catalogue-fields/acceptance-criteria.md`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

FIXTURES = ROOT / "tests" / "fixtures" / "artifact-catalogue-fields"
MEASURE = ROOT / "scripts" / "measure-artifact-catalogue.py"
#: The catalogue as it was before this issue changed it: twelve kinds.
CATALOGUE_BEFORE = FIXTURES / "artifacts-before.yml"
#: The undeclared kind names the 6.x migrate lists on the archive copy.
AD_HOC_KINDS = ROOT / "tests" / "fixtures" / "ad-hoc-kinds.txt"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _issue(root, slug, created, approach, subtasks=None, registered=(), beside=(),
           documents=()):
    """One issue in a scratch archive: its manifest, the files beside it and
    the files in its documents folder."""
    manifest = {"schema_version": "3.0", "issue": slug, "created": created,
                "delivery_approach": approach}
    if subtasks is not None:
        manifest["subtasks"] = [{"id": f"subtask-{i}"} for i in range(1, subtasks + 1)]
    if registered:
        manifest["artifacts"] = [{"id": f"ART-{k.upper()}", "kind": k, "status": "draft",
                                  "path": f"docs/compass/{created}-{slug}/{k}.md"}
                                 for k in registered]
    work = root / ".compass" / "work" / slug
    _write(work / "manifest.yml", yaml.safe_dump(manifest))
    for name in beside:
        _write(work / name, f"# {name}\n")
    for name in documents:
        _write(root / "docs" / "compass" / f"{created}-{slug}" / name, f"# {name}\n")


def _measure(root, *extra):
    run = subprocess.run(
        [sys.executable, str(MEASURE), "--root", str(root),
         "--catalogue", str(CATALOGUE_BEFORE), "--json", *extra],
        capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_acf_52(tmp_path):
    # A small archive with a known answer for every figure.
    scratch = tmp_path / "scratch"
    _issue(scratch, "alpha", "2026-10-01", "regular", subtasks=0, beside=["design.md"],
           documents=["delivery-approach.md", "distribution-map.md", "review-1.md"])
    _issue(scratch, "beta", "2026-10-02", "regular", subtasks=2,
           registered=["bug-report"], documents=["distribution-map.md", "review-claims.md"])
    _issue(scratch, "gamma", "2026-10-03", "quick-fix", beside=["security-review.md"])
    found = _measure(scratch)
    assert found == {
        "kinds_declared": 12,
        "undeclared_kinds": 5,           # design, review-1, review-claims,
        "regular_issues": 2,             # security-review and bug-report
        "regular_with_record": 1,
        "regular_with_stub_map": 1,
        "review_filenames": 3,
    }
    # The measure only reads: nothing under the scratch archive changed.
    assert not list(scratch.rglob("*.v6.bak"))

    # The maintainer's archive copy, read only with the switch on, from a
    # throwaway copy so the run cannot touch the real folders.
    if os.environ.get("COMPASS_FULL_ARCHIVE") != "1":
        return
    copy = tmp_path / "archive-copy"
    shutil.copytree(ROOT / ".compass" / "work", copy / ".compass" / "work")
    shutil.copytree(ROOT / "docs" / "compass", copy / "docs" / "compass")
    names = [n for n in AD_HOC_KINDS.read_text(encoding="utf-8").splitlines() if n]
    listed = tmp_path / "kinds.txt"
    full = _measure(copy, "--list-kinds", str(listed))
    assert listed.read_text(encoding="utf-8").splitlines() == sorted(names)
    assert (full["kinds_declared"], full["undeclared_kinds"]) == (12, len(names))
    # 1 and 34 are the figures recorded on 2026-10-12. The copy holds one more
    # regular issue than the 40 the spec counted that day; it adds to neither.
    assert (full["regular_with_record"], full["regular_with_stub_map"],
            full["regular_issues"]) == (1, 34, 41)
    assert full["review_filenames"] > 25


# --- group A and F: the catalogue fields, their lint and the classifier ------------

CLI = ROOT / "cli" / "compass"

#: The stage, owner and traditional name of each shipped kind. Written out here
#: from the requirements review (Q16, accepted by jed72 as M2) and the design, so
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


def _show(root):
    """`compass policy show --json` as `{path: value}`."""
    code, out, err = _cli(root, "policy", "show", "--json")
    assert code == 0, out + err
    return {row["path"]: row["value"] for row in json.loads(out)["fields"]}


def _catalogue_of(root):
    """The artifacts catalogue as `policy show --json` reports it."""
    found = {}
    for path, value in _show(root).items():
        parts = path.split(".")
        if parts[0] == "artifacts" and len(parts) == 3:
            found.setdefault(parts[1], {})[parts[2]] = value
    return found


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
    shown = _show(root)
    catalogue = _catalogue_of(root)
    stages = {p.split(".")[1] for p in shown if p.startswith("stages.")}
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
    for path, owed in shown.items():
        if path.startswith("approaches.") and path.endswith(".artifacts"):
            for kind, depth in owed.items():
                assert depth in catalogue[kind]["sections"], (path, kind, depth)
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
    del entry["audience"]
    root = _scratch(tmp_path, {"schema": 1, "artifacts": {"test-charter": entry}})
    code, report, text = _lint(root)
    assert code != 0, text
    lines = [line for line in _words(report) if "test-charter" in line and "audience" in line]
    assert lines and all(line.startswith("error ") for line in lines), _words(report)
    entry["audience"] = _charter()["audience"]
    (root / "compass.yml").write_text(
        yaml.safe_dump({"schema": 1, "artifacts": {"test-charter": entry}}), encoding="utf-8")
    code, report, text = _lint(root)
    assert code == 0, text
    assert not [line for line in _words(report) if "audience" in line]


def test_acf_3(tmp_path):
    layer = {"schema": 1, "artifacts": {
        "bad-stage": _charter(file="bad-stage.md", stage="deploy"),
        "bad-depth": _charter(file="bad-depth.md", sections={"medium": ["One"]}),
        "bad-list": _charter(file="bad-list.md", sections={"thorough": "One"}),
        "empty-audience": _charter(file="empty-audience.md", audience=""),
        "empty-sections": _charter(file="empty-sections.md", sections={"thorough": []}),
        "bad-file": _charter(file="../outside.md"),
    }}
    root = _scratch(tmp_path, layer)
    code, report, text = _lint(root)
    assert code != 0, text
    lines = _words(report)
    for kind, field, value in (("bad-stage", "stage", "deploy"),
                               ("bad-depth", "sections", "medium"),
                               ("bad-list", "sections", "thorough"),
                               ("empty-audience", "audience", ""),
                               ("empty-sections", "sections", "thorough"),
                               ("bad-file", "file", "../outside.md")):
        found = [line for line in lines if f"artifacts.{kind}.{field}" in line]
        assert found, (kind, field, lines)
        assert all(line.startswith("error ") for line in found), found
        assert value in found[0], (value, found)
    # All six are reported in one run, and the shipped note is not one of them.
    assert not [line for line in lines if "verification-note" in line], lines
    # A good kind beside them draws nothing.
    assert not [line for line in lines if "artifacts.test-charter" in line]
    # The note prints its header and its one block marker, and no heading.
    code, out, err = _cli(_scratch(tmp_path / "plain"), "issue", "template", "show",
                          "verification-note", "--depth", "lightweight")
    assert code == 0, err
    assert "**Audience:**" in out and "<!-- compass:render verification-note -->" in out
    assert "\n## " not in out and not out.startswith("## ")


def test_acf_4(tmp_path):
    from test_artifact_freshness import CRITERIA, GUARDRAIL, _check, _entry, _scene, _write
    root, task_dir = _scene(tmp_path, capability=False, phase="implement")
    # With the capability off the digests are recorded and no reader refuses.
    assert _entry(task_dir, "technical-design")["upstream"]
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    assert _check(root)[1] == {}
    # The graph is still data in the catalogue, beside the new fields.
    catalogue = _catalogue_of(root)["technical-design"]
    assert catalogue["depends_on"] == ["acceptance-criteria"]
    for field in SIX_FIELDS:
        assert field in catalogue, field
    # With the capability on, the stale document names the changed dependency.
    doc = yaml.safe_load((root / "compass.yml").read_text(encoding="utf-8"))
    doc["capabilities"] = {GUARDRAIL: True}
    (root / "compass.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    from test_generation_store import _evaluate_write
    assert _evaluate_write(root)[0] == 0
    row = _check(root)[1]["technical-design"]
    assert row["status"] == "fail", row
    assert "acceptance-criteria changed" in row["detail"]


def test_acf_12(tmp_path):
    catalogue = _catalogue_of(_scratch(tmp_path))
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
    root = _scratch(tmp_path)
    assert _catalogue_of(root)["distribution-map"]["required_when"] == {"subtasks": {"min": 2}}
    assert _lint(root)[0] == 0
    refused = _scratch(tmp_path / "other", {"schema": 1, "artifacts": {
        "distribution-map": {"set": {"required_when": {"phase": {"min": 2}}}}}})
    code, report, text = _lint(refused)
    assert code != 0, text
    assert [line for line in _words(report)
            if "required_when" in line and "phase" in line], _words(report)


def test_acf_31(tmp_path):
    from test_generation_store import SLUG, _evaluate_write, _manifest, _project

    layer = {"schema": 1, "artifacts": {"test-charter": _charter()}}
    root, task_dir = _project(tmp_path, compass_yml=layer)
    assert _catalogue_of(root)["test-charter"] == _charter()
    assert _evaluate_write(root)[0] == 0
    created = _manifest(task_dir)["created"]
    rel = f"docs/compass/{created}-{SLUG}/test-charter.md"
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text("# Test charter\n", encoding="utf-8")
    code, out, err = _cli(root, "issue", "artifact", "set", "test-charter", "--status",
                          "draft", "--path", rel, "--issue", SLUG)
    assert code == 0, out + err
    entry = next(a for a in _manifest(task_dir)["artifacts"] if a["kind"] == "test-charter")
    assert (entry["status"], entry["path"]) == ("draft", rel)
    code, out, err = _cli(root, "issue", "lint", "--issue", SLUG)
    assert code == 0 and "test-charter" not in out + err, out + err
    # A kind the catalogue does not declare is still refused.
    code, out, err = _cli(root, "issue", "artifact", "set", "charter", "--status", "draft",
                          "--issue", SLUG)
    assert code == 2, out + err

    # A preset layer that adds the same kind gives the same catalogue entry.
    from compass_pkg import merge, policy_lint
    parent, _ = policy_lint.load_parent()
    base, provenance = merge.apply({}, parent.doc, parent.kind, parent.name, {})
    import copy
    added, _ = merge.apply(copy.deepcopy(base), layer, "parent", "fixture-preset", provenance)
    assert added["artifacts"]["test-charter"] == _charter()


def test_acf_32(tmp_path):
    from compass_pkg import merge, policy_lint
    import copy

    parent, _ = policy_lint.load_parent()
    base, provenance = merge.apply({}, parent.doc, parent.kind, parent.name, {})

    def merged(entry):
        return merge.apply(copy.deepcopy(base), {"schema": 1, "artifacts": {"test-charter": entry}},
                           "project", "project", dict(provenance))

    def refusal(entry):
        with pytest.raises(merge.MergeError) as raised:
            merged(entry)
        return raised.value.errors

    # No sections: refused, naming the kind and the field.
    no_sections = _charter()
    del no_sections["sections"]
    errors = refusal(no_sections)
    assert [e for e in errors if e[0] == "M-ADD-PARTIAL" and "test-charter" in e[1]
            and "sections" in e[2]], errors
    # Only a file name: every required field is named.
    errors = refusal({"file": "test-charter.md"})
    text = " ".join(e[2] for e in errors if e[0] == "M-ADD-PARTIAL")
    for field in ("stage", "owner", "audience", "stands_for", "sections"):
        assert field in text, (field, errors)
    # Every field but depends_on is accepted, and depends_on reads as empty.
    complete = _charter()
    del complete["depends_on"]
    config, _ = merged(complete)
    assert config["artifacts"]["test-charter"].get("depends_on", []) == []
    # An id the parent holds is refused as before.
    existing = {"schema": 1, "artifacts": {"technical-design": _charter()}}
    with pytest.raises(merge.MergeError) as raised:
        merge.apply(copy.deepcopy(base), existing, "project", "project", dict(provenance))
    assert [e for e in raised.value.errors if e[0] == "M-ADD-EXISTS"]

    # The same refusal reaches the command line, naming the field.
    root = _scratch(tmp_path, {"schema": 1, "artifacts": {"test-charter": no_sections}})
    code, out, err = _cli(root, "policy", "show")
    assert code != 0 and "M-ADD-PARTIAL" in out + err and "sections" in out + err, out + err


def test_acf_33(tmp_path):
    import copy

    from compass_pkg import classify, merge, policy_lint

    parent, _ = policy_lint.load_parent()
    base, provenance = merge.apply({}, parent.doc, parent.kind, parent.name, {})

    def verdict(layer):
        child, _ = merge.apply(copy.deepcopy(base), layer, "project", "project",
                               dict(provenance))
        return classify.classify(base, child).result

    adds = {"test-charter": _charter()}
    assert verdict({"schema": 1, "artifacts": adds}) == "equivalent"
    owed = {"schema": 1, "artifacts": adds, "approaches": {
        "regular": {"set": {"artifacts": {"set": {"test-charter": "lightweight"}}}}}}
    assert verdict(owed) == "tightening"
    removed = {"schema": 1, "approaches": {
        "regular": {"set": {"artifacts": {"remove": ["technical-design"]}}}}}
    assert verdict(removed) == "loosening"
    changed = {"schema": 1, "artifacts": {
        "distribution-map": {"set": {"required_when": {"subtasks": {"min": 3}}}}}}
    assert verdict(changed) == "incomparable"
    assert {verdict({"schema": 1, "artifacts": adds}), verdict(owed), verdict(removed),
            verdict(changed)} <= {"equivalent", "tightening", "loosening", "incomparable"}

    # `policy diff` names the added kind on a line of its own.
    root = _scratch(tmp_path, {"schema": 1, "artifacts": adds})
    code, out, err = _cli(root, "policy", "diff", "default@6", "project")
    assert code == 0, out + err
    lines = out.splitlines()
    assert lines.count("adds artifact kind test-charter") == 1, lines
    assert not [l for l in lines if l.startswith("classification:") and "test-charter" in l]


# --- group B: the skeleton, the templates and the generated documents --------------

PRESET = ROOT / "governance" / "presets" / "default" / "artifacts.yml"
TEMPLATES = ROOT / "templates"
OPTIONAL = "<!-- compass:optional -->"
#: Templates that are not catalogue kinds (ACF-61).
NOT_KINDS = ("devlog", "incident", "pull-request-body")


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


def _headings_of(output):
    return [line[3:].strip() for line in output.splitlines() if line.startswith("## ")]


def _issue_dir(root, slug="a-slug", created="2026-10-12", registered=()):
    """A bare issue with the given `(kind, depth)` entries in its registry."""
    manifest = {"schema_version": "3.0", "issue": slug, "created": created,
                "delivery_approach": "regular",
                "artifacts": [{"id": f"ART-{k.upper()}", "kind": k, "status": "draft",
                               "depth": d} for k, d in registered]}
    _write(root / ".compass" / "work" / slug / "manifest.yml", yaml.safe_dump(manifest))
    return slug


def _template_show(root, *argv):
    return _cli(root, "issue", "template", "show", *argv)


def test_acf_6(tmp_path):
    root = _scratch(tmp_path)
    entry = _preset()["technical-design"]
    text = (TEMPLATES / "technical-design.md").read_text(encoding="utf-8")
    code, light, err = _template_show(root, "technical-design", "--depth", "lightweight")
    assert code == 0, err
    head = light.split("\n## ", 1)[0]
    assert entry["audience"] in head
    assert "plan" in head and "planner" in head
    assert "docs/compass/<created>-<issue-slug>/technical-design.md" in head
    assert [_canon(h) for h in _headings_of(light)] == [
        _canon(h) for h in entry["sections"]["lightweight"]]
    assert "(optional)" not in light
    # The template's prose sits under its heading.
    assert "## 1. Approach" in light and "{{APPROACH}}" in light.split("## 1. Approach", 1)[1]
    assert "{{APPROACH}}" in text
    code, thorough, err = _template_show(root, "technical-design", "--depth", "thorough")
    assert code == 0, err
    labelled = [h for h in _headings_of(thorough) if h.endswith("(optional)")]
    assert [_canon(h) for h in _headings_of(thorough) if not h.endswith("(optional)")] == [
        _canon(h) for h in entry["sections"]["thorough"]]
    assert len(labelled) == 6, labelled
    # --json keeps its shape and gains the depth.
    code, out, err = _template_show(root, "technical-design", "--depth", "lightweight", "--json")
    assert code == 0, err
    body = json.loads(out)
    assert body["depth"] == "lightweight" and body["kind"] == "technical-design"
    assert body["text"] == light
    # With --issue the home names the issue's folder.
    slug = _issue_dir(root, registered=[("technical-design", "lightweight")])
    code, issue, err = _template_show(root, "technical-design", "--issue", slug)
    assert code == 0, err
    assert "docs/compass/2026-10-12-a-slug/technical-design.md" in issue
    # No --depth: the depth the issue registers the kind at, else thorough.
    assert [_canon(h) for h in _headings_of(issue)] == [
        _canon(h) for h in entry["sections"]["lightweight"]]
    code, none, err = _template_show(_scratch(tmp_path / "plain"), "technical-design")
    assert code == 0, err
    assert none == thorough


def test_acf_7():
    stale = []
    for kind in _preset():
        text = (TEMPLATES / f"{kind}.md").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("Produced by:") or line.startswith("Lives at:"):
                stale.append(f"templates/{kind}.md: {line[:50]}")
    assert not stale, stale


def test_acf_8(tmp_path):
    catalogue = _preset()
    assert _heading_problems(TEMPLATES, catalogue) == []
    copy = tmp_path / "templates"
    shutil.copytree(TEMPLATES, copy)
    report = copy / "verification-report.md"
    original = report.read_text(encoding="utf-8")
    report.write_text(original.replace("## Gate\n", "## Gate\n\n## An extra heading\n", 1),
                      encoding="utf-8")
    found = _heading_problems(copy, catalogue)
    assert any("verification-report thorough" in p and "An extra heading" in p
               for p in found), found
    report.write_text(original.replace("## 2. Test suite evidence\n", "", 1), encoding="utf-8")
    found = _heading_problems(copy, catalogue)
    assert any("verification-report thorough" in p and "2. Test suite evidence" in p
               for p in found), found
    lines = original.split("\n")
    a = lines.index("## 1. Scenario acceptance results")
    b = lines.index("## 2. Test suite evidence")
    lines[a], lines[b] = lines[b], lines[a]
    report.write_text("\n".join(lines), encoding="utf-8")
    found = _heading_problems(copy, catalogue)
    assert any("verification-report thorough" in p and "out of order" in p
               for p in found), found


def test_acf_60(tmp_path):
    from compass_pkg import artifact_kinds  # noqa: F401 - the module exists after U1

    catalogue = _preset()
    text = (TEMPLATES / "technical-design.md").read_text(encoding="utf-8")
    heads = _template_headings(text)
    optional = [h for h, marked in heads if marked]
    assert [h.split(".")[0].split(" ")[0] for h in optional] == ["0", "2", "3", "4", "5", "5a"]
    assert [h for h, marked in heads if not marked] == catalogue["technical-design"][
        "sections"]["thorough"]
    assert [h for h, marked in _template_headings(
        (TEMPLATES / "requirements-review.md").read_text(encoding="utf-8")) if marked] == [
        "Worked example"]
    assert [_canon(h) for h, marked in _template_headings(
        (TEMPLATES / "acceptance-criteria.md").read_text(encoding="utf-8")) if marked] == [
        "Scenario group B - <>"]
    # Every lightweight list is an ordered subset of the thorough list.
    assert _heading_problems(TEMPLATES, catalogue) == []
    root = _scratch(tmp_path)
    code, thorough, err = _template_show(root, "technical-design", "--depth", "thorough")
    assert code == 0, err
    assert _headings_of(thorough) == [h + " (optional)" if marked else h
                                      for h, marked in heads]
    code, light, err = _template_show(root, "technical-design", "--depth", "lightweight")
    assert code == 0, err
    assert not [h for h in optional if h in _headings_of(light)]
    # A marked heading that is also listed fails the test.
    copy = tmp_path / "templates"
    shutil.copytree(TEMPLATES, copy)
    path = copy / "technical-design.md"
    path.write_text(text.replace("## 1. Approach\n", "## 1. Approach\n" + OPTIONAL + "\n", 1),
                    encoding="utf-8")
    found = _heading_problems(copy, catalogue)
    assert any("technical-design" in p and "1. Approach" in p and "optional and listed" in p
               for p in found), found


def test_acf_9(tmp_path):
    root = _scratch(tmp_path)
    code, out, err = _template_show(root, "charter", "--depth", "thorough")
    assert code == 2, out + err
    assert "charter" in err
    for name in ("intent", "technical-design", "review", "devlog", "incident",
                 "pull-request-body"):
        assert name in err, name
    code, out, err = _template_show(root, "intent", "--depth", "medium")
    assert code == 2, out + err
    assert "medium" in err and "thorough" in err


def _skeleton_problems(kind, depth, output, catalogue, template_text):
    """Why `output` is not the skeleton of `kind` at `depth`, from the catalogue
    file and the template file alone."""
    problems = []
    entry = catalogue[kind]
    sections = entry["sections"][depth]
    head = output.split("\n## ", 1)[0]
    for field in ("audience", "stage", "owner", "stands_for"):
        if str(entry[field]) not in head:
            problems.append(f"{kind} {depth}: header lacks {field}")
    if f"docs/compass/<created>-<issue-slug>/{entry['file']}" not in head:
        problems.append(f"{kind} {depth}: header lacks the home")
    plain = [_canon(h) for h in _headings_of(output) if not h.endswith("(optional)")]
    if plain != [_canon(h) for h in sections]:
        problems.append(f"{kind} {depth}: headings {plain!r} are not {sections!r}")
    labelled = [_canon(h[:-len(" (optional)")]) for h in _headings_of(output)
                if h.endswith("(optional)")]
    marked = [_canon(h) for h, optional in _template_headings(template_text) if optional]
    if labelled != (marked if depth == "thorough" else []):
        problems.append(f"{kind} {depth}: optional headings {labelled!r}")
    return problems


def test_acf_10(tmp_path):
    root = _scratch(tmp_path)
    catalogue = _preset()
    assert len(catalogue) == 18
    outputs = {}
    for kind, entry in sorted(catalogue.items()):
        template_text = (TEMPLATES / f"{kind}.md").read_text(encoding="utf-8")
        for depth in sorted(entry["sections"]):
            code, out, err = _template_show(root, kind, "--depth", depth)
            assert code == 0, (kind, depth, err)
            outputs[kind, depth] = out
            assert _skeleton_problems(kind, depth, out, catalogue, template_text) == [], (
                kind, depth)
    # The check reports a skeleton builder that drops the last lightweight
    # heading, and one that prints the thorough headings for lightweight.
    text = (TEMPLATES / "technical-design.md").read_text(encoding="utf-8")
    dropped = outputs["technical-design", "lightweight"].rsplit("\n## Gate", 1)[0] + "\n"
    found = _skeleton_problems("technical-design", "lightweight", dropped, catalogue, text)
    assert found and "technical-design lightweight" in found[0], found
    found = _skeleton_problems("technical-design", "lightweight",
                               outputs["technical-design", "thorough"], catalogue, text)
    assert found and "technical-design lightweight" in found[0], found


def test_acf_11(tmp_path):
    root = _scratch(tmp_path, {"schema": 1, "artifacts": {"test-charter": _charter()}})
    assert not (TEMPLATES / "test-charter.md").exists()
    code, out, err = _template_show(root, "test-charter", "--depth", "thorough")
    assert code == 0, err
    assert _charter()["audience"] in out
    assert _headings_of(out) == ["Mission", "Areas"]
    # No prose sits under the headings: the next line after one is a heading
    # or the end.
    body = out.split("## Mission", 1)[1]
    assert body.replace("## Areas", "").strip() == ""


def test_acf_61(tmp_path):
    root = _scratch(tmp_path)
    for name in NOT_KINDS:
        code, out, err = _template_show(root, name)
        assert code == 0, err
        assert out == (TEMPLATES / f"{name}.md").read_text(encoding="utf-8"), name
        assert "**Audience:**" not in out
    code, out, err = _template_show(root, "devlog", "--depth", "thorough")
    assert code == 2, out + err
    assert "devlog" in err and "not a catalogue kind" in err and "no sections" in err
    # The heading test does not read them.
    assert not [p for p in _heading_problems(TEMPLATES, _preset()) if "devlog" in p]


def _derive(root, tmp_path, name):
    out = tmp_path / name
    code, text, err = _cli(root, "_derive-glossary", "--internal", "--root", str(root),
                           "--out", str(out / "glossary.md"),
                           "--catalogue-out", str(out / "artifact-catalogue.md"))
    assert code == 0, text + err
    return (out / "glossary.md").read_text(encoding="utf-8"), (
        out / "artifact-catalogue.md").read_text(encoding="utf-8")


def _mini_root(tmp_path):
    """A copy of the files the generator reads and the two it writes."""
    mini = tmp_path / "mini"
    for rel in ("governance/terminology.yml", "governance/presets/default/artifacts.yml",
                "docs/glossary.md", "docs/artifact-catalogue.md"):
        _write(mini / rel, (ROOT / rel).read_text(encoding="utf-8"))
    (mini / ".compass").mkdir()
    return mini


def test_acf_5(tmp_path):
    mini = _mini_root(tmp_path)
    glossary, doc = _derive(mini, tmp_path, "fresh")
    # The committed files equal a fresh generation.
    assert glossary == (ROOT / "docs" / "glossary.md").read_text(encoding="utf-8")
    assert doc == (ROOT / "docs" / "artifact-catalogue.md").read_text(encoding="utf-8")
    for kind, entry in _preset().items():
        for text in (glossary, doc):
            assert kind in text, kind
            assert " ".join(entry["audience"].split()) in " ".join(text.split()), kind
            assert entry["stands_for"] in text, kind
    owning = (ROOT / "docs" / "README.md").read_text(encoding="utf-8").split(
        "## Owning docs", 1)[1]
    row = [r for r in owning.splitlines() if r.startswith("|") and "`docs/artifact-catalogue.md`" in r.split("|")[-2]]
    assert row and "artifact_kinds.py" in row[0] and "template_lists.py" in row[0]
    assert not [r for r in owning.splitlines()
                if "template_lists.py" in r and "entry-exit-evaluation.md" in r]
    # A kind added to the catalogue without regenerating makes the committed
    # files stale.
    path = mini / "governance" / "presets" / "default" / "artifacts.yml"
    path.write_text(path.read_text(encoding="utf-8") + (
        "  test-charter:\n    file: test-charter.md\n    stage: plan\n    owner: planner\n"
        "    audience: A tester reads it to plan the session.\n    stands_for: test-charter\n"
        "    sections:\n      thorough:\n      - Mission\n    depends_on: []\n"),
        encoding="utf-8")
    added_glossary, added_doc = _derive(mini, tmp_path, "added")
    assert "test-charter" in added_glossary and "test-charter" in added_doc
    assert added_glossary != glossary and added_doc != doc
    # A hand edit of a generated entry no longer equals a fresh generation.
    audience = " ".join(_preset()["intent"]["audience"].split())
    for fresh in (glossary, doc):
        edited = fresh.replace(audience, "Edited by hand.")
        assert edited != fresh
    # The glossary meaning-only test passes on what was generated.
    from test_glossary_meaning_only import meaning_only_problems
    assert meaning_only_problems(glossary) == [] and meaning_only_problems(doc) == []


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


def _entries(task_dir, kind):
    return [a for a in _manifest_of(task_dir).get("artifacts") or [] if a.get("kind") == kind]


def _doc(root, name, text="# a document\n"):
    _write(root / HOME / name, text)
    return f"{HOME}/{name}"


def _set(root, kind, *argv):
    return _cli(root, "issue", "artifact", "set", kind, "--issue", SLUG, *argv)


def test_acf_13(tmp_path):
    root, task_dir = _registry_project(tmp_path)
    one, two = _doc(root, "review-1.md"), _doc(root, "review-2.md")
    assert _set(root, "review", "--status", "draft", "--path", one)[0] == 0
    assert _set(root, "review", "--status", "draft", "--path", two)[0] == 0
    found = _entries(task_dir, "review")
    assert [(e["round"], e["path"]) for e in found] == [(1, one), (2, two)]
    assert len({e["id"] for e in found}) == 2
    code, out, err = _cli(root, "issue", "artifact-path", "review", "--issue", SLUG)
    assert code == 0 and out.strip().endswith("review-2.md"), out + err
    code, out, err = _cli(root, "issue", "artifact-path", "review", "--round", "1",
                          "--issue", SLUG)
    assert code == 0 and out.strip().endswith("review-1.md"), out + err
    code, out, err = _cli(root, "issue", "artifact-path", "review", "--round", "9",
                          "--issue", SLUG)
    assert code != 0 and out == "", out + err
    code, out, err = _template_show(root, "review", "--depth", "thorough")
    assert code == 0, err
    assert _headings_of(out) == ["Scope", "Verdict", "Blocking", "Not blocking", "Security",
                                 "Probes"]
    # Registering round 2 again updates it and adds no third entry.
    assert _set(root, "review", "--status", "approved", "--path", two)[0] == 0
    found = _entries(task_dir, "review")
    assert len(found) == 2 and found[1]["status"] == "approved" and found[0]["status"] == "draft"
    # A round can be named without its path, and updates that round's entry.
    assert _set(root, "review", "--round", "1", "--status", "approved")[0] == 0
    assert _entries(task_dir, "review")[0]["status"] == "approved"
    # A reassessment keeps every round of a voluntary kind as it was: nothing earned
    # the review, so nothing can unearn it.
    from test_generation_store import _evaluate_write
    before_rounds = _entries(task_dir, "review")
    body = _manifest_of(task_dir)
    body["assessment"]["size"] = "large"
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    assert _evaluate_write(root, "--reason", "bigger than assessed")[0] == 0
    assert _manifest_of(task_dir)["delivery_approach"] == "full"
    assert _entries(task_dir, "review") == before_rounds
    # A path that is not review-<n>.md is refused, naming the pattern.
    before = (task_dir / "manifest.yml").read_bytes()
    code, out, err = _set(root, "review", "--status", "draft", "--path", _doc(root, "review-final.md"))
    assert code == 2 and "review-<n>.md" in err, out + err
    assert (task_dir / "manifest.yml").read_bytes() == before
    # A round named with a path of another round is refused.
    code, out, err = _set(root, "review", "--round", "1", "--status", "draft", "--path", two)
    assert code == 2 and "round" in err, out + err
    assert (task_dir / "manifest.yml").read_bytes() == before


def _pass_every_gate(task_dir):
    body = _manifest_of(task_dir)
    for gate in body.get("gates") or []:
        gate["status"] = "pass"
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")


def test_acf_58(tmp_path):
    root, task_dir = _registry_project(tmp_path)
    for n in (1, 2, 3):
        path = _doc(root, f"review-{n}.md")
        assert _set(root, "review", "--status", "draft", "--path", path)[0] == 0
    for n in (1, 2):
        assert _set(root, "review", "--round", str(n), "--status", "approved")[0] == 0
    ids = {n: e["id"] for n, e in enumerate(_entries(task_dir, "review"), 1)}
    assert len(set(ids.values())) == 3
    _pass_every_gate(task_dir)

    # compass check: round 3 is the one not approved, named by its entry id.
    code, out, err = _cli(root, "check", "--issue", SLUG, "--json")
    rows = {r["name"]: r for r in json.loads(out)["checks"]}
    detail = rows["artifacts-approved"]["detail"]
    assert ids[3] in detail and "round 3" in detail, detail
    assert ids[1] not in detail and ids[2] not in detail, detail

    # The issue page lists each round with its own entry id and path.
    code, out, err = _cli(root, "issue", "render", "--issue", SLUG)
    assert code == 0, out + err
    page = (root / HOME / "README.md").read_text(encoding="utf-8")
    for n in (1, 2, 3):
        lines = [line for line in page.splitlines() if ids[n] in line]
        assert len(lines) == 1 and f"review-{n}.md" in lines[0], (n, lines)

    # The board lists each round too.
    board = tmp_path / "board.html"
    code, out, err = _cli(root, "flow", "--html", str(board))
    assert code == 0, out + err
    html = board.read_text(encoding="utf-8")
    for n in (1, 2, 3):
        assert ids[n] in html and f"review-{n}.md" in html, n

    # The receipt lists each round, draft or not.
    code, out, err = _cli(root, "issue", "receipt", "--issue", SLUG)
    assert code == 0, out + err
    for n in (1, 2, 3):
        lines = [line for line in out.splitlines() if ids[n] in line]
        assert len(lines) == 1 and f"review-{n}.md" in lines[0], (n, lines, out)

    # A reader that asks for the review with no round gets round 3.
    code, out, err = _cli(root, "issue", "artifact-path", "review", "--issue", SLUG)
    assert code == 0 and out.strip().endswith("review-3.md"), out + err
    from compass_pkg import core
    state, path, why = core.resolve_artifact(str(task_dir), "review")
    assert state == core.FOUND and path.endswith("review-3.md"), (state, path, why)
    state, path, why = core.resolve_artifact(str(task_dir), "review", round=1)
    assert state == core.FOUND and path.endswith("review-1.md"), (state, path, why)


def test_acf_14(tmp_path):
    root, task_dir = _registry_project(tmp_path)
    for kind, name in (("bug-report", "bug-report.md"), ("review", "review-1.md"),
                       ("architecture-notes", "architecture-notes.md"),
                       ("product-owner-review", "product-owner-review.md"),
                       ("spike-conclusion", "spike-conclusion.md"),
                       ("positioning", "positioning.md"),
                       ("technical-design", "technical-design.md")):
        before = (task_dir / "manifest.yml").read_bytes()
        code, out, err = _set(root, kind, "--status", "draft", "--path",
                              f".compass/work/{SLUG}/{name}")
        assert code == 2, (kind, out + err)
        shown = "review-<n>.md" if kind == "review" else name
        assert kind in err and f"{HOME}/{shown}" in err, (kind, err)
        assert (task_dir / "manifest.yml").read_bytes() == before, kind
    # The home itself is accepted.
    assert _set(root, "bug-report", "--status", "draft",
                "--path", _doc(root, "bug-report.md"))[0] == 0


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


def test_acf_30(tmp_path):
    root, task_dir = _registry_project(tmp_path, goal="exploration")
    assert _manifest_of(task_dir)["delivery_approach"] == "spike"
    path = _doc(root, "spike-conclusion.md")
    assert _set(root, "spike-conclusion", "--status", "draft", "--path", path)[0] == 0

    def verdict():
        code, out, err = _cli(root, "check", "--issue", SLUG, "--json")
        rows = {r["name"]: r for r in json.loads(out)["checks"]}
        return rows["spike-conclusion-present"]

    row = verdict()
    assert row["status"] == "fail" and "no `spike-conclusion` evidence" in row["detail"], row
    body = _manifest_of(task_dir)
    body["evidence"] = [{"id": "EV-1", "type": "spike-conclusion", "decision": "discard",
                         "path": path}]
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    row = verdict()
    assert row["status"] == "pass" and "discard" in row["detail"], row
    body["evidence"][0]["decision"] = "graduate-to-delivery"
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    row = verdict()
    assert row["status"] == "fail" and "next_task" in row["detail"], row
    # The definition in the shipped checks catalogue is unchanged and locked.
    checks = yaml.safe_load((ROOT / "governance" / "presets" / "default" / "checks.yml")
                            .read_text(encoding="utf-8"))["checks"]
    one = checks["spike-conclusion-present"]
    assert (one["kind"], one["impl"], one["severity"], one["on_skipped"], one["locked"]) == (
        "deterministic", "spike-conclusion-present", "blocking", "fail", True)
    assert " ".join(one["statement"].split()) == (
        "A spike has a `spike-conclusion` evidence entry with a recorded decision "
        "(discard | graduate-to-delivery | defer); graduate-to-delivery links the next issue.")


def test_acf_62(tmp_path):
    root, task_dir = _registry_project(tmp_path, goal="exploration")
    path = _doc(root, "spike-conclusion.md")
    code, out, err = _set(root, "spike-conclusion", "--status", "draft", "--path", path,
                          "--decision", "discard")
    assert code == 0, out + err
    held = _entries(task_dir, "spike-conclusion")
    assert len(held) == 1 and held[0]["path"] == path
    records = [e for e in _manifest_of(task_dir)["evidence"] if e.get("type") == "spike-conclusion"]
    assert len(records) == 1 and records[0]["decision"] == "discard", records
    assert path in str(records[0]["path"]).replace("\\", "/").replace("../", ""), records
    code, out, err = _cli(root, "check", "--issue", SLUG, "--json")
    rows = {r["name"]: r for r in json.loads(out)["checks"]}
    assert rows["spike-conclusion-present"]["status"] == "pass", rows["spike-conclusion-present"]
    # A graduation without the next issue, and a decision that is not allowed, write nothing.
    before = (task_dir / "manifest.yml").read_bytes()
    code, out, err = _set(root, "spike-conclusion", "--status", "draft", "--path", path,
                          "--decision", "graduate-to-delivery")
    assert code == 2 and "--next-issue" in err, out + err
    code, out, err = _set(root, "spike-conclusion", "--status", "draft", "--path", path,
                          "--decision", "keep")
    assert code == 2, out + err
    for word in ("discard", "graduate-to-delivery", "defer"):
        assert word in err
    code, out, err = _set(root, "bug-report", "--status", "draft",
                          "--path", _doc(root, "bug-report.md"), "--decision", "discard")
    assert code == 2 and "--decision" in err, out + err
    assert (task_dir / "manifest.yml").read_bytes() == before
    # Running it again with another decision updates the one record.
    code, out, err = _set(root, "spike-conclusion", "--status", "draft", "--path", path,
                          "--decision", "defer")
    assert code == 0, out + err
    records = [e for e in _manifest_of(task_dir)["evidence"] if e.get("type") == "spike-conclusion"]
    assert len(records) == 1 and records[0]["decision"] == "defer", records
    code, out, err = _set(root, "spike-conclusion", "--status", "draft", "--path", path,
                          "--decision", "graduate-to-delivery", "--next-issue", "next-issue")
    assert code == 0, out + err
    records = [e for e in _manifest_of(task_dir)["evidence"] if e.get("type") == "spike-conclusion"]
    assert len(records) == 1 and records[0]["next_task"] == "next-issue", records


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


def test_acf_24(tmp_path):
    root, task_dir = _registry_project(tmp_path)
    _with_subtasks(task_dir, 1)
    # Gates still open: the line that says nothing is judged yet names the map as not needed.
    row = _check_row(root)
    assert row["status"] == "nothing-to-check", row
    assert "distribution-map" in row["detail"] and "not needed: one subtask" in row["detail"], row
    # Every gate passed: the verdict does not fail on the map, and says it is not needed.
    _pass_every_gate(task_dir)
    row = _check_row(root)
    assert row["status"] == "fail" and "distribution-map reads draft" not in row["detail"], row
    assert "distribution-map: not needed: one subtask" in row["detail"], row
    _approve_others(root, task_dir)
    row = _check_row(root)
    assert row["status"] == "pass", row
    assert "distribution-map: not needed: one subtask" in row["detail"], row


def test_acf_25(tmp_path):
    root, task_dir = _registry_project(tmp_path)
    _with_subtasks(task_dir, 2)
    _pass_every_gate(task_dir)
    _approve_others(root, task_dir)
    row = _check_row(root)
    assert row["status"] == "fail" and "distribution-map reads draft" in row["detail"], row
    assert "not needed" not in row["detail"], row
    path = _doc(root, "distribution-map.md")
    assert _set(root, "distribution-map", "--status", "approved", "--path", path)[0] == 0
    row = _check_row(root)
    assert row["status"] == "pass", row


def _shown_everywhere(root, task_dir, tmp_path, text):
    """The issue page, the board panel and the receipt each carry `text` for the map."""
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
    code, out, err = _cli(root, "issue", "receipt", "--issue", SLUG)
    assert code == 0, out + err
    receipt = [line for line in out.splitlines() if "distribution-map" in line]
    assert len(receipt) == 1 and text in receipt[0], receipt
    return page, html, out


def test_acf_26(tmp_path):
    root, task_dir = _registry_project(tmp_path)
    _with_subtasks(task_dir, 1)
    page, html, receipt = _shown_everywhere(root, task_dir, tmp_path, "not needed: one subtask")
    for text in (page, html, receipt):
        assert "missing" not in text.lower() or "distribution-map" not in text.lower().split(
            "missing")[0][-60:], text
    assert "omitted" not in [ln for ln in page.splitlines() if "distribution-map" in ln][0]
    # The four drafts that remain are counted (the record, criteria, design and report); the
    # map is not one of them.
    assert "4 more still draft" in receipt, receipt
    # `compass next` does not name the map as outstanding work.
    code, out, err = _cli(root, "next", "--issue", SLUG)
    assert "distribution-map" not in out + err, out + err
    # The one function: the page and the board take the text from `artifact_owed`.
    from compass_pkg import artifact_owed, effective
    task = _manifest_of(task_dir)
    view = effective.view_or_legacy(str(task_dir))
    verdict = artifact_owed.owed(task, view, "distribution-map")
    assert (verdict.owed, verdict.text) == (False, "not needed: one subtask")
    _with_subtasks(task_dir, 2)
    verdict = artifact_owed.owed(_manifest_of(task_dir), view, "distribution-map")
    assert (verdict.owed, verdict.text) == (True, None)
    assert artifact_owed.subtask_count({}) == 0 and artifact_owed.subtask_count(
        {"subtasks": [{}, {}, {}]}) == 3
    assert tuple(artifact_owed.CONDITIONS) == tuple(
        __import__("compass_pkg.catalogue_spec", fromlist=["x"]).REQUIRED_WHEN_CONDITIONS)


def test_acf_27(tmp_path):
    root, task_dir = _registry_project(tmp_path)
    _with_subtasks(task_dir, 2)
    code, out, err = _set(root, "distribution-map", "--status", "omitted",
                          "--reason", "pair worked from the design")
    assert code == 0, out + err
    _pass_every_gate(task_dir)
    _approve_others(root, task_dir)
    row = _check_row(root)
    assert row["status"] == "pass", row
    assert "not needed" not in row["detail"], row
    code, out, err = _cli(root, "issue", "render", "--issue", SLUG)
    assert code == 0, out + err
    page = (root / HOME / "README.md").read_text(encoding="utf-8")
    line = [ln for ln in page.splitlines() if "distribution-map" in ln]
    assert len(line) == 1 and "omitted" not in line[0] or "pair worked from the design" in line[0]
    assert "pair worked from the design" in line[0] and "not needed" not in page, line
    # One subtask, the same omission: the person's record still shows, with its reason.
    _with_subtasks(task_dir, 1)
    row = _check_row(root)
    assert "not needed" not in row["detail"], row
    code, out, err = _cli(root, "issue", "render", "--issue", SLUG)
    page = (root / HOME / "README.md").read_text(encoding="utf-8")
    line = [ln for ln in page.splitlines() if "distribution-map" in ln]
    assert "pair worked from the design" in line[0] and "not needed" not in page, line


def test_acf_28(tmp_path):
    root, task_dir = _registry_project(tmp_path)
    assert "subtasks" not in _manifest_of(task_dir)
    row = _check_row(root)
    assert "distribution-map" in row["detail"], row
    assert "not needed: no subtasks recorded" in row["detail"], row
    _pass_every_gate(task_dir)
    _approve_others(root, task_dir)
    row = _check_row(root)
    assert row["status"] == "pass" and "not needed: no subtasks recorded" in row["detail"], row
    # Breakdown records two subtasks: the map is owed.
    _with_subtasks(task_dir, 2)
    row = _check_row(root)
    assert row["status"] == "fail" and "distribution-map reads draft" in row["detail"], row
    # A full issue capped at one worktree, with one subtask, does not owe it either.
    other = tmp_path / "full"
    other.mkdir()
    root2, task_dir2 = _registry_project(other, goal="delivery")
    body = _manifest_of(task_dir2)
    body["delivery_approach"] = "full"
    (task_dir2 / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                            encoding="utf-8")
    _with_subtasks(task_dir2, 1)
    _pass_every_gate(task_dir2)
    row = _check_row(root2)
    assert "distribution-map reads draft" not in row["detail"], row
    assert "not needed: one subtask" in row["detail"], row


# --- group D: the delivery-approach record on every approach -----------------------

DIMENSIONS = ("risk", "familiarity", "size", "goal", "role", "urgency")


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


FIVE_APPROACHES = {
    "quick-fix": ({"risk": "trivial", "size": "atomic"}, "lightweight"),
    "regular": ({}, "thorough"),
    "hotfix": ({"urgency": "live-defect", "size": "small"}, "lightweight"),
    "full": ({"risk": "critical", "size": "large"}, "thorough"),
    "spike": ({"goal": "exploration"}, "lightweight"),
}


def test_acf_16(tmp_path):
    for approach, (assessment, depth) in FIVE_APPROACHES.items():
        root, task_dir = _fixture(tmp_path, approach, **assessment)
        body = _manifest_of(task_dir)
        code, out, err = _evaluate(root, *_justify_all(body["assessment"]))
        assert code == 0, (approach, out + err)
        body = _manifest_of(task_dir)
        assert body["delivery_approach"] == approach
        found = [a for a in body["artifacts"] if a["kind"] == "delivery-approach"]
        assert len(found) == 1, (approach, body["artifacts"])
        assert found[0]["status"] == "draft" and found[0]["depth"] == depth, (approach, found)
        assert "path" not in found[0], (approach, found)
        code, out, err = _cli(root, "issue", "artifact-path", "delivery-approach",
                              "--issue", SLUG)
        assert code == 0 and out.strip() == f"{HOME}/delivery-approach.md", (approach, out + err)
    # The depth follows the issue's configuration: a layer that lightens regular's
    # assess stage registers the record at lightweight. The shipped lint refuses such a
    # loosening without a waiver, so the layer is merged here and evaluated directly.
    import copy

    from compass_pkg import effective, merge, policy_lint, routing
    parent, _ = policy_lint.load_parent()
    base, provenance = merge.apply({}, parent.doc, parent.kind, parent.name, {})
    layer = {"schema": 1, "approaches": {"regular": {"set": {"stages": {
        "set": {"assess": "lightweight"}}}}}}
    child, _ = merge.apply(copy.deepcopy(base), layer, "project", "project", dict(provenance))
    for config, depth in ((base, "thorough"), (child, "lightweight")):
        view = effective.EffectiveView("live", SLUG, None, config, {})
        result = routing.evaluate_route(
            {"risk": "contained", "familiarity": "brownfield-mapped", "size": "medium",
             "goal": "delivery", "role": "engineer", "labels": []}, view.evaluator_policy())
        assert result["delivery_approach"] == "regular"
        found = [a for a in result["artifacts"] if a["kind"] == "delivery-approach"]
        assert [a["depth"] for a in found] == [depth], found


#: Words that send a writer to the old home, beside the manifest.
OLD_HOME_TEXTS = (r"\.compass/work/<[^>]*>/delivery-approach\.md",
                  r"into the issue directory",
                  r"alongside\s+`delivery-approach\.md`")


def test_acf_17(tmp_path):
    import re
    root, task_dir = _fixture(tmp_path, "regular")
    code, out, err = _evaluate(root, *_justify_all(_manifest_of(task_dir)["assessment"]))
    assert code == 0, out + err
    code, out, err = _cli(root, "issue", "artifact-path", "delivery-approach", "--issue", SLUG)
    assert code == 0, out + err
    path = out.strip()
    assert path == f"{HOME}/delivery-approach.md", path
    _write(root / path, "# Delivery approach - feature\n")
    code, out, err = _set(root, "delivery-approach", "--status", "draft", "--path", path)
    assert code == 0, out + err
    entry = _entries(task_dir, "delivery-approach")
    assert len(entry) == 1 and entry[0]["path"] == path, entry
    assert (root / path).is_file() and not (task_dir / "delivery-approach.md").exists()
    # A quick fix writes and registers the record at the same home.
    qf = _scratch(tmp_path / "qf-holder") if False else tmp_path / "qf"
    (qf / ".compass").mkdir(parents=True)
    code, out, err = _cli(qf, "quick-fix", "start", "fix-it",
                          "--risk", "trivial - one line", "--familiarity",
                          "brownfield-mapped - mapped", "--size", "atomic - one file",
                          "--intent", "A quick fix records its approach in the documents folder.",
                          "--scenario", "A quick fix records its approach in one place",
                          "--test", "tests/test_x.py::test_x")
    assert code == 0, out + err
    qf_home = next((qf / "docs" / "compass").iterdir())
    assert (qf_home / "delivery-approach.md").is_file()
    assert not (qf / ".compass" / "work" / "fix-it" / "delivery-approach.md").exists()
    code, out, err = _cli(qf, "issue", "artifact-path", "delivery-approach", "--issue", "fix-it")
    assert code == 0 and out.strip().endswith(f"{qf_home.name}/delivery-approach.md"), out + err
    # No writer's instructions name the old home.
    for folder in ("commands", "agents", "skills", "approaches"):
        for text_file in sorted((ROOT / folder).rglob("*.md")):
            text = text_file.read_text(encoding="utf-8")
            for pattern in OLD_HOME_TEXTS:
                assert not re.search(pattern, text), (str(text_file), pattern)
    for name in ("approaches/assess-procedure.md", "agents/router.md", "approaches/rubric.md"):
        assert "artifact-path delivery-approach" in (ROOT / name).read_text(encoding="utf-8"), name


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


def test_acf_18(tmp_path):
    from test_hook_artifact_paths import DOCS_REL, _pre_tool
    project = _hook_issue(tmp_path, "found", register=True, documents=True, beside=False)
    ran = _pre_tool(project)
    assert ran.returncode == 0 and "no-delivery-approach" not in ran.stderr, ran.stderr
    (project / DOCS_REL / "delivery-approach.md").unlink()
    ran = _pre_tool(project)
    assert ran.returncode != 0 and "delivery-approach" in ran.stderr, ran.stderr
    assert "a-moved-issue" in ran.stderr, ran.stderr


def test_acf_19(tmp_path):
    from test_hook_artifact_paths import DOCS_REL, _stop
    project = _hook_issue(tmp_path, "found", register=True, documents=True, beside=False)
    assert "MISSING" not in _stop(project).stderr
    (project / DOCS_REL / "delivery-approach.md").unlink()
    assert "delivery-approach record is MISSING" in _stop(project).stderr


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
    assert set(body["justifications"]) == {"risk", "familiarity", "size", "goal", "role"}
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


def test_acf_22(tmp_path):
    qf = tmp_path / "qf"
    (qf / ".compass").mkdir(parents=True)
    base = ["quick-fix", "start", "fix-it", "--risk", "trivial - risk reason",
            "--familiarity", "brownfield-mapped - familiarity reason",
            "--size", "atomic - size reason",
            "--intent", "A quick fix records each reason it was given.",
            "--scenario", "A quick fix shows every reason in its record",
            "--test", "tests/test_x.py::test_x"]
    # A goal or role with no reason is refused before anything is written.
    for flag, word in (("--goal", "goal"), ("--role", "role")):
        value = "delivery" if word == "goal" else "engineer"
        code, out, err = _cli(qf, *base, flag, value)
        assert code == 2 and word in err, out + err
        assert not (qf / ".compass" / "work" / "fix-it").exists()
        assert not (qf / "docs").exists()
    code, out, err = _cli(qf, *base, "--goal", "delivery - goal reason",
                          "--role", "engineer - role reason")
    assert code == 0, out + err
    body = yaml.safe_load((qf / ".compass" / "work" / "fix-it" / "manifest.yml").read_text())
    assert body["justifications"] == {
        "risk": "risk reason", "familiarity": "familiarity reason", "size": "size reason",
        "goal": "goal reason", "role": "role reason"}, body["justifications"]
    assert set(body["assessment"]) == {"risk", "familiarity", "size", "goal", "role", "labels"}
    record = (next((qf / "docs" / "compass").iterdir()) / "delivery-approach.md").read_text()
    for dim, reason in body["justifications"].items():
        assert any(dim.capitalize() in line and reason in line
                   for line in record.splitlines()), (dim, record)
    assert "(no reason given)" not in record
    for folder in ("cli", "hooks"):
        for source in (ROOT / folder).rglob("*"):
            if source.is_file() and "__pycache__" not in str(source) and "vendor" not in str(
                    source.relative_to(ROOT)):
                try:
                    text = source.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                assert "(no reason given)" not in text, str(source)
    # An omitted goal and role record no value and no justification (read as "not assessed").
    other = tmp_path / "plain"
    (other / ".compass").mkdir(parents=True)
    code, out, err = _cli(other, *[a if a != "fix-it" else "plain-fix" for a in base])
    assert code == 0, out + err
    plain = yaml.safe_load((other / ".compass" / "work" / "plain-fix" / "manifest.yml").read_text())
    assert "goal" not in plain["assessment"] and "role" not in plain["assessment"]
    assert set(plain["justifications"]) == {"risk", "familiarity", "size"}
    plain_record = (next((other / "docs" / "compass").iterdir()) / "delivery-approach.md").read_text()
    assert "(no reason given)" not in plain_record and "| Goal |" not in plain_record
    # The readers print "not assessed" for the absent values.
    code, out, err = _cli(other, "issue", "receipt", "--issue", "plain-fix")
    assert code == 0, out + err
    goal_line = [ln for ln in out.splitlines() if ln.strip().startswith("goal")]
    assert len(goal_line) == 1 and "not assessed" in goal_line[0], out
    assert "engineer" not in goal_line[0] and "delivery" not in goal_line[0], goal_line
    html = other / "board.html"
    code, out, err = _cli(other, "flow", "--html", str(html))
    assert code == 0, out + err
    assert "not assessed" in html.read_text(encoding="utf-8")
    code, out, err = _cli(other, "flow", "--json")
    assert code == 0, out + err
    rows = [r for lane in json.loads(out)["sections"].values() for r in lane
            if r.get("slug") == "plain-fix"]
    assert rows and rows[0]["assessment"]["goal"] == "not assessed", rows
    code, out, err = _cli(other, "retro")
    assert code == 0 and "None" not in out, out + err


def test_acf_29(tmp_path):
    root = _scratch(tmp_path)
    shown = _show(root)
    assert shown["approaches.spike.artifacts"] == {
        "delivery-approach": "lightweight", "spike-conclusion": "thorough"}
    assert shown["approaches.spike.locked"] is True
    root, task_dir = _fixture(tmp_path, "spike", goal="exploration")
    code, out, err = _evaluate(root, *_justify_all(_manifest_of(task_dir)["assessment"]))
    assert code == 0, out + err
    body = _manifest_of(task_dir)
    assert body["delivery_approach"] == "spike"
    got = {a["kind"]: a for a in body["artifacts"]}
    assert set(got) == {"delivery-approach", "spike-conclusion"}
    assert (got["delivery-approach"]["depth"], got["spike-conclusion"]["depth"]) == (
        "lightweight", "thorough")
    assert all("path" not in a for a in got.values())
    for kind in got:
        code, out, err = _cli(root, "issue", "artifact-path", kind, "--issue", SLUG)
        assert code == 0 and out.strip() == f"{HOME}/{kind}.md", (kind, out + err)


# --- group G: the delivery-approach record's rendered blocks (FU-1) ---------------

def _template(name):
    return (ROOT / "templates" / name).read_text(encoding="utf-8")


def _section(text, heading):
    """The lines under `heading` (a line start), up to the next heading of the same or
    a higher level."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(heading))
    level = len(heading) - len(heading.lstrip("#"))
    out = []
    for line in lines[start + 1:]:
        stripped = line.lstrip("#")
        if line.startswith("#") and stripped.startswith(" ") and len(line) - len(stripped) <= level:
            break
        out.append(line)
    return "\n".join(out)


def _without_comments(text):
    import re
    return re.sub(r"<!--(?!\s*/?compass:render).*?-->", "", text, flags=re.S)


def test_acf_34():
    from compass_pkg import block_renderers, rendered_blocks
    text = _template("delivery-approach.md")
    sections = {"## 1. ": "assessment", "## 3. ": "policy-rules",
                "### 4a. ": "stage-weights", "### 4b. ": "gate-set"}
    for heading, kind in sections.items():
        body = _section(text, heading)
        found = [b.kind for b in rendered_blocks.parse(body).blocks]
        assert found == [kind], (heading, found)
        outside = _without_comments(rendered_blocks.masked_text(body))
        assert not [ln for ln in outside.splitlines() if ln.lstrip().startswith("|")], heading
        assert "{{" not in outside, heading
        assert kind in rendered_blocks.KINDS
        assert kind in block_renderers.RENDERERS


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


def test_acf_35(tmp_path):
    reasons = {"risk": "The migrate moves folders Git cannot restore.",
               "familiarity": "The catalogue is documented.",
               "size": "It touches fourteen modules.",
               "goal": "The outcome wanted is a delivered change.",
               "role": "An engineer asked for it."}
    root, task_dir, record = _approach_issue(
        tmp_path, "full", reasons=reasons, risk="critical", size="large",
        labels=["cli", "migrations"])
    _render(root)
    block = _block(record.read_text(encoding="utf-8"), "assessment")
    values = _manifest_of(task_dir)["assessment"]
    assert (values["risk"], values["familiarity"], values["size"]) == (
        "critical", "brownfield-mapped", "large")
    rows = [line for line in block.splitlines() if line.startswith("|")]
    for dim, value in (("risk", "critical"), ("familiarity", "brownfield-mapped"),
                       ("size", "large"), ("goal", "delivery"), ("role", "engineer")):
        hit = [r for r in rows if dim.capitalize() in r and value in r and reasons[dim] in r]
        assert len(hit) == 1, (dim, block)
    assert "Labels: cli, migrations" in block, block
    code, out, err = _cli(root, "issue", "receipt", "--issue", SLUG)
    assert code == 0, out + err
    for dim in ("risk", "familiarity", "size"):
        assert reasons[dim] in out, (dim, out)
    # An archived issue with no justifications key: the receipt reads the record's table.
    old = tmp_path / "old"
    old.mkdir()
    root2, task_dir2 = _fixture(tmp_path, "archived")
    _rewrite_manifest(task_dir2, assessment=dict(_manifest_of(task_dir2)["assessment"]))
    body = _manifest_of(task_dir2)
    body.pop("justifications", None)
    (task_dir2 / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                            encoding="utf-8")
    _write(root2 / HOME / "delivery-approach.md",
           "# Delivery approach - feature\n\n| Dimension | Value | One-line justification |\n"
           "|---|---|---|\n| **Risk** | contained | Hand-written risk reason. |\n"
           "| **Familiarity** | brownfield-mapped | Hand-written familiarity reason. |\n"
           "| **Size** | medium | Hand-written size reason. |\n")
    _set(root2, "delivery-approach", "--status", "draft", "--path",
         f"{HOME}/delivery-approach.md")
    code, out, err = _cli(root2, "issue", "receipt", "--issue", SLUG)
    assert code == 0 and "Hand-written risk reason." in out, out + err


def test_acf_36(tmp_path):
    root, task_dir, record = _approach_issue(tmp_path, "rules")
    fired = [
        {"id": "RP-FLOOR-001", "kind": "floor", "rationale": "Migrations are never light.",
         "changed": ["approach raised to full"]},
        {"id": "RP-REQUIRE-006", "kind": "requirement",
         "rationale": "A public API needs a design.", "changed": ["artifact 'technical-design' required"]},
        {"id": "RP-CAP-001", "kind": "cap", "rationale": "Critical work runs one worktree.",
         "changed": ["max_worktrees 1"]},
    ]
    _rewrite_manifest(task_dir, policy_rules_fired=fired)
    _render(root)
    block = _block(record.read_text(encoding="utf-8"), "policy-rules")
    rows = [line for line in block.splitlines() if line.startswith("|")]
    for rule in fired:
        hit = [r for r in rows if rule["id"] in r and rule["kind"] in r
               and rule["changed"][0] in r and rule["rationale"] in r]
        assert len(hit) == 1, (rule["id"], block)
    generation = _manifest_of(task_dir)["generation"]
    assert "Policy:" in block and f"Generation: {generation}" in block, block
    # No rule fired.
    _rewrite_manifest(task_dir, policy_rules_fired=[])
    _render(root)
    block = _block(record.read_text(encoding="utf-8"), "policy-rules")
    assert "No policy rule fired." in block and "RP-" not in block, block
    assert "Generation: %s" % generation in block, block


def test_acf_37(tmp_path):
    root, task_dir, record = _approach_issue(tmp_path, "gates", risk="critical", size="large")
    gate_ids = ["plan.exit", "implement.tests", "verify.correctness", "verify.governance",
                "verify.traceability", "verify.security", "verify.docs", "ship.merge",
                "ship.follow-ups"]
    gates = [{"id": g, "status": "pending", "evidence": []} for g in gate_ids]
    fired = [{"id": "RP-REQUIRE-006", "kind": "floor", "rationale": "A rule.",
              "changed": [f"gate '{gate_ids[5]}' added to the approach's gate set"]},
             {"id": "RP-ROLE-002", "kind": "role_rule", "rationale": "Another rule.",
              "changed": [f"gate '{gate_ids[6]}' added to the approach's gate set"]}]
    stages = {"assess": "thorough", "define": "thorough", "refine": "lightweight",
              "plan": "thorough", "breakdown": "skipped", "implement": "thorough",
              "verify": "thorough", "ship": "lightweight"}
    _rewrite_manifest(task_dir, gates=gates, policy_rules_fired=fired, stages=stages)
    _render(root)
    text = record.read_text(encoding="utf-8")
    weights = _block(text, "stage-weights")
    rows = [line for line in weights.splitlines() if line.startswith("|")][2:]
    assert [r.split("|")[1].strip() for r in rows] == list(stages), weights
    assert [r.split("|")[2].strip() for r in rows] == list(stages.values()), weights
    block = _block(text, "gate-set")
    listed = [line for line in block.splitlines() if line.startswith("- ")]
    assert [line[2:].split(" ")[0].strip("`") for line in listed] == gate_ids, block
    assert "RP-REQUIRE-006" in listed[5] and "RP-ROLE-002" in listed[6], block
    assert not any("RP-" in listed[i] for i in (0, 1, 2, 3, 4, 7, 8)), block


def _check_rows(root):
    code, out, err = _cli(root, "check", "--issue", SLUG, "--json")
    assert out.strip().startswith("{"), out + err
    return {c["name"]: c for c in json.loads(out)["checks"]}


def test_acf_38(tmp_path):
    from compass_pkg import rendered_blocks
    root, task_dir, record = _approach_issue(tmp_path, "stale")
    _rewrite_manifest(task_dir, current_phase="verify")
    _render(root)
    assert _check_rows(root)["rendered-blocks-current"]["status"] == "pass"
    values = _manifest_of(task_dir)["assessment"]
    assert values["risk"] == "contained"
    _rewrite_manifest(task_dir, assessment=dict(values, risk="critical"))
    row = _check_rows(root)["rendered-blocks-current"]
    path = f"{HOME}/delivery-approach.md"
    assert row["status"] == "fail", row
    assert path in row["detail"] and "assessment" in row["detail"], row["detail"]
    before = record.read_text(encoding="utf-8")
    _render(root)
    assert _check_rows(root)["rendered-blocks-current"]["status"] == "pass"
    after = record.read_text(encoding="utf-8")
    assert "critical" in _block(after, "assessment")
    assert rendered_blocks.masked_text(after) == rendered_blocks.masked_text(before)
    _render(root)
    assert record.read_text(encoding="utf-8") == after


GATE_TEMPLATES = ("distribution-map.md", "requirements-review.md", "technical-design.md",
                  "verification-report.md")
PLAN_CHECK = "plan-reviewed"
PLAN_LAYER = {"schema": 1,
              "checks": {PLAN_CHECK: {"statement": "The design was read by a second engineer.",
                                      "kind": "human", "severity": "blocking",
                                      "on_skipped": "not-applicable"}},
              "stages": {"plan": {"set": {"exit": {"add": [PLAN_CHECK]}}}}}


def test_acf_39(tmp_path):
    import re
    from compass_pkg import rendered_blocks
    box = re.compile(r"^\s*- \[[ xX]\]", re.M)
    kinds = {}
    for name in GATE_TEMPLATES:
        text = _template(name)
        assert not box.search(text), name
        kinds[name] = [b.kind for b in rendered_blocks.parse(text).blocks]
    review = _template("requirements-review.md")
    parsed = rendered_blocks.parse(review)
    last = parsed.blocks[-1]
    assert last.kind == "dor"
    tail = "".join(parsed.lines[last.end + 1:]).strip().splitlines()
    assert all(not ln.startswith("#") for ln in tail) and len(tail) <= 1, tail
    assert {"gates", "dod"} <= set(kinds["verification-report.md"])
    assert "plan-exit" in kinds["technical-design.md"]
    assert "breakdown-exit" in kinds["distribution-map.md"]
    assert "plan-exit" not in kinds["distribution-map.md"]
    # The shipped default lists no exit check for plan or breakdown.
    root, task_dir = _fixture(tmp_path, "shipped")
    documents = {}
    for kind in ("technical-design", "distribution-map"):
        path = _doc(root, f"{kind}.md", _template(f"{kind}.md"))
        documents[kind] = root / path
        code, out, err = _set(root, kind, "--status", "draft", "--path", path)
        assert code == 0, out + err
    _render(root)
    assert _block(documents["technical-design"].read_text(encoding="utf-8"), "plan-exit").strip() \
        == "No exit checks are configured for the plan stage."
    assert _block(documents["distribution-map"].read_text(encoding="utf-8"),
                  "breakdown-exit").strip() == "No exit checks are configured for the breakdown stage."
    # A layer that adds an exit check to plan: the block lists it, with its state.
    root2, task_dir2 = _fixture(tmp_path, "layered", layer=PLAN_LAYER)
    path = _doc(root2, "technical-design.md", _template("technical-design.md"))
    code, out, err = _set(root2, "technical-design", "--status", "draft", "--path", path)
    assert code == 0, out + err
    _render(root2)
    design = root2 / path
    shown = _block(design.read_text(encoding="utf-8"), "plan-exit")
    assert PLAN_CHECK in shown and "open" in shown and "0 of 1 met" in shown, shown
    # A box typed by hand beside the block changes no item's state.
    design.write_text(design.read_text(encoding="utf-8") + f"\n- [x] {PLAN_CHECK}\n",
                      encoding="utf-8")
    _render(root2)
    assert _block(design.read_text(encoding="utf-8"), "plan-exit") == shown
    # Evidence recorded for an exit check meets the item: `--meets` accepts a stage exit check.
    _write(task_dir2 / "evidence.txt", "reviewed\n")
    code, out, err = _cli(root2, "evidence", "add", "EV-PLAN", "--issue", SLUG, "--type",
                          "command-output", "--path", "evidence.txt", "--meets", PLAN_CHECK)
    assert code == 0, out + err
    _render(root2)
    shown = _block(design.read_text(encoding="utf-8"), "plan-exit")
    assert "1 of 1 met" in shown and "met by EV-PLAN" in shown, shown


ASSESS_TEXTS = ("approaches/assess-procedure.md", "agents/router.md", "commands/assess.md")


def test_acf_64():
    # A re-assessment changes values, and evaluate --write refuses a changed value with
    # no justification (ACF-21). A text that tells the reader to run it bare sends them
    # into that refusal.
    import re
    for name in ASSESS_TEXTS:
        text = " ".join((ROOT / name).read_text(encoding="utf-8").split())
        spans = re.findall(r"`compass approach evaluate --write[^`]*`", text)
        assert spans, f"{name} no longer names `approach evaluate --write`"
        bare = [s for s in spans if "--justify" not in s]
        assert not bare, f"{name} shows approach evaluate --write without --justify: {bare}"


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
    # registered, so the migrate must not report it as unmapped (architect ruling AD-4).
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
    # The stop test can fail: moving the file before registering it leaves the hook blocking.
    from test_hook_artifact_paths import _pre_tool
    project = _hook_issue(tmp_path, "swapped", register=False, documents=False, beside=True)
    home = project / DOCS_REL
    home.mkdir(parents=True, exist_ok=True)
    os.replace(project / ".compass/work/a-moved-issue/delivery-approach.md", home / "delivery-approach.md")
    ran = _pre_tool(project)
    assert ran.returncode != 0 and "no-delivery-approach" in ran.stderr, ran.stderr


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


def test_acf_53(tmp_path):
    root = _planted_sample(tmp_path)
    _write(root / "docs" / "compass" / f"{STAMP}-planted-rounds" / "notes-on-cache.md", "# notes\n")
    older = _issue_on_an_older_generation(tmp_path, root)
    # The walk sees a file that matches no kind, so it can fail.
    found = _unregistered(root)
    assert any("notes-on-cache.md" in line for line in found), found
    assert any(line.startswith(older + ":") and "review.md" in line for line in found), found
    (root / "docs" / "compass" / f"{STAMP}-planted-rounds" / "notes-on-cache.md").unlink()
    out = _migrated(root)
    assert _totals(out)["unmapped files"] == [0], out
    # A file the migrate named for a shipped kind is not reported on an issue whose
    # stored generation predates the kind (the maintainer's archive holds 37 such issues).
    assert _unregistered(root) == []


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
    migrate adopted, and is kept (architect ruling, BD-11's follow-on)."""
    from compass_pkg import artifact_owed, migrate_kinds
    found = []
    for slug, (data, work, docs) in _issues_of(root).items():
        if data.get("delivery_approach") != "regular" or artifact_owed.subtask_count(data) >= 2:
            continue
        if not isinstance(data.get("subtasks"), list) and \
                migrate_kinds._map_rows(str(docs / "distribution-map.md")) >= 2:
            continue
        entries = [e for e in data.get("artifacts") or [] if isinstance(e, dict)
                   and e.get("kind") == "distribution-map" and e.get("depth") in LIGHTWEIGHT
                   and e.get("status") not in ("superseded", "omitted")]
        owed = [e for e in entries if artifact_owed.owed(data, None, "distribution-map", e).owed]
        if entries and ((docs / "distribution-map.md").is_file() or owed):
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


def _after(root):
    run = subprocess.run([sys.executable, str(MEASURE), "--root", str(root), "--after", "--json"],
                         capture_output=True, text=True, timeout=600)
    assert run.returncode == 0, run.stdout + run.stderr
    return json.loads(run.stdout)


def _unopenable_in(root):
    """The archive citation test's check, resolved against `root` in place of this
    checkout: each citation on a tracked surface that does not open there."""
    import test_archive_citations_resolve as cites
    roots = cites._search_roots()
    original = cites._search_roots
    cites._search_roots = lambda: [Path(root)] + roots[1:]
    try:
        return cites._unopenable()
    finally:
        cites._search_roots = original


def test_acf_57(tmp_path):
    # The after mode on the planted sample: it reports the planted faults before the
    # migrate and none after.
    root = _planted_sample(tmp_path)
    before = _after(root)
    assert before["regular_without_record"] >= 3 and before["regular_small_with_map"] == 1, before
    assert before["review_not_numbered"] >= 3, before
    _migrated(root)
    after = _after(root)
    assert (after["unregistered_files"], after["regular_without_record"],
            after["regular_small_with_map"], after["review_not_numbered"],
            after["review_round_clashes"]) == (0, 0, 0, 0, 0), after
    assert after["regular_issues"] == after["regular_with_record"] >= 3, after

    # The maintainer's archive: a copy in a temporary folder, read only with the switch on.
    if os.environ.get("COMPASS_FULL_ARCHIVE") != "1":
        return
    held = _digests(ROOT)
    copy = tmp_path / "archive-copy"
    shutil.copytree(ROOT / ".compass" / "work", copy / ".compass" / "work")
    shutil.copytree(ROOT / "docs" / "compass", copy / "docs" / "compass")
    _migrated(copy)
    full = _after(copy)
    print(json.dumps(full, indent=2, sort_keys=True))
    print("regular issues that never had a record: %d; maps adopted with no depth: %d"
          % (full["regular_never_had_record"], full["regular_small_adopted_map"]))
    assert (full["unregistered_files"], full["regular_without_record"],
            full["regular_small_with_map"], full["review_not_numbered"],
            full["review_round_clashes"]) == (0, 0, 0, 0, 0), full
    assert _unopenable_in(copy) == {}
    assert _digests(ROOT) == held


def test_acf_67(tmp_path):
    # The after measure counts a missing record only on an issue that held one before
    # the migrate, and a small map only when the migrate registered it at lightweight
    # depth. It prints both exclusions, so neither is silent (architect ruling on the
    # archive measures).
    root = _planted_sample(tmp_path)
    _m_issue(root, "planted-none")
    _plant_adopted_map(root)
    _migrated(root)
    after = _after(root)
    assert (after["regular_without_record"], after["regular_never_had_record"]) == (0, 1), after
    assert (after["regular_small_with_map"], after["regular_small_adopted_map"]) == (0, 1), after
    assert after["issues"]["regular_never_had_record"] == ["planted-none"], after
    assert after["issues"]["regular_small_adopted_map"] == ["planted-adopted"], after
    run = subprocess.run([sys.executable, str(MEASURE), "--root", str(root), "--after"],
                         capture_output=True, text=True, timeout=600)
    assert "never had a record: 1" in run.stdout and "no depth: 1" in run.stdout, run.stdout
