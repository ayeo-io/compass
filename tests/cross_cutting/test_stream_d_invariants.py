"""Cross-cutting invariants for the CLI surface and compass next.

These tests are structural assertions that protect Compass's USPs across the
three capabilities introduced in the 1.0 line: legibility budget,
determinism boundary, refused-idea boundaries (no tier menu, no persona zoo,
no fixed-depth pipeline, no fluid no-gate mode, no mandatory universal TDD),
and zero-setup on-ramp.
"""

# These tests assert the current file names; files written under older
# names still load (ADR-006).
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from hook_text import hook_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
CLI = ROOT / "cli" / "compass"


# ---------------------------------------------------------------------------
# The five-point mental model gains zero new top-level concepts (`TRC-D1`)
# Source-of-truth: the bulleted list under
# "## The mental model in five points" in docs/five-minutes.md.
# ---------------------------------------------------------------------------
def test_trc_d1_mental_model_bullets_unchanged():
    """The bulleted list under "## The mental model in five points"
    in docs/five-minutes.md has the same number of top-level bullets it had
    before this issue landed (`TRC-D1`).

    The pre-issue count is the five-point model - by design (the heading
    promises "five points"). The three candidates introduce zero net-new
    top-level concepts; the new CLI verb (`compass next`) is a product of
    existing concepts.
    """
    five_minutes = (ROOT / "docs" / "five-minutes.md").read_text(encoding="utf-8")
    # Find the section by heading
    m = re.search(
        r"^## The mental model in five points\s*$(.*?)^## ",
        five_minutes,
        re.MULTILINE | re.DOTALL,
    )
    assert m, "docs/five-minutes.md must contain '## The mental model in five points'"
    section = m.group(1)
    # Count top-level numbered items - lines starting with "1. ", "2. ", etc.
    # at column 0. The list in this section is numbered, not bulleted.
    top_level_items = re.findall(r"^\d+\.\s+", section, re.MULTILINE)
    assert len(top_level_items) == 5, (
        f"the five-point model must keep five top-level items; "
        f"found {len(top_level_items)}"
    )


# ---------------------------------------------------------------------------
# Public CLI surface guard, an architecture check (`TRC-D2`). Originally
# froze the surface at two new verbs, one of them `compass next`.
# It is now the framework's living public-surface check: the public
# subcommand set must equal the known list below, so no verb is added (or a
# private one exposed) without a deliberate update here.
# framework-field-feedback (`R5`/`R9`) adds ship-commit and the
# issue-manifest mutators; each addition updates this set on purpose.
# Leading-underscore subcommands stay private and excluded from --help (`DD-4`).
# ---------------------------------------------------------------------------
# The known set moved with the CLI-voice slice: the banned-word verbs
# renamed (route -> approach, task -> issue, backfill -> follow-up, <!-- vocabulary-scan: allow - names the retired verbs this rename-tracking comment lists -->
# calibration -> retro, plan -> design, land-commit -> ship-commit) and <!-- vocabulary-scan: allow - names the retired verbs this rename-tracking comment lists -->
# terminology was added. The assertion's premise is unchanged - the
# surface equals the known set, and deliberate changes update it here.
EXPECTED_PUBLIC_SUBCOMMANDS = {
    "approach", "check", "ci",    # 9.0.0 removed `retro`, `rework-scan` and
    "tdd-red", "tdd-green",       # `board` (ADR-093)
    "policy", "issue", "adr",
    "flow", "follow-up",
    "terminology",                # the CLI-voice slice: the glossary verb
    "review-rule",                # `review-rule list`; 9.0.0 removed `spec sync`
                                  # (ADR-091)
    "next",                       # cross-issue-architectural-integrity; 9.0.0
                                  # removed its partner `analyze` and the
                                  # placeholder scan `plan lint` (ADR-091)
    "ship-commit",                # framework-field-feedback `R5`
    "gate", "scenario", "changed-file", "evidence",  # framework-field-feedback `R6`/`R9`
    "acceptance",                 # honest-acceptance-for-config-and-refactor:
                                  # `compass acceptance start|record`, the
                                  # honest signal for a change with no natural
                                  # behavioural red (field report `R13`). A
                                  # GROUP, like `bdd`, so later kinds add
                                  # `compass acceptance <thing>`.
    "init",                       # init-is-the-opt-in: `compass init` creates
                                  # .compass/ and is safe to run twice. The
                                  # five entry points call it, so a project is
                                  # initialised by the command the user wanted
                                  # to run rather than by a setup step they had
                                  # to know about. A verb, not a group: there
                                  # is no group it belongs under, and nothing
                                  # else initialises anything.
    "bdd",                        # executable-bdd-and-richer-plans:
                                  # `compass bdd extract`. A subcommand GROUP,
                                  # so later BDD work (a scenarios-are-executable
                                  # check) adds `compass bdd <thing>` rather than
                                  # another top-level verb.
    "quick-fix",                  # quick-fix-overhead: `compass quick-fix
                                  # start|finish` - the mechanical steps of a
                                  # quick fix (init, assess, evaluate, record,
                                  # trace, check, gate, ship) in two calls
                                  # instead of a dozen, through the same code
                                  # each step already used. A GROUP, so a
                                  # later quick-fix verb has a home.
    "lesson",                     # project-lessons (ADR-029)
    "record",                     # delivery-record (ADR-031)
    "release",                    # intent-and-release-line (ADR-065): `compass
                                  # release notes --since <ref>`, read-only. A
                                  # GROUP, so a later release verb has a home.
    "decision",                   # decisions-ledger (ADR-027): record|list|
                                  # show|check, the settled-decisions ledger.
                                  # A GROUP; record reads the decider from git.
    # "readiness" (project-readiness-caps-autonomy): ADR-093 removed the
    # readiness measure.
    "isolation", "layering",      # isolation-and-layering (#328, ADR-086):
                                  # `compass isolation record` and `compass
                                  # layering record`, the only writers of the
                                  # strategy's two records. GROUPS, so a later
                                  # record verb has a home.
    "waiver",                     # #357 (ADR-094): `compass waiver add|withdraw`,
                                  # one check waived on one issue. A GROUP.
}


