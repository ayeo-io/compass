"""The request link and the requester: `--request` and `--requester` on
`compass issue link set` and `compass quick-fix start`.

Step 2 of #356 [Commit the issue record with the code and add trail.md]. The
manifest's `request` record holds the link, the requester and when the session
recorded them. `--request` takes an https URL or `owner/repo#N`, which also
writes `github` as `--github` does; `--github` alone gives the link. The
requester is free text on one line, at most 100 characters, recorded as a
claim. Nothing calls `gh`: every run here has a fake `gh` on PATH that records
each call, and the tests assert it recorded none. `quick-fix start` never
refuses for a missing request (contract 4 entry `quick-fix-start-valid`).
"""
from __future__ import annotations

import json
import re

import pytest

from test_issue_link import ROOT, FakeGh, make_issue, run  # noqa: F401
from test_quick_fix_verbs import _manifest, repo  # noqa: F401

SLUG = "sync-me"
LINK = "https://github.com/acme/widgets/issues/42"


@pytest.fixture
def gh(tmp_path):
    return FakeGh(tmp_path)


def _link(root, gh, *flags, slug=SLUG):
    return run(root, gh, "issue", "link", "set", *flags, "--issue", slug)


def _start(root, gh, *flags, slug="asked"):
    return run(root, gh, "quick-fix", "start", slug,
               "--risk", "trivial - one line", "--familiarity",
               "brownfield-mapped - the file and its test exist",
               "--size", "atomic - one line", "--intent", "it works",
               "--scenario", "Given a line, when read, then it is right.",
               "--test", "tests/test_x.py", *flags)


def test_link_set_records_the_link_and_the_requester(repo, gh):
    make_issue(repo, gh)
    result = _link(repo, gh, "--request", "https://tracker.example.com/T-7?x=1",
                   "--requester", "  Dana Smith  ")
    assert result.returncode == 0, result.stdout + result.stderr
    held = _manifest(repo, SLUG)["request"]
    assert held["link"] == "https://tracker.example.com/T-7?x=1"
    assert held["requester"] == "Dana Smith"
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT[\d:]+(Z|\+00:00)", held["recorded_at"]), held
    assert "github" not in _manifest(repo, SLUG)
    assert "requested by Dana Smith (recorded as a claim)" in result.stdout
    lint = run(repo, gh, "issue", "lint", "--issue", SLUG)
    assert lint.returncode == 0, lint.stdout + lint.stderr
    assert gh.calls() == []


def test_a_github_request_also_links_the_issue(repo, gh):
    make_issue(repo, gh)
    result = _link(repo, gh, "--request", "acme/widgets#42")
    assert result.returncode == 0, result.stdout + result.stderr
    body = _manifest(repo, SLUG)
    assert body["github"] == {"repo": "acme/widgets", "number": 42}
    assert body["request"]["link"] == LINK
    assert "requester" not in body["request"]
    assert "no requester yet" in result.stdout
    # The second part on its own keeps the first.
    assert _link(repo, gh, "--requester", "Dana Smith").returncode == 0
    assert _manifest(repo, SLUG)["request"]["link"] == LINK
    assert gh.calls() == []


def test_github_alone_counts_as_the_link(repo, gh):
    make_issue(repo, gh)
    result = _link(repo, gh, "--github", "acme/widgets#42")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo, SLUG)["request"]["link"] == LINK
    # A link already held is not replaced by a later `--github`.
    assert _link(repo, gh, "--request", "https://tracker.example.com/T-7").returncode == 0
    assert _link(repo, gh, "--github", "acme/widgets#43").returncode == 0
    assert _manifest(repo, SLUG)["request"]["link"] == "https://tracker.example.com/T-7"
    assert gh.calls() == []


def test_github_and_request_naming_two_issues_are_refused(repo, gh):
    make_issue(repo, gh)
    before = (repo / ".compass" / "work" / SLUG / "manifest.yml").read_bytes()
    result = _link(repo, gh, "--github", "acme/widgets#42", "--request", "acme/widgets#43")
    assert result.returncode != 0
    assert "name one GitHub issue" in result.stderr
    assert (repo / ".compass" / "work" / SLUG / "manifest.yml").read_bytes() == before


BAD_LINKS = ["http://example.com/x", "https://", "https://exa mple.com/x",
             "https://example.com/x\ny", "ftp://example.com/x", "example.com/x", "",
             "https://example.com/" + "a" * 2000, "acme/widgets#0"]


@pytest.mark.parametrize("bad", BAD_LINKS)
def test_a_bad_link_is_refused_and_nothing_is_written(repo, gh, bad):
    make_issue(repo, gh)
    before = (repo / ".compass" / "work" / SLUG / "manifest.yml").read_bytes()
    result = _link(repo, gh, f"--request={bad}", "--requester", "Dana Smith")
    assert result.returncode != 0, bad
    assert "is not a request link" in result.stderr, result.stderr
    assert "Nothing was written" in result.stderr
    assert (repo / ".compass" / "work" / SLUG / "manifest.yml").read_bytes() == before
    assert gh.calls() == []


