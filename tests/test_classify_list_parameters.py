"""A list parameter of a check tightens by superset (ADR-073).

The classifier compares the trigger lists of `contracts-declared` as sets of
exact entries: a list that holds every shipped entry and more is `tighter`, a
list that lacks a shipped entry is `looser`, and a list that lacks one and adds
another, or is malformed, is `incomparable`.

Scenario ids: `TRC-001` to `TRC-012` in
`list-parameter-superset-tightens/acceptance-criteria.md`. `TRC-008` is in
`tests/test_document_set_sections.py`.
"""
from __future__ import annotations

import dataclasses
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

PATHS = ["schemas/*", "governance/presets/*", "*.schema.json"]
PAIR = {"path": "*.py", "contains": "add_parser("}
OTHER_PAIR = {"path": "*.yaml", "contains": "openapi:"}
PATHS_KEY = "trigger_paths"
CONTENTS_KEY = "trigger_contents"
OVERALL = {"tighter": "tightening", "looser": "loosening",
           "incomparable": "incomparable", "equal": "equivalent"}


def _config(**params):
    """The classifier fixture whose check `tests-pass` runs `contracts-declared`
    with the given parameters, so its trigger lists are owed at every point."""
    import classifier_fixtures
    config = classifier_fixtures.base()
    config["checks"]["tests-pass"].update(impl="contracts-declared", params=params)
    return config


def _shipped():
    return _config(trigger_paths=list(PATHS), trigger_contents=[dict(PAIR)])


def _classify(parent, child, **kw):
    from compass_pkg import classify
    return classify.classify(parent, child, **kw)


def _change(key, value, parent=None):
    """`(parent, child)` where the child changes one trigger list."""
    parent = parent or _shipped()
    child = _shipped()
    child["checks"]["tests-pass"]["params"][key] = value
    return parent, child


def _refused(parent, child):
    """Whether a project layer with this child and no waiver is refused."""
    from compass_pkg import waivers
    return waivers.attribute(parent, child, []).result == "refused"


def _words(text):
    return re.sub(r"\s+", " ", text)


# --- TRC-001 to TRC-007: comparing a list parameter -------------------------------

def test_added_trigger_path_is_tighter():
    """Scenario id: `TRC-001` in list-parameter-superset-tightens/acceptance-criteria.md"""
    parent, child = _change(PATHS_KEY, PATHS + ["api/**"])
    got = _classify(parent, child)
    assert got.result == "tightening", got.reason
    assert not _refused(parent, child)


def test_added_trigger_contents_pair_is_tighter():
    """Scenario id: `TRC-002` in list-parameter-superset-tightens/acceptance-criteria.md"""
    parent, child = _change(CONTENTS_KEY, [dict(PAIR), dict(OTHER_PAIR)])
    got = _classify(parent, child)
    assert got.result == "tightening", got.reason
    assert not _refused(parent, child)


def test_removed_trigger_path_is_looser():
    """Scenario id: `TRC-003` in list-parameter-superset-tightens/acceptance-criteria.md"""
    parent, child = _change(PATHS_KEY, PATHS[:2])
    got = _classify(parent, child)
    assert got.result == "loosening", got.reason
    assert _refused(parent, child)


@pytest.mark.parametrize("key, shipped, project", [
    (PATHS_KEY, ["schemas/*", "*.schema.json"], ["schemas/*", "api/**"]),
    (CONTENTS_KEY, [dict(PAIR)], [{"path": "*.go", "contains": "add_parser("}]),
    (CONTENTS_KEY, [dict(PAIR)], [{"path": "*.py", "contains": "register("}]),
], ids=["path", "other-glob", "other-text"])
def test_replaced_list_entry_is_incomparable(key, shipped, project):
    """Scenario id: `TRC-004` in list-parameter-superset-tightens/acceptance-criteria.md"""
    parent = _config(**{PATHS_KEY: list(PATHS), CONTENTS_KEY: [dict(PAIR)], key: shipped})
    child = _config(**{PATHS_KEY: list(PATHS), CONTENTS_KEY: [dict(PAIR)], key: project})
    got = _classify(parent, child)
    assert got.result == "incomparable", got.reason
    assert _refused(parent, child)


