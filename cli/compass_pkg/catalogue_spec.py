# compass_pkg.catalogue_spec - the configuration catalogues' field table
"""What each configuration catalogue holds, as data.

The configuration foundation makes delivery approaches, stages, checks,
gates, artifacts, dimensions, rules and display names into catalogues a
project extends (ADR-035). The merge, the classifier (ADR-037), locks
(ADR-039) and lint all read one table so they cannot disagree about a
field. This module is that table and nothing else: no I/O, no logic.

Each field records:

- `type`: the YAML shape it takes;
- `merge`: how a child layer changes it - `scalar` replaces, `list` takes
  `add:`/`remove:` or a whole list, `map` takes `set:`/`remove:` or a whole
  map, `whole` replaces as one value;
- `compare`: how the classifier compares a parent and a child value -
  `ordered` by declared order, `obligation-set` (more is stricter),
  `way-set` (more is looser), `ceiling` (as the registry declares),
  `identity` (any change cannot be compared), `predicate` (evaluated at each
  assessment), `descriptive` (not compared), `activation` (turns a check on
  or off), `never` (not read by the classifier at all).
"""
# DEPENDENCY: none.
from __future__ import annotations

CATALOGUES = ("dimensions", "stages", "approaches", "rules", "checks", "gates",
              "artifacts", "vocabulary")

MERGE_KINDS = ("scalar", "list", "map", "whole")
COMPARE_KINDS = ("ordered", "obligation-set", "way-set", "ceiling", "identity",
                 "predicate", "descriptive", "activation", "never")

# A catalogue id: stable, and never a display name (those live in
# `vocabulary`).
ID_PATTERN = r"^[A-Za-z][A-Za-z0-9._-]*$"

DIMENSION_TYPES = ("ordered-enum", "enum", "set")
TIGHTER = ("higher", "lower")
CHECK_KINDS = ("deterministic", "evidence", "judged", "human")
SEVERITIES = ("advisory", "blocking")            # ascending strictness
ON_SKIPPED = ("pass", "not-applicable", "fail")  # ascending strictness
GATE_KINDS = ("review", "guardrail")
LOCKS = (True, "hard")

# The shipped order of the two ordered dimensions, for a `when:` clause
# that uses `at_least:` before any configuration is loaded.
SHIPPED_ORDERS = {
    "risk": ("trivial", "contained", "cross-cutting", "critical"),
    "size": ("atomic", "small", "standard", "large", "product"),
}

# Where a retired word can sit in a configuration layer, one row per field:
# `(catalogue, entry id or "*", field, shape, domain)`. `domain` names the
# word table that field is read through (`compass_pkg.word_map`). `shape` says
# where the word is in the field's value: `value` is the value itself, `keys`
# are the keys of a map, `values` are the values of a map and `items` are the
# members of a list. A path that is not here is never mapped, which is what
# keeps a check parameter that happens to be called `size` unchanged.
VALUE_DOMAINS = (
    ("stages", "*", "modes", "keys", "stage_mode"),
    ("stages", "*", "mode", "value", "stage_mode"),
    ("approaches", "*", "stages", "values", "stage_mode"),
    ("approaches", "*", "artifacts", "values", "artifact_depth"),
    ("dimensions", "size", "values", "items", "size"),
)

# The keys that hold a condition on the assessment, and the names of the size
# dimension a condition may use (`magnitude` is the older spelling).
PREDICATE_KEYS = ("when", "blocking_when", "applies_when", "applies_to")
SIZE_KEYS = ("size", "magnitude")


def _f(type_, merge, compare, required=False):
    return {"type": type_, "merge": merge, "compare": compare, "required": required}


