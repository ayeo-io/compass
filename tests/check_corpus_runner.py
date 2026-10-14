"""Builds each check-corpus case and computes the verdict the check gives.

ADR-038 makes the corpus the only evidence that a check's behaviour held
across a release, so a case must run the implementation rather than record a
label. Each case is a function here that writes the small project the check
reads (a manifest, evidence files, a document) into a temporary directory.
`run_case` then calls the implementation from the registry on it and maps
the result to `pass`, `fail` or `nothing-to-check`. The verdict is never
read from `expected.yml`; the test compares the two.

Every implementation has a `broken` case (the input its mutation proof breaks)
and a `restored` case (the input put right, or an input the check declines).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

from compass_pkg import check_registry
from compass_pkg.check_results import NOTHING_TO_CHECK

ROOT = Path(__file__).resolve().parent.parent
SLUG = "case"
CASES: dict[tuple[str, str], object] = {}


def case(impl: str, name: str):
    def register(fn):
        CASES[(impl, name)] = fn
        return fn
    return register


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _issue(root: Path, manifest: dict, slug: str = SLUG) -> tuple[dict, Path]:
    """Write `manifest` as the record of issue `slug` under a project at `root`."""
    task_dir = root / ".compass" / "work" / slug
    task_dir.mkdir(parents=True, exist_ok=True)
    manifest = dict(manifest, task=slug)
    _write(task_dir / "manifest.yml", yaml.safe_dump(manifest, sort_keys=False))
    return manifest, task_dir


def _scenario(**extra) -> dict:
    return dict({"id": "S-1", "intent": "INT-1"}, **extra)


def verdict(result) -> str:
    passed = result[0]
    if passed is NOTHING_TO_CHECK:
        return "nothing-to-check"
    return "pass" if passed else "fail"


def run_case(impl: str, name: str, root: Path) -> str:
    """Build the case under `root` and return the implementation's verdict."""
    task, task_dir = CASES[(impl, name)](root)
    fn = check_registry.REGISTRY[impl].fn
    here = os.getcwd()
    os.chdir(root)
    try:
        return verdict(fn(task, str(task_dir)))
    finally:
        os.chdir(here)


def computed_verdicts(impl: str, scratch: Path) -> dict[str, str]:
    out = {}
    for (name_impl, name) in sorted(CASES):
        if name_impl == impl:
            root = scratch / impl / name
            root.mkdir(parents=True)
            out[name] = run_case(impl, name, root)
    return out


# --- scenario and trace checks -----------------------------------------------------

@case("scenarios-have-tests", "broken")
def _(root):
    return _issue(root, {"scenarios": [_scenario()]})


@case("scenarios-have-tests", "restored")
def _(root):
    return _issue(root, {"scenarios": [_scenario(tests=["tests/test_a.py"])]})


@case("scenario-has-id-and-intent", "broken")
def _(root):
    return _issue(root, {"scenarios": [{"id": "S-1"}]})


@case("scenario-has-id-and-intent", "restored")
def _(root):
    return _issue(root, {"scenarios": [_scenario()]})


@case("changed-code-traces-to-scenario", "broken")
def _(root):
    return _issue(root, {"scenarios": [_scenario()],
                         "changed_files": [{"path": "src/a.py"}]})


@case("changed-code-traces-to-scenario", "restored")
def _(root):
    _write(root / "src" / "a.py", "x = 1\n")
    return _issue(root, {"scenarios": [_scenario()],
                         "changed_files": [{"path": "src/a.py",
                                            "scenarios": ["S-1"]}]})


@case("claim-traces-to-scenario", "broken")
def _(root):
    return _issue(root, {"scenarios": [_scenario()],
                         "claims": [{"id": "C-1", "scenario": "S-9"}]})


@case("claim-traces-to-scenario", "restored")
def _(root):
    return _issue(root, {"scenarios": [_scenario()],
                         "claims": [{"id": "C-1", "scenario": "S-1"}]})


@case("declared-tests-resolve", "broken")
def _(root):
    _write(root / "tests" / "test_a.py", "def test_other():\n    pass\n")
    return _issue(root, {"gates": [{"id": "verify.correctness", "status": "pass"}],
                         "scenarios": [_scenario(
                             tests=["tests/test_a.py::test_missing"])]})


