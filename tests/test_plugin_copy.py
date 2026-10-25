"""Each release publishes a smaller copy of Compass to the `plugin` branch.

The plugin directory holds a plugin of more than 512 files for a reviewer, and
an install downloaded the whole repository, tests included. So
`scripts/build-plugin-copy.py` makes a copy of only the files an installed
plugin reads, from one commit, checks it, and adds it as one commit to a
`plugin` branch with its own history. The marketplace entry fetches the plugin
from that branch.

The scenarios are in plugin-branch-release/acceptance-criteria.md. The tests
that write a branch or plant a failure work in a throwaway clone, so they
never move this repository's branches.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build-plugin-copy.py"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
IMAGES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")

_GIT_ENV = {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com"}


def _build(*args, repo=ROOT):
    env = {**os.environ, **_GIT_ENV}
    return subprocess.run([sys.executable, str(SCRIPT), "--repo", str(repo), *args],
                          capture_output=True, text=True, env=env, timeout=300)


def _git(repo, *args):
    env = {**os.environ, **_GIT_ENV}
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          env=env, check=True).stdout.strip()


@pytest.fixture(scope="module")
def copy_dir(tmp_path_factory):
    """Where the copy of HEAD is written, once for the module."""
    return tmp_path_factory.mktemp("copy") / "compass"


def _copy(folder: Path) -> Path:
    """The copy of HEAD in `folder`, built on first use. Built inside the
    test, so a build that fails is a failed test, not a setup error."""
    if not folder.exists():
        r = _build("--ref", "HEAD", "--out", str(folder))
        assert r.returncode == 0, r.stdout + r.stderr
    return folder


def _files(folder: Path) -> list[Path]:
    return [p for p in folder.rglob("*") if p.is_file()]


@pytest.fixture
def clone(tmp_path):
    """A throwaway clone of HEAD with no tags, so a test can tag and commit."""
    repo = tmp_path / "repo"
    subprocess.run(["git", "clone", "-q", "--no-tags", "--shared", str(ROOT), str(repo)],
                   check=True)
    return repo


def _plant(repo, rel, text):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", f"Plant {rel}")


def _bump(repo, version):
    """Commit a release of `version` in the clone: VERSION and plugin.json."""
    (repo / "VERSION").write_text(version + "\n", encoding="utf-8")
    manifest = repo / ".claude-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["version"] = version
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _git(repo, "add", "VERSION", ".claude-plugin/plugin.json")
    _git(repo, "commit", "-q", "-m", f"Release {version}")
    _git(repo, "tag", f"v{version}")


def test_trc_a1_the_copy_holds_only_runtime_files(copy_dir):
    """Scenario `TRC-A1`: no tests, docs, examples, architecture or decision
    records, 512 files or fewer, no non-image file over 256 KiB."""
    copy = _copy(copy_dir)
    rels = [p.relative_to(copy).as_posix() for p in _files(copy)]
    for left_out in ("tests/", "docs/", "examples/", "architecture/"):
        assert not [r for r in rels if r.startswith(left_out)], left_out
    # A decision record ships only when a shipped file sends the agent to it.
    named = " ".join(p.read_text(encoding="utf-8", errors="replace") for p in _files(copy)
                     if not p.suffix.lower() in IMAGES)
    records = [r for r in rels if r.startswith("governance/decisions/")]
    assert all(f"${{CLAUDE_PLUGIN_ROOT}}/{r}" in named for r in records), records
    assert len(rels) <= 512, len(rels)
    big = [r for r in rels if not r.endswith(IMAGES) and (copy / r).stat().st_size > 256 * 1024]
    assert not big, big


def test_trc_a2_the_copy_version_is_the_tag(copy_dir, clone):
    """Scenario `TRC-A2`: the copy's plugin.json names the release's version,
    and a tag whose number differs from VERSION is refused."""
    copy = _copy(copy_dir)
    manifest = json.loads((copy / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["version"] == VERSION
    _git(clone, "tag", f"v{VERSION}")
    assert _build("--ref", f"v{VERSION}", repo=clone).returncode == 0
    _git(clone, "tag", "v99.0.0")
    r = _build("--ref", "v99.0.0", repo=clone)
    assert r.returncode == 1
    assert "99.0.0" in r.stdout and VERSION in r.stdout, r.stdout


def test_trc_a3_every_named_path_is_in_the_copy():
    """Scenario `TRC-A3`: every path the copy reads from its own root exists
    in it; the build checks this and passes on HEAD."""
    r = _build("--ref", "HEAD")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "paths checked" in r.stdout, r.stdout


def test_trc_a4_the_cli_and_hooks_run_from_the_copy(copy_dir, tmp_path):
    """Scenario `TRC-A4`: the CLI and the session-start hook run from the
    copy, in a project that is not the repository."""
    copy = _copy(copy_dir)
    project = tmp_path / "proj"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA", "CLAUDE_PROJECT_DIR",
                        "COMPASS_ISSUE")}
    cli = [str(copy / "bin" / "compass")]
    for args in (["--version"], ["init"],
                 ["quick-fix", "start", "demo", "--risk", "trivial - a typo",
                  "--familiarity", "brownfield-mapped - one file", "--size", "atomic - one line",
                  "--intent", "the typo is fixed",
                  "--scenario", "Given a typo, When it is fixed, Then the word is right",
                  "--test", "tests/test_demo.py"]):
        r = subprocess.run(cli + args, cwd=project, env=env, capture_output=True, text=True,
                           timeout=120)
        assert r.returncode == 0, (args, r.stdout, r.stderr)
    hook = subprocess.run(["bash", str(copy / "hooks" / "session-start.sh")], input="{}",
                          cwd=project, env={**env, "CLAUDE_PROJECT_DIR": str(project)},
                          capture_output=True, text=True, timeout=60)
    assert hook.returncode == 0, hook.stderr
    assert "Compass operating contract" in hook.stdout


def test_trc_b1_a_release_adds_one_commit(clone):
    """Scenario `TRC-B1`: each release adds one commit whose tree is the copy
    and whose only parent is the previous copy, never a commit of main."""
    _git(clone, "tag", f"v{VERSION}")
    first = _build("--ref", f"v{VERSION}", "--commit", repo=clone)
    assert first.returncode == 0, first.stdout + first.stderr
    tip = _git(clone, "rev-parse", "refs/heads/plugin")
    assert _git(clone, "rev-list", "--count", "plugin") == "1"

    _plant(clone, "docs/new-page.md", "A new page that does not ship.\n")
    _bump(clone, "99.0.0")
    second = _build("--ref", "v99.0.0", "--commit", repo=clone)
    assert second.returncode == 0, second.stdout + second.stderr
    new = _git(clone, "rev-parse", "refs/heads/plugin")
    assert new != tip
    assert _git(clone, "rev-list", "--parents", "-n", "1", "plugin").split()[1:] == [tip]
    source = _git(clone, "rev-parse", "v99.0.0^{commit}")
    message = _git(clone, "log", "-1", "--format=%B", "plugin")
    assert "Source-tag: v99.0.0" in message and f"Source-commit: {source}" in message
    main_commits = set(_git(clone, "rev-list", "HEAD").split())
    assert not main_commits & set(_git(clone, "rev-list", "plugin").split())
    tree = _git(clone, "ls-tree", "-r", "--name-only", "plugin").split("\n")
    assert "docs/new-page.md" not in tree and "cli/compass" in tree


def test_trc_b2_the_marketplace_names_the_plugin_branch():
    """Scenario `TRC-B2`: the Compass entry fetches the plugin from the
    plugin branch and names no other version than plugin.json."""
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    entry = market["plugins"][0]
    assert entry["source"] == {"source": "github", "repo": "ayeo-io/compass", "ref": "plugin"}
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert entry.get("version", plugin["version"]) == plugin["version"]


@pytest.mark.skip(reason="TRC-B3 is checked by hand: the owner updates a profile from the "
                         "pushed plugin branch (docs/install-smoke-test.md), recorded as evidence")
def test_trc_b3_an_update_reads_the_branch():
    """Scenario `TRC-B3`: an update needs Claude Code, a network and the
    pushed branch, so the owner's run is the evidence."""


