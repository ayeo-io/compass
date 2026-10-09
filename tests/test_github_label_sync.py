"""Compass writes an issue's domain labels and workflow state to its GitHub issue.

A project opts in with `github_labels` in `compass.yml`. Every test runs the
real CLI against a fake `gh` on PATH (tests/fake_gh.py), which records each
call, so no test reaches the network.

Scenario ids: GLS-1 to GLS-16 (issue `github-label-sync`).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

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
        env["FAKE_GH_DIR"] = str(self.dir)
        env["FAKE_GH_MODE"] = mode
        env.pop("COMPASS_ISSUE", None)
        if present:
            env["PATH"] = str(self.bin) + os.pathsep + env.get("PATH", "")
        else:
            env["PATH"] = str(self.empty)
        return env

    def calls(self):
        text = (self.dir / "calls.jsonl").read_text()
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def writes(self):
        return [c for c in self.calls() if c[:2] in (["label", "create"], ["issue", "edit"])]

    def state(self):
        return json.loads((self.dir / "state.json").read_text())

    def labels(self, key=KEY):
        return set(self.state()["issues"].get(key, []))

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


def settings(root, domain=True, status=True, extra=""):
    (root / "compass.yml").write_text(
        "schema: 1\ngithub_labels:\n"
        f"  domain: {str(domain).lower()}\n  status: {str(status).lower()}\n" + extra)


def link(root, gh, target=TARGET, slug=SLUG):
    # `--github=TARGET`: a target that starts with a dash is then the option's
    # value, so the command's own check refuses it, not the argument parser.
    return run(root, gh, "issue", "link", f"--github={target}", "--issue", slug)


def sync(root, gh, slug=SLUG, **kw):
    return run(root, gh, "issue", "labels", "sync", "--issue", slug, **kw)


def edit_manifest(root, change, slug=SLUG):
    data = _manifest(root, slug)
    change(data)
    _save_manifest(root, slug, data)


def status_labels(labels):
    return {name for name in labels if name.startswith("status:")}


def ready_project(repo, gh, labels="infra,ci"):
    """A linked issue with both switches on and its labels already written."""
    make_issue(repo, gh, labels)
    assert link(repo, gh).returncode == 0
    settings(repo)
    assert sync(repo, gh).returncode == 0
    return repo


# --- group A: the link ---------------------------------------------------------

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


# --- group B: writing labels ---------------------------------------------------

OFF_SETTINGS = {
    "none": None,
    "both-false": "schema: 1\ngithub_labels:\n  domain: false\n  status: false\n",
    "not-booleans": "schema: 1\ngithub_labels:\n  domain: 'yes'\n  status: 1\n",
    "empty-key": "schema: 1\ngithub_labels: {}\n",
}


@pytest.mark.parametrize("name", sorted(OFF_SETTINGS))
def test_gls_3_off_by_default_no_command_calls_gh(repo, gh, name):
    make_issue(repo, gh)
    text = OFF_SETTINGS[name]
    if text is not None:
        (repo / "compass.yml").write_text(text)
    assert link(repo, gh).returncode == 0
    for args in (["approach", "evaluate", "--write"],
                 ["issue", "status", "set", "backlog"],
                 ["issue", "status", "remove"],
                 ["issue", "status", "set", "done", "--close-reason", "not-planned"],
                 ["issue", "status", "remove"],
                 ["issue", "labels", "sync"],
                 ["issue", "lint"]):
        result = run(repo, gh, *args, "--issue", SLUG)
        assert result.returncode == 0, (args, result.stdout + result.stderr)
    assert gh.calls() == [], gh.calls()


def test_gls_4_both_on_assess_writes_domain_and_status_labels(repo, gh):
    make_issue(repo, gh, labels="infra,ci,zzz-undeclared")
    assert link(repo, gh).returncode == 0
    settings(repo)
    result = run(repo, gh, "approach", "evaluate", "--issue", SLUG, "--write")
    assert result.returncode == 0, result.stdout + result.stderr
    assert gh.labels() == {"infra", "ci", "status:ready"}
    created = {c[2]: c[c.index("--color") + 1]
               for c in gh.calls() if c[:2] == ["label", "create"]}
    assert set(created) == {"infra", "ci", "status:ready"}
    assert created["infra"] == created["ci"] != created["status:ready"]
    assert "zzz-undeclared" not in json.dumps(gh.calls())
    again = run(repo, gh, "approach", "evaluate", "--issue", SLUG, "--write")
    assert again.returncode == 0, again.stdout + again.stderr
    before = len(gh.writes())
    assert sync(repo, gh).returncode == 0
    assert len(gh.writes()) == before, "a sync with nothing to change writes nothing"


def test_gls_5_status_label_follows_the_state(repo, gh):
    ready_project(repo, gh)
    assert status_labels(gh.labels()) == {"status:ready"}
    edit_manifest(repo, lambda m: m.update(current_phase="implement"))
    assert sync(repo, gh).returncode == 0
    assert status_labels(gh.labels()) == {"status:in-progress"}
    held = run(repo, gh, "issue", "status", "set", "backlog", "--issue", SLUG)
    assert held.returncode == 0, held.stdout + held.stderr
    assert status_labels(gh.labels()) == {"status:backlog"}
    freed = run(repo, gh, "issue", "status", "remove", "--issue", SLUG)
    assert freed.returncode == 0, freed.stdout + freed.stderr
    assert status_labels(gh.labels()) == {"status:in-progress"}
    edit_manifest(repo, lambda m: m.update(current_phase="verify"))
    assert sync(repo, gh).returncode == 0
    assert status_labels(gh.labels()) == {"status:in-review"}
    assert {"infra", "ci"} <= gh.labels()


def test_gls_6_close_sets_done_and_close_reason_labels(repo, gh):
    ready_project(repo, gh)
    edit_manifest(repo, lambda m: m.update(current_phase="implement"))
    assert sync(repo, gh).returncode == 0
    assert status_labels(gh.labels()) == {"status:in-progress"}
    closed = run(repo, gh, "issue", "status", "set", "done",
                 "--close-reason", "not-planned", "--issue", SLUG)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert gh.labels() >= {"status:done", "close:not-planned", "infra", "ci"}
    assert status_labels(gh.labels()) == {"status:done"}
    reopened = run(repo, gh, "issue", "status", "remove", "--issue", SLUG)
    assert reopened.returncode == 0, reopened.stdout + reopened.stderr
    assert status_labels(gh.labels()) == {"status:in-progress"}
    assert not {name for name in gh.labels() if name.startswith("close:")}

    def pass_every_gate(manifest):
        for gate in manifest["gates"]:
            gate["status"] = "pass"

    edit_manifest(repo, pass_every_gate)
    completed = run(repo, gh, "issue", "status", "set", "done",
                    "--close-reason", "completed", "--issue", SLUG)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert gh.labels() >= {"status:done", "close:completed"}
    assert status_labels(gh.labels()) == {"status:done"}


def test_gls_7_each_switch_works_alone(repo, gh):
    make_issue(repo, gh)
    assert link(repo, gh).returncode == 0
    settings(repo, domain=True, status=False)
    assert sync(repo, gh).returncode == 0
    assert gh.labels() == {"infra", "ci"}
    gh.set_labels([])
    settings(repo, domain=False, status=True)
    assert sync(repo, gh).returncode == 0
    assert gh.labels() == {"status:ready"}


def test_gls_8_only_owned_labels_are_removed(repo, gh):
    make_issue(repo, gh, labels="infra,zzz-undeclared")
    assert link(repo, gh).returncode == 0
    settings(repo)
    foreign = {"bug", "customer-x", "zzz-undeclared", "statusquo", "status:custom"}
    gh.set_labels(sorted(foreign | {"ci", "status:in-review", "close:completed"}))
    result = sync(repo, gh)
    assert result.returncode == 0, result.stdout + result.stderr
    assert gh.labels() == foreign | {"infra", "status:ready"}
    removed = [name for c in gh.calls() if c[:2] == ["issue", "edit"]
               for name in c if name in foreign]
    assert removed == []


def test_gls_9_record_changing_commands_sync(repo, gh):
    ready_project(repo, gh)
    assert status_labels(gh.labels()) == {"status:ready"}
    added =run(repo, gh, "issue", "subtask", "add", "subtask-1", "--brief", "README.md",
                "--model", "m", "--budget", "0", "--issue", SLUG)
    assert added.returncode == 0, added.stdout + added.stderr
    assert status_labels(gh.labels()) == {"status:in-progress"}
    import importlib
    import pkgutil
    sys.path.insert(0, str(ROOT / "cli"))
    try:
        import compass_pkg
        from compass_pkg import github_labels
        defined = set()
        for info in pkgutil.iter_modules(compass_pkg.__path__):
            module = importlib.import_module(f"compass_pkg.{info.name}")
            defined |= {name for name in github_labels.TRIGGERS if hasattr(module, name)}
    finally:
        sys.path.remove(str(ROOT / "cli"))
    assert defined == set(github_labels.TRIGGERS)


# --- group C: failure and drift ------------------------------------------------

def _one_line_about_github(result):
    lines = [line for line in result.stderr.splitlines() if "github" in line.lower()]
    assert len(lines) == 1, result.stderr
    return lines[0]


def test_gls_10_missing_gh_never_fails_the_command(repo, gh):
    make_issue(repo, gh)
    assert link(repo, gh).returncode == 0
    settings(repo)
    result = run(repo, gh, "issue", "status", "set", "backlog", "--issue", SLUG,
                 present=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _manifest(repo, SLUG)["status"] == "backlog"
    line = _one_line_about_github(result)
    assert "gh" in line and "not installed" in line, line
    lint = run(repo, gh, "issue", "lint", "--issue", SLUG, present=False)
    assert lint.returncode == 0, lint.stdout + lint.stderr
    assert "out of sync" in lint.stdout
    assert gh.calls() == []


def test_gls_11_failing_gh_is_reported_and_recovers(repo, gh):
    make_issue(repo, gh)
    assert link(repo, gh).returncode == 0
    settings(repo)
    result = run(repo, gh, "issue", "status", "set", "backlog", "--issue", SLUG,
                 mode="unauth")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "not logged in" in _one_line_about_github(result)
    lint = run(repo, gh, "issue", "lint", "--issue", SLUG, mode="unauth")
    assert lint.returncode == 0
    assert "out of sync" in lint.stdout and "not logged in" in lint.stdout
    down = run(repo, gh, "issue", "status", "remove", "--issue", SLUG, mode="down")
    assert down.returncode == 0, down.stdout + down.stderr
    assert "api.github.com" in _one_line_about_github(down)
    fixed = sync(repo, gh)
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    assert gh.labels() == {"infra", "ci", "status:ready"}
    clean = run(repo, gh, "issue", "lint", "--issue", SLUG)
    assert clean.returncode == 0
    assert "out of sync" not in clean.stdout


def test_gls_12_drift_is_reported_and_not_pulled_back(repo, gh):
    ready_project(repo, gh)
    quiet = run(repo, gh, "issue", "lint", "--issue", SLUG)
    assert quiet.returncode == 0 and "out of sync" not in quiet.stdout
    gh.set_labels(sorted(gh.labels() - {"infra"}))
    writes = len(gh.writes())
    lint = run(repo, gh, "issue", "lint", "--issue", SLUG)
    assert lint.returncode == 0, lint.stdout + lint.stderr
    assert "out of sync" in lint.stdout and "infra" in lint.stdout
    assert "infra" not in gh.labels()
    assert len(gh.writes()) == writes, "the lint must not write to GitHub"
    assert "infra" in _manifest(repo, SLUG)["assessment"]["labels"]
    fixed = sync(repo, gh)
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    assert "infra" in gh.labels()


def test_gls_13_labels_sync_refuses_what_it_cannot_do(repo, gh):
    make_issue(repo, gh)
    settings(repo)
    unlinked = sync(repo, gh)
    assert unlinked.returncode != 0
    assert "compass issue link" in unlinked.stdout + unlinked.stderr
    (repo / "compass.yml").unlink()
    assert link(repo, gh).returncode == 0
    nothing = sync(repo, gh)
    assert nothing.returncode == 0, nothing.stdout + nothing.stderr
    assert "nothing" in (nothing.stdout + nothing.stderr).lower()
    assert gh.calls() == []
    settings(repo)
    failing = sync(repo, gh, mode="unauth")
    assert failing.returncode != 0
    assert "not logged in" in failing.stdout + failing.stderr


# --- group D: safety and documentation -----------------------------------------

def test_gls_14_gh_gets_argv_and_label_names_are_checked(repo, gh):
    make_issue(repo, gh)
    assert link(repo, gh).returncode == 0
    names = ["ok-label", "a;b", "x,y", "-dash", "$(id)"]
    settings(repo, extra="dimensions:\n  labels:\n    set:\n      common:\n        add: "
                         + json.dumps(names) + "\n")
    evaluated = run(repo, gh, "approach", "evaluate", "--issue", SLUG, "--write")
    assert evaluated.returncode == 0, evaluated.stdout + evaluated.stderr
    edit_manifest(repo, lambda m: m["assessment"].update(labels=list(names)))
    result = sync(repo, gh)
    assert result.returncode == 0, result.stdout + result.stderr
    line = _one_line_about_github(result)
    assert "skipped" in line, line
    sent = json.dumps(gh.calls())
    for bad in ("a;b", "x,y", "-dash", "$(id)"):
        assert bad not in sent, bad
    assert "ok-label" in gh.labels()
    for call in gh.calls():
        assert all(isinstance(word, str) for word in call)
        assert call[0] in ("label", "issue")
        assert call[call.index("--repo") + 1] == "acme/widgets"
    source = (ROOT / "cli" / "compass_pkg" / "github_labels.py").read_text()
    for forbidden in ("shell=True", "os.system", "os.popen", "GH_TOKEN", "GITHUB_TOKEN",
                      "hosts.yml", "auth token"):
        assert forbidden not in source, forbidden


def test_gls_15_settings_are_declared_and_documented(repo, gh):
    sys.path.insert(0, str(ROOT / "cli"))
    try:
        import compass_pkg
        from compass_pkg import catalogue_spec
        assert "github_labels" in catalogue_spec.SETTINGS_KEYS
    finally:
        sys.path.remove(str(ROOT / "cli"))
    schema = json.loads((ROOT / "schemas" / "compass.schema.json").read_text())
    node = schema["properties"]["github_labels"]
    assert node["description"]
    for name in ("domain", "status"):
        assert node["properties"][name]["description"]
        assert node["properties"][name]["type"] == "boolean"
    configuration = (ROOT / "docs" / "configuration.md").read_text()
    table = configuration.split("## Settings", 1)[1].split("\n###", 1)[0]
    assert "| `github_labels` |" in table
    make_issue(repo, gh)
    settings(repo)
    lint = run(repo, gh, "policy", "lint")
    assert lint.returncode == 0, lint.stdout + lint.stderr


def test_gls_16_glossary_and_docs_describe_the_sync():
    terms = yaml.safe_load((ROOT / "governance" / "terminology.yml").read_text())
    entry = None
    stack = [terms]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if isinstance(node.get("label"), dict) and "means" in node["label"]:
                entry = node["label"]
            stack.extend(node.values())
    assert entry is not None
    means = " ".join(entry["means"].split())
    assert "github_labels" in means and "status:" in means and "close:" in means
    assert "synced 1:1" not in means
    glossary = " ".join((ROOT / "docs" / "glossary.md").read_text().split())
    assert means in glossary
    readme = (ROOT / "docs" / "README.md").read_text()
    owning = readme.split("## Owning docs", 1)[1]
    assert "cli/compass_pkg/github_labels.py" in owning
    assert "docs/github-labels.md" in owning
    assert (ROOT / "docs" / "github-labels.md").is_file()
    walkthrough = ROOT / "docs" / "github-labels-walkthrough.md"
    assert walkthrough.is_file()
    text = walkthrough.read_text()
    for needle in ("compass.yml", "compass issue link", "compass issue labels sync",
                   "status:in-progress"):
        assert needle in text, needle
    assert "github-labels-walkthrough.md" in readme