@case("declared-tests-resolve", "restored")
def _(root):
    _write(root / "tests" / "test_a.py", "def test_there():\n    pass\n")
    return _issue(root, {"gates": [{"id": "verify.correctness", "status": "pass"}],
                         "scenarios": [_scenario(
                             tests=["tests/test_a.py::test_there"])]})


@case("scenarios-are-executable", "broken")
def _(root):
    _write(root / ".compass" / "config.yml", "project:\n  bdd_runner: behave\n")
    return _issue(root, {"scenarios": [_scenario()]})


@case("scenarios-are-executable", "restored")
def _(root):
    _write(root / ".compass" / "config.yml", "project:\n  bdd_runner: behave\n")
    task, task_dir = _issue(root, {"scenarios": [_scenario()]})
    spec = "# Acceptance criteria\n\nS-1\n"
    _write(task_dir / "acceptance-criteria.md", spec)
    _write(task_dir / "evidence" / "bdd-run.json", json.dumps({
        "spec_sha256": hashlib.sha256(spec.encode()).hexdigest(),
        "scenarios_seen": ["S-1"]}))
    return task, task_dir


# --- evidence checks ---------------------------------------------------------------

def _record(task_dir: Path, name: str, body: dict) -> str:
    _write(task_dir / "evidence" / name, json.dumps(body))
    return f"evidence/{name}"


@case("suite-passed", "broken")
def _(root):
    return _issue(root, {})


@case("suite-passed", "restored")
def _(root):
    task, task_dir = _issue(root, {})
    path = _record(task_dir, "green.json", {"exit_code": 0})
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path}]
    return task, task_dir


@case("gate-evidence-present", "broken")
def _(root):
    return _issue(root, {"gates": [{"id": "verify.correctness",
                                    "status": "pass", "evidence": []}]})


@case("gate-evidence-present", "restored")
def _(root):
    task, task_dir = _issue(root, {})
    path = _record(task_dir, "green.json", {"exit_code": 0})
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path}]
    task["gates"] = [{"id": "verify.correctness", "status": "pass",
                      "evidence": ["EV-1"]}]
    return task, task_dir


@case("human-approval-present", "broken")
def _(root):
    return _issue(root, {})


@case("human-approval-present", "restored")
def _(root):
    return _issue(root, {"evidence": [{
        "id": "EV-1", "type": "human-approval", "decision": "approved",
        "approver": "jed72", "role": "maintainer", "scope": "the change",
        "timestamp": "2026-10-06T10:00:00Z"}]})


@case("backfills-paid", "broken")
def _(root):
    return _issue(root, {"follow_ups": [{"id": "FU-1", "status": "outstanding"}]})


@case("backfills-paid", "restored")
def _(root):
    return _issue(root, {"follow_ups": [{"id": "FU-1", "status": "resolved"}]})


def _approved_issue(root, status):
    return _issue(root, {
        "delivery_approach": "regular",
        "gates": [{"id": "verify.correctness", "status": "pass", "evidence": ["EV-1"]}],
        "artifacts": [{"id": "ART-TECHNICAL_DESIGN", "kind": "technical-design",
                       "status": status, "path": "docs/technical-design.md",
                       "reason": "every regular approach carries one"}]})


@case("artifacts-approved", "broken")
def _(root):
    return _approved_issue(root, "draft")


@case("artifacts-approved", "restored")
def _(root):
    return _approved_issue(root, "approved")


@case("spike-conclusion-present", "broken")
def _(root):
    return _issue(root, {})


@case("spike-conclusion-present", "restored")
def _(root):
    return _issue(root, {"evidence": [{"id": "EV-1", "type": "spike-conclusion",
                                       "decision": "discard"}]})


@case("spike-no-production-changes", "broken")
def _(root):
    return _issue(root, {"changed_files": [{"path": "src/a.py"}]})


@case("spike-no-production-changes", "restored")
def _(root):
    return _issue(root, {})


@case("consistency-check-passes", "broken")
def _(root):
    return _issue(root, {"gates": [{"id": "verify.analyze", "status": "pending"}]})


