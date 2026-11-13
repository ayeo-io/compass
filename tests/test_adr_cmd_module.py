"""`compass adr new` lives in its own module, so the receipt module can be deleted.

9.0.0 removes `compass issue receipt` (ADR-091). `compass adr new` shared its
module, `receipt.py`, so it moves to `adr_cmd.py` first, and the verb stays as
it was.

Issue: ayeo-io/compass-delivery#353.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

MOVED = {"cmd_adr_new", "_adr_readme_row", "_with_adr_row"}


def _names(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    names |= {t.id for n in tree.body if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name)}
    return names


def test_compass_adr_new_is_defined_in_its_own_module():
    from compass_pkg import adr_cmd
    assert callable(adr_cmd.cmd_adr_new)
    names = _names(ROOT / "cli" / "compass_pkg" / "adr_cmd.py")
    assert MOVED | {"_ADR_TEMPLATE", "_ADR_README_HEADER"} <= names


def test_no_other_module_defines_compass_adr_new():
    owners = sorted(p.name for p in (ROOT / "cli" / "compass_pkg").glob("*.py")
                    if p.name != "adr_cmd.py" and MOVED & _names(p))
    assert owners == [], owners


def test_the_adr_new_verb_runs_the_moved_function():
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("compass_cli_adr", str(ROOT / "cli" / "compass"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    cli = importlib.util.module_from_spec(spec)
    loader.exec_module(cli)
    args = cli.build_parser().parse_args(["adr", "new", "a-decision"])
    assert args.func.__module__ == "compass_pkg.adr_cmd"
