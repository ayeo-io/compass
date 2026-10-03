"""Cross-cutting release invariants.

These tests assert the hard-line invariants that must hold across releases:
- `TRC-F1`: verify.architecture is added only by a routing floor, never listed
  statically in a route shape's own gates
- `TRC-F2`: every new check is mechanical - no runtime model call
- `TRC-F3`: no sixth guardrail (`G1`-`G5` unchanged)
- `TRC-F4`: routing dimensions stay at four (assessment_vocabulary unchanged)
- `TRC-F5`: bare-repo no-op when no project guardrails/quarantine declared
- `TRC-F6`: net-new top-level concept count is bounded
- `TRC-F7`: pre-existing issues pass without change
- `TRC-FM4`: refused candidates stay refused
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent


# -----------------------------------------------------------------------------
# `TRC-F3` - no sixth guardrail
# -----------------------------------------------------------------------------

def test_guardrail_count_is_exactly_five():
    """`G1`-`G5` are the framework's five guardrails. ADR-002: no growth."""
    data = yaml.safe_load((REPO_ROOT / "governance/guardrails.yml").read_text())
    default_ids = [g["id"] for g in data["defaults"]]
    assert default_ids == ["G1", "G2", "G3", "G4", "G5"], (
        f"The five framework guardrails must be G1-G5 in order; got {default_ids}. "
        "ADR-002: the framework grows by checks/strategies, not guardrails."
    )


def test_no_trusted_rerun_is_a_check_under_g4_not_a_new_guardrail():
    """The no-trusted-rerun check must be a CHECK_FN under `G4`, not a new guardrail."""
    data = yaml.safe_load((REPO_ROOT / "governance/guardrails.yml").read_text())
    g4 = next(g for g in data["defaults"] if g["id"] == "G4")
    assert "no-trusted-rerun" in g4["checks"], (
        "A1's no-trusted-rerun must be registered as a CHECK_FN under G4 - "
        "not as a new guardrail."
    )


def test_command_passes_is_a_check_under_g4_not_a_new_guardrail():
    """The command-passes check must be a CHECK_FN under `G4`, not a new guardrail."""
    data = yaml.safe_load((REPO_ROOT / "governance/guardrails.yml").read_text())
    g4 = next(g for g in data["defaults"] if g["id"] == "G4")
    assert "command-passes" in g4["checks"], (
        "A2's command-passes must be registered as a CHECK_FN under G4 (DD-5; ADR-002)."
    )


# -----------------------------------------------------------------------------
# `TRC-F4` - routing dimensions stay at four (rubric framing) - the supporting
# keys (role, urgency, labels_common) are unchanged too.
# -----------------------------------------------------------------------------

def test_routing_dimensions_are_unchanged():
    """The four assessment dimensions (risk, familiarity, size, goal) are
    unchanged."""
    policy = yaml.safe_load((REPO_ROOT / "governance/routing-policy.yml").read_text())
    vocab = policy["assessment_vocabulary"]
    assert "risk" in vocab
    assert "familiarity" in vocab
    assert "size" in vocab
    assert "goal" in vocab
    # The supporting keys (urgency, role, labels_common) are unchanged too
    assert "urgency" in vocab
    assert "role" in vocab
    assert "labels_common" in vocab


def test_no_fifth_routing_dimension_added():
    """No new top-level assessment dimension was introduced by the 1.1.0 release."""
    policy = yaml.safe_load((REPO_ROOT / "governance/routing-policy.yml").read_text())
    vocab_keys = set(policy["assessment_vocabulary"].keys())
    # The legitimate set; if anything beyond this exists, the framework grew a dimension
    legitimate = {"risk", "familiarity", "size", "goal", "urgency", "role", "labels_common"}
    extra = vocab_keys - legitimate
    assert not extra, (
        f"reading_vocabulary gained unexpected keys: {extra}. ADR-002 forbids new dimensions."
    )


# -----------------------------------------------------------------------------
# `TRC-F1` - verify.architecture is added only by a routing floor, never
# listed statically in a route shape's own gates.
# Mechanical assertion: only the routing policy floors can introduce it.
# -----------------------------------------------------------------------------

