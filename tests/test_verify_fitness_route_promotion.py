"""
Tests for `TRC-B4`, `TRC-B5`, `TRC-B8` - verify.architecture route promotion
and architecture documentation.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
import yaml

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = FRAMEWORK_ROOT / "cli" / "compass"


def _run_cli(*args: str, cwd: Path,
             extra_env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


#: The project's own rules that owe the architecture review. On a 9.0.0
#: delivery issue the check set holds no floor that adds a gate (ADR-099 decision 4);
#: a project adds the `architecture` token itself
#: with `require_evidence`, and the token's gate is `verify.architecture`.
#: The rules fire as `RP-SETTING-1` and `RP-SETTING-2`, in file order.
ARCHITECTURE_RULES = [
    {"when": {"risk": ["cross-cutting", "critical"]},
     "add": ["architecture"]},
    {"when": {"labels_any": ["auth", "payments", "personal-data", "migrations"]},
     "add": ["architecture"]},
]


def _setup_gov(tmp_path: Path) -> Path:
    """A project on the shipped check set that opts in to the architecture
    review. 9.0.0 reads no copy of the governance files (ADR-098), so none is
    made."""
    (tmp_path / ".compass").mkdir(exist_ok=True)
    (tmp_path / "compass.yml").write_text(
        yaml.safe_dump({"schema": 1, "require_evidence": ARCHITECTURE_RULES}),
        encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# verify.architecture promoted when risk is cross-cutting or critical (`TRC-B4`)
# ---------------------------------------------------------------------------

class TestVerifyFitnessPromotionBlastRadius:
    """verify.architecture is promoted to blocking when risk reaches
    cross-cutting or critical (`TRC-B4`)."""

    def test_cross_cutting_blast_radius_adds_verify_fitness(self, tmp_path):
        """`compass approach evaluate` on risk=cross-cutting includes
        verify.architecture in the gate set."""
        project_root = _setup_gov(tmp_path)
        result = _run_cli(
            "approach", "evaluate", "--json",
            "--assessment", "risk=cross-cutting",
            "--assessment", "familiarity=brownfield-mapped",
            "--assessment", "size=medium",
            "--assessment", "intent=delivery",
            cwd=project_root,
        )
        assert result.returncode == 0, (
            f"route evaluate failed: {result.stderr}"
        )
        data = json.loads(result.stdout)
        assert "verify.architecture" in data["gates"], (
            f"Expected verify.architecture in gates for cross-cutting blast_radius, "
            f"got: {data['gates']}"
        )

    def test_critical_blast_radius_adds_verify_fitness(self, tmp_path):
        """`compass approach evaluate` on risk=critical includes verify.architecture."""
        project_root = _setup_gov(tmp_path)
        result = _run_cli(
            "approach", "evaluate", "--json",
            "--assessment", "risk=critical",
            "--assessment", "familiarity=brownfield-mapped",
            "--assessment", "size=large",
            "--assessment", "intent=delivery",
            cwd=project_root,
        )
        assert result.returncode == 0, f"route evaluate failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert "verify.architecture" in data["gates"]

    def test_fired_guardrails_names_floor_rg_floor_006(self, tmp_path):
        """When cross-cutting fires the project's architecture rule, it appears in
        the rules fired."""
        project_root = _setup_gov(tmp_path)
        result = _run_cli(
            "approach", "evaluate", "--json",
            "--assessment", "risk=cross-cutting",
            "--assessment", "familiarity=brownfield-mapped",
            "--assessment", "size=medium",
            "--assessment", "intent=delivery",
            cwd=project_root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        floor_ids = [f["id"] for f in data.get("policy_rules_fired", [])]
        assert "RP-SETTING-1" in floor_ids, (
            f"Expected RP-SETTING-1 in fired_guardrails, got: {floor_ids}"
        )

    def test_contained_blast_radius_does_not_add_verify_fitness(self, tmp_path):
        """risk=contained does NOT promote verify.architecture."""
        project_root = _setup_gov(tmp_path)
        result = _run_cli(
            "approach", "evaluate", "--json",
            "--assessment", "risk=contained",
            "--assessment", "familiarity=brownfield-mapped",
            "--assessment", "size=small",
            "--assessment", "intent=delivery",
            cwd=project_root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "verify.architecture" not in data["gates"], (
            f"verify.architecture should NOT be in gates for contained, "
            f"got: {data['gates']}"
        )


# ---------------------------------------------------------------------------
# verify.architecture promoted when touches includes an irreversible domain (`TRC-B5`)
# ---------------------------------------------------------------------------

class TestVerifyFitnessPromotionTouches:
    """verify.architecture is promoted to blocking when touches lists an
    irreversible domain (`TRC-B5`)."""

    @pytest.mark.parametrize("domain", ["auth", "payments", "personal-data", "migrations"])
    def test_irreversible_domain_adds_verify_fitness(self, tmp_path, domain):
        """labels: [<domain>] causes verify.architecture to be added to gate set."""
        project_root = _setup_gov(tmp_path)
        result = _run_cli(
            "approach", "evaluate", "--json",
            "--assessment", "risk=contained",
            "--assessment", "familiarity=brownfield-mapped",
            "--assessment", "size=small",
            "--assessment", "intent=delivery",
            "--assessment", f"touches={domain}",
            cwd=project_root,
        )
        assert result.returncode == 0, (
            f"route evaluate failed for domain={domain}: {result.stderr}"
        )
        data = json.loads(result.stdout)
        assert "verify.architecture" in data["gates"], (
            f"Expected verify.architecture for touches=[{domain}], "
            f"got gates: {data['gates']}"
        )

    def test_fired_guardrails_names_floor_rg_floor_007(self, tmp_path):
        """When touches fires the project's architecture rule, it appears in the
        rules fired."""
        project_root = _setup_gov(tmp_path)
        result = _run_cli(
            "approach", "evaluate", "--json",
            "--assessment", "risk=contained",
            "--assessment", "familiarity=brownfield-mapped",
            "--assessment", "size=small",
            "--assessment", "intent=delivery",
            "--assessment", "touches=auth",
            cwd=project_root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        floor_ids = [f["id"] for f in data.get("policy_rules_fired", [])]
        assert "RP-SETTING-2" in floor_ids, (
            f"Expected RP-SETTING-2 in fired_guardrails, got: {floor_ids}"
        )

    def test_safe_domain_does_not_add_verify_fitness(self, tmp_path):
        """A non-irreversible domain does not promote verify.architecture."""
        project_root = _setup_gov(tmp_path)
        result = _run_cli(
            "approach", "evaluate", "--json",
            "--assessment", "risk=contained",
            "--assessment", "familiarity=brownfield-mapped",
            "--assessment", "size=small",
            "--assessment", "intent=delivery",
            "--assessment", "touches=public-api",
            cwd=project_root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "verify.architecture" not in data["gates"], (
            f"verify.architecture should NOT appear for touches=public-api, "
            f"got: {data['gates']}"
        )


# ---------------------------------------------------------------------------
# architecture/ documents the architecture-check pattern (`TRC-B8`)
# ---------------------------------------------------------------------------

class TestArchitectureDocumentation:
    """architecture/ documents the architecture-check pattern (`TRC-B8`)."""

    ARCH_DIR = FRAMEWORK_ROOT / "architecture"
    DECISIONS_DIR = FRAMEWORK_ROOT / "architecture" / "decisions"

    def test_adr_009_exists(self):
        """ADR-009 file must exist in architecture/decisions/."""
        adr_file = (
            self.DECISIONS_DIR
            / "ADR-009-fitness-functions-are-project-guardrails.md"
        )
        assert adr_file.is_file(), (
            f"ADR-009 not found at {adr_file}"
        )

    def test_adr_009_status_is_proposed(self):
        """ADR-009 must have status: proposed in its frontmatter."""
        adr_file = (
            self.DECISIONS_DIR
            / "ADR-009-fitness-functions-are-project-guardrails.md"
        )
        if not adr_file.is_file():
            pytest.skip("ADR-009 not yet created")
        text = adr_file.read_text(encoding="utf-8")
        assert "proposed" in text.lower(), (
            "ADR-009 must have status: proposed"
        )

    def test_adr_009_covers_command_passes_and_the_architecture_gate(self):
        """ADR-009 must mention command-passes and the gate it promotes.

        The gate is accepted under whichever spelling ADR-009 itself uses.
        ADR-023 renamed it to `verify.architecture` and deliberately did not
        edit the accepted records that carry the old spelling: a decision
        record is evidence of what was decided and in what words, so it keeps
        them. Accepting either name is what lets both rules hold at once.
        """
        adr_file = (
            self.DECISIONS_DIR
            / "ADR-009-fitness-functions-are-project-guardrails.md"
        )
        if not adr_file.is_file():
            pytest.skip("ADR-009 not yet created")
        text = adr_file.read_text(encoding="utf-8")
        assert "command-passes" in text, "ADR-009 must mention command-passes"
        assert ("verify.architecture" in text or "verify.fitness" in text), (
            "ADR-009 must name the gate it promotes, under either spelling")

    def test_adr_009_in_decisions_readme(self):
        """ADR-009 must be listed in architecture/decisions/README.md."""
        readme = self.DECISIONS_DIR / "README.md"
        assert readme.is_file()
        text = readme.read_text(encoding="utf-8")
        assert "ADR-009" in text, "ADR-009 must be indexed in decisions/README.md"

    def test_system_context_mentions_adr_009(self):
        """architecture/system-context.md must reference ADR-009."""
        sc = self.ARCH_DIR / "system-context.md"
        assert sc.is_file()
        text = sc.read_text(encoding="utf-8")
        assert "ADR-009" in text, (
            "system-context.md must contain a sentence pointing at ADR-009"
        )

    def test_evidence_gates_skill_mentions_fitness_functions(self):
        """The evidence-gates skill must describe the architecture-check
        pattern citing ADR-009.

        Reads the whole skill directory: the detail lives in
        architecture-checks.md since the skill was split, and it applies only
        where a project has declared an architecture check.
        """
        skill_dir = FRAMEWORK_ROOT / "skills" / "evidence-gates"
        assert skill_dir.is_dir()
        text = "\n".join(sorted(q.read_text(encoding="utf-8") for q in skill_dir.glob("*.md")))
        assert "fitness" in text.lower(), (
            "the evidence-gates skill must mention fitness functions"
        )
        assert "ADR-009" in text, (
            "the evidence-gates skill must cite ADR-009"
        )
