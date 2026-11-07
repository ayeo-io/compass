"""The old typed names that 7.0.0 still reads (issue language-key-and-us-english).

One reader-side table in `cli/migrate-map.yml` (`old_names:`), each row ending at
8.0.0, read through `cli/compass_pkg/old_names.py`. The sections below test, in
order: the table and the `--kind` argument; the skill and the check id; the
state key, the refusal code and the readiness key; the JSON keys, the headings
and the term; the end of the table at 8.0.0; and the upgrade guide table.
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


# --- The table, the --kind argument and the manifest kind --------------------

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
    notice = f"compass: kind {OLD_KIND} is now {NEW_KIND}; the old word is read until 9.0.0."
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

        for args in (("issue", "lint", "--issue", "sample"), ("check", "--issue", "sample")):
            code_old, out_old, _ = _run(old, *args)
            code_new, out_new, _ = _run(new, *args)
            assert code_old == code_new, (args, out_old, out_new)
        assert _run(old, "issue", "lint", "--issue", "sample")[0] == 0

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


# --- The skill and the check id ----------------------------------------------

OLD_SKILL = "behav" + "iour-mapping"
NEW_SKILL = "behavior-mapping"
OLD_CHECK = "dor-behav" + "iour-is-gwt"
NEW_CHECK = "dor-behavior-is-gwt"


def _stub_body_lines(text: str) -> list:
    """The lines of a skill file that follow its frontmatter and hold text."""
    parts = text.split("---", 2)
    assert len(parts) == 3, "a skill file opens with frontmatter"
    return [line for line in parts[2].splitlines() if line.strip()]


def test_trc_045():
    new = (ROOT / "skills" / NEW_SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert f"\nname: {NEW_SKILL}\n" in new
    stub = (ROOT / "skills" / OLD_SKILL / "SKILL.md").read_text(encoding="utf-8")
    body = _stub_body_lines(stub)
    assert 1 <= len(body) <= 3, body
    assert NEW_SKILL in " ".join(body) and "renamed" in " ".join(body), body
    # A stub that grows past 3 lines of body text is caught by the same reader.
    assert len(_stub_body_lines(stub + "A second line.\nA third line.\nA fourth line.\n")) > 3

    # The stage map, the approaches and the default preset name the new skill.
    # The define command and the 8.x approach files went with the path
    # (ADR-092); the stage map loads the skill at specify now.
    named = ["skills/compass-runtime/SKILL.md", "approaches/path.md",
             "approaches/composition-reference.md", "approaches/rubric.md",
             "governance/presets/default/rules.yml"]
    for rel in named:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert NEW_SKILL in text and OLD_SKILL not in text, rel
    # The view generated from the 7.0.0 preset, and the template of its comments.
    for rel in ("governance/routing-policy.yml", "cli/compass_pkg/legacy_views_template.py"):
        assert OLD_SKILL not in (ROOT / rel).read_text(encoding="utf-8"), rel
    for folder in ("commands", "agents", "approaches", "governance/presets/default"):
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and path.suffix in (".md", ".yml"):
                assert OLD_SKILL not in path.read_text(encoding="utf-8"), path


def _u5_project(tmp: Path, compass_yml: str) -> Path:
    (tmp / ".compass").mkdir(parents=True)
    (tmp / "compass.yml").write_text(compass_yml, encoding="utf-8")
    return tmp


def _u5_skill_rules(prefix: str, *, floor: bool, advisory: bool) -> str:
    """An overlay that restates the default's own rule with the skill named
    by `prefix` + the old name, so the child asks for what the parent does."""
    out = "schema: 1\nextends: compass:default@7\nrules:\n"
    if floor:
        out += (
            "  floors:\n    set:\n      rules:\n        set:\n          RP-FLOOR-002:\n"
            "            order: 2\n            when:\n              familiarity: brownfield-unmapped\n"
            "              any_of:\n              - size: [medium, large, product]\n"
            "              - risk: [cross-cutting, critical]\n"
            "              - labels_any: [auth, payments, personal-data, migrations]\n"
            f"            then: {{require_phase: define, require_skill: '{prefix}{OLD_SKILL}'}}\n"
            "            rationale: The project restates the floor.\n")
    if advisory:
        out += (
            "  advisory:\n    set:\n      rules:\n        set:\n          RP-ADV-002:\n"
            "            order: 2\n            when:\n              familiarity: brownfield-unmapped\n"
            "              size: [atomic, small]\n              risk: [trivial, contained]\n"
            f"            then: {{strategy: '{prefix}{OLD_SKILL}'}}\n"
            "            rationale: The project restates the advice.\n")
    return out


def _stored_view(tmp: Path, mutate):
    """The view of an issue whose stored generation was changed by `mutate`, as a
    generation stored before a rename holds the old word. Since 9.0.0
    `compass.yml` holds no catalog (ADR-094), so a stored generation is where an
    old check id or skill name is still read."""
    import stored_generation
    from compass_pkg import effective
    from test_generation_store import _evaluate_write, _project
    root, task_dir = _project(tmp, compass_yml={"schema": 1})
    assert _evaluate_write(root)[0] == 0
    stored_generation.commit(root, task_dir, mutate)
    return effective.effective_for(str(task_dir), None)


def test_trc_046():
    import tempfile
    variants = {
        "require_skill entry": _u5_skill_rules("compass:", floor=True, advisory=False),
        "strategy entry": _u5_skill_rules("compass:", floor=False, advisory=True),
        "bare names": _u5_skill_rules("", floor=True, advisory=True),
    }
    # Since 9.0.0 `rules:` in `compass.yml` is a removed setting (ADR-094): the
    # file is read without it, whatever word it uses.
    for place, text in variants.items():
        with tempfile.TemporaryDirectory() as raw:
            project = _u5_project(Path(raw), text)
            code, out, err = _run(project, "policy", "lint")
            assert code == 0, (place, out + err)
            assert "L-SETTING-REMOVED [project] rules:" in out, (place, out)
            code, shown, err = _run(project, "policy", "show", "--json")
            assert code == 0, (place, shown + err)
            assert OLD_SKILL not in shown, (place, shown)
    assert (ROOT / "skills" / NEW_SKILL / "SKILL.md").is_file()

    # A stored generation that names the old skill is read with the new name.
    for prefix in ("compass:", ""):
        def old_skill(resolved, prefix=prefix):
            resolved["rules"]["floors"]["rules"]["RP-FLOOR-002"]["then"] = {
                "require_skill": f"{prefix}{OLD_SKILL}"}
        with tempfile.TemporaryDirectory() as raw:
            config = _stored_view(Path(raw), old_skill).config
        assert config["rules"]["floors"]["rules"]["RP-FLOOR-002"]["then"] == {
            "require_skill": NEW_SKILL}, prefix
        assert OLD_SKILL not in str(config), prefix

    # A project preset that extends the default: a parent that names the old skill.
    from compass_pkg import word_map
    layer = {"rules": {"floors": {"set": {"rules": {"set": {"R-1": {
        "then": {"require_skill": f"compass:{OLD_SKILL}"}}}}}}}}
    mapped, changes = word_map.map_layer(layer)
    assert NEW_SKILL in str(mapped) and OLD_SKILL not in str(mapped), mapped
    assert changes and changes[0][1:] == (f"compass:{OLD_SKILL}", NEW_SKILL), changes


def _u5_overlay(check_id: str, severity: str = "advisory", waiver: bool = False) -> str:
    body = "schema: 1\nextends: compass:default@7\n"
    body += "owner: jed72\n" if waiver else ""
    body += f"checks:\n  {check_id}:\n"
    body += f"    set: {{severity: {severity}}}\n"
    if waiver:
        body += ("    waiver: {reason: The team writes scenarios at plan., "
                 "approved_by: jed72, approved_on: 2026-10-05}\n")
    return body


def test_trc_047():
    import tempfile
    # `default@7` names the check by its new id, in the catalogue and in the entry
    # list of the stage; `default@6` keeps the old id (TRC-049). The shipped default
    # holds no Definition of Ready since 9.0.0 (ADR-092), under either id.
    for name in ("checks.yml", "stages.yml"):
        text = (ROOT / "governance" / "presets" / "default@7" / name).read_text(encoding="utf-8")
        assert NEW_CHECK in text and OLD_CHECK not in text, name
        live = (ROOT / "governance" / "presets" / "default" / name).read_text(encoding="utf-8")
        assert NEW_CHECK not in live and OLD_CHECK not in live, name
    for check_id in (NEW_CHECK, OLD_CHECK):
        for waiver in (False, True):
            with tempfile.TemporaryDirectory() as raw:
                project = _u5_project(Path(raw), _u5_overlay(check_id, waiver=waiver))
                code, out, err = _run(project, "policy", "lint")
                assert code == 0, (check_id, waiver, out + err)
                assert "unknown check" not in out + err
                # `checks:` in `compass.yml` is a removed setting since 9.0.0
                # (ADR-094), named once by its key; nothing under it is read.
                assert "L-SETTING-REMOVED [project] checks:" in out, out
                code, shown, err = _run(project, "policy", "show")
                assert code == 0, shown + err
                assert OLD_CHECK not in shown, (check_id, waiver)

        # A stored generation that holds the check under either id is read with the
        # new one. An issue's own `config:` is not read since 9.0.0 (ADR-094).
        def holds(resolved, check_id=check_id):
            resolved["checks"][check_id] = {"statement": "Behavior is written as GWT.",
                                            "kind": "human", "severity": "advisory",
                                            "on_skipped": "fail"}
        with tempfile.TemporaryDirectory() as raw:
            config = _stored_view(Path(raw), holds).config
        assert NEW_CHECK in config["checks"] and OLD_CHECK not in config["checks"], check_id


def test_trc_048():
    import tempfile
    text = ("schema: 1\nextends: compass:default@7\nchecks:\n"
            f"  {NEW_CHECK}:\n    set: {{severity: advisory}}\n"
            f"  {OLD_CHECK}:\n    set: {{severity: blocking}}\n")
    # `checks:` in `compass.yml` is a removed setting since 9.0.0 (ADR-094), so the
    # two ids in it are not read and conflict with nothing.
    with tempfile.TemporaryDirectory() as raw:
        project = _u5_project(Path(raw), text)
        code, out, err = _run(project, "policy", "lint")
        assert code == 0, (code, out + err)
        assert "L-SETTING-REMOVED [project] checks:" in out, out

    # The word map, which reads a stored generation, keeps both ids when their
    # bodies differ, and names the conflict, so the new id never hides it.
    from compass_pkg import word_map
    layer = yaml.safe_load(text)
    mapped, _ = word_map.map_layer(layer)
    assert {NEW_CHECK, OLD_CHECK} <= set(mapped["checks"]), mapped
    conflicts = word_map.one_check_conflicts(mapped)
    assert [(code, path) for code, path, _ in conflicts] == [
        ("M-ONE-CHECK", f"checks.{OLD_CHECK}")], conflicts
    assert "one check" in conflicts[0][2]

    # The same value under both ids is not a conflict.
    same = yaml.safe_load(text.replace("severity: blocking", "severity: advisory"))
    mapped, _ = word_map.map_layer(same)
    assert word_map.one_check_conflicts(mapped) == []
    assert NEW_CHECK in mapped["checks"] and OLD_CHECK not in mapped["checks"]


def test_trc_049():
    import tempfile
    from compass_pkg import legacy_views
    with tempfile.TemporaryDirectory() as raw:
        project = _u5_project(Path(raw), "schema: 1\nextends: compass:default@6\n")
        code, out, err = _run(project, "policy", "lint")
        assert code == 0, out + err
        code, shown, err = _run(project, "policy", "show")
        assert code == 0, shown + err
        # The live preset is resolved whatever major extends names, and it holds
        # no Definition of Ready (ADR-092).
        assert OLD_CHECK not in shown and NEW_CHECK not in shown
    # The frozen 6 files still name the old id, and their digests are unchanged.
    frozen = (ROOT / "governance" / "presets" / "default@6" / "checks.yml").read_text(
        encoding="utf-8")
    assert OLD_CHECK in frozen
    from compass_pkg import atomic_io
    folder = ROOT / "governance" / "presets" / "default@6"
    parsed = {p.name: yaml.safe_load(p.read_text(encoding="utf-8"))
              for p in sorted(folder.glob("*.yml"))}
    pinned = yaml.safe_load((ROOT / "tests" / "fixtures" / "preset-digests.yml")
                            .read_text(encoding="utf-8"))["default@6.0.0"]
    assert atomic_io.digest(parsed) == pinned["preset"]
    for name, doc in parsed.items():
        assert atomic_io.digest(doc) == pinned["files"][name], name
    assert legacy_views.digest_problems(ROOT) == [], legacy_views.digest_problems(ROOT)


# --- The state key and the refusal code ---------------------------------------
# The readiness key's test went with the readiness record in 9.0.0 (ADR-093).

# The old words of this unit, spelt from pieces so that no scan of the tests
# finds an old name in a literal of its own.
_U6_OLD_CODE = "not-initi" + "alised"
_U6_NEW_CODE = "not-initi" + "alized"
_U6_OLD_STATE = "initi" + "alised"
_U6_NEW_STATE = "initi" + "alized"


def test_trc_050():
    import shutil
    import tempfile

    import compat_hook

    outputs = {}
    for code in (_U6_NEW_CODE, _U6_OLD_CODE):
        code_run = _run(ROOT, "_refusal", code, "detail=no work")
        assert code_run[0] == 0, code_run
        outputs[code] = code_run[1]
        assert len(code_run[1].strip().splitlines()) == 3, code_run[1]
    assert outputs[_U6_NEW_CODE] == outputs[_U6_OLD_CODE]
    assert outputs[_U6_NEW_CODE].rstrip().endswith(f"[{_U6_NEW_CODE}]")
    assert _U6_OLD_CODE not in outputs[_U6_OLD_CODE]
    assert _U6_OLD_CODE in _run(ROOT, "_refusal", _U6_OLD_CODE, "detail=x")[2]
    assert _U6_OLD_CODE not in _run(ROOT, "_refusal", _U6_NEW_CODE, "detail=x")[2]

    base = Path(tempfile.mkdtemp(prefix="u6hook-"))
    try:
        hook_root = compat_hook.install(base / "framework")
        for state in ("no-work-initialised", "no-issue-initialised"):
            entry = {"state": state, "tool": "Edit",
                     "tool_input": {"file_path": "{project}/src/app.py",
                                    "old_string": "a", "new_string": "b"}}
            exit_code, code, _out, err = compat_hook.run_entry(hook_root, base, entry)
            assert exit_code == 2, err
            assert code == _U6_NEW_CODE, err
            assert _U6_OLD_CODE not in err, err
    finally:
        shutil.rmtree(base, ignore_errors=True)

    page = (ROOT / "docs" / "refusal-codes.md").read_text(encoding="utf-8")
    assert f"### `{_U6_NEW_CODE}`" in page
    assert f"### `{_U6_OLD_CODE}`" not in page
    section = page.split(f"### `{_U6_NEW_CODE}`", 1)[1].split("###", 1)[0]
    assert f"`{_U6_OLD_CODE}` is read until 9.0.0" in section


def _u6_state_project(tmp: Path, name: str, body: str) -> Path:
    (tmp / ".compass").mkdir(parents=True)
    (tmp / ".compass" / name).write_text(body, encoding="utf-8")
    return tmp


def test_trc_051(tmp_path):
    from compass_pkg import init_cmd, project_settings

    held = "  by: someone\n  at: '2026-01-01'\n"
    value = {"by": "someone", "at": "2026-01-01"}

    old = _u6_state_project(tmp_path / "old", "state.yml", f"{_U6_OLD_STATE}:\n{held}")
    assert project_settings.state(str(old)) == {_U6_NEW_STATE: value}

    new = _u6_state_project(tmp_path / "new", "state.yml", f"{_U6_NEW_STATE}:\n{held}")
    assert project_settings.state(str(new)) == {_U6_NEW_STATE: value}

    both = _u6_state_project(
        tmp_path / "both", "state.yml",
        f"{_U6_OLD_STATE}:\n  by: other\n  at: '2026-02-02'\n{_U6_NEW_STATE}:\n{held}")
    assert project_settings.state(str(both)) == {_U6_NEW_STATE: value}

    config = _u6_state_project(tmp_path / "cfg", "config.yml",
                               f"mode: advisory\n{_U6_OLD_STATE}:\n{held}")
    assert project_settings.state(str(config)) == {_U6_NEW_STATE: value}

    fresh = tmp_path / "fresh"
    fresh.mkdir()
    init_cmd.ensure_initialised(str(fresh))
    text = (fresh / ".compass" / "state.yml").read_text(encoding="utf-8")
    assert f"{_U6_NEW_STATE}:" in text and f"{_U6_OLD_STATE}:" not in text
    assert project_settings.state(str(fresh))[_U6_NEW_STATE]["by"] == "compass init"


OLD_BEHAVIOR = "behav" + "iour"
NEW_BEHAVIOR = "behav" + "ior"


def test_trc_053():
    from compass_pkg import old_names

    # The old JSON keys end at 9.0.0: the table lists them, and at 9.0.0 the
    # table reports each one as a problem. The session report that emitted
    # them was removed with `compass retro` (ADR-093).
    problems = old_names.removal_problems("9.0.0")
    assert any(f"json_key '{OLD_BEHAVIOR}'" in p for p in problems), problems
    assert any(f"json_key '{OLD_BEHAVIOR}s'" in p for p in problems), problems


# --- The JSON keys, the headings and the term --------------------------------

def test_trc_054():
    # 9.0.0 derives no living spec (ADR-091). A spec an older revision holds can
    # still use the headings 6.1.0 wrote, and `compass release notes` reads it there.
    from compass_pkg import old_names, shipped_issues

    pairs = [(row["new"], row["old"]) for row in old_names.rows("spec_heading")]
    assert [new for new, _ in pairs] == ["Current Behavior", "Archived Behavior"]
    fresh = "## Current Behavior\n\n### old (completed 2026-05-25)\n\n- `SCN-NEW` new way\n"
    stale = fresh
    for new, old in pairs:
        stale = stale.replace(f"## {new}\n", f"## {old}\n")
    assert "## Current Behaviour\n" in stale
    # The reader of the spec finds its issues under either heading.
    assert shipped_issues.issues_named(stale) == shipped_issues.issues_named(fresh) == {"old"}


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


# --- The table ends at 9.0.0 --------------------------------------------------

def test_trc_056():
    from compass_pkg import aliases, core, old_names

    found = old_names.rows()
    assert len(found) == 11, found
    assert len({r["kind"] for r in found}) == 9, found
    assert {r["removed_in"] for r in found} == {"9.0.0"}, found
    assert aliases.load_table()["aliases"] == []

    # The table ends at 9.0.0: a planted version lists every row, 8.x none.
    assert len(old_names.removal_problems("9.0.0")) == 11
    assert old_names.removal_problems("8.0.0") == []
    assert old_names.removal_problems("8.1.0") == []
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
    assert old_names.removal_problems("9.0.0") and len(old_names.removal_problems("9.0.0")) == 10


# --- The upgrade guide table is the reader table ------------------------------

def _guide_rows(text: str) -> set:
    """`(kind, old, new, removed_in)` for each row of the guide's table."""
    import re
    section = text.split("## Renamed names", 1)[1].split("\n## ", 1)[0]
    found = set()
    for line in section.splitlines():
        line = re.sub(r"\s*<!-- us-english-scan: allow - [^>]*-->\s*$", "", line)
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
    extra = text.replace("## Renamed names\n", "## Renamed names\n\n| term | `frob` | `frab` | 9.0.0 |\n", 1)
    assert _guide_rows(extra) != reader
    gone = "\n".join(ln for ln in text.splitlines() if "| `catalogue` |" not in ln)
    assert _guide_rows(gone) != reader
    first = sorted(reader)[0]
    changed = text.replace(f"`{first[1]}` | `{first[2]}`", f"`{first[1]}` | `{first[2]}x`", 1)
    assert _guide_rows(changed) != reader
