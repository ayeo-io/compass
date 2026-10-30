"""Scenario group A of the four-layer acceptance strategy: the strategy, its
applicability, its routing and the project opt-out.

The specification is `acceptance-criteria.md` of the Compass issue
`acceptance-strategy-core` (ayeo-io/compass-delivery#321). Each test names
the scenario it checks; `support.py` builds the projects.
"""
from __future__ import annotations

import datetime
import json
import re

import pytest
import yaml

from tests.acceptance.atdd_strategy import support
from tests.acceptance.atdd_strategy.support import ROOT

CHECK = "acceptance-applicability-agrees"
STRATEGY = "four-layer acceptance strategy"
OFF_REASON = "no deployable candidate yet"


def _strategy_line(text):
    """The line of the rendered `acceptance-strategy` block of a delivery-approach record."""
    found = re.search(r"<!-- compass:render acceptance-strategy -->\n(.*?)\n"
                      r"<!-- /compass:render -->", text, re.S)
    assert found, "the delivery-approach record has no acceptance-strategy block"
    return " ".join(found.group(1).split())


def _row(document, name=CHECK):
    rows = [c for c in document["checks"] if c["name"] == name]
    assert len(rows) == 1, document["checks"]
    return rows[0]


# --- `TRC-A1` ------------------------------------------------------------------------------

def test_trc_a1():
    """The strategy has its own entry under the next free strategy number."""
    text = (ROOT / "governance" / "strategies.md").read_text(encoding="utf-8")
    numbers = [int(n) for n in re.findall(r"^### .*\(`S(\d+)`\)$", text, re.M)]
    assert max(numbers) == 17 and numbers.count(17) == 1, numbers
    entry = text[text.index(re.search(r"^### .*\(`S17`\)$", text, re.M).group(0)):]
    entry = entry[:re.search(r"\n##+ ", entry).start()]
    assert STRATEGY in entry.lower(), entry[:200]
    for needed in ("`validation`", "`refactor`", "quick-fix", "hotfix", "spike",
                   "`acceptance_strategy`", "issue waiver"):
        assert needed in entry, needed
    rationale = (ROOT / "governance" / "strategies-rationale.md").read_text(encoding="utf-8")
    assert re.search(r"^## .*\(`S17`\)$", rationale, re.M), "no S17 entry in the rationale"
    before = support.recorded("guardrails")["spike_guardrails"]
    now = yaml.safe_load((ROOT / "governance" / "guardrails.yml").read_text(encoding="utf-8"))
    assert [g["id"] for g in now["spike_guardrails"]] == before


# --- `TRC-A2` ------------------------------------------------------------------------------

@pytest.mark.parametrize("expected, applies, reason", [
    ("none", "applies", "client-observable behavior"),
    ("validation", "does not apply", "acceptance of kind validation"),
    ("refactor", "does not apply", "acceptance of kind refactor"),
])
def test_trc_a2(tmp_path, expected, applies, reason):
    """Assess records whether the strategy applies and why."""
    project = support.Project(tmp_path / "repo")
    issue = project.issue("change")
    code, out, err = issue.assess(expected=expected)
    assert code == 0, out + err
    line = _strategy_line(issue.approach_record())
    assert f"(`S17`): {applies} - {reason}" in line, line


# --- `TRC-A3` ------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["validation", "refactor"])
def test_trc_a3(tmp_path, kind):
    """Out of scope costs nothing: the result of compass 8.0.4, and no strategy finding."""
    project = support.Project(tmp_path / "repo")
    issue = support.out_of_scope_issue(project, kind)
    code, document = issue.check()
    assert support.strategy_findings(document) == []
    assert support.summary(code, document) == support.recorded("out-of-scope-" + kind)


# --- `TRC-A5` ------------------------------------------------------------------------------

@pytest.mark.parametrize("line", ["does not apply", "applies"])
def test_trc_a5(tmp_path, line):
    """An applicability line that disagrees with the records is an advisory failure."""
    project = support.Project(tmp_path / "repo")
    issue = project.issue("change")
    code, out, err = issue.assess(expected="validation" if line == "does not apply" else "none")
    assert code == 0, out + err
    assert f"(`S17`): {line} - " in _strategy_line(issue.approach_record())
    if line == "does not apply":
        issue.red()
        issue.green()
    else:
        issue.acceptance_start("validation")
    code, document = issue.check()
    row = _row(document)
    assert row["status"] == "advisory", row
    assert "compass approach evaluate --write" in row["detail"], row
    failures = {c["name"] for c in document["checks"] if c["status"] == "fail"}
    assert document["failed"] == len([c for c in document["checks"] if c["status"] == "fail"])
    assert CHECK not in failures
    assert code == (1 if failures else 0)


