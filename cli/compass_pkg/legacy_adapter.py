# compass_pkg.legacy_adapter - today's policy files as one catalogue-form layer
"""Convert a routing policy and a guardrails file into catalogue form.

The shipped defaults move into `governance/presets/default/`, one file per
catalogue (ADR-042). Until the loader reads that directory, today's two files
are the only description of the defaults, so the preset is produced from
them by this adapter, once, and committed. The adapter then stays as the
bridge for projects that still carry copies of the two files, which are read
as an overlay of the same form.

It reads data and returns data. It changes no behaviour and no argument:
every value is copied before it is renamed. Old key names are read through
the migration map the loaders use, so a policy copied before the renames
converts to the same document as today's.

What the legacy format holds that the catalogue form has no field for goes
to a sidecar, `legacy.yml`, which only the generator of the legacy files
reads: each guardrail's full `checked_at` list, the legacy spelling of a
value or a `when:` key, the order of keys inside a rule, the order of the
autonomy rows, the fallback approach and the generated rule that stands for
it, both file versions and `project:`. With the preset it holds every value
of today's two files, so they can be rebuilt from it. Three things also
change shape in the catalogue itself:

- the fallback approach (`default_route`) becomes the last rule of the
  `default_shapes` set, matching every assessment;
- the free-text `biases` become a rule set with no effect;
- a guardrail's `checked_at` keeps its first stage as the gate's `stage`,
  which the design records and does not enforce.
"""
# DEPENDENCY: PyYAML (bundled); compass_pkg.core, compass_pkg.routing,
# compass_pkg.catalogue_spec, compass_pkg.stable_ids.
from __future__ import annotations

import copy
import os

import yaml

from compass_pkg import core
from compass_pkg.catalogue_spec import CAPABILITIES
from compass_pkg.routing import canonical_routes
from compass_pkg.stable_ids import (APPROACH_REGULAR, APPROACH_SPIKE, GATE_G5, GATE_SPIKE_CONCLUDE, STAGE_ASSESS,
                                    STAGE_IDS, STAGE_SHIP, STAGE_VERIFY)

PRESET_ID = "default"
PRESET_VERSION = "6.0.0"
PRESET_FILES = ("dimensions", "stages", "approaches", "rules", "checks", "gates",
                "artifacts", "vocabulary")

# The eight stages in the order they run. A stage an approach names that is
# not here is appended, so an unusual policy still converts.
STAGE_ORDER = STAGE_IDS

# A mode has a rank only when it sits on the depth ladder. Every other mode
# differs in kind, not in depth, so it has no rank and the classifier treats
# it as incomparable. The one mode above `full` is "full, plus more". The ranks
# reproduce today's lift, which raises exactly `collapsed`, `skipped` and
# `light` to `full` and leaves every other mode as it is.
MODE_RANKS = {"skipped": 0, "collapsed": 1, "light": 2, "full": 3,
              "full-plus-backfill": 4}  # vocabulary-scan: allow - machine enum value that manifests on disk carry

# The dimensions that have an order, and which way is stricter.
ORDERED_DIMENSIONS = ("risk", "size")
REQUIRED_DIMENSIONS = ("risk", "familiarity", "size")

# How two rules that set the same effect combine. A selector is not an
# effect and has no entry: `ceiling` picks which loop ceiling `limit` sets,
# and `until` says when a blocked stage opens again.
EFFECT_HITS = {
    "force_minimum_approach": "max",
    "lean_toward": "first",
    "max_worktrees": "min",
    "limit": "min",
}
SELECTORS = ("ceiling", "until")

# Effects the catalogue form names differently (ADR-041).
RENAMED_EFFECTS = {"force_minimum_route": "force_minimum_approach",
                   "forbid_route": "forbid_approach"}
STAGE_EFFECTS = ("require_phase", "block_phase", "never_skip")
ARTIFACT_EFFECTS = ("add_artifact", "require_artifact", "suggest_artifact")