def test_trc_d2_only_two_new_public_cli_verbs():
    """The public CLI surface equals the known set (no unexpected additions or
    removals), and no private entry point appears in `compass --help`
    (`DD-4`). Deliberate additions update
    EXPECTED_PUBLIC_SUBCOMMANDS."""
    out = subprocess.run(
        [sys.executable, str(CLI), "--help"],
        check=True, capture_output=True, text=True,
    ).stdout
    # Parse the {a,b,c,...} positional argument listing in `compass --help`
    m = re.search(r"\{([a-z0-9_,\-]+)\}", out)
    assert m, "compass --help must list its subcommands in {a,b,...} form"
    actual = set(m.group(1).split(","))
    assert actual == EXPECTED_PUBLIC_SUBCOMMANDS, (
        f"public CLI surface drift: added {actual - EXPECTED_PUBLIC_SUBCOMMANDS}, "
        f"removed {EXPECTED_PUBLIC_SUBCOMMANDS - actual}. If deliberate, update "
        f"EXPECTED_PUBLIC_SUBCOMMANDS in this test."
    )
    # A private entry point must not appear in --help
    assert not [verb for verb in actual if verb.startswith("_")], (
        "a private entry point must not appear in compass --help"
    )


# ---------------------------------------------------------------------------
# No fixed-tier ladder is shipped (`TRC-D3`)
# Source-of-truth: governance/routing-policy.yml - no `tier`, `level`, or
# equivalent process vocabulary, outside the `model_rules` block, which names
# the model each seat runs on; the four assessment dimensions remain
# risk/familiarity/size/intent (`BR-012`).
# ---------------------------------------------------------------------------
#: The two lists the `model_rules` block may hold, and the keys a rule in them may hold.
MODEL_RULE_LISTS = {"default_tiers", "floors"}
MODEL_RULE_KEYS = {"id", "when", "seat", "tier", "effort", "rationale"}


def model_rules_problems(policy):
    """Why a routing policy's `model_rules` block could hold a process ladder: a
    list other than the two, or a rule key other than the six."""
    model_rules = policy.get("model_rules") or {}
    problems = [f"model_rules holds {sorted(set(model_rules) - MODEL_RULE_LISTS)}; it may hold "
                f"only default_tiers and floors"] if set(model_rules) - MODEL_RULE_LISTS else []
    for name in sorted(MODEL_RULE_LISTS & set(model_rules)):
        for rule in model_rules[name] or []:
            extra = sorted(set(rule) - MODEL_RULE_KEYS)
            if extra:
                problems.append(f"model rule {rule.get('id')} holds {extra}; a model rule "
                                f"names only a seat, a model tier and an effort")
    return problems


