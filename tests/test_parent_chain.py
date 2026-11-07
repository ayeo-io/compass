"""Chains of git parents, to depth three (issue `parent-chains`).

A git parent can name a git parent of its own. Each one is pinned by sha,
fetched the same way and checked as data. These tests build local git
repositories in a temporary folder and point `COMPASS_PARENT_REMOTE_BASE` at
them, so nothing reaches the network.

Scenario ids: `PC-1` to `PC-8`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

# --- PC-8: the docs ----------------------------------------------------------------------------

def test_pc_8_the_cycle_code_is_a_code_the_lint_can_name():
    from compass_pkg import policy_lint
    assert "L-PARENT-CYCLE" in policy_lint.FINDING_CODES


# --- PC-9: a parent's waiver answers to that parent's owner, at every depth --------------------

def _waiver_chain(place, *, approver, owner=True, above=None):
    """A lint over three parent layers where parent `place` carries a waiver
    approved by `approver`. Each parent's owner is `owner-<n>`. `above`, when
    set, is the `approvers.project-waiver` list of the layer above `place`."""
    from compass_pkg import layers, policy_lint
    import waiver_fixtures as fx
    default, _ = policy_lint.load_parent()
    parents = []
    for n in range(3):
        doc = {"schema": 1}
        if owner or n != place:
            doc["owner"] = f"owner-{n}"
        if n == place:
            # A human check the shipped default holds; it has no Definition of Ready
            # since 9.0.0 (ADR-092).
            doc["checks"] = {"dod-suite-green": {
                "set": {"severity": "advisory"},
                "waiver": fx.project_waiver(approved_by=approver)}}
        if above is not None and n == place - 1:
            doc["approvers"] = {"project-waiver": above}
        parents.append(layers.Layer(f"github:a/p{n}@1#abc123{n}", "parent", doc,
                                    layers.layer_digest(doc, "parent")))
    own = {"schema": 1, "owner": "project-owner"}
    project = layers.Layer("project", "project", own, layers.layer_digest(own, "project"))
    return policy_lint.lint_chain(default, project, extra_parents=parents, today=fx.TODAY), parents


@pytest.mark.parametrize("place", [0, 1, 2], ids=["furthest", "middle", "nearest"])
def test_pc_9_the_owner_of_a_parent_may_approve_that_parents_waiver(place):
    report, _ = _waiver_chain(place, approver=f"owner-{place}")
    assert [f.code for f in report.errors] == []


@pytest.mark.parametrize("place", [0, 1, 2], ids=["furthest", "middle", "nearest"])
def test_pc_9_the_owner_of_another_layer_may_not_approve_a_parents_waiver(place):
    others = [f"owner-{n}" for n in range(3) if n != place] + ["project-owner"]
    for approver in others:
        report, parents = _waiver_chain(place, approver=approver)
        assert [(f.code, f.layer) for f in report.errors] \
            == [("W-APPROVER-NOT-ALLOWED", parents[place].name)], approver


@pytest.mark.parametrize("place", [0, 1, 2], ids=["furthest", "middle", "nearest"])
def test_pc_9_a_parent_with_no_owner_cannot_carry_a_waiver(place):
    report, _ = _waiver_chain(place, approver="project-owner", owner=False)
    assert [f.code for f in report.errors] == ["W-NO-OWNER"]


@pytest.mark.parametrize("place", [1, 2], ids=["middle", "nearest"])
def test_pc_9_a_name_in_the_approvers_of_the_layer_above_may_approve(place):
    report, _ = _waiver_chain(place, approver="named-approver", above=["named-approver"])
    assert [f.code for f in report.errors] == []
    report, parents = _waiver_chain(place, approver="named-approver")
    assert [(f.code, f.layer) for f in report.errors] \
        == [("W-APPROVER-NOT-ALLOWED", parents[place].name)]
