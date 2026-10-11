"""Every reader asks the resolver where a document is.

Scenario group C of `docs-compass-artifacts`.

A document that has moved is not found by a reader that builds its own path to
it, and the failure is silent: the reader gets "no such file" and reports the
document as absent, which most checks treat as "nothing to check" and pass on.
That silent pass is the most expensive failure this group guards against,
and `TRC-C5` pins the worst instance - `dod-evidence-typed` goes GREEN on
every issue in a repository if the verification report moves and its
reader does not.

The class test (TRC-C3) is the one that matters most. Fixing thirteen
readers one at a time and calling the job done is exactly the failure this
group exists to prevent, so the guard enumerates the document kinds and
fails on any direct path join to one of them.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI_PKG = ROOT / "cli" / "compass_pkg"
COMPASS_CLI = ROOT / "cli" / "compass"

sys.path.insert(0, str(ROOT / "cli"))
from compass_pkg import core  # noqa: E402


#: The modules that read an issue's documents.
READER_MODULES = [
    "analyze.py", "checks.py", "check_cmd.py", "policy.py", "receipt.py",
    "next_cmd.py", "artifact_cmd.py", "bdd.py", "flow.py", "routing.py",
    "ingest.py", "borrowed_docs.py", "migrate.py", "verb_help.py",
]

#: `migrate.py` is the one module that MUST build its own paths: it is what
#: moves a document from beside the manifest to `docs/compass/`, so it has to
#: name both ends. Exempting it is not a hole - it is the only writer of the
#: registry entries every other module then reads.
BUILDS_ITS_OWN_PATHS = {"migrate.py"}


def _document_filenames():
    """Every human document the framework writes, from the shipped templates.

    Derived rather than listed. A hand-written list is the thing that goes
    stale when a template is added, and a stale list means the next reader to
    bypass the resolver does so unobserved.
    """
    machine_state = {"devlog.md", "pull-request-body.md"}
    return {p.name for p in (ROOT / "templates").glob("*.md")} - machine_state


# --- `TRC-C2` and `TRC-C3` -------------------------------------------------------

#: A path built by joining a directory to a document filename, rather than by
#: asking the resolver. Both spellings a reader reaches for.
_DIRECT_JOIN = re.compile(
    r"""os\.path\.join\(\s*[A-Za-z_][A-Za-z0-9_]*\s*,\s*["']([a-z0-9-]+\.md)["']"""
)


def _direct_joins():
    hits = []
    for name in READER_MODULES:
        if name in BUILDS_ITS_OWN_PATHS:
            continue
        path = CLI_PKG / name
        if not path.is_file():
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for doc in _DIRECT_JOIN.findall(line):
                if doc in _document_filenames():
                    hits.append((name, n, doc))
    return hits


def test_trc_c2_no_reader_builds_its_own_path_to_a_document():
    """Every reader in the list, and anything else of the same shape."""
    hits = _direct_joins()
    assert not hits, (
        "CLI readers build their own path to a document instead of asking "
        "the resolver, so each one stops finding it the moment it moves:\n  "
        + "\n  ".join(f"{m}:{n} -> {d}" for m, n, d in hits)
        + "\n\nUse artifact_path(task_dir, <name>) or "
          "resolve_artifact(task_dir, <kind>).")


def test_trc_c3_a_new_bypasser_is_named_by_the_test(tmp_path):
    """The guard above is only worth having if it can fail.

    Written as a real check against a real file rather than as a claim: a
    module with a fresh direct join is placed in the reader list and the
    matcher must name it, the file and the kind.
    """
    fake = CLI_PKG / "_trc_c3_probe.py"
    fake.write_text(
        "import os\n\n\ndef read(task_dir):\n"
        "    return os.path.join(task_dir, 'technical-design.md')\n",
        encoding="utf-8")
    try:
        READER_MODULES.append("_trc_c3_probe.py")
        hits = _direct_joins()
    finally:
        READER_MODULES.remove("_trc_c3_probe.py")
        fake.unlink()
    assert ("_trc_c3_probe.py", 5, "technical-design.md") in hits, (
        f"a reader that builds its own path to technical-design.md was not "
        f"caught, so this guard would let the next one through: {hits}")


def test_trc_c3_the_document_list_is_not_empty_and_is_derived():
    """A guard over a derived set is only as good as the set.

    An empty or near-empty list would make every check in this file pass over
    nothing at all.
    """
    docs = _document_filenames()
    assert len(docs) >= 10, (
        f"only {len(docs)} document filenames derived from templates/ - the "
        f"derivation has broken and these checks are inspecting almost "
        f"nothing: {sorted(docs)}")
    for expected in ("technical-design.md", "acceptance-criteria.md",
                     "verification-report.md", "threat-model.md",
                     "rollback-plan.md", "intent.md"):
        assert expected in docs, (
            f"{expected} is not in the derived document set, so a reader "
            f"bypassing the resolver for it would not be caught")


def test_trc_c3_the_exemption_names_a_module_that_still_exists():
    """An exemption for a module that has been renamed exempts nothing, and
    the guard quietly widens."""
    missing = [m for m in sorted(BUILDS_ITS_OWN_PATHS)
               if not (CLI_PKG / m).is_file()]
    assert not missing, (
        f"BUILDS_ITS_OWN_PATHS names modules that no longer exist: {missing}")


# --- `TRC-C1`, C4, C5 ----------------------------------------------------------

def _relocated_issue(tmp_path, dod_line, slug="a-moved-issue",
                     created="2026-09-08", meets=()):
    """An issue whose verification report lives under docs/compass/.

    Everything the checks need is present and passing except whatever the
    caller puts in the Definition of Done, so a failure can only come from the
    DoD line under test.
    """
    task_dir = tmp_path / ".compass" / "work" / slug
    (task_dir / "evidence").mkdir(parents=True)
    docs = tmp_path / "docs" / "compass" / f"{created}-{slug}"
    docs.mkdir(parents=True)

    (docs / "verification-report.md").write_text(
        "# Verification report\n\n### Definition of Done\n\n"
        f"{dod_line}\n", encoding="utf-8")
    (task_dir / "evidence" / "green-MV-1.json").write_text(
        '{"command": "pytest -q", "scenario": "MV-1", "exit_code": 0, '
        '"passed": true, "attempts": 1, '
        '"timestamp": "2026-09-08T09:00:00+00:00", "log_excerpt": "1 passed"}',
        encoding="utf-8")

    rel = os.path.join("docs", "compass", f"{created}-{slug}",
                       "verification-report.md").replace(os.sep, "/")
    manifest = {
        "schema_version": "2.0", "issue": slug, "created": created,
        "status": "active",
        "assessment": {"risk": "trivial", "familiarity": "brownfield-mapped",
                       "size": "atomic", "goal": "delivery", "role": "engineer"},
        "delivery_approach": "express",
        "stages": {"assess": "full", "define": "light", "refine": "collapsed",
                   "plan": "collapsed", "breakdown": "skipped",
                   "implement": "full", "verify": "light", "ship": "light"},
        "artifacts": [{"id": "ART-VERIFICATION_REPORT",
                       "kind": "verification-report", "status": "draft",
                       "reason": "every issue carries one", "path": rel}],
        "evidence": [{"id": "EV-T-MV-1", "type": "test-run",
                      "path": "evidence/green-MV-1.json", "scenario": "MV-1",
                      **({"meets": list(meets)} if meets else {})}],
        "gates": [{"id": g, "status": "pending", "evidence": []} for g in
                  ("verify.correctness", "verify.governance",
                   "verify.traceability")],
        "scenarios": [{"id": "MV-1", "title": "it works", "intent": "INT-1",
                       "tests": ["tests/test_x.py::test_mv_1"]}],
        "changed_files": [], "claims": [], "follow_ups": [],
    }
    (task_dir / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    (tmp_path / ".compass" / "current-task").write_text(slug, encoding="utf-8")
    return task_dir, docs


def _check(project, slug="a-moved-issue"):
    # The issue page is written by the render after a command; this fixture wrote the
    # manifest by hand, so render it as that step would.
    subprocess.run([sys.executable, str(COMPASS_CLI), "issue", "render", "--issue", slug],
                   capture_output=True, text=True, timeout=120, cwd=str(project), check=True)
    return subprocess.run(
        [sys.executable, str(COMPASS_CLI), "check", "--issue", slug,
         "--verbose"],
        capture_output=True, text=True, timeout=120, cwd=str(project))


def test_trc_c1_a_reader_finds_a_relocated_document(tmp_path):
    """The resolver answers FOUND, at the registered path, for a document that
    is nowhere near the manifest."""
    task_dir, docs = _relocated_issue(tmp_path, "- [x] everything")
    state, found, reason = core.resolve_artifact(
        str(task_dir), "verification-report")
    assert state == core.FOUND, (
        f"the resolver answered {state} ({reason}) for a document that is on "
        f"disk under docs/compass/")
    assert os.path.samefile(found, docs / "verification-report.md"), (
        f"the resolver found {found}, not the registered document")


SHIPPED_DONE = ["dod-every-scenario-passes", "dod-suite-green", "dod-coverage-floor",
                "dod-no-lint-errors", "dod-traceability-intact", "dod-living-docs-updated",
                "dod-follow-ups-settled"]


def test_trc_c4_the_gate_that_reads_the_report_clears(tmp_path):
    """`compass check` on an issue whose report has moved. The items are met by
    records in the manifest, so the page is not what clears the gate."""
    _relocated_issue(tmp_path, "- [ ] a box nobody ticked", meets=SHIPPED_DONE)
    r = _check(tmp_path)
    assert "dod-evidence-typed" in r.stdout, (
        "the DoD check did not run at all:\n" + r.stdout[-1500:])
    assert r.returncode == 0, (
        "compass check fails on an issue whose verification report is "
        "registered under docs/compass/:\n" + r.stdout[-2000:])
    # The scenario asks the check to NAME the path it read, and it asks for a
    # reason: "the gate cleared" and "there was no file to object to" are the
    # same green line otherwise, and telling them apart is the whole of C5.
    dod = next(l for l in r.stdout.splitlines() if "dod-evidence-typed" in l)
    assert "docs/compass" in dod, (
        f"the DoD check cleared without saying which file it read, so a pass "
        f"here cannot be told from a pass on a report it never found:\n  {dod}")


def test_trc_c5_an_item_with_no_record_turns_the_check_red(tmp_path):
    """The expensive failure, pinned.

    An item with no record in the manifest fails the check, whatever the page
    says: a ticked box on a relocated report counts for nothing. The check has
    to fail *for the right reason*, naming the open item.
    """
    _relocated_issue(tmp_path, "- [x] somebody looked at the logs")
    r = _check(tmp_path)
    assert r.returncode != 0, (
        "compass check PASSED on a relocated report whose Definition of Done "
        "items have no record in the manifest:\n" + r.stdout[-2000:])
    assert "dod-evidence-typed" in r.stdout and "dod-every-scenario-passes" in r.stdout, (
        "the check failed, but not by naming the open item - so it may be "
        "failing for an unrelated reason:\n" + r.stdout[-2000:])


def test_trc_c5_the_same_items_met_by_records_pass(tmp_path):
    """The other half. Without it, a check that fails on everything would
    also satisfy the test above."""
    _relocated_issue(tmp_path, "- [ ] a box nobody ticked", meets=SHIPPED_DONE)
    r = _check(tmp_path)
    assert r.returncode == 0, (
        "a Definition of Done met by records that resolve was still rejected:\n"
        + r.stdout[-2000:])