@case("consistency-check-passes", "restored")
def _(root):
    task, task_dir = _issue(root, {})
    path = _record(task_dir, "analyze.json", {"finding_count": 0})
    task["gates"] = [{"id": "verify.analyze", "status": "pending"}]
    task["evidence"] = [{"id": "EV-1", "type": "consistency-check", "path": path}]
    return task, task_dir


def _rerun(root, attempts):
    task, task_dir = _issue(root, {})
    path = _record(task_dir, "green.json", {"exit_code": 0, "attempts": attempts,
                                            "rerun_without_change": attempts > 1,
                                            "test": "tests/test_a.py::test_x"})
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path}]
    return task, task_dir


@case("no-trusted-rerun", "broken")
def _(root):
    return _rerun(root, 2)


@case("no-trusted-rerun", "restored")
def _(root):
    return _rerun(root, 1)


def _stamped(root, record_on_disk):
    task, task_dir = _issue(root, {})
    path = _record(task_dir, "green.json", record_on_disk)
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path,
                         "record_id": "rec-a"}]
    return task, task_dir


@case("evidence-identity-matches", "broken")
def _(root):
    return _stamped(root, {"record_id": "rec-b"})


@case("evidence-identity-matches", "restored")
def _(root):
    return _stamped(root, {"record_id": "rec-a"})


_DOD_ITEMS = ["dod-every-scenario-passes", "dod-suite-green", "dod-coverage-floor",
              "dod-no-lint-errors", "dod-traceability-intact", "dod-living-docs-updated",
              "dod-follow-ups-settled"]


def _dod(root, page, evidence=()):
    """A project on the shipped default, so the check finds the seven items of the
    `verify` exit list, and an issue whose verification report is `page`."""
    _write(root / "compass.yml", "schema: 1\n")
    task, task_dir = _issue(root, {"evidence": list(evidence)})
    _write(task_dir / "verification-report.md", page)
    return task, task_dir


@case("dod-evidence-typed", "broken")
def _(root):
    # An item with no record in the manifest.
    return _dod(root, "## Definition of Done\n\n- [ ] the thing is done\n")


@case("dod-evidence-typed", "restored")
def _(root):
    # A ticked box on the page, and still no record: the page counts for nothing.
    return _dod(root, "## Definition of Done\n\n- [x] the thing is done\n")


@case("dod-evidence-typed", "recorded")
def _(root):
    records = [{"id": "EV-%d" % n, "type": "manual-review", "path": "evidence/x.txt",
                "meets": [item]} for n, item in enumerate(_DOD_ITEMS)]
    return _dod(root, "## Definition of Done\n", records)


# --- checks that read a document or another issue ----------------------------------

@case("borrowed-documents-answered", "broken")
def _(root):
    task, task_dir = _issue(root, {})
    _write(task_dir / "threat-model.md",
           "| Threat | Answer |\n|---|---|\n| data loss on upgrade | none yet |\n")
    return task, task_dir


@case("borrowed-documents-answered", "restored")
def _(root):
    task, task_dir = _issue(root, {})
    _write(task_dir / "threat-model.md",
           "| Threat | Answer |\n|---|---|\n| data loss on upgrade | TRC-A1 |\n")
    return task, task_dir


def _rendered(root, stale):
    """An issue at `verify` whose acceptance criteria hold a coverage block and
    whose issue page exists, rendered. With `stale`, the block was edited by hand."""
    from compass_pkg import render_cmd
    task, task_dir = _issue(root, {
        "created": "2026-10-10", "current_phase": "verify",
        "scenarios": [_scenario(title="A scenario")],
        "artifacts": [{"id": "ART-AC", "kind": "acceptance-criteria", "status": "draft",
                       "path": "docs/compass/2026-10-10-case/acceptance-criteria.md"}]})
    doc = root / "docs" / "compass" / "2026-10-10-case" / "acceptance-criteria.md"
    _write(doc, "# Spec\n\n<!-- compass:render coverage -->\n<!-- /compass:render -->\n")
    render_cmd.apply(render_cmd.plan_issue(str(task_dir)))
    if stale:
        doc.write_text(doc.read_text(encoding="utf-8").replace("Coverage: 0 of 1",
                                                                "Coverage: 1 of 1"),
                       encoding="utf-8")
    return task, task_dir


@case("rendered-blocks-current", "broken")
def _(root):
    return _rendered(root, True)


@case("rendered-blocks-current", "restored")
def _(root):
    return _rendered(root, False)


