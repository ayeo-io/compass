"""Compass keeps one comment on a linked GitHub issue equal to the issue's README.

A project opts in with `github_labels.page: true` in `compass.yml`. Every
test runs the real CLI against a fake `gh` on PATH (tests/fake_gh.py), which
records each call and the text sent on standard input, so no test reaches the
network. Links are decided from local git only: a test that needs an
`origin` sets its URL and its remote-tracking refs by hand.

Each test is named for a scenario of the issue `issue-page-reaches-github`.
"""
from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from test_github_label_sync import FakeGh, KEY, SLUG, make_issue
from test_quick_fix_verbs import _manifest, _save_manifest, repo  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
MARKER = "<!-- compass:issue-page -->"
ASK_MARKER = "<!-- compass:issue-ask -->"
ISSUE_API = "repos/acme/widgets/issues/42"


@pytest.fixture
def gh(tmp_path):
    return FakeGh(tmp_path)


def run(root, gh, *args, mode="", present=True, fail="", env=None):
    full = gh.env(mode, present)
    full["FAKE_GH_FAIL"] = fail
    full.update(env or {})
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True, env=full)


def ok(result):
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def settings(root, domain=False, status=False, page=True, extra=""):
    text = (f"schema: 1\ngithub_labels:\n  domain: {str(domain).lower()}\n"
            f"  status: {str(status).lower()}\n")
    if page is not None:
        text += f"  page: {page if isinstance(page, str) else str(page).lower()}\n"
    (root / "compass.yml").write_text(text + extra)


def link(root, gh, target="acme/widgets#42", slug=SLUG):
    return ok(run(root, gh, "issue", "link", "set", f"--github={target}", "--issue", slug))


def gsync(root, gh, slug=SLUG, **kw):
    return run(root, gh, "issue", "github", "sync", "--issue", slug, **kw)


def render(root, gh, slug=SLUG):
    return ok(run(root, gh, "issue", "render", "--issue", slug))


def docs_dir(root, slug=SLUG):
    found = sorted((root / "docs" / "compass").glob(f"*-{slug}"))
    assert len(found) == 1, found
    return found[0]


def readme(root, slug=SLUG):
    return (docs_dir(root, slug) / "README.md").read_text(encoding="utf-8")


def comments(gh, key=KEY):
    return gh.state().get("comments", {}).get(key, [])


def ours(gh, key=KEY):
    return [c for c in comments(gh, key) if c["body"].split("\n", 1)[0] == MARKER]


def add_comment(gh, body, key=KEY):
    state = gh.state()
    state["next_id"] = state.get("next_id", 1000) + 1
    state.setdefault("comments", {}).setdefault(key, []).append(
        {"id": state["next_id"], "body": body})
    (gh.dir / "state.json").write_text(json.dumps(state))
    return state["next_id"]


def set_body(gh, body, key=KEY):
    state = gh.state()
    state.setdefault("bodies", {})[key] = body
    (gh.dir / "state.json").write_text(json.dumps(state))


def body_of(gh, key=KEY):
    return gh.state().get("bodies", {}).get(key, "")


def api_calls(gh):
    return [c for c in gh.calls() if c[:1] == ["api"]]


def sent(gh):
    path = gh.dir / "stdin.jsonl"
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def clear_calls(gh):
    (gh.dir / "calls.jsonl").write_text("")


