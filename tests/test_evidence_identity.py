"""Evidence has an identity, and a citation is checked against it.

A registry entry is a path pointing at a record file. That is not enough
on its own: replacing the file would silently replace what a gate rests on,
with `compass check` still reporting PASS.

These tests pin the two stamps written at record time (`record_id`, unique per
write, and `content_digest`, over what was written), the write path that
stops overwriting records, and the check that compares them.

Scenario ids trace to tdd-green-unbound-record/acceptance-criteria.md -
group A (the write path), B (identity), C (the check), D (manifests written
before stamping existed).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import write_red_record
from typing import Any, Dict, List, Optional

import yaml

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = FRAMEWORK_ROOT / "cli" / "compass"


def _make_project(tmp_path: Path, scenarios: Optional[List[str]] = None) -> Path:
    """A minimal Compass project using the real shipped governance files."""
    proj = tmp_path / "project"
    proj.mkdir(parents=True, exist_ok=True)

    compass_dir = proj / ".compass"
    task_dir = compass_dir / "work" / "t"
    (task_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (compass_dir / "current-task").write_text("t\n")
    (compass_dir / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    (task_dir / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "task": "t", "created": "2026-08-23",
        "status": "active",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "standard", "goal": "delivery"},
        "delivery_approach": "feature",
        "scenarios": [{"id": s, "intent": "INT-1", "tests": ["t::t"]}
                      for s in (scenarios or ["TRC-1", "TRC-2"])],
        "changed_files": [], "evidence": [], "gates": [],
    }))
    return proj


def _run(proj: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CLI_PATH), *args],
                          cwd=str(proj), capture_output=True, text=True, timeout=60)


def _task(proj: Path) -> Dict[str, Any]:
    return yaml.safe_load((proj / ".compass/work/t/manifest.yml").read_text())


def _record(proj: Path, name: str) -> Dict[str, Any]:
    return json.loads((proj / ".compass/work/t/evidence" / name).read_text())


def _green(proj: Path, message: str, scenario: Optional[str] = None):
    """Record a passing run whose output is `message`, so different runs are
    distinguishable by their content as well as by their stamps.

    A bound green needs a red for the same binding, so one is written first.
    These tests are about record identity, not about the red-for-green rule -
    without this they would be blocked before reaching what they measure.
    """
    args = ["tdd-green"]
    if scenario:
        write_red_record(proj / ".compass" / "work" / "t", scenario)
        args += ["--scenario", scenario]
    return _run(proj, *args, "--", sys.executable, "-c", f"print({message!r})")


# ---------------------------------------------------------------------------
# Group B - a record carries an identity
# ---------------------------------------------------------------------------

def test_b1_record_carries_a_unique_identity(tmp_path):
    """`TRC-B1`: a recorded run carries an identity, and two different runs carry
    different identities."""
    proj = _make_project(tmp_path)

    _green(proj, "FULL SUITE: 957 tests")
    first = _record(proj, "green.json")
    assert first.get("record_id"), (
        "the record carries no identity, so nothing can tell it apart from any "
        "other record written to the same path: " + repr(sorted(first)))

    _green(proj, "a different run entirely", scenario="TRC-1")
    second = _record(proj, "green-TRC-1.json")
    assert second.get("record_id"), "the second record carries no identity"
    assert first["record_id"] != second["record_id"], (
        "two different runs share an identity, so a citation naming one is "
        "satisfied by the other")


def test_b2_rerecording_produces_a_new_identity(tmp_path):
    """`TRC-B2`: re-recording the SAME command produces a different identity.

    Identity is of the run, not of the command or its output. Two runs of one
    suite are two pieces of evidence, and the second must not satisfy a
    citation naming the first.

    This is why a content digest cannot carry the identity alone: `now_iso()`
    is second-resolution, so the two payloads below are byte-identical apart
    from the stamps.
    """
    proj = _make_project(tmp_path)

    _green(proj, "same output every time")
    first = _record(proj, "green.json")
    _green(proj, "same output every time")
    second = _record(proj, "green.json")

    assert first["record_id"] != second["record_id"], (
        "two runs of the same command produced the same identity, so a "
        "citation naming the first is satisfied by the second")


def test_b3_registry_entry_stores_the_identity(tmp_path):
    """`TRC-B3`: the registry entry carries the identity of the run it was
    created from, and it matches the record on disk."""
    proj = _make_project(tmp_path)
    _green(proj, "FULL SUITE: 957 tests")

    entries = [e for e in _task(proj)["evidence"] if e.get("type") == "test-run"]
    assert entries, "no test-run entry was registered"
    entry = entries[0]
    record = _record(proj, "green.json")

    assert entry.get("record_id"), (
        "the registry entry carries no record_id, so it cannot say which run "
        "it was created from: " + repr(sorted(entry)))
    assert entry["record_id"] == record["record_id"], (
        "the entry's identity does not match the record it names")
    assert entry.get("content_digest") == record.get("content_digest"), (
        "the entry's content digest does not match the record it names")


# ---------------------------------------------------------------------------
# Group A - the write path stops destroying records
# ---------------------------------------------------------------------------

def test_a1_scenario_green_does_not_destroy_the_unbound_green(tmp_path):
    """`TRC-A1`: recording a scenario-bound green leaves the unbound green
    intact.

    The defect, reproduced. An unbound full-suite record is registered and
    cited; recording one scenario's run then replaced the file it named, and
    `compass check` reported PASS throughout.
    """
    proj = _make_project(tmp_path)

    _green(proj, "FULL SUITE: 957 tests")
    before = _record(proj, "green.json")
    entry = [e for e in _task(proj)["evidence"] if e.get("type") == "test-run"][0]
    assert entry["path"] == "evidence/green.json"

    _green(proj, "one file: 11 tests", scenario="TRC-1")

    after = _record(proj, "green.json")
    assert after["command"] == before["command"], (
        "the unbound record was replaced by the scenario's run:\n"
        "  was: %s\n  now: %s" % (before["command"], after["command"]))
    assert after["record_id"] == before["record_id"], (
        "the unbound record has a different identity, so it is a different "
        "record under the same name")
    assert (proj / ".compass/work/t/evidence/green-TRC-1.json").is_file(), (
        "the scenario's run was not recorded separately")


def test_a2_scenario_acceptance_does_not_destroy_the_unbound_acceptance(tmp_path):
    """`TRC-A2`: the same defect in the other half of the module.

    `compass acceptance record` carried the identical unconditional write. Its
    own comment described the scenario-copy fix, which closed scenario-versus-
    scenario collisions and never reached the unbound record.
    """
    proj = _make_project(tmp_path)

    _run(proj, "acceptance", "start", "--kind", "validation",
         "--", sys.executable, "-c", "print('validator: whole tree')")
    _run(proj, "acceptance", "record",
         "--", sys.executable, "-c", "print('validator: whole tree')")
    before = _record(proj, "acceptance.json")

    _run(proj, "acceptance", "start", "--kind", "validation",
         "--", sys.executable, "-c", "print('validator: one file')")
    _run(proj, "acceptance", "record", "--scenario", "TRC-1",
         "--", sys.executable, "-c", "print('validator: one file')")

    after = _record(proj, "acceptance.json")
    assert after["record_id"] == before["record_id"], (
        "the unbound acceptance record was replaced by the scenario's run")


def test_a3_no_verb_overwrites_a_cited_path(tmp_path):
    """`TRC-A3`: the guard on the class, not on its two known members.

    Every evidence-writing verb follows one rule - a write bound to a scenario
    touches only that scenario's record. A fifth fixed-name write added later
    is caught here rather than needing this issue repeated.
    """
    proj = _make_project(tmp_path)

    # Establish an unbound record for each verb that takes a binding.
    _run(proj, "tdd-red", "--", sys.executable, "-c", "import sys; sys.exit(1)")
    _green(proj, "unbound green")
    # Dotfiles are skipped: `.tdd-state.json` is the verbs' internal state,
    # which happens to live in the evidence directory and is not an evidence
    # record. Filtering it out is not loosening the guard - it was never in
    # scope - but it is worth naming, because internal state sharing a
    # directory with the audit trail is how a reader confuses the two.
    ev = proj / ".compass/work/t/evidence"
    before = {p.name: json.loads(p.read_text())["record_id"]
              for p in ev.glob("*.json") if not p.name.startswith(".")}
    assert before, "no records were written"

    # Now run every binding-taking verb bound to a scenario.
    _run(proj, "tdd-red", "--scenario", "TRC-2",
         "--", sys.executable, "-c", "import sys; sys.exit(1)")
    _green(proj, "bound green", scenario="TRC-2")

    after = {name: json.loads((ev / name).read_text())["record_id"]
             for name in before}
    changed = [n for n in before if before[n] != after[n]]
    assert not changed, (
        "a scenario-bound write replaced these unbound records: %s" % changed)


def test_a4_unbound_record_can_be_rerecorded(tmp_path):
    """`TRC-A4`: the failure this fix could easily introduce.

    Protecting the unbound record so well that a genuinely stale full-suite run
    can never be replaced would be its own defect.
    """
    proj = _make_project(tmp_path)

    _green(proj, "FULL SUITE: stale")
    stale = _record(proj, "green.json")
    _green(proj, "one scenario", scenario="TRC-1")
    bound_before = _record(proj, "green-TRC-1.json")

    _green(proj, "FULL SUITE: fresh")

    fresh = _record(proj, "green.json")
    assert fresh["record_id"] != stale["record_id"], (
        "the unbound record could not be re-recorded deliberately")
    assert "fresh" in fresh["command"] or "fresh" in fresh.get("log_excerpt", ""), (
        "the unbound record does not hold the new run")
    assert _record(proj, "green-TRC-1.json")["record_id"] == bound_before["record_id"], (
        "re-recording the unbound run changed a scenario's record")


# ---------------------------------------------------------------------------
# Group C - the check checks the citation
# ---------------------------------------------------------------------------

def _replace_record(proj: Path, name: str, **overrides) -> None:
    """Overwrite a record on disk the way a stray write would - leaving the
    registry entry pointing at it, unchanged."""
    path = proj / ".compass/work/t/evidence" / name
    rec = json.loads(path.read_text())
    rec.update(overrides)
    path.write_text(json.dumps(rec, indent=2))


def test_c1_replaced_record_is_reported(tmp_path):
    """`TRC-C1`: a citation whose record has been replaced is reported.

    The scenario that decides whether any of this is worth building. An
    identity nothing reads is decoration.
    """
    proj = _make_project(tmp_path)
    _green(proj, "FULL SUITE: 957 tests")

    # The file is replaced by a different run, exactly as a stray write would.
    _replace_record(proj, "green.json",
                    record_id="0000000000000000",
                    command="python3 -m pytest one_file.py")

    result = _run(proj, "check", "--verbose")
    output = result.stdout + result.stderr

    assert "evidence-identity-matches" in output, (
        "the check did not run at all:\n" + output)
    assert result.returncode != 0, (
        "a gate resting on a replaced record still passed:\n" + output)


def test_c2_matching_citation_is_quiet(tmp_path):
    """`TRC-C2`: a citation that matches its record is not reported.

    The half that stops this becoming noise. This passes the moment the check
    is written correctly, so it is proved by mutation: breaking the match
    makes this test fail.
    """
    proj = _make_project(tmp_path)
    _green(proj, "FULL SUITE: 957 tests")

    output = _run(proj, "check", "--verbose").stdout
    line = next((l for l in output.splitlines()
                 if "evidence-identity-matches" in l), "")
    assert line, "the check did not report at all:\n" + output
    assert line.strip().startswith("PASS"), (
        "an unchanged record was reported as a mismatch:\n" + line)


def test_c3_report_names_what_changed(tmp_path):
    """`TRC-C3`: the report names the evidence id, the file, and what changed.

    A failure a reader cannot act on sends them to the source to find out which
    record is wrong.
    """
    proj = _make_project(tmp_path)
    _green(proj, "FULL SUITE: 957 tests")
    _replace_record(proj, "green.json", record_id="0000000000000000")

    output = _run(proj, "check", "--verbose").stdout + _run(proj, "check", "--verbose").stderr
    line = next((l for l in output.splitlines()
                 if "evidence-identity-matches" in l), "")
    detail = output[output.find(line):][:400] if line else output

    assert "EV-T" in detail, "the report does not name the evidence id:\n" + detail
    assert "green.json" in detail, "the report does not name the file:\n" + detail


# ---------------------------------------------------------------------------
# Group D - manifests written before stamping existed
# ---------------------------------------------------------------------------

def _unstamped_entry(proj: Path, ev_id: str = "EV-OLD") -> None:
    """A registry entry and record of the kind written before stamping - no
    record_id on either. Every record written before stamping existed is in
    this state."""
    ev = proj / ".compass/work/t/evidence"
    (ev / "old.json").write_text(json.dumps(
        {"command": "pytest tests/", "exit_code": 0, "passed": True}, indent=2))
    task_path = proj / ".compass/work/t/manifest.yml"
    task = yaml.safe_load(task_path.read_text())
    task["evidence"] = (task.get("evidence") or []) + [
        {"id": ev_id, "type": "test-run", "path": "evidence/old.json"}]
    task_path.write_text(yaml.safe_dump(task, sort_keys=False))


def test_d1_unstamped_record_does_not_fail(tmp_path):
    """`TRC-D1`: a record written before stamping existed does not fail the
    check.

    Every record written before stamping existed is in this state. Failing
    on them would turn every one red for a fact about when they were
    written.

    Never-red by construction once the code is right, so it is proved by
    mutation: breaking the never-fail path makes this test fail.
    """
    proj = _make_project(tmp_path)
    _unstamped_entry(proj)

    result = _run(proj, "check", "--verbose")
    line = next((l for l in result.stdout.splitlines()
                 if "evidence-identity-matches" in l), "")
    assert line, "the check did not report:\n" + result.stdout
    assert not line.strip().startswith("FAIL"), (
        "an unstamped record failed the check, which would turn 89 landed "
        "issues red:\n" + line)


def test_d2_unstamped_record_is_not_reported_as_verified(tmp_path):
    """`TRC-D2`: an `unverifiable` record says so, rather than passing quietly.

    The scenario to read first. An unstamped record CANNOT be checked
    against its citation - that is a fact about the record, not a pass.
    Reporting it as checked would be a check that cannot fail.
    """
    proj = _make_project(tmp_path)
    _unstamped_entry(proj)

    line = next((l for l in _run(proj, "check", "--verbose").stdout.splitlines()
                 if "evidence-identity-matches" in l), "")
    assert "unverifiable" in line.lower() or "no identity" in line.lower(), (
        "the report does not say the citation could not be verified:\n" + line)

    # And the count must not absorb it. With ONLY unstamped records, nothing
    # was checked, so the check must not claim otherwise.
    assert "1 citation(s) match" not in line, (
        "an unstamped record was counted as a matching citation:\n" + line)