@pytest.mark.parametrize("key, shipped, project", [
    (PATHS_KEY, ["schemas/*", "governance/presets/*"],
     ["governance/presets/*", "schemas/*"]),
    (PATHS_KEY, ["schemas/*", "governance/presets/*"],
     ["schemas/*", "schemas/*", "governance/presets/*"]),
    (CONTENTS_KEY, [dict(PAIR), dict(OTHER_PAIR)],
     [dict(OTHER_PAIR), {"contains": "add_parser(", "path": "*.py"}]),
], ids=["reordered", "repeated", "pairs-reordered"])
def test_reordered_list_is_equal(key, shipped, project):
    """Scenario id: `TRC-005` in list-parameter-superset-tightens/acceptance-criteria.md"""
    other = CONTENTS_KEY if key == PATHS_KEY else PATHS_KEY
    rest = {PATHS_KEY: list(PATHS), CONTENTS_KEY: [dict(PAIR)]}[other]
    parent = _config(**{other: rest, key: shipped})
    child = _config(**{other: rest, key: project})
    got = _classify(parent, child)
    assert got.result == "equivalent", got.reason
    assert not _refused(parent, child)


def test_unknown_direction_still_raises():
    """Scenario id: `TRC-006` in list-parameter-superset-tightens/acceptance-criteria.md"""
    from compass_pkg.core import CompassError
    parent, child = _change(PATHS_KEY, PATHS + ["api/**"])
    wrong = {f"checks.params.contracts-declared.{PATHS_KEY}": "wider"}
    with pytest.raises(CompassError) as caught:
        _classify(parent, child, directions=wrong)
    message = str(caught.value)
    assert "wider" in message, message
    assert "superset" in message, message


@pytest.mark.parametrize("key, value", [
    (PATHS_KEY, None),
    (PATHS_KEY, "api/**"),
    (PATHS_KEY, ["schemas/*", ""]),
    (CONTENTS_KEY, None),
    (CONTENTS_KEY, [dict(PAIR), "add_parser("]),
    (CONTENTS_KEY, [dict(PAIR, extra="x")]),
    (CONTENTS_KEY, [{"path": "*.py"}]),
], ids=["no-paths", "string-paths", "empty-entry", "no-contents", "bare-string-entry",
        "extra-key", "no-text"])
def test_missing_or_malformed_list_is_incomparable(key, value):
    """Scenario id: `TRC-007` in list-parameter-superset-tightens/acceptance-criteria.md"""
    parent, child = _change(key, value)
    if value is None:
        del child["checks"]["tests-pass"]["params"][key]
    got = _classify(parent, child)
    assert got.result == "incomparable", got.reason
    # A missing side raises nothing on either side of the comparison.
    assert _classify(child, parent).result == "incomparable"
    assert _refused(parent, child)


# --- TRC-009, TRC-010: what the change must not disturb ---------------------------

TIMED = "tests-declared-and-under-two-minutes"


def _number(value, impl="command-passes"):
    config = _config()
    params = {} if value is None else {"timeout_seconds": value}
    config["checks"]["tests-pass"].update(impl=impl, params=params)
    return config


def _args(value):
    config = _config()
    config["checks"]["tests-pass"].update(impl="command-passes", params={"args": value})
    return config


def _timed(command):
    config = _config()
    config["readiness"] = {TIMED: {
        "statement": "A test command passes within two minutes.", "impl": "tests-under-limit",
        "params": {"command": command, "limit_seconds": 120},
        "weight": 3, "required_for_autonomous": True}}
    return config


TIMEOUT = "checks.params.command-passes.timeout_seconds"


@pytest.mark.parametrize("direction, parent, child, outcome", [
    ("lower", _number(3), _number(2), "tighter"),
    ("lower", _number(2), _number(3), "looser"),
    ("higher", _number(2), _number(3), "tighter"),
    ("higher", _number(3), _number(2), "looser"),
    ("none", _number(2), _number(3), "incomparable"),
    ("none", _number(None), _number(3), "incomparable"),
    (None, _args(["-x"]), _args(["-x", "-q"]), "incomparable"),
    (None, _timed("test_command"), _timed("test_micro_command"), "equal"),
    (None, _timed("test_command"), _timed("build_command"), "incomparable"),
], ids=["lower-tighter", "lower-looser", "higher-tighter", "higher-looser", "none",
        "no-ceiling", "args-list", "choice-swap", "outside-choices"])