FIELDS = {
    "dimensions": {
        "type": _f("string", "scalar", "identity", required=True),
        "values": _f("list", "list", "identity"),
        "tighter": _f("string", "scalar", "identity"),
        "open": _f("boolean", "scalar", "identity"),
        "common": _f("list", "list", "descriptive"),
        "required": _f("boolean", "scalar", "identity"),
    },
    "stages": {
        "order": _f("integer", "scalar", "identity", required=True),
        "modes": _f("map", "map", "ordered", required=True),
        "entry": _f("list", "list", "obligation-set"),
        "exit": _f("list", "list", "obligation-set"),
        "mode": _f("string", "scalar", "ordered"),   # the issue layer only
    },
    "approaches": {
        "weight": _f("integer", "scalar", "never", required=True),
        "ships": _f("boolean", "scalar", "identity"),
        "extends": _f("string", "scalar", "descriptive"),
        "stages": _f("map", "map", "ordered", required=True),
        "gates": _f("list", "list", "obligation-set"),
        "artifacts": _f("map", "map", "obligation-set"),
        "subtask_ceiling": _f("integer-or-null", "scalar", "ceiling"),
        "checkpoints": _f("map", "map", "obligation-set"),
    },
    "rules": {
        "kind": _f("string", "scalar", "identity", required=True),
        "hit": _f("map", "map", "identity", required=True),
        "rules": _f("map", "map", "predicate"),
    },
    "checks": {
        "statement": _f("string", "scalar", "identity", required=True),
        "kind": _f("string", "scalar", "identity", required=True),
        "impl": _f("string", "scalar", "identity"),
        "params": _f("map", "map", "ceiling"),
        "accepts": _f("list", "list", "way-set"),
        "reviewers": _f("list", "list", "way-set"),
        "approvers": _f("list", "list", "way-set"),
        "inputs": _f("list", "list", "obligation-set"),
        "when": _f("map", "whole", "predicate"),
        "blocking_when": _f("map", "whole", "predicate"),
        "severity": _f("string", "scalar", "ordered", required=True),
        "on_skipped": _f("string", "scalar", "ordered", required=True),
        "requires": _f("list", "list", "activation"),
        "locked": _f("boolean-or-hard", "scalar", "identity"),
    },
    "gates": {
        "kind": _f("string", "scalar", "identity", required=True),
        "stage": _f("string", "scalar", "identity"),
        "checks": _f("list", "list", "obligation-set"),
        "accepts": _f("list", "list", "way-set"),
        "when": _f("map", "whole", "predicate"),
        "applies_to": _f("map", "whole", "identity"),
        "name": _f("string", "scalar", "descriptive"),
        "statement": _f("string", "scalar", "descriptive"),
        "locked": _f("boolean-or-hard", "scalar", "identity"),
    },
    "artifacts": {
        "file": _f("string", "scalar", "identity", required=True),
        "depends_on": _f("list", "list", "obligation-set"),
        "checks": _f("list", "list", "obligation-set"),
        "bookkeeping": _f("boolean", "scalar", "identity"),
    },
    "vocabulary": {
        "name": _f("string", "scalar", "descriptive", required=True),
        "aliases": _f("list", "list", "descriptive"),
    },
}

# Keys any catalogue entry may also carry: how a layer changes it.
ENTRY_OPERATIONS = ("set", "replace", "remove", "locked", "unlock", "waiver")

# Which of those each layer may use. Only the project lifts a lock (ADR-039);
# an issue changes fields and asks for waivers but never replaces, removes
# or locks an entry (ADR-035, floors win over the issue layer).
LAYER_OPERATIONS = {
    "project": ENTRY_OPERATIONS,
    "parent": ("set", "replace", "remove", "locked", "waiver"),
    "issue": ("set", "waiver"),
}

# The obligation facts two configurations are compared on and a lock
# protects (ADR-037, ADR-039): one table, so the two cannot disagree. A
# key names a fact of the resolved configuration: a catalogue field
# (`checks.kind`), a part of one (`approaches.artifacts.depth`), or an
# output of the evaluator at an assessment (`evaluation.*`). A fact
# missing here compares as equivalent, so the test pins the whole table.
OBLIGATION_FIELDS = {
    "approaches.stages": "ordered",              # the mode chosen per stage
    "approaches.gates": "obligation-set",
    "approaches.artifacts": "obligation-set",    # which artifacts are owed
    "approaches.artifacts.depth": "ordered",     # light below full
    "approaches.checkpoints": "obligation-set",
    "approaches.subtask_ceiling": "ceiling",
    "approaches.ships": "identity",              # a lock's footprint (ADR-039)
    "artifacts.depends_on": "obligation-set",    # what an owed artifact builds on
    "artifacts.checks": "obligation-set",        # the checks an owed artifact carries
    "stages.mode": "ordered",                    # an issue's own choice
    "stages.order": "identity",                  # a lock's footprint
    "stages.entry": "obligation-set",
    "stages.exit": "obligation-set",
    "gates.stage": "identity",                   # a lock's footprint
    "gates.checks": "obligation-set",
    "gates.accepts": "way-set",
    "checks.kind": "identity",
    "checks.impl": "identity",
    "checks.params": "ceiling",
    "checks.accepts": "way-set",
    "checks.reviewers": "way-set",
    "checks.approvers": "way-set",
    "checks.inputs": "obligation-set",
    "checks.severity": "ordered",
    "checks.on_skipped": "ordered",
    "checks.statement": "identity",   # compared for human and judged checks only
    "rules.ceilings": "ceiling",                 # each loop ceiling
    "evaluation.max_worktrees": "ceiling",
    "evaluation.required_skills": "obligation-set",
    "evaluation.blocked_stages": "obligation-set",
    "evaluation.required_artifacts": "obligation-set",
}

