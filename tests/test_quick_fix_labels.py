"""`compass quick-fix start --labels`: a small change to auth, payments,
personal data or migrations must reach the domain floor and the human
sign-off guardrail. Before this option, quick-fix start recorded an empty
label list, so neither could fire for a change assessed this way.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=root, check=True)
    return root


def _start(root, slug, *extra):
    return subprocess.run(
        [sys.executable, str(CLI), "quick-fix", "start", slug,
         "--risk", "contained - one function",
         "--familiarity", "brownfield-mapped - the module and its tests are read",
         "--size", "small - one function and its test",
         "--intent", "the login error names the locked account",
         "--scenario", "Given a locked account, when it logs in, then the error says so",
         "--test", "tests/test_login.py", *extra],
        cwd=root, capture_output=True, text=True)


def _manifest(root, slug):
    return yaml.safe_load(
        (root / ".compass" / "work" / slug / "manifest.yml").read_text())


def test_a_labelled_change_records_its_labels_and_is_not_a_quick_fix(repo):
    r = _start(repo, "login-error", "--labels", "auth")
    assert r.returncode == 1, r.stdout + r.stderr
    m = _manifest(repo, "login-error")
    assert m["assessment"]["labels"] == ["auth"]
    assert m["delivery_approach"] != "quick-fix"


def test_the_human_sign_off_applies_to_a_labelled_change(repo):
    _start(repo, "login-error", "--labels", "auth,payments")
    r = subprocess.run([sys.executable, str(CLI), "check", "--verbose",
                        "--issue", "login-error"],
                       cwd=repo, capture_output=True, text=True)
    out = r.stdout + r.stderr
    g5 = [line for line in out.splitlines() if "signs off on the irreversible" in line]
    assert g5, out
    assert not any("not applicable" in line for line in g5), g5


def test_without_labels_nothing_changes(repo):
    r = _start(repo, "login-error")
    m = _manifest(repo, "login-error")
    assert m["assessment"]["labels"] == []
    assert m["delivery_approach"] == "quick-fix", r.stdout + r.stderr


def test_a_malformed_label_is_refused_before_anything_is_written(repo):
    r = _start(repo, "login-error", "--labels", "Auth Stuff")
    assert r.returncode != 0
    assert "'Auth Stuff' is not a label" in r.stdout + r.stderr, r.stdout + r.stderr
    assert not (repo / ".compass").exists()


@pytest.mark.parametrize("tag", ["auth-", "a--b", "x_y"])
def test_a_tag_is_lowercase_words_joined_by_single_hyphens(repo, tag):
    r = _start(repo, "login-error", "--labels", tag)
    assert f"{tag!r} is not a label" in r.stdout + r.stderr, r.stdout + r.stderr
