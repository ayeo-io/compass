"""Acceptance tests for issue record-keeping-integrity.

Three fixes on one theme: Compass's own record-keeping reporting success while
losing or failing to record information.

  * `declared-tests-resolve` (group A) - a scenario naming a test that does not
    exist must not pass `compass check`. Scoped to issues that are still `active`
    AND have already claimed `verify.correctness: pass`, because TDD writes a
    test id at define before the test exists.
  * friction merge (group B) - `_friction-capture` appends human notes instead
    of overwriting the list.
  * provenance column (group C) - the review-dimensions table records who
    assessed each judgement dimension.

Spec: record-keeping-integrity/acceptance-criteria.md
"""

# These tests read the per-check detail (name, PASS/FAIL, reason) that
# `compass check --verbose` prints.
from __future__ import annotations

import json
import re
import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _read(rel):
    return (ROOT / rel).read_text()


def _flat(text):
    """Collapse whitespace so assertions survive markdown reflowing."""
    return re.sub(r"\s+", " ", text).lower()


# ---------------------------------------------------------------------------
# Group A - declared test ids must resolve
# ---------------------------------------------------------------------------

def _task_claiming_correctness(tests, *, status="active", correctness="pass"):
    """A manifest.yml that has claimed correctness - the state the check fires in."""
    body = {
        "task": "resolve-me",
        "created": "2026-08-03",
        "status": status,
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
            "intent": "delivery",
        },
        "delivery_approach": "express",
        "scenarios": [{"id": "SCN-001", "intent": "INT-1", "tests": tests}],
        "changed_files": [{"path": "src/x.py", "scenarios": ["SCN-001"]}],
        "evidence": [{
            "id": "EV-T-SCN-001", "type": "test-run",
            "path": "evidence/green.json", "scenario": "SCN-001",
        }],
        "gates": [
            {"id": "verify.correctness", "status": correctness,
             "evidence": ["EV-T-SCN-001"] if correctness == "pass" else []},
            {"id": "verify.governance", "status": "pending"},
            {"id": "verify.traceability", "status": "pending"},
        ],
        "follow_ups": [],
    }
    return body


def _green(task_dir):
    ev = task_dir / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "green.json").write_text(json.dumps({
        "exit_code": 0, "passed": True, "scenario": "SCN-001",
        "command": "pytest", "timestamp": "2026-08-03T00:00:00+00:00",
    }))


def _real_test_file(project, name="tests/test_real.py", func="test_present"):
    p = project / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"def {func}():\n    assert True\n")
    # An issue claiming correctness must also have the file it says it
    # changed: `changed-code-traces-to-scenario` checks the path is still on
    # disk, so a fixture that models a correct issue needs its changed file
    # to exist too.
    changed = project / "src" / "x.py"
    changed.parent.mkdir(parents=True, exist_ok=True)
    changed.write_text("x = 1\n")
    return p


def test_trc_a1_missing_test_file_reported(run_cli, make_task, project):
    """A test id pointing at a file that does not exist is a broken chain."""
    task_dir = make_task("resolve-me",
                         _task_claiming_correctness(["tests/test_nothing_here.py::test_x"]))
    _green(task_dir)

    r = run_cli("check", "--verbose", "--issue", "resolve-me")

    assert r.returncode != 0, r
    assert "declared-tests-resolve" in r.stdout, r
    assert "SCN-001" in r.stdout, "the failure must name the scenario"
    assert "test_nothing_here" in r.stdout, "the failure must name the test id"


def test_trc_a2_missing_test_function_reported(run_cli, make_task, project):
    """The file existing is not enough - the named test must be in it. This is
    the case that happened: a test renamed during implement, never written
    back to manifest.yml."""
    _real_test_file(project, func="test_present")
    task_dir = make_task("resolve-me",
                         _task_claiming_correctness(["tests/test_real.py::test_absent"]))
    _green(task_dir)

    r = run_cli("check", "--verbose", "--issue", "resolve-me")

    assert r.returncode != 0, r
    assert "declared-tests-resolve" in r.stdout, r
    assert "test_absent" in r.stdout, r


def test_trc_a3_resolvable_test_id_passes(run_cli, make_task, project):
    _real_test_file(project, func="test_present")
    task_dir = make_task("resolve-me",
                         _task_claiming_correctness(["tests/test_real.py::test_present"]))
    _green(task_dir)

    r = run_cli("check", "--verbose", "--issue", "resolve-me")

    assert r.returncode == 0, r
    assert "declared-tests-resolve" in r.stdout, "the check should report a pass"


def test_trc_a3_parametrised_id_resolves(run_cli, make_task, project):
    """pytest parametrisation is part of the id but not part of the name."""
    _real_test_file(project, func="test_present")
    task_dir = make_task(
        "resolve-me",
        _task_claiming_correctness(["tests/test_real.py::test_present[case-1]"]))
    _green(task_dir)

    assert run_cli("check", "--verbose", "--issue", "resolve-me").returncode == 0


