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

#: The checks and evidence types the check set gained after
#: `governance/guardrails.yml` froze in 9.0.0 (its first line says so). The
#: frozen file cannot list them, and only the legacy readers read it, so a test
#: that compares the check set with that file leaves them out. #355 added the
#: ship approval, and #356 the request link.
ADDED_AFTER_THE_FREEZE = {"checks": frozenset({"ship-approval-present", "request-recorded"}),
                          "evidence_types": frozenset({"pr-approval"})}


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
