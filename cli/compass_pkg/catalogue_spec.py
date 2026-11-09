# compass_pkg.catalogue_spec - the configuration catalogues' field table
"""The shapes a resolved configuration holds, and the keys `compass.yml` can hold.

A resolved configuration (the check set or a stored generation) holds the
catalogues in `CATALOGUES`. `FIELDS` names the fields of each, which the
retired-word tables (`word_map`) read. The settings keys, the tighten-only keys and the descriptions the
settings schema carries (`settings_lint.schema`) are here too, and `at_least`,
which compares by the shipped orders. No I/O.

Each field records its YAML `type`, whether an entry must hold it
(`required`), and two columns the 8.x configuration layers read: `merge`
(how a child layer changed it) and `compare` (how the classifier compared
it). Since 9.0.0 nothing merges and nothing is classified (ADR-094); the
legacy copy reader still refuses an operation on a `list` or `map` field.
"""
# DEPENDENCY: compass_pkg.stable_ids (constants only).
from __future__ import annotations

from compass_pkg import stable_ids

CATALOGUES = ("dimensions", "stages", "approaches", "rules", "checks", "gates",
              "artifacts", "readiness", "vocabulary")


# A catalogue id: stable, and never a display name (those live in
# `vocabulary`).
ID_PATTERN = r"^[A-Za-z][A-Za-z0-9._-]*$"

SEVERITIES = ("advisory", "blocking")            # ascending strictness
ON_SKIPPED = ("pass", "not-applicable", "fail")  # ascending strictness
# The closed sets of the other enumerated fields. The reader of a governance copy
# refuses a value outside them (`effective._legacy_value_problems`).
DIMENSION_TYPES = ("ordered-enum", "enum", "set")
TIGHTER = ("higher", "lower")
CHECK_KINDS = ("deterministic", "evidence", "judged", "human")
GATE_KINDS = ("review", "guardrail")
LOCKS = (True, "hard")

# The shipped order of the two ordered dimensions, for a `when:` clause
# that uses `at_least:` before any configuration is loaded.
SHIPPED_ORDERS = {
    "risk": ("trivial", "contained", "cross-cutting", "critical"),
    "size": ("atomic", "small", "medium", "large", "product"),
}


def at_least(dimension, threshold, value, orders=None):
    """Does `value` reach `threshold` on an ordered dimension? The order is
    `orders[dimension]` when given, else the shipped order of risk and size
    (ADR-035). A value or threshold outside the order never matches.
    `core.reading_matches` reads it for a `when:` that uses `at_least:`."""
    if orders is not None and dimension in orders:
        order = list(orders[dimension] or ())
    else:
        order = list(SHIPPED_ORDERS.get(dimension) or ())
    return (threshold in order and value in order
            and order.index(value) >= order.index(threshold))

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
# dimension a condition may use (the second is an older spelling that
# `core.WHEN_KEY_MAP` still reads).
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
        "release_line": _f("boolean", "scalar", "ordered"),
        "extends": _f("string", "scalar", "descriptive"),
        "stages": _f("map", "map", "ordered", required=True),
        "gates": _f("list", "list", "obligation-set"),
        "artifacts": _f("map", "map", "obligation-set"),
        "subtask_ceiling": _f("integer-or-null", "scalar", "ceiling"),
        "checkpoints": _f("map", "map", "obligation-set"),
        # The classifier does not read it: the project setting turns the whole
        # strategy off with no approval (the product decision of 2026-10-29), so
        # one approach's routing needs no stronger control.
        "acceptance_strategy": _f("string", "scalar", "never"),
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
        "stage": _f("string", "scalar", "descriptive", required=True),
        "owner": _f("string", "scalar", "descriptive", required=True),
        "audience": _f("string", "scalar", "descriptive", required=True),
        "stands_for": _f("string", "scalar", "descriptive", required=True),
        "sections": _f("map", "map", "descriptive", required=True),
        "required_when": _f("map", "whole", "identity"),
        "word_ceiling": _f("map", "whole", "identity"),
        "every_approach": _f("boolean", "scalar", "descriptive"),
    },
    "readiness": {
        "statement": _f("string", "scalar", "descriptive", required=True),
        "impl": _f("string", "scalar", "identity", required=True),
        "weight": _f("integer", "scalar", "descriptive", required=True),
        "params": _f("map", "map", "ceiling"),
        "required_for_autonomous": _f("boolean", "scalar", "ordered"),
    },
    "vocabulary": {
        "name": _f("string", "scalar", "descriptive", required=True),
        "aliases": _f("list", "list", "descriptive"),
    },
}


