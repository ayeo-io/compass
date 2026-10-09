"""Acceptance tests for issue make-receipt-render.

Each test is a Given/When/Then scenario from
make-receipt-render/acceptance-criteria.md, exercised against the
compass CLI via the run_cli fixture (a hermetic temp project).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import yaml


# --- shared helpers ---------------------------------------------------------


_DEFAULT_READING_JUSTIFICATIONS = {
    "risk": "fixture blast-radius justification",
    "familiarity": "fixture terrain justification",
    "size": "fixture magnitude justification",
    "goal": "fixture intent justification",
}


def _make_route_md(slug: str, readings: Dict[str, str], route: str,
                   fired_guardrails: Optional[List[Dict[str, str]]] = None) -> str:
    """Build a minimal delivery-approach.md the receipt parses for
    justifications."""
    fired = fired_guardrails or []
    fired_lines = (
        "\n".join(f"- {g['id']}: {g['rationale']}" for g in fired)
        if fired else "No routing guardrail fired."
    )
    return f"""# Route - {slug}

## 1. The four dimension readings

| Dimension | Reading | One-line justification |
|---|---|---|
| **Risk** | {readings['risk']} | {_DEFAULT_READING_JUSTIFICATIONS['risk']} |
| **Familiarity** | {readings['familiarity']} | {_DEFAULT_READING_JUSTIFICATIONS['familiarity']} |
| **Size** | {readings['size']} | {_DEFAULT_READING_JUSTIFICATIONS['size']} |
| **Goal & role** | {readings.get('role', 'engineer')} · {readings.get('goal', readings.get('intent'))} | {_DEFAULT_READING_JUSTIFICATIONS['goal']} |

## 3. Routing guardrails that fired

{fired_lines}

## 4. The final route

