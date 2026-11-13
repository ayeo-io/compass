"""An issue must be able to say it stopped.

Real work gets parked - deprioritised, blocked on a decision, superseded by a
change of direction. Without a `parked` status, `compass flow` reported parked
work as in progress, indistinguishable from an issue genuinely under way.

With no `compass issue status set`, every status change - including each
new value here - was a hand-edited `str.replace` on the manifest.

Scenarios: status-vocabulary/acceptance-criteria.md (SCN-A1..F2).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
SCHEMA = ROOT / "schemas" / "manifest.schema.json"

NEW_STATUSES = ["queued", "parked", "abandoned"]


def _task(status=None, *, gates_pass=True, extra=None):
    t = {
        "schema_version": "1.1", "task": "t", "created": "2026-08-06",
        "assessment": {"risk": "contained", "familiarity": "greenfield",
                     "size": "small", "intent": "delivery",
                     "urgency": "none", "role": "engineer", "labels": []},
        "delivery_approach": "standard", "topology": "solo", "policy_rules_fired": [],
        "stages": {}, "evidence": [],
        "gates": [{"id": "verify.correctness",
                   "status": "pass" if gates_pass else "pending",
                   "evidence": []}],
        "scenarios": [], "changed_files": [], "claims": [], "follow_ups": [],
        "reassessments": [], "friction": [],
    }
    if status:
        t["status"] = status
    t.update(extra or {})
    return t


def _project(tmp_path, tasks):
    """tasks: {slug: issue-dict}"""
    root = tmp_path / "proj"
    shutil.copytree(ROOT / "governance", root / "governance")
    (root / ".compass").mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    for slug, body in tasks.items():
        d = root / ".compass" / "work" / slug
        d.mkdir(parents=True)
        (d / "delivery-approach.md").write_text("# Route\n")
        (d / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False))
    (root / ".compass" / "current-task").write_text(next(iter(tasks)) + "\n")
    return root


def _run(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=str(root),
                          capture_output=True, text=True, timeout=60)


# ---------------------------------------------------------------------------
# Group A - the vocabulary
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", NEW_STATUSES)
def test_scn_a1_new_statuses_validate(tmp_path, status):
    root = _project(tmp_path, {"t": _task(status)})
    r = _run(root, "issue", "lint", "--issue", "t")
    assert r.returncode == 0, f"status {status!r} rejected:\n{r.stdout}{r.stderr}"


def test_scn_a2_unknown_status_rejected(tmp_path):
    root = _project(tmp_path, {"t": _task("in-flight")})
    r = _run(root, "issue", "lint", "--issue", "t")
    assert r.returncode != 0, "an invented status was accepted"
    assert "backlog" in (r.stdout + r.stderr), (
        "the failure should name the permitted values")


def test_scn_a3_parked_reason_and_at_validate(tmp_path):
    root = _project(tmp_path, {"t": _task("parked", extra={
        "parked_reason": "blocked on a pricing decision",
        "parked_at": "2026-08-06T10:00:00Z"})})
    r = _run(root, "issue", "lint", "--issue", "t")
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"


# ---------------------------------------------------------------------------
# Group B - the mutator
# ---------------------------------------------------------------------------

def test_scn_b1_set_status_writes_the_field(tmp_path):
    root = _project(tmp_path, {"t": _task()})
    r = _run(root, "issue", "status", "set", "backlog", "--issue", "t",
             "--reason", "blocked on a pricing decision")
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"
    body = yaml.safe_load((root / ".compass" / "work" / "t" / "manifest.yml").read_text())
    assert body["status"] == "backlog", body   # the old word parked is a backlog hold
    assert body.get("parked_reason") == "blocked on a pricing decision", body
    assert body.get("parked_at"), "a parked task should record when"
    assert _run(root, "issue", "lint", "--issue", "t").returncode == 0


def test_scn_b2_set_status_refuses_unknown(tmp_path):
    root = _project(tmp_path, {"t": _task()})
    r = _run(root, "issue", "status", "set", "finished", "--issue", "t")
    assert r.returncode != 0, "an invented status was written"
    assert "backlog" in (r.stdout + r.stderr)


def test_scn_b3_set_status_landed_respects_gates(tmp_path):
    """`compass ship-commit` refuses to mark landed over unpassed gates. A
    second door into the same field must not be an easier one."""
    root = _project(tmp_path, {"t": _task(gates_pass=False)})
    r = _run(root, "issue", "status", "set", "done", "--close-reason", "completed",
             "--issue", "t")
    body = yaml.safe_load((root / ".compass" / "work" / "t" / "manifest.yml").read_text())
    assert body.get("status") not in ("landed", "done"), (
        f"marked landed over a pending gate:\n{r.stdout}{r.stderr}")
    assert "verify.correctness" in (r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# Group C - the readers
# ---------------------------------------------------------------------------

def test_scn_c1_flow_separates_parked(tmp_path):
    root = _project(tmp_path, {"live": _task("active"), "stopped": _task("parked")})
    r = _run(root, "flow")
    out = r.stdout
    # A parked issue is a backlog hold now: it is reported under the backlog
    # heading, apart from the issue under way.
    i_parked, i_live = out.lower().find("stopped"), out.lower().find("live")
    assert i_parked != -1 and i_live != -1, out
    assert "backlog" in out.lower().split("stopped")[0][-400:], (
        f"the held task must be reported under its own heading:\n{out}")


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------

def test_scn_f1_absent_status_is_active(tmp_path):
    """Every manifest.yml written before the status field existed omits it
    entirely."""
    root = _project(tmp_path, {"t": _task()})
    assert _run(root, "issue", "lint", "--issue", "t").returncode == 0
    r = _run(root, "flow")
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"
    assert "t" in r.stdout, f"a status-less task vanished from flow:\n{r.stdout}"


def test_scn_f2_landed_is_the_only_privileged_value(tmp_path):
    """The schema is the vocabulary's source of truth, and `done` with close
    reason `completed` is the only state that grants eligibility anywhere.
    Asserted behaviourally: an issue holding a stored status with no close
    reason must be treated as not completed, so a value added later cannot
    silently get that privilege."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enum = schema["properties"]["status"]["enum"]
    assert set(enum) == {"backlog", "done"}, enum

    sys.path.insert(0, str(ROOT / "cli"))
    # `compass release notes` lists only what this reader returns.
    from compass_pkg.shipped_issues import completed_issues
    scenarios = [{"id": "SCN-PRIV", "title": "s", "intent": "INT-1",
                  "tests": ["tests/test_x.py"]}]
    for status in [s for s in enum if s != "landed"]:
        root = _project(tmp_path / status,
                        {"t": _task(status, extra={"scenarios": scenarios})})
        assert completed_issues(str(root)) == [], (
            f"status {status!r} was treated as completed")
