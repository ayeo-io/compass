"""Layer documents, resolved configurations and evidence records for the
waiver tests. Each builder returns a fresh dictionary, so a test changes its
own copy. The configurations are the classifier's small ones, so a test can
classify a layer in a fraction of a second."""
from __future__ import annotations

import copy
from datetime import date

TODAY = date(2026, 10, 7)


def parent_config():
    import classifier_fixtures
    return classifier_fixtures.base()


def project_waiver(**over):
    body = {"reason": "Scenarios are written at plan in this repo.",
            "approved_by": "jed72", "approved_on": date(2026, 10, 5)}
    body.update(over)
    return {k: v for k, v in body.items() if v is not None}


def issue_waiver(**over):
    body = {"reason": "The spec is a one-line fix.", "approved_by": "EV-1"}
    body.update(over)
    return {k: v for k, v in body.items() if v is not None}


def severity_layer(waiver=None, check="tests-pass", severity="advisory"):
    """A layer that lowers one check's severity, with the given waiver."""
    entry = {"set": {"severity": severity}}
    if waiver is not None:
        entry["waiver"] = waiver
    return {"checks": {check: entry}}


def approval(**over):
    """A `human-approval` record naming the waiver it approves."""
    body = {"id": "EV-1", "type": "human-approval", "decision": "approved",
            "approver": "jed72", "role": "owner", "scope": "waiver",
            "timestamp": "2026-10-07T09:00:00Z",
            "waiver": {"scope": "issue", "entry": "checks.tests-pass",
                       "fields": {"severity": {"from": "blocking", "to": "advisory"}}}}
    body.update(over)
    return body


def resolve(parent, layer, kind="project"):
    from compass_pkg import merge
    return merge.apply(copy.deepcopy(parent), {"schema": 1, **layer}, kind, f"test-{kind}")[0]
