"""Git parents: `extends: github:<owner>/<repo>@<ref>#<sha>` (issue `git-parents`).

A parent is fetched at an exact commit into `.compass/cache/parents/`, read as
data and merged between the shipped default and the project. These tests build
local git repositories in a temporary folder and point
`COMPASS_PARENT_REMOTE_BASE` at them, so nothing reaches the network. A fake
`git` on the PATH records each call where a test needs to prove git was or was
not run.

Scenario ids: `GP-1` to `GP-15`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))
from parent_fixtures import PARENT_DOC, make_remote  # noqa: E402

SHA = "a" * 40


# --- helpers -------------------------------------------------------------------

def _project(tmp_path, extends):
    root = tmp_path / "project"
    (root / ".compass").mkdir(parents=True)
    doc = {"schema": 1}
    if extends is not None:
        doc["extends"] = extends
    (root / "compass.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    return root


def _ref(sha, owner="acme", repo="bank", ref="1.2.0"):
    return f"github:{owner}/{repo}@{ref}#{sha}"


# --- GP-3: a pinned sha is fetched into the cache -----------------------------------------

def _cache(root):
    return root / ".compass" / "cache" / "parents"


def _folder(root, sha, owner="acme", repo="bank"):
    """Where the cache keeps one commit of one repository."""
    return _cache(root) / owner / repo / sha


# --- GP-4: the fetched commit must be the pin ---------------------------------------------

def test_gp_4_a_fetched_commit_that_is_not_the_pin_is_refused_and_not_cached(
        tmp_path, monkeypatch):
    from compass_pkg import parents
    base = tmp_path / "remotes"
    sha = make_remote(base)
    root = _project(tmp_path, _ref(sha))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    real = parents._git

    def lying(argv, **kwargs):
        done = real(argv, **kwargs)
        if "rev-parse" in argv:
            return subprocess.CompletedProcess(argv, 0, b"c" * 40 + b"\n", b"")
        return done

    monkeypatch.setattr(parents, "_git", lying)
    with pytest.raises(parents.ParentError) as caught:
        parents.resolve(root, _ref(sha), fetch=True)
    assert caught.value.code == "L-PARENT-SHA-MISMATCH"
    assert sha in str(caught.value) and "c" * 40 in str(caught.value)
    assert not (_folder(root, sha)).exists()
    assert not [p for p in _cache(root).iterdir() if p.name.startswith(".fetch")]
    assert not (_cache(root) / "seen.yml").exists()


# --- GP-8: how git is run -------------------------------------------------------------------

def _record_git_calls(monkeypatch):
    from compass_pkg import parents
    calls = []
    real = subprocess.run

    def spy(argv, **kwargs):
        calls.append((argv, kwargs))
        return real(argv, **kwargs)

    monkeypatch.setattr(parents.subprocess, "run", spy)
    return calls


def test_gp_8_git_runs_with_an_argument_list_no_shell_and_restricted_protocols(
        tmp_path, monkeypatch):
    from compass_pkg import parents
    base = tmp_path / "remotes"
    sha = make_remote(base)
    root = _project(tmp_path, _ref(sha))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    calls = _record_git_calls(monkeypatch)
    parents.resolve(root, _ref(sha), fetch=True)
    assert calls, "git was not run"
    for argv, kwargs in calls:
        assert isinstance(argv, list) and argv[0] == "git"
        assert kwargs["shell"] is False
        assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
        assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == "https:file"
        assert "protocol.allow=never" in argv and "protocol.https.allow=always" in argv
        assert "core.hooksPath=/dev/null" in argv
        assert kwargs["stdin"] == subprocess.DEVNULL and kwargs["timeout"] > 0
    verbs = [next(a for a in argv[1:] if not a.startswith("-") and "=" not in a
                  and a not in ("protocol.allow", "never", "always"))
             for argv, _ in calls]
    assert "fetch" in verbs
    fetch = next(argv for argv, _ in calls if "fetch" in argv)
    assert fetch[fetch.index("--") + 1:] == ["origin", sha], fetch
    add = next(argv for argv, _ in calls if "remote" in argv)
    assert add[add.index("--") + 1:] == [f"{base}/acme/bank.git"], add
    init = next(argv for argv, _ in calls if "init" in argv)
    assert "--template=" in init, "a template could copy hooks into the scratch repository"


def test_gp_8_the_https_default_does_not_allow_the_file_protocol(tmp_path, monkeypatch):
    from compass_pkg import parents
    monkeypatch.delenv("COMPASS_PARENT_REMOTE_BASE", raising=False)
    assert parents.remote_base() == ("https://github.com", False)
    seen = {}

    def spy(argv, **kwargs):
        seen["argv"], seen["env"] = argv, kwargs["env"]
        return subprocess.CompletedProcess(argv, 1, b"", b"stop")

    monkeypatch.setattr(parents.subprocess, "run", spy)
    parents._git(["init"], cwd=tmp_path, local=False)
    assert seen["env"]["GIT_ALLOW_PROTOCOL"] == "https"
    assert "protocol.file.allow=never" in seen["argv"]


def test_gp_8_variables_that_move_or_script_git_are_not_passed_on(tmp_path, monkeypatch):
    from compass_pkg import parents
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_SSH_COMMAND", "GIT_EXEC_PATH",
                 "GIT_CONFIG_COUNT", "GIT_PROXY_COMMAND", "GIT_EXTERNAL_DIFF",
                 "GIT_INDEX_FILE", "GIT_TEMPLATE_DIR", "GIT_ASKPASS_EVIL"):
        monkeypatch.setenv(name, "/tmp/evil")
    seen = {}

    def spy(argv, **kwargs):
        seen.update(kwargs["env"])
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(parents.subprocess, "run", spy)
    parents._git(["status"], cwd=tmp_path, local=False)
    assert {k for k in seen if k.startswith("GIT_")} <= {
        "GIT_ALLOW_PROTOCOL", "GIT_TERMINAL_PROMPT", "GIT_ASKPASS", "GIT_SSL_CAINFO",
        "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "GIT_NO_LAZY_FETCH"}
    assert seen["GIT_TERMINAL_PROMPT"] == "0" and seen["GIT_NO_LAZY_FETCH"] == "1"


@pytest.mark.parametrize("base", ["http://example.com", "ftp://example.com", "-oops",
                                  "https://a b", "relative/path", "https://x\\y",
                                  "file:///tmp/x", "https://exa;mple.com"])
def test_gp_8_the_remote_base_must_be_https_or_an_absolute_folder(monkeypatch, base):
    from compass_pkg import parents
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", base)
    with pytest.raises(parents.ParentError) as caught:
        parents.remote_base()
    assert caught.value.code == "L-PARENT-FETCH"


# --- GP-12: versions.yml records the parent ----------------------------------------------------

def test_gp_12_a_project_with_the_shipped_default_records_no_git_parent(tmp_path, monkeypatch):
    from parent_fixtures import commit, issue_project
    root, task_dir = issue_project(tmp_path, "compass:default@6")
    monkeypatch.chdir(root)
    assert commit(task_dir).committed
    stored = yaml.safe_load((task_dir / "generations" / "1" / "versions.yml")
                            .read_text(encoding="utf-8"))
    assert [p["source"] for p in stored["parents"]] == ["shipped"]


# --- GP-15: the owning doc, the help, the codes and the corpus -----------------------------------

def _text(*parts):
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def _parent_codes():
    from compass_pkg import policy_lint
    return [c for c in policy_lint.FINDING_CODES if c.startswith("L-PARENT-")]


def test_gp_15_every_parent_code_is_a_code_the_lint_can_name():
    assert _parent_codes() == [
        "L-PARENT-FORM", "L-PARENT-NO-SHA", "L-PARENT-NOT-CACHED", "L-PARENT-FETCH",
        "L-PARENT-CONTENT", "L-PARENT-SHA-MISMATCH", "L-PARENT-SYMLINK", "L-PARENT-CACHE",
        "L-PARENT-CHAIN", "L-PARENT-SHA-AMBIGUOUS", "L-PARENT-CYCLE"]


def test_gp_15_the_owning_doc_names_every_code_setting_and_file():
    doc = _text("docs", "git-parents.md")
    for name in _parent_codes() + ["COMPASS_PARENT_REMOTE_BASE", "COMPASS_OFFLINE",
                                   "--offline", "seen.yml", "versions.yml",
                                   ".compass/cache/parents", "content_digest", "source: git"]:
        assert name in doc, f"docs/git-parents.md does not mention {name}"


def test_gp_15_the_docs_index_lists_the_owning_doc_in_both_places():
    index = _text("docs", "README.md")
    assert "[git-parents.md](git-parents.md)" in index
    assert "`cli/compass_pkg/parents.py`" in index and "`docs/git-parents.md`" in index


def test_gp_15_the_corpus_has_entries_with_a_reason_for_each_new_behaviour():
    raw = _text("tests", "fixtures", "compat", "contract-4-commands.yml")
    entries = {e["id"]: e for e in yaml.safe_load(raw)["entries"]}
    for entry_id in ("policy-lint-offline", "policy-lint-git-parent-no-sha",
                     "policy-lint-git-parent-uncached-offline"):
        assert entry_id in entries, entry_id
        before = raw.split(f"- id: {entry_id}\n")[0].rstrip().splitlines()
        assert before[-1].startswith("#") or before[-2].startswith("#"), entry_id
        assert "Added on purpose by git-parents" in "\n".join(before[-6:]), entry_id
    assert entries["policy-lint-git-parent-no-sha"]["exit"] == 1
    assert entries["policy-lint-offline"]["exit"] == 0


# --- GP-16: the README and security.md say the fetch happens -------------------------------------

def test_gp_16_security_says_a_parent_is_data_and_is_fetched():
    doc = " ".join(_text("docs", "security.md").split())
    assert "git parent" in doc and "is data" in doc and "fetch" in doc
    assert "git-parents.md" in doc


# --- GP-18: what git sees ---------------------------------------------------------------------

def test_gp_18_the_doc_says_the_users_credential_helper_runs_and_ci_needs_credentials():
    doc = " ".join(_text("docs", "git-parents.md").split())
    for needle in ("credential helper", "insteadOf", "GIT_CONFIG_GLOBAL", "GIT_ASKPASS",
                   "CI", "ref label is not checked", "accidental edit"):
        assert needle in doc, needle
    assert "short list" not in doc


def test_gp_18_git_receives_home_the_global_config_and_the_askpass_program(monkeypatch, tmp_path):
    from compass_pkg import parents
    monkeypatch.setenv("GIT_ASKPASS", "/bin/true")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/tmp/x")
    monkeypatch.setenv("HOME", "/tmp/h")
    seen = {}

    def spy(argv, **kwargs):
        seen.update(kwargs["env"])
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(parents.subprocess, "run", spy)
    parents._git(["status"], cwd=tmp_path, local=False)
    assert (seen["GIT_ASKPASS"], seen["GIT_CONFIG_GLOBAL"], seen["HOME"]) \
        == ("/bin/true", "/tmp/x", "/tmp/h")


# --- GP-19: a partial fetch reads only the root entry --------------------------------------------

def _spy_git(monkeypatch):
    from compass_pkg import parents
    calls = []
    real = parents._git

    def spy(argv, **kwargs):
        calls.append(list(argv))
        return real(argv, **kwargs)

    monkeypatch.setattr(parents, "_git", spy)
    return calls


def test_gp_19_the_fetch_is_partial_and_only_the_root_entry_is_listed(tmp_path, monkeypatch):
    from compass_pkg import parents
    base = tmp_path / "remotes"
    sha = make_remote(base, files={"compass.yml": yaml.safe_dump(PARENT_DOC),
                                   "deep/er/file.txt": "x"})
    root = _project(tmp_path, _ref(sha))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    calls = _spy_git(monkeypatch)
    parents.resolve(root, _ref(sha), fetch=True)
    fetch = next(c for c in calls if "fetch" in c)
    assert any(a.startswith("--filter=blob:") for a in fetch), fetch
    listing = next(c for c in calls if "ls-tree" in c)
    assert "-r" not in listing and listing[-2:] == ["--", "compass.yml"], listing


def test_gp_19_a_large_unrelated_file_is_not_fetched(tmp_path, monkeypatch):
    from compass_pkg import parents
    base = tmp_path / "remotes"
    sha = make_remote(base, files={"compass.yml": yaml.safe_dump(PARENT_DOC),
                                   "big.bin": "x" * (3 * 1024 * 1024)})
    from parent_fixtures import _git
    big = _git(base / "acme" / "bank.git", "rev-parse", "HEAD:big.bin")
    small = _git(base / "acme" / "bank.git", "rev-parse", "HEAD:compass.yml")
    root = _project(tmp_path, _ref(sha))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    real = parents._git
    listed = {}

    def spy(argv, **kwargs):
        done = real(argv, **kwargs)
        if "fetch" in argv:
            missing = real(["rev-list", "--objects", "--missing=print", sha], **kwargs)
            listed["missing"] = missing.stdout.decode()
        return done

    monkeypatch.setattr(parents, "_git", spy)
    parents.resolve(root, _ref(sha), fetch=True)
    missing = listed["missing"].split()
    assert f"?{big}" in missing, "the large unrelated file was fetched"
    assert f"?{small}" not in missing, "the parent file itself must arrive with the fetch"


# --- GP-20: guards that the first plants missed ------------------------------------------------

def test_gp_20_the_fetch_options_are_pinned(tmp_path, monkeypatch):
    from compass_pkg import parents
    base = tmp_path / "remotes"
    sha = make_remote(base)
    root = _project(tmp_path, _ref(sha))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    calls = _spy_git(monkeypatch)
    parents.resolve(root, _ref(sha), fetch=True)
    fetch = next(c for c in calls if "fetch" in c)
    assert fetch[fetch.index("--depth") + 1] == "1"
    assert "--no-recurse-submodules" in fetch and "--no-tags" in fetch


def test_gp_20_the_fsck_option_reaches_git(monkeypatch, tmp_path):
    from compass_pkg import parents
    seen = {}

    def spy(argv, **kwargs):
        seen["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(parents.subprocess, "run", spy)
    parents._git(["status"], cwd=tmp_path, local=False)
    assert "transfer.fsckObjects=true" in seen["argv"]


@pytest.mark.parametrize("repo", [".hidden", ".", "..", ".git"])
def test_gp_20_a_repository_name_starting_with_a_dot_is_refused(repo):
    from compass_pkg import parents
    with pytest.raises(parents.ParentError) as caught:
        parents.spec_of(f"github:acme/{repo}@1#{SHA}")
    assert caught.value.code == "L-PARENT-FORM"


@pytest.mark.parametrize("ref", ["a..b", "a//b", "a/", "a.", "a.lock", "a/b.lock"])
def test_gp_20_an_unsound_ref_is_refused(ref):
    from compass_pkg import parents
    with pytest.raises(parents.ParentError) as caught:
        parents.spec_of(f"github:acme/bank@{ref}#{SHA}")
    assert caught.value.code == "L-PARENT-FORM"


@pytest.mark.parametrize("ref", ["1.2.0", "v1.2.0", "feature/x-1", "a.b", "main"])
def test_gp_20_a_sound_ref_is_accepted(ref):
    from compass_pkg import parents
    assert parents.spec_of(f"github:acme/bank@{ref}#{SHA}").ref == ref


@pytest.mark.parametrize("ref,version", [
    ("1.2.0", "1.2.0"), ("v1.2.0", "1.2.0"), ("1.2", "1.2"), ("3", "3"),
    ("1.0.0-rc.1", "1.0.0-rc.1"), ("main", ""), ("1.2.3.4", ""), ("release-1.2.0", ""),
    ("v", ""), ("1.2.0/extra", "")])
def test_gp_20_the_version_is_the_ref_only_when_it_reads_as_one(ref, version):
    from compass_pkg import parents
    assert parents.version_of(ref) == version


# --- GP-21: a failed read caches nothing, and a cache write race is safe --------------------------

def _failing(monkeypatch, match, returncode=1):
    from compass_pkg import parents
    real = parents._git

    def wrapper(argv, **kwargs):
        if all(word in argv for word in match):
            return subprocess.CompletedProcess(argv, returncode, b"", b"fatal: no")
        return real(argv, **kwargs)

    monkeypatch.setattr(parents, "_git", wrapper)


@pytest.mark.parametrize("match", [["cat-file", "blob"], ["ls-tree"]])
def test_gp_21_a_failed_cat_file_caches_nothing(tmp_path, monkeypatch, match):
    from compass_pkg import parents
    base = tmp_path / "remotes"
    sha = make_remote(base)
    root = _project(tmp_path, _ref(sha))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    _failing(monkeypatch, match)
    with pytest.raises(parents.ParentError) as caught:
        parents.resolve(root, _ref(sha), fetch=True)
    assert caught.value.code == "L-PARENT-FETCH"
    assert not _folder(root, sha).exists()
    assert not (_cache(root) / "seen.yml").exists()


def test_gp_21_a_destination_that_appears_during_the_write_is_fine_when_it_matches(
        tmp_path, monkeypatch):
    from compass_pkg import parents
    base = tmp_path / "remotes"
    sha = make_remote(base)
    root = _project(tmp_path, _ref(sha))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    real = os.rename

    def racing(source, target):
        if os.path.basename(target) == sha:
            os.makedirs(target)
            Path(target, "compass.yml").write_text(yaml.safe_dump(PARENT_DOC), encoding="utf-8")
        return real(source, target)

    monkeypatch.setattr(parents.os, "rename", racing)
    assert parents.resolve(root, _ref(sha), fetch=True).sha == sha
    assert not [p for p in _cache(root).iterdir() if p.name.startswith(".fetch")]


def test_gp_21_a_destination_that_appears_during_the_write_is_refused_when_it_differs(
        tmp_path, monkeypatch):
    from compass_pkg import parents
    base = tmp_path / "remotes"
    sha = make_remote(base)
    root = _project(tmp_path, _ref(sha))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    real = os.rename

    def racing(source, target):
        if os.path.basename(target) == sha:
            os.makedirs(target)
            Path(target, "compass.yml").write_text("schema: 1\nowner: someone-else\n",
                                                   encoding="utf-8")
        return real(source, target)

    monkeypatch.setattr(parents.os, "rename", racing)
    with pytest.raises(parents.ParentError) as caught:
        parents.resolve(root, _ref(sha), fetch=True)
    assert caught.value.code == "L-PARENT-CACHE"


# --- GP-22: a waiver in a git parent answers to the parent's owner --------------------------------

def _chain_report(parent_owner, approver, project_owner="project-owner"):
    from compass_pkg import layers, policy_lint
    sys.path.insert(0, str(ROOT / "tests"))
    import waiver_fixtures as fx
    default, _ = policy_lint.load_parent()
    # A human check the shipped default holds; it has no Definition of Ready
    # since 9.0.0 (ADR-092).
    doc = {"schema": 1, "checks": {"dod-suite-green": {
        "set": {"severity": "advisory"}, "waiver": fx.project_waiver(approved_by=approver)}}}
    if parent_owner:
        doc["owner"] = parent_owner
    parent = layers.Layer("github:a/b@1#abc1234", "parent", doc,
                          layers.layer_digest(doc, "parent"))
    own = {"schema": 1, "owner": project_owner}
    project = layers.Layer("project", "project", own, layers.layer_digest(own, "project"))
    return policy_lint.lint_chain(default, project, extra_parents=[parent], today=fx.TODAY)


def test_gp_22_the_parents_owner_may_approve_the_parents_waiver():
    report = _chain_report("parent-owner", "parent-owner")
    assert [f.code for f in report.findings if f.level == "error"] == []


def test_gp_22_the_projects_owner_may_not_approve_the_parents_waiver():
    report = _chain_report("parent-owner", "project-owner")
    assert [(f.code, f.layer) for f in report.errors] \
        == [("W-APPROVER-NOT-ALLOWED", "github:a/b@1#abc1234")]


def test_gp_22_a_parent_with_no_owner_cannot_carry_a_waiver():
    report = _chain_report(None, "project-owner")
    assert [f.code for f in report.errors] == ["W-NO-OWNER"]
