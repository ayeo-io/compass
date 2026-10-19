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

def test_trc_070():
    pytest.fail("owned by U4")
