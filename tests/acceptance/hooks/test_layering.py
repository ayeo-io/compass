"""The four layers hold their shape, for the pilot of the four-layer acceptance
test model (ayeo-io/compass-delivery#306, in the private delivery record).

| Scenario | What it checks |
|---|---|
| `TRC-P1` | the DSL makes no check, and each specification is only DSL calls, one per Given, When or Then line |
| `TRC-P3` | a change to where the hook keeps its parts is absorbed by a driver alone |
| `TRC-P4` | one scenario runs twice in a row, and four run at once, with the same result |
| `TRC-P5` | the note gives the counts it is meant to give |

The scenario `TRC-P2`, the same specifications through both hook clients,
is `test_hook_refusals.py` itself: its fixture runs each scenario once per client.
"""
from __future__ import annotations

import ast
import re
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tests.acceptance.hooks import dsl as dsl_module
from tests.acceptance.hooks import test_hook_refusals as specs
from tests.acceptance.hooks.drivers import base
from tests.acceptance.hooks.drivers.claude_code import ClaudeCodeDriver
from tests.acceptance.hooks.dsl import Dsl

HERE = Path(__file__).resolve().parent
STEP = re.compile(r"^\s*(Given|When|Then|And)\b", re.M)


def _spec_functions():
    tree = ast.parse((HERE / "test_hook_refusals.py").read_text(encoding="utf-8"))
    return [node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]


def test_trc_p1_the_dsl_makes_no_check():
    tree = ast.parse((HERE / "dsl.py").read_text(encoding="utf-8"))
    # A check in any form: an assert, a raise, or a call such as expect(),
    # should() or pytest.fail().
    found = [f"line {node.lineno}: {type(node).__name__}" for node in ast.walk(tree)
             if isinstance(node, (ast.Assert, ast.Raise))]
    found += [f"line {node.lineno}: {node.id}" for node in ast.walk(tree)
              if isinstance(node, ast.Name) and node.id in ("expect", "should")]
    found += [f"line {node.lineno}: {node.attr}" for node in ast.walk(tree)
              if isinstance(node, ast.Attribute) and node.attr in ("fail", "expect", "should")]
    assert not found, f"the DSL checks something itself: {found}"


@pytest.mark.parametrize("function", _spec_functions(), ids=lambda f: f.name)
def test_trc_p1_each_specification_is_one_dsl_call_per_step(function):
    body = function.body
    docstring = ast.get_docstring(function)
    assert docstring, f"{function.name} has no scenario in its docstring"
    calls = body[1:]
    for statement in calls:
        assert isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call), (
            f"{function.name} line {statement.lineno} is not a DSL call")
        root = statement.value.func
        while isinstance(root, ast.Attribute):
            root = root.value
        assert isinstance(root, ast.Name) and root.id == "dsl", (
            f"{function.name} line {statement.lineno} calls something other than the DSL")
    steps = len(STEP.findall(docstring))
    assert steps == len(calls), (
        f"{function.name}: {steps} Given/When/Then lines, {len(calls)} DSL calls")


def test_trc_p1_every_refusal_check_names_a_code():
    # The Codex adapter turns a hook that crashes into a refusal with no code,
    # so a check that names no code passes on a crash.
    bare = [f"{function.name} line {node.lineno}" for function in _spec_functions()
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "confirmRefused"
            and not any(k.arg == "code" for k in node.keywords)]
    assert not bare, f"refusal checks that name no code: {bare}"


class _PartsElsewhere(ClaudeCodeDriver):
    """A driver for a hook that keeps its parts in hooks/parts/, not hooks/lib/.
    The only change a move like that needs in the acceptance suite."""

    def hasCompleteInstall(self):
        if self.install.exists():
            return
        super().hasCompleteInstall()
        (self.install / "hooks" / "lib").rename(self.install / "hooks" / "parts")
        script = self.install / "hooks" / "pre-tool.sh"
        text = script.read_text(encoding="utf-8")
        old = 'PRE_TOOL_PARTS="${PRE_TOOL_SELF%/*}/lib"'
        assert text.count(old) == 1, "the hook no longer sets PRE_TOOL_PARTS this way"
        script.write_text(text.replace(old, 'PRE_TOOL_PARTS="${PRE_TOOL_SELF%/*}/parts"'),
                          encoding="utf-8")

    def _part(self, part):
        return self.install / base.INSTALL_PARTS[part].replace("hooks/lib/", "hooks/parts/")


@pytest.fixture
def workspace():
    folder = Path(tempfile.mkdtemp(prefix="compass-acc-"))
    yield folder
    for path in folder.rglob("*"):
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() else 0o644)
    shutil.rmtree(folder, ignore_errors=True)


@pytest.mark.parametrize("scenario, args", [
    (specs.test_hfm_1_an_edit_whose_checks_all_pass_is_allowed, ("src/app.py",)),
    (specs.test_trc_a3_a_missing_part_refuses_every_call, ("pre-tool-guards.sh",)),
    (specs.test_trc_a3_an_unreadable_part_refuses_every_call, ("pre-tool-checks.sh",)),
], ids=lambda value: getattr(value, "__name__", None))
def test_trc_p3_a_layout_change_touches_only_a_driver(monkeypatch, workspace, scenario, args):
    monkeypatch.setattr(dsl_module, "driver_for", lambda folder, client: _PartsElsewhere(folder))
    scenario(Dsl(workspace, "claude-code"), *args)


def _run_once(scenario, args):
    folder = Path(tempfile.mkdtemp(prefix="compass-acc-"))
    try:
        scenario(Dsl(folder, "claude-code"), *args)
        return "passed"
    finally:
        for path in folder.rglob("*"):
            if not path.is_symlink():
                path.chmod(0o755 if path.is_dir() else 0o644)
        shutil.rmtree(folder, ignore_errors=True)


def test_trc_p4_one_scenario_twice_and_four_at_once():
    scenario = specs.test_hfm_1_a_check_that_cannot_run_refuses_and_names_itself
    assert _run_once(scenario, ("red record", 1)) == "passed"
    assert _run_once(scenario, ("red record", 1)) == "passed"
    jobs = [(scenario, (check, 3)) for check in specs.CHECKS]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda job: _run_once(*job), jobs))
    assert results == ["passed"] * 4


def test_trc_p5_the_note_gives_the_counts():
    note = (HERE / "README.md").read_text(encoding="utf-8")
    assert "## What a change to the hook's layout touches" in note
    assert re.search(r"\| Before \(#699\) \| \d+ \|", note), "no 'before' count"
    assert re.search(r"\| After \| \d+ \|", note), "no 'after' count"
    assert "## Recommendation for ayeo-io/compass-delivery#307" in note
