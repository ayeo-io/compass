"""The per-issue README - the page a reviewer opens first.

An issue directory answers "what files exist". It does not answer the questions
a reviewer actually has: what am I being asked to approve, what should I read,
and what was deliberately left out. Those live in the registry, and this page
renders them.

WHAT THIS PAGE IS NOT. It carries no raw evidence. Command output and test runs
are linked, not reproduced - a review page that reproduces its evidence stops
being two screens and stops being read.

It is generated, never hand-edited, and guarded for staleness the way
`docs/system-spec.md` is. A generated page nobody checks is trusted anyway,
which is worse than no page.

Scenario ids trace to the-human-front-door/acceptance-criteria.md.
"""

# These tests assert the current names (technical-design.md, intent.md).
# Older manifests and documents still load (ADR-006).
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "cli"))

INSTRUCTION_SURFACES = [REPO_ROOT / "commands", REPO_ROOT / "skills",
                        REPO_ROOT / "templates"]


def _issue(tmp_path: Path, artifacts: Optional[List[Dict[str, Any]]] = None,
           **spine_extra: Any) -> Path:
    task_dir = tmp_path / "work" / "export-portfolio-data"
    task_dir.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {
        "schema_version": "2.0", "task": "export-portfolio-data",
        "created": "2026-08-23", "status": "active",
        "assessment": {"risk": "cross-cutting", "familiarity": "brownfield-mapped",
                       "size": "large", "goal": "delivery"},
        "delivery_approach": "initiative", "scenarios": [], "changed_files": [],
        "evidence": [], "gates": [],
    }
    if artifacts is not None:
        manifest["artifacts"] = artifacts
    manifest.update(spine_extra)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    return task_dir


PACK = [
    {"id": "ART-HLD", "kind": "design", "path": "technical-design.md",
     "status": "awaiting-approval",
     "reason": "new service, queue and storage boundaries"},
    {"id": "ART-AC", "kind": "acceptance-criteria", "path": "acceptance-criteria.md",
     "status": "approved",
     "reason": "14 scenarios across export, permissions and failure recovery"},
    {"id": "ART-THREAT", "kind": "threat-model", "status": "omitted",
     "reason": "no auth, privacy or trust-boundary surface changes here"},
]


# ---------------------------------------------------------------------------
# Group C - the dashboard
# ---------------------------------------------------------------------------

def test_c1_dashboard_names_decision_and_start(tmp_path):
    """`TRC-C1`: the first screen states what is being asked and what to read.

    A reviewer who has to work out what they are approving has already been
    failed by the page.
    """
    from compass_pkg.dashboard import render_dashboard
    task_dir = _issue(tmp_path, artifacts=PACK)
    page = render_dashboard(str(task_dir))

    first_screen = "\n".join(page.splitlines()[:25]).lower()
    assert "decision" in first_screen, (
        "the first screen does not say what the reviewer is being asked to "
        "decide:\n" + first_screen)
    assert "technical-design.md" in "\n".join(page.splitlines()[:25]), (
        "the first screen does not name the one document to read")


def test_c2_dashboard_lists_registered_artifacts(tmp_path):
    """`TRC-C2`: each document appears with its status and the reason it exists."""
    from compass_pkg.dashboard import render_dashboard
    task_dir = _issue(tmp_path, artifacts=PACK)
    # The documents have to EXIST for their registry status to mean anything -
    # `awaiting-approval` on a file nobody wrote is not a state a reviewer can
    # act on, and the page reports absence instead.
    for e in PACK:
        if e.get("path"):
            (task_dir / e["path"]).write_text("# %s\n" % e["kind"])
    page = render_dashboard(str(task_dir))

    for entry in PACK:
        if entry["status"] == "omitted":
            continue
        assert entry["kind"] in page, f"{entry['kind']} is missing from the pack"
        # The reason has to travel with the ROW - and it has to be the table
        # row, not the first line that happens to mention the kind. The
        # decision sentence names the same document, so an unscoped match read
        # that instead and reported a missing status that was never missing.
        row = next((l for l in page.splitlines()
                    if entry["kind"] in l and l.lstrip().startswith("|")), "")
        assert entry["status"] in row, (
            f"{entry['kind']} appears without its status:\n  {row}")
        assert entry["reason"][:24] in row, (
            f"{entry['kind']} appears without the reason it exists:\n  {row}")