def test_trc_f1_a_missing_path_stops_the_build(clone):
    """Scenario `TRC-F1`: a command that names a plugin-root path the copy
    lacks stops the build, which names both, and no branch changes."""
    _plant(clone, "commands/zz-planted.md",
           "---\ndescription: planted\n---\nRead ${CLAUDE_PLUGIN_ROOT}/nowhere/missing.md\n")
    r = _build("--ref", "HEAD", "--commit", repo=clone)
    assert r.returncode == 1
    assert "nowhere/missing.md" in r.stdout and "commands/zz-planted.md" in r.stdout, r.stdout
    assert subprocess.run(["git", "-C", str(clone), "rev-parse", "--verify", "-q",
                           "refs/heads/plugin"], capture_output=True).returncode != 0


def test_trc_f2_a_copy_over_the_limits_stops_the_build(clone):
    """Scenario `TRC-F2`: a non-image file over 256 KiB, or more than 512
    files, stops the build with the limit named."""
    _plant(clone, "skills/zz-planted/big.md", "x" * (257 * 1024))
    r = _build("--ref", "HEAD", repo=clone)
    assert r.returncode == 1
    assert "256 KiB" in r.stdout and "skills/zz-planted/big.md" in r.stdout, r.stdout

    _git(clone, "rm", "-q", "skills/zz-planted/big.md")
    for i in range(520):
        (clone / "skills" / "zz-planted").mkdir(parents=True, exist_ok=True)
        (clone / "skills" / "zz-planted" / f"f{i}.md").write_text("x\n", encoding="utf-8")
    _git(clone, "add", "skills/zz-planted")
    _git(clone, "commit", "-q", "-m", "Plant many files")
    r = _build("--ref", "HEAD", repo=clone)
    assert r.returncode == 1
    assert "512" in r.stdout, r.stdout