def record(root, slug=SLUG):
    path = root / ".compass" / "work" / slug / "github-sync.yml"
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def digest(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def edit_manifest(root, change, slug=SLUG):
    data = _manifest(root, slug)
    change(data)
    _save_manifest(root, slug, data)


def plain(text, folder):
    """The README with every relative link turned into its repository path in
    code format: what the page posts when there is no github.com origin."""
    def one(match):
        target = match.group(3).split("#", 1)[0]
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
            return match.group(0)
        return "`" + posixpath.normpath(posixpath.join(folder, target)) + "`"
    return re.sub(r"(!?)\[([^\]\n]*)\]\(([^)\s]+)\)", one, text)


def expected_comment(root, slug=SLUG):
    folder = docs_dir(root, slug).relative_to(root).as_posix()
    return MARKER + "\n" + plain(readme(root, slug), folder)


def change_readme(root, gh, title, slug=SLUG):
    """Change a scenario title in the manifest and render, with no triggering command."""
    def retitle(m):
        m["scenarios"][0]["title"] = title
    edit_manifest(root, retitle, slug)
    render(root, gh, slug)


def write_intent(root, problem, outcome="It works for every reader.", slug=SLUG):
    (docs_dir(root, slug) / "intent.md").write_text(
        f"# Intent\n\n## Problem\n\n{problem}\n\n## Desired outcome\n\n{outcome}\n\n"
        "## Success signals\n\n- one\n")


def page_issue(repo, gh, slug=SLUG, target="acme/widgets#42", **switches):
    """A linked issue with its README rendered, then the switches set; nothing posted yet."""
    make_issue(repo, gh, slug=slug)
    render(repo, gh, slug)
    link(repo, gh, target, slug)
    settings(repo, **switches)
    return repo


def stderr_lines(result, needle):
    return [x for x in result.stderr.splitlines() if needle in x]


def git(root, *args):
    done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def commit_all(root, message):
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


def set_origin(root, url="https://github.com/acme/widgets.git", main=None):
    git(root, "remote", "add", "origin", url)
    if main:
        git(root, "update-ref", "refs/remotes/origin/main", main)
        git(root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")


# --- group A: posting the page and the body --------------------------------------

OFF_VALUES = {"none": None, "false": False, "no": "'no'", "one": "1"}


@pytest.mark.parametrize("name", sorted(OFF_VALUES))
def test_ipg_1_page_off_adds_no_call(repo, gh, name):
    make_issue(repo, gh)
    render(repo, gh)
    link(repo, gh)
    settings(repo, domain=True, status=True, page=OFF_VALUES[name])

    def commands(n):
        return (["approach", "evaluate", "--write"],
                ["scenario", "add", f"TRC-{n}", "--title", "More", "--intent", "INT-1",
                 "--test", "tests/test_more.py"],
                ["issue", "status", "set", "backlog"],
                ["issue", "status", "remove"],
                ["issue", "github", "sync"],
                ["issue", "lint"])

    for args in commands(101):
        ok(run(repo, gh, *args, "--issue", SLUG))
    calls = gh.calls()
    assert calls
    for call in calls:
        assert call[:2] in (["issue", "view"], ["label", "list"], ["label", "create"],
                            ["issue", "edit"]), call
        if call[:2] == ["issue", "view"]:
            assert call[-2:] == ["--json", "labels"], call
        if call[:2] == ["issue", "edit"]:
            assert all(word in ("--add-label", "--remove-label", "--repo")
                       for word in call[3::2]), call
    text = json.dumps(calls)
    assert "api" not in [c[0] for c in calls]
    for word in ("comment", "body", "--input"):
        assert word not in text, word
    settings(repo, page=False)
    clear_calls(gh)
    for args in commands(102):
        ok(run(repo, gh, *args, "--issue", SLUG))
    assert gh.calls() == []


def test_ipg_2_first_sync_creates_one_comment(repo, gh):
    page_issue(repo, gh)
    result = ok(gsync(repo, gh))
    assert len(comments(gh)) == 1
    text = comments(gh)[0]["body"]
    assert text.split("\n", 1)[0] == MARKER
    assert text == expected_comment(repo)
    folder = docs_dir(repo).relative_to(repo).as_posix()
    assert f"`{folder}/delivery-approach.md`" in text
    assert "](delivery-approach.md)" not in text
    for kind in ("ask", "acceptance", "related", "decisions"):
        assert f"<!-- compass:render {kind} -->" in text, kind
    assert record(repo)["page"]["digest"] == digest(text)
    assert record(repo)["page"]["comment_id"] == comments(gh)[0]["id"]
    assert result.returncode == 0


def test_ipg_3_record_change_edits_the_same_comment(repo, gh):
    page_issue(repo, gh)
    ok(gsync(repo, gh))
    first = ours(gh)[0]["id"]
    people = {add_comment(gh, "I see the crash too."): "I see the crash too.",
              add_comment(gh, "Fixed on my side?"): "Fixed on my side?"}
    evidence = repo / ".compass" / "work" / SLUG / "evidence"
    evidence.mkdir(exist_ok=True)
    (evidence / "proof.json").write_text('{"command": "true", "exit_code": 0}')
    on = {"COMPASS_RENDER_AFTER": "1"}
    ok(run(repo, gh, "evidence", "add", "EV-1", "--type", "test-run",
           "--path", "evidence/proof.json", "--issue", SLUG, env=on))
    steps = (["scenario", "add", "TRC-002", "--title", "Second", "--intent", "INT-1",
              "--test", "tests/test_two.py"],
             ["gate", "pass", "verify.correctness", "--evidence", "EV-1"],
             ["issue", "artifact", "set", "delivery-approach", "--status",
              "awaiting-approval"])
    for args in steps:
        before = readme(repo)
        ok(run(repo, gh, *args, "--issue", SLUG, env=on))
        assert readme(repo) != before, args
        mine = ours(gh)
        assert len(mine) == 1 and mine[0]["id"] == first, (args, comments(gh))
        assert mine[0]["body"] == expected_comment(repo), args
        theirs = {c["id"]: c["body"] for c in comments(gh) if c["id"] != first}
        assert theirs == people, args
    assert not [c for c in api_calls(gh) if "POST" in c and c[1].endswith("/comments")][1:]


def test_ipg_22_page_posts_the_readme_its_command_rendered(repo, gh):
    on = {"COMPASS_RENDER_AFTER": "1"}
    make_issue(repo, gh)
    ok(run(repo, gh, "scenario", "add", "TRC-002", "--title", "Second", "--intent", "INT-1",
           "--test", "tests/test_two.py", "--issue", SLUG, env=on))
    link(repo, gh)
    settings(repo)
    ok(gsync(repo, gh))
    assert "0 of 2 scenarios passed" in ours(gh)[0]["body"]
    # A green record on disk, written without a command, so the README does not change yet.
    evidence = repo / ".compass" / "work" / SLUG / "evidence"
    evidence.mkdir(exist_ok=True)
    (evidence / "green-TRC-001.json").write_text(json.dumps(
        {"scenario": "TRC-001", "command": "true", "exit_code": 0}))
    (evidence / "proof.json").write_text('{"command": "true", "exit_code": 0}')
    # With the render switched off, a record-changing command leaves the README as it
    # was, and the page step neither renders it nor calls GitHub.
    before = readme(repo)
    clear_calls(gh)
    ok(run(repo, gh, "evidence", "add", "EV-1", "--type", "test-run",
           "--path", "evidence/proof.json", "--issue", SLUG))
    assert readme(repo) == before
    assert api_calls(gh) == []
    ok(run(repo, gh, "gate", "pass", "verify.correctness", "--evidence", "EV-1",
           "--issue", SLUG, env=on))
    assert "1 of 2 scenarios passed" in readme(repo)
    assert "1 of 2 scenarios passed" in ours(gh)[0]["body"]
    assert ours(gh)[0]["body"] == expected_comment(repo)
    # A linked issue whose README this command rewrites waits for its own sync.
    other = "other-issue"
    make_issue(repo, gh, slug=other)
    render(repo, gh, other)
    link(repo, gh, "acme/widgets#43", other)
    ok(gsync(repo, gh, slug=other))
    assert len(ours(gh, "acme/widgets#43")) == 1
    other_before = readme(repo, other)
    clear_calls(gh)
    ok(run(repo, gh, "issue", "raised-by", other, "--found-at", "verify", "--issue", SLUG,
           env=on))
    assert readme(repo, other) != other_before
    assert not [c for c in gh.calls() if "/issues/43" in " ".join(c)], gh.calls()
    lint = run(repo, gh, "issue", "lint", "--issue", other)
    assert lint.returncode == 0, lint.stdout + lint.stderr
    assert "out of date" in lint.stdout and "compass issue github sync" in lint.stdout


def test_ipg_4_unchanged_issue_makes_no_call(repo, gh):
    page_issue(repo, gh)
    ok(gsync(repo, gh))
    assert record(repo)["page"]["digest"] == digest(expected_comment(repo))
    clear_calls(gh)
    ok(gsync(repo, gh))
    ok(run(repo, gh, "issue", "status", "set", "backlog", "--issue", SLUG))
    assert gh.calls() == []


def test_ipg_5_finds_its_comment_by_the_marker(repo, gh):
    page_issue(repo, gh)
    quoted = "I copied this:\n\n" + MARKER + "\nand it broke"
    person = add_comment(gh, quoted)
    ok(gsync(repo, gh))
    mine = ours(gh)
    assert len(mine) == 1
    (repo / ".compass" / "work" / SLUG / "github-sync.yml").unlink()
    change_readme(repo, gh, "A changed title")
    clear_calls(gh)
    ok(gsync(repo, gh))
    assert [c["id"] for c in ours(gh)] == [mine[0]["id"]]
    assert "A changed title" in ours(gh)[0]["body"]
    assert not [c for c in api_calls(gh) if "POST" in c]
    assert {c["id"]: c["body"] for c in comments(gh)}[person] == quoted
    # Someone deletes the Compass comment on GitHub.
    state = gh.state()
    state["comments"][KEY] = [c for c in state["comments"][KEY] if c["id"] != mine[0]["id"]]
    (gh.dir / "state.json").write_text(json.dumps(state))
    change_readme(repo, gh, "Changed again")
    ok(gsync(repo, gh))
    assert len(ours(gh)) == 1 and "Changed again" in ours(gh)[0]["body"]
    assert {c["id"]: c["body"] for c in comments(gh)}[person] == quoted


def test_ipg_6_links_open_on_github(repo, gh):
    from compass_pkg import github_links
    # The rewriting itself, on a README that links an intent, a sibling and an ADR.
    folder = "docs/compass/2026-01-01-demo"
    for rel in (f"{folder}/intent.md", "docs/compass/2026-01-01-other/README.md",
                "architecture/decisions/ADR-001-x.md"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("x\n")
    main = commit_all(repo, "documents")
    set_origin(repo, main=main)
    git(repo, "checkout", "-q", "-b", "the-issue")
    (repo / folder / "technical-design.md").write_text("design\n")
    branch = commit_all(repo, "design")
    text = ("[intent](intent.md), [other](../2026-01-01-other/README.md), "
            "[ADR](../../../architecture/decisions/ADR-001-x.md#context), "
            "[design](technical-design.md), [web](https://example.com/a/b), [top](#x)\n"
            "```\n[fenced](intent.md)\n```\n[out](../../../../elsewhere.md)\n")
    out = github_links.rewrite_links(text, f"{folder}/README.md", str(repo))
    blob = "https://github.com/acme/widgets/blob/main/"
    assert f"[intent]({blob}{folder}/intent.md)" in out
    assert f"[other]({blob}docs/compass/2026-01-01-other/README.md)" in out
    assert f"[ADR]({blob}architecture/decisions/ADR-001-x.md#context)" in out
    assert f"`{folder}/technical-design.md` (not on main)" in out
    assert "[design]" not in out and "yet" not in out
    assert "[web](https://example.com/a/b)" in out and "[top](#x)" in out
    assert "```\n[fenced](intent.md)\n```" in out
    assert "elsewhere" not in out and "out" in out
    git(repo, "update-ref", "refs/remotes/origin/main", branch)
    out = github_links.rewrite_links(text, f"{folder}/README.md", str(repo))
    assert f"[design]({blob}{folder}/technical-design.md)" in out
    # No origin, or one that is not on github.com: every link is a plain path.
    for url in (None, "https://gitlab.example.com/acme/widgets.git"):
        if "origin" in git(repo, "remote").split():
            git(repo, "remote", "remove", "origin")
        if url:
            set_origin(repo, url, main=branch)
        out = github_links.rewrite_links(text, f"{folder}/README.md", str(repo))
        assert f"`{folder}/intent.md`" in out and "(not on" not in out
        assert "github.com" not in out
    git(repo, "remote", "remove", "origin")
    # Through the sync: the issue's own documents are not on origin/main until they are.
    git(repo, "checkout", "-q", "-")
    page_issue(repo, gh)
    set_origin(repo, main=git(repo, "rev-parse", "HEAD"))
    ok(gsync(repo, gh))
    issue_folder = docs_dir(repo).relative_to(repo).as_posix()
    body = ours(gh)[0]["body"]
    assert f"`{issue_folder}/delivery-approach.md` (not on main)" in body
    assert "(not on main yet)" not in body and "main yet" not in body
    landed = commit_all(repo, "land the issue folder")
    git(repo, "update-ref", "refs/remotes/origin/main", landed)
    clear_calls(gh)
    ok(gsync(repo, gh))
    assert [c for c in api_calls(gh) if "PATCH" in c]
    body = ours(gh)[0]["body"]
    assert f"[delivery-approach]({blob}{issue_folder}/delivery-approach.md)" in body


def test_ipg_7_empty_body_gets_the_ask_once(repo, gh):
    for number, empty in ((42, ""), (43, "  \n\t"), (44, ASK_MARKER)):
        slug, key = f"issue-{number}", f"acme/widgets#{number}"
        make_issue(repo, gh, slug=slug)
        write_intent(repo, f"Problem number {number}.", f"Outcome number {number}.", slug=slug)
        render(repo, gh, slug)
        set_body(gh, empty, key)
        link(repo, gh, key, slug)
        settings(repo)
        ok(gsync(repo, gh, slug=slug))
        body = body_of(gh, key)
        assert body.split("\n", 1)[0] == ASK_MARKER, body
        assert f"Problem number {number}." in body and f"Outcome number {number}." in body
        assert "**Problem**" in body and "**Desired outcome**" in body
        assert "Success signals" not in body
        cid = ours(gh, key)[0]["id"]
        assert body.rstrip("\n").splitlines()[-1].endswith(
            f"(https://github.com/acme/widgets/issues/{number}#issuecomment-{cid}).")
        assert record(repo, slug)["page"]["body"] == "set"
        clear_calls(gh)
        for turn in range(5):
            change_readme(repo, gh, f"Title {turn}", slug=slug)
            ok(gsync(repo, gh, slug=slug))
        issue_path = f"repos/acme/widgets/issues/{number}"
        assert not [c for c in api_calls(gh) if c[1] == issue_path], api_calls(gh)
        assert body_of(gh, key) == body
    # With no intent.md, the issue line stands in for the two sections.
    slug, key = "no-intent", "acme/widgets#45"
    make_issue(repo, gh, slug=slug)
    render(repo, gh, slug)
    link(repo, gh, key, slug)
    ok(gsync(repo, gh, slug=slug))
    body = body_of(gh, key)
    assert body.startswith(ASK_MARKER + "\n") and "it works" in body
    assert "**Problem**" not in body


def test_ipg_8_written_body_and_title_unchanged(repo, gh):
    page_issue(repo, gh)
    set_body(gh, "Customer reports a crash on export")
    ok(gsync(repo, gh))
    change_readme(repo, gh, "Another title")
    ok(gsync(repo, gh))
    assert body_of(gh) == "Customer reports a crash on export"
    assert len(ours(gh)) == 1 and "Another title" in ours(gh)[0]["body"]
    assert not [c for c in api_calls(gh) if c[1] == ISSUE_API and "PATCH" in c]
    for one in sent(gh):
        assert set(json.loads(one["stdin"])) == {"body"}, one
        assert one["argv"][1] != ISSUE_API, one
    assert record(repo)["page"]["body"] == "kept"
    # A body Compass once wrote, to which a person added a paragraph.
    slug, key = "second", "acme/widgets#43"
    make_issue(repo, gh, slug=slug)
    render(repo, gh, slug)
    written = ASK_MARKER + "\n**Problem**\n\nOld.\n\nA paragraph a person added."
    set_body(gh, written, key)
    link(repo, gh, key, slug)
    ok(gsync(repo, gh, slug=slug))
    assert body_of(gh, key) == written
    assert record(repo, slug)["page"]["body"] == "kept"


# --- group B: failure, drift and the command --------------------------------------

def test_ipg_9_gh_failure_keeps_the_exit_code(repo, gh):
    page_issue(repo, gh)
    for kind, mode, present in (("missing", "", False), ("unauth", "unauth", True),
                                ("down", "down", True)):
        for args in (["issue", "status", "set", "backlog"], ["issue", "status", "remove"]):
            result = run(repo, gh, *args, "--issue", SLUG, mode=mode, present=present)
            assert result.returncode == 0, (kind, result.stdout + result.stderr)
            lines = [x for x in result.stderr.splitlines() if x.strip()]
            assert len(lines) == 1, (kind, result.stderr)
            assert "compass issue github sync" in lines[0], lines[0]
            assert record(repo)["page"]["error"], kind
        assert "status" not in _manifest(repo, SLUG)
        lint = run(repo, gh, "issue", "lint", "--issue", SLUG, mode=mode, present=present)
        assert lint.returncode == 0, lint.stdout + lint.stderr
        assert "out of date" in lint.stdout, (kind, lint.stdout)
    stored = run(repo, gh, "issue", "status", "set", "backlog", "--issue", SLUG, mode="down")
    assert stored.returncode == 0 and _manifest(repo, SLUG)["status"] == "backlog"
    clear_calls(gh)
    refused = run(repo, gh, "issue", "status", "set", "ready", "--issue", SLUG)
    assert refused.returncode != 0
    assert gh.calls() == []


def test_ipg_10_labels_and_page_fail_independently(repo, gh):
    page_issue(repo, gh, status=True)
    # Only the page calls fail: the status label still lands.
    result = run(repo, gh, "issue", "status", "set", "backlog", "--issue", SLUG, fail="api")
    ok(result)
    assert "status:backlog" in gh.labels()
    assert len(stderr_lines(result, "github page not")) == 1, result.stderr
    assert not stderr_lines(result, "github labels not"), result.stderr
    # Only the label calls fail: the comment still lands.
    change_readme(repo, gh, "A new title")
    result = run(repo, gh, "issue", "status", "remove", "--issue", SLUG, fail="labels")
    ok(result)
    assert ours(gh) and ours(gh)[0]["body"] == expected_comment(repo)
    assert len(stderr_lines(result, "github labels not")) == 1, result.stderr
    assert not stderr_lines(result, "github page not"), result.stderr
    # Both land, then the page fails: the label result is new, the page keeps its digest.
    ok(gsync(repo, gh))
    earlier = record(repo)["page"]["digest"]
    change_readme(repo, gh, "Third title")
    ok(run(repo, gh, "issue", "status", "set", "backlog", "--issue", SLUG, fail="api"))
    kept = record(repo)
    assert kept["labels"]["state"] == ["status:backlog"] and kept["labels"]["error"] is None
    assert kept["page"]["error"] and kept["page"]["digest"] == earlier
    # Both land, then the labels fail: the page result is new, the labels keep their state.
    ok(gsync(repo, gh))
    change_readme(repo, gh, "Fourth title")
    ok(run(repo, gh, "issue", "status", "remove", "--issue", SLUG, fail="labels"))
    kept = record(repo)
    assert kept["labels"]["error"] and kept["labels"]["state"] == ["status:backlog"]
    assert kept["page"]["error"] is None
    assert kept["page"]["digest"] == digest(ours(gh)[0]["body"])
    assert "Fourth title" in ours(gh)[0]["body"]


def test_ipg_11_lint_reports_a_stale_page(repo, gh):
    page_issue(repo, gh)
    ok(gsync(repo, gh))
    change_readme(repo, gh, "Changed by hand")
    clear_calls(gh)
    lint = run(repo, gh, "issue", "lint", "--issue", SLUG)
    assert lint.returncode == 0, lint.stdout + lint.stderr
    page_lines = [x for x in lint.stdout.splitlines() if "page" in x]
    assert len(page_lines) == 1, lint.stdout
    assert "out of date" in page_lines[0] and "compass issue github sync" in page_lines[0]
    assert gh.calls() == []
    ok(gsync(repo, gh))
    lint = run(repo, gh, "issue", "lint", "--issue", SLUG)
    assert lint.returncode == 0
    assert not [x for x in lint.stdout.splitlines() if "page" in x], lint.stdout


def test_ipg_12_github_sync_refreshes_both(repo, gh):
    page_issue(repo, gh, domain=True, status=True)
    ok(gsync(repo, gh))
    gh.set_labels(["status:in-review"])
    change_readme(repo, gh, "Stale on GitHub")
    result = gsync(repo, gh)
    assert result.returncode == 0, result.stdout + result.stderr
    assert gh.labels() == {"infra", "ci", "status:ready"}
    assert ours(gh)[0]["body"] == expected_comment(repo)
    # Not linked.
    make_issue(repo, gh, slug="unlinked")
    unlinked = gsync(repo, gh, slug="unlinked")
    assert unlinked.returncode != 0
    assert "compass issue link set" in unlinked.stdout + unlinked.stderr
    # All three switches off.
    settings(repo, page=False)
    clear_calls(gh)
    nothing = ok(gsync(repo, gh))
    assert "nothing is switched on" in nothing.stdout + nothing.stderr
    assert gh.calls() == []
    # A failing gh, and a refused post.
    settings(repo, domain=True, status=True)
    change_readme(repo, gh, "Stale again")
    failing = gsync(repo, gh, mode="unauth")
    assert failing.returncode != 0
    assert "not logged in" in failing.stdout + failing.stderr
    write_intent(repo, "A token ghp_" + "a1" * 18 + " was pasted here.")
    render(repo, gh)
    refused = gsync(repo, gh)
    assert refused.returncode != 0
    assert "credential" in refused.stdout + refused.stderr


def test_ipg_13_labels_sync_is_removed(repo, gh):
    page_issue(repo, gh, status=True, page=False)
    clear_calls(gh)
    old = run(repo, gh, "issue", "labels", "sync", "--issue", SLUG)
    assert old.returncode == 2, old.stdout + old.stderr
    assert "compass issue github sync" in old.stderr or "issue github sync" in old.stderr
    assert gh.calls() == []
    table = yaml.safe_load((ROOT / "cli" / "aliases.yml").read_text())
    rows = [r for r in table["hints"] if r["old"] == ["issue", "labels", "sync"]]
    assert rows == [{"old": ["issue", "labels", "sync"], "new": ["issue", "github", "sync"],
                     "released_in": "v6.0.0", "removed_in": "7.0.0"}]
    assert not [r for r in table["aliases"] if r["old"][:2] == ["issue", "labels"]]
    from compass_pkg import github_labels, verb_help
    assert "issue labels sync" not in verb_help.VERB_DESCRIPTIONS
    assert "issue github sync" in verb_help.VERB_DESCRIPTIONS
    for helped in (run(repo, gh, "--help"), run(repo, gh, "issue", "--help"),
                   run(repo, gh, "issue", "github", "sync", "--help")):
        assert "labels sync" not in helped.stdout + helped.stderr
    assert "compass issue github sync" in github_labels._fail_line("x")
    settings(repo, status=True, page=False)
    gh.set_labels([])
    lint = run(repo, gh, "issue", "lint", "--issue", SLUG)
    assert "compass issue github sync" in lint.stdout and "labels sync" not in lint.stdout
    # No tracked teaching surface names the old verb, except the release history, the
    # upgrade notes, the one sentence that records the removal and the derived spec.
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                             text=True).stdout.split()
    allowed = {"docs/releasing.md", "docs/upgrade-7-0-0.md", "docs/system-spec.md"}
    found = []
    for rel in tracked:
        if rel in allowed or rel == "cli/aliases.yml" or rel.startswith(
                ("tests/", "docs/compass/", ".compass/", "examples/", "evals/")):
            continue
        if not rel.endswith((".md", ".py", ".yml", ".yaml", ".txt")) and rel != "cli/compass":
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = [x for x in text.splitlines() if "issue labels sync" in x]
        if rel == "docs/github-labels.md":
            removal = [x for x in lines if "removed" in x]
            lines = [x for x in lines if "removed" not in x] + removal[1:]
        if lines:
            found.append(rel)
    assert found == [], found


def test_ipg_14_never_reads_github_text_back(tmp_path):
    results = {}
    for edited in (False, True):
        base = tmp_path / ("edited" if edited else "plain")
        base.mkdir()
        root = base / "repo"
        root.mkdir()
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"],
                     ["config", "user.name", "t"]):
            git(root, *args)
        (root / "README.md").write_text("hello\n")
        commit_all(root, "base")
        fake = FakeGh(base)
        page_issue(root, fake)
        ok(gsync(root, fake))
        if edited:
            state = fake.state()
            state["comments"][KEY][0]["body"] = MARKER + "\nA person rewrote this."
            state.setdefault("bodies", {})[KEY] = "A person wrote this body."
            (fake.dir / "state.json").write_text(json.dumps(state))
            add_comment(fake, "Another person's comment.")
        steps = [["scenario", "add", f"TRC-{n}", "--title", f"S{n}", "--intent", "INT-1",
                  "--test", f"tests/test_{n}.py"] for n in range(2, 6)]
        steps += [["issue", "status", "set", "backlog"], ["issue", "status", "remove"],
                  ["follow-up", "add", "FU-1", "--summary", "later"],
                  ["issue", "decision", "add", "D-1", "--question", "Which?",
                   "--resolution", "This one", "--by", "planner", "--stage", "plan"],
                  ["approach", "evaluate", "--write"],
                  ["scenario", "add", "TRC-9", "--title", "S9", "--intent", "INT-1",
                   "--test", "tests/test_9.py"]]
        for args in steps:
            ok(run(root, fake, *args, "--issue", SLUG))
        render(root, fake)
        ok(gsync(root, fake))
        files = {}
        stamp = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:[+-]\d\d:\d\d|Z)?")
        for path in [root / ".compass" / "work" / SLUG / "manifest.yml",
                     *sorted((root / "docs" / "compass").rglob("*"))]:
            if path.is_file():
                text = path.read_text(encoding="utf-8").replace(str(base), "<base>")
                files[path.relative_to(root).as_posix()] = stamp.sub("<time>", text)
        results[edited] = files
        sync_text = (root / ".compass" / "work" / SLUG / "github-sync.yml").read_text()
        assert "person" not in sync_text.lower()
        data = yaml.safe_load(sync_text)
        assert set(data) <= {"labels", "page"}
        assert set(data["page"]) <= {"at", "digest", "comment_id", "body", "error"}
        assert set(data.get("labels") or {}) <= {"at", "state", "error"}
    assert results[True] == results[False]


