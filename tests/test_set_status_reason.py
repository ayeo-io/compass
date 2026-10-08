"""`compass issue set-status --reason` leaves the manifest valid (issue
set-status-reason-writes-an-invalid-manifest).

`--reason` on any status must leave a manifest that passes `issue lint`. No
earlier test set a status with a reason and then linted the result.

Scenario ids: `TRC-A1`, `TRC-A2`, `TRC-F1` in
set-status-reason-writes-an-invalid-manifest/acceptance-criteria.md
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "cli" / "compass"
SCHEMA = REPO_ROOT / "schemas" / "manifest.schema.json"

# Every way the command stores a status: the words it takes and the flags that
# go with `done`. Checked against the CLI's own help, so a word the help drops
# fails here instead of shrinking the sweep below.
def _accepted_statuses() -> list[tuple[str, list[str]]]:
    r = subprocess.run([sys.executable, str(CLI), "issue", "status", "set", "--help"],
                       capture_output=True, text=True, timeout=60)
    text = r.stdout + r.stderr
    for word in ("backlog", "done", "--close-reason", "--duplicate-of", "completed",
                 "not-planned", "duplicate"):
        assert word in text, (
            f"`issue status set --help` does not mention {word!r}, so this list has "
            f"drifted from the command and the sweep below covers less than "
            f"it claims:\n{text[:600]}")
    return [("backlog", []), ("done", ["--close-reason", "not-planned"]),
            ("done", ["--close-reason", "completed"])]


def _project(tmp: Path) -> Path:
    """A minimal project with one issue whose manifest lints clean."""
    work = tmp / ".compass" / "work" / "sample"
    work.mkdir(parents=True)
    (tmp / ".compass" / "config.yml").write_text("version: 1.0.0\n", encoding="utf-8")
    # Carries an `assessment:` block because lint needs one of any issue
    # that has left `queued`, and this fixture is set to every status in turn.
    # Without it the sweep would fail on a rule that has nothing to do with
    # the key under test - a test failing for the wrong reason proves nothing
    # about the right one.
    (work / "manifest.yml").write_text(
        'schema_version: "2.0"\n'
        'issue: sample\n'
        'created: "2026-08-29"\n'
        'status: queued\n'
        "assessment:\n"
        "  risk: contained\n"
        "  familiarity: brownfield-mapped\n"
        "  size: atomic\n"
        "  goal: delivery\n"
        "  urgency: none\n"
        "  role: engineer\n"
        "  labels: []\n"
        "evidence: []\ngates: []\nscenarios: []\n"
        "changed_files: []\nclaims: []\nfollow_ups: []\nreassessments: []\n",
        encoding="utf-8")
    shutil.copytree(REPO_ROOT / "schemas", tmp / "schemas")
    return tmp


def _run(project: Path, *args):
    r = subprocess.run([sys.executable, str(CLI), *args],
                       cwd=str(project), capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout + r.stderr


# ---------------------------------------------------------------------------
# A reason on any status leaves the manifest valid (TRC-A1)
# ---------------------------------------------------------------------------

def test_a_reason_on_any_status_leaves_the_manifest_valid():
    statuses = _accepted_statuses()
    broken = []

    for status, flags in statuses:
        with tempfile.TemporaryDirectory() as raw:
            project = _project(Path(raw))
            code, out = _run(project, "issue", "status", "set", status, *flags,
                             "--issue", "sample",
                             "--reason", "why this transition happened")
            if code != 0:
                # `completed` legitimately refuses when gates are unmet. That
                # is a different rule and not what this scenario is about.
                if "completed" in flags and "gate" in out.lower():
                    continue
                broken.append(f"{status}: status set itself failed:\n{out[-300:]}")
                continue

            code, out = _run(project, "issue", "lint", "--issue", "sample")
            if code != 0:
                broken.append(f"{status}: the manifest no longer lints:\n{out[-300:]}")

    assert not broken, (
        "`set-status --reason` wrote a manifest that fails its own linter:\n  "
        + "\n  ".join(broken)
        + "\nThe schema sets additionalProperties: false, so any key the CLI "
          "writes must be declared in schemas/manifest.schema.json.")


# ---------------------------------------------------------------------------
# The recorded reason says which transition it belongs to (TRC-A2)
# ---------------------------------------------------------------------------

def test_the_recorded_reason_says_which_transition_it_belongs_to():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    props = schema.get("properties", {})

    assert schema.get("additionalProperties") is False, (
        "the manifest schema no longer forbids undeclared keys, so this whole "
        "class of defect stops being caught and these scenarios assert less "
        "than they appear to")

    assert "parked_reason" in props, (
        "parked_reason is gone from the schema - parking an issue with a "
        "reason would now write an undeclared key")
    assert "status_reason" in props, (
        "status_reason is not declared, so a reason recorded against any "
        "status other than parked writes a key the schema forbids")

    # A bare `note` is not in the schema and must not be: the key must say
    # which transition the reason belongs to.
    assert "note" not in props, (
        "`note` was added to the schema instead of naming the field for what "
        "it records. The key should say which transition the reason belongs "
        "to, the way parked_reason does")

    with tempfile.TemporaryDirectory() as raw:
        project = _project(Path(raw))
        # The fixture holds the issue in backlog; ending the hold records why.
        code, out = _run(project, "issue", "status", "remove",
                         "--issue", "sample", "--reason", "re-opened for rework")
        assert code == 0, out
        body = (project / ".compass" / "work" / "sample" / "manifest.yml").read_text(
            encoding="utf-8")
        assert "re-opened for rework" in body, (
            "the reason was accepted and then not recorded, so it is lost the "
            "moment the command returns")
        assert "status_reason" in body, (
            f"the reason was recorded under some other key:\n{body}")


# ---------------------------------------------------------------------------
# A key the schema forbids is refused (TRC-F1)
# ---------------------------------------------------------------------------

def test_a_key_the_schema_forbids_is_refused():
    """The linter really does reject an undeclared key.

    Without this, the two scenarios above could both pass against a linter
    that had quietly stopped enforcing `additionalProperties`, and the whole
    file would be asserting nothing.
    """
    with tempfile.TemporaryDirectory() as raw:
        project = _project(Path(raw))
        manifest = project / ".compass" / "work" / "sample" / "manifest.yml"

        code, out = _run(project, "issue", "lint", "--issue", "sample")
        assert code == 0, f"the fixture manifest does not lint clean:\n{out}"

        manifest.write_text(manifest.read_text(encoding="utf-8")
                            + "note: an undeclared key\n", encoding="utf-8")
        code, out = _run(project, "issue", "lint", "--issue", "sample")

    assert code != 0, (
        "an undeclared key passed `compass issue lint`. The schema's "
        "additionalProperties: false is what makes the scenarios above "
        "meaningful, and it is not being enforced")
    assert "note" in out, (
        f"the lint failed but did not name the offending key:\n{out[-300:]}")