# The hit policies a rule set can name for an effect (ADR-035). `first` stops
# at the first matching rule, `max` and `min` take the highest or lowest
# value, and `collect` gathers every match. Lint refuses a policy the effect
# does not allow, and a rule set that uses an effect without naming one. An
# effect is a key a rule's `then:` can hold; the other keys there (a ceiling
# name, an end date) qualify an effect and take no policy.
EFFECT_POLICIES = {
    "lean_toward": ("first",),
    "force_minimum_approach": ("max",),
    "max_worktrees": ("min",),
    "limit": ("min",),
    "never_skip": ("collect",),
    "require_phase": ("collect",),
    "require_skill": ("collect",),
    "add_gate": ("collect",),
    "add_artifact": ("collect",),
    "gate": ("collect",),
    "require_artifact": ("collect",),
    "block_phase": ("collect",),
    "strategy": ("collect",),
    "suggest_artifact": ("collect",),
}

# The catalogue each effect's value names: a value is an id of that catalogue
# (one id, or a list of them). Lint refuses an id the catalogue lacks. An
# effect that is not here names no catalogue entry (a skill, a number).
EFFECT_TARGETS = {
    "lean_toward": "approaches",
    "force_minimum_approach": "approaches",
    "never_skip": "stages",
    "require_phase": "stages",
    "block_phase": "stages",
    "add_gate": "gates",
    "gate": "gates",
    "add_artifact": "artifacts",
    "require_artifact": "artifacts",
    "suggest_artifact": "artifacts",
}

# The other keys a rule's `then:` may hold. They qualify an effect and take no
# hit policy. Any key in neither this tuple nor `EFFECT_POLICIES` is refused,
# so a misspelt effect fails lint and is not silently ignored.
EFFECT_QUALIFIERS = ("ceiling", "until")

# Which way is stricter for each ceiling the classifier compares and a lock
# protects (ADR-037, ADR-039). A key is a ceiling field of the table above,
# or `rules.ceilings.<name>` for a loop ceiling. `lower` means a smaller
# number is stricter, and no ceiling at all is the loosest. `none` makes any
# change incomparable: the four correction loops, where an earlier stop also
# removes a chance to fix a defect. A ceiling not listed here is `none`. Only
# the framework declares a direction, so a loader must never fill this from
# project data.
CEILING_DIRECTIONS = {
    "approaches.subtask_ceiling": "lower",
    "evaluation.max_worktrees": "lower",
    "rules.ceilings.run_cost_usd": "lower",
    "rules.ceilings.run_minutes": "lower",
    "rules.ceilings.run_cycles": "lower",
    "rules.ceilings.builder_attempts": "none",
    "rules.ceilings.review_rounds": "none",
    "rules.ceilings.replans": "none",
    "rules.ceilings.repeated_error": "none",
}

ARTIFACT_DEPTHS = ("light", "full")              # ascending strictness
AUTONOMY = ("controlled", "balanced", "autonomous")
ADOPTION = ("advisory", "enforced")
# `governance_drift`: any value other than `strict` reads as `advisory`.
GOVERNANCE_DRIFT = ("advisory", "strict")
# The approver lists a layer names (ADR-039); an unlock is the owner's.
APPROVER_KINDS = ("issue-waiver", "project-waiver")

# The classifier compares at most this many named set values (ADR-037).
LABEL_CAP = 8

# Named switches for new blocking behaviour, off in the shipped default.
CAPABILITIES = ("entry-exit-evaluation", "artifact-freshness")