def test_trc_a3_non_file_shaped_id_is_skipped(run_cli, make_task, project):
    """Compass does not own the test-id vocabulary of every runner. A false
    positive on a legitimate id teaches people to switch the check off."""
    task_dir = make_task(
        "resolve-me",
        _task_claiming_correctness(["grep: governance/strategies.md carries S7"]))
    _green(task_dir)

    r = run_cli("check", "--verbose", "--issue", "resolve-me")
    assert r.returncode == 0, r


def test_trc_a4_narrative_scenario_exempt(run_cli, make_task, project):
    """`verifiable: narrative` is the sanctioned way to say a scenario has no
    automated test. The resolution check must respect it."""
    body = _task_claiming_correctness([])
    body["scenarios"][0].pop("tests")
    body["scenarios"][0]["verifiable"] = "narrative"
    task_dir = make_task("resolve-me", body)
    _green(task_dir)
    spec = task_dir / "acceptance-criteria.md"
    spec.write_text(
        "# Spec\n\n### Scenario: a documented playbook\n"
        "<!-- traceability id: SCN-001 -->\n\n"
        "```gherkin\nScenario: a documented playbook\n"
        "  Given a documented procedure\n  When it is followed\n"
        "  Then the outcome is recorded\n```\n")

    r = run_cli("check", "--verbose", "--issue", "resolve-me")

    assert r.returncode == 0, r
    assert "FAIL declared-tests-resolve" not in r.stdout, (
        "a narrative scenario has no test to resolve and must not be reported:\n"
        + r.stdout)


def test_trc_a7_pending_correctness_not_checked(run_cli, make_task, project):
    """Between define and implement the declared test legitimately does not
    exist yet. An active-only rule would fail every issue in that window."""
    task_dir = make_task(
        "resolve-me",
        _task_claiming_correctness(["tests/test_not_written_yet.py::test_x"],
                                   correctness="pending"))
    _green(task_dir)

    r = run_cli("check", "--verbose", "--issue", "resolve-me")
    combined = r.stdout
    assert "test_not_written_yet" not in combined, (
        "the resolution check must not fire before correctness is claimed:\n" + combined)


def test_trc_a8_landed_task_not_rechecked(run_cli, make_task, project):
    """Tests get renamed after an issue lands. Re-checking a historical
    record against a moving codebase produces failures that mean nothing
    (ADR-006)."""
    task_dir = make_task(
        "resolve-me",
        _task_claiming_correctness(["tests/test_long_gone.py::test_x"], status="landed"))
    _green(task_dir)

    r = run_cli("check", "--verbose", "--issue", "resolve-me")
    assert "test_long_gone" not in r.stdout, (
        "a landed task must not be re-checked:\n" + r.stdout)


def test_trc_a5_registered_under_g1_no_new_guardrail():
    """ADR-002: the framework grows by adding artifacts, not rules. The
    check registers under `G1`; the count stays at five."""
    gy = yaml.safe_load(_read("governance/guardrails.yml"))

    defaults = {g["id"]: g for g in gy["defaults"]}
    assert set(defaults) == {"G1", "G2", "G3", "G4", "G5"}, (
        f"guardrail count must stay at five, found {sorted(defaults)}")
    assert "declared-tests-resolve" in defaults["G1"]["checks"], (
        "the resolution check must be declared under G1")


def test_trc_a6_policy_lint_accepts_the_check(run_cli):
    """`compass policy lint` cross-checks that every declared check exists in
    CHECK_FNS. A check declared but not implemented fails here."""
    r = run_cli("policy", "lint")
    assert r.returncode == 0, r


# ---------------------------------------------------------------------------
# Group B - friction is appended, not overwritten
# ---------------------------------------------------------------------------

def _friction_task(slug, make_task, friction=None):
    body = {
        "task": slug, "created": "2026-08-03", "status": "active",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                     "size": "small", "intent": "delivery"},
        "delivery_approach": "express", "scenarios": [], "gates": [], "follow_ups": [],
    }
    if friction is not None:
        body["friction"] = friction
    return make_task(slug, body)


def test_trc_b1_second_note_appends(run_cli, make_task):
    """The defect: `task['friction'] = entries` discarded the first note."""
    task_dir = _friction_task("fric", make_task, friction=[
        {"phase": "verify", "category": "tooling", "source": "human",
         "observation": "the first note"},
    ])

    r = run_cli("_friction-capture", "--internal", "--issue", "fric",
                "--note", "the second note", "--note-category", "tooling",
                "--note-phase", "land")
    assert r.returncode == 0, r

    got = yaml.safe_load((task_dir / "manifest.yml").read_text())["friction"]
    observations = [e["observation"] for e in got]
    assert "the first note" in observations, (
        "the earlier note was destroyed - this is the bug:\n" + str(got))
    assert "the second note" in observations
    assert len(got) == 2, got