# --- `TRC-A6` ------------------------------------------------------------------------------

@pytest.mark.parametrize("approach, routing", [
    ("regular", "on"),
    ("full", "on"),
    ("quick-fix", "existing DSL only"),
    ("hotfix", "existing DSL only, isolation proof required"),
    ("spike", "suspended, as strategy `S2`"),
])
def test_trc_a6(tmp_path, approach, routing):
    """The strategy is routed per delivery approach."""
    project = support.Project(tmp_path / "repo")
    issue = project.issue("change", approach=approach)
    code, out, err = issue.assess()
    assert code == 0, out + err
    assert issue.manifest()["delivery_approach"] == approach
    line = _strategy_line(issue.approach_record())
    assert line.endswith(f"Routing on the {approach} approach: {routing}."), line


def test_trc_a6_the_record_quick_fix_start_writes_shows_the_line(tmp_path):
    """The quick-fix example of `TRC-A6`, on the record `quick-fix start` itself writes."""
    project = support.Project(tmp_path / "repo")
    code, out, err = project.run(
        "quick-fix", "start", "docs", "--risk", "trivial - a docs edit",
        "--familiarity", "brownfield-mapped - known file", "--size", "atomic - one line",
        "--intent", "The README names the command.",
        "--scenario", "A reader finds the command in the README",
        "--test", "tests/test_readme.py::test_names_the_command",
        "--expected-acceptance", "validation")
    assert code == 0, out + err
    code, out, err = project.run("issue", "render", "--issue", "docs")
    assert code == 0, out + err
    records = list((project.root / "docs" / "compass").glob("*-docs/delivery-approach.md"))
    assert len(records) == 1
    line = _strategy_line(records[0].read_text(encoding="utf-8"))
    assert "(`S17`): does not apply - acceptance of kind validation" in line, line
    assert line.endswith("Routing on the quick-fix approach: existing DSL only."), line


# --- `TRC-A9` ------------------------------------------------------------------------------

def test_trc_a9(tmp_path):
    """A spike is exempt: the spike guardrails report what compass 8.0.4 reports."""
    project = support.Project(tmp_path / "repo")
    code, document = support.spike_issue(project).check()
    assert support.strategy_findings(document) == []
    assert not [r for r in support.rows(document) if r[0] in support.STRATEGY_CHECKS]
    assert support.summary(code, document) == support.recorded("spike")


# --- `TRC-A11` -----------------------------------------------------------------------------

@pytest.mark.parametrize("where", ["compass.yml", ".compass/config.yml"])
def test_trc_a11(tmp_path, where):
    """The opt-out is recorded in the delivery-approach record."""
    project = support.Project(tmp_path / "repo")
    project.setting({"state": "off", "reason": OFF_REASON}, where=where)
    issue = project.issue("change")
    code, out, err = issue.assess()
    assert code == 0, out + err
    line = _strategy_line(issue.approach_record())
    assert f"(`S17`): off for this project - {OFF_REASON}" in line, line


# --- `TRC-A12` -----------------------------------------------------------------------------

@pytest.mark.parametrize("green, code, failed", [
    (True, 0, []),
    (False, 1, ["suite-passed"]),
])
def test_trc_a12(tmp_path, green, code, failed):
    """An opted-out project keeps today's checks and no more."""
    project = support.Project(tmp_path / "repo")
    (project.root / "tests").mkdir()
    (project.root / "tests" / "test_one.py").write_text("def test_one():\n    assert True\n")
    support.git(project.root, "add", "-A")
    support.git(project.root, "commit", "-q", "-m", "test")
    project.setting({"state": "off", "reason": OFF_REASON})
    issue = project.issue("fix", approach="quick-fix")
    assert issue.assess()[0] == 0
    issue.must("scenario", "add", "TRC-1", "--issue", "fix", "--intent", "INT-1",
               "--title", "one", "--test", "tests/test_one.py::test_one")
    issue.must("tdd-red", "--issue", "fix", "--scenario", "TRC-1", "--", "sh", "-c",
               "echo 'tests/test_one.py::test_one FAILED'; exit 1")
    if green:
        issue.must("tdd-green", "--issue", "fix", "--scenario", "TRC-1", "--", "sh", "-c",
                   "echo 'tests/test_one.py::test_one PASSED'")
    assert issue.manifest()["acceptance_strategy"]["state"] == "off"
    issue.must("issue", "render", "--issue", "fix")
    exit_code, document = issue.check()
    assert support.strategy_findings(document) == []
    assert sorted({r[0] for r in support.findings(document) if r[1] == "fail"}) == failed
    assert exit_code == code