# Top-level keys of a layer file (ADR-043).
LAYER_KEYS = ("schema", "extends", "owner", "approvers", "capabilities") + CATALOGUES
SETTINGS_KEYS = ("autonomy", "adoption", "allow_project_commands", "enforcement",
                 "record", "project", "prices", "multiagent", "governance_drift",
                 "preset_index")
RESERVED_KEYS = ("preset",)

# What an issue's own layer (the manifest's `config:`) may hold.
ISSUE_KEYS = ("stages", "checks", "gates", "rules", "autonomy", "ceilings", "approach")


# --- what each field means (`schemas/compass.schema.json` descriptions) ------------------
# The generated schema reads these texts, so a person or an editor sees what
# a field means beside its name. A test fails on a schema node with no text,
# and on an enumeration value its text does not name. Each text says what the
# field is, its allowed values or units, and its shipped default where the
# shipped preset sets one.

CATALOGUE_DESCRIPTIONS = {
    "dimensions": "The facts an assessment records about a piece of work, such as risk and size. "
                  "Each key is a dimension id.",
    "stages": "The eight stages of delivery, from assess to ship. Each key is a stage id.",
    "approaches": "The delivery approaches: which mode each stage runs in, which gates and "
                  "artifacts are owed, and how far work may be split. Each key is an approach id.",
    "rules": "The rule sets the evaluator reads to choose an approach and to raise its minimum. "
             "Each key is a rule set id.",
    "checks": "The checks a gate is made of. Each key is a check id.",
    "gates": "The gates: groups of checks cleared at a stage. Each key is a gate id.",
    "artifacts": "The documents an issue can owe, such as the acceptance criteria. Each key is an "
                 "artifact id.",
    "vocabulary": "The display names and aliases of catalogue entries. Each key is "
                  "`<catalogue>.<id>`, for example `approaches.quick-fix`.",
}

ENTRY_DESCRIPTIONS = {
    "dimensions": "One dimension: how its value is chosen and which values it allows.",
    "stages": "One stage: its place in the order and the modes it can run in.",
    "approaches": "One delivery approach: its weight, the mode of each stage, and what it owes.",
    "rules": "One rule set: what kind it is, how matching rules combine and the rules it holds.",
    "checks": "One check: what it asserts, how it is decided and how strictly it applies.",
    "gates": "One gate: the checks it groups, the stage it is cleared at and where it applies.",
    "artifacts": "One artifact: the file that holds it and what it builds on.",
    "vocabulary": "The display name of one catalogue entry, and the other names a person may type "
                  "for it.",
}

OPERATION_DESCRIPTIONS = {
    "set": "Changes only the fields named here and leaves every other field of the inherited "
           "entry as it is.",
    "replace": "When `true`, the entry in this layer replaces the inherited entry as a whole.",
    "remove": "When `true`, removes the inherited entry. This fails while another entry still "
              "refers to it.",
    "locked": "Protects the entry from a change in a later layer that loosens it: `true` lets a "
              "project unlock it, `hard` lets no one.",
    "unlock": "When `true`, lifts a lock the shipped default placed on the entry. Only the "
              "project file may write it, and only with a waiver its owner approves.",
    "waiver": "An approved departure from the layer above, written in the entry it excuses. "
              "It holds `reason`, `approved_by` and, in the project file, `approved_on`.",
}

LIST_DESCRIPTIONS = {
    "whole": "The whole list, written out in full.",
    "changes": "The inherited list changed by adding and removing items.",
    "add": "Items to add to the inherited list.",
    "remove": "Items to remove from the inherited list.",
}