AUTONOMY = ("controlled", "balanced", "autonomous")
ADOPTION = ("advisory", "enforced")
# The approver lists a layer names (ADR-039); an unlock is the owner's.
APPROVER_KINDS = ("waiver", "issue-waiver", "project-waiver")


# Named switches for new blocking behaviour, off in the shipped default.
# `artifact-freshness` was removed in 9.0.0 (ADR-091) and is not read; it stays
# valid because stored 8.x generations declare it.
CAPABILITIES = ("entry-exit-evaluation", "artifact-freshness")

# Top-level keys of a layer file (ADR-043).
LAYER_KEYS = ("schema", "extends", "owner", "approvers", "capabilities") + CATALOGUES
SETTINGS_KEYS = ("autonomy", "adoption", "allow_project_commands", "enforcement",
                 "record", "project", "prices", "models", "multiagent", "governance_drift",
                 "preset_index", "github_labels", "language", "acceptance_strategy",
                 "living_spec", "signoff_labels", "require_evidence", "agent_review",
                 "project_checks")
#: The tighten-only settings of `compass.yml` (ADR-094): each can only add to what
#: the check set owes. `capabilities` is one of them, and stays a layer key above
#: so the 8.x merge still reads it. `compass_pkg.tighten` applies them and
#: `compass_pkg.settings_lint` refuses a value that is not one of these shapes.
TIGHTEN_KEYS = ("signoff_labels", "require_evidence", "agent_review", "project_checks",
                "capabilities")
#: The stages a project check (`project_checks`) may run at.
PROJECT_CHECK_STAGES = (stable_ids.STAGE_BUILD, stable_ids.STAGE_SHIP)
#: The pieces of acceptance support code a project names under `project.acceptance_support`.
ACCEPTANCE_SUPPORT = ("alias_helper", "driver_factory", "dsl_root", "layering_test")

# What an issue's own layer (the manifest's `config:`) may hold.
ISSUE_KEYS = ("stages", "checks", "gates", "rules", "autonomy", "ceilings", "approach")


# --- what each field means (`schemas/compass.schema.json` descriptions) ------------------
# The generated schema reads these texts, so a person or an editor sees what
# a field means beside its name. A test fails on a schema node with no text,
# and on an enumeration value its text does not name. Each text says what the
# field is, its allowed values or units, and its shipped default where the
# shipped preset sets one.