def test_c3_dashboard_lists_omissions(tmp_path):
    """`TRC-C3`: each omission appears with the reason it was omitted.

    This makes an omission visible without making the reviewer read the
    routing algorithm.
    """
    from compass_pkg.dashboard import render_dashboard
    page = render_dashboard(str(_issue(tmp_path, artifacts=PACK)))

    omitted = [e for e in PACK if e["status"] == "omitted"][0]
    row = next((l for l in page.splitlines()
                if omitted["kind"] in l and "trust-boundary" in l), "")
    assert row, (
        "the omitted document does not appear with its reason, so a reader "
        "cannot tell a decision from a gap:\n" + page)


def test_c4_dashboard_carries_no_raw_evidence(tmp_path):
    """`TRC-C4`: evidence is linked, not reproduced.

    Asserts an ABSENCE, which is the easiest thing to satisfy without checking
    anything - so the fixture plants real captured output in the manifest and the
    assertion looks for it. A page that renders nothing would pass a test that
    only searched for a marker.
    """
    from compass_pkg.dashboard import render_dashboard
    captured = "===== 1268 passed, 7 skipped in 209.93s ====="
    task_dir = _issue(tmp_path, artifacts=PACK, evidence=[
        {"id": "EV-T", "type": "test-run", "path": "evidence/green.json"}])
    (task_dir / "evidence").mkdir(exist_ok=True)
    (task_dir / "evidence" / "green.json").write_text(
        '{"command": "pytest", "exit_code": 0, "log_excerpt": "%s"}' % captured)

    page = render_dashboard(str(task_dir))

    assert captured not in page, (
        "captured command output was reproduced in the review page")
    assert "log_excerpt" not in page, (
        "a raw evidence field was rendered into the review page")
    assert "evidence/green.json" in page or "EV-T" in page, (
        "the evidence is neither pasted nor linked - it has vanished from the "
        "page entirely, which is not what 'linked, not pasted' means")


# ---------------------------------------------------------------------------
# Group D - a generated page that has drifted
# ---------------------------------------------------------------------------

def test_d1_stale_dashboard_is_reported(tmp_path):
    """`TRC-D1`: a dashboard that no longer matches its manifest says so.

    `docs/system-spec.md` is the worked precedent for a generated artifact
    in this repository, with its own currency guard.
    """
    from compass_pkg.dashboard import render_dashboard, dashboard_is_current
    task_dir = _issue(tmp_path, artifacts=PACK)
    (task_dir / "README.md").write_text(render_dashboard(str(task_dir)))
    assert dashboard_is_current(str(task_dir))[0], (
        "a freshly generated dashboard reported itself stale")

    # The manifest changes and nobody regenerates.
    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text())
    manifest["artifacts"].append(
        {"id": "ART-ROLL", "kind": "rollback-plan", "path": "rollback-plan.md",
         "status": "draft", "reason": "an irreversible migration is in scope"})
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))

    current, detail = dashboard_is_current(str(task_dir))
    assert not current, (
        "the manifest gained a document and the dashboard still reported itself "
        "current - so the page can disagree with its source and nothing says so")
    assert "regenerate" in detail.lower() or "compass" in detail.lower(), (
        "the report does not name how to fix it:\n" + detail)


# ---------------------------------------------------------------------------
# Group E - evidence is linked, not pasted
# ---------------------------------------------------------------------------

def test_e1_instructions_say_link_not_paste():
    """`TRC-E1`: no instruction asks for raw output to be pasted into a document
    a person reads.

    Reads each instruction's own sentence rather than the whole file:
    whole-file searches pass on unrelated text.
    """
    offenders = []
    pattern = re.compile(r"\bpaste[sd]?\b[^.\n]{0,80}", re.IGNORECASE)
    for root in INSTRUCTION_SURFACES:
        if not root.is_dir():
            continue
        for path in root.rglob("*.md"):
            for m in pattern.finditer(path.read_text(encoding="utf-8")):
                sentence = " ".join(m.group(0).split())
                # Pasting INTO evidence is fine; pasting into a human document
                # is what this forbids.
                # Plurals too: `\bartifact\b` does not match "artifacts".
                if re.search(r"\b(reports?|documents?|artifacts?|verification|"
                             r"devlogs?|reviews?)\b", sentence, re.IGNORECASE):
                    offenders.append("%s: %s"
                                     % (path.relative_to(REPO_ROOT), sentence))
    assert not offenders, (
        "these instructions ask for raw output to be pasted into a document a "
        "person reads - write the evidence file and link it:\n  "
        + "\n  ".join(offenders))