# --- `TRC-A13` -----------------------------------------------------------------------------

@pytest.mark.parametrize("value", [
    {"state": "off"},
    {"state": "off", "reason": "  "},
    {"state": "maybe", "reason": "unsure"},
    {"state": "off", "reason": datetime.date(2026, 10, 29)},
], ids=["no-reason", "empty-reason", "maybe", "date-reason"])
@pytest.mark.parametrize("command", ["evaluate", "check"])
def test_trc_a13(tmp_path, value, command):
    """An opt-out setting that cannot be read is refused with exit 2."""
    project = support.Project(tmp_path / "repo")
    issue = project.issue("change")
    if command == "check":
        assert issue.assess()[0] == 0
    project.setting(value)
    if command == "evaluate":
        code, out, err = issue.assess()
    else:
        code, out, err = issue.run("check", "--issue", "change")
    message = out + err
    assert code == 2, message
    assert "acceptance_strategy" in message and "compass.yml" in message, message
    assert "`acceptance_strategy: {state: on}`" in message and "reason" in message, message


# --- `TRC-A14` -----------------------------------------------------------------------------

def test_trc_a14(tmp_path):
    """Turning the strategy off during an issue takes effect at re-assess."""
    project = support.Project(tmp_path / "repo")
    issue = project.issue("change")
    assert issue.assess()[0] == 0
    issue.red()
    project.setting({"state": "off", "reason": OFF_REASON})
    code, document = issue.check()
    row = _row(document)
    assert row["status"] == "advisory", row
    assert "still applies" in row["detail"] and "setting" in row["detail"], row
    assert "compass approach evaluate --write" in row["detail"], row
    assert issue.manifest()["acceptance_strategy"]["state"] == "on"
    # After the re-assess, the stored block is off and the check has nothing to compare.
    code, out, err = issue.assess(reason="the project turned the strategy off")
    assert code == 0, out + err
    assert issue.manifest()["acceptance_strategy"]["state"] == "off"
    assert _row(issue.check()[1])["status"] == "nothing-to-check"


# --- `TRC-A15` and `TRC-A21`: the retrospective ----------------------------------------------

def _retro(project):
    code, out, err = project.run("retro", "--acceptance")
    assert code == 0, out + err
    code, raw, err = project.run("retro", "--acceptance", "--format", "json")
    assert code == 0, raw + err
    return out, json.loads(raw)


def _closed_in_scope(project, slug):
    issue = project.issue(slug)
    assert issue.assess()[0] == 0
    issue.red()
    issue.green()
    issue.close()
    return issue


def test_trc_a15(tmp_path):
    """The retrospective reports an opted-out project apart."""
    project = support.Project(tmp_path / "repo")
    project.setting({"state": "off", "reason": OFF_REASON})
    for n in range(3):
        _closed_in_scope(project, f"change-{n}")
    text, report = _retro(project)
    assert f"has opted out of the {STRATEGY}" in text and OFF_REASON in text, text
    assert report["opted_out"] == {"reason": OFF_REASON}
    assert report["measured"] == []
    assert sorted(report["off"]) == ["change-0", "change-1", "change-2"]


WAIVER_REASON = "the staging environment is down until 3 November"


def test_trc_a21(tmp_path):
    """The retrospective reports an issue that stepped off apart."""
    project = support.Project(tmp_path / "repo")
    project.setting(None, owner="jed72")
    for n in range(3):
        _closed_in_scope(project, f"change-{n}")
    issue = support.Issue(project, "change-1")
    body = issue.manifest()
    body["config"] = {"checks": {CHECK: {
        "set": {"on_skipped": "pass"},
        "waiver": {"reason": WAIVER_REASON, "approved_by": "EV-W1"}}}}
    body["evidence"].append({
        "id": "EV-W1", "type": "human-approval", "decision": "approved",
        "approver": "jed72", "role": "owner", "scope": "waiver",
        "timestamp": "2026-10-29T10:00:00Z",
        "waiver": {"scope": "issue", "entry": f"checks.{CHECK}",
                   "fields": {"on_skipped": {"from": "not-applicable", "to": "pass"}}}})
    issue.write_manifest(body)
    code, out, err = issue.assess(reason="step off the strategy for one issue")
    assert code == 0, out + err
    # An issue closed as not planned delivered nothing, so it is not measured.
    dropped = project.issue("dropped")
    assert dropped.assess()[0] == 0
    dropped.red()
    body = dropped.manifest()
    body.update({"status": "done", "close_reason": "not-planned"})
    dropped.write_manifest(body)
    text, report = _retro(project)
    assert "change-1" in text and WAIVER_REASON in text, text
    assert sorted(report["measured"]) == ["change-0", "change-2"]
    assert report["stepped_off"] == [{"issue": "change-1", "reason": WAIVER_REASON}]


