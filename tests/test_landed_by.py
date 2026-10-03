"""An issue delivered through another issue can say so, checkably.

`landed_by:` moves the claim to another record; it does not waive it. Six of
the nine scenarios prove the relaxation applies only when that record
exists.

Six issues sat as `abandoned` with an empty record and had actually been
delivered - the fix arrived through a different issue. `abandoned` was the only
status that did not lie about the record, so it lied about the outcome instead,
in the one place `compass retro` reads to judge whether assessment is drifting.

Scenario ids: DEL-A1..A2, B1..B5, C1..C2 in
no-status-for-work-done-elsewhere/acceptance-criteria.md
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# The archive these tests read: the tracked sample, or this checkout's own
# with COMPASS_FULL_ARCHIVE=1 (tests/archive.py).
sys.path.insert(0, str(REPO_ROOT / "tests"))
from archive import archive_root  # noqa: E402
CLI = REPO_ROOT / "cli" / "compass"

_FULL_RECORD = {
    "scenarios": [{"id": "X-1", "title": "s", "intent": "INT-1",
                   "tests": ["tests/test_landed_by.py"]}],
    "evidence": [{"id": "EV-T", "type": "test-run", "path": "evidence/green.json"}],
}


def _issue(root, slug, *, status="landed", record=False, landed_by=None,
           delivered=None):
    d = root / ".compass" / "work" / slug
    d.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "2.0", "task": slug, "created": "2026-01-01",
        "status": status,
        "assessment": {"risk": "contained", "familiarity": "greenfield",
                       "size": "small", "goal": "delivery"},
        "delivery_approach": "quick-fix",
        "stages": {"assess": "full"},
        "evidence": [], "gates": [], "scenarios": [], "changed_files": [],
        "follow_ups": [],
    }
    if record:
        manifest.update(_FULL_RECORD)
        ev = d / "evidence"
        ev.mkdir(exist_ok=True)
        (ev / "green.json").write_text('{"exit_code": 0, "passed": true}')
    if landed_by:
        manifest["landed_by"] = landed_by
    if delivered:
        manifest["delivered"] = list(delivered)
    (d / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    return d


def _project(tmp_path):
    (tmp_path / ".compass").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    return tmp_path


def _check(project, slug):
    """`compass check --verbose`.

    Verbose because the default view shows three failures and then "... and N
    more - run with --verbose". That truncation is the existing convention for
    every check, so asserting against the short view would be testing the
    truncation rather than the behaviour.
    """
    return subprocess.run(
        [sys.executable, str(CLI), "check", "--issue", slug, "--verbose"],
        cwd=str(project), capture_output=True, text=True, timeout=120)


# ---------------------------------------------------------------------------
# Group A - the pointer works, and only when it is there
# ---------------------------------------------------------------------------

def test_del_a1_a_landed_issue_with_a_pointer_passes(tmp_path):
    """DEL-A1: the record is somewhere else, and check agrees."""
    p = _project(tmp_path)
    _issue(p, "doer", record=True, delivered=["absorbed"])
    _issue(p, "absorbed", landed_by="doer")

    run = _check(p, "absorbed")
    combined = run.stdout + run.stderr
    assert run.returncode == 0, combined
    assert "doer" in combined, (
        "the report does not say which issue carries the record:\n" + combined)


def test_del_a2_the_same_issue_without_the_pointer_still_fails(tmp_path):
    """DEL-A2: the control, and the one that matters most.

    Without it, a relaxation that fired unconditionally would satisfy DEL-A1
    while waiving the record guardrail for every landed issue in the archive.
    """
    p = _project(tmp_path)
    _issue(p, "absorbed")

    run = _check(p, "absorbed")
    assert run.returncode != 0, (
        "an empty landed record passed with no pointer - the relaxation is "
        "firing unconditionally:\n" + run.stdout + run.stderr)
    assert "scenario" in (run.stdout + run.stderr).lower()


# ---------------------------------------------------------------------------
# Group B - the pointer is a claim, and claims are checked
# ---------------------------------------------------------------------------

def test_del_b1_a_pointer_at_nothing_fails(tmp_path):
    p = _project(tmp_path)
    _issue(p, "absorbed", landed_by="no-such-issue")

    run = _check(p, "absorbed")
    combined = run.stdout + run.stderr
    assert run.returncode != 0
    assert "no-such-issue" in combined, combined


def test_del_b2_a_pointer_at_an_unlanded_issue_fails(tmp_path):
    """A pointer at an active issue is a promise, not a record.

    Two issues pointing at each other while neither has landed would let a
    pair of empty records vouch for one another.
    """
    p = _project(tmp_path)
    _issue(p, "doer", status="active", record=True, delivered=["absorbed"])
    _issue(p, "absorbed", landed_by="doer")

    run = _check(p, "absorbed")
    combined = run.stdout + run.stderr
    assert run.returncode != 0
    assert "landed" in combined.lower(), combined


def test_del_b3_a_pointer_at_an_empty_issue_fails(tmp_path):
    """A points at B, B is empty too."""
    p = _project(tmp_path)
    _issue(p, "doer", delivered=["absorbed"])          # landed, but no record
    _issue(p, "absorbed", landed_by="doer")

    run = _check(p, "absorbed")
    combined = run.stdout + run.stderr
    assert run.returncode != 0
    assert "doer" in combined, combined


def test_del_b5_a_pointer_the_named_issue_does_not_acknowledge_fails(tmp_path):
    """DEL-B5: the link is two-way, or it is not a link.

    Without this, any issue could name any landed issue and pass - the named
    one is landed and carries a record, so every check clears. The relaxation
    would be available to anything for the price of typing a slug that exists.
    """
    p = _project(tmp_path)
    _issue(p, "doer", record=True)                     # no `delivered:`
    _issue(p, "absorbed", landed_by="doer")

    run = _check(p, "absorbed")
    combined = run.stdout + run.stderr
    assert run.returncode != 0, (
        "a pointer the named issue does not acknowledge was accepted:\n"
        + combined)
    assert "one-way" in combined.lower() or "does not name" in combined.lower(), \
        combined


def test_del_b4_a_pointer_is_inert_below_landed(tmp_path):
    """DEL-B4: on a queued or active issue it does nothing, and says so.

    A field that silently does nothing at some statuses is a trap - somebody
    writes it, sees no complaint, and assumes it is working.
    """
    p = _project(tmp_path)
    _issue(p, "doer", record=True, delivered=["wip"])
    _issue(p, "wip", status="active", landed_by="doer")

    run = _check(p, "wip")
    combined = run.stdout + run.stderr
    assert "no effect" in combined.lower() or "only applies" in combined.lower(), (
        "the pointer is silently inert at this status:\n" + combined)


# ---------------------------------------------------------------------------
# The widening - a list, and two kinds of entry
#
# The six records take three forms: another issue, an ordinary commit,
# several parents. One was decided against. These scenarios are the shape
# the data actually has.
# ---------------------------------------------------------------------------

def test_del_a3_every_entry_in_the_list_is_checked(tmp_path):
    """DEL-A3: a list, and one bad entry fails the whole claim.

    `the-human-review-pack` was delivered by three child issues. Picking one of
    the three would be a record that is true and incomplete - and a check that
    stopped at the first good entry would let the other two say anything.
    """
    p = _project(tmp_path)
    _issue(p, "one", record=True, delivered=["absorbed"])
    _issue(p, "two", record=True, delivered=["absorbed"])
    _issue(p, "three", status="active", record=True, delivered=["absorbed"])
    _issue(p, "absorbed", landed_by=[{"issue": "one"}, {"issue": "two"},
                                     {"issue": "three"}])

    run = _check(p, "absorbed")
    combined = run.stdout + run.stderr
    assert run.returncode != 0, (
        "a list containing an unlanded issue passed - the check stops at the "
        "first good entry:\n" + combined)
    # Asserted on the REASON, not on the slug appearing. Stringifying the whole
    # list into an error message would put "three" in the output by accident.
    assert "has not landed" in combined, (
        "the failure does not say WHY the entry is bad, so it could be any "
        "error that happens to quote the list:\n" + combined)


def test_del_d1_a_commit_entry_resolves(tmp_path):
    """DEL-D1: the common case - a commit did it, no issue was ever opened."""
    p, sha = _git_project(tmp_path)
    _issue(p, "absorbed", landed_by=[
        {"commit": sha, "what": "moved the record name onto the scenario "
                                "binding"}])

    run = _check(p, "absorbed")
    assert run.returncode == 0, run.stdout + run.stderr


def test_del_d2_a_commit_that_does_not_resolve_fails(tmp_path):
    p, _sha = _git_project(tmp_path)
    _issue(p, "absorbed", landed_by=[
        {"commit": "0000000000000000000000000000000000000000",
         "what": "something that never happened"}])

    run = _check(p, "absorbed")
    combined = run.stdout + run.stderr
    assert run.returncode != 0
    assert "commit" in combined.lower() and "could not" in combined.lower(), (
        "the failure does not say it could not find the commit - quoting the "
        "sha back is something a stringified list does by accident:\n"
        + combined)


def test_del_d3_a_commit_with_no_explanation_fails(tmp_path):
    """A bare sha is a reference nobody can act on.

    The point of the record is that a reader learns what happened without
    running `git show` - and on a tree cloned without that history, they
    cannot run it at all.
    """
    p, sha = _git_project(tmp_path)
    _issue(p, "absorbed", landed_by=[{"commit": sha}])

    run = _check(p, "absorbed")
    combined = run.stdout + run.stderr
    assert run.returncode != 0
    assert "what" in combined.lower(), combined


def test_del_d4_without_git_the_commit_form_declines(tmp_path, monkeypatch):
    """A check that passes because it could not look is not a check."""
    from compass_pkg import landed_by as mod

    ok, detail = mod.landed_by_holds(
        {"status": "landed", "task": "absorbed",
         "landed_by": [{"commit": "deadbee", "what": "did a thing"}]},
        str(tmp_path), git_reader=lambda sha, cwd: None)

    assert not ok, "an unresolvable commit passed when git was unreachable"
    assert "git" in detail.lower(), detail


def _git_project(tmp_path):
    """A project that is also a git repository, with one commit.

    Resolved against the PROJECT's history, not Compass's - an adopter's
    `landed_by` names a commit in their repository, and testing against this
    one would prove the wrong thing.
    """
    import subprocess

    p = _project(tmp_path)
    run = lambda *a: subprocess.run(a, cwd=str(p), capture_output=True, text=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@example.invalid")
    run("git", "config", "user.name", "t")
    (p / "seed.txt").write_text("seed\n")
    run("git", "add", "-A")
    run("git", "commit", "-q", "-m", "the commit that fixed it")
    sha = run("git", "rev-parse", "HEAD").stdout.strip()
    return p, sha


# ---------------------------------------------------------------------------
# Group C - the archive itself
#
# `.compass/work/` is gitignored, so these SKIP with a reason on a clean
# checkout rather than passing on an empty tree. A check that passes because
# it could not look is not a check.
# ---------------------------------------------------------------------------

ARCHIVE = archive_root() / ".compass" / "work"


def _archive_or_skip():
    if not ARCHIVE.is_dir() or not any(ARCHIVE.iterdir()):
        pytest.skip(".compass/work/ is not in this checkout (it is gitignored), "
                    "so there is no archive to assert on")
    return ARCHIVE


def _spine(slug):
    return yaml.safe_load((ARCHIVE / slug / "manifest.yml").read_text())


def test_del_c1_the_delivered_issues_are_landed_with_a_pointer():
    """DEL-C1: the point of the exercise.

    Shipping the mechanism and leaving the records wrong would be building a
    tool and not using it - and the wrong data would stay in `compass retro`,
    which is the reason the issue exists.
    """
    _archive_or_skip()
    for slug in ("the-human-review-pack",
                 "evaluator-prints-code-before-meaning",
                 "tdd-green-scenario-overwrites-the-record",
                 "landed-issues-trace-rot-is-unchecked"):
        manifest = _spine(slug)
        assert manifest.get("status") == "landed", (
            "%s is %r - it was delivered, and `abandoned` reads as gave up"
            % (slug, manifest.get("status")))
        assert manifest.get("landed_by"), (
            "%s is landed with no record of its own and no `landed_by` to say "
            "where the record is" % slug)


def test_del_c3_an_issue_that_was_decided_against_stays_abandoned():
    """DEL-C3: the control on DEL-C1, and not a formality.

    `publish-the-archive` was not delivered - the maintainer chose not to
    publish. `abandoned` is exactly right for it. A sweep that moved all six
    would have replaced six wrong data points with one wrong data point
    pointing the other way, which is not an improvement.
    """
    _archive_or_skip()
    manifest = _spine("publish-the-archive")
    assert manifest.get("status") == "abandoned", (
        "publish-the-archive is %r - the work was deliberately not done, and "
        "that is what abandoned means" % manifest.get("status"))
    assert not manifest.get("landed_by"), (
        "publish-the-archive carries a `landed_by` - nothing delivered it")


def test_del_c2_retro_does_not_count_the_delivered_ones_as_abandoned():
    """DEL-C2: the mechanism `compass retro` reads is now telling the truth."""
    _archive_or_skip()
    run = subprocess.run([sys.executable, str(CLI), "retro"],
                         cwd=str(archive_root()), capture_output=True, text=True,
                         timeout=180)
    combined = run.stdout + run.stderr
    for slug in ("the-human-review-pack",
                 "evaluator-prints-code-before-meaning"):
        assert not _abandoned_in(combined, slug), (
            "%s is still being counted as abandoned by retro:\n%s"
            % (slug, combined[:2000]))


def _abandoned_in(text, slug):
    """Is `slug` named on a line that also says abandoned?"""
    return any(slug in line and "abandon" in line.lower()
               for line in text.splitlines())


def test_del_a4_an_absorbed_issue_that_was_never_assessed_still_lints(tmp_path):
    """DEL-A4: `assessment` is not demanded of an issue delivered elsewhere.

    The schema needs `assessment` at the root, because every issue that goes
    through the pipeline is assessed. An issue whose work was absorbed by
    another never entered the pipeline - so needing it asks for a record of a
    judgement nobody made, and the only way to satisfy it is to invent one.

    That is the same argument as the rest of this issue: the claim moves to the
    issue that has the record. `artifact-filenames-rename-slice` is the real
    case - split off, absorbed by `the-vocabulary-rename`, never assessed.
    """
    p = _project(tmp_path)
    _issue(p, "doer", record=True, delivered=["absorbed"])

    d = p / ".compass" / "work" / "absorbed"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "task": "absorbed", "created": "2026-01-01",
        "status": "landed", "landed_by": [{"issue": "doer"}],
    }, sort_keys=False))

    run = subprocess.run(
        [sys.executable, str(CLI), "issue", "lint", "--issue", "absorbed"],
        cwd=str(p), capture_output=True, text=True, timeout=120)
    combined = run.stdout + run.stderr
    assert run.returncode == 0, (
        "an issue delivered elsewhere was required to carry an assessment it "
        "never made:\n" + combined)


def test_del_a4b_an_ordinary_issue_still_needs_its_assessment(tmp_path):
    """The control. Without it, dropping the requirement outright would
    satisfy DEL-A4 while letting every issue skip assessment."""
    p = _project(tmp_path)
    d = p / ".compass" / "work" / "ordinary"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "task": "ordinary", "created": "2026-01-01",
        "status": "active",
    }, sort_keys=False))

    run = subprocess.run(
        [sys.executable, str(CLI), "issue", "lint", "--issue", "ordinary"],
        cwd=str(p), capture_output=True, text=True, timeout=120)
    assert run.returncode != 0, (
        "an issue with no assessment and no landed_by passed the lint - the "
        "requirement has been dropped rather than moved")
    assert "assessment" in (run.stdout + run.stderr).lower()