def test_c5_dashboard_verb_generates_and_checks(tmp_path):
    """`TRC-C5`: the page can be generated, and checked, from the CLI.

    A renderer nobody can run is not a usable page. `--check` writes nothing
    and reports drift, which is the mode the currency guard calls.
    """
    import subprocess
    cli = REPO_ROOT / "cli" / "compass"
    proj = tmp_path / "project"
    (proj / ".compass").mkdir(parents=True)
    (proj / ".compass" / "current-task").write_text("export-portfolio-data\n")
    (proj / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    task_dir = _issue(proj / ".compass", artifacts=PACK)

    gen = subprocess.run([sys.executable, str(cli), "issue", "dashboard"],
                         cwd=str(proj), capture_output=True, text=True, timeout=60)
    assert gen.returncode == 0, gen.stdout + gen.stderr
    readme = task_dir / "README.md"
    assert readme.is_file(), "the verb reported success and wrote no page"

    ok = subprocess.run([sys.executable, str(cli), "issue", "dashboard", "--check"],
                        cwd=str(proj), capture_output=True, text=True, timeout=60)
    assert ok.returncode == 0, (
        "a freshly generated page was reported stale:\n" + ok.stdout + ok.stderr)

    readme.write_text(readme.read_text() + "\nhand-edited\n")
    drifted = subprocess.run([sys.executable, str(cli), "issue", "dashboard", "--check"],
                             cwd=str(proj), capture_output=True, text=True, timeout=60)
    assert drifted.returncode != 0, (
        "an edited page was reported current, so --check cannot detect drift")


# ---------------------------------------------------------------------------
# Group D, second half - the currency guard as a real check
# ---------------------------------------------------------------------------

def test_d2_stale_dashboard_fails_a_guardrail_check(tmp_path):
    """`TRC-D2`: a drifted dashboard fails `compass check`, it does not merely warn.

    `dashboard_is_current` is a function nobody has to call. The complaint this
    issue answers is that a reviewer trusts what is in front of them, so the
    guard has to sit where the reviewer's approval is gated - which is the
    check, under the evidence-not-assertion guardrail. A drifted page is an
    assertion the record contradicts.

    Its three outcomes are all asserted, because two of them are the ones that
    would quietly make it a check that cannot fail: no page and a hand-written
    page must BOTH decline to check rather than pass.
    """
    from compass_pkg.check_results import NOTHING_TO_CHECK
    from compass_pkg.dashboard import (_check_dashboard_current,
                                       render_dashboard)
    task_dir = _issue(tmp_path, artifacts=PACK)
    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text())

    # 1. No page. Nothing on disk is claiming anything, so there is nothing to
    #    check - and that is NOT a pass.
    ok, detail = _check_dashboard_current(manifest, str(task_dir))
    assert ok is NOTHING_TO_CHECK, (
        "an issue with no dashboard reported a real pass, so this check would "
        "clear the guardrail on the 148 issues with no registry without "
        "reading anything:\n"
        + str(detail))

    # 2. A hand-written page. Not Compass's to police, and again not a pass.
    (task_dir / "README.md").write_text("# notes I keep by hand\n")
    ok, detail = _check_dashboard_current(manifest, str(task_dir))
    assert ok is NOTHING_TO_CHECK, (
        "a hand-written README was judged as a generated one:\n" + str(detail))

    # 3. Generated and current.
    (task_dir / "README.md").write_text(render_dashboard(str(task_dir)))
    ok, detail = _check_dashboard_current(manifest, str(task_dir))
    assert ok is True, ("a freshly generated dashboard failed the check:\n"
                        + str(detail))

    # 4. Generated, then the manifest moved underneath it.
    manifest["artifacts"] = PACK + [
        {"id": "ART-ROLL", "kind": "rollback-plan", "path": "rollback-plan.md",
         "status": "draft", "reason": "an irreversible migration is in scope"}]
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    ok, detail = _check_dashboard_current(manifest, str(task_dir))
    assert ok is False, (
        "the manifest gained a document the page does not show, and the check "
        "still cleared - so the review page can disagree with the record and "
        "nothing blocks on it")
    assert "compass issue dashboard" in detail, (
        "the failure does not name the command that fixes it:\n" + detail)


def test_d3_currency_check_is_registered_under_a_guardrail():
    """`TRC-D3`: the check is wired into `compass check`, not just importable.

    A check function that no guardrail lists never runs. Compass grows by
    adding checks under the five existing guardrails, never a sixth
    guardrail (ADR-002), so this asserts both the registration and the
    guardrail it joined.
    """
    sys.path.insert(0, str(REPO_ROOT / "cli"))
    from compass_pkg.check_cmd import CHECK_FNS, CHECK_GUIDANCE

    assert "dashboard-current" in CHECK_FNS, (
        "the currency check is not in CHECK_FNS, so naming it in guardrails.yml "
        "would make `compass check` fail with an unknown-check error")
    assert "dashboard-current" in CHECK_GUIDANCE, (
        "the check has no guidance entry, so its failure reads as bureaucracy "
        "rather than telling the reader why it matters and how to fix it")

    guardrails = yaml.safe_load(
        (REPO_ROOT / "governance" / "guardrails.yml").read_text())
    g4 = next(g for g in guardrails["defaults"] if g["id"] == "G4")
    assert "dashboard-current" in g4["checks"], (
        "the check is registered in code but no guardrail lists it, so it "
        "never runs:\n" + str(g4["checks"]))
    assert "dashboard-current" in guardrails["checks"], (
        "the check has no description in guardrails.yml's `checks:` catalogue")


