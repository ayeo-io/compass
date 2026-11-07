"""The two hooks ask the CLI where a document is.

Scenario group D of `docs-compass-artifacts`.

This group carries the highest consequence in the spec. `hooks/pre-tool.sh`
treats a missing `delivery-approach.md` beside the manifest as "assessment did
not complete" and **blocks every code edit in the project**. Move that file
without moving this reader and nobody can work.

The hooks are shell and cannot import the resolver, so they ask the CLI for the
path with `compass issue artifact-path <kind>`. One answer, from the same code
the Python readers use, rather than a second implementation in bash that drifts
from the first.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRE_TOOL = ROOT / "hooks" / "pre-tool.sh"
STOP = ROOT / "hooks" / "stop.sh"
COMPASS_CLI = ROOT / "cli" / "compass"

SLUG = "a-moved-issue"
CREATED = "2026-09-08"
DOCS_REL = f"docs/compass/{CREATED}-{SLUG}"


def _manifest(*, register):
    """A manifest for an issue whose documents live under docs/compass/.

    `register=False` gives the half-finished case: the documents are there and
    the registry does not know, which must read as "not written" rather than
    as a clean hit.
    """
    artifacts = []
    if register:
        for kind, name in (("delivery-approach", "delivery-approach.md"),
                           ("acceptance-criteria", "acceptance-criteria.md"),
                           ("verification-report", "verification-report.md")):
            artifacts.append({
                "id": "ART-" + kind.upper().replace("-", "_"), "kind": kind,
                "status": "draft", "reason": "every issue carries one",
                "path": f"{DOCS_REL}/{name}",
            })
    return yaml.safe_dump({
        "schema_version": "2.0", "issue": SLUG, "created": CREATED,
        "status": "active",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "small", "goal": "delivery", "role": "engineer"},
        "delivery_approach": "standard",
        "stages": {"assess": "full", "define": "full", "refine": "light",
                   "plan": "full", "breakdown": "skipped", "implement": "full",
                   "verify": "full", "ship": "full"},
        "artifacts": artifacts, "evidence": [], "gates": [],
        # A stated criterion, so the acceptance-before-code guardrail is
        # satisfied and the only thing these tests can fail on is where the
        # delivery-approach record lives.
        "scenarios": [{"id": "MV-1", "title": "it works", "intent": "INT-1",
                       "tests": ["tests/test_x.py::test_mv_1"]}],
        "changed_files": [], "claims": [], "follow_ups": [],
        "reassessments": [], "friction": [],
    }, sort_keys=False)


def _project(tmp_path, *, documents=True, register=True, red=True,
             gate_decision="FAIL"):
    work = tmp_path / ".compass" / "work" / SLUG
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n",
                                                      encoding="utf-8")
    (tmp_path / ".compass" / "current-task").write_text(SLUG, encoding="utf-8")
    (work / "manifest.yml").write_text(_manifest(register=register),
                                       encoding="utf-8")
    if red:
        # A REAL red, written by the CLI. The hook rejects a marker with no
        # record beside it. An empty file here would make these tests
        # measure that rejection, not where the delivery-approach record
        # lives.
        r = subprocess.run(
            [sys.executable, str(COMPASS_CLI), "tdd-red", "--issue", SLUG,
             "--quiet", "--", sys.executable, "-c", "print('1 failed'); raise SystemExit(1)"],
            capture_output=True, text=True, timeout=120, cwd=str(tmp_path))
        assert (work / ".red").is_file(), (
            "the fixture could not record a red:\n" + r.stdout + r.stderr)

    if documents:
        docs = tmp_path / DOCS_REL
        # The render after `tdd-red` has made the folder for the issue page.
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "delivery-approach.md").write_text(
            "# Delivery approach - a-moved-issue\n\nStandard.\n",
            encoding="utf-8")
        (docs / "acceptance-criteria.md").write_text(
            "# Acceptance criteria - a-moved-issue\n", encoding="utf-8")
        # `Overall:` is the wording the stop hook actually greps for, and the
        # shipped template writes. A fixture with its own phrasing would prove
        # only that the hook found *a* file.
        (docs / "verification-report.md").write_text(
            f"# Verification report\n\n**Overall:** {gate_decision}\n",
            encoding="utf-8")

    # A production file for the hook to be asked about.
    src = tmp_path / "src"
    src.mkdir()
    (src / "thing.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def _env(project):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
            "HOME": str(project), "CLAUDE_PROJECT_DIR": str(project)}


def _pre_tool(project, path="src/thing.py"):
    payload = json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(project / path)},
    })
    return subprocess.run(["bash", str(PRE_TOOL)], input=payload,
                          cwd=str(project), capture_output=True, text=True,
                          timeout=120, env=_env(project))


def _stop(project):
    return subprocess.run(["bash", str(STOP)], input="{}", cwd=str(project),
                          capture_output=True, text=True, timeout=120,
                          env=_env(project))


# --- the verb the hooks call -------------------------------------------------



def test_the_verb_exits_non_zero_when_the_document_is_absent(tmp_path):
    """A caller in bash reads the exit code before it reads the string.

    Printing a plausible path for a document that is not there is how a hook
    concludes assessment ran when it did not.
    """
    project = _project(tmp_path, documents=False, register=False)
    r = subprocess.run(
        [sys.executable, str(COMPASS_CLI), "issue", "artifact-path",
         "delivery-approach", "--issue", SLUG],
        capture_output=True, text=True, timeout=120, cwd=str(project))
    assert r.returncode != 0, (
        "the verb reported success for a document that does not exist:\n"
        + r.stdout + r.stderr)


# --- `TRC-D1` ------------------------------------------------------------------

def test_trc_d1_the_hook_accepts_a_relocated_delivery_approach_record(tmp_path):
    project = _project(tmp_path)
    r = _pre_tool(project)
    assert r.returncode == 0, (
        "the pre-tool hook blocked an edit on an issue whose "
        "delivery-approach record is registered under docs/compass/:\n"
        + r.stderr)
    assert "triage did not complete" not in r.stderr, (
        "the hook found the record but still says assessment did not "
        f"complete:\n{r.stderr}")


# --- `TRC-D2` ------------------------------------------------------------------

def _no_approach(project):
    """The manifest with no `delivery_approach`: the assessment did not finish."""
    manifest = project / ".compass" / "work" / SLUG / "manifest.yml"
    body = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    body.pop("delivery_approach")
    manifest.write_text(yaml.safe_dump(body), encoding="utf-8")
    return project


def test_trc_d2_the_hook_still_blocks_with_no_record_anywhere(tmp_path):
    """The control. 9.0.0 reads the approach from the manifest (ADR-091), so the
    record is missing when the manifest names no approach."""
    project = _no_approach(_project(tmp_path, documents=False, register=False))
    r = _pre_tool(project)
    assert r.returncode != 0, (
        "the pre-tool hook allowed a code edit on an issue with no "
        "delivery-approach record in either location:\n" + r.stderr)
    assert "delivery approach" in r.stderr and "assess" in r.stderr, (
        "the hook blocked without naming the missing record and the command "
        f"that writes it:\n{r.stderr}")


# --- `TRC-D3` ------------------------------------------------------------------

@pytest.mark.parametrize("register", [True, False])
def test_trc_d3_the_stop_hook_finds_the_approach_and_ignores_the_report(tmp_path, register):
    """The stop hook reads the delivery approach from the manifest, so it does not
    warn that the record is missing, whether or not the documents are registered.
    It no longer reads `verification-report.md`: 9.0.0 writes none, so a failing
    gate decision in an old report draws no warning (#358)."""
    project = _project(tmp_path, register=register, gate_decision="FAIL")
    out = _stop(project).stderr
    assert "delivery approach is MISSING" not in out, (
        "the stop hook says the delivery approach is missing, though the "
        f"manifest names it:\n{out}")
    assert "verification-report.md" not in out, (
        f"the stop hook still reads the verification report:\n{out}")
    assert ".red marker still present" in out, (
        f"the stop hook did not run its check on the issue:\n{out}")


def test_trc_d3_the_stop_hook_still_reports_a_missing_record(tmp_path):
    """The control for the check above."""
    project = _no_approach(_project(tmp_path, documents=False, register=False))
    out = _stop(project).stderr
    assert "delivery approach" in out, (
        "an issue directory with no delivery-approach record anywhere drew no "
        f"warning:\n{out}")


# --- 9.0.0: the manifest is the delivery-approach record (ADR-091) ------------------

def test_the_hook_reads_the_approach_from_the_manifest(tmp_path):
    """9.0.0 writes no delivery-approach.md, so an assessed issue with no document lets
    a code edit through, and one whose manifest records no approach is blocked."""
    project = _project(tmp_path, documents=False, register=False)
    r = _pre_tool(project)
    assert r.returncode == 0, r.stderr
    manifest = project / ".compass" / "work" / SLUG / "manifest.yml"
    body = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    body.pop("delivery_approach")
    manifest.write_text(yaml.safe_dump(body), encoding="utf-8")
    r = _pre_tool(project)
    assert r.returncode != 0 and "assess" in r.stderr, r.stderr