BAD_REQUESTERS = ["", "   ", "a" * 101, "Dana\nSmith", "Dana\x1b[31mSmith"]


@pytest.mark.parametrize("bad", BAD_REQUESTERS)
def test_a_bad_requester_is_refused_and_nothing_is_written(repo, gh, bad):
    make_issue(repo, gh)
    before = (repo / ".compass" / "work" / SLUG / "manifest.yml").read_bytes()
    result = _link(repo, gh, "--request", LINK, f"--requester={bad}")
    assert result.returncode != 0, repr(bad)
    assert "--requester must name who asked" in result.stderr, result.stderr
    assert (repo / ".compass" / "work" / SLUG / "manifest.yml").read_bytes() == before


def test_a_requester_of_one_hundred_characters_is_kept(repo, gh):
    make_issue(repo, gh)
    name = "D" * 100
    assert _link(repo, gh, "--requester", name).returncode == 0
    assert _manifest(repo, SLUG)["request"]["requester"] == name


def test_link_set_with_no_flag_names_the_request_flags(repo, gh):
    make_issue(repo, gh)
    result = run(repo, gh, "issue", "link", "set", "--issue", SLUG)
    assert result.returncode != 0
    assert "--request and --requester" in result.stderr


# --- quick-fix start -------------------------------------------------------------------------

def test_quick_fix_start_records_the_request_in_its_one_call(repo, gh):
    result = _start(repo, gh, "--request", "acme/widgets#42", "--requester", "Dana Smith")
    assert result.returncode == 0, result.stdout + result.stderr
    body = _manifest(repo, "asked")
    assert body["request"]["link"] == LINK and body["request"]["requester"] == "Dana Smith"
    assert body["github"] == {"repo": "acme/widgets", "number": 42}
    assert body["evidence_required"][0] == "request"
    assert "--request" not in result.stdout.splitlines()[-1]
    check = run(repo, gh, "check", "--json", "--issue", "asked")
    rows = {c["name"]: c["status"] for c in json.loads(check.stdout)["checks"]}
    assert rows["request-recorded"] == "pass", rows
    assert gh.calls() == []


def test_quick_fix_start_without_a_request_succeeds_and_next_asks_for_it(repo, gh):
    result = _start(repo, gh)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "request" not in _manifest(repo, "asked")
    assert result.stdout.splitlines()[-1] == (
        "next: compass issue link set --issue asked --request <url> --requester <name>")
    check = run(repo, gh, "check", "--json", "--issue", "asked")
    rows = {c["name"]: c["status"] for c in json.loads(check.stdout)["checks"]}
    assert rows["request-recorded"] == "fail", rows


def test_finish_lands_when_the_request_is_the_only_failure(repo):
    """The request is not a stop (#356, VD-033): `quick-fix finish` lands an issue
    whose only failing check is `request-recorded`, names the missing request,
    and `compass check` keeps failing on it until it is recorded."""
    from test_quick_fix_verbs import _finish, _ready_to_finish, _run
    _ready_to_finish(repo, "no-ask", request=False)
    finish = _finish(repo, "no-ask")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert "request : not recorded" in finish.stdout, finish.stdout
    assert "`compass issue link set --issue no-ask --request <url> --requester <name>`" \
        in finish.stdout, finish.stdout
    assert _manifest(repo, "no-ask")["status"] == "done"
    check = _run(repo, "check", "--json", "--issue", "no-ask")
    body = json.loads(check.stdout)
    assert check.returncode == 1
    assert [c["name"] for c in body["checks"] if c["status"] == "fail"] == ["request-recorded"]
    linked = _run(repo, "issue", "link", "set", "--issue", "no-ask", "--request", LINK,
                  "--requester", "Dana Smith")
    assert linked.returncode == 0, linked.stdout + linked.stderr
    assert _run(repo, "check", "--issue", "no-ask").returncode == 0


def test_finish_still_refuses_on_another_failure_beside_the_request(repo):
    from test_quick_fix_verbs import _finish, _ready_to_finish
    _ready_to_finish(repo, "no-ask", request=False)
    body = _manifest(repo, "no-ask")
    body["scenarios"][0]["intent"] = ""
    from test_quick_fix_verbs import _save_manifest
    _save_manifest(repo, "no-ask", body)
    finish = _finish(repo, "no-ask")
    assert finish.returncode != 0
    assert "`compass check` failed" in finish.stdout + finish.stderr
    assert _manifest(repo, "no-ask").get("status") != "done"


def test_quick_fix_start_refuses_a_bad_request_before_writing(repo, gh):
    result = _start(repo, gh, "--request", "http://example.com/x")
    assert result.returncode != 0
    assert "compass quick-fix start: --request" in result.stderr
    assert not (repo / ".compass" / "work" / "asked").exists()


def test_the_schema_holds_the_record_and_the_token():
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text())
    request = schema["properties"]["request"]
    assert set(request["properties"]) == {"link", "requester", "recorded_at"}
    assert request["properties"]["requester"]["maxLength"] == 100
    assert schema["properties"]["evidence_required"]["items"]["enum"][0] == "request"