def test_c6_dashboard_separates_written_from_still_owed(tmp_path):
    """`TRC-C6`: the pack distinguishes a document that exists from one that does not.

    `draft` is the status the routing seeds, and nothing moves it on its
    own, so a document can sit as `draft` whether or not it has been
    written. A reviewer reading a page that shows `draft` for a finished
    document goes looking for a decision that has already been made; one
    that shows it for a document that does not exist goes looking for a
    file that is not there. The resolver already knows the difference; the
    page must ask it.
    """
    from compass_pkg.dashboard import render_dashboard
    task_dir = _issue(tmp_path, artifacts=[
        {"id": "ART-AC", "kind": "acceptance-criteria",
         "path": "acceptance-criteria.md", "status": "draft",
         "reason": "every initiative carries one"},
        {"id": "ART-HLD", "kind": "hld", "path": "hld.md", "status": "draft",
         "reason": "every initiative carries one"},
    ])
    (task_dir / "acceptance-criteria.md").write_text("# criteria\n")

    page = render_dashboard(str(task_dir))
    rows = {l.split("|")[1].strip(): l for l in page.splitlines()
            if l.lstrip().startswith("|") and "---" not in l}

    assert "acceptance-criteria" in rows and "hld" in rows, (
        "the pack lost a document:\n" + page)
    written, owed = rows["acceptance-criteria"], rows["hld"]

    assert "not written" in owed.lower() or "owed" in owed.lower(), (
        "a document that does not exist on disk is shown the same way as one "
        "that does, so the page sends a reviewer looking for a missing "
        "file:\n  " + owed)
    assert "not written" not in written.lower(), (
        "a document that DOES exist was reported as missing - the check now "
        "fails in the opposite direction, which is just as wrong:\n  " + written)


def test_c7_artifact_status_can_be_moved_from_the_cli(tmp_path):
    """`TRC-C7`: a document's status can be changed, and an omission recorded.

    Routing seeds every earned document as `draft`. A CLI verb must be able
    to move it to `omitted`, `awaiting-approval` or `approved`, or the
    page's two headline sections, "Decision required" and "Deliberately
    omitted", stay permanently empty.

    An omission MUST carry a reason. A document dropped without one is
    indistinguishable from one nobody got to, which is the distinction the
    whole registry exists to make.
    """
    import subprocess
    cli = REPO_ROOT / "cli" / "compass"
    proj = tmp_path / "project"
    (proj / ".compass").mkdir(parents=True)
    (proj / ".compass" / "current-task").write_text("export-portfolio-data\n")
    (proj / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    task_dir = _issue(proj / ".compass", artifacts=[
        {"id": "ART-PRD", "kind": "prd", "path": "intent.md", "status": "draft",
         "reason": "every initiative carries one"},
        {"id": "ART-HLD", "kind": "design", "path": "technical-design.md",
         "status": "draft", "reason": "every initiative carries one"}])

    def run(*a):
        return subprocess.run([sys.executable, str(cli), "issue", "artifact", *a],
                              cwd=str(proj), capture_output=True, text=True,
                              timeout=60)

    # An omission with no reason is refused.
    bad = run("prd", "--status", "omitted")
    assert bad.returncode != 0, (
        "a document was omitted with no reason recorded, so a deliberate "
        "decision and a gap nobody noticed now look identical")
    assert "reason" in (bad.stdout + bad.stderr).lower()

    ok = run("prd", "--status", "omitted", "--reason",
             "no product owner on this issue - the intent is in the bug report")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert run("design", "--status", "awaiting-approval").returncode == 0

    # An unknown kind is refused rather than silently added, the way
    # `tdd-red --scenario` refuses an id that is not in the manifest.
    assert run("no-such-doc", "--status", "approved").returncode != 0, (
        "a status was set on a document this issue never earned")

    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text())
    by_kind = {a["kind"]: a for a in manifest["artifacts"]}
    assert by_kind["prd"]["status"] == "omitted"
    assert "product owner" in by_kind["prd"]["reason"]
    assert by_kind["design"]["status"] == "awaiting-approval"

    from compass_pkg.dashboard import render_dashboard
    page = render_dashboard(str(task_dir))
    assert "No decision required" not in page, (
        "a document is awaiting approval and the page still says there is no "
        "decision to make")
    assert "Nothing recorded as omitted" not in page, (
        "an omission was recorded and the page still reports none")
    assert "no product owner" in page, (
        "the omission is listed without the reason it was omitted")


