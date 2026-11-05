"""`compass ci` lives in its own module, so `compass analyze` can be deleted.

9.0.0 removes `compass analyze` (ADR-091). `compass ci` shared its module,
`analyze.py`, so it moves to `ci_cmd.py` first, and the verb stays as it was.

Issue: ayeo-io/compass-delivery#353.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))


def _functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}


def test_compass_ci_is_defined_in_its_own_module():
    from compass_pkg import ci_cmd
    assert callable(ci_cmd.cmd_ci)
    names = _functions(ROOT / "cli" / "compass_pkg" / "ci_cmd.py")
    assert {"cmd_ci", "_landed_before", "_gate_checks_wait"} <= names


def test_no_other_module_defines_compass_ci():
    owners = sorted(p.name for p in (ROOT / "cli" / "compass_pkg").glob("*.py")
                    if p.name != "ci_cmd.py" and "cmd_ci" in _functions(p))
    assert owners == [], owners


def test_the_ci_verb_runs_the_moved_function():
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("compass_cli_ci", str(ROOT / "cli" / "compass"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    cli = importlib.util.module_from_spec(spec)
    loader.exec_module(cli)
    args = cli.build_parser().parse_args(["ci"])
    assert args.func.__module__ == "compass_pkg.ci_cmd"