# Locks (ADR-039). The human sign-off guardrail `G5` and its check cannot be
# unlocked by anyone.
LOCKED_STAGES = (STAGE_ASSESS, STAGE_VERIFY, STAGE_SHIP)
LOCKED_REVIEW_GATES = (GATE_SPIKE_CONCLUDE,)
HARD_GUARDRAILS = (GATE_G5,)

# What a check reports when it cannot run, read from each module that
# returns `NOTHING_TO_CHECK` for it: checks.py (scenarios-are-executable,
# claim-traces-to-scenario, command-passes), borrowed_docs.py, binding.py
# (evidence-matches-tree), dashboard.py, landed_by.py, multiagent_check.py
# and evidence_identity.py. The check declared-tests-resolve returns a pass
# with a note. Every other check fails. `tests/test_obligations.py` replays
# these verdicts against the archive sample.
DECLINING_CHECKS = (
    "scenarios-are-executable", "claim-traces-to-scenario", "command-passes",
    "borrowed-documents-answered", "evidence-matches-tree",
    "evidence-identity-matches", "dashboard-current", "landed-by-resolves",
    "multiagent-run-recorded",
)
PASSING_CHECKS = ("declared-tests-resolve",)

# The order the generator rebuilds a rule or a guardrail in unless the
# sidecar says the legacy file differs.
GUARDRAIL_KEYS = ("id", "name", "statement", "checks", "applies_when", "checked_at")

_FALLBACK_RULE = "RP-SHAPE-FALLBACK"


class _Notes:
    """What the catalogue form cannot hold, collected while converting, for
    the sidecar."""

    def __init__(self):
        self.policy_when = {}
        self.guardrail_when = {}
        self.legacy_values = {}
        self.rule_key_order = {}
        self.guardrail_key_order = {}
        self.checked_at = {}


def _dimension_name(name):
    name = core.ASSESSMENT_KEY_MAP.get(name, name)
    return core.WHEN_KEY_MAP.get(name, name)


def _when(when, seen=None):
    """A `when:` clause with current dimension names, copied. `seen` collects
    each renamed key, current spelling to legacy spelling."""
    if not isinstance(when, dict):
        return copy.deepcopy(when)
    out = {}
    for key, value in when.items():
        new = core.WHEN_KEY_MAP.get(key, key)
        if seen is not None and new != key:
            seen[new] = key
        if new == "any_of" and isinstance(value, list):
            out[new] = [_when(c, seen) for c in value]
        else:
            out[new] = copy.deepcopy(value)
    return out


def _stage(name):
    return core._stage_key_renames().get(name, name)


def _artifact_id(value):
    value = str(value)
    return value[:-3] if value.endswith(".md") else value


# --- dimensions ----------------------------------------------------------------

def _dimensions(policy):
    vocabulary = {
        _dimension_name(k): v
        for k, v in (policy.get("assessment_vocabulary")
                     or policy.get("reading_vocabulary") or {}).items()}
    out = {}
    for name, values in vocabulary.items():
        if name == "labels_common":
            continue
        entry = {"type": "ordered-enum" if name in ORDERED_DIMENSIONS else "enum",
                 "values": list(values)}
        if name in ORDERED_DIMENSIONS:
            entry["tighter"] = "higher"
        if name in REQUIRED_DIMENSIONS:
            entry["required"] = True
        out[name] = entry
    # Labels are an open set: the common values are suggestions.
    out["labels"] = {"type": "set", "open": True,
                     "common": list(vocabulary.get("labels_common") or [])}
    return out


# --- approaches and stages -------------------------------------------------------

