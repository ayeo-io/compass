"""The check set in the shape of the files of the preset it replaced.

Until 9.0.0 the shipped defaults were the files of `governance/presets/default/`,
one catalogue each, and tests read them one file at a time. 9.0.0 replaced the
preset with the fixed check set (`governance/check-set.yml`, ADR-094), which
holds the same catalogues with no `locked:` field. `shipped(name)` gives the
check set's content in the shape the preset file `name` had, so a test keeps
its guarantee about the shipped defaults with one change of reader.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

def shipped(name):
    """The mapping the preset file `name` (such as `checks.yml`) held, read from
    the check set."""
    from compass_pkg import check_set
    doc, resolved = check_set.load(), check_set.resolved()
    stem = name[:-len(".yml")] if name.endswith(".yml") else name
    if stem == "preset":
        return {"schema": 1, "id": doc["id"], "version": doc["version"],
                "capabilities": dict(doc["capabilities"]),
                "never_waived": list(doc["never_waived"])}
    if stem == "evidence-types":
        return {"schema": 1, "evidence_types": resolved["evidence_types"]}
    if stem == "vocabulary":
        return {"schema": 1, "vocabulary": resolved.get("vocabulary") or {}}
    return {"schema": 1, stem: resolved.get(stem) or {}}


def view(name):
    """The check set in the shape of the 8.x view `name`, `routing-policy.yml` or
    `guardrails.yml`. 9.0.0 deleted the two views (ADR-098); a test that read one
    for the shipped defaults reads this instead. The routing policy is what the
    evaluator reads (`EffectiveView.evaluator_policy`); the guardrails mapping has
    the view's keys `defaults`, `spike_guardrails`, `project`, `checks`,
    `evidence_types` and `gate_evidence_requirements`."""
    from compass_pkg import check_set, effective
    resolved = check_set.resolved()
    shown = effective.EffectiveView("live", None, None, resolved, {})
    if name == "routing-policy.yml":
        return shown.evaluator_policy()
    if name != "guardrails.yml":
        raise ValueError(f"no 8.x view is named {name!r}")
    gates = shown.guardrail_gates()
    requirements, _known = shown.gate_requirements()
    # The view listed the checks an implementation runs, not the human or judged
    # ones of the Definition of Done, each with its statement as `description`.
    return {"checks": {check_id: dict(body, description=body.get("statement"))
                       for check_id, body in (resolved.get("checks") or {}).items()
                       if isinstance(body, dict) and body.get("kind") == "deterministic"},
            "evidence_types": dict(resolved.get("evidence_types") or {}),
            "gate_evidence_requirements": requirements,
            "defaults": gates["defaults"], "spike_guardrails": gates["spike_guardrails"],
            "project": []}
