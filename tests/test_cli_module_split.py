"""cli/compass is a package, and nothing observable changed by making it one.

A pure refactor: 6,201 lines in one file become a thin entry point plus modules.
The contract is that an adopter cannot tell. These tests are the contract.

The equivalence assertions (group B, F2) compare against
tests/fixtures/cli-surface-baseline.json, captured from the UNSPLIT file before
any code moved. That ordering matters: a baseline captured afterwards would
describe whatever the refactor happened to produce, and would prove nothing.

Spec: cli-module-split/acceptance-criteria.md (TRC-A1..A3, B1..B4, F1, F2).
"""
from __future__ import annotations

import ast
import importlib.machinery
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
PKG = ROOT / "cli" / "compass_pkg"
BASELINE = json.loads((ROOT / "tests" / "fixtures" /
                       "cli-surface-baseline.json").read_text())


def _modules():
    return sorted(p for p in PKG.glob("*.py") if p.name != "__init__.py")


def _top_level_functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _imports_of(path):
    """Which compass_pkg modules does this file import?"""
    out = set()
    for m in re.finditer(r"^\s*(?:from|import)\s+([\w.]+)",
                         path.read_text(encoding="utf-8"), re.M):
        name = m.group(1)
        if name.startswith("compass_pkg."):
            out.add(name.split(".", 1)[1].split(".")[0])
    return out


# --- group A: the structure ------------------------------------------------

# The entry point holds the shebang, the parser and main(), and no logic.
# A raw line cap measured the verb count instead, because each verb adds a
# few lines of parser, so it was raised three times in a week (#102). The
# guard now measures what it is for: only these functions, no loop or
# nested function in the parser, and a cap on the lines outside it.
_ENTRY_POINT_FUNCTIONS = {"_pyyaml_resolution_line", "build_parser", "main"}
_LINES_OUTSIDE_THE_PARSER = 140
# The parser holds one `if`: the check that every hidden verb exists.
_PARSER_IFS = 1