FIELD_DESCRIPTIONS = {
    "dimensions": {
        "type": "How a value of the dimension is chosen: `ordered-enum` is one value from an "
                "ordered list, `enum` is one value from an unordered list and `set` is any "
                "number of values.",
        "values": "The values the dimension allows. For an `ordered-enum` the list is in order, "
                  "and `tighter` says which end is stricter.",
        "tighter": "Which end of `values` is stricter for an `ordered-enum`: `higher` means the "
                   "later values and `lower` the earlier ones. The shipped `risk` and `size` use "
                   "`higher`.",
        "open": "Whether a `set` accepts a value beyond those listed in `common`. "
                "The shipped `labels` set is open.",
        "common": "Values of a `set` that people use often, shown as suggestions. "
                  "The classifier does not compare them.",
        "required": "Whether an assessment must give the dimension a value. "
                    "The shipped `risk`, `familiarity` and `size` are required.",
    },
    "stages": {
        "order": "The stage's place in the sequence, as a whole number from 1. "
                 "The shipped stages run from assess (1) to ship (8).",
        "modes": "The modes the stage can run in, keyed by mode name. Each mode may set a `rank`, "
                 "a whole number where a higher rank means more process.",
        "entry": "The ids of the checks that must hold before the stage starts. "
                 "They run only when the `entry-exit-evaluation` capability is on.",
        "exit": "The ids of the checks that must hold before the stage is finished. "
                "They run only when the `entry-exit-evaluation` capability is on.",
        "mode": "The mode an issue chooses for the stage. Only an issue's own layer sets it.",
    },
    "approaches": {
        "weight": "A whole number that orders approaches from lightest to heaviest, distinct for "
                  "each approach. A floor compares approaches by it, and the shipped weights "
                  "run from 0 (spike) to 4 (full).",
        "ships": "Whether the approach delivers work. It is `true` unless the approach delivers "
                 "nothing, as the shipped spike does.",
        "extends": "The id of another approach this one builds on, so that it states only what "
                   "differs.",
        "stages": "The mode the approach runs each stage in, keyed by stage id.",
        "gates": "The ids of the gates the approach must clear.",
        "artifacts": "The artifacts the approach owes, keyed by artifact id. Each value is a "
                     "depth, `light` or `full`.",
        "subtask_ceiling": "The largest number of subtasks the approach allows, or `null` for no "
                           "limit, where a lower number is stricter. The shipped default is 1 or 2 "
                           "for every approach except full, which has no limit.",
        "checkpoints": "For each autonomy value (`controlled`, `balanced`, `autonomous`), the "
                       "stages at which a session waits for a person.",
    },
    "rules": {
        "kind": "What the rule set does. The shipped kinds are `shapes`, `floors`, `caps`, "
                "`ceilings`, `immovable-gates`, `role-rules`, `advisory` and `biases`.",
        "hit": "How matching rules combine, per effect: `first` stops at the first match, `max` "
               "and `min` take the highest or lowest value, and `collect` gathers every match. "
               "Each effect allows only some of these.",
        "rules": "The rules of the set, keyed by rule id. A rule has an `order`, a `when` "
                 "condition, a `then` effect and a `rationale`.",
    },
    "checks": {
        "statement": "What the check asserts, in plain words. A person reads it to judge a "
                     "`human` or `judged` check.",
        "kind": "How the check reaches its verdict: `deterministic`, `evidence`, `judged` or "
                "`human`.",
        "impl": "The id of the built-in implementation that runs the check. Each implementation "
                "carries a version.",
        "params": "Named values the implementation reads. A ceiling in `params` is compared as "
                  "a number.",
        "accepts": "The evidence types the check accepts. Accepting more types is looser.",
        "reviewers": "Who may review the check. Allowing more reviewers is looser.",
        "approvers": "Who may approve the check. Allowing more approvers is looser.",
        "inputs": "What the check reads. Reading more is stricter.",
        "when": "A condition on the assessment, such as `risk: [critical]`, under which the "
                "check applies.",
        "blocking_when": "A condition on the assessment under which the check blocks.",
        "severity": "Whether a failure blocks (`blocking`) or is only reported (`advisory`). "
                    "`blocking` is stricter.",
        "on_skipped": "The verdict when the check has nothing to check: `pass`, "
                      "`not-applicable` or `fail`, in ascending strictness.",
        "requires": "The capabilities that must be on for the check to run.",
        "locked": "Protects the check from a change that loosens it: `true` lets the project "
                  "owner unlock it and `hard` lets no one.",
    },
    "gates": {
        "kind": "The kind of gate: `guardrail` or `review`.",
        "stage": "The id of the stage at which the gate is cleared.",
        "checks": "The ids of the checks that make up the gate.",
        "accepts": "The evidence types the gate accepts. A gate that lists none accepts any "
                   "type.",
        "when": "A condition on the assessment under which the gate applies.",
        "applies_to": "Which approaches the gate applies to, for example `ships: true` for every "
                      "approach that delivers work.",
        "name": "The gate's display name.",
        "statement": "What the gate demands, in plain words.",
        "locked": "Protects the gate from a change that loosens it: `true` lets the project "
                  "owner unlock it and `hard` lets no one.",
    },
    "artifacts": {
        "file": "The file name of the artifact in the issue's folder, for example "
                "`acceptance-criteria.md`.",
        "depends_on": "The ids of the artifacts this one builds on. A cycle, a bookkeeping "
                      "artifact and a directory are each an error.",
        "checks": "The ids of the checks the artifact carries.",
        "bookkeeping": "Whether the artifact is a record the framework keeps about the work, "
                       "such as the dashboard, the receipt or the verification report. Such "
                       "an artifact is never an input to another.",
    },
    "vocabulary": {
        "name": "The display name of the entry, shown to people in place of its id.",
        "aliases": "Other names a person may type for the entry. A name or alias may belong "
                   "to only one entry of a catalogue.",
    },
}