def _approaches(policy):
    shapes = policy.get("route_shapes") or {}
    table = policy.get("autonomy_checkpoints") or {}
    out = {}
    for name, shape in shapes.items():
        entry = {
            "weight": shape["weight"],
            "ships": name != APPROACH_SPIKE,
            # `shape_stages` also reads the retired `phases:` block.
            "stages": core.shape_stages(shape),
            "gates": list(shape.get("gates") or []),
            "artifacts": {_artifact_id(k): v
                          for k, v in (shape.get("artifacts") or {}).items()},
            # A shape with no ceiling allows one subtask, as the evaluator reads it.
            "subtask_ceiling": shape.get("subtask_ceiling", 1),
        }
        # An autonomy level or approach the table leaves out waits at every
        # hand-off, so it is left out here too rather than given an empty list.
        checkpoints = {level: [_stage(s) for s in row[name]]
                       for level, row in table.items()
                       if isinstance(row, dict) and name in row}
        if checkpoints:
            entry["checkpoints"] = checkpoints
        if name == APPROACH_SPIKE:
            entry["locked"] = True
        out[name] = entry
    return out


def _stages(approaches):
    used = {}
    for approach in approaches.values():
        for stage, mode in approach["stages"].items():
            used.setdefault(stage, [])
            if mode not in used[stage]:
                used[stage].append(mode)
    names = [s for s in STAGE_ORDER if s in used]
    names += [s for s in used if s not in STAGE_ORDER]
    out = {}
    for order, stage in enumerate(names, start=1):
        modes = sorted(used[stage], key=lambda m: (m not in MODE_RANKS,
                                                   MODE_RANKS.get(m, 0), m))
        entry = {"order": order,
                 "modes": {m: ({"rank": MODE_RANKS[m]} if m in MODE_RANKS else {})
                           for m in modes}}
        if stage in LOCKED_STAGES:
            entry["locked"] = True
        out[stage] = entry
    return out


# --- rules -------------------------------------------------------------------------

def _effect(key, value):
    """An effect in its catalogue spelling: the key, then the value."""
    key = RENAMED_EFFECTS.get(key, key)
    if key in STAGE_EFFECTS:
        value = [_stage(v) for v in value] if isinstance(value, list) else _stage(value)
    elif key in ARTIFACT_EFFECTS:
        value = _artifact_id(value)
    return key, copy.deepcopy(value)


def _convert_rule(rule, notes):
    """`(id, when, then, extra)` for one legacy rule. Every key but `id`,
    `when` and `rationale` is an effect, so none is lost; what the new
    spelling cannot say goes to the notes."""
    rule_id = rule["id"]
    when = _when(rule["when"], notes.policy_when) if "when" in rule else None
    then = {}
    for key, value in rule.items():
        if key in ("id", "when", "rationale"):
            continue
        new_key, new_value = _effect(key, value)
        then[new_key] = new_value
        if new_value != value:
            notes.legacy_values.setdefault(rule_id, {})[key] = copy.deepcopy(value)
    default = ["id"] + (["when"] if when is not None else []) \
        + [k for k in rule if k not in ("id", "when", "rationale")] \
        + (["rationale"] if "rationale" in rule else [])
    if list(rule) != default:
        notes.rule_key_order[rule_id] = list(rule)
    extra = {"rationale": rule["rationale"]} if "rationale" in rule else {}
    return rule_id, when, then, extra


def _rule_set(kind, rules, locked=False):
    """A rule set from `(id, when, then, extra)` tuples, with a hit policy
    for each effect any rule sets."""
    hit, body = {}, {}
    for order, (rule_id, when, then, extra) in enumerate(rules, start=1):
        rule = {"order": order}
        if when is not None:
            rule["when"] = when
        if then:
            rule["then"] = then
        rule.update(extra)
        body[rule_id] = rule
        for effect in then:
            if effect not in SELECTORS:
                hit.setdefault(effect, EFFECT_HITS.get(effect, "collect"))
    out = {"kind": kind, "hit": hit, "rules": body}
    if locked:
        out["locked"] = True
    return out


