"""The system-spec deriver honours a scenario that serves several intents.

`schemas/manifest.schema.json` says a scenario's `intent` may be "a string or a
list of strings (a scenario may serve more than one intent)". The deriver
must accept a list; using a list as a dictionary key raises
`TypeError: unhashable type: 'list'`.

Scenario ids: see docs/system-spec.md (TRC-1).
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _flow_module():
    sys.path.insert(0, str(ROOT / "cli"))
    loader = importlib.machinery.SourceFileLoader(
        "compass_flow_multi_intent", str(ROOT / "cli" / "compass_pkg" / "flow.py"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _project(tmp_path, intent):
    """A project with one landed issue whose single scenario carries `intent`."""
    work = tmp_path / ".compass" / "work" / "an-issue"
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text(
        "version: 1.0.0\n", encoding="utf-8")
    intent_yaml = (
        "[" + ", ".join(intent) + "]" if isinstance(intent, list) else intent
    )
    (work / "manifest.yml").write_text(
        "schema_version: '2.0'\n"
        "task: an-issue\n"
        "created: '2026-08-10'\n"
        "status: landed\n"
        "scenarios:\n"
        "- id: TRC-1\n"
        "  title: the behaviour this scenario states\n"
        f"  intent: {intent_yaml}\n",
        encoding="utf-8",
    )
    return tmp_path


def test_a_scenario_serving_two_intents_answers_for_both(tmp_path):
    """A list intent derives, and the scenario is current behaviour.

    The living spec lists the scenario once and does not print its intents.
    """
    flow = _flow_module()
    project = _project(tmp_path, ["INT-1", "INT-2"])

    flow.derive_system_spec(str(project))

    spec = (project / "docs" / "system-spec.md").read_text(encoding="utf-8")
    assert spec.count("- `TRC-1` ") == 1


def test_a_scenario_serving_one_intent_still_derives(tmp_path):
    """The scalar form is unchanged - the list form must not break the scalar form."""
    flow = _flow_module()
    project = _project(tmp_path, "INT-9")

    flow.derive_system_spec(str(project))

    spec = (project / "docs" / "system-spec.md").read_text(encoding="utf-8")
    assert spec.count("- `TRC-1` ") == 1