def test_trc_d3_no_tier_ladder_in_routing_policy():
    """governance/routing-policy.yml has no `tier` or `level`
    vocabulary; the four assessment dimensions are unchanged (`TRC-D3`)."""
    text = (ROOT / "governance" / "routing-policy.yml").read_text(encoding="utf-8")
    # The `model_rules` block names a model tier per seat (which model runs a
    # stage), not a process tier a person picks from a menu: it changes no
    # stage, gate or approach. It is checked on its own below, and the rest of
    # the file keeps the hard prohibition.
    policy = yaml.safe_load(text)
    problems = model_rules_problems(policy)
    assert not problems, "\n".join(problems)
    start = text.find("\nmodel_rules:\n")
    rest = text if start < 0 else text[:start] + text[text.index("\n# ----", start + 1):]
    # Hard prohibition - no "tier:" or "level:" keys anywhere else
    for forbidden in ("tier:", "level:"):
        assert forbidden not in rest, (
            f"routing-policy.yml must not introduce '{forbidden}' - would be a tier-ladder"
        )
    # Reading vocabulary keys: the dimensions + urgency. Role left the
    # assessment at 7.0.0 (ADR-070); nothing took its place.
    vocab = policy.get("assessment_vocabulary", {})
    expected_dims = {"risk", "familiarity", "size", "goal", "urgency", "labels_common"}
    assert set(vocab.keys()) == expected_dims, (
        f"assessment_vocabulary must be {expected_dims}; got {set(vocab.keys())}"
    )


# ---------------------------------------------------------------------------
# The five roles are unchanged; no new agent persona was added (`TRC-D4`)
# Source-of-truth: agents/*.md. The agent count cannot grow. The five roles
# left the assessment at 7.0.0 (ADR-070).
# ---------------------------------------------------------------------------
PRE_TASK_AGENT_FILES = {
    "spec-author.md", "planner.md", "builder.md", "orchestrator.md",
    "verifier.md", "reviewer.md", "router.md",
    "product-owner.md", "product-marketer.md", "architect.md",
}


def test_trc_d4_no_new_agent_persona_no_new_role():
    """The count of role agent files is unchanged; the five
    roles remain the canonical set (`TRC-D4`, `BR-013`)."""
    agents_dir = ROOT / "agents"
    actual_agents = {p.name for p in agents_dir.glob("*.md")}
    # New agent files would be a `BR-013` violation
    new_agents = actual_agents - PRE_TASK_AGENT_FILES
    assert not new_agents, (
        f"no new role/lens agent file may be added by this task; observed new: {new_agents}"
    )
    # The layered lint held the five roles as the perspectives a document kind
    # may be owned by. 9.0.0 declares no document kind (ADR-091) and removed that
    # lint with the layers (ADR-094); the role agent files above are what remains.


# ---------------------------------------------------------------------------
# Pipeline phases still flex by delivery approach (`TRC-D5`)
# Source-of-truth: governance/routing-policy.yml `route_shapes` - at least
# two route shapes differ in their phase-weight maps (`BR-014`).
# ---------------------------------------------------------------------------
def test_trc_d5_pipeline_phases_flex_by_route():
    """The five route shapes have different phase-weight maps;
    none has been flattened to a one-size-fits-all shape (`TRC-D5`, `BR-014`).

    The shapes are read from the 8.0.4 governance copy, the last release that
    declared them. The shipped default runs one path of four stages with no
    stage modes since 9.0.0 (ADR-092)."""
    import tarfile
    sys.path.insert(0, str(ROOT / "tests"))
    from compat_baseline import GOVERNANCE_8_0_4
    with tarfile.open(GOVERNANCE_8_0_4) as tar:
        policy = yaml.safe_load(tar.extractfile("governance/routing-policy.yml").read())
    shapes = policy["route_shapes"]
    phase_maps = {name: shape["stages"] for name, shape in shapes.items()}
    # All five shapes present
    assert {"spike", "quick-fix", "regular", "hotfix", "full"} == set(phase_maps.keys())
    # At least two shapes must have distinct phase maps
    distinct = {tuple(sorted(pm.items())) for pm in phase_maps.values()}
    assert len(distinct) >= 2, (
        "at least two route shapes must have different phase-weight maps; "
        f"all shapes resolved to {len(distinct)} unique phase map(s)"
    )
    # Specifically: a quick fix collapses the requirements review; a spike
    # skips the breakdown. Read by the CURRENT stage keys - the policy
    # declared the retired ones until 2026-08-25, which is the whole reason
    # `shape_stages` had to canonicalise them for every caller.
    assert phase_maps["quick-fix"]["refine"] in {"collapsed", "light"}
    assert phase_maps["spike"]["breakdown"] in {"skipped", "collapsed"}


# ---------------------------------------------------------------------------
# Phases and gates remain enforced (`TRC-D6`)
# Source-of-truth: governance/routing-policy.yml `immovable_gates` and every
# route_shape's `gates` list (`BR-015`).
# ---------------------------------------------------------------------------
IMMOVABLE_GATE_IDS = {"verify.correctness", "verify.governance", "verify.traceability"}


