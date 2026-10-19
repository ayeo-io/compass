"""`compass policy migrate --undo`: the command line, the report output and the help text.

The tests run the real parser and `main` in the test process, in a scratch
project that a real `compass policy migrate --apply` migrated. The planner
and the writer of `policy_migrate_undo` are the real ones, wrapped to record
that they ran, so the output is the real report and the checks of the
command are the flag, the refusals, that a dry run writes nothing, and the
shape of the output. The undo itself is checked in the tests of the undo module.

Scenario id: `TRC-032` in policy-migrate-undo/acceptance-criteria.md. The
other ids run in the same way, `TRC-033` to `TRC-039`.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_policy_migrate import _full_project, _run  # noqa: E402

HINT = "Run with --apply to make these changes."


def _cli():
    loader = importlib.machinery.SourceFileLoader("compass_cli_undo_test", str(ROOT / "cli" / "compass"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture
def undo(tmp_path, monkeypatch):
    """A scratch project after a real migration, with the real planner and writer recorded."""
    from compass_pkg import policy_migrate_undo as module
    root = _full_project(tmp_path)
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 0, out + err
    monkeypatch.chdir(root)
    monkeypatch.setenv("NO_COLOR", "1")
    calls = []
    real_plan, real_apply = module.plan, module.apply

    def plan(project):
        calls.append("plan")
        return real_plan(project)

    def apply(project, made):
        calls.append("apply")
        return real_apply(project, made)

    monkeypatch.setattr(module, "plan", plan)
    monkeypatch.setattr(module, "apply", apply)
    return root, calls


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
    # Each file the undo changes is on its own line, with its action.
    assert "restore .compass/config.yml" in " ".join(out.split())
    assert "remove  compass.yml\n" in out


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
    assert [(f["action"], f["path"]) for f in document["files"]][:4] == [
        ("restore", ".compass/config.yml"), ("remove", "compass.yml"),
        ("remove", ".compass/state.yml"), ("remove", ".compass/migration.yml")]


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
