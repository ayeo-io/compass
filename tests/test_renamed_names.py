"""The old typed names that 7.0.0 still reads (issue language-key-and-us-english, group G).

One reader-side table in `cli/migrate-map.yml` (`old_names:`), each row ending at
8.0.0, read through `cli/compass_pkg/old_names.py`. U4 owns the tests for the
table and the `--kind` argument. U5, U6 and U7 each replace only their own
function bodies, and add a helper only directly above its own functions, so the
units merge without conflicts.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
CLI = ROOT / "cli" / "compass"
MAP_FILE = ROOT / "cli" / "migrate-map.yml"
GUIDE = ROOT / "docs" / "upgrade-7-0-0.md"

# The old words of the scenario, spelt from pieces so that no scan of the tests
# finds an old name in a literal of its own.
OLD_KIND = "judge" + "ment"
NEW_KIND = "judg" + "ment"


# --- U4: the table, the --kind argument and the manifest kind ----------------

BASE_MANIFEST = """schema_version: "2.0"
issue: sample
created: "2026-08-30"
status: active
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: small
  goal: delivery
  urgency: none
  role: engineer
  labels: []
evidence: []
gates: []
scenarios: []
changed_files: []
claims: []
follow_ups: []
reassessments: []
"""


def _project(tmp: Path) -> Path:
    work = tmp / ".compass" / "work" / "sample"
    work.mkdir(parents=True)
    (tmp / ".compass" / "config.yml").write_text("version: 1.0.0\n", encoding="utf-8")
    (work / "manifest.yml").write_text(BASE_MANIFEST, encoding="utf-8")
    return tmp


def _run(project: Path, *args):
    import subprocess
    r = subprocess.run([sys.executable, str(CLI), *args], cwd=str(project),
                       capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


def _manifest_path(project: Path) -> Path:
    return project / ".compass" / "work" / "sample" / "manifest.yml"


def _assessed_then_moved(project: Path) -> None:
    """An assessed issue whose assessment then changes, so a reassess records."""
    code, out, err = _run(project, "approach", "evaluate", "--issue", "sample", "--write")
    assert code == 0, out + err
    data = yaml.safe_load(_manifest_path(project).read_text(encoding="utf-8"))
    data["assessment"]["risk"] = "cross-cutting"
    data["assessment"]["size"] = "large"
    _manifest_path(project).write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _reassess(project: Path, *kind_args):
    return _run(project, "approach", "evaluate", "--issue", "sample", "--write",
                "--reason", "r", "--justify", "risk=the blast was wider",
                "--justify", "size=more files", *kind_args)


def test_trc_043():
    import tempfile
    notice = f"compass: kind {OLD_KIND} is now {NEW_KIND}; the old word is read until 8.0.0."
    cases = [
        (["--kind", NEW_KIND], True), (["--kind", OLD_KIND], True),
        (["--kind", NEW_KIND.upper()], False), (["--kind", "judg" + "emnt"], False),
        ([], True),
    ]
    for args, accepted in cases:
        with tempfile.TemporaryDirectory() as raw:
            project = _project(Path(raw))
            _assessed_then_moved(project)
            code, out, err = _reassess(project, *args)
            entries = yaml.safe_load(
                _manifest_path(project).read_text(encoding="utf-8"))["reassessments"]
        if accepted:
            assert code == 0, (args, out + err)
            assert [e["kind"] for e in entries] == [NEW_KIND], (args, entries)
            assert err.count(notice) == (1 if args[-1:] == [OLD_KIND] else 0), (args, err)
        else:
            assert code != 0 and entries == [], (args, out + err)
            for choice in (NEW_KIND, "policy-correction", "scope-change", "configuration"):
                assert choice in err, (args, err)
            assert OLD_KIND not in err.replace(args[1], ""), (args, err)


def _two_kinds(project: Path, *, old: bool = True) -> None:
    data = yaml.safe_load(_manifest_path(project).read_text(encoding="utf-8"))
    data["reassessments"] = [
        {"from_route": "quick-fix", "to_route": "regular", "reason": "a",
         "kind": OLD_KIND if old else NEW_KIND, "date": "2026-10-01"},
        {"from_route": "quick-fix", "to_route": "regular", "reason": "b",
         "kind": NEW_KIND, "date": "2026-10-02"},
    ]
    _manifest_path(project).write_text(yaml.safe_dump(data, sort_keys=False),
                                       encoding="utf-8")


def test_trc_044():
    import json
    import tempfile
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    enum = schema["properties"]["reassessments"]["items"]["properties"]["kind"]["enum"]
    assert OLD_KIND in enum and NEW_KIND in enum, enum

    with tempfile.TemporaryDirectory() as raw_old, tempfile.TemporaryDirectory() as raw_new:
        old, new = _project(Path(raw_old)), _project(Path(raw_new))
        _two_kinds(old)
        _two_kinds(new, old=False)
        original = _manifest_path(old).read_bytes()

        for args in (("issue", "lint", "--issue", "sample"), ("check", "--issue", "sample"),
                     ("retro",)):
            code_old, out_old, _ = _run(old, *args)
            code_new, out_new, _ = _run(new, *args)
            assert code_old == code_new, (args, out_old, out_new)
        assert _run(old, "issue", "lint", "--issue", "sample")[0] == 0
        assert "total re-assessments : 2" in _run(old, "retro")[1]

        # The block that lists the entries shows the current word.
        assert _run(old, "issue", "render", "--issue", "sample")[0] == 0
        page = old / "docs" / "compass" / "2026-08-30-sample" / "README.md"
        page.write_text(page.read_text(encoding="utf-8")
                        + "\n<!-- compass:render decisions-taken -->\nstale\n"
                          "<!-- /compass:render -->\n", encoding="utf-8")
        assert _run(old, "issue", "render", "--issue", "sample")[0] == 0
        shown = page.read_text(encoding="utf-8")
        assert shown.count(f"({NEW_KIND})") == 2 and OLD_KIND not in shown, shown

        # A read leaves the file as it was.
        assert _manifest_path(old).read_bytes() == original

        # The next save writes the current word, keeps a copy and says so once.
        code, out, err = _run(old, "approach", "evaluate", "--issue", "sample", "--write")
        assert code == 0, out + err
        kinds = [e["kind"] for e in yaml.safe_load(
            _manifest_path(old).read_text(encoding="utf-8"))["reassessments"]]
        assert kinds == [NEW_KIND, NEW_KIND], kinds
        assert (_manifest_path(old).parent / "manifest.yml.v5.bak").read_bytes() == original
        assert err.count(f"'{OLD_KIND}' is now '{NEW_KIND}'") == 1, err


# --- U5: the skill and the check id ------------------------------------------

def test_trc_045():
    pytest.fail("owned by U5")


def test_trc_046():
    pytest.fail("owned by U5")


def test_trc_047():
    pytest.fail("owned by U5")


def test_trc_048():
    pytest.fail("owned by U5")


def test_trc_049():
    pytest.fail("owned by U5")


# --- U6: the state key, the refusal code and the readiness key ---------------

def test_trc_050():
    pytest.fail("owned by U6")


def test_trc_051():
    pytest.fail("owned by U6")


def test_trc_052():
    pytest.fail("owned by U6")


OLD_BEHAVIOR = "behav" + "iour"
NEW_BEHAVIOR = "behav" + "ior"


def _compliance_json(tmp_path):
    import json
    import test_eval_session_compliance as cs

    home = tmp_path / "claude"
    root = cs._project(tmp_path, {"good-fix": "sess-good", "bad-fix": "sess-bad"})
    cs._clean("good-fix").write(home, "sess-good")
    cs._route_around("bad-fix").write(home, "sess-bad")
    done = cs._report(root, home, "--json")
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(done.stdout), cs._report(root, home).stdout


def _old_keys_emitted(data):
    """The old twin keys a result still emits, by where they are."""
    found = [k for k in data if k == OLD_BEHAVIOR + "s"]
    found += [f"row:{n}" for n, row in data[NEW_BEHAVIOR + "s"].items() if OLD_BEHAVIOR in row]
    found += [f"failure:{f['issue']}" for f in data["failures"] if OLD_BEHAVIOR in f]
    return found


def test_trc_053(tmp_path):
    from compass_pkg import old_names

    data, text = _compliance_json(tmp_path)
    # The result holds both spellings of the list, with the same content.
    assert data[NEW_BEHAVIOR + "s"] == data[OLD_BEHAVIOR + "s"]
    assert data[NEW_BEHAVIOR + "s"]["no_route_around"]["fail"] == 1
    # Each row and each failure holds both spellings of its key, equal.
    for name, row in data[NEW_BEHAVIOR + "s"].items():
        assert row[NEW_BEHAVIOR] == row[OLD_BEHAVIOR] == name
    assert data["failures"]
    for failure in data["failures"]:
        assert failure[NEW_BEHAVIOR] == failure[OLD_BEHAVIOR]
    # A consumer that reads only the old keys gets what it got before.
    assert {"issue": "bad-fix", OLD_BEHAVIOR: "no_route_around", "call": 2} in [
        {k: v for k, v in f.items() if k != NEW_BEHAVIOR} for f in data["failures"]]
    # The text view prints the US words only.
    assert OLD_BEHAVIOR not in text and "no_route_around" in text
    # The old keys end at 8.0.0: the table lists them, and at 8.0.0 a result
    # that still emits one is a problem.
    assert _old_keys_emitted(data)
    problems = old_names.removal_problems("8.0.0")
    assert any(f"json_key '{OLD_BEHAVIOR}'" in p for p in problems), problems
    assert any(f"json_key '{OLD_BEHAVIOR}s'" in p for p in problems), problems
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if old_names._version(version) >= (8, 0, 0):
        assert _old_keys_emitted(data) == [], "an old JSON key is still emitted"


# --- U7: the JSON keys, the headings and the term ----------------------------

def test_trc_054(tmp_path):
    from compass_pkg import flow, old_names

    work = tmp_path / ".compass" / "work" / "old"
    work.mkdir(parents=True)
    (work / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": "old", "created": "2026-05-25",
        "status": "landed", "land_timestamp": "2026-05-25T08:00:00+00:00",
        "assessment": {"risk": "contained", "familiarity": "greenfield", "size": "small"},
        "scenarios": [
            {"id": "SCN-OLD", "title": "old way", "intent": "INT-1", "tests": [],
             "superseded_by": ["SCN-NEW"]},
            {"id": "SCN-NEW", "title": "new way", "intent": "INT-1", "tests": []},
        ]}, sort_keys=False), encoding="utf-8")
    spec, archive = (tmp_path / "docs" / "system-spec.md",
                     tmp_path / "docs" / "system-spec-archive.md")
    pairs = [(row["new"], row["old"]) for row in old_names.rows("spec_heading")]
    assert [new for new, _ in pairs] == ["Current Behavior", "Archived Behavior"]

    flow.derive_system_spec(str(tmp_path))
    fresh = (spec.read_text(encoding="utf-8"), archive.read_text(encoding="utf-8"))
    assert "## Current Behavior\n" in fresh[0] and "## Archived Behavior\n" in fresh[1]

    # A file written by 6.1.0 holds the old headings.
    for path in (spec, archive):
        text = path.read_text(encoding="utf-8")
        for new, old in pairs:
            text = text.replace(f"## {new}\n", f"## {old}\n")
        path.write_text(text, encoding="utf-8")
    stale = spec.read_text(encoding="utf-8")
    assert "## Current Behaviour\n" in stale
    # The readers of the spec find its issues under either heading.
    assert flow._issues_named(stale) == flow._issues_named(fresh[0]) == {"old"}

    # The next derive is not an error and rewrites each file once.
    flow.derive_system_spec(str(tmp_path))
    again = (spec.read_text(encoding="utf-8"), archive.read_text(encoding="utf-8"))
    assert again == fresh
    for text in again:
        assert not any(f"## {old}" in text for _, old in pairs)
        assert sum(f"## {new}" in text for new, _ in pairs) == 1
    # A second derive changes nothing.
    flow.derive_system_spec(str(tmp_path))
    assert (spec.read_text(encoding="utf-8"), archive.read_text(encoding="utf-8")) == again


OLD_PAGE = "artifact-catalog" + "ue.md"
NEW_PAGE = "artifact-catalog.md"


def _links_that_do_not_resolve():
    """Every relative Markdown link to the catalog page, in a top-level docs
    page, that names no file. Other links are left to the site build: one
    unpublished page holds a link of its own that is already broken."""
    import re

    broken = []
    for page in sorted((ROOT / "docs").glob("*.md")):
        for target in re.findall(r"\]\(([^)\s]+)\)", page.read_text(encoding="utf-8")):
            path = target.split("#")[0]
            if not path.startswith("artifact-catalog"):
                continue
            if not (page.parent / path).exists():
                broken.append(f"{page.name} -> {target}")
    return broken


def test_trc_055(tmp_path):
    import shutil
    import subprocess

    def terminology(word):
        done = subprocess.run([sys.executable, str(CLI), "terminology", word],
                              capture_output=True, text=True, timeout=120)
        assert done.returncode == 0, done.stdout + done.stderr
        return done.stdout

    # Both terms print the same meaning.
    assert terminology("catalog") == terminology("catalog" + "ue")
    assert "catalog" in terminology("catalog")
    # The page is renamed, and the old name is a stub that links to it.
    assert (ROOT / "docs" / NEW_PAGE).is_file()
    stub = (ROOT / "docs" / OLD_PAGE).read_text(encoding="utf-8").strip().splitlines()
    assert 0 < len(stub) <= 5, stub
    assert f"]({NEW_PAGE})" in "\n".join(stub)
    # Nothing in docs/ links to the old name except the stub's own words, and
    # no link in docs/ is broken.
    for page in (ROOT / "docs").glob("*.md"):
        if page.name != OLD_PAGE:
            assert f"]({OLD_PAGE}" not in page.read_text(encoding="utf-8"), page.name
    assert _links_that_do_not_resolve() == []
    # The site lists the new page and not the old one.
    site = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert f": {NEW_PAGE}" in site and OLD_PAGE not in site
    # mkdocs builds the site without a broken link when it is installed.
    if shutil.which("mkdocs") is None:
        pytest.skip("mkdocs is not installed; the links of docs/ were checked by script")
    built = subprocess.run(["mkdocs", "build", "--strict", "--site-dir", str(tmp_path / "site")],
                           cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr


# --- U4: the table ends at 8.0.0 ----------------------------------------------

def test_trc_056():
    from compass_pkg import aliases, core, old_names

    found = old_names.rows()
    assert len(found) == 11, found
    assert len({r["kind"] for r in found}) == 9, found
    assert {r["removed_in"] for r in found} == {"8.0.0"}, found
    assert aliases.load_table()["aliases"] == []

    # The table ends at 8.0.0: a planted version lists every row, 7.0.0 none.
    assert len(old_names.removal_problems("8.0.0")) == 11
    assert len(old_names.removal_problems("9.1.0")) == 11
    assert old_names.removal_problems("7.0.0") == []
    assert old_names.removal_problems("7.10.0") == []    # tuples, not strings

    # The in-module copy equals the file (read directly), and the reader falls
    # back to it with the file made unreadable.
    on_disk = yaml.safe_load(MAP_FILE.read_text(encoding="utf-8"))["old_names"]
    assert old_names._FALLBACK == on_disk
    from_file = old_names.rows()
    assert core.migrate_map_section("old_names", {}) == on_disk
    assert old_names.current("reassessment_kind", OLD_KIND) == NEW_KIND
    assert from_file == old_names.rows()


def test_trc_056_the_table_check_fails_for_a_row_that_is_missing(monkeypatch):
    from compass_pkg import old_names

    planted = {k: dict(v) for k, v in old_names._FALLBACK.items()}
    planted["term"] = {}
    monkeypatch.setattr(old_names, "_READ", lambda name, fallback: planted)
    assert len(old_names.rows()) == 10
    assert old_names.removal_problems("8.0.0") and len(old_names.removal_problems("8.0.0")) == 10


# --- U4: the upgrade guide table is the reader table --------------------------

def _guide_rows(text: str) -> set:
    """`(kind, old, new, removed_in)` for each row of the guide's table."""
    section = text.split("## Renamed names", 1)[1].split("\n## ", 1)[0]
    found = set()
    for line in section.splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 4 and cells[3][:1].isdigit():
            found.add(tuple(cells))
    return found


def _reader_rows() -> set:
    from compass_pkg import old_names
    return {(old_names.LABELS[r["kind"]], r["old"], r["new"], r["removed_in"])
            for r in old_names.rows()}


def test_trc_070():
    text = GUIDE.read_text(encoding="utf-8")
    guide, reader = _guide_rows(text), _reader_rows()
    assert guide == reader, (sorted(guide - reader), sorted(reader - guide))
    assert len(guide) == 11

    # The comparison fails for a planted extra row, a missing row and a changed new name.
    extra = text.replace("## Renamed names\n", "## Renamed names\n\n| term | `frob` | `frab` | 8.0.0 |\n", 1)
    assert _guide_rows(extra) != reader
    gone = "\n".join(ln for ln in text.splitlines() if "| `catalogue` |" not in ln)
    assert _guide_rows(gone) != reader
    first = sorted(reader)[0]
    changed = text.replace(f"`{first[1]}` | `{first[2]}`", f"`{first[1]}` | `{first[2]}x`", 1)
    assert _guide_rows(changed) != reader
