"""`compass record commit` commits a committed record after the merge, and nothing else.

Step 7 of #356 [Commit the issue record with the code and add trail.md],
ADR-096, plan section 3.5. In committed mode the ship commit holds the issue
record, but the ship approval, the merge time and the merge commit come after
the merge. `compass issue link set --pr <n>` writes them, writes `trail.md`
again and prints `next: compass record commit --issue <slug>`. That verb
commits only the record: the issue folder, its documents folder and
`.compass/work/.gitignore`. It refuses when anything else is staged, when the
record is kept out, and when the record has no change.

Every `gh` call goes to the fake `gh` (tests/fake_gh.py), so no test reaches
the network.
"""
from __future__ import annotations

import json

import yaml

from test_issue_link import FakeGh
from test_ship_commit_commits_the_record import (RECORD, SLUG, TRAIL, _compass, _files,
                                                 _git, _manifest, _ready, _repo, _ship,
                                                 _trail_mismatches)

KEY = "acme/widgets#7"
REVIEWER = "reviewer-dev"
NEXT = f"next: compass record commit --issue {SLUG}"


def _landed(tmp_path, compass_yml=None):
    """A quick fix landed in committed mode, its pull request acme/widgets#7
    merged as the ship commit, with one approving review by another person."""
    root = _ready(_repo(tmp_path / "repo", compass_yml=compass_yml))
    done = _ship(root)
    assert done.returncode == 0, done.stdout + done.stderr
    _git(root, "remote", "add", "origin", "https://github.com/acme/widgets.git")
    gh = FakeGh(tmp_path)
    _pull_request(gh, _git(root, "rev-parse", "HEAD"))
    return root, gh


def _pull_request(gh, merge_commit, state="MERGED"):
    s = gh.state()
    s.setdefault("prs", {})[KEY] = {
        "number": 7, "state": state, "url": "https://github.com/acme/widgets/pull/7",
        "mergeCommit": {"oid": merge_commit} if state == "MERGED" else None,
        "mergedAt": "2026-11-07T01:48:47Z" if state == "MERGED" else None,
        "author": {"login": "author-dev", "is_bot": False}, "headRefOid": merge_commit}
    s.setdefault("reviews", {})[KEY] = [{
        "id": 101, "state": "APPROVED", "submitted_at": "2026-11-07T01:27:26Z",
        "commit_id": merge_commit,
        "html_url": "https://github.com/acme/widgets/pull/7#pullrequestreview-101",
        "user": {"login": REVIEWER, "type": "User"}}]
    (gh.dir / "state.json").write_text(json.dumps(s))


def _link(root, gh):
    return _compass(root, "issue", "link", "set", "--pr=7", "--issue", SLUG, env=gh.env())


def _commit(root, gh, *extra):
    return _compass(root, "record", "commit", "--issue", SLUG, *extra, env=gh.env())


def _head(root):
    return _git(root, "rev-parse", "HEAD")


# --- the post-merge fields ------------------------------------------------------------------

def test_the_merged_trail_says_the_approval_is_read_after_the_merge(tmp_path):
    root, _ = _landed(tmp_path)
    committed = _git(root, "show", f"HEAD:{TRAIL}")
    assert "read from the pull request after the merge" in committed, committed


def test_link_set_writes_the_merge_fields_and_names_record_commit(tmp_path):
    root, gh = _landed(tmp_path)
    ship = _head(root)
    done = _link(root, gh)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.rstrip().splitlines()[-1] == NEXT, done.stdout
    task = _manifest(root)
    assert task["pull_request"]["merge_commit"] == ship
    # The record landed with the code, so git gives the land commit.
    assert "land_commit" not in task, task
    assert any(e.get("type") == "pr-approval" and e.get("approver") == REVIEWER
               for e in task["evidence"]), task["evidence"]
    trail = (root / TRAIL).read_text()
    assert f"review 101 by {REVIEWER} on {KEY}" in trail, trail
    assert f"Check these at the merge commit {ship}" in trail, trail
    assert _compass(root, "trail", "--check", "--issue", SLUG).returncode == 0
    # Nothing is committed by link set.
    assert _head(root) == ship
    assert "next: compass record commit" in _compass(root, "next", "--issue", SLUG).stdout