# ---------------------------------------------------------------------------
# The status line shows the state read from the records (TRC-D1)
# ---------------------------------------------------------------------------

def _status_line(task_dir: Path) -> str:
    from compass_pkg.dashboard import render_dashboard
    page = render_dashboard(str(task_dir))
    return next(l for l in page.splitlines() if l.startswith("**Status:**"))


def _store(task_dir: Path, drop=(), **keys: Any) -> None:
    """Rewrite the manifest the way a 6.0 CLI leaves an in-flight issue: no
    stored status, whatever else the test sets."""
    path = task_dir / "manifest.yml"
    manifest = yaml.safe_load(path.read_text())
    for key in drop:
        manifest.pop(key, None)
    manifest.update(keys)
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))


DESIGN = [{"id": "ART-TD", "kind": "technical-design", "path": "technical-design.md",
           "status": "draft", "reason": "regular approach"}]


def test_the_status_line_shows_the_derived_state(tmp_path):
    """An in-flight issue stores no status, so the page reads the state from
    its records instead of printing a question mark (`TRC-D1`)."""
    task_dir = _issue(tmp_path, artifacts=DESIGN)
    _store(task_dir, drop=("status",))
    line = _status_line(task_dir)
    assert "in-progress" in line, line
    assert "?" not in line, line


def test_the_status_line_shows_the_close_reason_of_a_done_issue(tmp_path):
    task_dir = _issue(tmp_path, artifacts=DESIGN)
    _store(task_dir, status="done", close_reason="not-planned")
    line = _status_line(task_dir)
    assert "done (not-planned)" in line, line


def test_the_status_line_says_when_an_issue_is_blocked(tmp_path):
    task_dir = _issue(tmp_path, artifacts=DESIGN)
    _store(task_dir, drop=("status",),
           blocked={"reason": "waiting for the schema decision", "at": "2026-10-09"})
    line = _status_line(task_dir)
    assert "in-progress (blocked: waiting for the schema decision)" in line, line


def test_a_blocked_flag_with_no_reason_says_so_as_flow_does(tmp_path):
    task_dir = _issue(tmp_path, artifacts=DESIGN)
    _store(task_dir, drop=("status",), blocked={"at": "2026-10-09"})
    assert "in-progress (blocked: no reason recorded)" in _status_line(task_dir)


def test_a_held_issue_shows_backlog(tmp_path):
    task_dir = _issue(tmp_path, artifacts=DESIGN)
    _store(task_dir, status="backlog")
    assert "backlog" in _status_line(task_dir)


def test_an_issue_with_a_gate_past_pending_shows_in_review(tmp_path):
    task_dir = _issue(tmp_path, artifacts=DESIGN)
    _store(task_dir, drop=("status",), gates=[{"id": "verify.correctness", "status": "pass"}])
    assert "**Status:** in-review" in _status_line(task_dir)


def test_a_done_issue_shows_each_close_reason_or_none(tmp_path):
    for reason, shown in (("completed", "done (completed)"), ("duplicate", "done (duplicate)")):
        task_dir = _issue(tmp_path / reason, artifacts=DESIGN)
        _store(task_dir, status="done", close_reason=reason)
        assert f"**Status:** {shown} " in _status_line(task_dir) + " "
    task_dir = _issue(tmp_path / "none", artifacts=DESIGN)
    _store(task_dir, status="done")
    assert "**Status:** done " in _status_line(task_dir) + " "
    assert "done (" not in _status_line(task_dir)


def test_a_blocked_flag_left_on_a_done_issue_is_ignored(tmp_path):
    task_dir = _issue(tmp_path, artifacts=DESIGN)
    _store(task_dir, status="done", close_reason="completed", blocked={"reason": "old"})
    line = _status_line(task_dir)
    assert "done (completed)" in line and "blocked" not in line, line


def test_an_unreadable_manifest_still_prints_a_question_mark(tmp_path):
    for name, text in (("bad-yaml", "key: [unclosed\n"), ("a-list", "- 1\n- 2\n")):
        task_dir = _issue(tmp_path / name, artifacts=DESIGN)
        (task_dir / "manifest.yml").write_text(text)
        assert "**Status:** ? " in _status_line(task_dir) + " ", name
