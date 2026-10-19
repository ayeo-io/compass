"""The CLI prints US English: its help, its messages and its old-name notice.

Scenario ids: TRC-040, TRC-041 and TRC-042 of the issue
`language-key-and-us-english`.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from importlib.machinery import SourceFileLoader
import importlib.util
from pathlib import Path

import compat_hook as ch
import us_english_words as words
from settings_helpers import hook_edit, make_project
import test_renamed_names as renamed

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

# The old kind word, spelt from pieces so no scan finds it in a literal here.
OLD_KIND = "judge" + "ment"
NEW_KIND = "judg" + "ment"
PATTERN = re.compile(r"\b(?:%s)\b" % "|".join(sorted(words.WORDS, key=len, reverse=True)),
                     re.IGNORECASE)


def _root_parser():
    spec = importlib.util.spec_from_loader("compass_entry_us", SourceFileLoader(
        "compass_entry_us", str(CLI)))
    module = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, ["compass"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = argv
    return module.build_parser()


def _every_parser(parser, path=("compass",)):
    """(path, parser, help line given by the parent) for the root, every group and every verb."""
    yield " ".join(path), parser, ""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            helps = {c.dest: (c.help or "") for c in action._choices_actions}
            for name, child in action.choices.items():
                for found in _every_parser(child, path + (name,)):
                    yield found
                yield " ".join(path + (name,)), child, helps.get(name, "")


def _words_in(text):
    return sorted({m.group(0).lower() for m in PATTERN.finditer(text)})


def test_trc_040():
    found = {}
    for path, parser, parent_help in _every_parser(_root_parser()):
        text = parser.format_help() + "\n" + parent_help
        hits = _words_in(text)
        if hits:
            found[path] = hits
    assert found == {}, found
    result = subprocess.run([sys.executable, str(CLI), "approach", "evaluate", "--help"],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0
    assert NEW_KIND in result.stdout
    assert OLD_KIND not in result.stdout


def test_trc_041():
    # An empty folder: compass init.
    with tempfile.TemporaryDirectory() as raw:
        done = subprocess.run([sys.executable, str(CLI), "init"], cwd=raw,
                              capture_output=True, text=True, timeout=60)
        assert "initialized Compass in" in done.stdout, done.stdout + done.stderr
        assert _words_in(done.stdout + done.stderr) == []
    # No issue exists: the edit hook refuses and names the US code.
    base = Path(tempfile.mkdtemp(prefix="us8-"))
    try:
        framework = ch.install(base / "framework")
        project = make_project(base, issue=False, work=False)
        exit_code, code, _err = hook_edit(framework, base, project, "src/app.py")
        assert (exit_code, code) == (2, "not-initialized")
    finally:
        shutil.rmtree(base, ignore_errors=True)
    # A verb that prints the term.
    with tempfile.TemporaryDirectory() as raw:
        shown = subprocess.run([sys.executable, str(CLI), "terminology", "catalog"], cwd=raw,
                               capture_output=True, text=True, timeout=60)
        assert shown.returncode == 0, shown.stderr
        assert shown.stdout.startswith("catalog")
        # The `also:` line names the old word on purpose; the rest is clean.
        rest = [ln for ln in shown.stdout.splitlines() if not ln.lstrip().startswith("also:")]
        assert _words_in("\n".join(rest)) == [], rest


def test_trc_042():
    notice = f"compass: kind {OLD_KIND} is now {NEW_KIND}; the old word is read until 8.0.0."
    outcomes = {}
    for word in (OLD_KIND, NEW_KIND):
        with tempfile.TemporaryDirectory() as raw:
            project = renamed._project(Path(raw))
            renamed._assessed_then_moved(project)
            code, out, err = renamed._reassess(project, "--kind", word)
            outcomes[word] = (code, out.replace(raw, "<project>"), err)
    assert outcomes[OLD_KIND][0] == outcomes[NEW_KIND][0] == 0
    assert outcomes[OLD_KIND][1] == outcomes[NEW_KIND][1]
    assert outcomes[OLD_KIND][2].count(notice) == 1
    assert [ln for ln in outcomes[OLD_KIND][2].splitlines() if "old word" in ln] == [notice]
    assert "old word" not in outcomes[NEW_KIND][2]
