"""`compass issue lint` against malformed manifest.yml files, plus schema_version
compatibility checks."""
from __future__ import annotations


def _valid_task_body(**overrides):
    body = {
        "task": "ok",
        "created": "2026-05-15",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
            "goal": "delivery",
        },
    }
    body.update(overrides)
    return body


def test_task_lint_passes_on_valid_task(run_cli, make_task):
    make_task("good", _valid_task_body())
    r = run_cli("issue", "lint", "--issue", "good")
    assert r.returncode == 0, r
    assert "PASS" in r.stdout


def test_task_lint_fails_on_missing_readings(run_cli, make_task):
    """A manifest.yml without an assessment is not a Compass issue."""
    body = _valid_task_body()
    body.pop("assessment")
    make_task("no-readings", body)
    r = run_cli("issue", "lint", "--issue", "no-readings")
    assert r.returncode != 0, r
    assert "FAIL" in r.stdout, r
    assert "assessment" in (r.stdout + r.stderr), r


def test_task_lint_fails_on_missing_required_reading_dimension(run_cli, make_task):
    """risk/familiarity/size are required."""
    body = _valid_task_body()
    body["assessment"].pop("size")
    make_task("missing-magnitude", body)
    r = run_cli("issue", "lint", "--issue", "missing-magnitude")
    assert r.returncode != 0, r
    assert "magnitude" in (r.stdout + r.stderr).lower(), r


def test_task_lint_fails_on_bad_enum_value(run_cli, make_task):
    """A reading outside the vocabulary fails JSON Schema validation."""
    body = _valid_task_body()
    body["assessment"]["risk"] = "asteroid"   # not in the enum
    make_task("bad-enum", body)
    r = run_cli("issue", "lint", "--issue", "bad-enum")
    assert r.returncode != 0, r
    combined = (r.stdout + r.stderr).lower()
    assert "asteroid" in combined or "enum" in combined or "blast_radius" in combined, r


def test_task_lint_fails_on_scenario_without_id(run_cli, make_task):
    body = _valid_task_body(scenarios=[{"goal": "INT-1",
                                        "tests": ["tests/x.py::y"]}])
    make_task("scn-no-id", body)
    r = run_cli("issue", "lint", "--issue", "scn-no-id")
    assert r.returncode != 0, r


def test_task_lint_fails_on_changed_file_without_path(run_cli, make_task):
    body = _valid_task_body(changed_files=[{"scenarios": ["SCN-001"]}])
    make_task("cf-no-path", body)
    r = run_cli("issue", "lint", "--issue", "cf-no-path")
    assert r.returncode != 0, r


# --- schema_version compatibility ------------------------------------------


def test_task_lint_passes_with_schema_version_1_0(run_cli, make_task):
    """schema_version=1.0 is the current major; passes."""
    body = _valid_task_body()
    body["schema_version"] = "1.0"
    make_task("sv-1-0", body)
    r = run_cli("issue", "lint", "--issue", "sv-1-0")
    assert r.returncode == 0, r


def test_task_lint_passes_with_absent_schema_version(run_cli, make_task):
    """An absent schema_version is allowed for back-compat in 1.0."""
    body = _valid_task_body()
    body.pop("schema_version", None)
    make_task("sv-absent", body)
    r = run_cli("issue", "lint", "--issue", "sv-absent")
    assert r.returncode == 0, r


def test_task_lint_accepts_schema_version_3_0(run_cli, make_task):
    """3.0 is the schema this CLI writes: it stores only a backlog hold or
    done with a close reason."""
    body = _valid_task_body()
    body["schema_version"] = "3.0"
    make_task("sv-3-0", body)
    r = run_cli("issue", "lint", "--issue", "sv-3-0")
    assert r.returncode == 0, r


def test_task_lint_rejects_schema_version_4_0(run_cli, make_task):
    """A future major version must NOT be silently accepted - the same rule
    that once rejected 2.0 on a 1.x CLI now rejects 4.0 on the 3.0 CLI
    (which reads 1.x by key normalisation)."""
    body = _valid_task_body()
    body["schema_version"] = "4.0"
    make_task("sv-4-0", body)
    r = run_cli("issue", "lint", "--issue", "sv-4-0")
    assert r.returncode != 0, r
    combined = (r.stdout + r.stderr).lower()
    assert "schema_version" in combined or "4.0" in combined, r


def test_task_lint_with_explicit_file_path(run_cli, make_task, project):
    """`compass issue lint --file <path>` lints a specific file."""
    body = _valid_task_body()
    body["assessment"].pop("risk")
    make_task("via-file", body)
    path = project / ".compass" / "work" / "via-file" / "manifest.yml"
    r = run_cli("issue", "lint", "--file", str(path))
    assert r.returncode != 0, r


# --- friction (the self-calibration signal) --------------------------------
# The optional `friction:` block on the issue manifest (`TRC-A1`, `TRC-F3`).


def test_friction_block_validates(run_cli, make_task):
    """An optional friction list with the documented fields passes validation,
    and category and source are constrained to their enums (`TRC-A1`)."""
    body = _valid_task_body(friction=[
        {
            "phase": "plan",
            "category": "over-ceremony",
            "observation": "Standard route's full Clarify added a gate the change didn't need.",
            "proposed_change": "routing-policy.yml: lower Clarify weight for size=small.",
            "source": "derived",
        },
        {
            "category": "tooling",
            "observation": "had to hand-edit the marker",
            "source": "human",
        },
    ])
    make_task("friction-ok", body)
    r = run_cli("issue", "lint", "--issue", "friction-ok")
    assert r.returncode == 0, r
    assert "PASS" in r.stdout, r


def test_friction_bad_category_rejected(run_cli, make_task):
    """A category outside the documented set fails validation (`TRC-A1`)."""
    body = _valid_task_body(friction=[
        {"category": "vibes", "observation": "x", "source": "derived"},
    ])
    make_task("friction-bad-cat", body)
    r = run_cli("issue", "lint", "--issue", "friction-bad-cat")
    assert r.returncode != 0, r
    combined = (r.stdout + r.stderr).lower()
    assert "vibes" in combined or "category" in combined or "enum" in combined, r


def test_friction_bad_source_rejected(run_cli, make_task):
    """Source is constrained to derived | human (`TRC-A1`)."""
    body = _valid_task_body(friction=[
        {"category": "tooling", "observation": "x", "source": "guessed"},
    ])
    make_task("friction-bad-src", body)
    r = run_cli("issue", "lint", "--issue", "friction-bad-src")
    assert r.returncode != 0, r
    combined = (r.stdout + r.stderr).lower()
    assert "guessed" in combined or "source" in combined or "enum" in combined, r


def test_friction_absent_is_valid(run_cli, make_task):
    """A 1.x manifest.yml with no friction key stays valid, per ADR-006's no-op rule (`TRC-F3`)."""
    body = _valid_task_body()
    body.pop("friction", None)
    make_task("friction-absent", body)
    r = run_cli("issue", "lint", "--issue", "friction-absent")
    assert r.returncode == 0, r
    assert "PASS" in r.stdout, r