def _landed_by(root, delivered):
    task, task_dir = _issue(root, {"status": "landed",
                                   "landed_by": [{"issue": "other"}]})
    _issue(root, {"status": "landed", "scenarios": [_scenario()],
                  "delivered": [SLUG] if delivered else []}, slug="other")
    return task, task_dir


@case("landed-by-resolves", "broken")
def _(root):
    return _landed_by(root, False)


@case("landed-by-resolves", "restored")
def _(root):
    return _landed_by(root, True)


def _multiagent(root, subtasks):
    return _issue(root, {"status": "landed", "created": "2026-01-01",
                         "stages": {"breakdown": "multiagent"},
                         "subtasks": subtasks})


@case("multiagent-run-recorded", "broken")
def _(root):
    return _multiagent(root, [])


@case("multiagent-run-recorded", "restored")
def _(root):
    return _multiagent(root, [{"id": "subtask-1", "status": "done",
                               "review_rounds": [{"verdict": "pass"}]}])


# --- checks that read one section of the spec or the design (ADR-064) ---------------
#
# Each corpus holds the archive shapes the checks must decline to judge: no `generation`
# key, a closed issue, a document not registered with a path, a catalogue that does not
# list the section, and a registry entry with no depth. In each the document lacks the
# section, so a check that judged the shape would fail it.

_SECTION_FILES = {"acceptance-criteria": "docs/spec.md", "technical-design": "docs/design.md"}
_NO_SECTION = "# A document written before the section existed\n\nNo such section.\n"


def _sectioned(root, kind, doc, *, generation=True, closed=False, registered=True,
               depth="thorough", sections=None, changed=()):
    """An issue in a project with a `compass.yml`, registering `kind` at `depth` with
    the document `doc`. With `generation`, its configuration is committed as generation
    1 from the shipped default; `sections` replaces the catalogue's sections of `kind`
    in that configuration. `closed` marks the issue done once it is committed."""
    from compass_pkg import effective
    from compass_pkg.core import load_manifest

    layer = {"schema": 1}
    if sections is not None:
        layer["artifacts"] = {kind: {"set": {"sections": sections}}}
    _write(root / "compass.yml", yaml.safe_dump(layer, sort_keys=False))
    entry = {"id": "ART-" + kind.upper().replace("-", "_"), "kind": kind, "status": "draft"}
    if depth:
        entry["depth"] = depth
    if registered:
        entry["path"] = _SECTION_FILES[kind]
        _write(root / _SECTION_FILES[kind], doc)
    _, task_dir = _issue(root, {
        "schema_version": "3.0", "issue": SLUG, "created": "2026-10-14",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "medium", "goal": "delivery", "role": "engineer",
                       "labels": []},
        "delivery_approach": "regular", "evidence": [],
        "scenarios": [_scenario(title="Export is fast")],
        "artifacts": [entry], "changed_files": list(changed)})
    if generation:
        effective.commit_generation(str(task_dir), load_manifest(str(task_dir))[0])
    if closed:
        task, _ = load_manifest(str(task_dir))
        _write(task_dir / "manifest.yml", yaml.safe_dump(dict(task, status="done"),
                                                         sort_keys=False))
    return load_manifest(str(task_dir))[0], task_dir


def _declining_cases(impl, kind):
    """Register the five declining shapes for `impl`, which reads `kind`."""
    shapes = {
        "no-generation": ("an issue with no generation key, whose document lacks the section",
                          {"generation": False}),
        "closed": ("a closed issue on a generation that declares the check, whose document "
                   "lacks the section", {"closed": True}),
        "not-registered": ("an open issue on a generation that declares the check, with "
                           "the document not registered with a path", {"registered": False}),
        "no-section": ("an open issue on a generation that declares the check, whose "
                       "catalogue does not list the section", {"sections": {
                           "thorough": ["Summary"], "lightweight": ["Summary"]}}),
        "no-depth": ("an open issue on a generation that declares the check, whose registry "
                     "entry has no depth key", {"depth": None}),
    }
    for name, (_, options) in shapes.items():
        def build(root, options=options):
            return _sectioned(root, kind, _NO_SECTION, changed=_CONTRACT_CHANGE, **options)
        CASES[(impl, name)] = build
    return {name: text for name, (text, _) in shapes.items()}


