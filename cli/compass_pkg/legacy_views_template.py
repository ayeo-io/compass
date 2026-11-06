# compass_pkg.legacy_views_template - what the generated policy files say besides data
# DEPENDENCY: compass_pkg.stable_ids (plain constants; no third-party code).
"""The template of the two generated views.

`legacy_views.py` writes `governance/routing-policy.yml` and
`governance/guardrails.yml` from the default preset and the sidecar. The values
come from those two. Everything else a reader sees in the files comes from
here: the banner, the comment blocks between sections, the comments before or
inside one entry, which prose is folded or wrapped, and the blank lines between
entries. Nothing here is a value the evaluator or a check reads, so a change
here changes only how a view reads.

A `<<name>>` line in a template is replaced by the rendered data of that
section.
"""
from compass_pkg.stable_ids import (
    GATE_G1, GATE_G2, GATE_G3, GATE_G4, GATE_G5, GATE_S1, GATE_S2, GATE_SPIKE_CONCLUDE,
    GATE_VERIFY_ANALYZE, GATE_VERIFY_ARCHITECTURE, GATE_VERIFY_CLARITY)

REGENERATE_COMMAND = "python3 scripts/generate-legacy-views.py"

# The first lines of both views. They say the file is generated, so nobody
# edits it by hand and has the edit overwritten at the next regeneration.
BANNER = """\
# GENERATED FILE - do not edit by hand. The source is the default preset in
# governance/presets/default/ and governance/legacy-views.yml. Change those,
# then regenerate this file with: <<command>>
# A test fails when this file differs from what that command writes.
"""

