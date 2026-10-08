"""Framework invariants for this issue (executable-bdd-and-richer-plans).

Two properties that must hold across everything this issue changed, and
that no single subtask can prove on its own:

  * A project that opted into nothing sees no change (ADR-006). The BDD work
    adds a CLI verb and four config keys; none of them may change behaviour
    for a project that does not set them.
  * The framework grew by artifacts and skills only (ADR-002). No new
    guardrail, no new gate, no fifth assessment dimension.

Spec: executable-bdd-and-richer-plans/acceptance-criteria.md
      (TRC-F5, `TRC-F6`).
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GOVERNANCE = ROOT / "governance"


# ---------------------------------------------------------------------------
# `TRC-F5` - a project that opted into nothing sees no change
# ---------------------------------------------------------------------------

BDD_KEYS = ("bdd_runner", "bdd_features_dir", "bdd_steps_dir", "bdd_run_command")


def test_trc_f5_no_optin_means_no_change():
    # 1. the shipped config sets none of the bdd keys as live values
    cfg = yaml.safe_load((ROOT / "compass.yml").read_text()) or {}
    project = cfg.get("project") or {}
    for key in BDD_KEYS:
        assert not project.get(key), (
            f"{key} ships with a live value; a project that edits nothing "
            f"would have opted in"
        )

    # 2. the mechanical gate suite passes on a project that opted into nothing.
    #
    # Run it against a SYNTHETIC project, not this repository. `compass ci`
    # checks every issue under .compass/work/, so running it here would fail
    # whenever any issue is mid-pipeline - which conflates "the BDD keys
    # changed nothing" (what this scenario is about) with "nobody is working
    # right now".
    proj = pathlib.Path(tempfile.mkdtemp(prefix="compass-optin-"))
    try:
        shutil.copytree(ROOT / "governance", proj / "governance")
        (proj / ".compass" / "work").mkdir(parents=True)
        shutil.copyfile(ROOT / "compass.yml", proj / "compass.yml")
        result = subprocess.run(
            [sys.executable, str(CLI), "ci"],
            cwd=str(proj), capture_output=True, text=True, timeout=300,
        )
        assert result.returncode == 0, (
            "compass ci fails on a project that opted into nothing:\n"
            f"{result.stdout[-3000:]}\n{result.stderr[-2000:]}"
        )
        assert "bdd" not in result.stdout.lower(), (
            "compass ci mentions BDD on a project that set no bdd_ key:\n"
            f"{result.stdout[-2000:]}"
        )
    finally:
        shutil.rmtree(proj, ignore_errors=True)

    # 3. EXTRACTION must not depend on a runner being declared.
    #
    # The assertion checks only the extract function's body, because other
    # commands read `bdd_runner` legitimately - `compass bdd verify` needs
    # it, because opting in is what the key is for. It finds the function
    # wherever it lives, rather than pinning its file.
    candidates = [CLI] + sorted((CLI.parent / "compass_pkg").glob("*.py"))
    source = next(s for s in (c.read_text(encoding="utf-8") for c in candidates)
                  if "def cmd_bdd_extract(" in s)
    start = source.index("def cmd_bdd_extract(")
    nxt = source.find("\ndef ", start + 1)
    extract_body = source[start:nxt if nxt != -1 else len(source)]
    assert "bdd_runner" not in extract_body, (
        "cmd_bdd_extract branches on project.bdd_runner; extraction must work "
        "for a project that has declared no runner"
    )


# ---------------------------------------------------------------------------
# `TRC-F6` - the framework grew by artifacts and skills only (ADR-002)
# ---------------------------------------------------------------------------

EXPECTED_GUARDRAIL_IDS = {"G1", "G2", "G3", "G4", "G5", "S1", "S2"}

EXPECTED_GATE_IDS = {
    "verify.correctness", "verify.governance", "verify.traceability",
    "verify.regression", "verify.security", "verify.clarity", "verify.claims",
    "verify.analyze", "verify.architecture", "spike.conclude",
}

EXPECTED_READING_KEYS = {
    "risk", "familiarity", "size", "goal", "urgency", "role",
    "labels_common",
}


def test_trc_f6_no_new_guardrail_gate_or_dimension():
    guardrails = yaml.safe_load((GOVERNANCE / "guardrails.yml").read_text())
    policy = yaml.safe_load((GOVERNANCE / "routing-policy.yml").read_text())

    # The guardrail id set is unchanged. Ids live under `defaults` (`G1`-`G5`) and
    # `spike_guardrails` (`S1`-`S2`); `checks` is a dict of named check functions,
    # which is a different thing and may legitimately grow.
    ids = {g["id"] for g in guardrails["defaults"]}
    ids |= {g["id"] for g in guardrails["spike_guardrails"]}
    ids |= {g["id"] for g in guardrails.get("project") or []}
    assert ids == EXPECTED_GUARDRAIL_IDS, (
        f"the guardrail id set changed.\n  unexpected: {sorted(ids - EXPECTED_GUARDRAIL_IDS)}"
        f"\n  missing   : {sorted(EXPECTED_GUARDRAIL_IDS - ids)}"
    )

    # the four assessment dimensions plus urgency, role, labels - no fifth
    vocab = set(policy["assessment_vocabulary"].keys())
    assert vocab == EXPECTED_READING_KEYS, (
        f"the reading vocabulary changed.\n  unexpected: "
        f"{sorted(vocab - EXPECTED_READING_KEYS)}\n"
        f"  missing   : {sorted(EXPECTED_READING_KEYS - vocab)}"
    )

    # no new gate id anywhere in the policy
    seen = set()
    for shape in policy["route_shapes"].values():
        seen.update(shape.get("gates", []))
    for group in ("floors", "immovable_gates", "role_rules"):
        for rule in policy["routing_guardrails"].get(group, []):
            for key in ("gate", "add_gate"):
                if rule.get(key):
                    seen.add(rule[key])
    assert seen <= EXPECTED_GATE_IDS, (
        f"new gate id(s) introduced: {sorted(seen - EXPECTED_GATE_IDS)}"
    )