# The top-level keys of compass.yml and the keys inside them.
TOP_DESCRIPTIONS = {
    "": "A project's settings file: settings that do not touch the check set, and settings "
        "that only add to it (ADR-094). Generated by `settings_lint.schema()`; do not edit by hand.",
    "schema": "The version of the file format. Its presence also marks `compass.yml` as "
              "Compass's file.",
    "owner": "The name of the person who owns the project's configuration. The owner approves "
             "waivers unless a list of approvers says otherwise.",
    "approvers": "Lists of the people who may approve a waiver, by kind.",
    "approvers.waiver": "The names that may approve a waiver of one check on one issue "
                        "(ADR-094). When absent, issue-waiver is read; when both are "
                        "absent, the owner approves.",
    "approvers.issue-waiver": "The names that may approve a waiver in an issue, read as "
                              "`waiver` from 9.0.0 when that list is absent. When both are "
                              "absent, the owner approves.",
    "capabilities": "Named switches for new blocking behavior. Each is off in the shipped "
                    "default.",
    "capabilities.entry-exit-evaluation": "Whether the entry and exit checks of each stage are "
                                          "evaluated. Off in the shipped default.",
    "autonomy": "How often a session stops for a person at a stage hand-off: `controlled` at "
                "every listed hand-off, `balanced` at fewer, `autonomous` never. "
                "The shipped default is `balanced`.",
    "language": "The language of the prose an agent writes, as a BCP 47 tag: a language, an "
                "optional script and an optional region, joined by hyphens, such as `en-US`. "
                "Unset: no instruction; only the project's own `compass.yml` can hold it, "
                "never a parent, a preset or an issue.",
    "adoption": "Whether a failed check blocks: `enforced` makes `compass check` and "
                "`compass ci` exit non-zero, and `advisory` reports the failure and exits 0. "
                "The shipped default is `enforced`.",
    "allow_project_commands": "Whether `compass check` may run commands that a project "
                              "guardrail declares, read from the project's own file only. "
                              "The default is `false`.",
    "enforcement": "Extra paths the pre-tool hook guards. Holds `code_globs`, a list of path "
                   "patterns the hook treats as code.",
    "record": "Where the delivery record is kept, with `remote`, `paths` and `names_key`, "
              "and whether each issue's record is committed with its code (`commit`). "
              "Without `remote` no record repository is kept.",
    "record.commit": "`true` commits each issue's record with its code and `false` keeps it "
                     "out of the project's git history. Unset, the record is committed unless "
                     "`remote` is set.",
    "project": "The project's name, its commands (`test_command`, `test_micro_command`, "
               "`bdd_run_command` and `layering_command`, which `compass layering record` "
               "runs when given no command), and the paths of its acceptance support code "
               "(`acceptance_support`). Since 9.0.0 (ADR-093) nothing reads `lint_command`, "
               "`format_check_command`, `build_command`, `typecheck_command`, `secret_scan` "
               "or `structured_logging`, which stay valid and which `compass policy lint` "
               "names.",
    "project.acceptance_support": "The paths of the support code of the four-layer acceptance "
                                  "strategy (`S17`), each relative to the project root. "
                                  "`acceptance-support-present` reports a piece with no path, or "
                                  "a path that does not exist, as missing; it opens no file and "
                                  "blocks nothing.",
    "project.acceptance_support.alias_helper": "The path of the alias helper, which makes each "
                                               "identifier a scenario uses unique to the run.",
    "project.acceptance_support.driver_factory": "The path of the driver factory, which picks "
                                                 "the protocol driver at start-up.",
    "project.acceptance_support.dsl_root": "The path of the root of the domain-specific "
                                           "language the specifications call.",
    "project.acceptance_support.layering_test": "The path of the layering test, which checks "
                                                "that each test layer calls only the layer "
                                                "below it.",
    "acceptance_strategy": "Whether the four-layer acceptance strategy (`S17`) is on for the "
                           "project: `state` is `on` or `off`, and `off` needs a `reason`, which "
                           "assess records. Unset means on; only the project's own file can hold "
                           "it.",
    "acceptance_strategy.state": "`on` or `off`.",
    "signoff_labels": "More labels that owe what the four shipped `G5` labels owe: a person's "
                      "sign-off (`human-approval`) and approved scenarios (`scenario-approval`). "
                      "It only adds to `auth`, `payments`, `personal-data` and `migrations`.",
    "signoff_labels.item": "One label name, as an assessment writes it.",
    "require_evidence": "More evidence a delivery issue owes when its assessment matches. "
                        "Each entry adds tokens and never removes one.",
    "require_evidence.item": "One rule: the assessment it applies to (`when`) and the tokens it "
                             "adds (`add`).",
    "require_evidence.when": "A condition on the assessment, such as `risk: [critical]` or "
                             "`labels_any: [billing]`. Absent or empty, the rule applies to "
                             "every delivery issue.",
    "require_evidence.add": "The evidence tokens the rule adds, from the closed set the "
                            "evidence rows use.",
    "require_evidence.token": "One token: `request`, `scenarios`, `red-before-green`, "
                              "`suite-green`, "
                              "`correctness`, `governance`, `traceability`, `regression`, "
                              "`security`, `clarity`, `architecture`, `outer-loop`, `isolation`, "
                              "`layering`, `definition-of-done`, `reproduce-first`, "
                              "`scenario-approval`, `human-approval` or `ship-approval`.",
    "agent_review": "Turns on the advisory judged check `agent-review` at the `ship` stage "
                    "(ADR-090 decision 7). `on` or `true` turns it on, and `off` or `false` "
                    "leaves the default, which is off.",
    "agent_review.switch": "`true` turns the check on and `false` leaves it off.",
    "agent_review.word": "`on` turns the check on and `off` leaves it off.",
    "project_checks": "The project's own checks, each a command that must exit 0. "
                      "`compass check` runs one only when `allow_project_commands` is `true`.",
    "project_checks.item": "One project check: its `id`, `name`, `command`, `stage` and an "
                           "optional `when`.",
    "project_checks.id": "The check's id, which must not be the id of a shipped check or "
                         "gate, or of a check Compass deleted.",
    "project_checks.name": "The check's display name.",
    "project_checks.command": "The command `compass check` runs from the project root; exit "
                              "0 passes.",
    "project_checks.stage": "The stage the check is cleared at: `build` or `ship`.",
    "project_checks.when": "A condition on the assessment under which the check applies. "
                           "Absent, it applies to every issue that ships.",
    "acceptance_strategy.reason": "Why the project turned the strategy off. Required with `off`.",
}