def test_link_set_json_names_the_next_command(tmp_path):
    root, gh = _landed(tmp_path)
    done = _compass(root, "issue", "link", "set", "--pr=7", "--issue", SLUG, "--json",
                    env=gh.env())
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout)["next"] == f"compass record commit --issue {SLUG}"


def test_an_open_pull_request_names_no_record_commit(tmp_path):
    root, gh = _landed(tmp_path)
    _pull_request(gh, _head(root), state="OPEN")
    done = _link(root, gh)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "record commit" not in done.stdout, done.stdout
    assert "after the merge" in (root / TRAIL).read_text()


# --- the record commit ----------------------------------------------------------------------

def test_record_commit_commits_only_the_record(tmp_path):
    root, gh = _landed(tmp_path)
    assert _link(root, gh).returncode == 0
    ship = _head(root)
    done = _commit(root, gh)
    assert done.returncode == 0, done.stdout + done.stderr
    assert _head(root) != ship
    held = _files(root)
    assert held and all(p.startswith(f"{RECORD}/") or p == ".compass/work/.gitignore"
                        or p.startswith("docs/compass/") for p in held), held
    assert f"{RECORD}/manifest.yml" in held and TRAIL in held, held
    assert _git(root, "log", "-1", "--format=%s") == f"Record the merge of {SLUG}"
    assert _git(root, "status", "--porcelain", "--", ".compass/work") == ""
    # The committed record holds the ship approval and a trail that matches it.
    committed = yaml.safe_load(_git(root, "show", f"HEAD:{RECORD}/manifest.yml"))
    assert committed["pull_request"]["merged_at"] == "2026-11-07T01:48:47Z"
    assert REVIEWER in _git(root, "show", f"HEAD:{TRAIL}")
    assert _trail_mismatches(root) == []
    assert "record commit" not in _compass(root, "next", "--issue", SLUG).stdout


def test_record_commit_takes_a_message(tmp_path):
    root, gh = _landed(tmp_path)
    assert _link(root, gh).returncode == 0
    done = _commit(root, gh, "-m", "Record the review of fix-f")
    assert done.returncode == 0, done.stdout + done.stderr
    assert _git(root, "log", "-1", "--format=%s") == "Record the review of fix-f"


def test_record_commit_refuses_when_code_is_staged(tmp_path):
    root, gh = _landed(tmp_path)
    assert _link(root, gh).returncode == 0
    before = (root / TRAIL).read_bytes()
    (root / "src" / "g.py").write_text("x = 1\n")
    _git(root, "add", "--", "src/g.py")
    ship = _head(root)
    done = _commit(root, gh)
    assert done.returncode != 0, done.stdout
    assert "src/g.py" in done.stderr and "Nothing was written" in done.stderr, done.stderr
    assert _head(root) == ship
    assert (root / TRAIL).read_bytes() == before
    # The record was not staged by the refused run.
    assert _git(root, "diff", "--cached", "--name-only") == "src/g.py"


def test_record_commit_refuses_with_no_change(tmp_path):
    root, gh = _landed(tmp_path)
    assert _link(root, gh).returncode == 0
    assert _commit(root, gh).returncode == 0
    head = _head(root)
    done = _commit(root, gh)
    assert done.returncode != 0, done.stdout
    assert "no change" in done.stderr, done.stderr
    assert _head(root) == head


def test_record_commit_refuses_in_kept_out_mode(tmp_path):
    root, gh = _landed(tmp_path, compass_yml="record:\n  commit: false\n")
    head = _head(root)
    done = _commit(root, gh)
    assert done.returncode != 0, done.stdout
    assert "compass record sync" in done.stderr, done.stderr
    assert "record.commit is false" in done.stderr, done.stderr
    assert _head(root) == head


def test_kept_out_link_set_moves_land_commit_and_names_no_record_commit(tmp_path):
    root, gh = _landed(tmp_path, compass_yml="record:\n  commit: false\n")
    merged = "c" * 40
    _pull_request(gh, merged)
    done = _link(root, gh)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "record commit" not in done.stdout, done.stdout
    assert _manifest(root)["land_commit"] == merged
    trail = (root / TRAIL).read_text()
    assert "Landed " in trail and merged in trail, trail
    assert _compass(root, "trail", "--check", "--issue", SLUG).returncode == 0
