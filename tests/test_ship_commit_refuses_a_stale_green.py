"""`compass ship-commit` refuses a stale green.

`ship-commit` commits whatever is staged, even when a file the issue changed
was edited after its newest green - so the landed files were not the tested
files, and only a later `compass check` noticed. Before it commits, it now
compares the newest bound record's `changes_id` with the same files now
(`binding.changes_paths`), refuses on a mismatch, and names the paths whose
content changed. An edit outside the issue's declared files and tests causes
no refusal.

Scenario ids: QFG-3 (the refusal), QFG-4 (the safety contract states the
limits a green record carries).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

SLUG = "ssg"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


def _git(root, *args):
    return subprocess.run([*GIT, *args], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()


def _cli(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})


@pytest.fixture
def repo(tmp_path):
    """A git repository with a tracked, unclaimed file, and an issue that
    claims a new source file, gates already passed."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    _write_manifest(root)
    return root


def _write_manifest(root, *, gates="pass"):
    path = root / ".compass" / "work" / SLUG / "manifest.yml"
    data = yaml.safe_load(path.read_text()) if path.exists() else {}
    data.update({"schema_version": "2.0", "issue": SLUG,
                 "created": "2026-09-28", "status": "active",
                 "gates": [{"id": "verify.correctness", "status": gates,
                            "evidence": []}],
                 "changed_files": [{"path": "src/new.py",
                                    "scenarios": ["S-1"]}]})
    data.setdefault("evidence", [])
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _green(root):
    result = _cli(root, "tdd-green", "--issue", SLUG, "--", sys.executable,
                  "-c", "pass")
    assert result.returncode == 0, result.stderr


def test_qfg3_a_changed_file_after_the_green_refuses(repo):
    """An edit to an issue file after its newest green stops the commit."""
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    (repo / "src" / "new.py").write_text("y = 2\n")   # edited after the green
    _git(repo, "add", "src/new.py")
    head_before = _git(repo, "rev-parse", "HEAD")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")

    assert result.returncode != 0, result.stdout
    combined = result.stdout + result.stderr
    assert "src/new.py" in combined, combined
    assert "tdd-green" in combined, combined
    assert _git(repo, "rev-parse", "HEAD") == head_before, combined


def test_qfg3_an_edit_outside_the_issue_does_not_refuse(repo):
    """A file the issue did not claim can change freely; it is not compared."""
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    (repo / "src" / "app.py").write_text("x = 2\n")   # unclaimed, unstaged
    _git(repo, "add", "src/new.py")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")

    assert result.returncode == 0, result.stdout + result.stderr


def test_qfg3_a_matching_green_commits(repo):
    """The control: nothing changed after the green, so the commit lands."""
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    _git(repo, "add", "src/new.py")
    head_before = _git(repo, "rev-parse", "HEAD")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _git(repo, "rev-parse", "HEAD") != head_before


def test_qfg3_a_landed_issue_does_not_block_a_later_ship(repo):
    """A landed issue's green was judged when it landed. A later edit to
    one of its files belongs to later work, which the pointer may still
    name, so it must not be refused as this issue's stale green."""
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    path = repo / ".compass" / "work" / SLUG / "manifest.yml"
    data = yaml.safe_load(path.read_text())
    data["status"] = "landed"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    (repo / "src" / "new.py").write_text("y = 3\n")   # later work
    _git(repo, "add", "src/new.py")
    head_before = _git(repo, "rev-parse", "HEAD")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "later work")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _git(repo, "rev-parse", "HEAD") != head_before


def test_qfg4_the_safety_contract_states_the_limits():
    text = " ".join((ROOT / "docs" / "safety-contract.md")
                    .read_text(encoding="utf-8").split())
    assert "runs no test" in text and "records a green" in text
    assert "not flagged as a rerun" in text and "changed_files" in text


def test_fse4_the_safety_contract_states_what_finish_does_not_guard():
    text = (ROOT / "docs" / "safety-contract.md").read_text(encoding="utf-8")
    flat = " ".join(text.split())
    assert "created after `start` is taken as the change's" in flat
    assert "not checked for tampering" in flat
    assert "no start record" in flat and "changed before the fix began" in flat