def test_trc_b2_derived_entries_not_duplicated(run_cli, make_task):
    """Derived entries are recomputed each run, so a plain append would
    duplicate them (DD-3)."""
    task_dir = _friction_task("fric", make_task, friction=[
        {"phase": "plan", "category": "over-ceremony", "source": "derived",
         "observation": "a derived observation"},
    ])

    run_cli("_friction-capture", "--internal", "--issue", "fric",
            "--note", "a human note", "--note-category", "tooling")

    got = yaml.safe_load((task_dir / "manifest.yml").read_text())["friction"]
    derived = [e for e in got if e.get("observation") == "a derived observation"]
    assert len(derived) <= 1, f"derived entry duplicated: {got}"


def test_trc_b1_identical_note_not_appended_twice(run_cli, make_task):
    task_dir = _friction_task("fric", make_task, friction=[
        {"phase": "verify", "category": "tooling", "source": "human",
         "observation": "same note"},
    ])

    run_cli("_friction-capture", "--internal", "--issue", "fric",
            "--note", "same note", "--note-category", "tooling",
            "--note-phase", "verify")

    got = yaml.safe_load((task_dir / "manifest.yml").read_text())["friction"]
    assert len([e for e in got if e["observation"] == "same note"]) == 1, got


def test_trc_b3_nothing_captured_stays_absent(run_cli, make_task):
    """An issue that hit no friction stays a clean no-op (ADR-006)."""
    task_dir = _friction_task("fric", make_task)

    r = run_cli("_friction-capture", "--internal", "--issue", "fric")

    assert r.returncode == 0, r
    body = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert "friction" not in body or not body["friction"], body
    assert "nothing recorded" in r.stdout.lower(), r


def test_trc_f2_task_without_friction_key_loads(run_cli, make_task):
    """A manifest written before the friction key existed must still accept a note."""
    task_dir = _friction_task("fric", make_task)   # no friction key at all

    r = run_cli("_friction-capture", "--internal", "--issue", "fric",
                "--note", "a note", "--note-category", "tooling")

    assert r.returncode == 0, r
    got = yaml.safe_load((task_dir / "manifest.yml").read_text())["friction"]
    assert [e["observation"] for e in got] == ["a note"], got


# ---------------------------------------------------------------------------
# Group C - who assessed the judgement
# ---------------------------------------------------------------------------

def test_trc_c1_review_table_has_assessor_column():
    tpl = _read("templates/verification-report.md")

    m = re.search(r"^\|\s*Dimension\s*\|.*$", tpl, re.M)
    assert m, "review-dimensions table header not found"
    header = m.group(0).lower()
    assert "assessed by" in header, (
        f"no column recording who assessed the dimension:\n{m.group(0)}")


def test_trc_c2_template_explains_assessor_column():
    tpl = _read("templates/verification-report.md")
    i = tpl.find("## 3. Review dimensions")
    assert i >= 0
    flat = _flat(tpl[i:i + 2000])

    assert "reviewer" in flat, "guidance does not mention the reviewer agent"
    assert "author" in flat, "guidance does not mention the author case"
    assert re.search(r"weaker|less independent|not independent", flat), (
        "guidance does not say an author-assessed dimension is weaker evidence")


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------

def _pre_existing_task_slugs():
    """Every issue on disk except the active one.

    The active issue is excluded deliberately. An issue mid-implement has
    not recorded its green run yet, so checking it would assert that
    unfinished work is finished - and running the whole of `compass ci`
    here would make this test fail for the duration of every future issue,
    which is a test that reports on the calendar rather than on the change.
    """
    work = ROOT / ".compass" / "work"
    if not work.is_dir():
        return []
    current = (ROOT / ".compass" / "current-task")
    in_flight = current.read_text().strip() if current.is_file() else ""
    # Same principle for issues the manifest says have not started or will not
    # finish: 'queued', 'parked', and 'abandoned' work has no green run by
    # definition, so sweeping it would assert unstarted work is finished.
    import yaml as _yaml
    not_startable = {"queued", "parked", "abandoned"}
    slugs = []
    for p in sorted(work.glob("*/manifest.yml")):
        if p.parent.name == in_flight:
            continue
        try:
            status = (_yaml.safe_load(p.read_text()) or {}).get("status", "active")
        except Exception:
            status = "active"
        if status in not_startable:
            continue
        slugs.append(p.parent.name)
    return slugs


# One test per issue, so parallel workers share the sweep. An empty list (no
# local archive) makes pytest skip the test, as the loop used to return early.
@pytest.mark.parametrize("slug", _pre_existing_task_slugs())
def test_trc_f1_existing_tasks_still_pass(slug):
    """Every issue that predates this change still passes, once the references
    `declared-tests-resolve` exposed have been repaired. Run against the real
    .compass/work/, not a fixture - the point is the actual audit trail."""
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "compass"), "check", "--verbose", "--issue", slug],
        capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    assert r.returncode == 0, (
        f"adding declared-tests-resolve broke {slug}, already on disk:\n"
        f"{r.stdout[-1500:]}")
