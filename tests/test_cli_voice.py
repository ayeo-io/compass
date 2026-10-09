"""The CLI speaks the v2 register.

These tests assert the v2 verb map: approach evaluate, follow-up resolve
(states outstanding -> resolved), retro, plan lint, issue
lint/receipt/set-status, ship-commit, and the terminology verb. Retired
verbs and the tolerated --task and --reading flag spellings were removed at <!-- vocabulary-scan: allow - names the retired flag spellings this suite removed -->
the major version (ADR-014); what remains of those contracts is asserted in
tests/test_no_deprecation_stubs.py, which checks they no longer parse. The
cli/ scan surface is enforced and widened to cli/compass_pkg/ string
literals, and the receipt speaks v2 change-type names and shows recorded
orchestration overrides.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
CLI = REPO_ROOT / "cli" / "compass"

V2_SPINE = {
    "schema_version": "2.0", "task": "t", "created": "2026-08-07",
    "status": "active",
    "assessment": {"risk": "cross-cutting", "familiarity": "brownfield-mapped",
                   "size": "large", "goal": "delivery",
                   "role": "engineer", "labels": []},
    "delivery_approach": "expedition", "topology": "swarm",
    "policy_rules_fired": [],
    "stages": {}, "evidence": [], "gates": [], "scenarios": [],
    "changed_files": [], "claims": [],
    "follow_ups": [{"id": "BF-1", "description": "promote the test",
                    "status": "outstanding"}],
    "reassessments": [], "friction": [],
}


def _project(tmp_path, manifest=None, approach_md="# Delivery approach\n"):
    root = tmp_path / "proj"
    shutil.copytree(REPO_ROOT / "governance", root / "governance")
    (root / ".compass").mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n")
    d = root / ".compass" / "work" / "t"
    d.mkdir(parents=True)
    (d / "delivery-approach.md").write_text(approach_md)
    (d / "manifest.yml").write_text(
        yaml.safe_dump(manifest or dict(V2_SPINE), sort_keys=False))
    (root / ".compass" / "current-task").write_text("t\n")
    return root


def _run(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=str(root),
                          capture_output=True, text=True, timeout=60)


def test_the_v2_verbs_exist_and_work(tmp_path):
    """`TRC-1`: each renamed verb does what its predecessor did, and
    terminology renders the vocabulary file."""
    root = _project(tmp_path)
    r = _run(root, "approach", "evaluate", "--issue", "t", "--write")
    assert r.returncode == 0, r.stderr[-400:]
    out = yaml.safe_load(
        (root / ".compass" / "work" / "t" / "manifest.yml").read_text())
    assert out.get("delivery_approach"), "approach evaluate wrote nothing"

    r = _run(root, "issue", "lint", "--issue", "t")
    assert r.returncode == 0, r.stderr[-400:]
    r = _run(root, "issue", "receipt", "--issue", "t")
    assert r.returncode == 0, r.stderr[-400:]
    r = _run(root, "plan", "lint", "--help")
    assert r.returncode == 0
    r = _run(root, "retro")
    assert r.returncode == 0, r.stderr[-400:]
    r = _run(root, "follow-up", "resolve", "--issue", "t", "BF-1")
    assert r.returncode == 0, r.stderr[-400:]
    r = _run(root, "terminology", "receipt")
    assert r.returncode == 0, r.stderr[-400:]
    assert "receipt" in r.stdout.lower()
    r = _run(root, "ship-commit", "--help")
    assert r.returncode == 0
    assert "ship" in r.stdout.lower()


# tests/test_no_deprecation_stubs.py asserts that retired verbs fail
# (RCD-F2).


def test_the_issue_flag_is_the_only_spelling(tmp_path):
    """`TRC-3`: the help text teaches --issue, and its metavar speaks v2.

    tests/test_no_deprecation_stubs.py asserts that --task no longer <!-- vocabulary-scan: allow - names the retired flag spelling that no longer parses -->
    parses (RCD-F3). The help-text assertions below are unchanged.
    """
    root = _project(tmp_path)
    r = _run(root, "check", "--help")
    assert "--issue" in r.stdout, "check --help does not document --issue"
    # The metavar speaks v2 too: "--issue TASK" would teach the banned word <!-- vocabulary-scan: allow - names the retired metavar the help screen must not print -->
    # from the help screen itself.
    assert re.search(r"--issue\s+SLUG", r.stdout), (
        "the --issue flag's metavar is not SLUG:\n" + r.stdout)
    assert not re.search(r"\bTASK\b", r.stdout), (
        "help output still prints the v1 metavar TASK:\n" + r.stdout)
    r = _run(root, "approach", "evaluate", "--help")
    assert not re.search(r"\bREADING\b|\bTASK\b", r.stdout), (
        "evaluate --help still prints a v1 metavar:\n" + r.stdout)


def test_follow_up_states_outstanding_resolved_with_1x_readable(tmp_path):
    """`TRC-4`: the resolver writes 'resolved'; a 1.x manifest carrying
    owed/paid is normalised read-side so checks still see the truth."""
    root = _project(tmp_path)
    r = _run(root, "follow-up", "resolve", "--issue", "t", "BF-1")
    assert r.returncode == 0, r.stderr[-400:]
    out = yaml.safe_load(
        (root / ".compass" / "work" / "t" / "manifest.yml").read_text())
    assert out["follow_ups"][0]["status"] == "resolved", out["follow_ups"]

    sys.path.insert(0, str(REPO_ROOT / "cli"))
    from compass_pkg.core import normalize_spine
    old = dict(V2_SPINE)
    old["follow_ups"] = [
        {"id": "BF-1", "description": "d", "status": "owed"},
        {"id": "BF-2", "description": "d", "status": "paid"},
    ]
    norm = normalize_spine(old)
    states = [f["status"] for f in norm["follow_ups"]]
    assert states == ["outstanding", "resolved"], (
        f"1.x values not normalised: {states}")


OVERRIDE_MD = """# Delivery approach - t