# --- group C: what may not leave the project -------------------------------------

def test_ipg_15_no_shell_no_token_text_on_stdin(repo, gh):
    page_issue(repo, gh)
    write_intent(repo, "--body $(touch pwned) and a `backtick` here.")
    render(repo, gh)
    ok(gsync(repo, gh))
    # A second sync edits the comment, so both the create and the edit path are read.
    change_readme(repo, gh, "--title $(touch pwned)")
    ok(gsync(repo, gh))
    assert [c for c in api_calls(gh) if "PATCH" in c and "/comments/" in c[1]]
    calls = gh.calls()
    assert calls
    for call in calls:
        assert all(isinstance(word, str) for word in call)
        for word in call:
            assert "pwned" not in word and "backtick" not in word and "\n" not in word, call
    carried = sent(gh)
    assert any("$(touch pwned)" in json.loads(x["stdin"])["body"] for x in carried)
    assert all(x["argv"][-2:] == ["--input", "-"] for x in carried)
    assert not (repo / "pwned").exists() and not Path("pwned").exists()
    for name in ("github_page.py", "publish_check.py", "github_links.py",
                 "github_sync_record.py", "github_labels.py"):
        source = (ROOT / "cli" / "compass_pkg" / name).read_text()
        for forbidden in ("shell=True", "os.system", "os.popen", "GH_TOKEN", "GITHUB_TOKEN",
                          "hosts.yml", "auth token", "os.getenv"):
            assert forbidden not in source, (name, forbidden)
    page_source = (ROOT / "cli" / "compass_pkg" / "github_page.py").read_text()
    assert "os.environ" not in page_source
    assert "env={}" in (ROOT / "cli" / "compass_pkg" / "publish_check.py").read_text()