POLICY_TEMPLATE = """\
<<banner>>
# =============================================================================
# Compass - routing-policy.yml
# =============================================================================
# THE MACHINE-READABLE ROUTING POLICY. This file is authoritative for the
# mechanical parts of routing. `routing-policy.md` explains the why; this file
# is what the deterministic evaluator (`compass approach evaluate`) actually runs.
#
# The split that matters: the *assessment* (three scored dimensions - risk,
# familiarity and size - plus the goal and urgency switches and labels) is JUDGMENT - the assess stage, an LLM or a
# human, produces it, and it is not mechanisable, because that judgment
# IS the adaptivity. This file governs only what happens *after* the assessment
# is recorded: composing and constraining the delivery approach. That part is deterministic and
# reproducible - same assessment + same policy => same delivery approach, every time.
#
# Tune routing in the preset, then regenerate this file (see the first lines).
# `compass policy lint` checks it against schemas/routing-policy.schema.json.
# Loosening a routing rule weakens the framework for everyone - see
# routing-policy.md.
# =============================================================================

version: <<version>>
# -----------------------------------------------------------------------------
# ROUTING STRATEGIES - soft. They BIAS the candidate delivery approach. The evaluator uses
# them in composition (step 1); a later rule can override the result.
# -----------------------------------------------------------------------------
routing_strategies:

  # default_shapes - the reference approach the evaluator leans towards for an assessment.
  # Evaluated top to bottom; the first whose `when` matches sets the candidate.
  # `when` keys match against the assessment; a list value means "any of".
  default_shapes:
<<default_shapes>>

  # Fallback when no default_shape matches.
  default_route: <<default_route>>

  # biases - free-text tie-breakers the assess stage applies during composition.
  # Not machine-evaluated; surfaced to the assess stage and recorded for audit.
  biases:
<<biases>>

  # advisory_strategies - soft strategies the evaluator surfaces (in
  # `applicable_strategies`) when their `when` matches the assessment. They BIAS
  # and are ASSESSED at `verify`; they NEVER add a gate, raise the delivery approach, or block
  # `ship`. A strategy, not a guardrail (the full method strategy is `S6` in
  # governance/strategies.md).
  advisory_strategies:
<<advisory_strategies>>

# -----------------------------------------------------------------------------
# ROUTING RULES - hard. They BOUND the candidate delivery approach. The evaluator
# applies these after composition; they cannot be bypassed, and a human
# cannot override them per-issue (changing one means editing the preset).
# -----------------------------------------------------------------------------
routing_guardrails:

  # floors - a matching assessment value asks for a skill or adds a gate. Since
  # 9.0.0 no floor raises the delivery approach (ADR-092): every delivery issue
  # runs the four-stage path, and the evidence it owes is computed from its
  # assessment. A copy of an older file can still say `force_minimum_route`.
  # NOTE: two of the entries below carry RP-REQUIRE ids because they attach a
  # gate and raise no minimum - they are not floors. The block name lags its
  # contents: moving them into their own section changes a
  # structure the evaluator iterates and the schema checks, which is filed
  # as rename-routing-policy-machine-keys. See ADR-016.
  floors:
<<floors>>

  # 9.0.0 has no caps (ADR-092): the one cap limited the worktrees of a
  # critical change, and 9.0.0 makes no worktree (ADR-090).

  # loop_ceilings - how far a multiagent run or an unattended run went
  # before it stopped with a reason. 9.0.0 removed both runs (ADR-090), so
  # nothing applies these limits; they stay readable until the configuration
  # layers are replaced. For each ceiling the LOWEST limit among the matching
  # rules applies, so a rule can only lower a limit.
  loop_ceilings:
<<loop_ceilings>>

  # immovable_gates - review gates no delivery approach may drop.
  # These three are "the default guardrails in review form": every delivery
  # issue owes them, and listing them here means a tuned configuration still
  # cannot drop them. NOTE what is NOT here: verify.regression is owed only
  # where the evidence an issue owes lists `regression` (a small, contained
  # change does not run it), and verify.claims is added by no shipped rule
  # since 9.0.0 (ADR-091).
  # Immovable means immovable *everywhere* - keep the set to what genuinely is.
  immovable_gates:
<<immovable_gates>>

# -----------------------------------------------------------------------------
# Assessment vocabulary - the legal values the assessment may take. The evaluator
# rejects a value outside this vocabulary (a misclassification should fail
# loudly, not pick an approach silently).
# -----------------------------------------------------------------------------
assessment_vocabulary:
<<assessment_vocabulary>>

# -----------------------------------------------------------------------------
# Autonomy checkpoints - which stage hand-offs wait for a person. A checkpoint
# is a hand-off where the session stops. `autonomy:` in `compass.yml` (or
# `.compass/config.yml` in a project without one) sets it, default balanced.
# On the four-stage path (ADR-092) the hand-offs are assess, specify, build
# and ship, and the path decides which wait from the autonomy value and the
# evidence the issue owes; the `delivery` row below says what it decides for an
# issue that owes no person's approval of its scenarios. An issue assessed
# before 9.0.0 waits at the legacy hand-offs its own approach lists. Only a
# checkpoint stage can be named: the setting never changes a gate, evidence,
# the pre-tool hook, `compass check`, guardrail 5 or the sign-off the domain
# labels bring. Added 2026-10-03, issue #329.
# -----------------------------------------------------------------------------
autonomy_checkpoints:
<<autonomy_checkpoints>>

# -----------------------------------------------------------------------------
# Approach shapes - the machine-readable mirror of the two approaches: the
# spike and `delivery`, the four-stage path (ADR-092). approaches/spike.md and
# approaches/path.md describe them. A spike's manifest keeps the stage map and
# gate below. A delivery issue writes no stage map: its gates come from the
# evidence it owes, so the `delivery` entry holds only the three immovable
# gates and a mode per path stage, which no reader judges.
# -----------------------------------------------------------------------------
route_shapes:
<<route_shapes>>
"""