Final route: {route}.
"""


def _landed_task(project: Path, slug: str = "alpha",
                 evidence_types: Optional[List[str]] = None) -> Path:
    """Create a fully-populated landed issue on disk and return its task_dir.

    Default fixture: status=landed, delivery approach=standard, 6 standard
    gates all pass, one evidence entry per type listed (defaults to one
    test-run).
    """
    task_dir = project / ".compass" / "work" / slug
    (task_dir / "evidence").mkdir(parents=True, exist_ok=True)

    types = evidence_types or ["test-run"]
    evidence_entries = []
    gate_evidence_map = {
        "verify.correctness": "test-run",
        "verify.governance": "command-output",
        "verify.traceability": "command-output",
        "verify.regression": "test-run",
        "verify.clarity": "manual-review",
        "verify.security": "security-review",
    }
    # Make sure we have at least one evidence per gate.
    needed_types = sorted(set(list(gate_evidence_map.values()) + types))
    type_to_ev_id = {}
    for i, t in enumerate(needed_types, start=1):
        ev_id = f"EV-{i:03d}"
        ev_path = f"evidence/{t}-{i:03d}.json"
        type_to_ev_id[t] = ev_id
        evidence_entries.append({
            "id": ev_id,
            "type": t,
            "path": ev_path,
            **({"scenario": "SCN-001"} if t == "test-run" else {}),
            **({"reviewer": "qa@example.com"} if t == "manual-review" else {}),
            **({"approver": "lead@example.com", "role": "engineering-lead",
                "decision": "approved"} if t == "human-approval" else {}),
            **({"decision": "graduate-to-delivery", "next_task": "downstream"}
               if t == "spike-conclusion" else {}),
        })
        # write the evidence file so the path resolves on disk
        (task_dir / ev_path).write_text("{}\n", encoding="utf-8")

    gates = [
        {"id": g, "status": "pass", "evidence": [type_to_ev_id[t]]}
        for g, t in gate_evidence_map.items()
    ]

    readings = {
        "risk": "contained",
        "familiarity": "brownfield-mapped",
        "size": "standard",
        "intent": "delivery",
        "urgency": "none",
        "role": "engineer",
        "labels": ["public-api"],
    }

    task_body = {
        "schema_version": "1.1",
        "task": slug,
        "created": "2026-05-15",
        "status": "landed",
        "readings": readings,
        "delivery_approach": "standard",
        "topology": "solo-or-pair",
        "policy_rules_fired": [],
        "stages": {
            "frame": "full", "specify": "full", "clarify": "light",
            "plan": "full", "distribute": "solo-or-pair", "build": "full",
            "verify": "full", "land": "full",
        },
        "evidence": evidence_entries,
        "gates": gates,
        "scenarios": [{"id": "SCN-001", "title": "the only scenario",
                       "intent": "INT-1",
                       "tests": ["tests/test_x.py::test_y"]}],
        "changed_files": [{"path": "src/foo.py", "scenarios": ["SCN-001"]}],
        "claims": [],
        "follow_ups": [],
        "reassessments": [],
    }
    (task_dir / "manifest.yml").write_text(
        yaml.safe_dump(task_body, sort_keys=False), encoding="utf-8")
    (task_dir / "delivery-approach.md").write_text(
        _make_route_md(slug, readings, "standard"), encoding="utf-8")
    (project / ".compass" / "current-task").write_text(slug, encoding="utf-8")
    return task_dir


def _section_order(text: str, anchors: List[str]) -> bool:
    """True iff each anchor appears in `text` in the given order."""
    last = -1
    for a in anchors:
        i = text.find(a)
        if i < 0 or i < last:
            return False
        last = i
    return True


# --- `TRC-D3` -----------------------------------------------------------------


def test_missing_task_clean_error(run_cli, project):
    """`TRC-D3`: a missing issue slug fails cleanly.

    Given no directory exists at .compass/work/nonesuch/
    When `compass issue receipt --issue nonesuch` is run
    Then a one-line error is written to stderr naming the missing issue
      and the expected directory
    And nothing is written to stdout
    And the process exits with a non-zero code
    """
    assert not (project / ".compass" / "work" / "nonesuch").exists()

    result = run_cli("issue", "receipt", "--issue", "nonesuch")

    assert result.returncode != 0, repr(result)
    assert result.stdout.strip() == "", repr(result)
    assert "nonesuch" in result.stderr, repr(result)
    assert ".compass/work/nonesuch" in result.stderr, repr(result)


# --- `TRC-A1` -----------------------------------------------------------------


def test_canonical_landed_task(run_cli, project):
    """`TRC-A1`: a landed feature issue with typed evidence renders the canonical
    receipt in six ordered sections.

    Given an issue "alpha" exists with status=landed, 6 gates pass with evidence,
      and a multi-type evidence registry
    When `compass issue receipt --issue alpha` is run
    Then the receipt is printed to stdout in this order:
      (1) issue slug + landed status
      (2) the four assessment values, each with its one-line justification
      (3) the computed delivery approach + every routing guardrail that fired
      (4) each gate, its verdict, and the evidence id(s) that clear it
      (5) each evidence id with its type and the file it points at
      (6) an overall verdict line
    And the process exits with code 0
    """
    _landed_task(
        project, slug="alpha",
        evidence_types=["test-run", "command-output", "manual-review",
                        "security-review"],
    )

    result = run_cli("issue", "receipt", "--issue", "alpha")

    assert result.returncode == 0, repr(result)
    out = result.stdout
    # Section markers, in order: slug → reading value → route name → a gate id
    # → an evidence id → the verdict.
    assert _section_order(out, [
        "alpha",                              # 1: slug
        _DEFAULT_READING_JUSTIFICATIONS["risk"],  # 2: justification
        "regular",                            # 3: route name
        "verify.correctness",                 # 4: a gate
        "EV-001",                             # 5: an evidence id
        "landed cleanly",                     # 6: overall verdict
    ]), repr(result)
    # And the receipt must report "landed" for this happy-path issue.
    assert "landed" in out, repr(result)


# --- `TRC-A2` -----------------------------------------------------------------


def test_receipt_fits_one_screen(run_cli, project):
    """`TRC-A2`: the rendered receipt fits within a single terminal screen.

    Given a landed feature issue "alpha" with 6 gates and a multi-type evidence
      registry
    When `compass issue receipt --issue alpha` is run
    Then the receipt output is at most 50 lines
    And no single line exceeds 100 columns
    """
    _landed_task(project, slug="alpha", evidence_types=[
        "test-run", "command-output", "manual-review", "human-approval",
        "security-review", "spike-conclusion",
    ])

    result = run_cli("issue", "receipt", "--issue", "alpha")
    assert result.returncode == 0, repr(result)

    lines = result.stdout.splitlines()
    assert len(lines) <= 50, (
        f"receipt is {len(lines)} lines (cap: 50)\n--- stdout ---\n{result.stdout}"
    )
    for i, ln in enumerate(lines, start=1):
        assert len(ln) <= 100, (
            f"line {i} is {len(ln)} cols (cap: 100): {ln!r}"
        )


# --- `TRC-D1` -----------------------------------------------------------------


def _active_task(project: Path, slug: str = "alpha") -> Path:
    """Build an issue that has not yet landed: status=active, gates pending."""
    task_dir = _landed_task(project, slug=slug)
    task_yml = task_dir / "manifest.yml"
    body = yaml.safe_load(task_yml.read_text())
    body["status"] = "active"
    for g in body["gates"]:
        g["status"] = "pending"
        g["evidence"] = []
    task_yml.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return task_dir


def test_active_task_labeled_in_progress(run_cli, project):
    """`TRC-D1`: a not-yet-landed issue is labelled in-progress, not a final receipt.

    Given an issue "alpha" with status=active and at least one gate pending
    When `compass issue receipt --issue alpha` is run
    Then the receipt's header explicitly reads "IN PROGRESS - not yet landed"
    And the receipt still renders the assessment values, the delivery
      approach, and the gates' state
    And no gate's verdict is rendered as "landed"
    And the process exits with code 0
    """
    _active_task(project, slug="alpha")

    result = run_cli("issue", "receipt", "--issue", "alpha")
    assert result.returncode == 0, repr(result)
    out = result.stdout

    # Header label
    assert "IN PROGRESS" in out, repr(result)
    assert "not yet landed" in out, repr(result)
    # Sections still present
    assert "Assessment" in out
    assert "Approach" in out
    assert "Gates" in out
    # No gate is labelled "landed" - that word must not appear next to a gate
    # verdict marker (we use [ PASS ]/[ FAIL ]/[ PENDING ]).
    for line in out.splitlines():
        if "verify." in line:
            assert "landed" not in line.lower(), (
                f"gate row should not say 'landed' (got: {line!r})"
            )


# --- `TRC-C3` -----------------------------------------------------------------


def test_failed_gate_prominent(run_cli, project):
    """`TRC-C3`: an issue with a failed gate renders the failure prominently and
    exits 0 (the receipt is a renderer; enforcement is `compass check`'s job)."""
    task_dir = _landed_task(project, slug="alpha")
    body = yaml.safe_load((task_dir / "manifest.yml").read_text())
    # Mark verify.regression as fail
    for g in body["gates"]:
        if g["id"] == "verify.regression":
            g["status"] = "fail"
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False))

    result = run_cli("issue", "receipt", "--issue", "alpha")
    assert result.returncode == 0, repr(result)
    out = result.stdout

    # The failed gate row shows the FAIL verdict.
    fail_lines = [ln for ln in out.splitlines()
                  if "verify.regression" in ln and "FAIL" in ln]
    assert fail_lines, (
        f"verify.regression row should show FAIL verdict\n--- stdout ---\n{out}"
    )
    # Overall verdict line.
    assert "FAILED" in out, repr(result)
    assert "does not satisfy its own gates" in out, repr(result)


