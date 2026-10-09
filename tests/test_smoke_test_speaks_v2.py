"""The install smoke test describes the framework a reader actually installed.

`docs/install-smoke-test.md` is the first document a new user follows, so it
must use the v2 names: `/compass:assess`, `assessment:`, `delivery_approach:`,
schema 2.0.

Zero pending surfaces means the listed surfaces are clean, not the whole
repository - `docs/install-smoke-test.md` was never in
`governance/terminology.yml`'s `scan.surfaces`, so nothing held it to the
frozen vocabulary through the whole of v2.

This asserts both halves: the document speaks v2, and it is in the scanned
set so a retired term in it fails the build.

Scenario ids: see docs/system-spec.md (TRC-1, `TRC-2`).
"""

# These tests assert the current file names; files written under older
# names still load (ADR-006).
from __future__ import annotations

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SMOKE_TEST = ROOT / "docs" / "install-smoke-test.md"
SMOKE_TEST_REL = "docs/install-smoke-test.md"

# Retired v1 spellings that describe behaviour this framework no longer has.
# Each is paired with what a reader should see instead, so a failure says what
# to write rather than only what is wrong.
RETIRED = {
    "/compass:frame": "/compass:assess",
    "readings:": "assessment:",
    'schema_version: "1.0"': 'schema_version: "2.0"',
}


def test_trc_1_the_smoke_test_describes_v2_behaviour():
    text = SMOKE_TEST.read_text(encoding="utf-8")
    found = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for retired, replacement in RETIRED.items():
            if retired in line:
                found.append(
                    f"{SMOKE_TEST_REL}:{lineno}: {retired!r} - v2 says "
                    f"{replacement!r}"
                )
    assert not found, (
        "the install smoke test describes v1 behaviour, on the first "
        "document a new user follows:\n  " + "\n  ".join(found)
    )


def test_trc_2_the_smoke_test_is_scanned_for_the_frozen_vocabulary():
    """The smoke test must be in the scanned set: that keeps a retired
    term out of it."""
    terminology = yaml.safe_load(
        (ROOT / "governance" / "terminology.yml").read_text(encoding="utf-8")
    )
    surfaces = terminology.get("scan", {}).get("surfaces", [])
    assert SMOKE_TEST_REL in surfaces, (
        f"{SMOKE_TEST_REL} is not in governance/terminology.yml's "
        f"scan.surfaces, so nothing holds it to the frozen vocabulary - "
        f"which is exactly how it kept describing v1 through the whole of v2"
    )


# --- TRC-S6 (issue `six-zero-docs-sweep`): every step a healthy install passes --

def smoke_step_findings(text):
    """Claims in the smoke test that a healthy 6.0.0 install fails."""
    flat = " ".join(text.split())
    found = []
    if "must contain at least `manifest.yml` and `delivery-approach.md`" in flat:
        found.append("step 4 looks for delivery-approach.md beside the manifest")
    if "approval state and next action" in flat:
        found.append("step 4 expects the dashboard to show a next action")
    if "bash scripts/install.sh --uninstall" in text and \
            "bash scripts/install.sh --global --uninstall" not in text:
        found.append("step 7 uninstalls the project install after a global install")
    if "explains why it matters" in flat:
        found.append("step 5 expects a failed check to explain why it matters")
    return found


def test_trc_s6_the_scan_reports_the_old_steps():
    old = ("The issue directory must contain at least `manifest.yml` and "
           "`delivery-approach.md`. It must show the approval state and next action. "
           "bash scripts/install.sh --uninstall. It explains why it matters;")
    assert len(smoke_step_findings(old)) == 4
    assert not smoke_step_findings("bash scripts/install.sh --global --uninstall")


def test_trc_s6_smoke_steps_pass_on_a_healthy_install(tmp_path):
    """Run step 4 and step 5 in a scratch project and check what the page says
    about their results."""
    import subprocess
    import sys
    text = SMOKE_TEST.read_text(encoding="utf-8")
    assert not smoke_step_findings(text)
    assert "docs/compass/<date>-<issue-slug>/delivery-approach.md" in text
    assert ".compass/work/<issue-slug>/manifest.yml" in text
    assert "--global --uninstall" in text

    cli = [sys.executable, str(ROOT / "cli" / "compass")]

    def run(*argv):
        return subprocess.run(cli + list(argv), cwd=tmp_path, capture_output=True,
                              text=True, timeout=120)

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert run("init").returncode == 0
    start = run("quick-fix", "start", "scratch-issue", "--risk", "trivial - scratch",
                "--familiarity", "greenfield - scratch", "--size", "atomic - scratch",
                "--intent", "the install works", "--scenario",
                "Given a scratch repo When assessed Then the issue exists",
                "--test", "tests/test_x.py::test_a")
    assert start.returncode == 0, start.stdout + start.stderr
    assert (tmp_path / ".compass" / "current-task").is_file()
    assert (tmp_path / ".compass" / "work" / "scratch-issue" / "manifest.yml").is_file()
    created = next((tmp_path / "docs" / "compass").glob("*-scratch-issue"))
    assert (created / "delivery-approach.md").is_file()
    where = run("issue", "artifact-path", "delivery-approach")
    assert where.returncode == 0 and where.stdout.strip().endswith("delivery-approach.md")

    render = run("issue", "dashboard", "render", "--issue", "scratch-issue")
    assert render.returncode == 0, render.stdout + render.stderr
    page = (tmp_path / ".compass" / "work" / "scratch-issue" / "README.md").read_text()
    assert "next action" not in page.lower()
    assert "## Decision required" in page and "## Review pack" in page
    assert "## Deliberately omitted" in page

    check = run("check", "--issue", "scratch-issue")
    assert check.returncode != 0 and "Traceback" not in check.stdout + check.stderr
    assert "FAIL suite-passed" in check.stdout and "fix:" in check.stdout
