# compass_pkg.stable_ids - the ids of the approaches, stages and gates (ADR-040)
# DEPENDENCY: none (constants only; it imports nothing so every module can import it).
APPROACH_SPIKE = "spike"
APPROACH_QUICK_FIX = "quick-fix"
APPROACH_REGULAR = "regular"
APPROACH_HOTFIX = "hotfix"
APPROACH_FULL = "full"
APPROACH_IDS = (APPROACH_SPIKE, APPROACH_QUICK_FIX, APPROACH_REGULAR, APPROACH_HOTFIX, APPROACH_FULL)
# The one approach a path issue records besides the spike (ADR-092). It is not
# in `APPROACH_IDS`, which lists the approaches the default preset declares.
APPROACH_DELIVERY = "delivery"

LEGACY_APPROACH_ALIASES = {
    "express": APPROACH_QUICK_FIX,
    "standard": APPROACH_REGULAR,
    "expedition": APPROACH_FULL,
    "feature": APPROACH_REGULAR,
    "initiative": APPROACH_FULL,
}

# The stage weights and artifact depths. `full` is also a delivery approach;
# the depth that used to share its name is `thorough`. The retired spellings
# sit in cli/migrate-map.yml (VR-G12), and a test keeps these constants equal
# to the modes the default preset declares.
MODE_THOROUGH = "thorough"
MODE_LIGHTWEIGHT = "lightweight"
MODE_THOROUGH_WITH_FOLLOW_UP = "thorough-with-follow-up"
DEPTH_THOROUGH = "thorough"
DEPTH_LIGHTWEIGHT = "lightweight"
ARTIFACT_DEPTHS = (DEPTH_LIGHTWEIGHT, DEPTH_THOROUGH)           # ascending strictness
MODE_RANKS = {"skipped": 0, "collapsed": 1, MODE_LIGHTWEIGHT: 2, MODE_THOROUGH: 3,
              MODE_THOROUGH_WITH_FOLLOW_UP: 4}

STAGE_ASSESS = "assess"
STAGE_DEFINE = "define"
STAGE_REFINE = "refine"
STAGE_PLAN = "plan"
STAGE_BREAKDOWN = "breakdown"
STAGE_IMPLEMENT = "implement"
STAGE_VERIFY = "verify"
STAGE_SHIP = "ship"
# The eight stages an issue assessed before #351 records in its `stages:` map.
# `STAGE_IDS` keeps the old name so no importer changes.
LEGACY_STAGE_IDS = (STAGE_ASSESS, STAGE_DEFINE, STAGE_REFINE, STAGE_PLAN, STAGE_BREAKDOWN,
                    STAGE_IMPLEMENT, STAGE_VERIFY, STAGE_SHIP)
STAGE_IDS = LEGACY_STAGE_IDS

# The four-stage path (ADR-092). The stages are fixed here, not in a preset,
# and a path issue writes no `stages:` map. A spike explores in build and
# concludes in ship, so it has no specify stage. `specify` and `build` are
# also v1 stage names: `path_stages.rename_v1_stage_keys` renames them only
# in a v1 record.
STAGE_SPECIFY = "specify"
STAGE_BUILD = "build"
PATH_STAGE_IDS = (STAGE_ASSESS, STAGE_SPECIFY, STAGE_BUILD, STAGE_SHIP)
SPIKE_STAGE_IDS = (STAGE_ASSESS, STAGE_BUILD, STAGE_SHIP)
# The path stage that shows a legacy stage, for every reader that shows or acts
# on the stage of an old issue. The migration that #359 adds uses the same mapping.
LEGACY_TO_PATH = {
    STAGE_ASSESS: STAGE_ASSESS,
    STAGE_DEFINE: STAGE_SPECIFY, STAGE_REFINE: STAGE_SPECIFY, STAGE_PLAN: STAGE_SPECIFY,
    STAGE_BREAKDOWN: STAGE_BUILD, STAGE_IMPLEMENT: STAGE_BUILD,
    STAGE_VERIFY: STAGE_SHIP, STAGE_SHIP: STAGE_SHIP,
}

# The model tiers, weakest first. 9.0.0 removed model tiers (ADR-090); the names
# stay because the `models` setting a project file can still hold is checked
# against them. `standard` is also a retired approach name.
TIER_FAST = "fast"
TIER_STANDARD = "standard"
TIER_STRONG = "strong"
MODEL_TIERS = (TIER_FAST, TIER_STANDARD, TIER_STRONG)
# The effort levels a Claude Code subagent takes, lowest first. `medium` is also a
# size value; as an effort it names how hard the model works.
EFFORT_LOW = "low"
EFFORT_MEDIUM = "medium"
EFFORT_HIGH = "high"
EFFORT_LEVELS = (EFFORT_LOW, EFFORT_MEDIUM, EFFORT_HIGH, "xhigh", "max")

GATE_G1 = "G1"
GATE_G2 = "G2"
GATE_G3 = "G3"
GATE_G4 = "G4"
GATE_G5 = "G5"
GATE_S1 = "S1"
GATE_S2 = "S2"
GATE_VERIFY_CORRECTNESS = "verify.correctness"
GATE_VERIFY_REGRESSION = "verify.regression"
GATE_VERIFY_SECURITY = "verify.security"
GATE_VERIFY_GOVERNANCE = "verify.governance"
GATE_VERIFY_TRACEABILITY = "verify.traceability"
GATE_VERIFY_CLAIMS = "verify.claims"
GATE_VERIFY_CLARITY = "verify.clarity"
GATE_SPIKE_CONCLUDE = "spike.conclude"
GATE_VERIFY_ARCHITECTURE = "verify.architecture"
GATE_IDS = (GATE_G1, GATE_G2, GATE_G3, GATE_G4, GATE_G5, GATE_S1, GATE_S2,
            GATE_VERIFY_CORRECTNESS, GATE_VERIFY_REGRESSION, GATE_VERIFY_SECURITY,
            GATE_VERIFY_GOVERNANCE, GATE_VERIFY_TRACEABILITY, GATE_VERIFY_CLAIMS,
            GATE_VERIFY_CLARITY, GATE_SPIKE_CONCLUDE, GATE_VERIFY_ARCHITECTURE)
# 9.0.0 removed this gate with `compass analyze` (ADR-091). The live default does
# not declare it; an older manifest, a frozen preset and a stored generation do.
GATE_VERIFY_ANALYZE = "verify.analyze"
REMOVED_GATE_IDS = (GATE_VERIFY_ANALYZE,)

# The names in an issue's documents folder that are not artifacts: the migrate
# leaves them where they are and does not register them, and `compass issue
# lint` does not report them. Framework-owned (ADR-040), read by both.
# `*` stands for any text. `compare.md` and `report.md` are an evaluation run's
# outputs, and `*.v6.bak` is a distribution map the migrate set aside.
# `result.md` and `result-subtask-*.md` are a multiagent builder's hand-back,
# the same class of file as its brief: no reader needs one registered.
NOT_AN_ARTIFACT = (
    "README.md", "devlog.md",
    "*review-brief*.md",
    "assignment-subtask-*.md", "brief-subtask-*.md",
    "result.md", "result-subtask-*.md",
    "architect-ruling.md", "recommendation.md", "released-verbs-v5.6.0.md",
    "compare.md", "report.md",
    "*.v6.bak",
)
