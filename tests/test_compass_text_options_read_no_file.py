"""Scenario `TRC-052` of issue `hooks-stop-refusing-harmless-work`: no text option
of the `compass` command reads a file.

The approval guard does not judge the value of `--note`, `--reason`, `--scope`,
`--description` and `--title` of `compass`, because the value is text. That
holds only while no parser turns such a value into a file to open: a file type
on the option, or an `@file` prefix on the parser. A later change that adds
either must fail here, so the guard's list of text options and the parsers
stay in step.

The walk is checked twice: it finds the options on the real parsers (so it
does not pass on an empty search), and it reports a parser built to break the rule (so it can fail).
"""
from __future__ import annotations

import argparse
import sys
from importlib.machinery import SourceFileLoader
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

TEXT_OPTIONS = ("--note", "--reason", "--scope", "--description", "--title")


def _root_parser():
    import compass_pkg  # noqa: F401  - resolves the bundled yaml
    spec = importlib.util.spec_from_loader(
        "compass_entry_text_options", SourceFileLoader("compass_entry_text_options",
                                                       str(ROOT / "cli" / "compass")))
    module = importlib.util.module_from_spec(spec)
    old = sys.argv
    sys.argv = ["compass"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old
    return module.build_parser()


def _parsers(parser, path="compass"):
    """Every parser under `parser`, with the words a person types to reach it."""
    yield path, parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                yield from _parsers(child, f"{path} {name}")


def _opens_a_file(kind):
    return isinstance(kind, argparse.FileType) or kind is open


def _offences(parser):
    """`(where, what)` for each way a parser makes a text option read a file."""
    found, seen = [], 0
    for path, one in _parsers(parser):
        if one.fromfile_prefix_chars:
            found.append((path, f"reads {one.fromfile_prefix_chars}file values"))
        for action in one._actions:
            options = [o for o in action.option_strings if o in TEXT_OPTIONS]
            if not options:
                continue
            seen += 1
            if _opens_a_file(action.type):
                found.append((path, f"{options[0]} has a file type"))
    return found, seen


def test_trc_052_no_text_option_of_the_compass_command_reads_a_file():
    found, seen = _offences(_root_parser())
    assert seen >= 5, f"the walk found only {seen} text options, so it may be looking in the wrong place"
    assert not found, found


def test_trc_052_the_walk_reports_a_text_option_that_reads_a_file():
    broken = argparse.ArgumentParser(prog="x", fromfile_prefix_chars="@")
    sub = broken.add_subparsers(dest="cmd")
    child = sub.add_parser("start")
    child.add_argument("--note", type=argparse.FileType("r"))
    found, seen = _offences(broken)
    assert seen == 1
    assert ("compass", "reads @file values") in found
    assert ("compass start", "--note has a file type") in found