def _imports_or_calls(path, name):
    """The lines of `path` that import `name`, or read it as a name or attribute."""
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits += [node.lineno for a in node.names if a.name.split(".")[-1] == name]
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[-1] == name:
                hits.append(node.lineno)
            hits += [node.lineno for a in node.names if a.name == name]
        elif isinstance(node, ast.Name) and node.id == name:
            hits.append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr == name:
            hits.append(node.lineno)
    return hits


def test_ipg_17_the_page_runs_no_rival_name_check(repo, gh, tmp_path):
    # The page carries the issue's own requirements, which never name another
    # product, so it runs two checks only: private paths and credentials.
    for name in ("github_page.py", "publish_check.py"):
        path = ROOT / "cli" / "compass_pkg" / name
        assert _imports_or_calls(path, "rival_names") == [], name
        assert "names_key" not in path.read_text(encoding="utf-8"), name
    # The guard reports a planted import and a planted call.
    planted = tmp_path / "planted.py"
    planted.write_text("from compass_pkg import rival_names\n")
    assert _imports_or_calls(planted, "rival_names") == [1]
    planted.write_text("import compass_pkg\ncompass_pkg.rival_names.scan('x', set())\n")
    assert _imports_or_calls(planted, "rival_names") == [2]
    # A names key set for `compass record sync` does not stop the post, and no
    # post writes a line about a names key.
    key = repo / ".compass" / "private" / "rivals.yml"
    key.parent.mkdir(parents=True, exist_ok=True)
    key.write_text("rivals:\n  R1:\n    name: Zentrafold\n")
    page_issue(repo, gh, extra="record:\n  names_key: .compass/private/rivals.yml\n")
    write_intent(repo, "Readers compare us with Zentrafold every day.")
    render(repo, gh)
    result = ok(gsync(repo, gh))
    assert len(ours(gh)) == 1 and "Zentrafold" in ours(gh)[0]["body"]
    assert not stderr_lines(result, "names")
    settings(repo)
    change_readme(repo, gh, "Edited")
    assert not stderr_lines(ok(gsync(repo, gh)), "names")