def test_trc_f3_the_same_release_twice_adds_nothing(clone):
    """Scenario `TRC-F3`: a second run for the release the branch already
    holds adds no commit and says so."""
    _git(clone, "tag", f"v{VERSION}")
    assert _build("--ref", f"v{VERSION}", "--commit", repo=clone).returncode == 0
    tip = _git(clone, "rev-parse", "refs/heads/plugin")
    again = _build("--ref", f"v{VERSION}", "--commit", repo=clone)
    assert again.returncode == 0
    assert "already holds" in again.stdout, again.stdout
    assert _git(clone, "rev-parse", "refs/heads/plugin") == tip


def test_trc_f1_a_missing_cli_root_read_stops_the_build(clone):
    """Scenario `TRC-F1`: a file the CLI reads from its own root that is not
    in the copy stops the build too."""
    _plant(clone, "cli/compass_pkg/zz_planted.py",
           'import os\nFRAMEWORK_ROOT = ""\nPATH = os.path.join(FRAMEWORK_ROOT, "nowhere", "x.yml")\n')
    r = _build("--ref", "HEAD", repo=clone)
    assert r.returncode == 1
    assert "nowhere/x.yml" in r.stdout and "zz_planted.py" in r.stdout, r.stdout


def test_trc_f2_a_failed_check_changes_no_branch(clone):
    """Scenario `TRC-F2`: a copy over the limits leaves the branch alone,
    even with --commit; a symbolic link is refused too."""
    _plant(clone, "skills/zz-planted/big.md", "x" * (257 * 1024))
    _bump(clone, "99.0.0")
    r = _build("--ref", "v99.0.0", "--commit", repo=clone)
    assert r.returncode == 1
    assert subprocess.run(["git", "-C", str(clone), "rev-parse", "--verify", "-q",
                           "refs/heads/plugin"], capture_output=True).returncode != 0
    _git(clone, "rm", "-q", "skills/zz-planted/big.md")
    os.symlink("../../README.md", clone / "skills" / "zz-link")
    _git(clone, "add", "skills/zz-link")
    _git(clone, "commit", "-q", "-m", "Plant a link")
    r = _build("--ref", "HEAD", repo=clone)
    assert r.returncode == 1
    assert "skills/zz-link" in r.stdout and "link" in r.stdout, r.stdout


def test_trc_b1_a_commit_needs_a_newer_release_tag(clone):
    """Scenario `TRC-B1`: --commit takes only a vX.Y.Z tag, and only one
    newer than the release the branch holds."""
    r = _build("--ref", "HEAD", "--commit", repo=clone)
    assert r.returncode == 1 and "vX.Y.Z" in r.stdout, r.stdout
    _bump(clone, "99.0.0")
    assert _build("--ref", "v99.0.0", "--commit", repo=clone).returncode == 0
    _bump(clone, "98.0.0")
    r = _build("--ref", "v98.0.0", "--commit", repo=clone)
    assert r.returncode == 1 and "99.0.0" in r.stdout, r.stdout


def test_trc_b1_a_branch_behind_origin_is_refused(clone, tmp_path):
    """Scenario `TRC-B1`: a local plugin branch that is missing or behind the
    remote's is refused, so a release never starts a second history."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(clone), str(origin)], check=True)
    _git(clone, "remote", "set-url", "origin", str(origin))
    _bump(clone, "99.0.0")
    assert _build("--ref", "v99.0.0", "--commit", repo=clone).returncode == 0
    _git(clone, "push", "-q", "origin", "plugin")
    _git(clone, "fetch", "-q", "origin")
    _git(clone, "branch", "-D", "plugin")
    _bump(clone, "99.0.1")
    r = _build("--ref", "v99.0.1", "--commit", repo=clone)
    assert r.returncode == 1 and "origin/plugin" in r.stdout, r.stdout
