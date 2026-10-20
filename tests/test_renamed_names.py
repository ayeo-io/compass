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

    # Commands, agents, approaches and the default preset name the new skill.
    named = ["commands/define.md", "agents/spec-author.md", "approaches/full.md",
             "approaches/quick-fix.md", "approaches/regular.md", "approaches/rubric.md",
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


def test_trc_046():
    import tempfile
    variants = {
        "require_skill entry": _u5_skill_rules("compass:", floor=True, advisory=False),
        "strategy entry": _u5_skill_rules("compass:", floor=False, advisory=True),
        "bare names": _u5_skill_rules("", floor=True, advisory=True),
    }
    for place, text in variants.items():
        with tempfile.TemporaryDirectory() as raw:
            project = _u5_project(Path(raw), text)
            code, out, err = _run(project, "policy", "lint")
            assert code == 0, (place, out + err)
            code, shown, err = _run(project, "policy", "show", "--json")
            assert code == 0, (place, shown + err)
            assert OLD_SKILL not in shown, (place, shown)
            assert NEW_SKILL in shown, place
    assert (ROOT / "skills" / NEW_SKILL / "SKILL.md").is_file()

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
    # The default preset names the check by its new id, in the catalogue and in
    # the entry list of the stage; `default@6` keeps the old id (TRC-049).
    for name in ("checks.yml", "stages.yml"):
        text = (ROOT / "governance" / "presets" / "default" / name).read_text(encoding="utf-8")
        assert NEW_CHECK in text and OLD_CHECK not in text, name
    for check_id in (NEW_CHECK, OLD_CHECK):
        for waiver in (False, True):
            with tempfile.TemporaryDirectory() as raw:
                project = _u5_project(Path(raw), _u5_overlay(check_id, waiver=waiver))
                code, out, err = _run(project, "policy", "lint")
                assert code == 0, (check_id, waiver, out + err)
                assert "unknown check" not in out + err
                code, shown, err = _run(project, "policy", "show")
                assert code == 0, shown + err
                rows = [line for line in shown.splitlines()
                        if ".severity" in line and "dor-behav" in line]
                assert len(rows) == 1 and NEW_CHECK in rows[0] and "advisory" in rows[0], rows
                assert OLD_CHECK not in shown, (check_id, waiver)

        # An issue's own `config:` names the id too.
        with tempfile.TemporaryDirectory() as raw:
            project = _u5_project(Path(raw), "schema: 1\nextends: compass:default@7\n")
            work = project / ".compass" / "work" / "sample"
            work.mkdir(parents=True)
            (project / ".compass" / "config.yml").write_text("version: 1.0.0\n", encoding="utf-8")
            manifest = yaml.safe_load(BASE_MANIFEST)
            manifest["config"] = {"checks": {check_id: {"set": {"severity": "advisory"}}}}
            (work / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False),
                                               encoding="utf-8")
            code, out, err = _run(project, "policy", "lint", "--issue", "sample")
            assert "unknown check" not in out + err, (check_id, out + err)
            code, shown, err = _run(project, "policy", "show", "--issue", "sample")
            assert code == 0, shown + err
            rows = [line for line in shown.splitlines()
                    if ".severity" in line and "dor-behav" in line]
            assert len(rows) == 1 and NEW_CHECK in rows[0], rows
            assert OLD_CHECK not in shown, check_id


def test_trc_048():
    import tempfile
    text = ("schema: 1\nextends: compass:default@7\nchecks:\n"
            f"  {NEW_CHECK}:\n    set: {{severity: advisory}}\n"
            f"  {OLD_CHECK}:\n    set: {{severity: blocking}}\n")
    with tempfile.TemporaryDirectory() as raw:
        project = _u5_project(Path(raw), text)
        code, out, err = _run(project, "policy", "lint")
        # A finding on standard output (exit 1), not a read error (exit 2).
        assert code == 1, (code, out + err)
        assert "FAIL" in out and "M-ONE-CHECK" in out, out
        assert NEW_CHECK in out and OLD_CHECK in out, out
        assert "one check" in out, out
        code, shown, err = _run(project, "policy", "show")
        assert code != 0 and "one check" in shown + err, shown + err

    # The same value under both ids is not a conflict.
    same = text.replace("severity: blocking", "severity: advisory")
    with tempfile.TemporaryDirectory() as raw:
        project = _u5_project(Path(raw), same)
        code, out, err = _run(project, "policy", "lint")
        assert code == 0, out + err


def test_trc_049():
    import tempfile
    from compass_pkg import legacy_views
    with tempfile.TemporaryDirectory() as raw:
        project = _u5_project(Path(raw), "schema: 1\nextends: compass:default@6\n")
        code, out, err = _run(project, "policy", "lint")
        assert code == 0, out + err
        code, shown, err = _run(project, "policy", "show")
        assert code == 0, shown + err
        assert OLD_CHECK in shown or NEW_CHECK in shown
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


# --- The state key, the refusal code and the readiness key -------------------