def test_ipg_17_private_path_refuses_the_post(repo, gh):
    from compass_pkg import publish_check
    (repo / ".gitignore").write_text("notes/private/\n")
    commit_all(repo, "ignore")
    page_issue(repo, gh)
    write_intent(repo, "See notes/private/brief.md for the background.")
    render(repo, gh)
    result = ok(run(repo, gh, "issue", "status", "set", "backlog", "--issue", SLUG))
    assert api_calls(gh) == []
    lines = [x for x in result.stderr.splitlines() if x.strip()]
    assert len(lines) == 1, result.stderr
    assert "keeps out of git" in lines[0] and "ask" in lines[0], lines[0]
    assert "brief.md" not in lines[0]
    write_intent(repo, "The notes are in .compass/private/notes.yml for now.")
    render(repo, gh)
    result = ok(run(repo, gh, "issue", "status", "remove", "--issue", SLUG))
    assert api_calls(gh) == []
    assert "keeps out of git" in result.stderr
    # Paths the project keeps out of git on purpose, and directories, are posted.
    (repo / ".gitignore").write_text("notes/private/\n.compass/work/\ndocs/compass/\n")
    (repo / "notes" / "private").mkdir(parents=True)
    write_intent(repo, "It reads .compass/work/demo-issue/released-verbs.md and "
                       "docs/compass/2026-01-01-demo/notes.md, and the folders "
                       ".compass/private/ and notes/private/.")
    render(repo, gh)
    ok(gsync(repo, gh))
    assert len(ours(gh)) == 1
    assert "released-verbs.md" in ours(gh)[0]["body"]
    # The strings the check reads, one at a time.
    assert publish_check.check({"comment": "x notes/private/brief.md", "body": None},
                               str(repo)).check == "private-path"
    assert publish_check.check({"comment": "ok", "body": "notes/private/brief.md."},
                               str(repo)).line.find("issue body") >= 0
    assert publish_check.check({"comment": "https://example.com/notes/private/a.md",
                                "body": None}, str(repo)) is None
    # git cannot be asked about a path outside the project, but a file under
    # .compass/private/ is refused by its name alone, however the path is written.
    for text in ("see /home/u/widgets/.compass/private/rival-codes.yml",
                 "see ../../../.compass/private/notes.yml"):
        found = publish_check.check({"comment": text, "body": None}, str(repo))
        assert found is not None and found.check == "private-path", text


