"""`compass ship-commit` refuses an issue whose documents are not approved (issue
`artifact-status-written-by-stages`, ASW-4 and ASW-16 to ASW-21).

The refusal is the blocking check `artifacts-approved`. `compass quick-fix
finish` approves a quick fix's document itself, and a regular issue run with the
stage commands alone ends with every document approved.

Scenario ids: `ASW-4`, `ASW-16` to `ASW-21`. Each test name starts with its id.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))

from artifact_status_support import (DOCS, HUMAN_DESIGN, SLUG, add_entry,  # noqa: E402
                                     add_evidence, entries, git, manifest, project,
                                     register, run, write_manifest)
import test_quick_fix_verbs as qf  # noqa: E402

BY_SET = "compass issue artifact set"
REGULAR = ("acceptance-criteria", "technical-design", "distribution-map",
           "verification-report")


def _ready(root):
    """Every gate passed, one changed file traced and a green on record,
    that file staged: the state in which `ship-commit` would land."""
    body = manifest(root)
    for gate in body["gates"]:
        gate["status"] = "pass"
    body["changed_files"] = [{"path": "src/new.py", "scenarios": ["S-1"]}]
    write_manifest(root, body)
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "new.py").write_text("y = 1\n")
    code, out, err = run(root, "tdd-green", "--issue", SLUG, "--", sys.executable, "-c", "pass")
    assert code == 0, out + err
    git(root, "add", "src/new.py")


def _approved(root):
    for kind in REGULAR:
        assert register(root, kind, "approved")[0] == 0, kind


def _ship(root):
    return run(root, "ship-commit", "--issue", SLUG, "-m", "Land it")


def _untouched(root, head):
    assert git(root, "rev-parse", "HEAD") == head
    assert "land_commit" not in manifest(root)


# --- ASW-4 ---------------------------------------------------------------------

def test_asw_4_ship_commit_approves_ship_stage_document(tmp_path):
    layer = {"schema": 1, "owner": "jed72", "artifacts": {
        "release-notes": {"file": "release-notes.md", "stage": "ship"}}}
    root = project(tmp_path, compass_yml=layer)
    (root / DOCS / "release-notes.md").write_text("# notes\n")
    _approved(root)
    add_entry(root, "release-notes")
    assert entries(root)["release-notes"]["status"] == "draft"
    _ready(root)
    code, out, err = _ship(root)
    assert code == 0, out + err
    found = entries(root)["release-notes"]
    assert (found["status"], found["approved_by"]) == ("approved", "compass ship-commit")
    assert "land_commit" in manifest(root)


# --- ASW-16 --------------------------------------------------------------------

def test_asw_16_ship_commit_refuses_draft_design(tmp_path):
    root = project(tmp_path)
    _approved(root)
    (root / DOCS / "technical-design.md").write_text("# technical-design\n\nRewritten.\n")
    assert register(root, "technical-design")[0] == 0
    assert entries(root)["technical-design"]["status"] == "draft"
    _ready(root)
    head = git(root, "rev-parse", "HEAD")
    code, out, err = _ship(root)
    assert code == 2, out + err
    text = out + err
    assert "artifacts-approved" in text and "technical-design" in text
    assert "compass issue artifact set technical-design --status approved" in text
    _untouched(root, head)

    # An approved issue waiver turns the refusal into one advisory line.
    body = manifest(root)
    body["config"] = {"checks": {"artifacts-approved": {
        "set": {"severity": "advisory"},
        "waiver": {"reason": "A one-line fix.", "approved_by": "EV-W"}}}}
    body["evidence"].append({
        "id": "EV-W", "type": "human-approval", "decision": "approved", "approver": "jed72",
        "role": "owner", "scope": "waiver", "timestamp": "2026-10-10T09:00:00Z",
        "waiver": {"scope": "issue", "entry": "checks.artifacts-approved",
                   "fields": {"severity": {"from": "blocking", "to": "advisory"}}}})
    write_manifest(root, body)
    code, out, err = run(root, "approach", "evaluate", "--issue", SLUG, "--write",
                         "--reason", "waive the check")
    assert code == 0, out + err
    code, out, err = _ship(root)
    assert code == 0, out + err
    assert "artifacts-approved" in out + err
    assert "land_commit" in manifest(root)


# --- ASW-17 --------------------------------------------------------------------

def test_asw_17_ship_commit_refuses_awaiting_approval(tmp_path):
    root = project(tmp_path, compass_yml=HUMAN_DESIGN)
    for kind in ("acceptance-criteria", "distribution-map", "verification-report"):
        assert register(root, kind, "approved")[0] == 0
    assert register(root, "technical-design", "awaiting-approval")[0] == 0
    _ready(root)
    head = git(root, "rev-parse", "HEAD")
    code, out, err = _ship(root)
    assert code == 2, out + err
    assert "artifacts-approved" in out + err
    assert "compass evidence approve --artifact technical-design" in out + err
    _untouched(root, head)


# --- ASW-18, ASW-19 ------------------------------------------------------------

def test_asw_18_omitted_with_reason_passes_ship_commit(tmp_path):
    root = project(tmp_path)
    for kind in ("acceptance-criteria", "technical-design", "verification-report"):
        assert register(root, kind, "approved")[0] == 0
    code, out, err = run(root, "issue", "artifact", "set", "distribution-map", "--status",
                         "omitted", "--reason", "single subtask, no parallel work",
                         "--issue", SLUG)
    assert code == 0, out + err
    _ready(root)
    code, out, err = run(root, "check", "--issue", SLUG, "--json")
    rows = [r for r in json.loads(out)["checks"] if r["name"] == "artifacts-approved"]
    assert rows and rows[0]["status"] == "pass", out
    code, out, err = _ship(root)
    assert code == 0, out + err
    assert "land_commit" in manifest(root)
    assert entries(root)["distribution-map"]["status"] == "omitted"


def test_asw_19_omitted_without_reason_refused(tmp_path):
    root = project(tmp_path)
    for kind in ("acceptance-criteria", "technical-design", "verification-report"):
        assert register(root, kind, "approved")[0] == 0
    body = manifest(root)
    for entry in body["artifacts"]:
        if entry["kind"] == "distribution-map":
            entry["status"] = "omitted"
            entry.pop("reason", None)
    write_manifest(root, body)
    _ready(root)
    head = git(root, "rev-parse", "HEAD")
    code, out, err = _ship(root)
    assert code == 2, out + err
    assert "distribution-map" in out + err
    assert 'compass issue artifact set distribution-map --status omitted --reason "<why>"' in out + err
    _untouched(root, head)


# --- ASW-20 --------------------------------------------------------------------

def _repo(path):
    root = Path(path)
    root.mkdir(parents=True)
    git(root, "init", "-q")
    (root / "README.md").write_text("hello\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    return root


def _approach_entry(root, slug):
    return next(a for a in qf._manifest(root, slug)["artifacts"]
                if a["kind"] == "delivery-approach")


def test_asw_20_quick_fix_gains_no_new_stop(tmp_path):
    repo = _repo(tmp_path / "lands")
    slug = "greet-lands"
    qf._ready_to_finish(repo, slug)
    assert _approach_entry(repo, slug)["status"] == "draft"
    finish = qf._finish(repo, slug)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    found = _approach_entry(repo, slug)
    assert (found["status"], found["approved_by"]) == ("approved", "compass quick-fix finish")
    assert found["approved_at"]
    assert "land_commit" in qf._manifest(repo, slug)

    later = _repo(tmp_path / "later")
    slug = "greet-later"
    qf._ready_to_finish(later, slug)
    finish = qf._finish(later, slug, "--no-commit")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert _approach_entry(later, slug)["approved_by"] == "compass quick-fix finish"
    head = git(later, "rev-parse", "HEAD")
    docs = f"docs/compass/{qf._manifest(later, slug)['created']}-{slug}"
    git(later, "add", "data/greeting.txt", docs, f".compass/work/{slug}")
    result = run(later, "ship-commit", "--issue", slug, "-m", "Say hello")
    assert result[0] == 0, result[1] + result[2]
    assert git(later, "rev-parse", "HEAD") != head


# --- ASW-21 --------------------------------------------------------------------

def _stage_run(root, swap):
    """A regular issue run with the stage commands only."""
    qf_brief = root / "brief.md"
    qf_brief.write_text("# brief\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "brief")
    assert register(root, "acceptance-criteria")[0] == 0           # define
    assert register(root, "technical-design")[0] == 0              # plan
    assert register(root, "distribution-map")[0] == 0              # breakdown

    def subtask():
        return run(root, "issue", "subtask", "add", "subtask-1", "--brief", "brief.md",
                   "--model", "m", "--budget", "1", "--issue", SLUG)

    def red():
        return run(root, "tdd-red", "--issue", SLUG, "--", "sh", "-c", "echo FAILED; exit 1")

    for step in ((red, subtask) if swap else (subtask, red)):
        code, out, err = step()
        assert code == 0, out + err
    assert register(root, "verification-report")[0] == 0           # verify
    _ready(root)
    body = manifest(root)
    for gate in body["gates"]:
        gate["status"] = "pending"
    write_manifest(root, body)
    kinds = {"verify.correctness": "test-run", "verify.governance": "command-output",
             "verify.traceability": "command-output", "verify.regression": "test-run",
             "verify.clarity": "artifact", "verify.security": "command-output"}
    for number, (gate, kind) in enumerate(kinds.items(), 1):
        add_evidence(root, f"EV-G{number}", kind)
        code, out, err = run(root, "gate", "pass", gate, "--evidence", f"EV-G{number}",
                             "--issue", SLUG)
        assert code == 0, out + err
    code, out, err = _ship(root)
    assert code == 0, out + err
    return {k: (a["status"], a.get("approved_by"), bool(a.get("approved_at")))
            for k, a in entries(root).items()}


def test_asw_21_regular_issue_end_to_end_every_artifact_approved(tmp_path):
    first = _stage_run(project(tmp_path / "a"), swap=False)
    assert set(first) == set(REGULAR)
    for kind, (status, by, at) in first.items():
        assert status == "approved" and by and at, kind
        assert by.startswith("compass "), (kind, by)
    assert first["acceptance-criteria"][1] == BY_SET
    assert first["technical-design"][1] == BY_SET
    assert first["distribution-map"][1] == "compass tdd-red"
    assert first["verification-report"][1] == "compass gate pass"
    second = _stage_run(project(tmp_path / "b"), swap=True)
    assert second == first