def _rules(policy, notes):
    strategies = policy.get("routing_strategies") or {}
    guard = policy.get("routing_guardrails") or {}

    def converted(items):
        return [_convert_rule(r, notes) for r in items or []]

    out = {}
    shapes = converted(strategies.get("default_shapes"))
    shapes.append((_FALLBACK_RULE, {}, {"lean_toward":
                   strategies.get("default_route", APPROACH_REGULAR)},
                   {"rationale": "No other shape matched, so the working default."}))
    out["default_shapes"] = _rule_set("shapes", shapes)
    out["floors"] = _rule_set("floors", converted(guard.get("floors")))
    out["caps"] = _rule_set("caps", converted(guard.get("caps")))
    out["loop_ceilings"] = _rule_set("ceilings", converted(guard.get("loop_ceilings")))
    out["immovable_gates"] = _rule_set(
        "immovable-gates", converted(guard.get("immovable_gates")), locked=True)
    out["role_rules"] = _rule_set("role-rules", converted(guard.get("role_rules")))
    out["advisory"] = _rule_set("advisory", converted(strategies.get("advisory_strategies")))
    out["role_defaults"] = _rule_set("advisory", converted(strategies.get("role_defaults")))
    out["biases"] = _rule_set("biases", [
        (f"RP-BIAS-{i:03d}", None, {}, {"rationale": str(text)})
        for i, text in enumerate(strategies.get("biases") or [], start=1)])
    return out


# --- checks and gates ------------------------------------------------------------

def _locked_by_gate(guardrails):
    """Each check's lock: `hard` when a hard-locked guardrail holds it,
    `true` when any other guardrail does."""
    locks = {}
    for group in ("defaults", "spike_guardrails"):
        for gate in guardrails.get(group) or []:
            level = "hard" if gate["id"] in HARD_GUARDRAILS else True
            for check in gate.get("checks") or []:
                if locks.get(check) != "hard":
                    locks[check] = level
    return locks


def _checks(guardrails, notes):
    locks = _locked_by_gate(guardrails)
    out = {}
    for name, body in (guardrails.get("checks") or {}).items():
        entry = {"statement": body["description"], "kind": "deterministic",
                 "impl": name, "severity": "blocking"}
        if "blocking_when" in body:
            entry["blocking_when"] = _when(body["blocking_when"], notes.guardrail_when)
        entry["on_skipped"] = ("not-applicable" if name in DECLINING_CHECKS
                               else "pass" if name in PASSING_CHECKS else "fail")
        if name in locks:
            entry["locked"] = locks[name]
        out[name] = entry
    return out


def _first_stage(guardrail):
    for stage in guardrail.get("checked_at") or []:
        return _stage(stage)
    return None


def _guardrail_gate(guardrail, ships, notes):
    notes.checked_at[guardrail["id"]] = list(guardrail.get("checked_at") or [])
    default = [k for k in GUARDRAIL_KEYS if k in guardrail]
    if list(guardrail) != default:
        notes.guardrail_key_order[guardrail["id"]] = list(guardrail)
    entry = {"kind": "guardrail", "name": guardrail["name"],
             "statement": guardrail["statement"]}
    stage = _first_stage(guardrail)
    if stage:
        entry["stage"] = stage
    entry["applies_to"] = {"ships": ships}
    if "applies_when" in guardrail:
        entry["when"] = _when(guardrail["applies_when"], notes.guardrail_when)
    entry["checks"] = list(guardrail.get("checks") or [])
    entry["locked"] = "hard" if guardrail["id"] in HARD_GUARDRAILS else True
    return entry


def _gates(policy, guardrails, approaches, rules, notes):
    out = {}
    for g in guardrails.get("defaults") or []:
        out[g["id"]] = _guardrail_gate(g, True, notes)
    for g in guardrails.get("spike_guardrails") or []:
        out[g["id"]] = _guardrail_gate(g, False, notes)
    immovable = {r["gate"] for r in
                 (policy.get("routing_guardrails") or {}).get("immovable_gates") or []}
    accepted = guardrails.get("gate_evidence_requirements") or {}
    # A gate an approach or a rule names but the requirements do not list
    # accepts any evidence type, which an entry with no `accepts` says.
    review = list(accepted)
    for approach in approaches.values():
        review += [g for g in approach["gates"] if g not in review]
    for rule_set in rules.values():
        for rule in rule_set["rules"].values():
            for key in ("add_gate", "gate"):
                gate = (rule.get("then") or {}).get(key)
                if gate and gate not in review:
                    review.append(gate)
    for gate in review:
        entry = {"kind": "review", "stage": "verify"}
        if gate in accepted:
            entry["accepts"] = list(accepted[gate])
        if gate in immovable or gate in LOCKED_REVIEW_GATES:
            entry["locked"] = True
        out[gate] = entry
    return out