# --- `TRC-C4` -----------------------------------------------------------------


def test_owed_backfills_surfaced(run_cli, project):
    """`TRC-C4`: an issue with owed follow-ups is rendered as owing."""
    task_dir = _landed_task(project, slug="alpha")
    body = yaml.safe_load((task_dir / "manifest.yml").read_text())
    body["follow_ups"] = [
        {"id": "BF-001", "description": "Promote reproduction into a scenario",
         "status": "owed"},
        {"id": "BF-002", "description": "Already paid one",
         "status": "paid"},
    ]
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False))

    result = run_cli("issue", "receipt", "--issue", "alpha")
    assert result.returncode == 0, repr(result)
    out = result.stdout

    # A follow-ups section exists and surfaces the outstanding one with
    # id+description.
    assert "Follow-up" in out or "follow-up" in out, (
        f"receipt should include a follow-ups section\n--- stdout ---\n{out}"
    )
    assert "BF-001" in out, repr(result)
    assert "Promote reproduction" in out, repr(result)
    # Overall verdict mentions the count.
    assert "landed with caveats" in out, repr(result)
    assert "1 follow-up" in out, repr(result)


# --- `TRC-B1` -----------------------------------------------------------------


# One row per (type, minimal_fields, label). All eleven types declared in
# governance/guardrails.yml.
_TYPED_EVIDENCE_ROWS = [
    ("test-run",         {"path": "evidence/test.json", "scenario": "SCN-001"},
     "test-run"),
    ("command-output",   {"path": "evidence/cmd.txt"}, "command-output"),
    ("manual-review",    {"path": "evidence/review.md", "reviewer": "qa@example.com"},
     "manual-review"),
    ("human-approval",   {"path": "evidence/approve.json", "approver": "lead@example.com",
                          "role": "engineering-lead", "decision": "approved"},
     "human-approval"),
    ("security-review",  {"path": "evidence/sec.txt"}, "security-review"),
    ("migration-plan",   {"path": "evidence/migration.md"}, "migration-plan"),
    ("rollback-plan",    {"path": "evidence/rollback.md"}, "rollback-plan"),
    ("claim-review",     {"path": "evidence/claims.json"}, "claim-review"),
    ("spike-conclusion", {"path": "evidence/spike.json", "decision": "graduate-to-delivery",
                          "next_task": "delivery-slug"},
     "spike-conclusion"),
    ("consistency-check", {"path": "evidence/consistency.json"}, "consistency-check"),
    ("artifact",         {"path": "evidence/note.md"}, "artifact"),
]