def test_ipg_23_private_path_inside_a_url_refuses_the_post(repo):
    # A URL is not a way round the private-path check: the path part of a
    # non-web URL is checked like any other path, and a web link into
    # .compass/private/ is refused by its name.
    from compass_pkg import publish_check
    (repo / ".gitignore").write_text("notes/private/\n")
    commit_all(repo, "ignore")
    root = str(repo)
    inside = Path(root).resolve() / "notes" / "private" / "brief.md"
    refused = ("see file:///Users/j/r/.compass/private/x.yml",
               "see vscode://file/Users/j/r/.compass/private/x.yml",
               "see https://github.com/o/r/blob/main/.compass/private/x.yml",
               "see http://example.com/.compass/private/x.yml?raw=1.",
               f"see file://{inside}")
    for text in refused:
        for texts in ({"comment": text, "body": None}, {"comment": "ok", "body": text}):
            found = publish_check.check(texts, root)
            assert found is not None and found.check == "private-path", (text, texts)
    allowed = ("see https://github.com/o/r/blob/main/docs/guide.md",
               "see https://example.com/notes/private/a.md",
               "see https://github.com/o/r/tree/main/.compass/private/",
               f"see file://{Path(root).resolve() / 'docs' / 'guide.md'}")
    for text in allowed:
        assert publish_check.check({"comment": text, "body": None}, root) is None, text


_EQUIVALENT_FORMS = (
    "https://github.com/o/r/blob/main/%2Ecompass/private/x.yml",
    "https://github.com/o/r/blob/main/.compass%2Fprivate/x.yml",
    "https://github.com/o/r/blob/main/%252Ecompass/private/x.yml",
    "file:///Users/j/r/%2Ecompass/private/x.yml",
    "file://{root}/notes/%70rivate/brief.md",
    "file://{root}/notes/%2570rivate/brief.md",
    ".compass%2Fprivate/x.yml",
    "%2Ecompass/private/x.yml",
    "{root}/docs/../notes/private/brief.md",
    "file://{root}/docs/../notes/private/brief.md",
    "docs/../notes/private/brief.md",
    "https://h/a/.compass/./private/x.yml",
    "https://h/a/.compass//private/x.yml",
    ".compass//private/x.yml",
    ".compass/./private/x.yml",
)


@pytest.mark.parametrize("form", _EQUIVALENT_FORMS)
def test_ipg_24_equivalent_forms_of_a_private_path_refuse_the_post(repo, form):
    # A private path is checked in the form it resolves to: percent-encoding,
    # "./", "//" and ".." do not hide it from either check.
    from compass_pkg import publish_check
    (repo / ".gitignore").write_text("notes/private/\n")
    commit_all(repo, "ignore")
    root = str(Path(repo).resolve())
    text = "see " + form.format(root=root)
    for texts in ({"comment": text, "body": None}, {"comment": "ok", "body": text}):
        found = publish_check.check(texts, root)
        assert found is not None and found.check == "private-path", (text, texts)
    for allowed in ("see https://github.com/o/r/blob/main/docs/guide.md",
                    "see https://github.com/o/r/blob/main/docs/%67uide.md",
                    "see docs/./guide.md"):
        assert publish_check.check({"comment": allowed, "body": None}, root) is None, allowed