# The top-level keys of compass.yml and the keys inside them.
TOP_DESCRIPTIONS = {
    "": "A project's one configuration file: its overlay on the shipped default and its "
        "settings. Generated from `cli/compass_pkg/catalogue_spec.py`; do not edit by hand.",
    "schema": "The version of the file format. Its presence also marks `compass.yml` as "
              "Compass's file.",
    "extends": "The parent configuration this file builds on.",
    "extends.name": "A parent named by reference, for example `compass:default@<major>`. A git "
                    "parent ends in `#<sha>`, which pins its commit.",
    "extends.object": "A parent with the approval that goes with it.",
    "extends.from": "The parent reference, in the same form as a plain `extends`.",
    "extends.approved_by": "The name of the person who approved the parent.",
    "extends.approved_on": "The date of that approval.",
    "owner": "The name of the person who owns the project's configuration. The owner approves "
             "waivers and unlocks unless a list of approvers says otherwise.",
    "approvers": "Lists of the people who may approve a waiver, by kind.",
    "approvers.issue-waiver": "The names that may approve a waiver in an issue. When absent, "
                              "the owner approves.",
    "approvers.project-waiver": "The names that may approve a waiver in the project file. A "
                                "parent writes the list; when it is absent, the owner approves.",
    "capabilities": "Named switches for new blocking behaviour. Each is off in the shipped "
                    "default.",
    "capabilities.entry-exit-evaluation": "Whether the entry and exit checks of each stage are "
                                          "evaluated. Off in the shipped default.",
    "capabilities.artifact-freshness": "Whether a change to an artifact marks the artifacts and "
                                       "check results that depend on it as stale. Off in the "
                                       "shipped default.",
    "autonomy": "How often a session stops for a person at a stage hand-off: `controlled` at "
                "every listed hand-off, `balanced` at fewer, `autonomous` never. "
                "The shipped default is `balanced`.",
    "adoption": "Whether a failed check blocks: `enforced` makes `compass check` and "
                "`compass ci` exit non-zero, and `advisory` reports the failure and exits 0. "
                "The shipped default is `enforced`.",
    "governance_drift": "Whether drift from the shipped governance fails: `strict` fails "
                        "`compass policy lint` and `advisory` only reports it. "
                        "The default is `advisory`.",
    "allow_project_commands": "Whether `compass check` may run commands that a project "
                              "guardrail declares, read from the project's own file only. "
                              "The default is `false`.",
    "enforcement": "Extra paths the pre-tool hook guards. Holds `code_globs`, a list of path "
                   "patterns the hook treats as code.",
    "record": "Where the delivery record is kept, with `remote`, `paths` and `names_key`. "
              "Without it no record is kept.",
    "project": "The project's name and test commands. Holds `name`, `test_command`, "
               "`test_micro_command` and `bdd_run_command`.",
    "prices": "Dollars per million tokens for each model name, used to price the usage of a "
              "quick fix. Without it no cost is recorded.",
    "multiagent": "Where multiagent worktrees go and how many are allowed. Holds `worktree_root`"
                  " (default `../.compass-worktrees`) and `max_worktrees` (default 6).",
    "preset_index": "Reserved for published presets. It has no behaviour yet.",
    "preset": "Reserved key for a published preset's own data. It is not part of a layer's "
              "digest.",
}