# --- artifacts and vocabulary ----------------------------------------------------

def _artifacts(approaches, rules):
    names = []

    def note(value):
        value = _artifact_id(value)
        if value not in names:
            names.append(value)

    for approach in approaches.values():
        for artifact in approach["artifacts"]:
            note(artifact)
    for rule_set in rules.values():
        for rule in rule_set["rules"].values():
            for key in ("add_artifact", "require_artifact", "suggest_artifact"):
                if key in (rule.get("then") or {}):
                    note(rule["then"][key])
    return {name: {"file": f"{name}.md"} for name in names}


# A display name a person would not guess from the id. The id keeps its
# name; the display name says what the check asks today.
DISPLAY_NAMES = {
    "checks.backfills-paid": "Follow-ups resolved",
    "checks.dod-evidence-typed": "Definition of Done evidence is typed",
    "checks.landed-by-resolves": "Landed-by resolves",
    "checks.spike-no-production-changes": "Spike changes no production code",
}


def _humanise(identifier):
    text = identifier.replace("-", " ")
    return text[:1].upper() + text[1:]


def _vocabulary(approaches, stages, checks, gates):
    out = {}
    for name in approaches:
        out[f"approaches.{name}"] = {"name": core.display_shape(name), "aliases": []}
    for name in stages:
        out[f"stages.{name}"] = {"name": core.display_stage(name), "aliases": []}
    for name, gate in gates.items():
        if "name" in gate:
            out[f"gates.{name}"] = {"name": gate["name"], "aliases": []}
    for name in checks:
        out[f"checks.{name}"] = {
            "name": DISPLAY_NAMES.get(f"checks.{name}", _humanise(name)),
            "aliases": []}
    return out


# --- the public surface -----------------------------------------------------------

def _convert(policy, guardrails):
    policy, _renamed = canonical_routes(policy or {})
    guardrails = copy.deepcopy(guardrails or {})
    notes = _Notes()
    approaches = _approaches(policy)
    stages = _stages(approaches)
    rules = _rules(policy, notes)
    checks = _checks(guardrails, notes)
    gates = _gates(policy, guardrails, approaches, rules, notes)
    document = {
        "schema": 1,
        "dimensions": _dimensions(policy),
        "stages": stages,
        "approaches": approaches,
        "rules": rules,
        "checks": checks,
        "gates": gates,
        "artifacts": _artifacts(approaches, rules),
        "vocabulary": _vocabulary(approaches, stages, checks, gates),
    }
    table = policy.get("autonomy_checkpoints") or {}
    views = {
        "schema": 1,
        "routing_policy": {
            "version": policy.get("version"),
            "default_route": (policy.get("routing_strategies") or {}).get(
                "default_route", APPROACH_REGULAR),
            "generated_rules": [_FALLBACK_RULE],
            "autonomy_checkpoints": {level: list(row) for level, row in table.items()
                                     if isinstance(row, dict)},
            "when_keys": notes.policy_when,
            "rule_key_order": notes.rule_key_order,
            "legacy_values": notes.legacy_values,
        },
        "guardrails": {
            "version": guardrails.get("version"),
            "project": guardrails.get("project"),
            "when_keys": notes.guardrail_when,
            "checked_at": notes.checked_at,
            "key_order": notes.guardrail_key_order,
        },
    }
    return document, views


def adapt(policy, guardrails):
    """One layer document in catalogue form from a routing policy and a
    guardrails file: `schema: 1` and the eight catalogues."""
    return _convert(policy, guardrails)[0]


def legacy_views(policy, guardrails):
    """What the two files hold that the catalogues have no field for, for the
    generator of the legacy views (`governance/legacy-views.yml`)."""
    return _convert(policy, guardrails)[1]


