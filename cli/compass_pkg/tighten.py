# compass_pkg.tighten - apply the tighten-only settings to a resolved configuration
"""The five settings of `compass.yml` that can only add to the check set (ADR-094).

`apply(base, settings)` takes a resolved configuration, in the shape a
generation's `resolved.yml` holds, and returns a new one with the settings
applied. It only adds:

- `signoff_labels`: unions the labels into the `when.labels_any` of gate `G5`;
- `require_evidence`: appends each rule to the top-level `require_evidence`
  list, with an id `RP-SETTING-<n>`, which `evidence_required` reads;
- `agent_review: on`: adds the check set's `optional.agent_review` block, the
  advisory judged check `agent-review` listed at the `ship` stage's entry
  (ADR-090 decision 7);
- `project_checks`: adds one `command-passes` check and one guardrail gate per
  entry, each under the entry's own id;
- `capabilities: {entry-exit-evaluation: true}`: switches the capability on.

No code path removes an entry, lowers a severity or narrows a `when:`. A
setting whose value is not one of these shapes is refused with
`CompassError` before anything is applied (`settings_lint.value_problems`).

`evaluator_settings(resolved)` gives the two keys the evidence evaluator reads
from a resolved configuration, and `with_settings(policy, resolved)` adds them
to an evaluator policy. Nothing calls this module yet: the resolver reads it
once it reads the check set (#357, step 7).
"""
# DEPENDENCY: standard library (copy); compass_pkg.catalogue_spec, compass_pkg.check_set,
# compass_pkg.core (CompassError), compass_pkg.evidence_required (G5_LABELS),
# compass_pkg.settings_lint and compass_pkg.stable_ids (GATE_G5).
from __future__ import annotations

import copy

from compass_pkg import catalogue_spec as spec
from compass_pkg import check_set, settings_lint
from compass_pkg.core import CompassError
from compass_pkg.evidence_required import G5_LABELS
from compass_pkg.stable_ids import GATE_G5

#: The id of the judged check `agent_review: on` adds. Its entry and the stage
#: that lists it are the check set's `optional.agent_review` block, which
#: `check_set.resolved()` leaves out.
AGENT_REVIEW = settings_lint.AGENT_REVIEW
#: The prefix of the id each `require_evidence` rule fires under.
RULE_PREFIX = "RP-SETTING-"


def settings_of(doc):
    """The tighten-only settings `doc` (a `compass.yml` mapping) holds, as a
    copy."""
    if not isinstance(doc, dict):
        return {}
    return {key: copy.deepcopy(doc[key]) for key in spec.TIGHTEN_KEYS if key in doc}


def _on(value):
    return value is True or value == "on"


def apply(base, settings, check_set_doc=None):
    """`base` with `settings` applied, as a new mapping; `base` is not changed.
    `check_set_doc` is the loaded check set the optional entries are read from,
    `check_set.load()` by default. Raises `CompassError` naming each problem when a setting is unknown or its
    value is not a shape that adds."""
    settings = settings or {}
    problems = [(key, "not a tighten-only setting") for key in settings
                if key not in spec.TIGHTEN_KEYS]
    problems += settings_lint.value_problems(settings, base)
    if problems:
        raise CompassError("the tighten-only settings cannot be applied:\n  - "
                           + "\n  - ".join(f"{path}: {message}" for path, message in problems))
    out = copy.deepcopy(base)
    if settings.get("signoff_labels"):
        _add_signoff_labels(out, settings["signoff_labels"])
    if settings.get("require_evidence"):
        _add_required_evidence(out, settings["require_evidence"])
    if _on(settings.get("agent_review")):
        _add_agent_review(out, check_set_doc)
    for entry in settings.get("project_checks") or ():
        _add_project_check(out, entry)
    for name, on in (settings.get("capabilities") or {}).items():
        if on is True and name == "entry-exit-evaluation":
            out.setdefault("capabilities", {})[name] = True
    return out


def _add_signoff_labels(out, labels):
    gate = (out.get("gates") or {}).get(GATE_G5)
    if not isinstance(gate, dict):
        raise CompassError(f"signoff_labels: the configuration holds no gate {GATE_G5} "
                           f"to add the labels to")
    when = gate.setdefault("when", {})
    held = list(when.get("labels_any") or ())
    when["labels_any"] = held + [label for label in dict.fromkeys(labels) if label not in held]


def _add_required_evidence(out, rules):
    held = out.setdefault("require_evidence", [])
    for rule in rules:
        held.append({"id": f"{RULE_PREFIX}{len(held) + 1}",
                     "when": copy.deepcopy(rule.get("when") or {}),
                     "add": list(rule["add"])})


def _add_agent_review(out, check_set_doc=None):
    """Add the check set's `optional.agent_review` block: its checks, unless the
    configuration already holds one of the same id, and its ids in each stage
    list it names."""
    doc = check_set_doc if check_set_doc is not None else check_set.load()
    block = (doc.get("optional") or {}).get("agent_review") or {}
    if not block.get("checks"):
        raise CompassError("agent_review: the check set holds no optional agent review "
                           "to turn on")
    checks = out.setdefault("checks", {})
    for check_id, body in block["checks"].items():
        if check_id not in checks:
            checks[check_id] = copy.deepcopy(body)
    for stage_id, lists in (block.get("stages") or {}).items():
        stage = out.setdefault("stages", {}).setdefault(stage_id, {})
        for key, ids in lists.items():
            held = list(stage.get(key) or ())
            stage[key] = held + [i for i in ids if i not in held]


def _add_project_check(out, entry):
    check_id = entry["id"]
    check = {"statement": entry["name"], "kind": "deterministic", "impl": "command-passes",
             "severity": "blocking", "on_skipped": "not-applicable",
             "params": {"command": entry["command"]}}
    gate = {"kind": "guardrail", "name": entry["name"], "statement": entry["name"],
            "stage": entry["stage"], "applies_to": {"ships": True}, "checks": [check_id]}
    if entry.get("when"):
        gate["when"] = copy.deepcopy(entry["when"])
    out.setdefault("checks", {})[check_id] = check
    out.setdefault("gates", {})[check_id] = gate


def evaluator_settings(resolved):
    """The keys the evidence evaluator reads from `resolved`: `signoff_labels`,
    the labels gate `G5` names beyond the four shipped ones, and
    `require_evidence`. A key with nothing in it is left out."""
    gate = ((resolved or {}).get("gates") or {}).get(GATE_G5) or {}
    named = ((gate.get("when") or {}) if isinstance(gate, dict) else {}).get("labels_any") or ()
    out = {}
    extra = [label for label in named if label not in G5_LABELS]
    if extra:
        out["signoff_labels"] = extra
    if (resolved or {}).get("require_evidence"):
        out["require_evidence"] = copy.deepcopy(resolved["require_evidence"])
    return out


def with_settings(policy, resolved):
    """An evaluator policy (`EffectiveView.evaluator_policy()`) with the keys
    of `evaluator_settings` added."""
    return {**policy, **evaluator_settings(resolved)}