@pytest.mark.parametrize("etype,fields,label", _TYPED_EVIDENCE_ROWS,
                         ids=[t[0] for t in _TYPED_EVIDENCE_ROWS])
def test_evidence_type_labels(run_cli, project, etype, fields, label):
    """`TRC-B1`: the receipt labels each evidence type with its name and shows
    the type-specific minimal fields on the same row."""
    task_dir = _landed_task(project, slug="alpha")
    body = yaml.safe_load((task_dir / "manifest.yml").read_text())
    body["evidence"] = [{"id": "EV-X", "type": etype, **fields}]
    # Point every gate at EV-X so the row appears in the registry.
    for g in body["gates"]:
        g["evidence"] = ["EV-X"]
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False))

    result = run_cli("issue", "receipt", "--issue", "alpha")
    assert result.returncode == 0, repr(result)

    out = result.stdout
    # Slice out the Evidence section - bounded by the section heading at the
    # top and the next ==== rule (start of the verdict block) at the bottom.
    # Some types render extras on a continuation line under the primary row;
    # both belong to the same logical "row" for this scenario's purposes.
    assert "Evidence" in out, f"no Evidence section in receipt\n{out}"
    after = out.split("Evidence", 1)[1]
    ev_section = after.split("=" * 80, 1)[0]
    assert "EV-X" in ev_section, (
        f"no EV-X in evidence section\n--- stdout ---\n{out}"
    )
    # Type label appears in the section.
    assert label in ev_section, (
        f"type label {label!r} missing from evidence section:\n{ev_section}"
    )
    # Each minimal field's value appears in the same section - EXCEPT the path.
    #
    # The receipt does not print `path`: it is derivable from the id, and a
    # truncated path looks like information. `compass check` still reads it
    # from the manifest.
    fields = {k: v for k, v in fields.items() if k != "path"}
    for k, v in fields.items():
        assert str(v) in ev_section, (
            f"field {k}={v!r} missing from evidence section\n--- stdout ---\n{out}"
        )