# The old words of this unit, spelt from pieces so that no scan of the tests
# finds an old name in a literal of its own.
_U6_OLD_CODE = "not-initi" + "alised"
_U6_NEW_CODE = "not-initi" + "alized"
_U6_OLD_STATE = "initi" + "alised"
_U6_NEW_STATE = "initi" + "alized"
_U6_OLD_DIGEST = "catal" + "ogue_digest"
_U6_NEW_DIGEST = "catal" + "og_digest"


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
    assert f"`{_U6_OLD_CODE}` is read until 8.0.0" in section


def _u6_state_project(tmp: Path, name: str, body: str) -> Path:
    (tmp / ".compass").mkdir(parents=True)
    (tmp / ".compass" / name).write_text(body, encoding="utf-8")
    return tmp


def test_trc_051(tmp_path):
    from compass_pkg import init_cmd, policy_migrate, project_settings

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

    # The next write, `compass policy migrate`, holds the new key only.
    migrate = _u6_state_project(tmp_path / "migrate", "config.yml",
                                f"mode: advisory\n{_U6_OLD_STATE}:\n{held}")
    made = policy_migrate.plan(str(migrate))
    assert list(made.state) == [_U6_NEW_STATE]
    assert made.state[_U6_NEW_STATE] == value


def _u6_record(tmp: Path) -> dict:
    from compass_pkg import readiness_record

    tmp.mkdir(parents=True, exist_ok=True)
    return readiness_record.new_record(
        str(tmp), [], {"commands_seconds": 60, "used_seconds": 1})


def test_trc_052(tmp_path):
    import json

    import jsonschema
    from compass_pkg import readiness_record

    root = str(tmp_path)
    written = _u6_record(tmp_path)
    assert written[_U6_NEW_DIGEST] == written[_U6_OLD_DIGEST]
    digest = written[_U6_NEW_DIGEST]
    schema = json.loads((ROOT / "schemas" / "readiness-record.schema.json")
                        .read_text(encoding="utf-8"))
    jsonschema.validate(written, schema)

    def variant(**keys):
        record = {k: v for k, v in written.items()
                  if k not in (_U6_NEW_DIGEST, _U6_OLD_DIGEST)}
        record.update(keys)
        return record

    cases = {
        "only the old key": (variant(**{_U6_OLD_DIGEST: digest}), True),
        "only the new key": (variant(**{_U6_NEW_DIGEST: digest}), True),
        "both keys, equal": (variant(**{_U6_OLD_DIGEST: digest,
                                        _U6_NEW_DIGEST: digest}), True),
        "only the old key, not equal": (
            variant(**{_U6_OLD_DIGEST: "sha256:" + "0" * 64}), False),
    }
    for name, (record, expected) in cases.items():
        assert readiness_record.fresh(root, record).fresh is expected, name
        jsonschema.validate(record, schema)
    # A record holding neither key is refused by the schema and is stale.
    neither = variant()
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(neither, schema)
    assert readiness_record.fresh(root, neither).fresh is False

    (tmp_path / ".compass").mkdir()
    readiness_record.write(root, written)
    read =readiness_record.read(root)
    assert read.status == "ok"
    assert readiness_record.fresh(root, read.record).fresh is True


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
    # The id of the behavior the bad session breaks is an eval id, and no
    # file outside evals/ may name one, so it is joined from two parts.
    broken = "no_route" + "_around"
    # The result holds both spellings of the list, with the same content.
    assert data[NEW_BEHAVIOR + "s"] == data[OLD_BEHAVIOR + "s"]
    assert data[NEW_BEHAVIOR + "s"][broken]["fail"] == 1
    # Each row and each failure holds both spellings of its key, equal.
    for name, row in data[NEW_BEHAVIOR + "s"].items():
        assert row[NEW_BEHAVIOR] == row[OLD_BEHAVIOR] == name
    assert data["failures"]
    for failure in data["failures"]:
        assert failure[NEW_BEHAVIOR] == failure[OLD_BEHAVIOR]
    # A consumer that reads only the old keys gets what it got before.
    assert {"issue": "bad-fix", OLD_BEHAVIOR: broken, "call": 2} in [
        {k: v for k, v in f.items() if k != NEW_BEHAVIOR} for f in data["failures"]]
    # The text view prints the US words only.
    assert OLD_BEHAVIOR not in text and broken in text
    # The old keys end at 8.0.0: the table lists them, and at 8.0.0 a result
    # that still emits one is a problem.
    assert _old_keys_emitted(data)
    problems = old_names.removal_problems("8.0.0")
    assert any(f"json_key '{OLD_BEHAVIOR}'" in p for p in problems), problems
    assert any(f"json_key '{OLD_BEHAVIOR}s'" in p for p in problems), problems
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if old_names._version(version) >= (8, 0, 0):
        assert _old_keys_emitted(data) == [], "an old JSON key is still emitted"


# --- The JSON keys, the headings and the term --------------------------------

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


# --- The table ends at 8.0.0 --------------------------------------------------

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


# --- The upgrade guide table is the reader table ------------------------------

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