_ENTITY_BACKSLASH_SLASH_FORMS = (
    "&#46;compass/private/x.yml",
    "[x](&#46;compass/private/x.yml)",
    "https://github.com/o/r/blob/main/&#46;compass/private/x.yml",
    "&amp;#46;compass/private/x.yml",
    "%26%2346%3Bcompass/private/x.yml",
    "&period;compass/private/x.yml",
    "notes/&#112;rivate/brief.md",
    "https://github.com/o/r/blob/main/.compass\\private/x.yml",
    "https://github.com/o/r/blob/main/.compass%5Cprivate/x.yml",
    ".compass/private/x.yml/",
    ".compass/private/x.yml/.",
)
#: Texts that must still post: a tracked symlink into an ignored folder is
#: asked of git as written, and an anchor is not part of a path.
_POSTED_FORMS = (
    "bin/tool",
    "docs/guide.md#usage",
    "https://github.com/o/r/blob/main/docs/guide.md#usage",
)


@pytest.mark.parametrize("form,refused",
                         [(f, True) for f in _ENTITY_BACKSLASH_SLASH_FORMS]
                         + [(f, False) for f in _POSTED_FORMS])
def test_ipg_25_entity_backslash_and_trailing_slash_forms_refuse_and_a_tracked_symlink_posts(
        repo, form, refused):
    # HTML entities, a backslash in a web link and a trailing "/" or "/." do
    # not hide a private path; a tracked symlink is asked of git as written,
    # so one pointing into an ignored folder still posts.
    from compass_pkg import publish_check
    (repo / ".gitignore").write_text("notes/private/\nbuild/\n")
    (repo / "build").mkdir()
    (repo / "build" / "tool").write_text("built\n")
    (repo / "bin").mkdir()
    os.symlink(os.path.join("..", "build", "tool"), repo / "bin" / "tool")
    commit_all(repo, "ignore build; track the bin/tool symlink")
    root = str(Path(repo).resolve())
    text = "see " + form
    for texts in ({"comment": text, "body": None}, {"comment": "ok", "body": text}):
        found = publish_check.check(texts, root)
        if refused:
            assert found is not None and found.check == "private-path", (text, texts)
        else:
            assert found is None, (text, texts, found)


#: Every form the four reviews of this issue's pull request found, for a file
#: under .compass/private/ and for a git-ignored file. Each must refuse.
_REVIEWED_REFUSED = (
    # inside a URL
    ".compass/private/x.yml",
    "file:///Users/j/r/.compass/private/x.yml",
    "vscode://file/Users/j/r/.compass/private/x.yml",
    "https://github.com/o/r/blob/main/.compass/private/x.yml",
    "http://example.com/.compass/private/x.yml?raw=1.",
    "file://{root}/notes/private/brief.md",
    "vscode://file{root}/build/tool",
    # percent-encoding, single, double and mixed case
    "https://github.com/o/r/blob/main/%2Ecompass/private/x.yml",
    "https://github.com/o/r/blob/main/%2ecompass/private/x.yml",
    "https://github.com/o/r/blob/main/.compass%2Fprivate/x.yml",
    "https://github.com/o/r/blob/main/%252Ecompass/private/x.yml",
    "file:///Users/j/r/%2Ecompass/private/x.yml",
    "file://{root}/notes/%70rivate/brief.md",
    "file://{root}/notes/%2570rivate/brief.md",
    "notes/%70rivate/brief.md",
    "%0A.compass/private/k.yml",
    "notes/private/brief.md%00",
    # HTML entities
    "&#46;compass/private/x.yml",
    "[x](&#46;compass/private/x.yml)",
    "https://github.com/o/r/blob/main/&#46;compass/private/x.yml",
    "&amp;#46;compass/private/x.yml",
    "%26%2346%3Bcompass/private/x.yml",
    "&period;compass/private/x.yml",
    "notes/&#112;rivate/brief.md",
    # backslash
    "https://github.com/o/r/blob/main/.compass\\private/x.yml",
    "https://github.com/o/r/blob/main/.compass%5Cprivate/x.yml",
    # dot segments and doubled slashes
    "{root}/docs/../notes/private/brief.md",
    "file://{root}/docs/../notes/private/brief.md",
    "docs/../notes/private/brief.md",
    "docs/../build/tool",
    "https://h/a/.compass/./private/x.yml",
    "https://h/a/.compass//private/x.yml",
    ".compass//private/x.yml",
    ".compass/./private/x.yml",
    # trailing slash
    ".compass/private/x.yml/",
    ".compass/private/x.yml/.",
    # joined to a word
    "x;.compass/private/k.yml",
    "a&.compass/private/k.yml",
    "Q#.compass/private/k.yml",
    "x;build/tool",
    "#build/tool",
    "see&amp;build/tool",
    "a&notes/private/brief.md",
    # an encoded control character before the path
    "&#10;.compass/private/k.yml",
    "&#0;.compass/private/k.yml",
    "&#10;build/tool",
    "&#0;build/tool",
    # a tracked symlink into the private folder, and the ignored file itself
    "lnk/k",
    "build/tool",
)
#: Texts that must post: links to published files, a tracked symlink to an
#: ignored target, and folders named with no file.
_REVIEWED_POSTED = (
    "https://github.com/o/r/blob/main/docs/guide.md",
    "https://github.com/o/r/blob/main/docs/%67uide.md",
    "https://github.com/o/r/blob/main/docs/guide.md#usage",
    "https://example.com/notes/private/a.md",
    "https://github.com/o/r/tree/main/.compass/private/",
    "file://{root}/docs/guide.md",
    "bin/tool",
    "docs/guide.md#usage",
    "docs/./guide.md",
    "`.compass/private/`",
    "notes/private/",
    "the build folder",
)


@pytest.mark.parametrize("form,refused",
                         [(f, True) for f in _REVIEWED_REFUSED]
                         + [(f, False) for f in _REVIEWED_POSTED])
def test_ipg_26_every_form_found_in_review_is_refused_and_a_published_link_posts(
        repo, form, refused):
    # The whole text is decoded before any path is picked out of it, so no
    # spelling of a private path, and no word joined to one, gets it past.
    from compass_pkg import publish_check
    (repo / ".gitignore").write_text("notes/private/\nbuild/\n")
    (repo / "build").mkdir()
    (repo / "build" / "tool").write_text("built\n")
    (repo / "bin").mkdir()
    os.symlink(os.path.join("..", "build", "tool"), repo / "bin" / "tool")
    (repo / "lnk").mkdir()
    os.symlink(os.path.join("..", ".compass", "private", "k.yml"), repo / "lnk" / "k")
    commit_all(repo, "ignore build; track the bin/tool and lnk/k symlinks")
    root = str(Path(repo).resolve())
    text = "see " + form.format(root=root)
    for texts in ({"comment": text, "body": None}, {"comment": "ok", "body": text}):
        found = publish_check.check(texts, root)
        if refused:
            assert found is not None and found.check == "private-path", (text, texts)
        else:
            assert found is None, (text, texts, found)