# --- `TRC-A19` -----------------------------------------------------------------------------

def test_trc_a19():
    """The strategy changes no locked guardrail, and the definition of a strategy changed."""
    before = support.recorded("guardrails")["checks"]
    now = yaml.safe_load((ROOT / "governance" / "guardrails.yml").read_text(encoding="utf-8"))
    lists = {g["id"]: g["checks"] for g in now["defaults"]}
    assert {g: lists[g] for g in ("G1", "G4")} == before
    preset = yaml.safe_load(
        (ROOT / "governance" / "presets" / "default" / "preset.yml").read_text(encoding="utf-8"))
    locked = [entry for kind in preset["locks"].values() for entry in kind]
    for check in support.STRATEGY_CHECKS:
        assert f"checks.{check}" not in locked, check
    checks = yaml.safe_load((ROOT / "governance" / "presets" / "default" / "checks.yml")
                            .read_text(encoding="utf-8"))["checks"]
    assert CHECK in checks and not checks[CHECK].get("locked")
    gates = yaml.safe_load((ROOT / "governance" / "presets" / "default" / "gates.yml")
                           .read_text(encoding="utf-8"))["gates"]
    assert not [g for g, body in gates.items() if CHECK in (body.get("checks") or [])]
    sentence = "can carry blocking checks that a recorded step-off makes advisory"
    terms = yaml.safe_load((ROOT / "governance" / "terminology.yml").read_text(encoding="utf-8"))
    term = next(body for name, body in _terms(terms) if name == "strategy")
    assert sentence in " ".join(term["means"].split())
    strategies = (ROOT / "governance" / "strategies.md").read_text(encoding="utf-8")
    introduction = strategies[:strategies.index("\n## ")]
    assert sentence in " ".join(introduction.split())
    assert "No strategy fails `compass check`" not in introduction
    header = (ROOT / "governance" / "guardrails.yml").read_text(encoding="utf-8")
    assert sentence in " ".join(line.lstrip("# ") for line in header.splitlines()[:30])


def _terms(doc):
    """Every `(name, body)` of the vocabulary file, whatever section holds it."""
    for value in doc.values():
        if isinstance(value, dict):
            for name, body in value.items():
                if isinstance(body, dict) and "means" in body:
                    yield name, body


# --- `TRC-A22` -----------------------------------------------------------------------------

def test_trc_a22():
    """The compatibility corpus moves with a major preset bump, and only it."""
    import sys
    sys.path.insert(0, str(ROOT / "tests"))
    import test_frozen_files_unchanged as frozen
    corpus = ROOT / "tests" / "fixtures" / "compat" / "contract-4-commands.yml"
    entries = {e["id"]: e for e in
               yaml.safe_load(corpus.read_text(encoding="utf-8"))["entries"]}
    assert entries["policy-effective-shipped"]["stdout_contains"] == "default@8.0.0"
    assert entries["policy-update-major-not-kept"]["argv"] == ["policy", "update", "--to", "9"]
    text = corpus.read_text(encoding="utf-8")
    for entry in ("policy-effective-shipped", "policy-update-major-not-kept"):
        body = text[text.index(f"- id: {entry}\n"):].split("\n- id:", 1)[0]
        said = " ".join(line.strip().lstrip("#").strip() for line in body.splitlines())
        assert "a major preset bump moves it" in said and "jed72, 2026-10-30" in said, entry
    assert frozen.digest_problems(ROOT, frozen._pinned()) == []


# --- `TRC-A23` -----------------------------------------------------------------------------

@pytest.mark.parametrize("major, applies", [(6, False), (7, False), (8, True)])
def test_trc_a23(tmp_path, major, applies):
    """A project pinned to an earlier major does not get the strategy."""
    project = support.Project(tmp_path / "repo")
    project.setting(None, extends=f"compass:default@{major}")
    issue = project.issue("change")
    code, out, err = issue.assess()
    assert code == 0, out + err
    assert ("acceptance_strategy" in issue.manifest()) is applies
    issue.red()
    code, document = issue.check()
    assert bool([c for c in document["checks"] if c["name"] == CHECK]) is applies
    line = _strategy_line(issue.approach_record())
    if applies:
        assert "(`S17`): applies - " in line, line
    else:
        assert f"project extends compass:default@{major}, before the strategy" in line, line
        assert "assessed before the strategy shipped" not in line, line


