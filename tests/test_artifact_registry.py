"""The artifact registry, and what it means for issues written before it.

An issue directory is a list of filenames. Nothing in it records why a document
exists, and nothing records that a document was deliberately *not* written - so
a reviewer cannot tell a considered omission from a gap.

The registry records both. Its value is the reason, not the filename, which is
why the schema needs one on every entry including the omitted ones.

The risk in this change is not the registry; it is the issues already landed
without one. The resolver reads a registered path first and the old flat
filename second. The case that matters is when neither works: an entry
naming a path that is not there is a broken record, not a decision, and
reporting it as "omitted" is how a document stops being read while the page
says it was left out on purpose.

Scenario ids trace to the-human-front-door/acceptance-criteria.md.
"""

# These tests assert the current file names; files written under older
# names still load (ADR-006).
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# The archive these tests read: the tracked sample, or this checkout's own
# with COMPASS_FULL_ARCHIVE=1 (tests/archive.py).
sys.path.insert(0, str(REPO_ROOT / "tests"))
from archive import archive_root  # noqa: E402
SCHEMA = REPO_ROOT / "schemas" / "manifest.schema.json"
sys.path.insert(0, str(REPO_ROOT / "cli"))


def _spine(tmp_path: Path, artifacts: Optional[List[Dict[str, Any]]] = None,
           files: Optional[Dict[str, str]] = None) -> Path:
    """An issue directory with an optional registry and some files on disk."""
    task_dir = tmp_path / "work" / "t"
    task_dir.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {
        "schema_version": "2.0", "task": "t", "created": "2026-08-23",
        "status": "active",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "standard", "goal": "delivery"},
        "delivery_approach": "feature", "scenarios": [], "changed_files": [],
        "evidence": [], "gates": [],
    }
    if artifacts is not None:
        manifest["artifacts"] = artifacts
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    for name, body in (files or {}).items():
        p = task_dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return task_dir


# ---------------------------------------------------------------------------
# Group A - the registry records what exists and why
# ---------------------------------------------------------------------------

def test_a1_entry_declares_kind_path_status_reason():
    """`TRC-A1`: a registered artifact declares its kind, path, status and reason.

    Checked against the schema rather than an example, so the contract is the
    thing that travels with the framework rather than this repository's habits.
    """
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    arts = schema["properties"].get("artifacts")
    assert arts, "the manifest schema has no `artifacts` registry"
    item = arts["items"]
    for field in ("id", "kind", "status", "reason"):
        assert field in item["properties"], (
            f"a registry entry cannot record its {field!r}")
    assert "path" in item["properties"], (
        "a registry entry cannot record where the document is")


def test_a2_omitted_artifact_records_its_reason():
    """`TRC-A2`: an omitted artifact records why it was omitted.

    This is the half that makes omission visible. A document absent because
    nobody thought of it and one absent for a stated reason look identical in a
    directory listing.
    """
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    status = schema["properties"]["artifacts"]["items"]["properties"]["status"]
    assert "omitted" in status.get("enum", []), (
        "there is no way to record that a document was deliberately not "
        "written: " + repr(status.get("enum")))


def test_a3_schema_refuses_an_entry_with_no_reason():
    """`TRC-A3`: the schema refuses an entry that explains nothing.

    An entry with no reason is a filename in a list. The reason is the whole
    value of the registry, so it is required rather than conventional.
    """
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    item = schema["properties"]["artifacts"]["items"]
    assert "reason" in item.get("required", []), (
        "`reason` is not required, so a registry entry can be added that "
        "explains nothing - which is a directory listing with extra steps")
    assert set(item["properties"]["status"]["enum"]) == {
        "draft", "awaiting-approval", "approved", "superseded", "omitted"}, (
        "the status vocabulary is not the closed set the requirements review "
        "settled: " + repr(item["properties"]["status"].get("enum")))


# ---------------------------------------------------------------------------
# Group B - issues written before the registry
# ---------------------------------------------------------------------------

def test_b1_registered_path_wins(tmp_path):
    """`TRC-B1`: a registered path resolves ahead of the flat filename."""
    from compass_pkg.core import artifact_path
    task_dir = _spine(
        tmp_path,
        artifacts=[{"id": "ART-D", "kind": "technical-design", "path": "30-design/hld.md",
                    "status": "approved", "reason": "an initiative earns one"}],
        files={"30-design/hld.md": "nested", "design.md": "flat"})
    got = artifact_path(str(task_dir), "technical-design.md")
    assert Path(got).read_text() == "nested", (
        "the flat filename won over the registered path, so registering a "
        "document has no effect: " + got)


