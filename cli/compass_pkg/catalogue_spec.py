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

ARTIFACT_DEPTHS = ("light", "full")              # ascending strictness
AUTONOMY = ("controlled", "balanced", "autonomous")
ADOPTION = ("advisory", "enforced")
# The approver lists a layer names (ADR-039); an unlock is the owner's.
APPROVER_KINDS = ("issue-waiver", "project-waiver")

# The classifier compares at most this many named set values (ADR-037).
LABEL_CAP = 8

# Named switches for new blocking behaviour, off in the shipped default.
CAPABILITIES = ("entry-exit-evaluation", "artifact-freshness")

# Top-level keys of a layer file (ADR-043).
LAYER_KEYS = ("schema", "extends", "owner", "approvers", "capabilities") + CATALOGUES
SETTINGS_KEYS = ("autonomy", "adoption", "allow_project_commands", "enforcement",
                 "record", "project", "prices", "multiagent", "preset_index")
RESERVED_KEYS = ("preset",)

# What an issue's own layer (the manifest's `config:`) may hold.
ISSUE_KEYS = ("stages", "checks", "gates", "rules", "autonomy", "ceilings", "approach")
