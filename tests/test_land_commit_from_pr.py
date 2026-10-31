"""An issue records its pull request, and `land_commit` follows the merge.

The repository squash-merges pull requests, so the commit `ship-commit`
records never reaches the default branch. `compass issue link set --pr`
records the pull request and, once it is merged, moves `land_commit` to the
merge commit `gh pr view` reports. `compass check` reports a `land_commit`
that origin's default branch does not reach, as advice.

Every test runs the real CLI against a fake `gh` (tests/fake_gh.py).

Scenario ids: `TRC-LC1` to `TRC-LC4` (issue `land-commit-from-merged-pr`).
"""
from __future__ import annotations

import json

from test_github_label_sync import FakeGh, edit_manifest, make_issue, run  # noqa: F401
from test_github_label_sync import gh  # noqa: F401  (fixture)
from test_quick_fix_verbs import _git, _manifest, repo  # noqa: F401  (fixture)

SLUG = "sync-me"
PR_KEY = "acme/widgets#7"
CHECK = "land-commit-on-default-branch"


def _commit(root, name):
    (root / name).write_text(name + "\n")
    _git(root, "add", name)
    _git(root, "commit", "-q", "-m", name)
    return _git(root, "rev-parse", "HEAD")


def _landed(root, gh, land_commit):
    """A landed issue in a project whose origin is acme/widgets on github.com."""
    make_issue(root, gh, labels="infra")
    _git(root, "remote", "add", "origin", "https://github.com/acme/widgets.git")

    def landed(data):
        data["status"] = "done"
        data["close_reason"] = "completed"
        data["land_commit"] = land_commit
    edit_manifest(root, landed)


def _set_pr(gh, value, key=PR_KEY):
    state = gh.state()
    state.setdefault("prs", {})[key] = value
    (gh.dir / "state.json").write_text(json.dumps(state))


def _link_pr(root, gh, target="7"):
    return run(root, gh, "issue", "link", "set", f"--pr={target}", "--issue", SLUG)


def _default_branch(root, commit):
    """Make `commit` the tip of origin's default branch, as a clone records it."""
    _git(root, "update-ref", "refs/remotes/origin/main", commit)
    _git(root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")


def _check_row(root, gh):
    result = run(root, gh, "check", "--issue", SLUG, "--json")
    data = json.loads(result.stdout)
    rows = [c for c in data["checks"] if c["name"] == CHECK]
    return data, rows


def test_trc_lc1_a_merged_pr_moves_land_commit_to_its_merge_commit(repo, gh):
    _git(repo, "checkout", "-q", "-b", "work")
    local = _commit(repo, "work.txt")
    _git(repo, "checkout", "-q", "-")
    merged = _commit(repo, "squashed.txt")
    _landed(repo, gh, local)
    _set_pr(gh, {"number": 7, "state": "MERGED", "url": "https://github.com/acme/widgets/pull/7",
                 "mergeCommit": {"oid": merged}})

    result = _link_pr(repo, gh)

    assert result.returncode == 0, result.stdout + result.stderr
    data = _manifest(repo, SLUG)
    assert data["pull_request"] == {"repo": "acme/widgets", "number": 7}
    assert data["land_commit"] == merged
    assert local[:8] in result.stdout and merged[:8] in result.stdout
    views = [c for c in gh.calls() if c[:2] == ["pr", "view"]]
    assert views and views[0][2:5] == ["7", "--repo", "acme/widgets"]
    lint = run(repo, gh, "issue", "lint", "--issue", SLUG)
    assert "pull_request" not in lint.stdout + lint.stderr


def test_trc_lc2_an_open_pr_records_the_link_only(repo, gh):
    local = _git(repo, "rev-parse", "HEAD")
    _landed(repo, gh, local)
    _set_pr(gh, {"number": 7, "state": "OPEN", "url": "https://github.com/acme/widgets/pull/7",
                 "mergeCommit": None})

    result = _link_pr(repo, gh, "https://github.com/acme/widgets/pull/7")

    assert result.returncode == 0, result.stdout + result.stderr
    data = _manifest(repo, SLUG)
    assert data["pull_request"] == {"repo": "acme/widgets", "number": 7}
    assert data["land_commit"] == local
    assert "not merged" in result.stdout


def test_trc_lc2_an_issue_not_landed_gets_no_land_commit(repo, gh):
    make_issue(repo, gh, labels="infra")
    merged = _git(repo, "rev-parse", "HEAD")
    _set_pr(gh, {"number": 7, "state": "MERGED", "url": "https://github.com/acme/widgets/pull/7",
                 "mergeCommit": {"oid": merged}})

    result = _link_pr(repo, gh, "acme/widgets#7")

    assert result.returncode == 0, result.stdout + result.stderr
    data = _manifest(repo, SLUG)
    assert data["pull_request"] == {"repo": "acme/widgets", "number": 7}
    assert "land_commit" not in data
    assert "has not landed" in result.stdout


def test_trc_lc3_a_land_commit_off_the_default_branch_is_advice(repo, gh):
    main = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "work")
    local = _commit(repo, "work.txt")
    _landed(repo, gh, local)
    _default_branch(repo, main)

    data, rows = _check_row(repo, gh)

    assert [r["status"] for r in rows] == ["advisory"]
    assert local[:12] in rows[0]["detail"]
    assert "origin/main" in rows[0]["detail"]
    assert "compass issue link set --pr" in rows[0]["detail"]
    assert data["advisory"] >= 1


def test_trc_lc3_a_land_commit_on_the_default_branch_passes(repo, gh):
    _git(repo, "checkout", "-q", "-b", "work")
    local = _commit(repo, "work.txt")
    _landed(repo, gh, local)
    _default_branch(repo, local)

    _data, rows = _check_row(repo, gh)

    assert [r["status"] for r in rows] == ["pass"]


def test_trc_lc3_no_row_without_a_default_branch_or_a_landing(repo, gh):
    """No origin default branch, or an issue in flight: nothing to judge, no row."""
    local = _git(repo, "rev-parse", "HEAD")
    _landed(repo, gh, local)
    assert _check_row(repo, gh)[1] == []

    _default_branch(repo, local)
    edit_manifest(repo, lambda d: [d.pop(k) for k in ("status", "close_reason")])
    assert _check_row(repo, gh)[1] == []


def test_trc_lc4_a_pr_gh_cannot_read_writes_nothing(repo, gh):
    local = _git(repo, "rev-parse", "HEAD")
    _landed(repo, gh, local)
    before = _manifest(repo, SLUG)

    result = _link_pr(repo, gh, "acme/widgets#99")

    assert result.returncode != 0
    assert "Nothing was written" in result.stdout + result.stderr
    assert _manifest(repo, SLUG) == before


def test_trc_lc4_a_value_that_is_not_a_pr_writes_nothing(repo, gh):
    local = _git(repo, "rev-parse", "HEAD")
    _landed(repo, gh, local)
    before = _manifest(repo, SLUG)

    for target in ("acme/widgets", "https://github.com/acme/widgets/issues/7", "-3"):
        result = _link_pr(repo, gh, target)
        assert result.returncode != 0, target
        assert "Nothing was written" in result.stdout + result.stderr, target
    assert _manifest(repo, SLUG) == before
    assert not [c for c in gh.calls() if c[:2] == ["pr", "view"]]


def test_trc_lc4_neither_target_is_refused(repo, gh):
    make_issue(repo, gh, labels="infra")
    result = run(repo, gh, "issue", "link", "set", "--issue", SLUG)
    assert result.returncode != 0
    assert "--github" in result.stdout + result.stderr