def test_b2_no_registry_falls_back_to_flat_filename(tmp_path):
    """`TRC-B2`: an issue with no registry still resolves its artifacts.

    Most issue directories in this repository are in this state. It is the
    ordinary case, not a fault.
    """
    from compass_pkg.core import artifact_path, resolve_artifact, FOUND
    task_dir = _spine(tmp_path, artifacts=None, files={"design.md": "flat"})
    got = artifact_path(str(task_dir), "technical-design.md")
    assert Path(got).read_text() == "flat", "an unregistered issue lost its file"
    state, path, reason = resolve_artifact(str(task_dir), "technical-design")
    assert state == FOUND, (
        f"an issue with no registry reported {state!r} rather than found - a "
        f"missing registry is not a fault")


def test_b3_unresolvable_artifact_is_reported(tmp_path):
    """`TRC-B3`: an entry naming a path that is not there is reported, and is not
    reported as omitted.

    Both mean "no document here" and they mean opposite things: one is a
    decision, the other is a broken record.
    """
    from compass_pkg.core import resolve_artifact, UNRESOLVABLE, OMITTED
    task_dir = _spine(
        tmp_path,
        artifacts=[{"id": "ART-D", "kind": "technical-design", "path": "30-design/hld.md",
                    "status": "approved", "reason": "an initiative earns one"}],
        files={})
    state, path, reason = resolve_artifact(str(task_dir), "technical-design")
    assert state == UNRESOLVABLE, (
        f"a registry entry pointing at nothing reported {state!r}")
    assert state != OMITTED, "a broken record was reported as a decision"
    assert "30-design/hld.md" in reason, (
        "the report does not name the registered path it tried: " + reason)
    assert "design.md" in reason, (
        "the report does not name the flat filename it also tried: " + reason)


def test_b3_omitted_is_reported_as_a_decision(tmp_path):
    """`TRC-B3`, the other side: an omission carries its reason and is not
    confused with a broken record."""
    from compass_pkg.core import resolve_artifact, OMITTED
    task_dir = _spine(
        tmp_path,
        artifacts=[{"id": "ART-T", "kind": "threat-model", "status": "omitted",
                    "reason": "no trust-boundary surface changes here"}],
        files={})
    state, path, reason = resolve_artifact(str(task_dir), "threat-model")
    assert state == OMITTED, f"a recorded omission reported {state!r}"
    assert "trust-boundary" in reason, (
        "the omission lost its reason, which is the only thing it carries: "
        + reason)


def test_b4_landed_issues_still_resolve():
    """`TRC-B4`: every issue already in this repository still resolves.

    The compatibility claim, checked against the real archive rather than a
    fixture. Most issue directories have no registry; if any of their
    documents stops resolving, the fallback is wrong.
    """
    from compass_pkg.core import artifact_path
    work = archive_root() / ".compass" / "work"
    if not work.is_dir():
        import pytest
        pytest.skip("no issue archive in this checkout")

    checked = 0
    for issue in sorted(work.iterdir()):
        if not (issue / "manifest.yml").is_file():
            continue
        for doc in issue.glob("*.md"):
            got = artifact_path(str(issue), doc.name)
            assert Path(got).is_file(), (
                f"{issue.name}/{doc.name} resolved to {got}, which does not "
                f"exist - the registry fallback broke a landed issue")
            checked += 1
    assert checked > 0, "no landed artifacts were checked - this guard read nothing"


# ---------------------------------------------------------------------------
# Group F - the artifact set is a routing output
# ---------------------------------------------------------------------------
#
# The registry records WHICH documents an issue has. What it should have is not
# a human's list - it is computed from the assessment, exactly like the stages,
# the gates and the orchestration. Judgement produces the assessment; the
# mechanism produces everything downstream. That is the framework, and an
# artifact set assembled by hand is a checklist someone fills in.

