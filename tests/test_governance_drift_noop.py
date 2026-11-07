"""Invariants for governance drift detection (issue governance-drift-detection).

This issue has critical risk, and the one unacceptable outcome is changing
how delivery approaches are computed. A drift detector that changes routing
is worse than the silent drift it was built to find.

9.0.0 removed the drift report (ADR-098), and `TRC-F1` to `TRC-F4`, which
said when the report fired, with it. The routing, surface and evidence-type
invariants below do not depend on the report, so they stay.

Spec: governance-drift-detection/acceptance-criteria.md (`TRC-F1`..`TRC-F7`).
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GOVERNANCE = ROOT / "governance"
FIXTURES = ROOT / "tests" / "fixtures" / "routes"


# ---------------------------------------------------------------------------
# `TRC-F5` - no computed delivery approach changes. THE guard on this issue's
# critical risk.
# ---------------------------------------------------------------------------

def _readings(fx):
    """A fixture's assessment as `approach evaluate --assessment` reads it."""
    from compass_pkg import routing
    from compass_pkg.core import ASSESSMENT_KEY_MAP
    out = {}
    for key, value in (fx.get("assessment") or fx.get("readings") or {}).items():
        if value in (None, ""):
            continue
        key = ASSESSMENT_KEY_MAP.get(key, key)
        out[key] = list(value) if isinstance(value, list) else routing.read_size(key, value)
    return out


def _cli_args(fx):
    args = []
    for key, value in (fx.get("assessment") or fx.get("readings") or {}).items():
        if isinstance(value, list):
            value = ",".join(str(v) for v in value)
        if value in (None, ""):
            continue
        args += ["--assessment", f"{key}={value}"]
    return args


def test_trc_f5_drift_detection_should_not_change_any_computed_route():
    """Every routing fixture must evaluate identically after this change.

    This issue touches `compass approach evaluate`. The one outcome worse
    than silent drift is a drift detector that changes routing, so this
    re-runs the whole fixture corpus and compares the computed delivery
    approach, gates, topology and fired guardrails against what the fixture
    declares.

    The command now prints the path for a delivery assessment (ADR-092), so
    the approach is computed by the 8.x evaluator, `routing.evaluate_route`,
    in process. The shipped default no longer declares the 8.x approaches the
    fixtures name (ADR-092), so it runs on the 8.0.4 governance copy, which
    routes as the shipped policy did before 9.0.0. The twin below runs the
    command.
    """
    import compat_baseline as cb
    from compass_pkg import routing

    policy = cb.policy_8_0_4()
    fixtures = sorted(FIXTURES.glob("*.yml"))
    assert fixtures, "no routing fixtures found - this guard would be empty"
    total_checks = 0

    for path in fixtures:
        fx = yaml.safe_load(path.read_text())
        expect = fx.get("expected") or {}

        # Some fixtures are NEGATIVE: the evaluator must refuse rather than
        # silently promote (e.g. exploration intent that would touch auth).
        # Those must keep refusing, with the same message.
        if expect.get("conflict"):
            try:
                routing.evaluate_route(_readings(fx), policy)
            except routing.RoutingConflict as exc:
                needle = expect.get("conflict_message_contains", "")
                assert needle in str(exc), (
                    f"{path.name}: the conflict message changed; expected to find "
                    f"{needle!r}")
            else:
                raise AssertionError(
                    f"{path.name}: the evaluator stopped refusing a routing "
                    f"conflict - it now returns a route where it must not")
            continue

        got = routing.evaluate_route(_readings(fx), policy)

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