## Topology: human override recorded

| What was overridden | From -> To | Who | Why |
|---|---|---|---|
| Topology | swarm -> solo | maintainer, 2026-08-07 | interlocked rename |
"""


def test_output_speaks_v2_shape_names_and_receipt_shows_overrides(tmp_path):
    """`TRC-5`: the receipt prints 'initiative' for the machine value
    'expedition' and shows the recorded orchestration override; the
    evaluator's output uses v2 shape names too."""
    root = _project(tmp_path, approach_md=OVERRIDE_MD)
    r = _run(root, "issue", "receipt", "--issue", "t")
    assert r.returncode == 0, r.stderr[-400:]
    assert "full" in r.stdout, (
        "receipt does not translate 'expedition' to 'full':\n"
        + r.stdout)
    assert "expedition" not in r.stdout.lower(), (
        "receipt still prints the machine value 'expedition':\n" + r.stdout)
    assert re.search(r"overridden:?\s+solo", r.stdout), (
        "receipt does not show the recorded topology override:\n" + r.stdout)

    r = _run(root, "approach", "evaluate", "--issue", "t")
    assert r.returncode == 0, r.stderr[-400:]
    assert "expedition" not in r.stdout.lower(), (
        "the evaluator still prints v1 shape names:\n" + r.stdout)


def test_vocabulary_carries_receipt_follow_up_and_bump():
    """`TRC-6`: version past 2.0.0-pre6; a receipt term with the evidence
    disambiguation; the follow-up entry speaks outstanding/resolved."""
    doc = yaml.safe_load(
        (REPO_ROOT / "governance" / "terminology.yml").read_text())
    m = re.fullmatch(r"2\.0\.0-pre(\d+)", str(doc["version"]))
    assert m and int(m.group(1)) > 6, (
        f"version is {doc['version']} - this diff carries a bump past pre6")
    receipt = doc["terms"].get("receipt")
    assert receipt, "no receipt term in the vocabulary"
    assert "evidence" in str(receipt.get("means", "")), (
        "the receipt term lacks the evidence disambiguation")
    follow_up = doc["terms"]["follow-up"]
    joined = str(follow_up)
    assert "outstanding" in joined and "resolved" in joined, (
        "the follow-up entry does not speak outstanding/resolved")


def test_cli_surface_enforced_and_widened():
    """`TRC-7`: cli/compass left pending (file and baseline);
    cli/compass_pkg/ is a scanned surface; the migrate map is exempt."""
    from test_terminology import PENDING_BASELINE
    scan = yaml.safe_load(
        (REPO_ROOT / "governance" / "terminology.yml").read_text())["scan"]
    assert "cli/compass" not in scan["pending_surfaces"], (
        "cli/compass is still pending in terminology.yml")
    assert "cli/compass" not in PENDING_BASELINE, (
        "cli/compass is still in the committed baseline")
    assert "cli/compass_pkg/" in scan["surfaces"], (
        "the scan surface was not widened to cli/compass_pkg/")
    # Asserted as "not scanned" rather than "exempt": the exemption excluded
    # nothing, because `scan.exempt` only applies to files under
    # `scan.surfaces` and this file is under none of them.
    reachable = [sfc for sfc in scan["surfaces"]
                 if "cli/migrate-map.yml".startswith(sfc.rstrip("/") + "/")
                 or sfc == "cli/migrate-map.yml"]
    assert not reachable, (
        f"cli/migrate-map.yml is now reachable from {reachable} and would be "
        f"scanned - the v1-to-v2 pointer data must name v1 spellings")
    assert (REPO_ROOT / "cli" / "migrate-map.yml").is_file(), (
        "cli/migrate-map.yml does not exist")


def test_compass_backfill_tolerance_re_tightened():
    """`TRC-8`: 'compass backfill' in prose is flagged like any other use - <!-- vocabulary-scan: allow - names the retired verb this test proves is still banned -->
    no lookbehind exemption applies."""
    from test_terminology import BAN_PATTERNS
    line = "settle it with compass " + "backfill pay before shipping"
    hits = [p for p in BAN_PATTERNS["backfill"] if p.search(line)]
    assert hits, (
        "'compass backfill' in prose is still tolerated - the CLI-voice "
        "slice ends that tolerance")