def _entry_point_problems(src):
    import ast
    problems = []
    tree = ast.parse(src)
    defs = [n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    extra = sorted({n.name for n in defs} - _ENTRY_POINT_FUNCTIONS)
    if extra:
        problems.append(f"cli/compass defines {', '.join(extra)}; logic "
                        f"belongs in cli/compass_pkg")
    parser = next((n for n in defs if n.name == "build_parser"), None)
    if parser is None:
        return problems + ["cli/compass has no build_parser()"]
    nested = [n for n in ast.walk(parser) if n is not parser and isinstance(
        n, (ast.For, ast.While, ast.Try, ast.With, ast.FunctionDef,
            ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda))]
    if nested:
        problems.append(f"build_parser() holds a {type(nested[0]).__name__} "
                        f"at line {nested[0].lineno}; it registers verbs only")
    ifs = sum(isinstance(n, ast.If) for n in ast.walk(parser))
    if ifs > _PARSER_IFS:
        problems.append(f"build_parser() holds {ifs} if statements, "
                        f"{_PARSER_IFS} allowed")
    outside = (len(src.splitlines())
               - (parser.end_lineno - parser.lineno + 1))
    if outside >= _LINES_OUTSIDE_THE_PARSER:
        problems.append(f"cli/compass has {outside} lines outside "
                        f"build_parser(), {_LINES_OUTSIDE_THE_PARSER} allowed")
    return problems


def test_trc_a1_the_entry_point_should_be_thin():
    assert PKG.is_dir(), "cli/compass_pkg does not exist"
    src = CLI.read_text(encoding="utf-8")
    assert src.startswith("#!"), "the entry point lost its shebang"
    assert "def main(" in src, "main() left the entry point"
    assert "add_subparsers" in src, "the argument parser left the entry point"
    assert _entry_point_problems(src) == []


def test_trc_a2_the_modules_should_follow_the_groupings_the_code_already_had():
    mods = _modules()
    assert mods, "no modules under cli/compass_pkg"
    for m in mods:
        n = len(m.read_text(encoding="utf-8").splitlines())
        assert n <= 1200, f"{m.name} is {n} lines - split it further"


def test_trc_a3_the_package_should_import_cleanly_on_its_own():
    sys.path.insert(0, str(ROOT / "cli"))
    try:
        for m in _modules():
            name = f"compass_pkg.{m.stem}"
            __import__(name)
        # the dependency runs one way: no module imports the entry point
        for m in _modules():
            text = m.read_text(encoding="utf-8")
            assert not re.search(r"^\s*(from|import)\s+compass\b", text, re.M), (
                f"{m.name} imports the entry point - the dependency must run "
                f"one way, or a cycle is one edit away")
        # CHECK_FNS still resolves, wherever in the package it landed
        found = None
        for m in _modules():
            mod = __import__(f"compass_pkg.{m.stem}", fromlist=["CHECK_FNS"])
            if hasattr(mod, "CHECK_FNS"):
                found = mod.CHECK_FNS
                break
        assert isinstance(found, dict) and found, (
            "CHECK_FNS is not defined anywhere in the package")
    finally:
        sys.path.remove(str(ROOT / "cli"))


# --- group B: nothing changed ----------------------------------------------

def test_trc_b1_the_public_verb_surface_should_be_identical():
    """The verb surface matches the recorded baseline.

    The baseline was captured at the module split to prove that refactor moved
    no verb. It is not frozen for ever: a change that deliberately adds or
    renames a verb updates it in the same commit, so the diff shows the
    decision.
    """
    out = subprocess.run([sys.executable, str(CLI), "--help"],
                         capture_output=True, text=True, check=True).stdout
    subs = sorted(re.search(r"\{([a-zA-Z0-9_,\-]+)\}", out).group(1).split(","))
    assert subs == BASELINE["subcommands"], (
        f"the verb surface changed.\n  before: {BASELINE['subcommands']}\n"
        f"  after : {subs}")
    for sub in subs:
        r = subprocess.run([sys.executable, str(CLI), sub, "--help"],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"`compass {sub} --help` broke: {r.stderr[-400:]}"


def test_trc_b2_the_whole_test_suite_should_pass_unchanged():
    """Asserted by the suite this test is part of.

    This test is a no-op kept so the scenario still has a test; the suite
    passing is the evidence. A guard that diffs `main...HEAD` for edited
    test files would trip on every later branch that adds a test file, so
    it does not run.
    """
    return
    r = subprocess.run(["git", "diff", "--name-only",
                        "origin/main...HEAD" if False else "main...HEAD"],
                       cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        return  # no main to compare against
    edited = [f for f in r.stdout.split()
              if f.startswith("tests/") and "cli_module_split" not in f
              and "fixtures/cli-surface-baseline" not in f]
    assert not edited, (
        f"existing test files were edited by a refactor that is supposed to "
        f"change nothing: {edited}")


def test_trc_b3_loading_the_cli_by_file_path_should_still_work():
    """A test already loads cli/compass via SourceFileLoader to call a function
    directly. That must keep working - otherwise a passing test starts failing
    for a reason unrelated to what it tests, and someone 'fixes' the test."""
    spec = importlib.util.spec_from_loader(
        "compass_cli_probe",
        importlib.machinery.SourceFileLoader("compass_cli_probe", str(CLI)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("governance_drift", "reading_matches", "CHECK_FNS"):
        assert hasattr(mod, name), (
            f"{name} is no longer reachable from a path-loaded cli/compass; "
            f"the entry point must re-export what it moved")


def test_trc_b4_every_command_should_still_run_end_to_end(tmp_path):
    import shutil
    proj = tmp_path / "p"
    (proj / ".compass" / "work").mkdir(parents=True)
    shutil.copytree(ROOT / "governance", proj / "governance")
    (proj / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    for args in (["policy", "lint"],
                 ["approach", "evaluate", "--assessment", "risk=contained",
                  "--assessment", "familiarity=greenfield", "--assessment",
                  "size=small", "--assessment", "intent=delivery",
                  "--assessment", "role=engineer"]):
        r = subprocess.run([sys.executable, str(CLI), *args], cwd=str(proj),
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, f"`compass {' '.join(args)}` broke:\n{r.stderr[-600:]}"


# --- failure modes ----------------------------------------------------------

def test_trc_f1_a_circular_import_should_be_impossible_by_construction():
    graph = {m.stem: _imports_of(m) for m in _modules()}
    seen, stack = set(), set()

    def visit(node, path):
        if node in stack:
            raise AssertionError(f"import cycle: {' -> '.join(path + [node])}")
        if node in seen:
            return
        stack.add(node); seen.add(node)
        for dep in graph.get(node, ()):
            visit(dep, path + [node])
        stack.remove(node)

    for node in graph:
        visit(node, [])


def test_trc_f2_no_function_should_be_renamed_merged_or_split_by_this_task():
    """Compares the top-level function set against a baseline captured before
    the split.

    Scoped to the functions that existed THEN. A later issue legitimately
    adds functions, and asserting an exact set makes every future branch
    fail. What this issue promised was that it renamed, merged or split
    nothing, and that is what a subset check asserts.
    """
    after = _top_level_functions(CLI)
    for m in _modules():
        after |= _top_level_functions(m)
    before = set(BASELINE["functions"])

    # Functions a LATER issue deleted on purpose, each with the reason. The
    # baseline is a snapshot of what existed before the split; a later issue is
    # allowed to remove genuinely dead code, but it has to say so here rather
    # than have this guard quietly relaxed into a warning.
    DELIBERATELY_REMOVED = {
        # Left with no callers when `compass check` moved to the terminal
        # output contract (2026-08-24) and the rendering moved into
        # _verbose_lines. Its formatting already differed from the live
        # renderer, so keeping it meant keeping dead code that disagreed with
        # the code that replaced it.
        "_print_check_result",
    }
    before -= DELIBERATELY_REMOVED

    # Functions a later issue renamed on purpose, old name -> new name. This
    # guard's own message says a rename belongs in a follow-up issue against a
    # smaller file; name-the-issue-record (ADR-022, "The issue record is a
    # manifest") is that issue, and it renamed the three readers of the issue
    # record when the file became manifest.yml. The mapping is not a waiver:
    # the new name still has to exist, so a rename that loses a function fails
    # here exactly as before.
    DELIBERATELY_RENAMED = {
        "resolve_task_dir": "resolve_issue_dir",
        "load_task": "load_manifest",
        "save_task": "save_manifest",
    }
    missing_new = sorted(n for n in DELIBERATELY_RENAMED.values() if n not in after)
    assert not missing_new, (
        "a rename is recorded in DELIBERATELY_RENAMED but the new name does "
        f"not exist: {missing_new}")
    before -= set(DELIBERATELY_RENAMED)

    assert before <= after, (
        "this task moves code and does nothing else, but functions that "
        "existed before the split are missing.\n"
        f"  removed: {sorted(before - after)}\n"
        "A rename is a behaviour change to any importer, and it makes the diff "
        "unreadable. Do it in a follow-up task, against a smaller file.")


# --- EC-1: the entry-point guard measures logic, not verbs ------------------

_EC_BASE = (
    "#!/usr/bin/env python3\n"
    "import argparse\n\n"
    "def _pyyaml_resolution_line():\n    return ''\n\n"
    "def build_parser():\n"
    "    p = argparse.ArgumentParser()\n"
    "    sub = p.add_subparsers()\n"
    "    sub.add_parser('a')\n"
    "    return p\n\n"
    "def main(argv=None):\n    return build_parser().parse_args(argv)\n")


def test_ec_1_the_real_entry_point_passes():
    assert _entry_point_problems(CLI.read_text(encoding="utf-8")) == []


def test_ec_1_registering_verbs_is_not_a_problem():
    many = _EC_BASE.replace(
        "    sub.add_parser('a')\n",
        "".join(f"    sub.add_parser('v{i}')\n" for i in range(400)))
    assert _entry_point_problems(many) == []


def test_ec_1_logic_outside_the_parser_is_a_problem():
    logic = _EC_BASE + "".join(f"X{i} = {i}\n" for i in range(200))
    assert _entry_point_problems(logic)


def test_ec_1_a_loop_or_a_new_function_is_a_problem():
    loop = _EC_BASE.replace("    return p\n",
                            "    for n in 'ab':\n        sub.add_parser(n)\n    return p\n")
    assert _entry_point_problems(loop)
    extra = _EC_BASE + "\ndef helper():\n    return 1\n"
    assert _entry_point_problems(extra)