GUARDRAILS_TEMPLATE = """\
<<banner>>
# =============================================================================
# A CHECK DERIVES FROM THIS FILE'S STRUCTURE.
# tests/plain_language_check.py builds its registry of what each code means from
# the `gates` of the preset in governance/presets/default/, and from `defaults:`
# and each entry's `id`, `name` and `statement` here when the preset is absent.
# Change those key names or that nesting and the derivation fails loudly,
# naming this file - it does not fall back to a hand-written table, because a
# table would drift from this file in silence. This is the derivation-failure
# criterion (`TRC-C9`).
# =============================================================================
# Compass - guardrails.yml
# =============================================================================
# THE MACHINE-READABLE GUARDRAIL DEFINITIONS. This file is authoritative for
# how guardrails are *checked*. `guardrails.md` explains what each guardrail is
# and why; this file says what evidence clears it, and `compass check` runs
# those checks against an issue's `manifest.yml` and `evidence/`.
#
# Note the asymmetry, and that it is deliberate: GUARDRAILS get a .yml because
# they are checkable and nobody steps off them. A STRATEGY is a strong default
# you can step off with a recorded reason, so `strategies.md` holds it as prose.
# A strategy can carry blocking checks that a recorded step-off makes advisory:
# they sit outside every guardrail below, in no lock, so an approved waiver can
# make them advisory (strategy `S17`). The guardrails keep their own checks.
#
# The five default guardrails below ship active. A project may ADD guardrails
# under `project:` - each needs a named check, or it is a strategy, not a
# guardrail. `compass policy lint` checks this file against
# schemas/guardrails.schema.json.
# =============================================================================

version: <<version>>
# -----------------------------------------------------------------------------
# Named checks - the mechanical checks `compass check` knows how to run. Each
# guardrail below references one or more of these by name. The check reads
# manifest.yml and evidence/ - it does not re-run tests (that is tdd-green's job);
# it checks the recorded state is coherent and backed by evidence.
# -----------------------------------------------------------------------------
checks:
<<checks>>

# -----------------------------------------------------------------------------
# Evidence types - what KINDS of evidence a gate can be cleared with. Without
# this, `gate-evidence-present` is circular: a gate could be marked `pass`
# pointing at a weak markdown note and still clear the mechanical check. Typing
# the evidence makes the *strength* of a gate's backing visible - and lets the
# checker demand a real mechanical capture for the gates that need one.
#
# Evidence model: manifest.yml has a top-level `evidence:` REGISTRY of typed
# entries (each {id, type, path, ...}); a gate's `evidence:` is a list of
# evidence ids referencing the registry. Multiple gates can share one entry.
# -----------------------------------------------------------------------------
evidence_types:
<<evidence_types>>

# gate_evidence_requirements - which evidence types each gate will accept. A
# gate not listed here accepts any type. The point is the constrained ones:
# you cannot clear `verify.correctness` with a markdown note, because
# correctness is a mechanical fact and demands a `test-run`.
gate_evidence_requirements:
<<gate_evidence_requirements>>

# -----------------------------------------------------------------------------
# DEFAULT GUARDRAILS - `G1`–`G5`. Shipped active. The floor under every delivery approach.
# -----------------------------------------------------------------------------
defaults:

<<defaults>>

# -----------------------------------------------------------------------------
# SPIKE GUARDRAILS - apply only on a spike. A spike is intentionally
# free of the delivery guardrails (`G1`-`G5` do not apply), but it is still
# CONTROLLED: it must conclude, and it must not silently produce production
# work. `compass check` runs these instead of the defaults on a spike.
# -----------------------------------------------------------------------------
spike_guardrails:

<<spike_guardrails>>

# -----------------------------------------------------------------------------
# PROJECT GUARDRAILS - the team adds here. Each MUST reference a named check
# (add new checks to `checks:` above, or ask the CLI maintainer to add the
# check logic). A would-be guardrail with no mechanical check is a strategy -
# put it in strategies.md instead. Leave this empty rather than padding it.
# -----------------------------------------------------------------------------
project: <<project>>
# Empty on purpose, not by oversight: the framework ships no project guardrails,
# so an adopting repo sees no project-level check until it declares one.
#  - id: Q1
#    name: "Coverage floor"
#    statement: "Line coverage does not drop below 80%."
#    checks: [coverage-floor]          # <- a project-added check
#    params: { min_line_coverage: 80 }
#    checked_at: [build]
#    # Coverage is a floor, never a target - a high coverage number is a side effect of test discipline, not its goal.

# -----------------------------------------------------------------------------
# Cross-cutting: the conflict rule (a guardrail beats a strategy) and the
# Definition of Done checklist are governance too, but they live where they
# are used - see governance/README.md and the `build` exit list of the shipped
# preset. The four-stage path owes no Definition of Ready (ADR-092).
# -----------------------------------------------------------------------------
"""