def test_sjs1_a_stale_staged_copy_refuses(repo):
    """The check judges what is staged, which is what commits."""
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    (repo / "src" / "new.py").write_text("y = 2\n")
    _git(repo, "add", "src/new.py")                    # y = 2 staged
    (repo / "src" / "new.py").write_text("y = 1\n")   # disk back to tested
    head_before = _git(repo, "rev-parse", "HEAD")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert result.returncode != 0, result.stdout
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_sjs1_a_tested_staged_copy_commits_despite_a_disk_edit(repo):
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    _git(repo, "add", "src/new.py")                    # the tested copy
    (repo / "src" / "new.py").write_text("y = 9\n")   # later, unstaged

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _git(repo, "show", "HEAD:src/new.py") == "y = 1"


def test_sjs3_a_committed_multiagent_land_refuses_a_later_change(repo):
    """Every file already committed, then one changed in a later commit:
    the land at HEAD judges the files as HEAD holds them."""
    (repo / "src" / "new.py").write_text("y = 1\n")
    _git(repo, "add", "src/new.py")
    _git(repo, "commit", "-q", "-m", "integrate")
    _green(repo)
    (repo / "src" / "new.py").write_text("y = 2\n")
    _git(repo, "commit", "-q", "-am", "later")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert result.returncode != 0, result.stdout
    assert "src/new.py" in result.stdout + result.stderr


def test_sjs4_a_name_with_a_pattern_character_stages_only_itself(tmp_path):
    """No issue: `ship-commit` stages exactly the names it is given."""
    root = tmp_path / "plain"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "base.txt").write_text("base\n")
    _git(root, "add", "base.txt")
    _git(root, "commit", "-q", "-m", "base")
    (root / "x[1].txt").write_text("named\n")
    (root / "x1.txt").write_text("not named\n")
    result = _cli(root, "ship-commit", "-m", "one file", "x[1].txt")
    assert result.returncode == 0, result.stdout + result.stderr
    committed = _git(root, "show", "--name-only", "--format=", "HEAD")
    assert "x[1].txt" in committed
    assert "x1.txt" not in committed.split("\n")


def test_sjs6_the_safety_contract_states_the_three_cases():
    flat = " ".join((ROOT / "docs" / "safety-contract.md")
                    .read_text(encoding="utf-8").split())
    assert "a test the scenario declares is committed" in flat.lower()
    assert "digest record" in flat
    assert "tracing an already-tracked file changes only `changes_id`" in flat.lower()