def test_other_directions_classify_as_before(direction, parent, child, outcome):
    """Scenario id: `TRC-009` in list-parameter-superset-tightens/acceptance-criteria.md"""
    directions = {TIMEOUT: direction} if direction else None
    got = _classify(parent, child, directions=directions)
    assert got.result == OVERALL[outcome], got.reason


def test_classifier_version_is_raised_for_the_list_rule(monkeypatch):
    """Scenario id: `TRC-010` in list-parameter-superset-tightens/acceptance-criteria.md"""
    from compass_pkg import classify
    assert classify.CLASSIFIER_VERSION > 10
    parent, child = _change(PATHS_KEY, PATHS + ["api/**"])
    now = classify.classification_key(parent, child)
    monkeypatch.setattr(classify, "CLASSIFIER_VERSION", 10)
    assert classify.classification_key(parent, child) != now


# --- the registry guards (design decision DD-4) ------------------------------------

def test_only_the_two_trigger_lists_declare_superset():
    from compass_pkg.check_registry import REGISTRY
    from compass_pkg.readiness_registry import READINESS
    declared = {(name, param) for table in (REGISTRY, READINESS)
                for name, entry in table.items()
                for param, direction in entry.tighter.items() if direction == "superset"}
    assert declared == {("contracts-declared", PATHS_KEY),
                        ("contracts-declared", CONTENTS_KEY)}


def test_a_check_parameter_that_is_not_a_list_cannot_declare_superset():
    from compass_pkg.check_registry import CheckImpl
    ok = CheckImpl(name="x", fn=len, params_spec={"items": "list"},
                   tighter={"items": "superset"})
    assert ok.tighter == {"items": "superset"}
    for kind in ("number", "string", "integer"):
        with pytest.raises(ValueError) as caught:
            CheckImpl(name="x", fn=len, params_spec={"items": kind},
                      tighter={"items": "superset"})
        assert "superset" in str(caught.value) and "items" in str(caught.value)
    assert dataclasses.is_dataclass(ok)


# --- TRC-011, TRC-012: the documents state the rule -------------------------------

def test_governance_documents_state_the_superset_rule():
    """Scenario id: `TRC-011` in list-parameter-superset-tightens/acceptance-criteria.md"""
    from compass_pkg import classify
    guardrails = _words((ROOT / "governance" / "guardrails.md").read_text(encoding="utf-8"))
    policy = _words((ROOT / "governance" / "routing-policy.md").read_text(encoding="utf-8"))

    entry = guardrails.split("**Trigger paths**", 1)[1].split("**Four conditions", 1)[0]
    assert "adding an entry" in entry and "needs no waiver" in entry, entry
    assert "removing or replacing an entry needs a waiver" in entry, entry
    assert "a trigger path makes the check run, so more entries check more changes" in entry
    assert "with a project waiver, because `tighter` is `none` for the key" not in guardrails

    registry = guardrails.split("**The check registry", 1)[1].split("- The corpus is", 1)[0]
    assert "`superset`" in registry and "a list parameter" in registry, registry
    assert "a check parameter cannot declare `equivalent`" in registry, registry

    assert "the direction `superset`" in policy
    rule = policy.split("the direction `superset`", 1)[1][:1500]
    for word in ("`tighter`", "`looser`", "`incomparable`", "reordering"):
        assert word in rule, (word, rule)
    held = re.findall(r"`CLASSIFIER_VERSION` is (\d+) since the list rule", policy)
    assert held == [str(classify.CLASSIFIER_VERSION)], held


def test_adr_073_records_the_list_rule():
    """Scenario id: `TRC-012` in list-parameter-superset-tightens/acceptance-criteria.md"""
    found = sorted((ROOT / "architecture" / "decisions").glob("ADR-073-*.md"))
    assert len(found) == 1, found
    text = found[0].read_text(encoding="utf-8")
    front = text.split("---", 2)[1]
    assert re.search(r"^id: ADR-073$", front, re.M), front
    assert re.search(r"^title: A list parameter tightens by superset; narrowing it is a waiver$",
                     front, re.M), front
    body = _words(text)
    assert "a trigger path makes a check run, so fewer entries check fewer changes" in body
    assert "`tighter: none`" in body, body
    first = body.split("## Decision", 1)[1].split(". ", 1)[0]
    assert "trigger_paths" in first and "trigger_contents" in first, first
    assert "only" in first, first
    clash = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "decision", "check",
                            "--base", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    assert clash.returncode == 0, clash.stdout + clash.stderr