#: A changed file that is a trigger path of `contracts-declared`; the spec check ignores it.
_CONTRACT_CHANGE = ({"path": "schemas/manifest.schema.json", "scenarios": ["S-1"]},)

_NFR_SPEC = """\
# Spec

### Scenario: Export is fast
<!-- traceability id: S-1 · serves: INT-1 -->

```gherkin
Scenario: Export is fast
  When the ledger is exported
  Then the file is written within 3 seconds
```

## Non-functional requirements

| Concern | Scenario | Reason it does not apply |
|---|---|---|
| performance | S-1 | |
| capacity | | No stored data grows. |
| compatibility | | Nothing stored changes shape. |
| security | {security} |
| privacy | | No personal data is read. |
| operability | | Nothing runs unattended. |
| accessibility | | No interface changes. |
"""

NFR_DECLINING = _declining_cases("nfr-rows-resolved", "acceptance-criteria")


@case("nfr-rows-resolved", "broken")
def _(root):
    return _sectioned(root, "acceptance-criteria", _NFR_SPEC.format(security=" | "))


@case("nfr-rows-resolved", "restored")
def _(root):
    return _sectioned(root, "acceptance-criteria",
                      _NFR_SPEC.format(security=" | No input crosses a trust boundary. "))


_DESIGN = """\
# Plan

## Data and interfaces

<!-- A field table here would not count: it sits in a comment.
| Name | Type | Required | Meaning | Written by | Read by |
|---|---|---|---|---|---|
| a | b | c | d | e | f |
-->

{body}
## Gate

None.
"""

CONTRACTS_DECLINING = _declining_cases("contracts-declared", "technical-design")


@case("contracts-declared", "broken")
def _(root):
    return _sectioned(root, "technical-design", _DESIGN.format(body="None.\n"),
                      changed=_CONTRACT_CHANGE)


@case("contracts-declared", "restored")
def _(root):
    table = ("| Name | Type | Required | Meaning | Written by | Read by |\n"
             "|---|---|---|---|---|---|\n"
             "| `generation` | integer | no | the stored configuration | assess | check |\n")
    return _sectioned(root, "technical-design", _DESIGN.format(body=table),
                      changed=_CONTRACT_CHANGE)


# --- checks that read git or run a project command ---------------------------------

def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   cwd=root, check=True, capture_output=True)


@case("evidence-matches-tree", "broken")
def _(root):
    task, task_dir = _issue(root, {"status": "landed", "land_commit": "not-a-commit"})
    path = _record(task_dir, "green.json", {"exit_code": 0, "tree_id": "a" * 40,
                                            "timestamp": "2026-10-06T10:00:00Z"})
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path}]
    return task, task_dir


@case("evidence-matches-tree", "restored")
def _(root):
    from compass_pkg.binding import claimed_paths, work_tree_id
    _write(root / "src" / "a.py", "x = 1\n")
    _git(root, "init", "-q")
    _git(root, "add", "src/a.py")
    _git(root, "commit", "-q", "-m", "seed")
    task, task_dir = _issue(root, {"changed_files": [{"path": "src/a.py",
                                                      "scenarios": ["S-1"]}]})
    tree = work_tree_id(str(root), claimed_paths(task))
    path = _record(task_dir, "green.json", {"exit_code": 0, "tree_id": tree,
                                            "timestamp": "2026-10-06T10:00:00Z"})
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path}]
    return task, task_dir


@case("command-passes", "broken")
def _(root):
    gov = root / "governance"
    gov.mkdir()
    for name in ("routing-policy.yml", "guardrails.yml"):
        shutil.copy(ROOT / "governance" / name, gov / name)
    rules = yaml.safe_load((gov / "guardrails.yml").read_text(encoding="utf-8"))
    rules["project"] = [{"id": "P-1", "name": "fails", "checks": ["command-passes"],
                         "params": {"command": "false"}}]
    _write(gov / "guardrails.yml", yaml.safe_dump(rules, sort_keys=False))
    _write(root / ".compass" / "config.yml", "allow_project_commands: true\n")
    return _issue(root, {})


# No project guardrail declares a command, so the check has nothing to run.
@case("command-passes", "restored")
def _(root):
    return _issue(root, {})