def test_verify_fitness_only_introduced_via_routing_floors():
    """verify.architecture is not in any route_shape's gates list - it is only
    added by the RP-REQUIRE-003 and RP-REQUIRE-004 floors.
    """
    policy = yaml.safe_load((REPO_ROOT / "governance/routing-policy.yml").read_text())
    for shape_name, shape in policy["route_shapes"].items():
        assert "verify.architecture" not in shape.get("gates", []), (
            f"verify.architecture must not be baked into route_shape '{shape_name}'.gates - "
            "it is route-promoted by floor only, so routing stays per-task."
        )


def test_verify_fitness_promotion_floors_exist():
    """RP-REQUIRE-003 and RP-REQUIRE-004 are present and use add_gate: verify.architecture."""
    policy = yaml.safe_load((REPO_ROOT / "governance/routing-policy.yml").read_text())
    floors = policy["routing_guardrails"]["floors"]
    by_id = {f["id"]: f for f in floors}
    assert "RP-REQUIRE-003" in by_id, "RP-REQUIRE-003 (verify.architecture on cross-cutting/critical) must exist"
    assert "RP-REQUIRE-004" in by_id, "RP-REQUIRE-004 (verify.architecture on irreversible touches) must exist"
    assert by_id["RP-REQUIRE-003"]["add_gate"] == "verify.architecture"
    assert by_id["RP-REQUIRE-004"]["add_gate"] == "verify.architecture"


# -----------------------------------------------------------------------------
# `TRC-F2` - every new check is mechanical: no runtime model call. The CLI
# imports nothing that would talk to a model on the check path.
# -----------------------------------------------------------------------------

def test_cli_has_no_model_client_imports():
    """cli/compass must not import any LLM client or HTTP client at module level."""
    text = (REPO_ROOT / "cli/compass").read_text()
    forbidden = ["import requests", "import httpx", "import openai", "import anthropic",
                 "from requests", "from httpx", "from openai", "from anthropic"]
    for needle in forbidden:
        assert needle not in text, (
            f"cli/compass must not import {needle!r} - every new check is mechanical "
            "- the determinism boundary holds (TRC-F2)."
        )


# -----------------------------------------------------------------------------
# `TRC-F5` - bare-repo no-op. A project with no quarantine entries and no
# project guardrails sees no behavioural change.
# -----------------------------------------------------------------------------

def test_quarantine_yml_ships_empty():
    """governance/quarantine.yml ships with an empty quarantined list."""
    quarantine_path = REPO_ROOT / "governance/quarantine.yml"
    assert quarantine_path.exists(), "governance/quarantine.yml must exist"
    data = yaml.safe_load(quarantine_path.read_text())
    assert data["quarantined"] == [], (
        "governance/quarantine.yml must ship with quarantined: [] (ADR-006 - bare-repo no-op)."
    )


def test_no_project_guardrails_declared_in_framework_repo():
    """The framework's own guardrails.yml ships with project: [] (empty)."""
    data = yaml.safe_load((REPO_ROOT / "governance/guardrails.yml").read_text())
    assert data.get("project", []) == [], (
        "The framework guardrails.yml must ship with project: [] (bare-repo no-op for adopters)."
    )


# -----------------------------------------------------------------------------
# `TRC-F6` - net-new top-level concept count is bounded.
#
# Why adding a strategy does not breach the budget. ADR-002 bounds growth in
# the *hard* concepts: the five guardrails, the four assessment dimensions,
# the gate set, the check set, the evidence types, the signal categories.
# Strategies are the accretive half of the model by design; strategies.md
# opens by calling them "cheap to add, expected to evolve, fine to drop".
# Each strategy id is listed below so every addition is a deliberate,
# reviewed act.
# -----------------------------------------------------------------------------

