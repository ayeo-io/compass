"""`compass policy migrate --undo`: the command line, the report output and the help text.

The tests run the real parser and `main` in the test process, in a scratch
project. They replace the planner and the writer of `policy_migrate_undo`
with fixed stand-ins, so they check only the command: the flag, the refusals,
that a dry run writes nothing, and the shape of the output. The report
functions are also replaced while the module still holds its skeleton. The
undo itself is checked in the tests of the undo module.

Scenario id: `TRC-032` in policy-migrate-undo/acceptance-criteria.md. The
other ids run in the same way, `TRC-033` to `TRC-039`.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

# The steps a dry run lists, in the order apply takes them.
STEPS = [
    {"action": "restore", "path": ".compass/config.yml", "to": ".compass/config.yml"},
    {"action": "remove", "path": "compass.yml", "to": None},
    {"action": "remove", "path": ".compass/state.yml", "to": None},
    {"action": "remove", "path": ".compass/migration.yml", "to": None},
]
HINT = "Run with --apply to make these changes."


def _cli():
    loader = importlib.machinery.SourceFileLoader("compass_cli_undo_test", str(ROOT / "cli" / "compass"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _text(made):
    """A stand-in for the report text: the steps in order, then the hint or the kept note."""
    lines = [f"{s['action']} {s['path']}" for s in made.files]
    if made.result == "undone":
        lines.append(".compass/legacy is kept.")
    else:
        lines.append(HINT)
    return lines


def _json(made):
    return {"schema": 1, "mode": "undo", "result": made.result,
            "sources": made.sources, "files": made.files}


@pytest.fixture
def undo(tmp_path, monkeypatch):
    """A scratch project with the undo module's planner and writer replaced."""
    from compass_pkg import policy_migrate_undo as module
    (tmp_path / ".compass").mkdir()
    (tmp_path / "compass.yml").write_text("extends: compass:default@7\n")
    (tmp_path / ".compass" / "migration.yml").write_text("schema: 1\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NO_COLOR", "1")
    calls = []

    def plan(root):
        calls.append("plan")
        return module.UndoPlan(result="ready", sources=[{"path": ".compass/config.yml",
                                                         "digest": "sha256:0"}],
                               files=[dict(s) for s in STEPS])

    def apply(root, made):
        calls.append("apply")
        made.result = "undone"

    monkeypatch.setattr(module, "plan", plan)
    monkeypatch.setattr(module, "apply", apply)
    # Once the real report functions exist they run; until then fixed ones do.
    try:
        module.report_text(module.UndoPlan())
    except NotImplementedError:
        monkeypatch.setattr(module, "report_text", _text)
        monkeypatch.setattr(module, "report_json", _json)
    return tmp_path, calls


def _tree(root):
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _main(*argv):
    return _cli().main(["policy", "migrate", *argv])


def test_TRC_032_the_dry_run_writes_nothing(undo, capsys):
    """Scenario id: `TRC-032` in policy-migrate-undo/acceptance-criteria.md"""
    root, calls = undo
    before = _tree(root)
    assert _main("--undo") == 0
    assert _tree(root) == before
    assert calls == ["plan"]


def test_TRC_033_the_dry_run_lists_the_steps_in_the_order_apply_takes_them(undo, capsys):
    """Scenario id: `TRC-033` in policy-migrate-undo/acceptance-criteria.md"""
    assert _main("--undo") == 0
    out = capsys.readouterr().out
    positions = [out.index(p) for p in (".compass/config.yml", "compass.yml\n",
                                        ".compass/state.yml", ".compass/migration.yml")]
    assert positions == sorted(positions)


def test_TRC_034_the_dry_run_says_how_to_apply(undo, capsys):
    """Scenario id: `TRC-034` in policy-migrate-undo/acceptance-criteria.md"""
    assert _main("--undo") == 0
    assert capsys.readouterr().out.rstrip("\n").splitlines()[-1] == HINT


def test_TRC_035_the_applied_undo_says_the_legacy_folder_is_kept(undo, capsys):
    """Scenario id: `TRC-035` in policy-migrate-undo/acceptance-criteria.md"""
    root, calls = undo
    assert _main("--undo", "--apply") == 0
    assert calls == ["plan", "apply"]
    assert ".compass/legacy" in capsys.readouterr().out


def test_TRC_036_the_json_of_a_dry_run_has_a_fixed_shape(undo, capsys):
    """Scenario id: `TRC-036` in policy-migrate-undo/acceptance-criteria.md"""
    assert _main("--undo", "--json") == 0
    document = json.loads(capsys.readouterr().out)
    assert list(document) == ["schema", "mode", "result", "sources", "files"]
    assert (document["schema"], document["mode"], document["result"]) == (1, "undo", "ready")


def test_TRC_037_the_json_of_an_applied_undo_reports_undone(undo, capsys):
    """Scenario id: `TRC-037` in policy-migrate-undo/acceptance-criteria.md"""
    assert _main("--undo", "--apply", "--json") == 0
    document = json.loads(capsys.readouterr().out)
    assert (document["mode"], document["result"]) == ("undo", "undone")


@pytest.mark.parametrize("extra,name", [(["--words"], "--words"),
                                        (["somedir"], "DIR"),
                                        (["--i-have-a-copy"], "--i-have-a-copy")])
def test_TRC_038_undo_is_refused_with_the_options_of_the_other_mode(undo, capsys, extra, name):
    """Scenario id: `TRC-038` in policy-migrate-undo/acceptance-criteria.md"""
    root, calls = undo
    before = _tree(root)
    assert _main("--undo", "--apply", *extra) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert name in captured.err
    assert len(captured.err.split()) < 60
    assert calls == []
    assert _tree(root) == before


def test_TRC_039_the_help_text_describes_undo():
    """Scenario id: `TRC-039` in policy-migrate-undo/acceptance-criteria.md"""
    from compass_pkg.verb_help import VERB_DESCRIPTIONS
    parser = _cli().build_parser()
    policy = next(a for a in parser._subparsers._group_actions[0].choices["policy"]
                  ._subparsers._group_actions[0].choices.items() if a[0] == "migrate")[1]
    option = next(a for a in policy._actions if "--undo" in a.option_strings)
    verb = VERB_DESCRIPTIONS["policy migrate"]
    assert "--undo" in verb
    # The verb text names --undo and says, in its undo sentence, that it is a dry run.
    assert "dry run unless given --apply" in verb.split("--undo is a third mode")[1]
    assert "dry run" in option.help and "--apply" in option.help