def test_ipg_18_credential_refuses_the_post(repo, gh):
    from compass_pkg import publish_check
    page_issue(repo, gh, page=False)
    token = "ghp_" + "Ab3" * 12
    ok(run(repo, gh, "issue", "decision", "add", "D-1", "--question", "Which key?",
           "--resolution", f"use {token}", "--by", "planner", "--stage", "plan",
           "--issue", SLUG))
    render(repo, gh)
    settings(repo)
    result = ok(run(repo, gh, "issue", "status", "set", "backlog", "--issue", SLUG))
    assert api_calls(gh) == []
    lines = [x for x in result.stderr.splitlines() if x.strip()]
    assert len(lines) == 1 and "credential" in lines[0], result.stderr
    assert "decisions" in lines[0]
    assert token not in result.stderr and token not in json.dumps(record(repo))
    refusal = publish_check.check({"comment": "x", "body": "key " + token}, str(repo))
    assert refusal.check == "credential" and "issue body" in refusal.line


def _big_readme(root, slug=SLUG, chart_line=None, rows=0, chart=0):
    """Grow the README on disk: `chart` lines in the traceability chart and `rows`
    rows in the artifacts table."""
    path = docs_dir(root, slug) / "README.md"
    text = path.read_text(encoding="utf-8")
    filler = "\n".join([f'  n{i} ==> m{i}["{"x" * 90}"]' for i in range(chart)]
                       + ([chart_line] if chart_line else []))
    text = text.replace("```mermaid\nflowchart LR\n", "```mermaid\nflowchart LR\n"
                        + filler + "\n", 1)
    table = "\n".join(f"| [doc-{i}](doc-{i}.md) | draft | - | {'y' * 120} |"
                      for i in range(rows))
    text = re.sub(r"(\| verification-note \|[^\n]*)", r"\1\n" + table, text, count=1)
    path.write_text(text, encoding="utf-8")
    return text


def test_ipg_19_comment_stays_within_the_size_limit(repo, gh):
    from compass_pkg import github_page
    # Five scenarios: everything is posted.
    page_issue(repo, gh)
    for n in range(2, 6):
        ok(run(repo, gh, "scenario", "add", f"TRC-{n}", "--title", f"S{n}", "--intent",
               "INT-1", "--test", f"tests/test_{n}.py", "--issue", SLUG))
    render(repo, gh)
    ok(gsync(repo, gh))
    body = ours(gh)[0]["body"]
    assert "```mermaid" in body and "| Document | Status |" in body
    # Sixty-eight scenarios, each with two tests and a green record, fit: past 25
    # scenarios the render draws one summary node per intent, so the README stays small.
    big = "big-issue"
    make_issue(repo, gh, slug=big)

    def many(m):
        m["scenarios"] = [{"id": f"TRC-{n:03d}", "title": f"Scenario {n} " + "w" * 60,
                           "intent": "INT-1", "tests": [f"tests/test_{n}.py::test_a",
                                                        f"tests/test_{n}.py::test_b"]}
                          for n in range(1, 69)]
    edit_manifest(repo, many, slug=big)
    evidence = repo / ".compass" / "work" / big / "evidence"
    evidence.mkdir(exist_ok=True)
    for n in range(1, 69):
        (evidence / f"green-TRC-{n:03d}.json").write_text(json.dumps(
            {"scenario": f"TRC-{n:03d}", "command": "true", "exit_code": 0}))
    render(repo, gh, big)
    link(repo, gh, "acme/widgets#43", big)
    ok(gsync(repo, gh, slug=big))
    posted = ours(gh, "acme/widgets#43")[0]["body"]
    assert "68 of 68 scenarios passed" in posted and len(posted) <= github_page.LIMIT
    assert "left out" not in posted and "```mermaid" in posted
    # A traceability chart past the limit is the first block left out.
    before = _big_readme(repo, chart=700)
    assert len(before) > github_page.LIMIT
    ok(gsync(repo, gh))
    body = ours(gh)[0]["body"]
    assert len(body) <= github_page.LIMIT and body.startswith(MARKER + "\n")
    assert "traceability chart is left out" in body and "n1 ==>" not in body
    assert "| Document | Status |" in body
    assert readme(repo) == before
    # Still too long: the artifacts table is reduced to links.
    render(repo, gh)
    before = _big_readme(repo, chart=700, rows=500)
    ok(gsync(repo, gh))
    body = ours(gh)[0]["body"]
    assert len(body) <= github_page.LIMIT
    assert "traceability chart is left out" in body
    assert "| Document | Status |" not in body and "`" in body
    assert "first column" in body
    assert readme(repo) == before
    # Too long after both: refused, with the size and the limit.
    path = docs_dir(repo) / "README.md"
    path.write_text(before + "\n" + ("z" * 100 + "\n") * 700, encoding="utf-8")
    clear_calls(gh)
    result = run(repo, gh, "issue", "github", "sync", "--issue", SLUG)
    assert result.returncode != 0
    assert "65536" in result.stdout + result.stderr
    assert not [c for c in api_calls(gh) if "PATCH" in c or "POST" in c]
    # A chart that alone names an ignored file is left out, so the post goes ahead.
    (repo / ".gitignore").write_text("notes/private/\n")
    path.write_text(before, encoding="utf-8")
    render(repo, gh)
    _big_readme(repo, chart=700, chart_line='  p ==> q["notes/private/brief.md"]')
    ok(gsync(repo, gh))
    assert "notes/private" not in ours(gh)[0]["body"]


# --- group D: settings and documentation ------------------------------------------

def test_ipg_20_page_switch_is_declared(repo, gh):
    from compass_pkg import catalogue_spec, github_page
    assert "page" in catalogue_spec.GITHUB_LABEL_SWITCHES
    schema = json.loads((ROOT / "schemas" / "compass.schema.json").read_text())
    node = schema["properties"]["github_labels"]["properties"]["page"]
    assert node["type"] == "boolean" and node["default"] is False
    assert "`false`" in node["description"]
    assert "page" in schema["properties"]["github_labels"]["description"]
    configuration = (ROOT / "docs" / "configuration.md").read_text()
    table = configuration.split("## Settings", 1)[1].split("\n###", 1)[0]
    row = [x for x in table.splitlines() if x.startswith("| `github_labels` |")][0]
    assert "`page`" in row
    section = configuration.split("### `github_labels`", 1)[1].split("\n### ", 1)[0]
    assert "- `page`:" in section
    make_issue(repo, gh)
    settings(repo, page=True)
    ok(run(repo, gh, "policy", "lint"))
    for value, on in ((True, True), (False, False), ("'yes'", False), ("1", False),
                      ("'true'", False), (None, False)):
        settings(repo, page=value)
        assert github_page.page_on(str(repo)) is on, value
