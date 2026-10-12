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
