"""Every command that saves a manifest is in a trigger table or named as exempt.

The table in `record_triggers` decides which commands move an issue's labels and which are
refused on an issue whose generation was built by another major. A command that saves a
manifest and is in no table would silently skip both, so a walk of the CLI's call graph
names it. The test moved here from the rendered-blocks tests when 9.0.0 removed the
after-command render (ADR-091); the table it guards stayed.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))


def _package_sources():
    sources = {"compass": (ROOT / "cli" / "compass").read_text("utf-8")}
    for path in sorted((ROOT / "cli" / "compass_pkg").glob("*.py")):
        sources[path.name] = path.read_text("utf-8")
    return sources


def commands_that_save(sources):
    """The command functions (the `func=` of a `set_defaults`) from which a call
    reaches `save_manifest`, over a call graph of the given sources `{name: text}`.
    A name defined more than once is not followed, so two unrelated helpers that
    share a name cannot join two unrelated commands."""
    defs, targets = {}, set()
    for text in sources.values():
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.FunctionDef):
                calls = set()
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Call):
                        func = inner.func
                        calls.add(func.id if isinstance(func, ast.Name)
                                  else func.attr if isinstance(func, ast.Attribute) else "")
                defs.setdefault(node.name, []).append(calls)
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr == "set_defaults"):
                targets |= {kw.value.id for kw in node.keywords
                            if kw.arg == "func" and isinstance(kw.value, ast.Name)}

    def reaches(start):
        seen, stack = set(), [start]
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            if name == "save_manifest":
                return True
            bodies = defs.get(name, [])
            if len(bodies) == 1 or name == start:
                for body in bodies:
                    stack.extend(body)
        return False
    return {t for t in targets if reaches(t)}, targets


def uncovered(sources, covered):
    saving, _ = commands_that_save(sources)
    return sorted(saving - set(covered))


def test_dcj_75_trigger_table_complete():
    from compass_pkg import record_triggers
    covered = set(record_triggers.RECORD_TRIGGERS) | set(record_triggers.EXEMPT)
    sources = _package_sources()
    assert uncovered(sources, covered) == []
    # Every entry names a real command, and every exemption carries its reason.
    _, targets = commands_that_save(sources)
    gone = sorted(n for n in covered - targets
                  if n not in ("cmd_route_evaluate", "cmd_issue_raised_by"))
    assert gone == [], gone
    assert all(isinstance(r, str) and len(r.split()) >= 5 for r in record_triggers.EXEMPT.values())
    assert not set(record_triggers.EXEMPT) & set(record_triggers.RECORD_TRIGGERS)
    # A command that saves a manifest and is in neither is named by the test.
    planted = dict(sources)
    planted["planted.py"] = (
        "from compass_pkg.core import save_manifest\n"
        "def cmd_planted(args):\n    save_manifest({}, 'x')\n    return 0\n"
        "def build(p):\n    p.set_defaults(func=cmd_planted)\n")
    assert uncovered(planted, covered) == ["cmd_planted"]
    # The label sync wraps the command and receives its exit code; nothing else runs after it.
    entry = "".join((ROOT / "cli" / "compass").read_text("utf-8").split())
    assert "github_labels.after_command(a,args.func(a)or0)" in entry
    assert "render_after" not in entry and "github_page" not in entry


def test_the_major_refusal_reads_the_same_table():
    from compass_pkg import command_guard, record_triggers
    text = (ROOT / "cli" / "compass_pkg" / "command_guard.py").read_text("utf-8")
    assert "record_triggers.RECORD_TRIGGERS" in text
    assert set(record_triggers.ISSUE_FROM) == set(record_triggers.RECORD_TRIGGERS)
    assert record_triggers.LABEL_TRIGGERS.keys() <= record_triggers.RECORD_TRIGGERS.keys()
    assert callable(command_guard.before_command)
