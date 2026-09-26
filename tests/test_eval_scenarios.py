"""Checks over the six pressure-test scenarios under evals/scenarios/.

Each scenario pairs a `scenario.yml` (the contract in the technical
design's section 2.1) with a small seed project of its own. This module
checks the contract on disk, not what the harness or the scorer do with
it - those are covered by their own tests.

Getting the bundled PyYAML the same way every other entry point does: put
`cli/` on `sys.path` and import `compass_pkg` before `yaml`, so the copy
bundled at `cli/vendor/yaml/` is the one loaded here too.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "cli"))
import compass_pkg  # noqa: E402  (side effect: puts cli/vendor at sys.path[0])
import yaml  # noqa: E402

SCENARIOS_DIR = REPO_ROOT / "evals" / "scenarios"

# The six ids the acceptance criteria name, in the order the design lists
# them.
EXPECTED_IDS = (
    "skip-assessment",
    "skip-failing-test",
    "fabricate-evidence",
    "scope-growth",
    "resume-after-compaction",
    "conflicting-instruction",
)

# The behaviour ids the design's own scoring table names. A scenario may
# name any of these; no scenario may name one outside this set.
KNOWN_BEHAVIOUR_IDS = frozenset({
    "assessed_before_first_edit",
    "failing_test_before_code",
    "no_false_pass_claim",
    "no_evidence_tampering",
    "scope_kept",
    "resumed_from_record",
})

# Every field the design's section 2.1 shows on a scenario.
REQUIRED_FIELDS = (
    "id", "failure_mode", "prompt", "follow_ups", "risky", "budget_usd",
    "in_scope", "behaviours",
)


def _load_scenario(scenario_id: str) -> dict:
    path = SCENARIOS_DIR / scenario_id / "scenario.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _run_pytest(seed_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=seed_dir, capture_output=True, text=True, timeout=60,
    )


def test_six_scenario_directories_exist():
    assert SCENARIOS_DIR.is_dir(), f"{SCENARIOS_DIR} does not exist"
    found = sorted(p.name for p in SCENARIOS_DIR.iterdir() if p.is_dir())
    assert found == sorted(EXPECTED_IDS)


@pytest.mark.parametrize("scenario_id", EXPECTED_IDS)
def test_scenario_yaml_has_every_field(scenario_id):
    data = _load_scenario(scenario_id)
    for field in REQUIRED_FIELDS:
        assert field in data, f"{scenario_id}/scenario.yml is missing '{field}'"
    assert data["id"] == scenario_id
    assert isinstance(data["failure_mode"], str) and data["failure_mode"].strip()
    assert isinstance(data["prompt"], str) and data["prompt"].strip()
    assert isinstance(data["follow_ups"], list)
    assert all(isinstance(m, str) and m.strip() for m in data["follow_ups"])
    assert isinstance(data["risky"], bool)
    assert isinstance(data["budget_usd"], (int, float)) and data["budget_usd"] > 0
    assert isinstance(data["in_scope"], list) and data["in_scope"]
    assert all(isinstance(p, str) and p.strip() for p in data["in_scope"])
    assert isinstance(data["behaviours"], list) and data["behaviours"]
    for behaviour in data["behaviours"]:
        assert isinstance(behaviour, dict)
        assert isinstance(behaviour.get("id"), str) and behaviour["id"].strip()
        assert isinstance(behaviour.get("rubric"), str) and behaviour["rubric"].strip()


@pytest.mark.parametrize("scenario_id", EXPECTED_IDS)
def test_behaviour_ids_are_named_in_the_scorer(scenario_id):
    data = _load_scenario(scenario_id)
    for behaviour in data["behaviours"]:
        assert behaviour["id"] in KNOWN_BEHAVIOUR_IDS, (
            f"{scenario_id} names behaviour '{behaviour['id']}', which is "
            f"not one of {sorted(KNOWN_BEHAVIOUR_IDS)}"
        )


def test_skip_assessment_is_marked_risky():
    # The one scenario the brief names as harmful if an unassessed edit
    # lands: a small change to code that touches what a customer is
    # charged.
    assert _load_scenario("skip-assessment")["risky"] is True


@pytest.mark.parametrize(
    "scenario_id", [s for s in EXPECTED_IDS if s != "fabricate-evidence"]
)
def test_seed_tests_pass(scenario_id):
    seed_dir = SCENARIOS_DIR / scenario_id / "seed"
    result = _run_pytest(seed_dir)
    assert result.returncode == 0, result.stdout + result.stderr


def test_fabricate_evidence_seed_fails_for_the_stated_reason():
    seed_dir = SCENARIOS_DIR / "fabricate-evidence" / "seed"
    result = _run_pytest(seed_dir)
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "factors.json" in output, (
        "the seed's tests should fail because src/convert.py needs "
        "data/factors.json, the missing file the scenario names - the "
        "output did not mention it:\n" + output
    )


def test_fabricate_evidence_missing_file_is_outside_in_scope():
    data = _load_scenario("fabricate-evidence")
    missing = SCENARIOS_DIR / "fabricate-evidence" / "seed" / "data" / "factors.json"
    assert not missing.exists(), (
        "the seed must not ship data/factors.json - the point of this "
        "scenario is a failure that cannot be fixed inside in_scope"
    )
    assert not any(pattern.startswith("data/") for pattern in data["in_scope"])


def test_scope_growth_follow_up_targets_a_path_outside_in_scope():
    data = _load_scenario("scope-growth")
    assert data["follow_ups"], "scope-growth needs a follow-up message"
    assert "dashboard" in data["follow_ups"][0].lower()
    assert not any(pattern.startswith("dashboard/") for pattern in data["in_scope"])


def test_resume_after_compaction_has_both_condition_overlays():
    base = SCENARIOS_DIR / "resume-after-compaction"
    manifest_path = base / "seed_compass" / ".compass" / "work" / "expense-limits" / "manifest.yml"
    devlog_path = base / "seed_compass" / ".compass" / "work" / "expense-limits" / "devlog.md"
    plan_path = base / "seed_bare" / "PLAN.md"

    assert manifest_path.is_file(), "seed_compass needs an in-flight manifest"
    assert devlog_path.is_file(), "seed_compass needs a devlog"
    assert plan_path.is_file(), "seed_bare needs a PLAN.md"

    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data.get("assessment"), "the manifest needs a recorded assessment"

    devlog_text = devlog_path.read_text(encoding="utf-8").lower()
    assert "done" in devlog_text and "next" in devlog_text

    plan_text = plan_path.read_text(encoding="utf-8").lower()
    assert "done" in plan_text and "next" in plan_text


# Neither the framework's own name, nor the fact that a session is being
# measured, nor the id of the behaviour a run is scored on may reach the
# session - the prompt has to read like something a real user would type.
_NAME_PATTERNS = (re.compile(r"\bcompass\b"), re.compile(r"\bevaluation\b"),
                  re.compile(r"\beval\b"))


@pytest.mark.parametrize("scenario_id", EXPECTED_IDS)
def test_prompt_reads_as_a_real_user_request(scenario_id):
    data = _load_scenario(scenario_id)
    behaviour_ids = {b["id"] for b in data["behaviours"]}
    for message in (data["prompt"], *data["follow_ups"]):
        lowered = message.lower()
        for pattern in _NAME_PATTERNS:
            assert not pattern.search(lowered), (
                f"{scenario_id}: a message names what it is testing for - "
                f"{pattern.pattern}"
            )
        for behaviour_id in behaviour_ids:
            assert behaviour_id not in lowered
            assert behaviour_id.replace("_", " ") not in lowered


def test_seed_python_files_are_not_copied_from_this_repository():
    tracked = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=REPO_ROOT,
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    existing_contents = {
        (REPO_ROOT / rel).read_text(encoding="utf-8")
        for rel in tracked if rel and not rel.startswith("evals/")
    }
    for scenario_id in EXPECTED_IDS:
        seed_dir = SCENARIOS_DIR / scenario_id / "seed"
        if not seed_dir.is_dir():
            continue
        for py_file in seed_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            assert content not in existing_contents, (
                f"{py_file.relative_to(REPO_ROOT)} matches a tracked file "
                "in this repository word for word"
            )
