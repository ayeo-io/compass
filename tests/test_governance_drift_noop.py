"""Invariants for governance drift detection (issue governance-drift-detection).

This issue has critical risk, and the one unacceptable outcome is changing
how delivery approaches are computed. A drift detector that changes routing
is worse than the silent drift it was built to find.

The other properties here are about trust. A detector that fires on a project
which is current, or which has never run `/compass:init`, or which is AHEAD of
the framework, is a detector that gets switched off - and then it detects
nothing at all.

Spec: governance-drift-detection/acceptance-criteria.md (`TRC-F1`..`TRC-F6`).
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GOVERNANCE = ROOT / "governance"
FIXTURES = ROOT / "tests" / "fixtures" / "routes"


def _clean_project(tmp_path, *, local_governance=True):
    proj = tmp_path / "proj"
    (proj / ".compass" / "work").mkdir(parents=True)
    (proj / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    if local_governance:
        shutil.copytree(GOVERNANCE, proj / "governance")
    return proj


def _lint(proj):
    return subprocess.run([sys.executable, str(CLI), "policy", "lint"],
                          cwd=str(proj), capture_output=True, text=True, timeout=60)


# ---------------------------------------------------------------------------
# `TRC-F1` - a project with current governance sees no drift report
# ---------------------------------------------------------------------------

def test_trc_f1_a_project_with_current_governance_should_see_no_drift_report(tmp_path):
    result = _lint(_clean_project(tmp_path))
    assert result.returncode == 0, result.stdout
    lowered = result.stdout.lower()
    assert "drift" not in lowered and "missing" not in lowered, (
        f"a project whose governance matches the framework is being told it "
        f"has drifted:\n{result.stdout}")


# ---------------------------------------------------------------------------
# `TRC-F2` - a project with no local governance is not compared to itself
# ---------------------------------------------------------------------------

def test_trc_f2_a_project_with_no_local_governance_should_not_be_compared_to_itself(tmp_path):
    # No governance/ of its own: find_governance() falls back to the framework's,
    # so project and framework are literally the same directory.
    result = _lint(_clean_project(tmp_path, local_governance=False))
    assert result.returncode == 0, result.stdout
    lowered = result.stdout.lower()
    assert "drift" not in lowered and "missing" not in lowered, (
        f"a project that never ran init is being told it is missing rules:\n"
        f"{result.stdout}")


# ---------------------------------------------------------------------------
# `TRC-F3` - a project AHEAD of the framework is not drift
# ---------------------------------------------------------------------------

def test_trc_f3_a_project_ahead_of_the_framework_should_not_be_reported_as_drifted(tmp_path):
    proj = _clean_project(tmp_path)
    rp = proj / "governance" / "routing-policy.yml"
    d = yaml.safe_load(rp.read_text())
    d["routing_guardrails"]["floors"].append({
        "id": "PROJ-FLOOR-001",
        "when": {"risk": "critical"},
        "force_minimum_route": "expedition",
        "rationale": "a rule this project added for itself",
    })
    d["routing_guardrails"]["caps"].append({
        "id": "PROJ-CAP-001", "when": {"risk": "critical"},
        "max_worktrees": 2, "rationale": "local coordination limit",
    })
    rp.write_text(yaml.safe_dump(d, sort_keys=False))

    result = _lint(proj)
    assert result.returncode == 0, result.stdout
    assert "missing" not in result.stdout.lower(), (
        f"a project with MORE rules than the framework is reported as missing "
        f"some:\n{result.stdout}")
    assert "PROJ-FLOOR-001" not in result.stdout, (
        f"the project's own rules are reported as errors:\n{result.stdout}")


# ---------------------------------------------------------------------------
# `TRC-F4` - an unreadable framework policy degrades gracefully
# ---------------------------------------------------------------------------

def test_trc_f4_an_unreadable_framework_policy_should_not_break_the_lint(tmp_path):
    """The comparison must never be able to break the validation that existed
    before it. Simulated by pointing the drift function at a broken directory,
    since the real framework policy cannot be corrupted from a test."""
    sys.path.insert(0, str(ROOT / "cli"))
    import importlib.util
    spec = importlib.util.spec_from_loader(
        "compass_cli", importlib.machinery.SourceFileLoader("compass_cli", str(CLI)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    broken = tmp_path / "broken-framework"
    (broken / "governance").mkdir(parents=True)
    (broken / "governance" / "routing-policy.yml").write_text("not: [valid\n")
    (broken / "governance" / "guardrails.yml").write_text("also: [broken\n")

    proj = _clean_project(tmp_path)
    report = mod.governance_drift(str(proj / "governance"),
                                  str(broken / "governance"))
    assert report.comparable is False, "a broken framework policy was compared anyway"
    assert report.reason, "no reason recorded for an impossible comparison"
    assert not report.drifted, "an impossible comparison reported drift"

    # and the lint itself still completes on the real framework
    assert _lint(proj).returncode == 0


# ---------------------------------------------------------------------------
# `TRC-F5` - no computed delivery approach changes. THE guard on this issue's
# critical risk.
# ---------------------------------------------------------------------------

def test_trc_f5_drift_detection_should_not_change_any_computed_route():
    """Every routing fixture must evaluate identically after this change.

    This issue touches `compass approach evaluate`. The one outcome worse
    than silent drift is a drift detector that changes routing, so this
    re-runs the whole fixture corpus and compares the computed delivery
    approach, gates, topology and fired guardrails against what the fixture
    declares.
    """
    fixtures = sorted(FIXTURES.glob("*.yml"))
    assert fixtures, "no routing fixtures found - this guard would be empty"
    total_checks = 0

    for path in fixtures:
        fx = yaml.safe_load(path.read_text())
        readings = fx.get("assessment") or fx.get("readings") or {}
        args = []
        for key, value in readings.items():
            if isinstance(value, list):
                value = ",".join(str(v) for v in value)
            if value in (None, ""):
                continue
            args += ["--assessment", f"{key}={value}"]
        result = subprocess.run(
            [sys.executable, str(CLI), "approach", "evaluate", *args, "--json"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        )
        expect = fx.get("expected") or {}

        # Some fixtures are NEGATIVE: the evaluator must refuse rather than
        # silently promote (e.g. exploration intent that would touch auth).
        # Those must keep refusing, with the same message.
        if expect.get("conflict"):
            assert result.returncode != 0, (
                f"{path.name}: the evaluator stopped refusing a routing "
                f"conflict - it now returns a route where it must not")
            needle = expect.get("conflict_message_contains", "")
            assert needle in (result.stdout + result.stderr), (
                f"{path.name}: the conflict message changed; expected to find "
                f"{needle!r}")
            continue

        assert result.returncode == 0, f"{path.name}: {result.stderr}"
        got = json.loads(result.stdout)

        checked = 0
        if "route" in expect:
            checked += 1
            assert got["delivery_approach"] == expect["delivery_approach"], (
                f"{path.name}: route changed to {got['route']}, expected "
                f"{expect['route']}")
        if "candidate_route" in expect:
            checked += 1
            assert got["candidate_route"] == expect["candidate_route"], (
                f"{path.name}: candidate route changed to "
                f"{got['candidate_route']}")
        if "topology" in expect:
            checked += 1
            assert got["topology"] == expect["topology"], (
                f"{path.name}: topology changed to {got['topology']}")
        if "fired_guardrail_ids" in expect:
            checked += 1
            fired = [g["id"] for g in got.get("policy_rules_fired", [])]
            wanted_ids = expect["fired_guardrail_ids"]
            if isinstance(wanted_ids, str):
                wanted_ids = [wanted_ids]
            for rid in wanted_ids:
                assert rid in fired, (
                    f"{path.name}: {rid} no longer fires; fired={fired}")
        if "has_gate" in expect:
            checked += 1
            wanted = expect["has_gate"]
            if isinstance(wanted, str):        # fixtures use a bare string
                wanted = [wanted]
            for gate in wanted:
                assert gate in got["gates"], (
                    f"{path.name}: gate {gate} is gone; gates={got['gates']}")

        # A fixture that asserts nothing passes without checking anything -
        # the exact failure mode this issue exists to stop.
        assert checked, f"{path.name}: no expectation was actually compared"
        total_checks += checked

    assert total_checks >= len(fixtures), (
        f"only {total_checks} expectations compared across {len(fixtures)} "
        f"fixtures - this guard is weaker than it looks")


# ---------------------------------------------------------------------------
# `TRC-F6` - grew by artifacts and checks only
# ---------------------------------------------------------------------------

EXPECTED_GUARDRAIL_IDS = {"G1", "G2", "G3", "G4", "G5", "S1", "S2"}
# Each verb below is in the set for its own reason. `plan` is the planning
# stage's live command. `intent` reads a brief that already exists, by path
# or https URL, so a team arriving with one does not retype it - a
# top-level group rather than a subverb, because no subverb owns it.
EXPECTED_SUBCOMMANDS = {
    "approach", "bdd", "check", "analyze", "retro", "ci", "tdd-red",
    "tdd-green", "policy", "plan", "intent", "issue", "adr", "rework-scan", "flow",
    "next", "follow-up", "ship-commit", "gate", "scenario", "changed-file",
    "evidence", "terminology",
    "review-rule", "spec",        # `review-rule list` and `spec sync`
    # `init` creates `.compass/config.yml` and `.compass/work/`, and is safe
    # to run twice. It exists because no other command owns initialisation,
    # and the five entry points call it directly.
    "init",
    # `acceptance` is the recorded path for a change with no natural
    # behavioural red - config, docs, a behaviour-preserving refactor. It is a
    # GROUP (`start`, `record`), so later kinds add a subcommand rather than a
    # verb.
    "acceptance",
    # `quick-fix` (`start`, `finish`) runs the quick-fix path's mechanical
    # steps in two calls instead of a dozen, through the same handlers; it
    # adds no guardrail, gate or record. A GROUP, like `acceptance`.
    "quick-fix",
    # decisions-ledger (ADR-027): the settled-decisions ledger. A group of
    # four subcommands; it adds no guardrail or gate, and its history check
    # runs inside the existing `compass ci`.
    "decision",
    "lesson",  # project-lessons (ADR-029)
    "run",  # headless-runner (ADR-030)
    "record",  # delivery-record (ADR-031)
}


def test_trc_f6_the_framework_should_grow_by_artifacts_and_checks_only():
    g = yaml.safe_load((GOVERNANCE / "guardrails.yml").read_text())
    ids = {x["id"] for x in g["defaults"]}
    ids |= {x["id"] for x in g["spike_guardrails"]}
    ids |= {x["id"] for x in (g.get("project") or [])}
    assert ids == EXPECTED_GUARDRAIL_IDS, (
        f"the guardrail id set changed: {sorted(ids ^ EXPECTED_GUARDRAIL_IDS)}")

    policy = yaml.safe_load((GOVERNANCE / "routing-policy.yml").read_text())
    gates = set()
    for shape in policy["route_shapes"].values():
        gates.update(shape.get("gates", []))
    known = {"verify.correctness", "verify.governance", "verify.traceability",
             "verify.regression", "verify.security", "verify.clarity",
             "verify.claims", "verify.analyze", "verify.architecture",
             "spike.conclude"}
    assert gates <= known, f"new gate id(s): {sorted(gates - known)}"

    import re as _re
    out = subprocess.run([sys.executable, str(CLI), "--help"],
                         capture_output=True, text=True, check=True).stdout
    m = _re.search(r"\{([a-zA-Z0-9_,\-]+)\}", out)
    assert m, out
    assert set(m.group(1).split(",")) == EXPECTED_SUBCOMMANDS, (
        "a new top-level CLI verb was added. `compass policy sync` was declined "
        "at Clarify: rewriting the file that defines a project's rules is "
        "destructive and deserves its own Frame.")


# ---------------------------------------------------------------------------
# `TRC-F7` - the evidence types the CLI writes are accepted by the manifest schema
# ---------------------------------------------------------------------------

def test_trc_f7_evidence_types_agree_across_surfaces():
    """Two shipped surfaces must declare the same evidence types.

    `compass analyze` writes a `consistency-check` entry, and
    manifest.schema.json did not accept it - so an issue whose delivery
    approach includes verify.analyze produced evidence its own `compass
    issue lint` rejected. No issue here had hit it, because verify.analyze
    only enters the gate set at critical risk or on irreversible surface.
    The same defect this issue fixes: two governance surfaces disagreeing,
    with nothing checking.
    """
    declared = set(
        (yaml.safe_load((GOVERNANCE / "guardrails.yml").read_text())
         .get("evidence_types") or {}))
    assert declared, "guardrails.yml declares no evidence types"

    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text())

    def enums(node):
        if isinstance(node, dict):
            if "enum" in node and "test-run" in (node["enum"] or []):
                yield set(node["enum"])
            for v in node.values():
                yield from enums(v)
        elif isinstance(node, list):
            for v in node:
                yield from enums(v)

    found = list(enums(schema))
    assert found, "manifest.schema.json has no evidence-type enum"
    for accepted in found:
        assert accepted == declared, (
            "governance and the task schema disagree about evidence types.\n"
            f"  declared in guardrails.yml but not accepted by the schema: "
            f"{sorted(declared - accepted)}\n"
            f"  accepted by the schema but not declared: "
            f"{sorted(accepted - declared)}")