# --- `TRC-A24` -----------------------------------------------------------------------------

def test_trc_a24(tmp_path):
    """A shipping approach cannot suspend the strategy; the spike keeps `suspended`."""
    import sys
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import acceptance_strategy, policy_lint
    project = support.Project(tmp_path / "repo")
    project.setting(None, approaches={"regular": {"set": {"acceptance_strategy": "suspended"}}})
    code, out, err = project.run("policy", "lint")
    assert code != 0, out + err
    assert "acceptance_strategy: {state: off, reason:" in out + err, out + err
    issue = project.issue("change")
    code, out, err = issue.assess()
    assert code == 2, out + err
    assert "acceptance_strategy: {state: off, reason:" in out + err, out + err
    shipped, _ = policy_lint.load_parent()
    assert acceptance_strategy.approach_routing(shipped.doc, "spike") == "suspended"


def test_trc_a3_a_quick_fix_started_as_validation_costs_nothing(tmp_path):
    """The quick-fix path records the expected kind too, so a docs quick fix
    gets no strategy finding (`TRC-A3`)."""
    project = support.Project(tmp_path / "repo")
    code, out, err = project.run(
        "quick-fix", "start", "docs", "--risk", "trivial - a docs edit",
        "--familiarity", "brownfield-mapped - known file", "--size", "atomic - one line",
        "--intent", "The README names the command.",
        "--scenario", "A reader finds the command in the README",
        "--test", "tests/test_readme.py::test_names_the_command",
        "--expected-acceptance", "validation")
    assert code == 0, out + err
    issue = support.Issue(project, "docs")
    assert issue.manifest()["acceptance_strategy"]["expected_acceptance"] == "validation"
    issue.acceptance_start("validation")
    assert support.strategy_findings(issue.check()[1]) == []


def test_trc_a13_an_empty_key_is_refused(tmp_path):
    """`acceptance_strategy:` with no value is refused, as the lint refuses it (`TRC-A13`)."""
    project = support.Project(tmp_path / "repo")
    issue = project.issue("change")
    assert issue.assess()[0] == 0
    (project.root / "compass.yml").write_text("schema: 1\nacceptance_strategy:\n",
                                              encoding="utf-8")
    for argv in (("check", "--issue", "change"), ("approach", "evaluate", "--issue", "change")):
        code, out, err = issue.run(*argv)
        assert code == 2 and "acceptance_strategy" in out + err, (argv, out + err)


def test_trc_a23_a_pinned_compass_yml_still_passes_its_schema(tmp_path):
    """The strategy ignores the setting in a pinned project, but `compass.yml`
    must still pass its schema check, so an issue with no stored configuration
    is refused (`TRC-A23`)."""
    project = support.Project(tmp_path / "repo")
    issue = project.issue("change")
    (project.root / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@7\nacceptance_strategy: maybe\n", encoding="utf-8")
    code, out, err = issue.run("check", "--issue", "change")
    assert code == 2 and "acceptance_strategy" in out + err, out + err


def test_trc_a23_a_bad_setting_does_not_stop_a_pinned_project(tmp_path):
    """The strategy's setting is not read in a project pinned before it (`TRC-A23`)."""
    project = support.Project(tmp_path / "repo")
    issue = project.issue("change")
    project.setting(None, extends="compass:default@7")
    assert issue.assess()[0] == 0
    (project.root / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@7\nacceptance_strategy: maybe\n", encoding="utf-8")
    assert issue.run("check", "--issue", "change")[0] != 2
    assert project.run("retro", "--acceptance")[0] == 0


def test_trc_a23_a_changed_pin_never_blocks_the_record(tmp_path):
    """The pin line comes from the project's `compass.yml`, not the issue's own
    records, so a changed `extends:` makes the block stale only as an advisory,
    as for any block drawn from the project (`TRC-A23`)."""
    project = support.Project(tmp_path / "repo")
    project.setting(None, extends="compass:default@6")
    issue = project.issue("change")
    assert issue.assess()[0] == 0
    issue.approach_record()
    body = issue.manifest()
    body["current_phase"] = "verify"
    issue.write_manifest(body)
    assert issue.run("issue", "render", "--issue", "change")[0] == 0

    def status():
        rows = [c for c in issue.check()[1]["checks"] if c["name"] == "rendered-blocks-current"]
        return rows[0]["status"]

    assert status() == "pass"
    project.setting(None, extends="compass:default@8")
    assert status() == "advisory"
