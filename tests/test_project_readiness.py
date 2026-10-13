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

import datetime  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

#: Every weight 1, through a project layer, as the PRC-8 fixture asks.
ALL_WEIGHTS_ONE = {signal_id: {"set": {"weight": 1}} for signal_id in SHIPPED_SIGNALS}
#: The five command signals, by the project key each one runs.
COMMAND_SIGNALS = {"build_command": "build-declared-and-succeeds",
                   "test_command": "tests-declared-and-under-two-minutes",
                   "lint_command": "lint-declared-and-clean",
                   "typecheck_command": "typecheck-declared-and-clean",
                   "format_check_command": "format-declared-and-clean"}


def _utc(text):
    return datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc)


def _flaky_files(issue="old-issue", scenario="SCN-1"):
    """Two green records for one scenario that disagree: a pass, then a
    failure of the same test."""
    folder = f".compass/work/{issue}/evidence"
    first = {"scenario": scenario, "passed": True, "exit_code": 0,
             "command": "pytest tests/t.py::t", "timestamp": "2026-10-01T10:00:00Z"}
    second = {**first, "passed": False, "exit_code": 1, "timestamp": "2026-10-02T10:00:00Z"}
    return {f"{folder}/green-{scenario}.json": json.dumps(first),
            f"{folder}/green-{scenario}-2.json": json.dumps(second)}


def _record_signal(signal_id, result="present", required=False,
                   impl="codeowners-present", weight=1):
    from compass_pkg.readiness_registry import READINESS
    return {"id": signal_id, "impl": impl, "version": READINESS[impl].version,
            "weight": weight, "required_for_autonomous": required, "result": result,
            "reason": f"{signal_id} is {result}", "not_run": None}


def _written_record(project, signals=None, measured_at=None):
    """Write a record for the fixture project through the record module."""
    from compass_pkg import readiness_record
    record = readiness_record.new_record(
        str(project), signals or [_record_signal("codeowners-present")],
        {"commands_seconds": 270, "used_seconds": 0.0}, measured_at=measured_at)
    readiness_record.write(str(project), record)
    return record


def _fresh(project, now=None):
    from compass_pkg import readiness_record
    reading = readiness_record.read(str(project))
    assert reading.status == "ok", reading
    return readiness_record.fresh(str(project), reading.record, now=now)


def test_prc_8_record_freshness_settings_catalogue_and_versions(tmp_path, monkeypatch):
    from compass_pkg import readiness_record, readiness_registry
    project = support.make_project(tmp_path / "p", {"schema": 1})
    record = _written_record(project)
    assert record["settings"]["path"] == "compass.yml"
    assert record["settings"]["digest"].startswith("sha256:")
    assert record["head"] == support.git(project, "rev-parse", "HEAD").strip()
    assert _fresh(project).fresh

    # The settings file changed.
    (project / "compass.yml").write_text("schema: 1\nautonomy: balanced\n", encoding="utf-8")
    verdict = _fresh(project)
    assert not verdict.fresh and "compass.yml changed" in verdict.reason

    # The shipped catalogue changed.
    record = _written_record(project)
    other = tmp_path / "readiness.yml"
    other.write_text("schema: 1\nreadiness: {}\n", encoding="utf-8")
    monkeypatch.setattr(readiness_record, "SHIPPED_CATALOGUE", str(other))
    verdict = _fresh(project)
    assert not verdict.fresh and "catalogue" in verdict.reason
    monkeypatch.undo()

    # An implementation version changed.
    assert _fresh(project).fresh
    entry = readiness_registry.READINESS["codeowners-present"]
    monkeypatch.setitem(readiness_registry.READINESS, "codeowners-present",
                        readiness_registry.ReadinessImpl(entry.name, entry.function, "2.0.0"))
    verdict = _fresh(project)
    assert not verdict.fresh
    assert "codeowners-present" in verdict.reason and "2.0.0" in verdict.reason


def test_prc_8_record_freshness_age(tmp_path):
    project = support.make_project(tmp_path / "p", {"schema": 1})
    record = _written_record(project)
    measured = _utc(record["measured_at"])
    assert _fresh(project, now=measured + datetime.timedelta(days=7)).fresh
    verdict = _fresh(project, now=measured + datetime.timedelta(days=7, seconds=1))
    assert not verdict.fresh and "seven days" in verdict.reason
    verdict = _fresh(project, now=measured - datetime.timedelta(seconds=60))
    assert not verdict.fresh and "future" in verdict.reason


def test_prc_8_record_freshness_commits(tmp_path):
    project = support.make_project(tmp_path / "p", {"schema": 1})
    _written_record(project)
    for n in range(25):
        support.git(project, "commit", "-q", "--allow-empty", "-m", f"c{n}")
    assert _fresh(project).fresh
    support.git(project, "commit", "-q", "--allow-empty", "-m", "c25")
    verdict = _fresh(project)
    assert not verdict.fresh and "26 commits" in verdict.reason

    # A recorded commit the repository does not hold.
    from compass_pkg import readiness_record
    record = readiness_record.read(str(project)).record
    record["head"] = "0" * 40
    verdict = readiness_record.fresh(str(project), record)
    assert not verdict.fresh and "not in this repository" in verdict.reason


def test_prc_8_record_freshness_without_git_history(tmp_path):
    from compass_pkg import readiness_record
    project = tmp_path / "plain"
    (project / ".compass").mkdir(parents=True)
    (project / "compass.yml").write_text("schema: 1\n", encoding="utf-8")
    record = _written_record(project)
    assert record["head"] is None
    assert _fresh(project).fresh
    (project / "compass.yml").write_text("schema: 1\nautonomy: balanced\n", encoding="utf-8")
    assert not _fresh(project).fresh
    # No settings file at all: the path and digest are null and still compared.
    bare = tmp_path / "bare"
    (bare / ".compass").mkdir(parents=True)
    record = _written_record(bare)
    assert record["settings"] == {"path": None, "digest": None}
    assert _fresh(bare).fresh
    # A record with no commit, read where history now exists, is stale.
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=bare, check=True,
                   env=support.environment(bare))
    support.git(bare, "commit", "-q", "--allow-empty", "-m", "first")
    assert not _fresh(bare).fresh
    assert record["schema"] == 1 and readiness_record.RECORD == ".compass/readiness.yml"


def test_prc_8_record_missing_unreadable_summary_and_line(tmp_path):
    from compass_pkg import readiness_record
    project = support.make_project(tmp_path / "p", {"schema": 1})
    summary = readiness_record.summary(str(project))
    assert summary["status"] == "not-measured" and summary["reason"] == "missing"
    assert readiness_record.line(summary).startswith("Repository readiness: not measured (")
    assert "compass readiness" in readiness_record.line(summary)

    path = project / ".compass" / "readiness.yml"
    path.write_text("schema: [1\n", encoding="utf-8")
    summary = readiness_record.summary(str(project))
    assert (summary["status"], summary["reason"]) == ("not-measured", "unreadable")
    assert ".compass/readiness.yml" in summary["detail"]
    path.write_text("- a list\n", encoding="utf-8")
    assert readiness_record.summary(str(project))["reason"] == "unreadable"
    path.write_text("schema: 1\n", encoding="utf-8")
    path.chmod(0)
    try:
        assert readiness_record.summary(str(project))["reason"] == "unreadable"
    finally:
        path.chmod(0o644)

    signals = [_record_signal("agent-instructions-present", required=True,
                              impl="agent-instructions-present"),
               _record_signal("codeowners-present", "absent"),
               _record_signal("build-declared-and-succeeds", "absent", required=True,
                              impl="project-command-succeeds")]
    record = _written_record(project, signals)
    summary = readiness_record.summary(str(project))
    assert summary == {"status": "measured", "score": 1, "signals": 3, "floor_met": False,
                       "absent": ["codeowners-present", "build-declared-and-succeeds"],
                       "measured_at": record["measured_at"]}
    assert readiness_record.line(summary) == \
        "Repository readiness: 1 of 3 signals, floor not met"
    assert readiness_record.hook_line(str(project), "balanced") == ""
    warning = readiness_record.hook_line(str(project), "autonomous")
    assert "build-declared-and-succeeds" in warning and "floor" in warning
    _written_record(project, signals[:2])
    assert readiness_record.line(readiness_record.summary(str(project))) == \
        "Repository readiness: 1 of 2 signals, floor met"
    assert readiness_record.hook_line(str(project), "autonomous") == ""

    (project / "compass.yml").write_text("schema: 1\nautonomy: autonomous\n", encoding="utf-8")
    summary = readiness_record.summary(str(project))
    assert (summary["status"], summary["reason"]) == ("not-measured", "stale")
    assert readiness_record.line(summary) == (
        f"Repository readiness: not measured (record stale: {summary['detail']})")
    assert "compass readiness" in readiness_record.hook_line(str(project), "autonomous")


#: What the record module may import: it is read by the session-start hook,
#: so it must not load the policy, the checks or a command module.
RECORD_IMPORTS = {"compass_pkg.atomic_io", "compass_pkg.project_settings",
                  "compass_pkg.readiness_registry"}