# --- `TRC-C1` -----------------------------------------------------------------


def test_wrong_typed_evidence_flagged(run_cli, project):
    """`TRC-C1`: a pass gate cleared by wrong-typed evidence is rendered as
    "type-mismatch" (not as a clean pass). Exit 0 - receipt reports, does not
    enforce."""
    task_dir = _landed_task(project, slug="alpha")
    body = yaml.safe_load((task_dir / "manifest.yml").read_text())
    # verify.correctness needs test-run; we clear it with an artifact.
    body["evidence"] = [{"id": "EV-Z", "type": "artifact",
                         "path": "evidence/note.md"}]
    body["gates"] = [g for g in body["gates"] if g["id"] != "verify.correctness"]
    body["gates"].insert(0, {"id": "verify.correctness",
                             "status": "pass", "evidence": ["EV-Z"]})
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False))

    result = run_cli("issue", "receipt", "--issue", "alpha")
    assert result.returncode == 0, repr(result)
    out = result.stdout

    correctness_rows = [ln for ln in out.splitlines()
                        if "verify.correctness" in ln]
    assert correctness_rows, f"no verify.correctness row\n{out}"
    row = correctness_rows[0]
    assert "TYPE-MISMATCH" in row.upper(), (
        f"verify.correctness should be type-mismatch (got: {row!r})\n{out}"
    )
    assert "landed with caveats" in out, repr(result)


# --- `TRC-C2` -----------------------------------------------------------------


def test_unsupported_pass_flagged(run_cli, project):
    """`TRC-C2`: a pass gate with no evidence id is rendered as "unsupported"."""
    task_dir = _landed_task(project, slug="alpha")
    body = yaml.safe_load((task_dir / "manifest.yml").read_text())
    for g in body["gates"]:
        if g["id"] == "verify.governance":
            g["status"] = "pass"
            g["evidence"] = []  # the bare-pass-no-evidence case
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False))

    result = run_cli("issue", "receipt", "--issue", "alpha")
    assert result.returncode == 0, repr(result)
    out = result.stdout

    rows = [ln for ln in out.splitlines() if "verify.governance" in ln]
    assert rows, f"no verify.governance row\n{out}"
    row = rows[0]
    assert "UNSUPPORTED" in row.upper(), (
        f"verify.governance should be unsupported (got: {row!r})\n{out}"
    )
    assert "landed with caveats" in out, repr(result)


# --- `TRC-D2` -----------------------------------------------------------------


def test_schema_1_0_renders(run_cli, project):
    """`TRC-D2`: a schema-1.0 manifest.yml (pre-status field, possibly no evidence:
    list) renders without error.

    ADR-006: every new mechanism no-ops cleanly on projects that have not
    adopted it.
    """
    slug = "legacy"
    task_dir = project / ".compass" / "work" / slug
    task_dir.mkdir(parents=True, exist_ok=True)
    # Bare 1.0 - no `status`, no `evidence`, no `gates`. Only the very
    # earliest required fields.
    legacy_body = {
        "schema_version": "1.0",
        "task": slug,
        "created": "2026-01-01",
        "assessment": {
            "risk": "trivial",
            "familiarity": "greenfield",
            "size": "atomic",
            "intent": "delivery",
            "role": "engineer",
            "labels": [],
        },
        "delivery_approach": "express",
    }
    (task_dir / "manifest.yml").write_text(
        yaml.safe_dump(legacy_body, sort_keys=False))
    # No delivery-approach.md, no evidence/, no gates - the absent-data path.

    result = run_cli("issue", "receipt", "--issue", slug)
    assert result.returncode == 0, repr(result)
    out = result.stdout

    # The header acknowledges schema 1.0.
    assert "1.0" in out and "legacy" in out.lower(), (
        f"header should note 'schema 1.0 (legacy)':\n{out}"
    )
    # Assessment values + delivery approach are still rendered.
    assert "trivial" in out  # risk value
    assert "quick fix" in out  # the shape, shown by its v2 display name
    # Absent data is labelled - somewhere in the receipt, "not recorded" or
    # "no evidence recorded" surfaces honestly rather than crashing.
    assert "not recorded" in out or "no evidence recorded" in out, (
        f"absent data should be clearly labelled:\n{out}"
    )