def test_trc_d6_phases_and_gates_remain_enforced():
    """Immovable gates are still immovable; no route shape's gate
    set is empty - no fluid no-gate mode (`TRC-D6`, `BR-015`)."""
    policy = yaml.safe_load(
        (ROOT / "governance" / "routing-policy.yml").read_text(encoding="utf-8")
    )
    # Immovable gates present
    immovable = {g["gate"] for g in policy["routing_guardrails"]["immovable_gates"]}
    assert IMMOVABLE_GATE_IDS.issubset(immovable), (
        f"immovable gates must include {IMMOVABLE_GATE_IDS}; got {immovable}"
    )
    # No route shape has an empty gate set
    for name, shape in policy["route_shapes"].items():
        gates = shape.get("gates", [])
        assert gates, f"route shape '{name}' must not have an empty gate set"


# ---------------------------------------------------------------------------
# TDD remains a strategy that Spike suspends (`TRC-D7`)
# Source-of-truth: hooks/pre-tool.sh - must read a .spike marker and suspend
# enforcement on a Spike delivery approach (`BR-016`).
# ---------------------------------------------------------------------------
def test_trc_d7_tdd_remains_a_strategy_spike_suspends():
    """The pre-tool hook still reads the .spike marker and
    suspends red-before-green on Spike delivery approaches (`TRC-D7`, `BR-016`)."""
    hook = hook_text(ROOT / "hooks" / "pre-tool.sh")
    assert ".spike" in hook, "pre-tool.sh must read the .spike marker to be route-aware"
    # The hook still enforces .red elsewhere - sanity that it's not been removed
    assert ".red" in hook, "pre-tool.sh must still enforce the .red marker contract"


# ---------------------------------------------------------------------------
# Every new capability functions on a bare repo with no /compass:init (`TRC-D8`)
# Source-of-truth: the CLI's behaviour when invoked from a bare directory
# with no project-level governance/ overrides. Falls back to the framework's
# shipped defaults (`BR-004` / `NFR-ONR-001`).
# ---------------------------------------------------------------------------
def test_trc_d8_bare_repo_zero_setup(tmp_path):
    """`compass next` produces a clean no-op behaviour when invoked from a
    bare repo without /compass:init (`TRC-D8`). Exit code may be non-zero
    because no issue is assessed, but the error must be informative, not a
    traceback."""
    # Bare repo - just a directory, no .compass/ at all
    out_next = subprocess.run(
        [sys.executable, str(CLI), "next"],
        cwd=str(tmp_path), capture_output=True, text=True,
    )
    assert "Traceback" not in out_next.stderr, (
        f"next on bare repo crashed: {out_next.stderr}"
    )


# ---------------------------------------------------------------------------
# Delivery-approach composition stays byte-identical across runs (`TRC-D9`)
# Source-of-truth: `compass approach evaluate --json` for a fixed assessment
# set returns byte-identical output across runs (`NFR-DET-001`).
# ---------------------------------------------------------------------------
def test_trc_d9_route_evaluate_deterministic(tmp_path):
    """`compass approach evaluate` is byte-identical for the same
    assessment and the same routing policy (`TRC-D9`)."""
    # Run `compass approach evaluate` twice with the same assessment against
    # the framework's own routing-policy.yml (no project overrides - work in
    # tmp_path).
    cmd = [
        sys.executable, str(CLI), "approach", "evaluate",
        "--assessment", "risk=contained",
        "--assessment", "familiarity=brownfield-mapped",
        "--assessment", "size=small",
        "--assessment", "intent=delivery",
        "--assessment", "role=engineer",
        "--json",
    ]
    out1 = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=True)
    out2 = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=True)
    # The route + phases + gates blocks must match byte-for-byte
    j1 = json.loads(out1.stdout)
    j2 = json.loads(out2.stdout)
    assert j1.get("delivery_approach") == j2.get("delivery_approach")
    assert j1.get("stages") == j2.get("stages")
    assert j1.get("gates") == j2.get("gates")


# ---------------------------------------------------------------------------
# The determinism boundary holds - no model call after the assessment (`TRC-D10`)
# Source-of-truth: static check of cli/compass for LLM SDK imports
# (`BR-002` / `NFR-DET-002`).
# ---------------------------------------------------------------------------
FORBIDDEN_LLM_IMPORTS = (
    "import anthropic",
    "from anthropic",
    "import openai",
    "from openai",
    "import litellm",
    "from litellm",
    "import langchain",
    "from langchain",
)


def test_trc_d10_no_llm_sdk_in_cli():
    """`cli/compass` imports no LLM SDK on any code path. The
    determinism boundary is post-assessment; the CLI is the post-boundary
    half and must be mechanism, not judgement (`TRC-D10`)."""
    cli_src = CLI.read_text(encoding="utf-8")
    for forbidden in FORBIDDEN_LLM_IMPORTS:
        assert forbidden not in cli_src, (
            f"cli/compass must not import an LLM SDK; found '{forbidden}'"
        )