def test_prc_8_record_module_imports_stay_small():
    import ast
    tree = ast.parse((ROOT / "cli/compass_pkg/readiness_record.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names.update(f"{base}.{alias.name}" if base == "compass_pkg" else base
                         for alias in node.names)
    compass = {name for name in names if name.startswith("compass_pkg")}
    assert compass == RECORD_IMPORTS
    others = {name.split(".")[0] for name in names - compass} - {"__future__", "yaml"}
    assert others <= set(sys.stdlib_module_names), others


def test_prc_8_record_matches_its_schema(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((ROOT / "schemas" / "readiness-record.schema.json")
                        .read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    marks, temp, env = _run_env(tmp_path)
    records = []
    for name, allow in (("measured", True), ("disabled", False)):
        project = _five_command_project(tmp_path / name, allow=allow,
                                        bodies={"lint_command": "exit 1"},
                                        files=_flaky_files())
        support.readiness(project, env=env)
        records.append(support.read_record(project))
    project = _prc_8_project(tmp_path / "p")
    support.readiness(project, env={BUDGET_ENV: "0.01"})
    records.append(support.read_record(project))
    for record in records:
        jsonschema.validate(record, schema)
    kinds = {s["not_run"] for r in records for s in r["signals"]}
    assert {None, "disabled", "undeclared"} <= kinds
    # The schema can fail: a result other than present or absent is refused.
    broken = copy.deepcopy(records[0])
    broken["signals"][0]["result"] = "unknown"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(broken, schema)


def _prc_8_project(tmp_path):
    """Three signals present (agent instructions, CODEOWNERS, lint), the other
    eight absent, every weight 1."""
    layer = {"schema": 1, "owner": "jed72", "allow_project_commands": True,
             "project": {"lint_command": "sh scripts/lint.sh"}, "readiness": ALL_WEIGHTS_ONE}
    files = {"AGENTS.md": "# Agents\n", "CODEOWNERS": "* @jed72\n", **_flaky_files()}
    return support.make_project(tmp_path, layer, files=files, scripts={"lint.sh": {}})


def test_prc_8(tmp_path):
    project = _prc_8_project(tmp_path / "p")
    code, out, err = support.readiness(project)
    assert code == 0, out + err
    lines = [line for line in out.splitlines()
             if line.split() and line.split()[0] in SHIPPED_SIGNALS]
    assert len(lines) == 11, out
    for line in lines:
        signal_id, result, *reason = line.split()
        assert result in ("present", "absent") and reason, line
    assert "3 of 11 signals" in out and "floor not met" in out
    for signal_id in ("build-declared-and-succeeds", "tests-declared-and-under-two-minutes"):
        assert signal_id in out.split("floor not met", 1)[1]

    record = support.read_record(project)
    present = sorted(s["id"] for s in record["signals"] if s["result"] == "present")
    assert present == ["agent-instructions-present", "codeowners-present",
                       "lint-declared-and-clean"]
    for entry in record["signals"]:
        assert entry["version"] and entry["reason"], entry
        assert entry["result"] in ("present", "absent")
    assert record["head"] == support.git(project, "rev-parse", "HEAD").strip()
    import hashlib
    digest = hashlib.sha256((project / "compass.yml").read_bytes()).hexdigest()
    assert record["settings"] == {"path": "compass.yml", "digest": f"sha256:{digest}"}
    assert _utc(record["measured_at"]) <= datetime.datetime.now(datetime.timezone.utc)
    assert "wrote .compass/readiness.yml" in out


def test_prc_9(tmp_path):
    project = _prc_8_project(tmp_path / "p")
    report = _json_run(project)
    record = support.read_record(project)
    for key in ("signals", "head", "settings", "measured_at", "catalogue_digest"):
        assert report[key] == record[key], key
    assert (report["score"], report["of"], report["floor_met"]) == (3, 11, False)
    assert sorted(report["below_floor"]) == ["build-declared-and-succeeds",
                                             "tests-declared-and-under-two-minutes"]
    assert report["path"] == ".compass/readiness.yml"
    (project / ".compass" / "readiness.yml").unlink()
    _json_run(project)
    assert support.read_record(project)["signals"] == record["signals"]


def _snapshot(project):
    return {str(p.relative_to(project)): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in Path(project).rglob("*") if p.is_file()}


def test_prc_12(tmp_path):
    project = _prc_8_project(tmp_path / "p")
    support.readiness(project)
    record = support.read_record(project)
    absent = [s for s in record["signals"] if s["result"] == "absent"]
    before = _snapshot(project)
    code, out, err = support.readiness(project, "--fix-list")
    assert code == 0, out + err
    items = [line.strip() for line in out.splitlines() if line.strip().startswith("- [ ] ")]
    assert len(items) == len(absent) == 8, out
    required = [s["id"] for s in absent if s["required_for_autonomous"]]
    assert [item.split()[3].rstrip(":") for item in items[:len(required)]] == required
    for entry in absent:
        item = next(i for i in items if f" {entry['id']}:" in i)
        assert entry["fix"]["change"] in item and f"({entry['fix']['file']})" in item, item
    assert _snapshot(project) == before

    # Weight orders the rest: the heaviest first.
    from compass_pkg import readiness_cmd
    ordered = readiness_cmd.fix_order([
        {"id": "a", "result": "absent", "weight": 1, "required_for_autonomous": False},
        {"id": "b", "result": "absent", "weight": 3, "required_for_autonomous": False},
        {"id": "c", "result": "absent", "weight": 1, "required_for_autonomous": True},
        {"id": "d", "result": "present", "weight": 9, "required_for_autonomous": False}])
    assert [s["id"] for s in ordered] == ["c", "b", "a"]

    # With no fresh record it says so, names the command and writes nothing.
    (project / "compass.yml").write_text(
        (project / "compass.yml").read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    before = _snapshot(project)
    code, out, err = support.readiness(project, "--fix-list")
    assert code == 0 and "- [ ]" not in out and "compass readiness" in out, out + err
    assert "stale" in out
    assert _snapshot(project) == before


def _signal_fixture(signal_id, present):
    """`(settings, files)` that make one shipped signal present or absent."""
    settings, files = {"schema": 1, "allow_project_commands": True, "project": {}}, {}
    keys = {v: k for k, v in COMMAND_SIGNALS.items()}
    if signal_id in keys:
        files["scripts/run.sh"] = "#!/bin/sh\nsleep 1\nexit 0\n" if present else \
            "#!/bin/sh\nexit 1\n"
        settings["project"][keys[signal_id]] = "sh scripts/run.sh"
    elif signal_id in ("secret-scan-declared", "structured-logging-declared"):
        if present:
            key = signal_id.replace("-declared", "").replace("-", "_")
            settings["project"][key] = "declared"
    elif present:
        files.update({"agent-instructions-present": {"CLAUDE.md": "# Agents\n"},
                      "codeowners-present": {".github/CODEOWNERS": "* @owner\n"},
                      "pre-commit-hooks-present": {".pre-commit-config.yaml": "repos: []\n"},
                      "no-flaky-tests-on-record": {}}[signal_id])
    elif signal_id == "no-flaky-tests-on-record":
        files.update(_flaky_files())
    return settings, files


def test_prc_4(tmp_path):
    times = {}
    for signal_id in SHIPPED_SIGNALS:
        for present in (True, False):
            settings, files = _signal_fixture(signal_id, present)
            project = support.make_project(
                tmp_path / f"{signal_id}-{present}", settings, files=files)
            started = time.monotonic()
            report = _json_run(project, env={BUDGET_ENV: ""})
            elapsed = time.monotonic() - started
            assert report["budget"]["commands_seconds"] == 270
            entry = support.signal(report, signal_id)
            assert entry["result"] == ("present" if present else "absent"), entry
            assert elapsed <= 300, (signal_id, present, elapsed)
            times[(signal_id, present)] = round(elapsed, 2)
    for (signal_id, present), seconds in sorted(times.items()):
        print(f"PRC-4 {signal_id} {'present' if present else 'absent'} {seconds}s")


def _json_run(project, env=None):
    code, out, err = support.readiness(project, "--json", env=env)
    assert code == 0, out + err
    return json.loads(out)


def test_prc_2(tmp_path):
    project = support.make_project(tmp_path / "p", {
        "schema": 1, "allow_project_commands": True,
        "project": {"test_command": "sh scripts/tests.sh"}}, scripts={"tests.sh": {}})
    report = _json_run(project)
    for key in ("lint_command", "format_check_command", "build_command", "typecheck_command"):
        entry = support.signal(report, COMMAND_SIGNALS[key])
        assert entry["result"] == "absent", entry
        assert f"project.{key}" in entry["reason"] and "compass.yml" in entry["reason"]
        assert entry["not_run"] == "undeclared"
    assert support.signal(report, "tests-declared-and-under-two-minutes")["result"] == "present"
    assert {entry["result"] for entry in report["signals"]} <= {"present", "absent"}
    assert len(report["signals"]) == 11


FOUR_COMMANDS = ("lint_command", "format_check_command", "build_command", "typecheck_command")


def test_prc_1(tmp_path):
    project_keys = {key: f"sh scripts/{key}.sh" for key in FOUR_COMMANDS}
    scripts = {f"{key}.sh": {} for key in FOUR_COMMANDS}
    project = support.make_project(tmp_path / "new", {
        "schema": 1, "allow_project_commands": True, "project": project_keys}, scripts=scripts)
    report = _json_run(project)
    for key in FOUR_COMMANDS:
        entry = support.signal(report, COMMAND_SIGNALS[key])
        assert (entry["result"], entry["key"], entry["command"]) == \
            ("present", key, project_keys[key]), entry

    # The same keys in the old settings file, in a project with no compass.yml.
    old = support.make_project(tmp_path / "old", None, files={
        ".compass/config.yml": yaml.safe_dump({"allow_project_commands": True,
                                               "project": project_keys})}, scripts=scripts)
    old_report = _json_run(old)
    for key in FOUR_COMMANDS:
        assert support.signal(old_report, COMMAND_SIGNALS[key]) == \
            support.signal(report, COMMAND_SIGNALS[key])
    assert old_report["settings"]["path"] == ".compass/config.yml"

    # A value that is not a string is refused, naming the key and the file.
    for place, key in (("new", "build_command"), ("old", "typecheck_command")):
        folder = tmp_path / f"bad-{place}"
        settings = {"allow_project_commands": True, "project": {**project_keys, key: 3}}
        if place == "new":
            bad = support.make_project(folder, {"schema": 1, **settings})
            named = "compass.yml"
        else:
            bad = support.make_project(folder, None, files={
                ".compass/config.yml": yaml.safe_dump(settings)})
            named = ".compass/config.yml"
        code, out, err = support.readiness(bad)
        assert code == 2, out + err
        assert f"project.{key}" in err and named in err
        assert not (bad / ".compass" / "readiness.yml").exists()


def _five_command_project(folder, allow, bodies=None, extra=None, files=None):
    """A fixture project declaring all five project commands as marker
    scripts. `bodies` maps a key to the script body (default: exit 0)."""
    folder.mkdir(parents=True, exist_ok=True)
    keys = {}
    for key in COMMAND_SIGNALS:
        keys[key] = support.marker_script(folder, f"{key}.sh", (bodies or {}).get(key, "exit 0"))
    settings = {"schema": 1, "project": keys, **(extra or {})}
    if allow:
        settings["allow_project_commands"] = True
    return support.make_project(folder, settings, files={"AGENTS.md": "# Agents\n",
                                                         **(files or {})})


def _run_env(tmp_path):
    """Marker and temp folders outside the project, and the environment that
    names them."""
    marks, temp = tmp_path / "markers", tmp_path / "temp"
    marks.mkdir(exist_ok=True)
    temp.mkdir(exist_ok=True)
    return marks, temp, {"READINESS_MARKERS": str(marks), "TMPDIR": str(temp)}


def test_prc_18(tmp_path):
    marks, temp, env = _run_env(tmp_path)
    project = _five_command_project(tmp_path / "p", allow=False)
    before = support.worktrees(project)
    report = _json_run(project, env=env)
    for key, signal_id in COMMAND_SIGNALS.items():
        entry = support.signal(report, signal_id)
        assert entry["result"] == "absent" and entry["not_run"] == "disabled", entry
        assert entry["reason"].startswith("not run: project commands are disabled")
        assert "allow_project_commands" in entry["reason"]
    assert support.markers(marks) == {}
    assert support.worktrees(project) == before
    assert list(temp.iterdir()) == []
    assert support.signal(report, "agent-instructions-present")["result"] == "present"


def _fork_payload(tmp_path):
    """A GitHub Actions pull request from a fork, with the payload outside
    the checkout, where the runner writes it."""
    runner = tmp_path / "runner"
    runner.mkdir(exist_ok=True)
    payload = runner / "event.json"
    payload.write_text(json.dumps({"pull_request": {
        "head": {"repo": {"full_name": "outsider/fixture", "fork": True}},
        "base": {"repo": {"full_name": "owner/fixture"}}}}), encoding="utf-8")
    return {"GITHUB_ACTIONS": "true", "CI": "true", "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_EVENT_PATH": str(payload), "GITHUB_REPOSITORY": "owner/fixture"}


def test_prc_19(tmp_path):
    marks, temp, env = _run_env(tmp_path)
    project = _five_command_project(tmp_path / "p", allow=True)
    for untrusted in ({"COMPASS_CONTRIBUTION_TRUST": "untrusted"}, _fork_payload(tmp_path)):
        code, out, err = support.readiness(project, env={**env, **untrusted})
        assert code == 0, out + err
        assert "allow_project_commands was not read" in out
        record = support.read_record(project)
        for signal_id in COMMAND_SIGNALS.values():
            entry = support.signal(record, signal_id)
            assert entry["result"] == "absent" and entry["not_run"] == "untrusted", entry
            assert "untrusted" in entry["reason"] or "fork" in entry["reason"], entry
        assert support.markers(marks) == {}
        assert list(temp.iterdir()) == []
    # The same project on a laptop runs them.
    report = _json_run(project, env=env)
    assert support.signal(report, "build-declared-and-succeeds")["result"] == "present"
    assert sorted(support.markers(marks)) == sorted(f"{key}.sh" for key in COMMAND_SIGNALS)


#: The tools a signal could use to reach outside the repository.
NETWORK_TOOLS = ("gh", "curl", "wget", "ssh", "git-remote-http", "git-remote-https",
                 "git-remote-ftp", "git-remote-ftps")


def _network_stubs(tmp_path):
    """A folder of stubs that record any call and fail, and a call log."""
    stubs, calls = tmp_path / "stubs", tmp_path / "calls.log"
    stubs.mkdir()
    for name in NETWORK_TOOLS:
        path = stubs / name
        path.write_text(f'#!/bin/sh\necho "{name} $*" >> "{calls}"\nexit 1\n', encoding="utf-8")
        path.chmod(0o755)
    return {"PATH": f"{stubs}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}"}, calls


def test_prc_6(tmp_path):
    path_env, calls = _network_stubs(tmp_path)
    declared = {"schema": 1, "project": {"secret_scan": "gitleaks in pre-commit",
                                         "structured_logging": "JSON lines to stdout"}}
    project = support.make_project(tmp_path / "p", declared, files={
        "AGENTS.md": "# Agents\n", "CODEOWNERS": "* @owner\n",
        ".pre-commit-config.yaml": "repos: []\n"})
    code, out, err = support.readiness(project, env=path_env)
    assert code == 0, out + err
    record = support.read_record(project)
    for signal_id in ("secret-scan-declared", "structured-logging-declared"):
        assert support.signal(record, signal_id)["result"] == "present"
    assert not calls.exists(), calls.read_text(encoding="utf-8")

    bare = support.make_project(tmp_path / "bare", {"schema": 1})
    support.readiness(bare, env=path_env)
    record = support.read_record(bare)
    for signal_id, key in (("secret-scan-declared", "secret_scan"),
                           ("structured-logging-declared", "structured_logging")):
        entry = support.signal(record, signal_id)
        assert entry["result"] == "absent" and f"project.{key}" in entry["reason"]
    assert not calls.exists()

    wrong = support.make_project(tmp_path / "wrong", {
        "schema": 1, "project": {"secret_scan": True}})
    code, out, err = support.readiness(wrong, env=path_env)
    assert code == 2 and "project.secret_scan" in err and "compass.yml" in err, out + err
    assert not (wrong / ".compass" / "readiness.yml").exists()


def _flaky_signal(tmp_path, name, files):
    project = support.make_project(tmp_path / name, {"schema": 1}, files=files)
    return support.signal(_json_run(project), "no-flaky-tests-on-record")


def test_prc_17(tmp_path):
    entry = _flaky_signal(tmp_path, "disagree", _flaky_files("issue-a", "SCN-4"))
    assert entry["result"] == "absent", entry
    assert "issue-a" in entry["reason"] and "SCN-4" in entry["reason"]

    folder = ".compass/work/issue-b/evidence"
    green = {"scenario": "SCN-1", "passed": True, "exit_code": 0,
             "timestamp": "2026-10-01T10:00:00Z"}
    agree = {f"{folder}/green-SCN-1.json": json.dumps(green),
             f"{folder}/green-SCN-1-2.json": json.dumps(
                 {**green, "timestamp": "2026-10-02T10:00:00Z"}),
             f"{folder}/green-SCN-2.json": json.dumps({**green, "scenario": "SCN-2"})}
    assert _flaky_signal(tmp_path, "agree", agree)["result"] == "present"
    assert _flaky_signal(tmp_path, "none", {})["result"] == "present"

    rerun = {f"{folder}/green-SCN-3.json": json.dumps(
        {**green, "scenario": "SCN-3", "attempts": 2, "rerun_without_change": True})}
    entry = _flaky_signal(tmp_path, "rerun", rerun)
    assert entry["result"] == "absent", entry
    assert "issue-b" in entry["reason"] and "SCN-3" in entry["reason"]
    # A re-run after a change is not a flaky test.
    changed = {f"{folder}/green-SCN-3.json": json.dumps(
        {**green, "scenario": "SCN-3", "attempts": 2, "rerun_without_change": False})}
    assert _flaky_signal(tmp_path, "changed", changed)["result"] == "present"


def _build_project(folder, body, files=None):
    folder.mkdir(parents=True, exist_ok=True)
    command = support.marker_script(folder, "build.sh", body)
    return support.make_project(folder, {"schema": 1, "allow_project_commands": True,
                                         "project": {"build_command": command}}, files=files)


def test_prc_13(tmp_path):
    project = _build_project(tmp_path / "p", "exit 1")
    (project / "scripts" / "build.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    entry = support.signal(_json_run(project), "build-declared-and-succeeds")
    assert entry["result"] == "absent" and "exited 1" in entry["reason"], entry
    assert "clean checkout of HEAD" in entry["reason"]
    support.git(project, "commit", "-q", "-am", "fix the build")
    entry = support.signal(_json_run(project), "build-declared-and-succeeds")
    assert entry["result"] == "present", entry

    needs_env = _build_project(tmp_path / "env", "[ -f .env ] || exit 3\nexit 0",
                               files={".gitignore": ".env\n.compass/\n"})
    (needs_env / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    entry = support.signal(_json_run(needs_env), "build-declared-and-succeeds")
    assert entry["result"] == "absent" and "exited 3" in entry["reason"], entry
    assert "no ignored or uncommitted file" in entry["reason"]


def test_prc_13_no_commit_to_check_out(tmp_path):
    """Without a commit there is no clean checkout of HEAD, so each declared
    command is absent, named as not run, and the run still writes a record."""
    project = tmp_path / "p"
    (project / ".compass").mkdir(parents=True)
    (project / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    (project / "compass.yml").write_text(yaml.safe_dump({
        "schema": 1, "allow_project_commands": True,
        "project": {"build_command": "true"}}), encoding="utf-8")
    for name, init in (("no-git", False), ("no-commit", True)):
        if init:
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True,
                           env=support.environment(project))
        code, out, err = support.readiness(project, "--json")
        assert code == 0, (name, out + err)
        entry = support.signal(json.loads(out), "build-declared-and-succeeds")
        assert entry["result"] == "absent" and entry["not_run"] == "no-checkout", entry
        assert "no commit" in entry["reason"], entry
        assert support.signal(json.loads(out), "agent-instructions-present")["result"] == \
            "present"


def _status(project):
    return support.git(project, "status", "--porcelain", "--untracked-files=all").splitlines()


def test_prc_10(tmp_path):
    marks, temp, env = _run_env(tmp_path)
    project = _five_command_project(tmp_path / "p", allow=True)
    assert _status(project) == []
    report = _json_run(project, env=env)
    assert all(support.signal(report, s)["result"] == "present"
               for s in COMMAND_SIGNALS.values())
    assert support.git(project, "diff", "--stat", "HEAD") == ""
    assert _status(project) == ["?? .compass/readiness.yml"]


def test_prc_43(tmp_path):
    marks, temp, env = _run_env(tmp_path)
    bodies = {"format_check_command": "echo rewritten > AGENTS.md\nexit 0",
              "test_command": "mkdir -p snapshots && echo snap > snapshots/new.txt\nexit 0"}
    project = _five_command_project(tmp_path / "p", allow=True, bodies=bodies)
    report = _json_run(project, env=env)
    for signal_id in ("format-declared-and-clean", "tests-declared-and-under-two-minutes"):
        assert support.signal(report, signal_id)["result"] == "present"
    assert support.git(project, "diff", "--stat", "HEAD") == ""
    assert _status(project) == ["?? .compass/readiness.yml"]
    assert (project / "AGENTS.md").read_text(encoding="utf-8") == "# Agents\n"


def test_prc_14(tmp_path):
    folder = tmp_path / "p"
    folder.mkdir()
    command = support.marker_script(folder, "tests.sh", "sleep 3\nexit 0")
    green = {"scenario": "SCN-1", "passed": True, "exit_code": 0,
             "timestamp": "2026-10-01T10:00:00Z"}
    green_path = ".compass/work/issue-a/evidence/green-SCN-1.json"
    project = support.make_project(folder, {
        "schema": 1, "allow_project_commands": True, "project": {"test_command": command}},
        files={green_path: json.dumps(green)})
    before = (project / green_path).read_bytes()
    _json_run(project)
    entry = support.signal(support.read_record(project),
                           "tests-declared-and-under-two-minutes")
    assert entry["result"] == "present", entry
    assert (entry["key"], entry["command"]) == ("test_command", command)
    assert entry["duration_seconds"] >= 3
    assert (project / green_path).read_bytes() == before


def _tests_project(folder, body, extra=None):
    folder.mkdir(parents=True, exist_ok=True)
    command = support.marker_script(folder, "tests.sh", body)
    return support.make_project(folder, {"schema": 1, "allow_project_commands": True,
                                         "project": {"test_command": command, **(extra or {})}})


def test_prc_15(tmp_path):
    project = _tests_project(tmp_path / "slow", "sleep 150\nexit 0")
    started = time.monotonic()
    entry = support.signal(_json_run(project), "tests-declared-and-under-two-minutes")
    elapsed = time.monotonic() - started
    assert entry["result"] == "absent" and entry["reason"] == "over two minutes", entry
    assert 120 <= entry["duration_seconds"] < 130, entry
    assert 120 <= elapsed < 145, elapsed

    failing = _tests_project(tmp_path / "failing", "sleep 2\nexit 1")
    entry = support.signal(_json_run(failing), "tests-declared-and-under-two-minutes")
    assert entry["result"] == "absent" and "exited 1" in entry["reason"], entry


def _wait_for(path, seconds=60):
    deadline = time.monotonic() + seconds
    while not Path(path).exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    return Path(path).exists()


def test_prc_42(tmp_path):
    marks, temp, env = _run_env(tmp_path)
    pids = tmp_path / "pids"
    pids.mkdir()
    folder = tmp_path / "p"
    folder.mkdir()
    # The build records the worktrees Git lists while it runs, and sleeps
    # while the test holds the slow flag, so the test can kill the run.
    body = (f'git worktree list --porcelain > "{pids}/during-$$"\n'
            f'if [ -f "{pids}/slow" ]; then echo $$ > "{pids}/build"; sleep 600; fi\nexit 0')
    command = support.marker_script(folder, "build.sh", body)
    subtasks = tmp_path / "subtask-worktrees"
    project = support.make_project(folder, {
        "schema": 1, "allow_project_commands": True, "project": {"build_command": command},
        "multiagent": {"worktree_root": str(subtasks), "max_worktrees": 1}})
    support.git(project, "worktree", "add", "-q", "--detach", str(subtasks / "s1"), "HEAD")
    before = support.worktrees(project)
    assert len(before) == 2

    entry = support.signal(_json_run(project, env=env), "build-declared-and-succeeds")
    assert entry["result"] == "present", entry
    where = support.markers(marks)["build.sh"][0][1]
    assert os.path.realpath(where).startswith(os.path.realpath(temp) + os.sep), where
    assert not os.path.realpath(where).startswith(os.path.realpath(subtasks))
    assert support.worktrees(project) == before

    # A run killed with SIGKILL while the build runs leaves its worktree.
    (pids / "slow").write_text("", encoding="utf-8")
    run = subprocess.Popen([sys.executable, str(support.CLI), "readiness"], cwd=project,
                           env=support.environment(project, env),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    live = None
    try:
        assert _wait_for(pids / "build"), "the build did not start"
        os.kill(run.pid, 9)
        run.wait(timeout=30)
        build = int((pids / "build").read_text(encoding="utf-8"))
        os.killpg(os.getpgid(build), 9)
        left = sorted(set(support.worktrees(project)) - set(before))
        assert len(left) == 1 and f"compass-readiness-{run.pid}-" in left[0], left

        # A second run still going on, here this test's own process, keeps
        # its worktree.
        live = temp / f"compass-readiness-{os.getpid()}-live"
        support.git(project, "worktree", "add", "-q", "--detach", str(live), "HEAD")
        (pids / "slow").unlink()
        for path in pids.glob("during-*"):
            path.unlink()
        entry = support.signal(_json_run(project, env=env), "build-declared-and-succeeds")
        assert entry["result"] == "present", entry
        during = next(pids.glob("during-*")).read_text(encoding="utf-8")
        assert left[0] not in during and os.path.basename(left[0]) not in during
        assert support.worktrees(project) == sorted(before + [os.path.realpath(live)])
    finally:
        if run.poll() is None:
            os.kill(run.pid, 9)
        if (pids / "build").exists():
            try:
                os.killpg(os.getpgid(int((pids / "build").read_text(encoding="utf-8"))), 9)
            except (ProcessLookupError, PermissionError):
                pass
        if live is not None and live.exists():
            support.git(project, "worktree", "remove", "--force", str(live))
    assert support.worktrees(project) == before


BUDGET_ENV = "COMPASS_READINESS_BUDGET_SECONDS"


def test_prc_41_help_states_the_budget_order_and_clean_checkout(tmp_path):
    project = support.make_project(tmp_path / "p", {"schema": 1})
    code, out, err = support.readiness(project, "--help")
    assert code == 0, out + err
    text = " ".join(out.split())
    for words in ("300 seconds", "270 seconds", "build, then tests, then lint",
                  "two minutes", "clean checkout of HEAD", "allow_project_commands",
                  "--fix-list", "exits 0"):
        assert words in text, words


MICRO_LAYER = {"tests-declared-and-under-two-minutes": {
    "set": {"params": {"command": "test_micro_command"}}}}


def test_prc_16(tmp_path):
    def project(name, layer):
        folder = tmp_path / name
        folder.mkdir()
        slow = support.marker_script(folder, "tests.sh", "sleep 150\nexit 0")
        micro = support.marker_script(folder, "micro.sh", "sleep 2\nexit 0")
        settings = {"schema": 1, "owner": "jed72", "allow_project_commands": True,
                    "project": {"test_command": slow, "test_micro_command": micro}}
        if layer:
            settings["readiness"] = MICRO_LAYER
        return support.make_project(folder, settings), micro, slow

    layered, micro, _ = project("layered", True)
    entry = support.signal(_json_run(layered), "tests-declared-and-under-two-minutes")
    assert entry["result"] == "present", entry
    assert (entry["key"], entry["command"]) == ("test_micro_command", micro)

    # Without the layer the signal times test_command, even with
    # test_micro_command declared. A low budget stops it early.
    plain, _, slow = project("plain", False)
    entry = support.signal(_json_run(plain, env={BUDGET_ENV: "5"}),
                           "tests-declared-and-under-two-minutes")
    assert (entry["key"], entry["command"]) == ("test_command", slow)
    assert entry["result"] == "absent"


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _gone_within(pid, seconds):
    deadline = time.monotonic() + seconds
    while _alive(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    return not _alive(pid)


def test_prc_11(tmp_path):
    marks, temp, env = _run_env(tmp_path)
    pids = tmp_path / "pids"
    pids.mkdir()
    body = (f'sleep 300 &\necho $! > "{pids}/child"\necho $$ > "{pids}/shell"\n'
            "sleep 300\nexit 0")
    project = _build_project(tmp_path / "p", body, files={"AGENTS.md": "# Agents\n"})
    started = time.monotonic()
    try:
        code, out, err = support.readiness(project, env={**env, BUDGET_ENV: "5"})
        elapsed = time.monotonic() - started
        child = int((pids / "child").read_text(encoding="utf-8"))
        shell = int((pids / "shell").read_text(encoding="utf-8"))
        assert code == 0, out + err
        assert elapsed < 5 + 30, elapsed
        # The build and the process it started are both stopped.
        assert _gone_within(shell, 5), "the build's shell is still running"
        assert _gone_within(child, 5), "the build's child process is still running"
    finally:
        # Stop only what this test's fixture started: the build's process
        # group, found from the ids it recorded, and the child by its id.
        for name in ("shell", "child"):
            if (pids / name).exists():
                pid = int((pids / name).read_text(encoding="utf-8"))
                if _alive(pid):
                    try:
                        os.killpg(os.getpgid(pid), 9)
                    except (ProcessLookupError, PermissionError):
                        pass
    record = support.read_record(project)
    entry = support.signal(record, "build-declared-and-succeeds")
    assert entry["result"] == "absent" and entry["reason"] == "ran over the time limit", entry
    assert "stopped at the time limit: build-declared-and-succeeds" in out
    assert support.signal(record, "agent-instructions-present")["result"] == "present"
    assert record["budget"]["commands_seconds"] == 5


def test_prc_41(tmp_path):
    marks, temp, env = _run_env(tmp_path)
    bodies = {"build_command": "sleep 2\nexit 0", "test_command": "sleep 2\nexit 0",
              "lint_command": "sleep 60\nexit 0", "typecheck_command": "sleep 1\nexit 0",
              "format_check_command": "sleep 1\nexit 0"}
    project = _five_command_project(tmp_path / "p", allow=True, bodies=bodies)
    started = time.monotonic()
    code, out, err = support.readiness(project, env={**env, BUDGET_ENV: "12"})
    elapsed = time.monotonic() - started
    assert code == 0, out + err
    ran = support.markers(marks)
    assert sorted(ran) == ["build_command.sh", "lint_command.sh", "test_command.sh"], ran
    starts = [ran[name][0][0] for name in ("build_command.sh", "test_command.sh",
                                           "lint_command.sh")]
    assert starts == sorted(starts), starts
    record = support.read_record(project)
    result = {s: support.signal(record, s) for s in COMMAND_SIGNALS.values()}
    assert result["build-declared-and-succeeds"]["result"] == "present"
    assert result["tests-declared-and-under-two-minutes"]["result"] == "present"
    assert result["lint-declared-and-clean"]["reason"] == "ran over the time limit"
    for signal_id in ("typecheck-declared-and-clean", "format-declared-and-clean"):
        assert result[signal_id]["result"] == "absent"
        assert result[signal_id]["reason"] == "not run: the time limit was reached"
        assert result[signal_id]["not_run"] == "budget"
    assert elapsed <= 12 + 30, elapsed

    # The variable only lowers the budget; a value that is not a positive
    # number is ignored with a warning.
    from compass_pkg import readiness_run
    warnings = []
    for raw, expected in (("12", 12), ("9999", 270), ("abc", 270), ("-3", 270), ("", 270)):
        assert readiness_run.command_budget({BUDGET_ENV: raw}, warnings.append) == expected
    assert readiness_run.command_budget({}) == 270
    assert len(warnings) == 2 and all(BUDGET_ENV in w for w in warnings)



# --- U3 the floor ---

FLOOR_SLUG = "floor-issue"
FLOOR_MANIFEST = {
    "schema_version": "2.0", "issue": FLOOR_SLUG, "created": "2026-10-13",
    "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                   "size": "medium", "goal": "delivery", "role": "engineer", "labels": []},
    "evidence": [],
}
HOOK = Path("hooks") / "session-start.sh"
UPGRADE_GUIDE = ROOT / "docs" / "upgrade-7-0-0.md"
#: The text the session-start hook adds from the readiness record.
READINESS_LINE = "Repository readiness"


def _floor_issue(project, slug=FLOOR_SLUG):
    """An assessed issue with no generation yet. Not committed: an issue's
    work folder is never what HEAD measures."""
    task_dir = Path(project) / ".compass" / "work" / slug
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "manifest.yml").write_text(
        yaml.safe_dump(dict(FLOOR_MANIFEST, issue=slug), sort_keys=False), encoding="utf-8")
    return task_dir


def _floor_project(folder, autonomy="autonomous", extra=None, files=None):
    """A fixture project with `autonomy` set (left out when None) and one
    assessed issue."""
    settings = {"schema": 1, **({"autonomy": autonomy} if autonomy else {}), **(extra or {})}
    project = support.make_project(folder, settings, files=files)
    _floor_issue(project)
    return project


def _catalogue_signals(absent=()):
    """Every shipped signal, as a record holds it: present unless named in
    `absent`, and an absent one carries the change that makes it present."""
    catalogue = yaml.safe_load((PRESET / "readiness.yml").read_text(encoding="utf-8"))
    signals = []
    for signal_id, entry in catalogue["readiness"].items():
        result = "absent" if signal_id in absent else "present"
        signal = _record_signal(signal_id, result,
                                required=bool(entry.get("required_for_autonomous")),
                                impl=entry["impl"], weight=entry["weight"])
        if result == "absent":
            signal["fix"] = {"change": f"make {signal_id} present", "file": "compass.yml"}
        signals.append(signal)
    return signals


def _floor_record(project, absent=(), measured_at=None):
    """A fresh record for the fixture project, written through the record module."""
    return _written_record(project, _catalogue_signals(absent), measured_at=measured_at)


def _evaluate_write(project, env=None, slug=FLOOR_SLUG):
    return support.run_compass(project, "approach", "evaluate", "--write", "--issue", slug,
                               env=env)


def _task_dir(project, slug=FLOOR_SLUG):
    return Path(project) / ".compass" / "work" / slug


def _floor_manifest(project, slug=FLOOR_SLUG):
    return yaml.safe_load((_task_dir(project, slug) / "manifest.yml").read_text(encoding="utf-8"))


def _generations(project, slug=FLOOR_SLUG):
    folder = _task_dir(project, slug) / "generations"
    return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []


def _manifest_before(project):
    return (_task_dir(project) / "manifest.yml").read_text(encoding="utf-8")


def _assert_refused_unwritten(project, before, code, out, err):
    """Exit 2, nothing printed before the refusal, no generation, the
    manifest byte for byte as it was."""
    assert code == 2, out + err
    assert "wrote the delivery approach" not in out and "Approach:" not in out, out
    assert _generations(project) == []
    assert _manifest_before(project) == before


def test_prc_20(tmp_path):
    project = _floor_project(tmp_path / "p")
    absent = ("lint-declared-and-clean", "tests-declared-and-under-two-minutes")
    _floor_record(project, absent=absent)
    before = _manifest_before(project)
    code, out, err = _evaluate_write(project)
    _assert_refused_unwritten(project, before, code, out, err)
    for signal_id in absent:
        assert signal_id in err, err
        assert f"make {signal_id} present" in err, err
    assert "autonomy" in err and "balanced" in err and "controlled" in err, err
    assert "never refused" in err, err
    # Without --write nothing is refused: the default view says what --write
    # would do, and --json carries the summary.
    code, out, err = support.run_compass(project, "approach", "evaluate", "--issue", FLOOR_SLUG)
    assert code == 0, out + err
    assert "evaluate --write would be refused" in out, out
    code, out, err = support.run_compass(project, "approach", "evaluate", "--json", "--issue",
                                         FLOOR_SLUG)
    assert code == 0, out + err
    readiness = json.loads(out)["readiness"]
    assert readiness["status"] == "measured" and readiness["floor_met"] is False, readiness
    assert readiness["would_refuse"], readiness
    assert _generations(project) == []


def test_prc_21(tmp_path):
    project = _floor_project(tmp_path / "p")
    _floor_record(project, absent=("codeowners-present", "secret-scan-declared",
                                    "pre-commit-hooks-present"))
    code, out, err = support.run_compass(project, "approach", "evaluate", "--json", "--issue",
                                         FLOOR_SLUG)
    assert code == 0, out + err
    expected = json.loads(out)
    code, out, err = _evaluate_write(project)
    assert code == 0, out + err
    manifest = _floor_manifest(project)
    assert manifest["delivery_approach"] == expected["delivery_approach"]
    assert [g["id"] for g in manifest["gates"]] == expected["gates"]
    assert manifest["checkpoints"] == expected["checkpoints"]
    assert manifest["stages"] == expected["stages"]
    assert _generations(project) == ["1"]


def _stale_settings(project):
    """Change compass.yml after the record was written."""
    path = Path(project) / "compass.yml"
    path.write_text(path.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")


def _unreadable_record(project):
    (Path(project) / support.RECORD).write_text("signals: [unclosed\n", encoding="utf-8")


def test_prc_22(tmp_path):
    states = {
        "all-four-absent": lambda p: _floor_record(p, absent=REQUIRED_SIGNALS),
        "missing": lambda p: None,
        "stale": lambda p: (_floor_record(p), _stale_settings(p)),
        "unreadable": _unreadable_record,
    }
    for autonomy in ("balanced", "controlled"):
        for name, make_state in states.items():
            project = _floor_project(tmp_path / f"{autonomy}-{name}", autonomy=autonomy)
            make_state(project)
            code, out, err = _evaluate_write(project)
            assert code == 0, (autonomy, name, out + err)
            assert (_task_dir(project) / "generations" / "1" / "complete").is_file(), (
                autonomy, name)


def _marker_commands_project(folder, autonomy="autonomous"):
    """A fixture on `autonomy` whose five project commands leave markers when
    they run, with project commands allowed, and one assessed issue."""
    project = _five_command_project(folder, allow=True, extra={"autonomy": autonomy})
    _floor_issue(project)
    return project


def test_prc_23(tmp_path):
    marks, temp, env = _run_env(tmp_path)
    source = _marker_commands_project(tmp_path / "source")
    _floor_record(source)
    # A fresh clone: the record is per checkout, so the clone has none.
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(source), str(clone)], check=True,
                   env=support.environment(tmp_path), capture_output=True)
    (clone / ".compass").mkdir(exist_ok=True)
    _floor_issue(clone)
    assert not (clone / support.RECORD).exists()
    before = _manifest_before(clone)
    code, out, err = _evaluate_write(clone, env=env)
    _assert_refused_unwritten(clone, before, code, out, err)
    assert "not measured in this checkout" in err, err
    assert "per checkout" in err and "not committed" in err, err
    assert "compass readiness" in err, err
    assert "CI job" in err and "before assess" in err, err
    assert "autonomy" in err, err
    # evaluate --write runs no signal: no project command ran, no record.
    assert support.markers(marks) == {}
    assert not (clone / support.RECORD).exists()


def test_prc_24(tmp_path):
    project = _floor_project(tmp_path / "p")
    _floor_record(project)
    _stale_settings(project)
    before = _manifest_before(project)
    code, out, err = _evaluate_write(project)
    _assert_refused_unwritten(project, before, code, out, err)
    assert "stale" in err and "compass.yml changed" in err, err
    # The settings digest matches again, but one signal's version is not the
    # shipped one.
    support.git(project, "commit", "-q", "-am", "settings change")
    from compass_pkg import readiness_record
    record = _floor_record(project)
    record["signals"][-1]["version"] = "0.0.1"
    readiness_record.write(str(project), record)
    code, out, err = _evaluate_write(project)
    _assert_refused_unwritten(project, before, code, out, err)
    assert "stale" in err and record["signals"][-1]["id"] in err, err
    # One new commit that changes neither leaves the record fresh.
    _floor_record(project)
    (Path(project) / "notes.txt").write_text("one more commit\n", encoding="utf-8")
    support.git(project, "add", "notes.txt")
    support.git(project, "commit", "-q", "-m", "one more")
    code, out, err = _evaluate_write(project)
    assert code == 0, out + err


def _days_ago(days):
    from compass_pkg import readiness_record
    return readiness_record.now_utc() - datetime.timedelta(days=days)


def _empty_commits(project, count):
    for n in range(count):
        support.git(project, "commit", "-q", "--allow-empty", "-m", f"empty {n}")


def _stale_records(project):
    """Write each stale record PRC-40 names in turn, yielding the words its
    reason must hold. The project ends 26 commits past its first commit."""
    from compass_pkg import readiness_record
    first = support.git(project, "rev-parse", "HEAD").strip()
    _floor_record(project, measured_at=_days_ago(8))
    yield "older than seven days"
    _empty_commits(project, 26)
    record = _floor_record(project, measured_at=_days_ago(6))
    record["head"] = first
    readiness_record.write(str(project), record)
    yield "26 commits"
    record["head"] = "0123456789abcdef0123456789abcdef01234567"
    readiness_record.write(str(project), record)
    yield "unknown"


def test_prc_40(tmp_path):
    project = _floor_project(tmp_path / "p")
    before = _manifest_before(project)
    for expected in _stale_records(project):
        code, out, err = _evaluate_write(project)
        _assert_refused_unwritten(project, before, code, out, err)
        assert expected in err, (expected, err)
    # 25 commits past the recorded commit is still fresh.
    from compass_pkg import readiness_record
    record = _floor_record(project, measured_at=_days_ago(6))
    record["head"] = support.git(project, "rev-parse", "HEAD~25").strip()
    readiness_record.write(str(project), record)
    code, out, err = _evaluate_write(project)
    assert code == 0, out + err
    # On balanced each stale record runs, recorded as not measured.
    balanced = _floor_project(tmp_path / "b", autonomy="balanced")
    for expected in _stale_records(balanced):
        code, out, err = _evaluate_write(balanced)
        assert code == 0, (expected, out + err)
        readiness = _floor_manifest(balanced)["readiness"]
        assert readiness["status"] == "not-measured" and readiness["reason"] == "stale", (
            expected, readiness)
        assert expected in readiness["detail"], (expected, readiness)


def test_prc_39(tmp_path):
    marks, temp, env = _run_env(tmp_path)
    project = _marker_commands_project(tmp_path / "p")
    untrusted = {**env, **_fork_payload(tmp_path)}
    code, out, err = support.readiness(project, env=untrusted)
    assert code == 0, out + err
    record = support.read_record(project)
    for signal_id in COMMAND_SIGNALS.values():
        entry = support.signal(record, signal_id)
        assert entry["result"] == "absent" and entry["not_run"] == "untrusted", entry
    before = _manifest_before(project)
    code, out, err = _evaluate_write(project, env=untrusted)
    _assert_refused_unwritten(project, before, code, out, err)
    assert "cannot be measured for an untrusted contribution" in err, err
    assert "not the same as below the readiness floor" in err, err
    assert "no setting lets an untrusted contribution run unattended" in err, err
    assert "balanced" in err and "controlled" in err, err
    assert "compass readiness" not in err, err
    # A trusted run on the same kind of runner measures, and the floor is met.
    trusted = {**env, "CI": "true", "COMPASS_CONTRIBUTION_TRUST": "trusted"}
    code, out, err = support.readiness(project, env=trusted)
    assert code == 0, out + err
    assert support.signal(support.read_record(project),
                          "build-declared-and-succeeds")["result"] == "present"
    code, out, err = _evaluate_write(project, env=trusted)
    assert code == 0, out + err


def test_prc_39_committed_record(tmp_path):
    # Trust is read before the record, so a record a contribution committed
    # cannot clear the floor on an untrusted runner.
    project = _floor_project(tmp_path / "p")
    _floor_record(project)
    support.git(project, "add", "-f", str(support.RECORD))
    support.git(project, "commit", "-q", "-m", "a contribution commits a record")
    before = _manifest_before(project)
    untrusted = {"CI": "true", "COMPASS_CONTRIBUTION_TRUST": "untrusted"}
    code, out, err = _evaluate_write(project, env=untrusted)
    _assert_refused_unwritten(project, before, code, out, err)
    assert "cannot be measured for an untrusted contribution" in err, err
    # The same record on a laptop meets the floor.
    code, out, err = _evaluate_write(project)
    assert code == 0, out + err


def _run_hook(project, framework=ROOT, env=None):
    """Run the session-start hook as a session in `project` starts. Returns
    `(exit code, the context it adds, stdout)`."""
    done = subprocess.run(
        ["bash", str(Path(framework) / HOOK)], cwd=project, capture_output=True, text=True,
        timeout=60, env=support.environment(project, {"CLAUDE_PROJECT_DIR": str(project),
                                                      **(env or {})}))
    context = ""
    if done.stdout.strip():
        context = json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"]
    return done.returncode, context, done.stdout


def _contract_heading():
    return (ROOT / "compass-contract.md").read_text(encoding="utf-8").splitlines()[0]


def test_prc_26(tmp_path):
    marks, temp, env = _run_env(tmp_path)
    project = _marker_commands_project(tmp_path / "p")
    _floor_record(project, absent=("build-declared-and-succeeds",))
    code, context, _ = _run_hook(project, env=env)
    assert code == 0
    assert _contract_heading() in context
    assert "below the readiness floor" in context.lower(), context
    assert "build-declared-and-succeeds" in context, context
    assert "assess will refuse" in context.lower(), context
    assert "autonomy" in context, context
    # No record, then a stale one.
    os.remove(project / support.RECORD)
    code, context, _ = _run_hook(project, env=env)
    assert code == 0 and "not measured" in context and "compass readiness" in context, context
    assert not (project / support.RECORD).exists()
    _floor_record(project)
    _stale_settings(project)
    code, context, _ = _run_hook(project, env=env)
    assert code == 0 and "stale" in context and "compass readiness" in context, context
    # The hook ran no signal and no project command.
    assert support.markers(marks) == {}
    # At the floor, and on balanced, there is no readiness line.
    floor_met = _floor_project(tmp_path / "met")
    _floor_record(floor_met)
    code, context, _ = _run_hook(floor_met, env=env)
    assert code == 0 and _contract_heading() in context
    assert READINESS_LINE not in context, context
    balanced = _floor_project(tmp_path / "balanced", autonomy="balanced")
    _floor_record(balanced, absent=("build-declared-and-succeeds",))
    code, context, _ = _run_hook(balanced, env=env)
    assert code == 0 and _contract_heading() in context
    assert READINESS_LINE not in context, context


def _planted_framework(folder, plant):
    """A copy of the framework parts the hook runs, with `plant` applied to
    the copied record module's text. Returns the copy's root."""
    for part in ("hooks", "cli"):
        shutil.copytree(ROOT / part, folder / part,
                        ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "scripts" / "lib", folder / "scripts" / "lib")
    shutil.copy2(ROOT / "compass-contract.md", folder / "compass-contract.md")
    module = folder / "cli" / "compass_pkg" / "readiness_record.py"
    module.write_text(plant(module.read_text(encoding="utf-8")), encoding="utf-8")
    return folder


def _assert_unreadable_line(context):
    assert "could not be read" in context, context
    assert str(support.RECORD) in context and "compass readiness" in context, context


def test_prc_44(tmp_path):
    project = _floor_project(tmp_path / "p")
    record = project / support.RECORD
    before = _manifest_before(project)
    # A record that is not valid YAML.
    _unreadable_record(project)
    code, context, _ = _run_hook(project)
    assert code == 0
    _assert_unreadable_line(context)
    code, out, err = _evaluate_write(project)
    _assert_refused_unwritten(project, before, code, out, err)
    assert str(support.RECORD) in err and "compass readiness" in err, err
    # A record the user cannot read.
    _floor_record(project)
    record.chmod(0)
    try:
        if os.access(record, os.R_OK):
            pytest.skip("running as a user who can read any file")
        code, context, _ = _run_hook(project)
        assert code == 0
        _assert_unreadable_line(context)
        code, out, err = _evaluate_write(project)
        _assert_refused_unwritten(project, before, code, out, err)
        assert str(support.RECORD) in err and "compass readiness" in err, err
    finally:
        record.chmod(0o644)
    # A compass.yml that is not valid YAML: the contract still reaches the session.
    broken = _floor_project(tmp_path / "broken")
    (broken / "compass.yml").write_text("autonomy: [autonomous\n", encoding="utf-8")
    code, context, _ = _run_hook(broken)
    assert code == 0 and _contract_heading() in context
    # The shared module made to raise, in a copy of the framework only this
    # test runs: the line is lost, the contract is not, and the hook exits 0.
    _unreadable_record(project)
    intact = _planted_framework(tmp_path / "intact", lambda text: text)
    code, context, _ = _run_hook(project, framework=intact)
    assert code == 0
    _assert_unreadable_line(context)
    planted = _planted_framework(
        tmp_path / "planted",
        lambda text: text + "\n\ndef hook_line(*args, **kwargs):\n"
                            "    raise RuntimeError('a fault the test planted')\n")
    code, context, _ = _run_hook(project, framework=planted)
    assert code == 0
    assert _contract_heading() in context, context
    assert READINESS_LINE not in context, context
    # On balanced the same two records run, recorded as not measured.
    for name in ("invalid", "no-permission"):
        balanced = _floor_project(tmp_path / f"balanced-{name}", autonomy="balanced")
        target = balanced / support.RECORD
        if name == "invalid":
            _unreadable_record(balanced)
        else:
            _floor_record(balanced)
            target.chmod(0)
        try:
            code, out, err = _evaluate_write(balanced)
        finally:
            target.chmod(0o644)
        assert code == 0, (name, out + err)
        readiness = _floor_manifest(balanced)["readiness"]
        assert readiness["status"] == "not-measured", (name, readiness)
        assert readiness["reason"] == "unreadable", (name, readiness)


def test_prc_27(tmp_path):
    project = support.make_project(tmp_path / "p", None)
    _floor_issue(project)
    code, context, _ = _run_hook(project)
    assert code == 0 and _contract_heading() in context
    assert READINESS_LINE not in context, context
    code, out, err = _evaluate_write(project)
    assert code == 0, out + err
    assert _floor_manifest(project)["readiness"]["status"] == "not-measured"


def _upgrade_section():
    text = UPGRADE_GUIDE.read_text(encoding="utf-8")
    heading = "## Repository readiness and autonomous work"
    assert heading in text, "the 7.0.0 upgrade guide has no readiness section"
    body = text.split(heading, 1)[1]
    following = body.find("\n## ")
    return body if following < 0 else body[:following]


def test_prc_28():
    flat = " ".join(_upgrade_section().split())
    assert "refused" in flat and "7.0.0" in flat, flat
    for signal_id in REQUIRED_SIGNALS:
        assert f"`{signal_id}`" in flat, signal_id
    assert "`compass readiness`" in flat
    # The three ways to carry on.
    assert "`autonomy`" in flat
    assert "make the absent signals present" in flat.lower(), flat
    assert "`required_for_autonomous`" in flat and "project layer" in flat
    # Who is never refused.
    assert "`balanced`" in flat and "`controlled`" in flat and "never refused" in flat
    assert "no settings file" in flat
    # The record.
    assert "per checkout" in flat and "never committed" in flat
    assert "seven days" in flat and "25 commits" in flat
    assert "plain file" in flat and "edit" in flat
    # The commands and trust.
    assert "clean checkout of HEAD" in flat
    assert "untrusted" in flat and "cannot run an autonomous project" in flat


def _complete_marker(project, number):
    return (_task_dir(project) / "generations" / str(number) / "complete").read_text(
        encoding="utf-8")


def test_prc_29(tmp_path):
    marks, temp, env = _run_env(tmp_path)
    project = _floor_project(tmp_path / "p", autonomy="balanced")
    absent = ("codeowners-present", "secret-scan-declared")
    measured_at = _days_ago(0) - datetime.timedelta(hours=1)
    record = _floor_record(project, absent=absent, measured_at=measured_at)
    code, out, err = _evaluate_write(project, env=env)
    assert code == 0, out + err
    assert _floor_manifest(project)["readiness"] == {
        "status": "measured", "score": 9, "signals": 11, "floor_met": True,
        "absent": list(absent), "measured_at": record["measured_at"]}
    code, out, err = support.run_compass(project, "issue", "lint", "--issue", FLOOR_SLUG)
    assert code == 0, out + err
    # No generation file holds the summary. The generation may store the
    # catalogue named `readiness`; it never stores a measurement.
    for path in (_task_dir(project) / "generations").rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert "floor_met" not in text and record["measured_at"] not in text, path
    marker = _complete_marker(project, 1)
    # A second measurement with a different result.
    code, out, err = support.readiness(project, env=env)
    assert code == 0, out + err
    second = support.read_record(project)
    present = sum(1 for s in second["signals"] if s["result"] == "present")
    assert present != 9
    code, out, err = _evaluate_write(project, env=env)
    assert code == 0, out + err
    assert _generations(project) == ["1"]
    assert _complete_marker(project, 1) == marker
    readiness = _floor_manifest(project)["readiness"]
    assert readiness["score"] == present and readiness["measured_at"] == second["measured_at"]


def _delivery_approach_text(project):
    found = sorted(Path(project).rglob("delivery-approach.md"))
    return "\n".join(p.read_text(encoding="utf-8") for p in found)


def _not_measured_manifests(tmp_path):
    """Two balanced issues assessed with no record and with a stale one; each
    manifest records why readiness is not measured. Returns the stale project."""
    missing = _floor_project(tmp_path / "missing", autonomy="balanced")
    stale = _floor_project(tmp_path / "stale", autonomy="balanced")
    _floor_record(stale)
    _stale_settings(stale)
    for project, reason in ((missing, "missing"), (stale, "stale")):
        code, out, err = _evaluate_write(project)
        assert code == 0, out + err
        readiness = _floor_manifest(project)["readiness"]
        assert readiness["status"] == "not-measured" and readiness["reason"] == reason, (
            reason, readiness)
    return stale


def test_prc_30_manifest(tmp_path):
    _not_measured_manifests(tmp_path)


def test_prc_30(tmp_path):
    stale = _not_measured_manifests(tmp_path)
    _register_approach(stale, FLOOR_SLUG)
    # The delivery approach says the record was stale, not only that it is missing.
    code, out, err = support.run_compass(stale, "issue", "render", "--issue", FLOOR_SLUG)
    assert code == 0, out + err
    assert "Repository readiness: not measured (record stale" in _delivery_approach_text(stale)


def test_prc_36(tmp_path):
    marks, temp, env = _run_env(tmp_path)
    folder = tmp_path / "p"
    folder.mkdir()
    settings = {"schema": 1, "autonomy": "autonomous", "allow_project_commands": True,
                "project": {"lint_command": support.marker_script(folder, "lint.sh", "exit 0"),
                            "test_command": support.marker_script(folder, "test.sh", "exit 0")}}
    project = support.make_project(folder, settings, files={"AGENTS.md": "# Agents\n"})
    _floor_issue(project)
    code, out, err = support.readiness(project, env=env)
    assert code == 0, out + err
    assert support.signal(support.read_record(project),
                          "lint-declared-and-clean")["result"] == "present"
    before = _manifest_before(project)
    code, out, err = _evaluate_write(project, env=env)
    _assert_refused_unwritten(project, before, code, out, err)
    assert "build-declared-and-succeeds" in err, err
    settings["autonomy"] = "balanced"
    (project / "compass.yml").write_text(yaml.safe_dump(settings, sort_keys=False),
                                         encoding="utf-8")
    support.git(project, "commit", "-q", "-am", "balanced")
    code, out, err = support.readiness(project, env=env)
    assert code == 0, out + err
    code, out, err = _evaluate_write(project, env=env)
    assert code == 0, out + err


# --- U4 readers, init and retro ---

READ_SLUG = "read-issue"
SAMPLE_SLUG = "ci-lints-every-issue"
NOT_MEASURED_LINE = "Repository readiness: not measured"


def _snapshot_tree(*folders):
    """`{path: bytes}` of every file under the folders, to prove a read wrote nothing."""
    found = {}
    for folder in folders:
        for path in sorted(Path(folder).rglob("*")):
            if path.is_file():
                found[str(path)] = path.read_bytes()
    return found


def _board_page(project):
    page = Path(str(project) + "-board.html")
    code, out, err = support.run_compass(project, "board", "render", "--no-open",
                                         "--out", str(page))
    assert code == 0, out + err
    return page.read_text(encoding="utf-8")


def _receipt(project, slug=READ_SLUG):
    code, out, err = support.run_compass(project, "issue", "receipt", "--issue", slug)
    assert code == 0, out + err
    return out


def _readiness_lines(text):
    return [line.strip() for line in text.splitlines() if "Repository readiness" in line]


def _register_approach(project, slug):
    """Write a delivery approach with the readiness block marker under
    docs/compass and register it in the issue's manifest. Returns the document."""
    rel = f"docs/compass/2026-10-13-{slug}/delivery-approach.md"
    document = Path(project) / rel
    document.parent.mkdir(parents=True, exist_ok=True)
    template = (ROOT / "templates" / "delivery-approach.md").read_text(encoding="utf-8")
    start = template.index("## 1. The assessment")
    document.write_text(f"# Delivery approach - {slug}\n\n" + template[start:].split("\n---\n")[0],
                        encoding="utf-8")
    path = Path(project) / ".compass" / "work" / slug / "manifest.yml"
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    manifest["delivery_approach"] = "feature"
    manifest["artifacts"] = [{"id": "ART-DELIVERY_APPROACH", "kind": "delivery-approach",
                              "status": "draft", "reason": "fixture", "path": rel}]
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return document


def _read_project(folder, readiness=None, slug=READ_SLUG):
    """A fixture project with one assessed issue whose delivery approach is
    registered under docs/compass and holds the readiness block marker. The
    manifest's `readiness:` key is `readiness` (left out when None)."""
    project = support.make_project(folder, {"schema": 1})
    manifest = dict(FLOOR_MANIFEST, issue=slug)
    if readiness is not None:
        manifest["readiness"] = readiness
    task_dir = Path(project) / ".compass" / "work" / slug
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False),
                                           encoding="utf-8")
    return project, _register_approach(project, slug)


def _measured_summary(project):
    """The summary of a nine-of-eleven record, written through the record module."""
    _floor_record(project, absent=("codeowners-present", "secret-scan-declared"))
    from compass_pkg import readiness_record
    return readiness_record.summary(str(project))


def test_prc_31(tmp_path):
    from archive import sample_root
    sample = sample_root()
    project = support.make_project(tmp_path / "p", {"schema": 1})
    shutil.copytree(sample / ".compass" / "work" / SAMPLE_SLUG,
                    Path(project) / ".compass" / "work" / SAMPLE_SLUG)
    shutil.copytree(sample / "docs" / "compass" / "2026-08-12-ci-lints-every-issue",
                    Path(project) / "docs" / "compass" / "2026-08-12-ci-lints-every-issue")
    # The board lists a closed issue only in the week after it landed, so the
    # copy lands now. This is the only change to the copied manifest.
    path = Path(project) / ".compass" / "work" / SAMPLE_SLUG / "manifest.yml"
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "readiness" not in manifest
    manifest["land_timestamp"] = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00")
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    before = _snapshot_tree(Path(project) / ".compass" / "work", Path(project) / "docs")
    receipt = _receipt(project, SAMPLE_SLUG)
    page = _board_page(project)
    assert any(NOT_MEASURED_LINE in line for line in _readiness_lines(receipt)), receipt
    assert NOT_MEASURED_LINE in page
    after = _snapshot_tree(Path(project) / ".compass" / "work", Path(project) / "docs")
    assert after == before
    assert not any("generations" in path for path in after)


def test_prc_32(tmp_path):
    project, document = _read_project(tmp_path / "p")
    summary = _measured_summary(project)
    assert (summary["score"], summary["signals"], summary["floor_met"]) == (9, 11, True)
    task = Path(project) / ".compass" / "work" / READ_SLUG / "manifest.yml"
    manifest = yaml.safe_load(task.read_text(encoding="utf-8"))
    manifest["readiness"] = summary
    task.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    line = "Repository readiness: 9 of 11 signals, floor met"
    code, out, err = support.run_compass(project, "issue", "render", "--issue", READ_SLUG)
    assert code == 0, out + err
    text = document.read_text(encoding="utf-8")
    assert line in text
    # The line sits under the assessment, inside a readiness block.
    assert text.index("## 1. The assessment") < text.index(line)
    assert "<!-- compass:render readiness -->" in text
    assert _readiness_lines(_receipt(project)) == [line]
    assert line in _board_page(project)

    # An issue whose record was never measured shows the same words in all three.
    other, other_document = _read_project(tmp_path / "q", readiness={
        "status": "not-measured", "reason": "missing",
        "detail": "no .compass/readiness.yml; run compass readiness"})
    code, out, err = support.run_compass(other, "issue", "render", "--issue", READ_SLUG)
    assert code == 0, out + err
    assert NOT_MEASURED_LINE in other_document.read_text(encoding="utf-8")
    assert NOT_MEASURED_LINE in "\n".join(_readiness_lines(_receipt(other)))
    assert NOT_MEASURED_LINE in _board_page(other)



def _bare_repository(folder, files=None):
    """A Git repository with no `.compass` directory, as `/compass:init` finds
    a new project. Returns the folder."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    support.git(folder, "init", "-q", "-b", "main")
    for name, text in (files or {}).items():
        (folder / name).write_text(text, encoding="utf-8")
    support.git(folder, "add", "-A")
    support.git(folder, "commit", "-q", "--allow-empty", "-m", "fixture")
    return folder


def test_prc_33(tmp_path):
    files = {"AGENTS.md": "# Agents\n"}
    project = _bare_repository(tmp_path / "p", files)
    (project / "compass.yml").write_text("schema: 1\n", encoding="utf-8")
    assert not (project / ".compass").exists()
    code, out, err = support.run_compass(project, "init", "--readiness")
    assert code == 0, out + err
    assert (project / ".compass" / "readiness.yml").is_file()
    lines = out.splitlines()
    marks = [i for i, line in enumerate(lines) if line.lstrip().startswith("- [ ] ")]
    assert marks, out
    # The list follows the files init wrote and comes before anything else the
    # measurement prints.
    first = lines[marks[0]]
    before = [line for line in lines[:marks[0]] if "readiness" in line.lower()]
    assert all("absent" in line.lower() or "initialised" in line.lower() for line in before), out
    listed = [lines[i].split(":", 1)[0].replace("- [ ] ", "").strip() for i in marks]
    record = support.read_record(project)
    absent = [s["id"] for s in record["signals"] if s["result"] == "absent"]
    assert sorted(listed) == sorted(absent), (listed, absent)
    required = [i for i in listed if i in REQUIRED_SIGNALS]
    assert listed[:len(required)] == required, listed
    for i in marks:
        assert "(compass.yml)" in lines[i] or "(" in lines[i], lines[i]
    assert first.split(":", 1)[1].strip(), first

    # Plain init measures nothing and runs no project command.
    marks_folder = tmp_path / "marks"
    marks_folder.mkdir()
    other = _bare_repository(tmp_path / "q", files)
    command = support.marker_script(other, "test.sh", "exit 0")
    (other / "compass.yml").write_text(yaml.safe_dump({
        "schema": 1, "allow_project_commands": True, "project": {"test_command": command}}),
        encoding="utf-8")
    support.git(other, "add", "-A")
    support.git(other, "commit", "-q", "-m", "commands")
    code, out, err = support.run_compass(other, "init",
                                         env={"READINESS_MARKERS": str(marks_folder)})
    assert code == 0, out + err
    assert not (other / ".compass" / "readiness.yml").exists()
    assert list(marks_folder.iterdir()) == []
    assert "- [ ] " not in out

    # /compass:init passes the flag after it writes compass.yml.
    steps = (ROOT / "commands" / "init.md").read_text(encoding="utf-8")
    assert "compass init --readiness" in steps
    assert "compass init --readiness" in steps.split("Write a minimal `compass.yml`")[1]


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                    reason="root can write into a read-only folder")
def test_prc_34(tmp_path):
    project = _bare_repository(tmp_path / "p", {"AGENTS.md": "# Agents\n"})
    (project / "compass.yml").write_text("schema: 1\n", encoding="utf-8")
    code, out, err = support.run_compass(project, "init")
    assert code == 0, out + err
    compass_dir = project / ".compass"
    mode = compass_dir.stat().st_mode
    compass_dir.chmod(0o555)
    try:
        code, out, err = support.run_compass(project, "init", "--readiness")
    finally:
        compass_dir.chmod(mode)
    assert code == 0, out + err
    text = out + err
    assert "readiness was not measured" in text, text
    assert "Permission denied" in text or "read-only" in text.lower(), text
    assert "compass readiness" in text
    assert (project / "compass.yml").read_text(encoding="utf-8") == "schema: 1\n"
    assert not (project / ".compass" / "readiness.yml").exists()


def test_prc_35(tmp_path):
    project = support.make_project(tmp_path / "p", {"schema": 1})
    measured = {"status": "measured", "signals": 11, "absent": [], "measured_at": "2026-10-10T10:00:00Z"}
    issues = [("zulu-issue", "2026-10-01", dict(measured, score=4, floor_met=False)),
              ("mike-issue", "2026-10-02", {"status": "not-measured", "reason": "missing",
                                              "detail": "run compass readiness"}),
              ("alpha-issue", "2026-10-03", dict(measured, score=7, floor_met=True))]
    # The names run against the dates, so neither the folder order nor the
    # name order can pass for the order of assessment.
    for slug, created, summary in (issues[2], issues[0], issues[1]):
        task_dir = Path(project) / ".compass" / "work" / slug
        task_dir.mkdir(parents=True)
        manifest = dict(FLOOR_MANIFEST, issue=slug, created=created, readiness=summary)
        (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False),
                                               encoding="utf-8")
    code, out, err = support.run_compass(project, "retro")
    assert code == 0, out + err
    lines = out.splitlines()
    assert "Repository readiness at assessment:" in lines, out
    start = lines.index("Repository readiness at assessment:") + 1
    rows = []
    for line in lines[start:]:
        if not line.strip():
            break
        rows.append(line)
    assert len(rows) == 3, out
    assert [next(s for s, _, _ in issues if s in line) for line in rows] == [
        "zulu-issue", "mike-issue", "alpha-issue"], out
    assert "4 of 11" in rows[0] and "floor not met" in rows[0], rows
    assert "not measured" in rows[1], rows
    assert "7 of 11" in rows[2] and "floor met" in rows[2] and "not met" not in rows[2], rows


# --- U5 this repository and the measures ---