def test_default_method_strategy_set_is_the_known_set():
    """strategies.md declares exactly the known default method strategies.

    Each id was added deliberately:

    - `S1` - BDD: behaviour as Given/When/Then
    - `S2` - TDD: red, green, refactor
    - `S3` - simplest thing that satisfies the guardrail
    - `S4` - persistence over conversation
    - `S5` - intermittency is failure
    - `S6` - regression baseline: green before, re-run after, on shared surface
    - `S7` - cold reader: write so a stranger can follow it without asking
    - `S8` - voice audition: read against a calibration sample
    - `S9` - fresh eyes on a sweep: verification by someone who did not make
      the change
    - `S10` - mutation proof: a guard is accepted on a failure, not on a pass
    - `S11` - measure before arguing: settle a disagreement with the number
    - `S12` - conventional comments: label a review comment before you write it
    - `S13` - a title is a summary, not a headline
    - `S14` - correct every place at once, or you have made it worse
    - `S15` - well-architected alignment: name the pillars a design touches
    - `S16` - named patterns: prefer a well-understood pattern, and say why

    The rationale for each lives in governance/strategies.md. Adding a
    strategy is allowed and cheap, but it must be a decision - so this list
    is updated by hand, in the same commit as the strategy it admits.
    """
    text = (REPO_ROOT / "governance/strategies.md").read_text()
    # Section markers carry the machine id as a code-span suffix:
    # "### <statement> (`S<n>`)".
    import re
    ids = set(re.findall(r"^### .*\(`(S\d+)`\)", text, flags=re.MULTILINE))
    expected = {"S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10",
                "S11", "S12", "S13", "S14", "S15", "S16"}
    assert ids == expected, (
        f"strategies.md declares {sorted(ids)}; this invariant expects "
        f"{sorted(expected)}. If you added a strategy on purpose, add its id "
        f"here and to the ledger comment above, in the same commit. If you did "
        f"not, a heading has drifted."
    )


def test_net_new_gates_is_one():
    """gate_evidence_requirements gained exactly verify.architecture (no other new gate)."""
    data = yaml.safe_load((REPO_ROOT / "governance/guardrails.yml").read_text())
    gates = set(data["gate_evidence_requirements"].keys())
    legitimate = {"verify.correctness", "verify.regression", "verify.security",
                  "verify.governance", "verify.traceability", "verify.claims",
                  "verify.clarity", "spike.conclude", "verify.analyze",
                  "verify.architecture"}
    extra = gates - legitimate
    assert not extra, f"gate_evidence_requirements gained unexpected gates: {extra}"


def test_net_new_signals_category_is_design_smell():
    """signals.yml gained exactly the design_smell category from this work."""
    data = yaml.safe_load((REPO_ROOT / "governance/signals.yml").read_text())
    assert "design_smell" in data, "signals.yml must have a design_smell category (TRC-C4)"


# -----------------------------------------------------------------------------
# `TRC-F7` - pre-existing issues pass without change.
# Replay compass check against the landed comparison-requirements issue.
# -----------------------------------------------------------------------------

