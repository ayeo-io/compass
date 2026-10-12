"""Scenarios ACF-1 to ACF-63 of the issue `artifact-catalogue-fields`.

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

