"""`compass issue link set` stores an issue's link to its GitHub issue.

Every test runs the real CLI against a fake `gh` on PATH (tests/fake_gh.py),
which records each call, so no test reaches the network. `FakeGh` and the
helpers here are also used by test_land_commit_from_pr.py.

Scenario ids: GLS-1, GLS-2, GLS-11, GLS-12 and GLS-14 (issue `github-label-sync`),
kept when 9.0.0 removed the label sync (ADR-093).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_quick_fix_verbs import _manifest, _save_manifest, repo  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
FAKE_GH = ROOT / "tests" / "fake_gh.py"
SLUG = "sync-me"
TARGET = "acme/widgets#42"
KEY = "acme/widgets#42"


class FakeGh:
    """A fake `gh` on PATH, its recorded calls and the GitHub state it holds."""

    def __init__(self, base):
        self.dir = base / "ghstate"
        self.bin = base / "ghbin"
        self.empty = base / "nogh"
        for folder in (self.dir, self.bin, self.empty):
            folder.mkdir()
        self.set_labels([], repo_labels=[])
        (self.dir / "calls.jsonl").write_text("")
        script = self.bin / "gh"
        script.write_text(
            f"#!{sys.executable}\nimport runpy, sys\n"
            f"sys.exit(runpy.run_path({str(FAKE_GH)!r}, run_name='fake_gh')"
            "['main'](sys.argv[1:]))\n")
        script.chmod(0o755)
        # A PATH with `git` and no `gh`: the commands under test may call git.
        git = shutil.which("git")
        if git:
            (self.empty / "git").symlink_to(git)

    def env(self, mode="", present=True):
        env = dict(os.environ)
        env["GH_FAKE_DIR"] = str(self.dir)
        env["GH_FAKE_MODE"] = mode
        env.pop("COMPASS_ISSUE", None)
        if present:
            env["PATH"] = str(self.bin) + os.pathsep + env.get("PATH", "")
        else:
            env["PATH"] = str(self.empty)
        return env

    def calls(self):
        text = (self.dir / "calls.jsonl").read_text()
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def state(self):
        return json.loads((self.dir / "state.json").read_text())

    def set_labels(self, labels, repo_labels=None, key=KEY):
        state = {"repo_labels": [], "issues": {}}
        path = self.dir / "state.json"
        if path.exists():
            state = self.state()
        state["issues"][key] = list(labels)
        if repo_labels is not None:
            state["repo_labels"] = list(repo_labels)
        else:
            state["repo_labels"] = sorted(set(state["repo_labels"]) | set(labels))
        path.write_text(json.dumps(state))


@pytest.fixture
def gh(tmp_path):
    return FakeGh(tmp_path)


def run(root, gh, *args, mode="", present=True):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True,
                          env=gh.env(mode, present))


def make_issue(repo, gh, labels="infra,ci", slug=SLUG):
    """An assessed issue in a git project with no settings file."""
    result = run(repo, gh, "quick-fix", "start", slug,
                 "--risk", "trivial - one line", "--familiarity",
                 "brownfield-mapped - the file and its test exist",
                 "--size", "atomic - one line", "--intent", "it works",
                 "--scenario", "Given a line, when read, then it is right.",
                 "--scenario-id", "TRC-001", "--test", "tests/test_x.py",
                 "--labels", labels)
    assert result.returncode == 0, result.stdout + result.stderr
    return repo


def link(root, gh, target=TARGET, slug=SLUG):
    # `--github=TARGET`: a target that starts with a dash is then the option's
    # value, so the command's own check refuses it, not the argument parser.
    return run(root, gh, "issue", "link", "set", f"--github={target}", "--issue", slug)


def edit_manifest(root, change, slug=SLUG):
    data = _manifest(root, slug)
    change(data)
    _save_manifest(root, slug, data)


def _issue_link():
    sys.path.insert(0, str(ROOT / "cli"))
    try:
        import compass_pkg  # noqa: F401
        from compass_pkg import issue_link
        return issue_link
    finally:
        sys.path.remove(str(ROOT / "cli"))


# --- the link ------------------------------------------------------------------

def test_gls_1_link_by_repo_number_or_url(repo, gh):
    make_issue(repo, gh)
    result = link(repo, gh, "acme/widgets#42")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo, SLUG)["github"] == {"repo": "acme/widgets", "number": 42}
    lint = run(repo, gh, "issue", "lint", "--issue", SLUG)
    assert lint.returncode == 0, lint.stdout + lint.stderr
    result = link(repo, gh, "https://github.com/acme/widgets/issues/43")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo, SLUG)["github"] == {"repo": "acme/widgets", "number": 43}
    assert gh.calls() == []


BAD_TARGETS = [
    "acme/widgets;rm#1", "-x/widgets#1", "acme/widgets#0", "acme/widgets",
    "https://example.com/acme/widgets/issues/1", "acme/wid gets#1",
    "acme/widgets#12abc", "$(id)/x#1", "acme/../x#1", "acme/widgets#1 --extra",
    "acme/.#1", "#5", "",
]


def test_gls_2_link_refuses_unsafe_or_malformed_targets(repo, gh):
    make_issue(repo, gh)
    for bad in BAD_TARGETS:
        result = link(repo, gh, bad)
        assert result.returncode != 0, bad
        assert "owner/repo#" in result.stdout + result.stderr, bad
        assert "github" not in _manifest(repo, SLUG), bad
    assert gh.calls() == []


def test_gls_1_the_schema_pattern_refuses_what_the_code_refuses():
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text())
    pattern = schema["properties"]["github"]["properties"]["repo"]["pattern"]
    for bad in ("acme/-w", "acme/..", "acme/.", "-x/widgets", "acme/", "acme"):
        assert not re.search(pattern, bad), bad
    for good in ("acme/widgets", "acme/.github", "a/b.c_d-e"):
        assert re.search(pattern, good), good


def test_gls_12_a_malformed_link_is_named_not_blamed_on_github(repo, gh):
    make_issue(repo, gh)
    assert link(repo, gh).returncode == 0
    edit_manifest(repo, lambda m: m.update(github={"repo": "acme/-w", "number": 1}))
    # The exit code depends on whether the optional jsonschema package is
    # installed, so only the output is checked: the lint asks GitHub nothing.
    lint = run(repo, gh, "issue", "lint", "--issue", SLUG)
    assert "on GitHub" not in lint.stdout, lint.stdout
    assert gh.calls() == []
    issue_link = _issue_link()
    with pytest.raises(issue_link.SyncError, match="the manifest's `github` field"):
        issue_link.link_of(_manifest(repo, SLUG))


# --- what 9.0.0 removed -----------------------------------------------------------

def test_linking_writes_no_label_when_the_old_setting_is_on(repo, gh):
    make_issue(repo, gh)
    (repo / "compass.yml").write_text("schema: 1\ngithub_labels:\n  domain: true\n"
                                      "  status: true\n")
    assert link(repo, gh).returncode == 0
    evaluated = run(repo, gh, "approach", "evaluate", "--issue", SLUG, "--write")
    assert evaluated.returncode == 0, evaluated.stdout + evaluated.stderr
    assert gh.calls() == []
    lint = run(repo, gh, "policy", "lint")
    assert "L-SETTING-REMOVED" in lint.stdout + lint.stderr, lint.stdout + lint.stderr
    assert "ADR-093" in lint.stdout + lint.stderr
    sync = run(repo, gh, "issue", "github", "sync", "--issue", SLUG)
    assert sync.returncode == 2
    assert ("'compass issue github sync' was removed in 9.0.0 (ADR-093)"
            in sync.stderr), sync.stderr
    assert gh.calls() == []


# --- gh ----------------------------------------------------------------------------

def test_gls_11_gh_timeout_is_fifteen_seconds():
    assert _issue_link()._TIMEOUT == 15
    assert "15 seconds" in (ROOT / "docs" / "github-links.md").read_text()


def test_gls_14_gh_is_run_with_an_argument_list_and_no_stored_token():
    for name in ("issue_link.py", "pull_request_link.py"):
        source = (ROOT / "cli" / "compass_pkg" / name).read_text()
        for forbidden in ("shell=True", "os.system", "os.popen", "GH_TOKEN", "GITHUB_TOKEN",
                          "hosts.yml", "auth token"):
            assert forbidden not in source, (name, forbidden)
