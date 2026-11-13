"""`compass issue link set --pr` reads the ship approval from the merged pull request.

Step 4 of #355 [Read the ship approval from the merged PR review]. After the
merge the command reads the pull request's reviews with `gh api --paginate
repos/<r>/pulls/<n>/reviews` and the login it reads as with `gh api user`,
before it writes anything. A reviewer counts when their latest
state-changing review at or before the merge is `APPROVED`, their account is
a `User`, and they are not the pull request's author. Each counting reviewer
becomes a `pr-approval` evidence record, which `compass check` reads without
calling `gh`.

Every test runs the real CLI against the fake `gh` (tests/fake_gh.py), so no
test reaches the network. The cases are the table in section 3.4 of the plan.
"""
from __future__ import annotations

import json
import subprocess
import sys

from test_issue_link import CLI, FakeGh, edit_manifest, make_issue, run  # noqa: F401
from test_issue_link import gh  # noqa: F401  (fixture)
from test_quick_fix_verbs import _git, _manifest, repo  # noqa: F401  (fixture)

SLUG = "sync-me"
KEY = "acme/widgets#7"
MERGED_AT = "2026-11-07T01:48:47Z"
AUTHOR = "author-dev"
CHECK = "ship-approval-present"


def _review(rid, login, state="APPROVED", at="2026-11-07T01:27:26Z", kind="User",
            commit="a" * 40):
    return {"id": rid, "state": state, "submitted_at": at, "commit_id": commit,
            "html_url": f"https://github.com/acme/widgets/pull/7#pullrequestreview-{rid}",
            "user": {"login": login, "type": kind}}


def _merged(root, gh, reviews, state="MERGED"):
    """A landed issue whose pull request acme/widgets#7 holds `reviews`."""
    make_issue(root, gh, labels="infra")
    _git(root, "remote", "add", "origin", "https://github.com/acme/widgets.git")
    head = _git(root, "rev-parse", "HEAD")

    def landed(data):
        data["status"] = "done"
        data["close_reason"] = "completed"
        data["land_commit"] = head
    edit_manifest(root, landed)
    s = gh.state()
    s.setdefault("prs", {})[KEY] = {
        "number": 7, "state": state, "url": "https://github.com/acme/widgets/pull/7",
        "mergeCommit": {"oid": "c" * 40} if state == "MERGED" else None,
        "mergedAt": MERGED_AT if state == "MERGED" else None,
        "author": {"login": AUTHOR, "is_bot": False}, "headRefOid": "b" * 40,
        "title": "not asked for"}
    s.setdefault("reviews", {})[KEY] = reviews
    s["login"] = "the-reader"
    (gh.dir / "state.json").write_text(json.dumps(s))


def _link(root, gh, mode="", present=True, fail=""):
    env = gh.env(mode, present)
    env["GH_FAKE_FAIL"] = fail
    return subprocess.run([sys.executable, str(CLI), "issue", "link", "set", "--pr=7",
                           "--issue", SLUG], cwd=root, capture_output=True, text=True,
                          env=env)


def _approvals(root):
    return [e for e in _manifest(root, SLUG).get("evidence") or []
            if e.get("type") == "pr-approval"]


def _check(root, gh):
    """The ship approval row of `compass check`, run with no `gh` on PATH."""
    result = run(root, gh, "check", "--issue", SLUG, "--json", present=False)
    rows = [c for c in json.loads(result.stdout)["checks"] if c["name"] == CHECK]
    return rows


def test_the_issue_owes_the_ship_approval(repo, gh):
    make_issue(repo, gh, labels="infra")
    assert "ship-approval" in _manifest(repo, SLUG)["evidence_required"]


