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
    1 from the shipped default; `sections` gives that stored generation a catalogue
    entry for `kind` with those sections. `closed` marks the issue done once it is
    committed.

    Since 9.0.0 a project layer cannot set the catalogue (ADR-091), so `sections` is
    written into the resolution before it is stored. That is the generation an issue
    configured before 9.0.0 still holds."""
    from compass_pkg import effective, project_settings
    from compass_pkg.core import load_manifest

    _write(root / "compass.yml", yaml.safe_dump({"schema": 1}, sort_keys=False))
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
        manifest = load_manifest(str(task_dir))[0]
        resolution = None
        if sections is not None:
            resolution = effective.resolve_live(project_settings.find_project_root(str(task_dir)),
                                                manifest, SLUG, str(task_dir))
            resolution.resolved.setdefault("artifacts", {})[kind] = {"sections": sections}
        effective.commit_generation(str(task_dir), manifest, resolution=resolution)
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


# The four-layer acceptance strategy's advisory check compares the block assess
# stored with what the red and acceptance records decide.
def _strategy_block(applies, why):
    return {"acceptance_strategy": {
        "state": "on", "routing": "on",
        "expected_acceptance": "none" if applies else "validation",
        "applies": applies, "why": why}}


def _strategy_red(task_dir):
    _record(task_dir, "red.json", {"passed": False, "exit_code": 1,
                                   "timestamp": "2026-10-29T10:00:00Z"})


# Assess expected an acceptance of kind validation, and a red is on record.
@case("acceptance-applicability-agrees", "broken")
def _(root):
    task, task_dir = _issue(root, _strategy_block(False, "acceptance of kind validation"))
    _strategy_red(task_dir)
    return task, task_dir


@case("acceptance-applicability-agrees", "restored")
def _(root):
    task, task_dir = _issue(root, _strategy_block(True, "client-observable behavior"))
    _strategy_red(task_dir)
    return task, task_dir


# A suspended routing takes the issue out of scope, so a red on record does not count.
@case("acceptance-applicability-agrees", "suspended")
def _(root):
    block = _strategy_block(False, "suspended on the regular approach by the project")
    block["acceptance_strategy"]["routing"] = "suspended"
    task, task_dir = _issue(root, block)
    _strategy_red(task_dir)
    return task, task_dir


# An issue assessed before the strategy shipped holds no block.
@case("acceptance-applicability-agrees", "no-block")
def _(root):
    task, task_dir = _issue(root, {})
    _strategy_red(task_dir)
    return task, task_dir


# The outer-loop check reads the loop of the red and green records of an issue in scope.
# An outer-loop green also names its candidate and client (ADR-085).
def _loop_records(task, task_dir, loop):
    marked = {"loop": loop} if loop else {}
    named = {"candidate": "build-417", "candidate_kind": "deployed",
             "client": "api"} if loop == "outer" else {}
    _record(task_dir, "red.json", {"passed": False, "exit_code": 1,
                                   "timestamp": "2026-10-29T10:00:00Z", **marked})
    path = _record(task_dir, "green.json", {"passed": True, "exit_code": 0,
                                            "timestamp": "2026-10-29T11:00:00Z", **marked,
                                            **named})
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path}]
    return task, task_dir


# A red and a green with no loop field read as inner, so the outer loop is missing.
@case("outer-loop-recorded", "broken")
def _(root):
    task, task_dir = _issue(root, _strategy_block(True, "client-observable behavior"))
    return _loop_records(task, task_dir, None)


@case("outer-loop-recorded", "restored")
def _(root):
    task, task_dir = _issue(root, _strategy_block(True, "client-observable behavior"))
    return _loop_records(task, task_dir, "outer")


# A suspended routing takes the issue out of scope, so inner-loop records are enough.
@case("outer-loop-recorded", "suspended")
def _(root):
    block = _strategy_block(False, "suspended on the regular approach by the project")
    block["acceptance_strategy"]["routing"] = "suspended"
    task, task_dir = _issue(root, block)
    return _loop_records(task, task_dir, "inner")


# The support-code check tests only that each path the project names exists.
_SUPPORT_PATHS = {"alias_helper": "tests/acceptance/alias.py",
                  "driver_factory": "conftest.py",
                  "dsl_root": "tests/acceptance/dsl.py",
                  "layering_test": "tests/acceptance/test_layering.py"}


def _support_project(root, present):
    """Name every piece in `compass.yml` and write the files of those in `present`."""
    _write(root / "compass.yml", yaml.safe_dump(
        {"schema": 1, "project": {"acceptance_support": _SUPPORT_PATHS}}, sort_keys=False))
    for key in present:
        _write(root / _SUPPORT_PATHS[key], "# support code\n")


# An in-scope issue with a green, in a project that names every piece but has built no
# alias helper. With no green the check has nothing to judge.
@case("acceptance-support-present", "broken")
def _(root):
    _support_project(root, ("driver_factory", "dsl_root", "layering_test"))
    task, task_dir = _issue(root, _strategy_block(True, "client-observable behavior"))
    return _loop_records(task, task_dir, "outer")


@case("acceptance-support-present", "restored")
def _(root):
    _support_project(root, tuple(_SUPPORT_PATHS))
    task, task_dir = _issue(root, _strategy_block(True, "client-observable behavior"))
    return _loop_records(task, task_dir, "outer")


# A suspended routing takes the issue out of scope, so missing support code is not judged.
@case("acceptance-support-present", "suspended")
def _(root):
    block = _strategy_block(False, "suspended on the regular approach by the project")
    block["acceptance_strategy"]["routing"] = "suspended"
    task, task_dir = _issue(root, block)
    _strategy_red(task_dir)
    return task, task_dir


# The `attempts` check reads `attempts` on each registered outer-loop green of an issue in scope.
def _outer_green(task, task_dir, **attempts):
    _record(task_dir, "red.outer.json", {"passed": False, "exit_code": 1, "loop": "outer",
                                         "timestamp": "2026-10-29T10:00:00Z"})
    path = _record(task_dir, "green.outer.json", {"passed": True, "exit_code": 0,
                                                  "loop": "outer", **attempts,
                                                  "timestamp": "2026-10-29T11:00:00Z"})
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path}]
    return task, task_dir


# An outer-loop green with no `attempts` field, as a record from before the field.
@case("outer-loop-attempts-recorded", "broken")
def _(root):
    task, task_dir = _issue(root, _strategy_block(True, "client-observable behavior"))
    return _outer_green(task, task_dir)


@case("outer-loop-attempts-recorded", "restored")
def _(root):
    task, task_dir = _issue(root, _strategy_block(True, "client-observable behavior"))
    return _outer_green(task, task_dir, attempts=1)


# An acceptance of kind validation and no red takes the issue out of scope.
@case("outer-loop-attempts-recorded", "validation")
def _(root):
    task, task_dir = _issue(root, _strategy_block(False, "acceptance of kind validation"))
    path = _record(task_dir, "green.outer.json", {"passed": True, "exit_code": 0,
                                                  "loop": "outer", "kind": "validation"})
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path}]
    return task, task_dir


# The isolation and layering checks read the record their command wrote (ADR-086).
# Each is stamped and registered with its identity, as its command writes it; a
# record without one is a written note and fails (ADR-086).
def _strategy_record(task, task_dir, kind, body):
    from compass_pkg.red_first import content_digest
    name = "isolation-proof.json" if kind == "isolation-proof" else "layering.json"
    body = dict(body, record_id="corpus-" + kind)
    body["content_digest"] = content_digest(body)
    path = _record(task_dir, name, body)
    task["scenarios"] = [_scenario(tests=["tests/acceptance/test_orders.py::test_place"])]
    task["evidence"] = [{"id": "EV-1", "type": kind, "path": path,
                         "record_id": body["record_id"],
                         "content_digest": body["content_digest"]}]
    return task, task_dir


def _proof(parallel=0):
    return {"type": "isolation-proof", "candidate": "build-417", "candidate_kind": "deployed",
            "client": "api", "parallel": {"command": "run -n 2", "exit_code": parallel},
            "repeat": [{"scenario": "S-1", "tests": ["tests/acceptance/test_orders.py::test_place"],
                        "runs": [0, 0], "same": True}]}


def _routed(routing):
    block = _strategy_block(True, "client-observable behavior")
    block["acceptance_strategy"]["routing"] = routing
    return block


@case("isolation-proven", "broken")
def _(root):
    task, task_dir = _issue(root, _strategy_block(True, "client-observable behavior"))
    return _strategy_record(task, task_dir, "isolation-proof", _proof(parallel=1))


@case("isolation-proven", "restored")
def _(root):
    task, task_dir = _issue(root, _strategy_block(True, "client-observable behavior"))
    return _strategy_record(task, task_dir, "isolation-proof", _proof())


# The quick fix's routing reuses the existing DSL and needs no isolation proof.
@case("isolation-proven", "quick-fix")
def _(root):
    task, task_dir = _issue(root, _routed("existing-dsl"))
    return _strategy_record(task, task_dir, "isolation-proof", _proof(parallel=1))


@case("layering-test-passed", "broken")
def _(root):
    task, task_dir = _issue(root, _strategy_block(True, "client-observable behavior"))
    return _strategy_record(task, task_dir, "layering", {
        "type": "layering", "command": "run layering", "exit_code": 1, "tests_ran": 3})


@case("layering-test-passed", "restored")
def _(root):
    task, task_dir = _issue(root, _strategy_block(True, "client-observable behavior"))
    return _strategy_record(task, task_dir, "layering", {
        "type": "layering", "command": "run layering", "exit_code": 0, "tests_ran": 3})


# The hotfix's routing needs the isolation proof and no layering record.
@case("layering-test-passed", "hotfix")
def _(root):
    task, task_dir = _issue(root, _routed("existing-dsl-isolation"))
    return task, task_dir