def test_trc_f5_drift_detection_should_not_change_what_the_command_prints():
    """Twin of the test above through `compass approach evaluate`, run in this
    checkout as before: a conflict is still refused with the same message, a
    spike prints the 8.x evaluator's approach and gates, and a delivery
    assessment prints `delivery` and the gates its evidence derives."""
    import compat_baseline as cb
    from compass_pkg import evidence_required as er
    from compass_pkg import routing

    # The 8.0.4 copy says which fixture is a spike; the command reads the
    # shipped policy, whose floors add the gates a delivery assessment owes.
    old_policy, policy = cb.policy_8_0_4(), cb.shipped_policy()
    for path in sorted(FIXTURES.glob("*.yml")):
        fx = yaml.safe_load(path.read_text())
        expect = fx.get("expected") or {}
        result = subprocess.run(
            [sys.executable, str(CLI), "approach", "evaluate", *_cli_args(fx), "--json"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        )
        if expect.get("conflict"):
            assert result.returncode != 0, (
                f"{path.name}: the command stopped refusing a routing conflict")
            needle = expect.get("conflict_message_contains", "")
            assert needle in (result.stdout + result.stderr), (
                f"{path.name}: the conflict message changed; expected to find "
                f"{needle!r}")
            continue
        assert result.returncode == 0, f"{path.name}: {result.stderr}"
        got = json.loads(result.stdout)
        old = routing.evaluate_route(_readings(fx), old_policy)
        if old["delivery_approach"] == "spike":
            assert got["delivery_approach"] == "spike", path.name
            assert got["gates"] == old["gates"], path.name
        else:
            assert got["delivery_approach"] == "delivery", path.name
            owed = er.evaluate(_readings(fx), routing.prepare_policy(policy).view)
            assert got["gates"] == owed["gates"], path.name


# ---------------------------------------------------------------------------
# `TRC-F6` - grew by artifacts and checks only
# ---------------------------------------------------------------------------

EXPECTED_GUARDRAIL_IDS = {"G1", "G2", "G3", "G4", "G5", "S1", "S2"}
# Each verb below is in the set for its own reason. `plan` is the planning
# stage's live command. `intent` reads a brief that already exists, by path
# or https URL, so a team arriving with one does not retype it - a
# top-level group rather than a subverb, because no subverb owns it.
EXPECTED_SUBCOMMANDS = {
    "approach", "bdd", "check", "ci", "tdd-red",  # 9.0.0 removed `retro` and
    "tdd-green", "policy", "issue", "adr", "flow",  # `rework-scan`, `intent` and `readiness` (ADR-093)
    "next", "follow-up", "ship-commit", "gate", "scenario", "changed-file",
    "evidence", "terminology",
    "review-rule",  # `review-rule list`; 9.0.0 removed `preset`, `spec` and `plan`
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
    "record",  # delivery-record (ADR-031); `record commit` added by #356 (ADR-096)
    # "board" (compass-board, ADR-046): ADR-093 removed the delivery board page.
    # "readiness" (ADR-061): ADR-093 removed the readiness measure.
    "release",  # intent-and-release-line (ADR-065): `release notes`, read-only
    # #359 (ADR-098): `compass migrate` moves an 8.x project to 9.0.0; it adds
    # no guardrail, gate or check.
    "migrate",
    # isolation-and-layering (#328, ADR-086): `isolation record` and `layering
    # record`, the two strategy records only their commands write. GROUPS, so a
    # later record verb has a home.
    "isolation", "layering",
    # one-check waivers (#357, ADR-094 decision 8): `waiver add` and
    # `waiver withdraw`, the one route by which an issue owes less.
    "waiver",
    # the trail (#356, ADR-096 decision 19): `compass trail [--check]` writes
    # the issue's trail.md, a file a reviewer checks with sha256sum. It adds
    # no guardrail or gate. `compass record commit` (#356) is a sub-verb of
    # the existing `record` group, so it adds no top-level verb.
    "trail",
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

    `compass analyze` (removed in 9.0.0, ADR-091) wrote a `consistency-check`
    entry, and manifest.schema.json did not accept it - so an issue whose
    delivery approach included verify.analyze produced evidence its own
    `compass issue lint` rejected. An older manifest can still hold one.
    The same defect this issue fixes: two governance surfaces disagreeing,
    with nothing checking.
    """
    declared = set(
        (yaml.safe_load((GOVERNANCE / "guardrails.yml").read_text())
         .get("evidence_types") or {}))
    assert declared, "guardrails.yml declares no evidence types"
    # The frozen file cannot list a type the check set gained after it froze.
    sys.path.insert(0, str(ROOT / "tests"))
    from check_set_files import ADDED_AFTER_THE_FREEZE
    declared |= ADDED_AFTER_THE_FREEZE["evidence_types"]

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