def _evaluate(tmp_path, **readings):
    """Run the evaluator over one assessment and return the written manifest."""
    import shutil, subprocess, sys
    proj = tmp_path / "p"
    (proj / "governance").mkdir(parents=True, exist_ok=True)
    for f in ("routing-policy.yml", "guardrails.yml"):
        shutil.copyfile(REPO_ROOT / "governance" / f, proj / "governance" / f)
    task_dir = proj / ".compass" / "work" / "t"
    task_dir.mkdir(parents=True, exist_ok=True)
    (proj / ".compass" / "current-task").write_text("t\n")
    (proj / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    assessment = {"risk": "contained", "familiarity": "brownfield-mapped",
                  "size": "standard", "goal": "delivery", "role": "engineer",
                  "labels": []}
    assessment.update(readings)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "task": "t", "created": "2026-08-23",
        "status": "active", "assessment": assessment,
        "delivery_approach": None, "stages": {}, "gates": [], "evidence": [],
        "scenarios": [], "changed_files": [],
    }, sort_keys=False))
    r = subprocess.run(
        [sys.executable, str(REPO_ROOT / "cli" / "compass"),
         "approach", "evaluate", "--issue", "t", "--write"],
        cwd=str(proj), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    return yaml.safe_load((task_dir / "manifest.yml").read_text())


def test_f1_evaluator_computes_the_artifact_set():
    """`TRC-F1`: `compass approach evaluate` writes the artifact set.

    Beside `stages`, `gates` and `subtask_ceiling` - the three outputs one
    judgement already produces. This is the fourth.
    """
    policy = yaml.safe_load(
        (REPO_ROOT / "governance" / "routing-policy.yml").read_text(encoding="utf-8"))
    shapes = policy.get("route_shapes") or policy.get("approach_shapes") or {}
    assert shapes, "no shape definitions found in the routing policy"
    for name, shape in shapes.items():
        assert "artifacts" in shape, (
            f"shape {name!r} declares stages, gates and topology but not the "
            f"artifacts it earns - so what an issue documents is not a routed "
            f"decision")


def test_f2_trivial_change_earns_almost_nothing(tmp_path):
    """`TRC-F2`: a trivial, atomic, mapped change earns almost nothing.

    A variable rename does not need a review pack, and nothing special-cases
    that. It falls out of the assessment the same way `clarify: collapsed`
    already does.
    """
    manifest = _evaluate(tmp_path, risk="trivial", size="atomic",
                      familiarity="brownfield-mapped")
    arts = manifest.get("artifacts")
    assert arts is not None, "the evaluator wrote no artifact set"
    earned = [a for a in arts if a.get("status") != "omitted"]
    # BOTH bounds, and the lower one is not decoration. "At most two
    # documents" is also true of no documents, so the test checks the lower
    # bound too. A trivial change earns a small pack, not an absent one.
    assert earned, (
        "a trivial atomic change earned NO documents. The smallest real pack "
        "is one - what changed and why - and an issue with nothing written "
        "down is not the light-touch end of the framework, it is outside it")
    assert len(earned) <= 2, (
        "a trivial atomic rename earned %d documents, which is a form to fill "
        "in rather than the smallest set the work justifies: %s"
        % (len(earned), [a.get("kind") for a in earned]))
    heavy = {"prd", "hld", "test-plan", "test-strategy", "threat-model"}
    assert not (heavy & {a.get("kind") for a in earned}), (
        "a trivial rename earned a heavyweight document")


def test_f3_policy_rule_adds_an_artifact(tmp_path):
    """`TRC-F3`: a policy rule adds an artifact the way it adds a gate.

    `RP-REQUIRE-003` already adds `verify.architecture` on cross-cutting
    risk. The same mechanism has to be able to say "this work earns a
    threat model", otherwise the artifact set can only ever be what the
    shape declares and the assessment's other dimensions buy nothing.
    """
    manifest = _evaluate(tmp_path, risk="critical", size="standard",
                      labels=["auth"])
    arts = manifest.get("artifacts") or []
    kinds = {a.get("kind") for a in arts}
    assert kinds, "the evaluator wrote no artifact set for a critical change"
    fired = [r.get("id") for r in (manifest.get("policy_rules_fired") or [])]

    # The DOCUMENT, not the log line about it. A rule's change log can name
    # "artifact" even when nothing composes the artifact set, so the check
    # below reads the composed document rather than the log line.
    assert "threat-model" in kinds, (
        "auth was in the labels and risk was critical, and no threat model "
        "was earned. Rules fired: %s. Documents earned: %s"
        % (fired, sorted(kinds)))

    # And it carries the rule's own words for why, because "a rule added it"
    # is not a reason a reviewer can act on.
    tm = next(a for a in arts if a.get("kind") == "threat-model")
    assert "trust boundary" in (tm.get("reason") or "").lower(), (
        "the threat model was added with no rationale from the rule that "
        "earned it: %r" % tm.get("reason"))


def test_f4_artifact_set_is_deterministic(tmp_path):
    """`TRC-F4`: same assessment, same artifact set, every time.

    The determinism boundary is the whole point: judgement produces the
    assessment, and everything downstream is mechanism. An artifact set that
    varied between runs would be a fourth output that is not actually routed.
    """
    a = _evaluate(tmp_path / "one", risk="cross-cutting", size="large")
    b = _evaluate(tmp_path / "two", risk="cross-cutting", size="large")
    # Non-empty first. Two runs that both produce nothing agree perfectly, so
    # equality alone is a comparison that holds however broken the evaluator
    # is.
    assert a.get("artifacts"), (
        "the evaluator produced no artifacts at all, so the equality below "
        "would compare two empty lists and report determinism")
    assert a.get("artifacts") == b.get("artifacts"), (
        "the same assessment produced different artifact sets")
