"""An issue raised from another issue names its parent and where it was found.

Most of Compass's defects are found while landing or reviewing other work,
and only private prose recorded it, so Compass could not say how much the `verify`
stage catches before an issue lands. An issue now carries `raised_by` (parent and
`found_at`), and `compass retro --lineage` counts it.

Scenario ids: LN-1, LN-2, LN-3 and LN-5 (issue `lineage`).
"""
from __future__ import annotations

from test_quick_fix_verbs import _manifest, _run, repo  # noqa: F401


def _start(root, slug, extra=()):
    return _run(root, "quick-fix", "start", slug,
                "--risk", "trivial - one line", "--familiarity",
                "brownfield-mapped - the file and its test exist",
                "--size", "atomic - one line", "--intent", "it works",
                "--scenario", "Given a line, when read, then it is right.",
                "--scenario-id", "TRC-001", "--test", "tests/test_x.py",
                *extra)


def _raised(root, slug, parent, found_at="review"):
    return _start(root, slug, extra=["--raised-by", parent, "--found-at", found_at])


# --- LN-1: the parent is recorded ---------------------------------------------

def test_ln_1_quick_fix_start_records_the_parent(repo):
    assert _start(repo, "parent-fix").returncode == 0
    result = _raised(repo, "child-fix", "parent-fix")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo, "child-fix")["raised_by"] == {
        "issue": "parent-fix", "found_at": "review"}
    lint = _run(repo, "issue", "lint", "--issue", "child-fix")
    assert lint.returncode == 0, lint.stdout + lint.stderr


def test_ln_1_issue_raised_by_records_the_parent_on_an_existing_issue(repo):
    assert _start(repo, "parent-fix").returncode == 0
    assert _start(repo, "later-fix").returncode == 0
    result = _run(repo, "issue", "raised-by", "parent-fix", "--found-at",
                  "after-landing", "--issue", "later-fix")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo, "later-fix")["raised_by"] == {
        "issue": "parent-fix", "found_at": "after-landing"}


# --- LN-2: refusals --------------------------------------------------------------

def test_ln_2_an_unknown_parent_is_refused_and_nothing_is_created(repo):
    result = _raised(repo, "orphan-fix", "no-such-issue")
    assert result.returncode != 0
    assert "no-such-issue" in result.stderr, result.stderr
    assert not (repo / ".compass" / "work" / "orphan-fix").exists()


def test_ln_2_an_unknown_place_is_refused(repo):
    assert _start(repo, "parent-fix").returncode == 0
    result = _raised(repo, "child-fix", "parent-fix", found_at="lunch")
    assert result.returncode != 0
    assert "after-landing" in result.stderr, result.stderr
    assert not (repo / ".compass" / "work" / "child-fix").exists()


def test_ln_2_one_flag_without_the_other_is_refused(repo):
    assert _start(repo, "parent-fix").returncode == 0
    result = _start(repo, "child-fix", extra=["--raised-by", "parent-fix"])
    assert result.returncode != 0
    assert "--found-at" in result.stderr, result.stderr
    assert not (repo / ".compass" / "work" / "child-fix").exists()


def test_ln_2_lint_reports_an_unknown_place(repo):
    import yaml
    assert _start(repo, "parent-fix").returncode == 0
    assert _raised(repo, "child-fix", "parent-fix").returncode == 0
    path = repo / ".compass" / "work" / "child-fix" / "manifest.yml"
    data = yaml.safe_load(path.read_text())
    data["raised_by"]["found_at"] = "lunch"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    lint = _run(repo, "issue", "lint", "--issue", "child-fix")
    assert lint.returncode != 0
    assert "lunch" in lint.stdout + lint.stderr


# --- LN-3: the report ------------------------------------------------------------

def test_ln_3_retro_counts_before_and_after_landing(repo):
    assert _start(repo, "root-fix").returncode == 0
    for slug in ("a-fix", "b-fix", "c-fix"):
        assert _raised(repo, slug, "root-fix", "review").returncode == 0
    assert _raised(repo, "d-fix", "root-fix", "after-landing").returncode == 0
    report = _run(repo, "retro", "--lineage")
    assert report.returncode == 0, report.stderr
    out = report.stdout
    assert "found before the parent landed: 3" in out, out
    assert "found after the parent landed: 1" in out, out
    assert "review 3" in out and "after-landing 1" in out, out
    assert "root-fix (4)" in out, out


def test_ln_3_retro_names_a_chain_of_three(repo):
    assert _start(repo, "a-fix").returncode == 0
    assert _raised(repo, "b-fix", "a-fix").returncode == 0
    assert _raised(repo, "c-fix", "b-fix").returncode == 0
    out = _run(repo, "retro", "--lineage").stdout
    assert "a-fix -> b-fix -> c-fix" in out, out


def test_ln_3_retro_with_no_raised_issue_says_so(repo):
    assert _start(repo, "a-fix").returncode == 0
    report = _run(repo, "retro", "--lineage")
    assert report.returncode == 0
    assert "no issue records where it was raised" in report.stdout, report.stdout


# --- LN-5: the third in a chain is told -------------------------------------------

def test_ln_5_the_third_issue_in_a_chain_names_the_root_and_s14(repo):
    assert _start(repo, "a-fix").returncode == 0
    second = _raised(repo, "b-fix", "a-fix")
    assert "S14" not in second.stdout + second.stderr
    third = _raised(repo, "c-fix", "b-fix")
    assert third.returncode == 0, third.stderr
    said = third.stdout + third.stderr
    assert "a-fix" in said and "S14" in said, said


def test_ln_5_a_loop_in_raised_by_does_not_hang(repo):
    import yaml
    assert _start(repo, "a-fix").returncode == 0
    assert _raised(repo, "b-fix", "a-fix").returncode == 0
    path = repo / ".compass" / "work" / "a-fix" / "manifest.yml"
    data = yaml.safe_load(path.read_text())
    data["raised_by"] = {"issue": "b-fix", "found_at": "review"}
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    report = _run(repo, "retro", "--lineage")
    assert report.returncode == 0, report.stderr


def test_ln_2_the_built_in_lint_reports_a_bad_place_without_jsonschema():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))
    from compass_pkg.policy import raised_by_errors
    assert raised_by_errors({}) == []
    assert raised_by_errors({"raised_by": {"issue": "a", "found_at": "review"}}) == []
    assert "lunch" in raised_by_errors({"raised_by": {"issue": "a", "found_at": "lunch"}})[0]
    assert raised_by_errors({"raised_by": "a"})


def test_ln_2_an_issue_cannot_be_raised_from_itself(repo):
    assert _start(repo, "b-fix").returncode == 0
    result = _run(repo, "issue", "raised-by", "b-fix", "--found-at", "ci",
                  "--issue", "b-fix")
    assert result.returncode != 0
    assert "raised_by" not in _manifest(repo, "b-fix")


def test_ln_3_a_bad_place_is_not_counted_as_before_landing(repo):
    import yaml
    assert _start(repo, "root-fix").returncode == 0
    assert _raised(repo, "a-fix", "root-fix", "review").returncode == 0
    assert _raised(repo, "b-fix", "root-fix", "after-landing").returncode == 0
    assert _raised(repo, "c-fix", "root-fix", "review").returncode == 0
    path = repo / ".compass" / "work" / "c-fix" / "manifest.yml"
    data = yaml.safe_load(path.read_text())
    data["raised_by"]["found_at"] = "lunch"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    out = _run(repo, "retro", "--lineage").stdout
    assert "found before the parent landed: 1" in out, out