def test_sjs1_a_stale_disk_copy_does_not_land_through_a_restage(repo, tmp_path):
    """With pre-commit set up, ship-commit re-stages the paths after the
    hooks run, which puts the disk copy in the index. The check must judge
    what is staged at the moment of the commit, not before the re-stage."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    fake = bin_dir / "pre-commit"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    (repo / ".pre-commit-config.yaml").write_text("repos: []\n")
    _git(repo, "add", ".pre-commit-config.yaml")
    _git(repo, "commit", "-q", "-m", "hooks")
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    _git(repo, "add", "src/new.py")                    # the tested copy
    (repo / "src" / "new.py").write_text("y = 9\n")   # untested, on disk
    head_before = _git(repo, "rev-parse", "HEAD")

    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo),
           "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run([sys.executable, str(CLI), "ship-commit",
                             "--issue", SLUG, "-m", "land it"], cwd=repo,
                            capture_output=True, text=True, env=env)
    if result.returncode == 0:
        assert _git(repo, "show", "HEAD:src/new.py") == "y = 1", (
            "the untested disk copy was committed")
    else:
        assert _git(repo, "rev-parse", "HEAD") == head_before


def test_sjs1_a_traced_symlink_can_ship(repo):
    (repo / "src" / "new.py").write_text("y = 1\n")
    os.symlink("new.py", repo / "src" / "link.py")
    path = repo / ".compass" / "work" / SLUG / "manifest.yml"
    data = yaml.safe_load(path.read_text())
    data["changed_files"].append({"path": "src/link.py", "scenarios": ["S-1"]})
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    _green(repo)
    _git(repo, "add", "src/new.py", "src/link.py")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert result.returncode == 0, result.stdout + result.stderr


def _hook(repo, body):
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\n" + body)
    hook.chmod(0o755)


def _fake_pre_commit(repo, tmp_path, record=None):
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "pre-commit"
    body = f'printf "%s\\n" "$@" > {record}\n' if record else ""
    fake.write_text("#!/bin/sh\n" + body + "exit 0\n")
    fake.chmod(0o755)
    (repo / ".pre-commit-config.yaml").write_text("repos: []\n")
    _git(repo, "add", ".pre-commit-config.yaml")
    _git(repo, "commit", "-q", "-m", "hooks")
    return {**os.environ, "CLAUDE_PROJECT_DIR": str(repo),
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}


def _ship(repo, env, *args):
    return subprocess.run([sys.executable, str(CLI), "ship-commit", *args],
                          cwd=repo, capture_output=True, text=True, env=env)


def _status(repo):
    path = repo / ".compass" / "work" / SLUG / "manifest.yml"
    return yaml.safe_load(path.read_text()).get("status")


def test_scf1_a_hook_that_stages_an_untested_copy_leaves_the_issue_unlanded(repo):
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    _git(repo, "add", "src/new.py")
    _hook(repo, "printf 'y = 9\\n' > src/new.py\ngit add src/new.py\nexit 0\n")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert result.returncode != 0, result.stdout
    assert "src/new.py" in result.stdout + result.stderr
    assert _status(repo) != "landed"


def test_scf2_an_unrelated_disk_edit_does_not_replace_the_tested_stage(repo, tmp_path):
    env = _fake_pre_commit(repo, tmp_path)
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    _git(repo, "add", "src/new.py")
    (repo / "src" / "new.py").write_text("y = 9\n")   # no hook touches it

    result = _ship(repo, env, "--issue", SLUG, "-m", "land it")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _git(repo, "show", "HEAD:src/new.py") == "y = 1"


def test_scf3_the_retry_judges_what_a_hook_rewrote(repo):
    (repo / "src" / "new.py").write_text("y = 1\n")
    _green(repo)
    _git(repo, "add", "src/new.py")
    head_before = _git(repo, "rev-parse", "HEAD")
    _hook(repo, "if [ ! -f .hooked ]; then touch .hooked; "
                "printf 'y = 9\\n' > src/new.py; exit 1; fi\nexit 0\n")

    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert result.returncode != 0, result.stdout
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_scf5_odd_names_stage_as_themselves_and_reach_pre_commit_as_names(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "base.txt").write_text("base\n")
    _git(root, "add", "base.txt")
    _git(root, "commit", "-q", "-m", "base")
    record = tmp_path / "args.txt"
    env = _fake_pre_commit(root, tmp_path, record=record)
    for name in ("-dash.txt", "a*b.txt", "q?.txt", "ab.txt", "qx.txt"):
        (root / name).write_text(name + "\n")

    result = _ship(root, env, "-m", "odd names", "--", "-dash.txt",
                   "a*b.txt", "q?.txt")
    assert result.returncode == 0, result.stdout + result.stderr
    committed = set(_git(root, "show", "--name-only", "--format=",
                         "HEAD").split("\n"))
    assert committed == {"-dash.txt", "a*b.txt", "q?.txt"}, committed
    assert "./-dash.txt" in record.read_text().split("\n")


def test_scf6_the_safety_contract_states_the_symlink_ignored_and_hook_cases():
    flat = " ".join((ROOT / "docs" / "safety-contract.md")
                    .read_text(encoding="utf-8").split()).lower()
    assert "a traced symlink is not checked" in flat
    assert "a traced file git ignores does not change `tree_id`" in flat
    assert "not marked landed" in flat