def adapt_evidence_types(guardrails):
    """The evidence types as the preset's ninth data set. A project cannot
    add, change or remove one, so it is not a catalogue."""
    types = (guardrails or {}).get("evidence_types") or {}
    return {"schema": 1,
            "evidence_types": {name: {"description": body["description"]}
                               for name, body in types.items()}}


def lock_summary(document):
    """The entries a document locks, by lock level, as `catalogue.id`."""
    hard, locked = [], []
    for catalogue in PRESET_FILES:
        for entry_id, entry in (document.get(catalogue) or {}).items():
            level = entry.get("locked") if isinstance(entry, dict) else None
            if level == "hard":
                hard.append(f"{catalogue}.{entry_id}")
            elif level:
                locked.append(f"{catalogue}.{entry_id}")
    return {"hard": hard, "locked": locked}


_HEADER = (
    "# The shipped default preset: the source of the shipped defaults.\n"
    "# The two files governance/routing-policy.yml and governance/guardrails.yml\n"
    "# are generated from these files and governance/legacy-views.yml.\n"
    "# Change a default here, then run python3 scripts/generate-legacy-views.py.\n"
    "# Also raise the version in legacy-views.yml, then run the script with --pin\n"
    "# and again with --pin-hashes, which update the digest and drift fixtures.\n"
    "# cli/compass_pkg/legacy_adapter.py wrote the first version of these files from\n"
    "# those two files. The preset is the source now; edit it here.\n")

_MODE_NOTE = ("  # vocabulary-scan: allow - machine enum value that manifests on "
              "disk already carry\n")


def _dump(data):
    text = yaml.safe_dump(data, sort_keys=False, default_flow_style=None,
                          allow_unicode=True, width=100)
    # A mode id that the vocabulary scan retires is data, not prose, so each
    # line that holds one carries its own marker rather than a path exemption.
    lines = []
    for line in text.splitlines(keepends=True):
        if "full-plus-backfill" in line:  # vocabulary-scan: allow - the id being marked
            line = line.rstrip("\n") + _MODE_NOTE
        lines.append(line)
    return "".join(lines)


def preset_files(policy, guardrails):
    """The preset's ten files as `{file name: text}`."""
    document = adapt(policy, guardrails)
    files = {
        "preset.yml": _HEADER + _dump({
            "schema": 1, "id": PRESET_ID, "version": PRESET_VERSION,
            "capabilities": {name: False for name in CAPABILITIES},
            "locks": lock_summary(document)}),
        "evidence-types.yml": _HEADER + _dump(adapt_evidence_types(guardrails)),
    }
    for name in PRESET_FILES:
        files[f"{name}.yml"] = _HEADER + _dump({"schema": 1, name: document[name]})
    return files


_VIEWS_HEADER = (
    "# What governance/routing-policy.yml and governance/guardrails.yml hold that the\n"
    "# preset in governance/presets/default/ has no field for: the values the generator\n"
    "# of those two views needs to rebuild them. Only that generator reads this file.\n"
    "# It goes with the views at 7.0.0.\n")


def legacy_views_text(policy, guardrails):
    return _VIEWS_HEADER + _dump(legacy_views(policy, guardrails))


def write_preset(directory, policy=None, guardrails=None, views_path=None):
    """Write the preset to `directory`, and the legacy-view values to
    `views_path`, from today's two files unless given."""
    governance = os.path.join(core.FRAMEWORK_ROOT, "governance")
    policy = policy if policy is not None else core.load_yaml(
        os.path.join(governance, "routing-policy.yml"))
    guardrails = guardrails if guardrails is not None else core.load_yaml(
        os.path.join(governance, "guardrails.yml"))
    os.makedirs(directory, exist_ok=True)
    for name, text in preset_files(policy, guardrails).items():
        with open(os.path.join(directory, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    views_path = views_path or os.path.join(governance, "legacy-views.yml")
    with open(views_path, "w", encoding="utf-8") as fh:
        fh.write(legacy_views_text(policy, guardrails))