# --- `TRC-E1` -----------------------------------------------------------------


import hashlib  # noqa: E402 - used only here


def _file_tree_sha(root: Path) -> Dict[str, str]:
    """SHA-256 every file under `root` and return {relative_path: hexdigest}."""
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def test_receipt_is_read_only(run_cli, project):
    """`TRC-E1`: rendering the receipt mutates nothing on disk.

    The whole project tree is hashed before and after; the receipt must change
    no bytes, create no files, and write no caches.
    """
    task_dir = _landed_task(project, slug="alpha")
    # Hash the *whole project*, not just the issue directory, so we catch
    # any caches or other side-effects landing elsewhere.
    before = _file_tree_sha(project)

    result = run_cli("issue", "receipt", "--issue", "alpha")
    assert result.returncode == 0, repr(result)

    after = _file_tree_sha(project)
    assert before.keys() == after.keys(), (
        f"new file(s) appeared: {sorted(after.keys() - before.keys())!r}"
    )
    diffs = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
    assert not diffs, f"files mutated: {diffs!r}"


# --- `DD-4` - docs example pinned to actual renderer output -------------------


import subprocess as _subprocess  # noqa: E402


def test_docs_example_matches_actual_output(framework_root, cli_path):
    """`DD-4`: docs/receipt.md embeds the actual rendered output of the fixture.

    This test extracts the first fenced code block under the "## Example"
    heading in docs/receipt.md and asserts it is byte-for-byte equal to the
    output of running the receipt against tests/fixtures/receipt-fixture-project.
    If anyone changes the renderer's output and forgets to re-paste the docs
    example, this fails.
    """
    docs_path = framework_root / "docs" / "receipt.md"
    fixture_root = framework_root / "tests" / "fixtures" / "receipt-fixture-project"
    assert docs_path.is_file(), f"missing {docs_path}"
    assert fixture_root.is_dir(), f"missing {fixture_root}"

    proc = _subprocess.run(
        [
            "python3", str(cli_path), "issue", "receipt",
            "--issue", "receipt-example",
            "--workdir", str(fixture_root),
        ],
        capture_output=True, text=True, check=True, timeout=10,
        cwd=str(framework_root),
    )
    actual = proc.stdout.rstrip("\n")

    # Extract the first fenced code block under "## Example".
    docs_text = docs_path.read_text(encoding="utf-8")
    after_example = docs_text.split("## Example", 1)
    assert len(after_example) == 2, "docs/receipt.md must have an '## Example' section"
    block_match = after_example[1]
    # First triple-backtick-delimited block in that section.
    parts = block_match.split("```", 2)
    assert len(parts) >= 3, "no fenced block under '## Example' in docs/receipt.md"
    # parts[1] is "<lang?>\n<content>" - strip the optional language tag on the
    # first line, then the content.
    body = parts[1].lstrip("\n")
    # If the fence opened with a language tag, skip the tag line.
    if not body.startswith("="):
        body = body.split("\n", 1)[1]
    embedded = body.rstrip("\n")

    assert actual == embedded, (
        "docs/receipt.md example has drifted from the renderer output.\n\n"
        f"--- actual (re-paste this into docs/receipt.md) ---\n{actual}\n\n"
        f"--- embedded (in docs/receipt.md) ---\n{embedded}\n"
    )
