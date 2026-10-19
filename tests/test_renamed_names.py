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


def test_trc_053():
    pytest.fail("owned by U6")


# --- U7: the JSON keys, the headings and the term ----------------------------

def test_trc_054():
    pytest.fail("owned by U7")


def test_trc_055():
    pytest.fail("owned by U7")


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