def test_a_merged_pr_with_one_approval_writes_the_record(repo, gh):
    _merged(repo, gh, [_review(5809189576, "tidy-dev")])

    result = _link(repo, gh)

    assert result.returncode == 0, result.stdout + result.stderr
    [record] = _approvals(repo)
    read_at = record.pop("read_at")
    assert read_at.endswith("Z")
    generation = _manifest(repo, SLUG).get("generation")
    expected = {
        "id": "EV-PR-APPROVAL-1", "type": "pr-approval",
        "pull_request": {"repo": "acme/widgets", "number": 7},
        "review_id": 5809189576,
        "url": "https://github.com/acme/widgets/pull/7#pullrequestreview-5809189576",
        "approver": "tidy-dev", "pr_author": AUTHOR, "decision": "approved",
        "timestamp": "2026-11-07T01:27:26Z", "reviewed_commit": "a" * 40,
        "head_commit": "b" * 40, "merge_commit": "c" * 40, "merged_at": MERGED_AT,
        "read_as": "the-reader", "via": "github", "issue": SLUG}
    if generation is not None:
        expected["generation"] = generation
    assert record == expected
    pr = _manifest(repo, SLUG)["pull_request"]
    assert pr == {"repo": "acme/widgets", "number": 7, "merged_at": MERGED_AT,
                  "merge_commit": "c" * 40, "author": AUTHOR}
    assert ("Ship approval: tidy-dev, review 5809189576, recorded as EV-PR-APPROVAL-1."
            in result.stdout)
    calls = gh.calls()
    assert calls[0][:2] == ["pr", "view"]
    assert calls[0][calls[0].index("--json") + 1] == (
        "number,state,mergeCommit,mergedAt,author,headRefOid,url")
    assert ["api", "--paginate", "repos/acme/widgets/pulls/7/reviews"] == calls[1][:3]
    assert calls[2][:2] == ["api", "user"]
    assert len(calls) == 3
    lint = run(repo, gh, "issue", "lint", "--issue", SLUG)
    assert "pull_request" not in lint.stdout + lint.stderr

    rows = _check(repo, gh)
    assert [r["status"] for r in rows] == ["pass"], rows
    assert "tidy-dev" in rows[0]["detail"] and "EV-PR-APPROVAL-1" in rows[0]["detail"]
    assert "a" * 12 in rows[0]["detail"]   # the approved commit is not the merged head


def test_compass_check_makes_no_gh_call(repo, gh):
    _merged(repo, gh, [_review(1, "tidy-dev")])
    assert _link(repo, gh).returncode == 0
    before = len(gh.calls())

    result = run(repo, gh, "check", "--issue", SLUG, "--json")

    assert result.stdout
    assert len(gh.calls()) == before


def test_a_second_run_writes_nothing_new(repo, gh):
    _merged(repo, gh, [_review(1, "tidy-dev"), _review(2, "other-dev")])
    assert _link(repo, gh).returncode == 0
    first = _manifest(repo, SLUG)

    result = _link(repo, gh)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo, SLUG) == first
    assert [r["id"] for r in _approvals(repo)] == ["EV-PR-APPROVAL-1", "EV-PR-APPROVAL-2"]
    assert "already on record" in result.stdout


def _set_aside(repo, gh, reviews, reason):
    _merged(repo, gh, reviews)
    result = _link(repo, gh)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _approvals(repo) == []
    assert reason in result.stdout, result.stdout
    assert "No approving review by a person other than the author" in result.stdout
    assert _manifest(repo, SLUG)["pull_request"]["merged_at"] == MERGED_AT
    rows = _check(repo, gh)
    assert [r["status"] for r in rows] == ["fail"], rows
    assert "acme/widgets#7 merged with no approving review" in rows[0]["detail"]


def test_an_approval_by_the_author_does_not_count(repo, gh):
    _set_aside(repo, gh, [_review(1, AUTHOR.upper())], "the pull request's author")


def test_an_approval_by_a_bot_does_not_count(repo, gh):
    _set_aside(repo, gh, [_review(1, "copilot-pull-request-reviewer[bot]", kind="Bot")],
               "account type Bot, not User")


def test_an_approval_after_the_merge_does_not_count(repo, gh):
    _set_aside(repo, gh, [_review(1, "tidy-dev", at="2026-11-07T02:00:00Z")],
               "given after the merge")


def test_an_approval_superseded_by_a_change_request_does_not_count(repo, gh):
    _set_aside(repo, gh, [_review(1, "tidy-dev"),
                          _review(2, "tidy-dev", state="CHANGES_REQUESTED",
                                  at="2026-11-07T01:30:00Z")],
               "a later review is changes requested")


def test_a_comment_after_an_approval_keeps_it(repo, gh):
    _merged(repo, gh, [_review(1, "tidy-dev"),
                       _review(2, "tidy-dev", state="COMMENTED", at="2026-11-07T01:30:00Z"),
                       _review(3, "tidy-dev", state="CHANGES_REQUESTED",
                               at="2026-11-07T03:00:00Z")])
    assert _link(repo, gh).returncode == 0
    assert [r["review_id"] for r in _approvals(repo)] == [1]


