"""The living spec archives a scenario only when its manifest says so.

Intent ids are local to an issue (most issues use INT-1). Keying supersession
on the intent id made each landing archive every other issue's scenario
that shared the id, and the issue's own siblings too. The recorded link is
`superseded_by`, which names a scenario in the same issue.

Scenario ids: see docs/system-spec.md (TRC-001).
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
        "compass_flow_supersession", str(ROOT / "cli" / "compass_pkg" / "flow.py"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _issue(project, slug, landed, scenarios):
    """Write a landed issue; `scenarios` is a list of (id, title, intent)."""
    work = project / ".compass" / "work" / slug
    work.mkdir(parents=True)
    body = (
        "schema_version: '2.0'\n"
        f"task: {slug}\n"
        "created: '2026-08-10'\n"
        "status: landed\n"
        f"land_timestamp: '{landed}'\n"
        "scenarios:\n"
    )
    for scn_id, title, intent, *link in scenarios:
        body += f"- id: {scn_id}\n  title: {title}\n  intent: {intent}\n"
        if link and link[0]:
            body += f"  superseded_by: {link[0]}\n"
    (work / "manifest.yml").write_text(body, encoding="utf-8")


def _derive(project):
    (project / ".compass" / "config.yml").write_text(
        "version: 1.0.0\n", encoding="utf-8")
    _flow_module().derive_system_spec(str(project))
    docs = project / "docs"
    return ((docs / "system-spec.md").read_text(encoding="utf-8"),
            (docs / "system-spec-archive.md").read_text(encoding="utf-8")
            if (docs / "system-spec-archive.md").exists() else "")


def test_a_later_issue_with_the_same_intent_id_leaves_the_earlier_one_current(tmp_path):
    _issue(tmp_path, "first-issue", "2026-08-01T10:00:00Z",
           [("TRC-001", "first behaviour", "INT-1")])
    _issue(tmp_path, "second-issue", "2026-08-02T10:00:00Z",
           [("TRC-001", "second behaviour", "INT-1")])

    spec, archive = _derive(tmp_path)

    assert "first behaviour" in spec, "the earlier issue's scenario left the living spec"
    assert "second behaviour" in spec
    assert "first behaviour" not in archive


def test_scenarios_of_one_issue_that_share_an_intent_are_all_current(tmp_path):
    _issue(tmp_path, "only-issue", "2026-08-01T10:00:00Z",
           [("TRC-001", "first sibling", "INT-1"),
            ("TRC-002", "second sibling", "INT-1")])

    spec, archive = _derive(tmp_path)

    assert "first sibling" in spec, "a sibling scenario was archived"
    assert "second sibling" in spec
    assert "first sibling" not in archive


def test_a_scenario_that_names_what_replaces_it_is_archived(tmp_path):
    """`superseded_by` is the recorded link; it names a scenario in the same issue."""
    _issue(tmp_path, "only-issue", "2026-08-01T10:00:00Z",
           [("TRC-001", "older wording", "INT-1", "[TRC-002]"),
            ("TRC-002", "newer wording", "INT-1", None)])

    spec, archive = _derive(tmp_path)

    assert "newer wording" in spec
    assert "older wording" not in spec
    assert "older wording" in archive