# Comment lines written before one entry (`id` is the key) or before one key
# of an entry, keyed by (entry id, key).
ENTRY_COMMENTS = {
    ('RP-FLOOR-002', 'rationale'): [
        '# A small, contained change on unmapped ground with none of the four',
        '# domain labels gets the same skill as advice instead (RP-ADV-002).',
    ],
    ('RP-REQUIRE-005', 'id'): [
        '# Artifacts are an output of the approach, like gates. A dimension the shape does not',
        '# know about can earn a document the same way it earns a gate - which is',
        '# what stops the artifact set being "whatever this shape always writes".',
    ],
    ('RP-LOOP-006', 'id'): [
        '# `compass run` (ADR-030), removed in 9.0.0: the sessions one unattended',
        '# run could start, and the minutes it could take.',
    ],
    ('assessment_vocabulary', 'labels_common'): [
        '# `labels` is an open list of domain tags - common ones, not exhaustive:',
    ],
    ('scenarios-are-executable', 'blocking_when'): [
        "# Assessment-scoped, exactly like a guardrail's `applies_when:`.",
        '# Below this threshold a finding is reported without failing the',
        '# run - most projects have wired no runner, and an advisory',
        '# finding is the honest default (ADR-006).',
    ],
    (GATE_G1, 'checks'): [
        '# The red-before-green cycle is strategy `S2`, not this guardrail. `G1` is the',
        '# outcome; `compass check` checks the outcome, the hook enforces `S2`.',
        '# `declared-tests-resolve` closes the gap that a test being *named* is not',
        '# the same as a test existing. It fires only once an issue has claimed',
        '# verify.correctness and is still active - before that the test legitimately',
        '# does not exist yet, and after landing the manifest is a historical record.',
    ],
    (GATE_G3, 'checks'): [
        '# `landed-by-resolves` is a traceability check: it is what makes a',
        "# pointer at another issue's record a LINK rather than a claim. Both",
        '# ends must name each other, the named issue must have landed, and it',
        '# must carry a record of its own - otherwise a chain of empty issues',
        '# could vouch for one another.',
    ],
    (GATE_G5, 'applies_when'): [
        '# Fires on the four labels only. Their change is the one a merge cannot',
        '# undo: a migration can lose data that cannot be restored, and auth,',
        '# payments and personal data reach people outside the repository.',
        '# Critical risk alone does not fire it: critical-risk code that carries',
        '# none of the labels can be reverted at merge, and CI and review gate',
        '# it (governance decision 2026-10-12, guardrail-5-triggers-on-the-',
        '# irreversible-labels). A project that wants critical risk too sets',
        '# `G5.when` back in compass.yml; the lock allows a stricter trigger.',
    ],
}

# A comment on the same line as a value, as (spaces before it, the comment).
INLINE_COMMENTS = {
    ('RP-ART-001', 'gate'): (16, "# adds the claims gate to the approach's set"),
    ('gate_evidence_requirements', GATE_VERIFY_CLARITY): (7, '# inherently judgment - and now visibly so'),
    ('gate_evidence_requirements', GATE_SPIKE_CONCLUDE): (14, '# SPECIFIC: a generic artifact will not do'),
    ('gate_evidence_requirements', GATE_VERIFY_ANALYZE): (14, '# SPECIFIC: advisory command-output does NOT clear this gate'),
    ('gate_evidence_requirements', GATE_VERIFY_ARCHITECTURE): (4, '# architecture checks: command-output from command-passes, or a test-run'),
}

# Entries of a mapping that follow a blank line. A list that separates every
# entry from the last names its section in GAPPED_SECTIONS instead.
BLANK_BEFORE = {"evidence-matches-tree", "command-passes"}
GAPPED_SECTIONS = {"floors", "defaults", "spike_guardrails"}

# Prose written as a folded block (`>`) and not on one quoted line, by
# (section, entry id).
FOLDED = {
    ("checks", "suite-passed"), ("checks", "claim-traces-to-scenario"),
    ("checks", "dod-evidence-typed"), ("checks", "no-trusted-rerun"),
    ("checks", "evidence-identity-matches"), ("checks", "evidence-matches-tree"),
    ("evidence_types", "test-run"), ("evidence_types", "rollback-plan"),
    ("defaults", GATE_G1), ("defaults", GATE_G2), ("defaults", GATE_G3), ("defaults", GATE_G4),
    ("defaults", GATE_G5), ("spike_guardrails", GATE_S1), ("spike_guardrails", GATE_S2),
}

# Quoted prose that breaks over several lines, by (entry id, key). Every other
# quoted string stays on one line however long it is.
WRAPPED = {("RP-ADV-001", "rationale"), ("RP-ADV-002", "rationale"), ("biases", "item")}

# Where wrapped prose and long lists break, in columns.
TEXT_WIDTH = 76
LIST_WIDTH = 100