def test_a_merged_pr_with_no_reviews_fails_the_check(repo, gh):
    _merged(repo, gh, [])
    result = _link(repo, gh)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No approving review" in result.stdout
    assert [r["status"] for r in _check(repo, gh)] == ["fail"]


def test_an_open_pr_records_the_link_and_reads_no_reviews(repo, gh):
    _merged(repo, gh, [_review(1, "tidy-dev")], state="OPEN")

    result = _link(repo, gh)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo, SLUG)["pull_request"] == {"repo": "acme/widgets", "number": 7}
    assert _approvals(repo) == []
    assert "read after the merge" in result.stdout
    assert [c[:2] for c in gh.calls()] == [["pr", "view"]]
    assert [r["status"] for r in _check(repo, gh)] == ["nothing-to-check"]


def _refused(repo, gh, **how):
    _merged(repo, gh, [_review(1, "tidy-dev")])
    before = _manifest(repo, SLUG)
    result = _link(repo, gh, **how)
    assert result.returncode != 0
    assert "Nothing was written" in result.stdout + result.stderr
    assert _manifest(repo, SLUG) == before
    assert "Traceback" not in result.stderr
    return result


def test_no_gh_writes_nothing(repo, gh):
    result = _refused(repo, gh, present=False)
    assert "gh is not installed" in result.stdout + result.stderr


def test_gh_not_logged_in_writes_nothing(repo, gh):
    result = _refused(repo, gh, mode="unauth")
    assert "gh auth login" in result.stdout + result.stderr


def test_github_down_writes_nothing(repo, gh):
    _refused(repo, gh, mode="down")


def test_a_failed_reviews_call_writes_nothing(repo, gh):
    result = _refused(repo, gh, fail="reviews")
    assert "cannot read the reviews" in result.stdout + result.stderr


def test_a_failed_user_call_writes_nothing(repo, gh):
    _refused(repo, gh, fail="user")


def test_a_repository_not_on_github_refuses_a_bare_number(repo, gh):
    make_issue(repo, gh, labels="infra")
    before = _manifest(repo, SLUG)
    result = _link(repo, gh)
    assert result.returncode != 0
    assert "Nothing was written" in result.stdout + result.stderr
    assert _manifest(repo, SLUG) == before
    assert gh.calls() == []


def test_evidence_add_refuses_a_pr_approval(repo, gh):
    make_issue(repo, gh, labels="infra")
    issue_dir = repo / ".compass" / "work" / SLUG
    (issue_dir / "evidence").mkdir(exist_ok=True)
    (issue_dir / "evidence" / "review.json").write_text("{}")
    before = _manifest(repo, SLUG)

    result = run(repo, gh, "evidence", "add", "--issue", SLUG, "--type", "pr-approval",
                 "--path", "evidence/review.json", "EV-PR-APPROVAL-1")

    assert result.returncode != 0
    assert "pr-approval record is copied from the merged pull request" in (
        result.stdout + result.stderr)
    assert _manifest(repo, SLUG) == before


# --- the selection rules, without the CLI -------------------------------------------------

def _select(reviews, author=AUTHOR, merged_at=MERGED_AT):
    sys.path.insert(0, str(CLI.parent))
    from compass_pkg import ship_approval
    return ship_approval.select(reviews, author, merged_at)


def test_select_keeps_each_counting_reviewer_once_oldest_first():
    counting, set_aside = _select([
        _review(3, "b-dev", at="2026-11-07T01:40:00Z"),
        _review(1, "a-dev", at="2026-11-07T01:10:00Z"),
        _review(2, "A-DEV", at="2026-11-07T01:20:00Z"),
    ])
    assert [r["id"] for r in counting] == [2, 3]
    assert set_aside == []


def test_select_sets_aside_a_dismissed_approval():
    counting, set_aside = _select([_review(1, "a-dev", state="DISMISSED")])
    assert counting == [] and set_aside == []


def test_select_ignores_a_review_with_no_login_or_time():
    broken = [_review(1, "a-dev", at="not a time"), dict(_review(2, "x"), user=None),
              dict(_review(3, "y"), id=None), "not a review"]
    assert _select(broken) == ([], [])


def test_select_counts_nothing_without_a_merge_time():
    counting, set_aside = _select([_review(1, "a-dev")], merged_at=None)
    assert counting == []
    assert [reason for _r, reason in set_aside] == ["given after the merge"]