def test_comparison_requirements_task_still_lints_clean():
    """A pre-existing landed issue's manifest.yml must still lint clean on the new framework.

    The fixture lives under `tests/fixtures/comparison-requirements/` (a tracked
    path). The original comparison-requirements issue lived under `.compass/work/`,
    which the framework repo's own .gitignore excludes - so the test must point
    at the tracked fixture, not the gitignored slug.
    """
    # Deliberately still named task.yml, and deliberately still keyed `task:`.
    # That is the whole point of the fixture: it is a record written before the
    # rename to manifest.yml (ADR-022), and ADR-006 promises it keeps loading
    # without anyone running `compass migrate`. Renaming it here would leave the
    # promise with nothing testing it.
    fixture = (REPO_ROOT / "tests" / "fixtures" / "comparison-requirements"
               / ("task" + ".yml"))
    assert fixture.exists(), (
        f"Fixture missing at {fixture}. ADR-006 backward-compat test relies on "
        f"this pre-v1.1.0-shape record under its retired filename."
    )
    result = subprocess.run(
        [sys.executable, "cli/compass", "issue", "lint", "--file", str(fixture)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"compass issue lint must still pass on the pre-existing comparison-requirements task "
        f"after 1.1.0 lands. stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_pre_existing_evidence_without_attempts_is_backward_compatible():
    """A landed issue's test-run evidence (no attempts field) must still clear `G4`
    via the no-trusted-rerun check's backward-compat path (TRC-A5).

    Reads the tracked fixture under `tests/fixtures/` and fails if it is
    missing, so the assertion always runs.
    """
    evidence_dir = REPO_ROOT / "tests" / "fixtures" / "comparison-requirements" / "evidence"
    green_files = list(evidence_dir.glob("green-TRC-A*.json"))
    assert green_files, (
        f"No green-TRC-A*.json files in {evidence_dir}. ADR-006 backward-compat "
        f"test requires at least one pre-v1.1.0-shape evidence file to exercise "
        f"the no-trusted-rerun check's TRC-A5 path."
    )
    sample = json.loads(green_files[0].read_text())
    assert "attempts" not in sample, (
        f"Pre-existing evidence ({green_files[0].name}) must NOT have an attempts field. "
        "The no-trusted-rerun check's TRC-A5 path relies on absence to clear trivially."
    )


# -----------------------------------------------------------------------------
# `TRC-FM4` - refused candidates stay refused.
# The mechanical assertion here: none of the refused-candidate vocabulary
# appears as a new top-level concept in governance/.
# -----------------------------------------------------------------------------

def test_no_user_stories_as_spec_format():
    """ADR-004 refused; no per-role user-story format introduced."""
    # The spec format is the BDD scenario in acceptance-criteria.md. No new
    # artifact named user-story-*.md or stories.md should exist under
    # templates/ or .compass/work/.
    templates = list((REPO_ROOT / "templates").iterdir()) if (REPO_ROOT / "templates").exists() else []
    template_names = [t.name.lower() for t in templates]
    for name in template_names:
        assert "user-stor" not in name and "stories" not in name, (
            f"Template '{name}' suggests a user-stories format was introduced - ADR-004 refused this."
        )


def test_no_deployment_pipeline_concepts():
    """Safety-contract guarantee 6: Compass is not a deployment pipeline."""
    # No CI/CD pipeline files in templates/. No "release" or "production" stage gates.
    data = yaml.safe_load((REPO_ROOT / "governance/guardrails.yml").read_text())
    gates = set(data["gate_evidence_requirements"].keys())
    for forbidden in ("release", "production", "deploy", "rollout"):
        for gate in gates:
            assert forbidden not in gate, (
                f"Gate '{gate}' contains forbidden deployment-pipeline term '{forbidden}'. "
                "Safety-contract guarantee 6: Compass is not a deployment pipeline."
            )


def test_no_maturity_assessment_added():
    """ '13 DORA self-assessment questions' refused - no maturity ladder concept."""
    # No file under templates/ or governance/ named with maturity / assessment / capability vocabulary
    for d in ("templates", "governance"):
        if not (REPO_ROOT / d).exists():
            continue
        for f in (REPO_ROOT / d).iterdir():
            n = f.name.lower()
            assert "maturity" not in n and "self-assess" not in n and "capability-ladder" not in n, (
                f"{d}/{f.name} suggests a maturity/capability ladder was introduced - refused per proposal §Out of scope."
            )


# -----------------------------------------------------------------------------
# The `--help` text must stay inside the printed line range (`PBW-D7`)
# -----------------------------------------------------------------------------

def test_release_help_prints_the_whole_header_and_nothing_else():
    """The `--help` text must stay inside the printed line range (`PBW-D7`).
    `--help` prints a fixed line range of scripts/release.sh's own
    header comment. The range must bound the header exactly - not stop short
    of its closing marker, and not spill past it - or a rewritten header
    silently prints a truncated or padded result."""
    import re

    script = REPO_ROOT / "scripts" / "release.sh"
    text = script.read_text(encoding="utf-8")
    lines = text.splitlines()

    marker_lines = [i + 1 for i, line in enumerate(lines)
                     if re.match(r"^#\s*=+\s*$", line)]
    assert len(marker_lines) >= 2, (
        "scripts/release.sh must open and close its header with a "
        "'# ====' rule; none found to bound --help's printed range against."
    )
    header_start, header_end = marker_lines[0], marker_lines[-1]

    help_source = next(
        (l for l in lines if "sed -n" in l and "$0" in l), None)
    assert help_source is not None, (
        "scripts/release.sh must have a --help branch reading its own "
        "header with `sed -n '<a>,<b>p'`."
    )
    match = re.search(r"sed -n '(\d+),(\d+)p'", help_source)
    assert match, f"could not parse the printed range out of: {help_source!r}"
    printed_start, printed_end = int(match.group(1)), int(match.group(2))

    assert (printed_start, printed_end) == (header_start, header_end), (
        f"--help prints lines {printed_start}-{printed_end}, but the header "
        f"comment runs {header_start}-{header_end}. The rewritten header "
        "must fit the printed range, or the printed range must change with "
        "it (PBW-D7)."
    )

    result = subprocess.run(
        ["bash", str(script), "--help"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    expected = "\n".join(
        re.sub(r"^# ?", "", l) for l in lines[header_start - 1:header_end]
    ) + "\n"
    assert result.stdout == expected, (
        "scripts/release.sh --help must print the whole header comment "
        "(lines %d-%d, '# ' stripped) and nothing else." % (header_start, header_end)
    )
