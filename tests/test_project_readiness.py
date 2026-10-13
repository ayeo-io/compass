"""Repository readiness: the signals, the record, the floor and the readers.

Scenario ids PRC-1 to PRC-44 (issue project-readiness-caps-autonomy). Each test
name starts with its scenario id. The file has one section per work unit; a
later unit writes only under its own heading.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import project_readiness_support as support  # noqa: E402

PRESET = ROOT / "governance" / "presets" / "default"

SHIPPED_SIGNALS = (
    "agent-instructions-present", "lint-declared-and-clean", "typecheck-declared-and-clean",
    "format-declared-and-clean", "build-declared-and-succeeds",
    "tests-declared-and-under-two-minutes", "no-flaky-tests-on-record",
    "structured-logging-declared", "codeowners-present", "pre-commit-hooks-present",
    "secret-scan-declared")
#: The keys of a red record before the readiness change, so a new project key
#: cannot add one.
BASELINE_RED_KEYS = ("_full_log", "argv", "changes_id", "changes_scope", "command",
                     "content_digest", "exit_code", "log_excerpt", "passed", "record_id",
                     "red_kind", "scenario", "timestamp", "tree_id")
REQUIRED_SIGNALS = ("agent-instructions-present", "build-declared-and-succeeds",
                    "tests-declared-and-under-two-minutes", "lint-declared-and-clean")


# --- U1 catalogue and settings ---


def test_prc_3(tmp_path):
    from compass_pkg import catalogue_spec
    from compass_pkg.check_registry import READINESS

    document = yaml.safe_load((PRESET / "readiness.yml").read_text(encoding="utf-8"))
    signals = document["readiness"]
    assert set(signals) == set(SHIPPED_SIGNALS) and len(signals) == 11
    for signal_id, entry in signals.items():
        assert isinstance(entry["statement"], str) and entry["statement"], signal_id
        assert isinstance(entry["weight"], int) and not isinstance(entry["weight"], bool)
        assert entry["impl"] in READINESS, signal_id
        assert READINESS[entry["impl"]].version, signal_id
        assert set(entry) <= set(catalogue_spec.FIELDS["readiness"]), signal_id
    required = {i for i, e in signals.items() if e.get("required_for_autonomous") is True}
    assert required == set(REQUIRED_SIGNALS)
    others = [e.get("required_for_autonomous", False) for i, e in signals.items()
              if i not in REQUIRED_SIGNALS]
    assert others == [False] * 7

    project = support.make_project(tmp_path / "fixture")
    code, out, err = support.run_compass(project, "policy", "lint")
    assert code == 0, out + err

    # The catalogue is read through the layer chain wherever a compass.yml
    # counts, including in the framework's own repository, where the
    # effective view otherwise skips the project file.
    from compass_pkg import effective, readiness_catalogue
    framework = tmp_path / "framework"
    shutil.copytree(ROOT / "governance" / "presets", framework / "governance" / "presets")
    (framework / ".compass").mkdir()
    (framework / "compass.yml").write_text(yaml.safe_dump({
        "schema": 1,
        "readiness": {"codeowners-present": {"set": {"weight": 7}}}}), encoding="utf-8")
    saved = effective.FRAMEWORK_ROOT
    effective.FRAMEWORK_ROOT = str(framework)
    try:
        assert effective._layered(str(framework)) is False
        layered = readiness_catalogue.catalogue(str(framework))
    finally:
        effective.FRAMEWORK_ROOT = saved
    assert layered["codeowners-present"]["weight"] == 7
    assert readiness_catalogue.catalogue(str(project))["codeowners-present"]["weight"] == 1
    assert readiness_catalogue.floor(layered) == sorted(REQUIRED_SIGNALS)


def _diff_result(project, parent="default@6", child="project"):
    code, out, err = support.run_compass(project, "policy", "diff", parent, child, "--json")
    assert code == 0, out + err
    return json.loads(out)["classification"]["result"]


def _lint(project):
    code, out, err = support.run_compass(project, "policy", "lint")
    return code, out + err


def test_prc_5(tmp_path):
    waiver = {"reason": "this project measures agent readiness another way",
              "approved_by": "jed72", "approved_on": "2026-10-01"}
    added = {"my-signal": {"statement": "A CODEOWNERS file exists.", "impl": "codeowners-present",
                           "weight": 1}}
    cases = {
        "added": {"readiness": added},
        "weight": {"readiness": {"codeowners-present": {"set": {"weight": 5}}}},
        "added-and-required": {"readiness": {"my-signal": {
            **added["my-signal"], "required_for_autonomous": True}}},
        "off-the-floor": {"readiness": {"agent-instructions-present": {
            "set": {"required_for_autonomous": False}}}},
    }
    results = {}
    for name, layer in cases.items():
        project = support.make_project(tmp_path / name, {"schema": 1, "owner": "jed72", **layer})
        results[name] = (_diff_result(project), _lint(project))
    assert results["added"][0] == "equivalent" and results["added"][1][0] == 0
    assert results["weight"][0] == "equivalent" and results["weight"][1][0] == 0
    assert results["added-and-required"][0] == "tightening"
    assert results["added-and-required"][1][0] == 0
    assert results["off-the-floor"][0] == "loosening"
    code, text = results["off-the-floor"][1]
    assert code == 1 and "C-LOOSENING" in text
    assert "readiness.agent-instructions-present.required_for_autonomous" in text

    # A blocking check made advisory is classified as a loosening by the same
    # rules, and an owner's waiver in the entry excuses either change.
    check = support.make_project(tmp_path / "check", {
        "schema": 1, "owner": "jed72",
        "checks": {"suite-passed": {"set": {"severity": "advisory"}}}})
    assert _diff_result(check) == "loosening"
    import waiver_fixtures as fx
    from compass_pkg import waivers
    parent = fx.parent_config()
    parent["readiness"] = {"agent-instructions-present": {
        "statement": "x", "impl": "agent-instructions-present", "weight": 1,
        "required_for_autonomous": True}}
    changes = {
        "check": ("checks", "tests-pass", {"severity": "advisory"}),
        "readiness": ("readiness", "agent-instructions-present",
                      {"required_for_autonomous": False})}
    for kind, (catalogue, entry_id, change) in changes.items():
        child = fx.resolve(parent, {catalogue: {entry_id: {"set": change}}})
        refused = waivers.attribute(parent, child, [])
        assert (refused.result, refused.refusal["result"]) == ("refused", "loosening"), kind
        found, faults = waivers.find(
            {catalogue: {entry_id: {"set": change, "waiver": fx.project_waiver()}}}, "project")
        assert not faults
        assert waivers.attribute(parent, child, found).result == "excused", kind

    # Both need the owner's waiver, written in the entry it excuses.
    waived = support.make_project(tmp_path / "waived", {
        "schema": 1, "owner": "jed72", "readiness": {"agent-instructions-present": {
            "set": {"required_for_autonomous": False}, "waiver": waiver}}})
    code, text = _lint(waived)
    assert code == 0, text
    # An approver who is not the owner does not excuse it.
    stranger = support.make_project(tmp_path / "stranger", {
        "schema": 1, "owner": "jed72", "readiness": {"agent-instructions-present": {
            "set": {"required_for_autonomous": False},
            "waiver": {**waiver, "approved_by": "someone-else"}}}})
    assert _lint(stranger)[0] == 1

    # Removing a signal that is on the floor loosens it too.
    removed = support.make_project(tmp_path / "removed", {
        "schema": 1, "owner": "jed72",
        "readiness": {"lint-declared-and-clean": {"remove": True}}})
    assert _diff_result(removed) == "loosening"

    # An added signal whose impl is not registered is refused by name, and so
    # is a parameter the implementation does not allow.
    bad_impl = support.make_project(tmp_path / "bad-impl", {
        "schema": 1, "owner": "jed72", "readiness": {"my-signal": {
            **added["my-signal"], "impl": "no-such-impl"}}})
    code, text = _lint(bad_impl)
    assert code == 1 and "my-signal" in text and "no-such-impl" in text
    bad_param = support.make_project(tmp_path / "bad-param", {
        "schema": 1, "owner": "jed72", "readiness": {"lint-declared-and-clean": {
            "set": {"params": {"key": "deploy_command"}}}}})
    code, text = _lint(bad_param)
    assert code == 1 and "lint-declared-and-clean" in text and "deploy_command" in text
    not_boolean = support.make_project(tmp_path / "not-boolean", {
        "schema": 1, "owner": "jed72", "readiness": {"my-signal": {
            **added["my-signal"], "required_for_autonomous": "yes"}}})
    assert _lint(not_boolean)[0] == 1


def test_prc_7(tmp_path):
    """Baseline: `tdd-red` with no command runs `test_micro_command`, falling
    back to `test_command`, and reads none of the new project keys."""
    manifest = {"task": "fixture-issue", "created": "2026-10-13",
                "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                               "size": "small", "intent": "delivery"},
                "delivery_approach": "regular",
                "scenarios": [{"id": "SCN-1", "intent": "INT-1", "tests": ["tests/t.py::t"]}],
                "evidence": []}
    scripts = ("micro.sh", "full.sh", "lint.sh")
    files = {f"scripts/{name}": (f"#!/bin/sh\ntouch ran-{name}\n"
                                      "echo 'tests/t.py::t FAILED'\nexit 1\n") for name in scripts}
    files[".compass/work/fixture-issue/manifest.yml"] = yaml.safe_dump(manifest, sort_keys=False)
    both = {"schema": 1, "project": {"test_command": "sh scripts/full.sh",
                                     "test_micro_command": "sh scripts/micro.sh",
                                     "lint_command": "sh scripts/lint.sh"}}
    project = support.make_project(tmp_path / "both", both, files=files)
    code, out, err = support.run_compass(project, "tdd-red", "--issue", "fixture-issue",
                                         "--scenario", "SCN-1")
    assert code == 0, out + err
    assert (project / "ran-micro.sh").exists()
    assert not (project / "ran-full.sh").exists() and not (project / "ran-lint.sh").exists()
    record = json.loads((project / ".compass/work/fixture-issue/evidence/red-SCN-1.json")
                        .read_text(encoding="utf-8"))
    assert record["command"] == "sh scripts/micro.sh"
    assert sorted(record) == sorted(BASELINE_RED_KEYS)

    only_full = {"schema": 1, "project": {"test_command": "sh scripts/full.sh",
                                          "lint_command": "sh scripts/lint.sh"}}
    project = support.make_project(tmp_path / "full", only_full, files=files)
    code, out, err = support.run_compass(project, "tdd-red", "--issue", "fixture-issue",
                                         "--scenario", "SCN-1")
    assert code == 0, out + err
    assert (project / "ran-full.sh").exists() and not (project / "ran-lint.sh").exists()


#: The shipped files that decide what blocks, what a gate asks and how work is
#: routed. None of them may name a readiness signal or the floor.
GOVERNED_FILES = ("governance/guardrails.yml", "governance/routing-policy.yml",
                  "governance/presets/default/gates.yml", "governance/presets/default/rules.yml",
                  "governance/presets/default/checks.yml",
                  "governance/presets/default/approaches.yml")


def _readiness_words(path):
    """The readiness words a governance file holds. `launch-readiness` is an
    unrelated artifact name, so it is not counted."""
    text = Path(path).read_text(encoding="utf-8").replace("launch-readiness", "")
    words = (*SHIPPED_SIGNALS, "required_for_autonomous", "readiness")
    return sorted(word for word in words if word in text)


def test_prc_25(tmp_path):
    for relative in GOVERNED_FILES:
        assert _readiness_words(ROOT / relative) == [], relative

    # The scan can fail: a readiness signal added to a copy of rules.yml is
    # found.
    planted = tmp_path / "rules.yml"
    planted.write_text((PRESET / "rules.yml").read_text(encoding="utf-8")
                       + "# codeowners-present\n", encoding="utf-8")
    assert _readiness_words(planted) == ["codeowners-present"]

    # `compass check` on a balanced issue with every readiness signal absent
    # reports no readiness failure.
    manifest = {"task": "fixture-issue", "created": "2026-10-13",
                "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                               "size": "small", "intent": "delivery"},
                "delivery_approach": "regular", "scenarios": [], "evidence": []}
    project = support.make_project(
        tmp_path / "balanced", {"schema": 1, "autonomy": "balanced"},
        files={".compass/work/fixture-issue/manifest.yml":
               yaml.safe_dump(manifest, sort_keys=False)})
    code, out, err = support.run_compass(project, "check", "--issue", "fixture-issue", "--json")
    assert json.loads(out)["ran"] > 0, out + err
    report = out + err
    assert "readiness" not in report.lower()
    assert not [word for word in SHIPPED_SIGNALS if word in report]


# --- U2 the readiness command ---


# --- U3 the floor ---


# --- U4 readers, init and retro ---


# --- U5 this repository and the measures ---
