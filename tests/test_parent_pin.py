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

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))
from parent_fixtures import PARENT_DOC, REAL_GIT, fake_git, make_remote  # noqa: E402

CLI = ROOT / "cli" / "compass"

SHA = "a" * 40


# --- helpers -------------------------------------------------------------------

def _env(home, extra=None):
    env = {"PATH": os.environ.get("PATH", REAL_GIT), "HOME": str(home), "LANG": "C.UTF-8",
           "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "100",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    env.update(extra or {})
    return env


def _run(cwd, *argv, env=None):
    done = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=_env(cwd, env),
                          capture_output=True, text=True, timeout=180)
    return done.returncode, done.stdout, done.stderr


def _project(tmp_path, extends):
    root = tmp_path / "project"
    (root / ".compass").mkdir(parents=True)
    doc = {"schema": 1}
    if extends is not None:
        doc["extends"] = extends
    (root / "compass.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    return root


def _lint(root, *extra, env=None):
    code, out, err = _run(root, "policy", "lint", "--json", *extra, env=env)
    return code, (json.loads(out) if out.strip().startswith("{") else {}), err


def _codes(report):
    return [f["code"] for f in report.get("findings", [])]


def _ref(sha, owner="acme", repo="bank", ref="1.2.0"):
    return f"github:{owner}/{repo}@{ref}#{sha}"


# --- GP-1: the spelling is strict ----------------------------------------------------

BAD_SPELLINGS = [
    "github:-acme/bank@1.2.0#" + SHA,
    "github:acme/-bank@1.2.0#" + SHA,
    "github:acme/bank@-1.2.0#" + SHA,
    "github:acme/../bank@1.2.0#" + SHA,
    "github:acme/bank@../x#" + SHA,
    "github:acme/bank@1.2.0#" + SHA.upper(),
    "github:acme/bank@1.2.0#" + "z" * 40,
    "github:acme/bank@1.2.0#" + "a" * 41,
    "github:acme/bank@1.2.0#abc",
    "github:acme/bank#" + SHA,
    "github:acme/bank@1.2.0 #" + SHA,
    "github:acme/bank@1.2.0;touch x#" + SHA,
    "github:acme/bank@$(id)#" + SHA,
    "github:acme/bank@1.2.0#" + SHA + "\n",
    "https://github.com/acme/bank@1.2.0#" + SHA,
    "git@github.com:acme/bank.git",
    "/tmp/bank@1.2.0#" + SHA,
]


@pytest.mark.parametrize("value", BAD_SPELLINGS)
def test_gp_1_a_spelling_outside_the_strict_form_is_refused(tmp_path, value):
    bin_dir, log = fake_git(tmp_path)
    root = _project(tmp_path, value)
    code, report, _ = _lint(root, env={"PATH": f"{bin_dir}:{REAL_GIT}"})
    assert code == 1
    assert "L-PARENT-FORM" in _codes(report), report
    assert not log.exists(), "git ran for a spelling that is not valid"


def test_gp_1_a_map_form_with_a_valid_from_loads_the_parent(tmp_path):
    base = tmp_path / "remotes"
    sha = make_remote(base)
    root = _project(tmp_path, {"from": _ref(sha), "approved_by": "jed72",
                               "approved_on": "2026-10-06"})
    code, report, err = _lint(root, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 0, (report, err)
    assert (_folder(root, sha) / "compass.yml").is_file()


def test_gp_1_the_map_form_is_read_through_from(tmp_path):
    root = _project(tmp_path, {"from": "github:-acme/bank@1.2.0#" + SHA,
                               "approved_by": "jed72", "approved_on": "2026-10-06"})
    _, report, _ = _lint(root)
    assert "L-PARENT-FORM" in _codes(report), report
    assert "-acme" in report["findings"][0]["message"], "the message must name the from: text"


# --- GP-2: a remote ref with no sha ---------------------------------------------------

@pytest.mark.parametrize("value", ["github:acme/bank@1.2.0", "github:acme/bank@1.2.0#"])
def test_gp_2_a_remote_ref_with_no_sha_is_refused_and_git_is_not_run(tmp_path, value):
    bin_dir, log = fake_git(tmp_path)
    root = _project(tmp_path, value)
    code, report, _ = _lint(root, env={"PATH": f"{bin_dir}:{REAL_GIT}"})
    assert code == 1
    assert _codes(report) == ["L-PARENT-NO-SHA"], report
    assert not log.exists(), "git ran for a ref with no sha"
    finding = report["findings"][0]
    assert finding["layer"] == "project" and finding["path"] == "extends"


# --- GP-3: a pinned sha is fetched into the cache -----------------------------------------

def _cache(root):
    return root / ".compass" / "cache" / "parents"


def _folder(root, sha, owner="acme", repo="bank"):
    """Where the cache keeps one commit of one repository."""
    return _cache(root) / owner / repo / sha


def test_gp_3_a_pinned_sha_is_fetched_into_the_cache_with_seen_yml(tmp_path):
    base = tmp_path / "remotes"
    sha = make_remote(base)
    root = _project(tmp_path, _ref(sha))
    code, report, err = _lint(root, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 0, (report, err)
    assert (_folder(root, sha) / "compass.yml").read_text(encoding="utf-8") \
        == yaml.safe_dump(PARENT_DOC)
    seen = yaml.safe_load((_cache(root) / "seen.yml").read_text(encoding="utf-8"))
    entry = seen["refs"]["github:acme/bank@1.2.0"]
    assert seen["schema"] == 1
    assert entry["sha"] == sha and entry["version"] == "1.2.0"
    assert entry["content_digest"].startswith("sha256:") and len(entry["content_digest"]) == 71
    assert len(entry["fetched"]) == 20 and entry["fetched"].endswith("Z")
    ignored = (root / ".compass" / ".gitignore").read_text(encoding="utf-8").split()
    assert "cache/" in ignored
    assert sorted(p.name for p in _cache(root).iterdir()) == ["acme", "seen.yml"]
    assert [p.name for p in (_cache(root) / "acme" / "bank").iterdir()] == [sha]


def test_gp_3_a_commit_the_remote_does_not_have_is_a_fetch_refusal(tmp_path):
    base = tmp_path / "remotes"
    make_remote(base)
    root = _project(tmp_path, _ref("b" * 40))
    code, report, _ = _lint(root, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 1
    assert _codes(report) == ["L-PARENT-FETCH"], report
    assert not list(_cache(root).glob("*")) or not any(
        p.name.startswith(("b" * 40, ".fetch")) for p in _cache(root).iterdir())


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


# --- GP-6: a symlink as the parent file ----------------------------------------------------

@pytest.mark.parametrize("where", ["link", "docs/deep/link"])
def test_gp_6_a_symlink_elsewhere_in_the_tree_is_not_read_and_does_not_refuse(tmp_path, where):
    """Only the root `compass.yml` entry is read, so a link beside it is not
    followed and is no reason to refuse."""
    base = tmp_path / "remotes"
    sha = make_remote(base, files={"compass.yml": yaml.safe_dump(PARENT_DOC),
                                   "docs/deep/readme.md": "x"},
                      symlink=(where, "/etc/passwd"))
    root = _project(tmp_path, _ref(sha))
    code, report, err = _lint(root, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 0, (report, err)
    assert sorted(p.name for p in _folder(root, sha).iterdir()) == ["compass.yml"]


def test_gp_6_a_compass_yml_that_is_a_symlink_is_refused(tmp_path):
    base = tmp_path / "remotes"
    sha = make_remote(base, files={"real.yml": yaml.safe_dump(PARENT_DOC)},
                      symlink=("compass.yml", "real.yml"))
    root = _project(tmp_path, _ref(sha))
    _, report, _ = _lint(root, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert _codes(report) == ["L-PARENT-SYMLINK"], report


# --- GP-5: check and offline read the cache only ------------------------------------------

def _cached_project(tmp_path):
    """A project whose pin is already in the cache, and the remote base."""
    base = tmp_path / "remotes"
    sha = make_remote(base)
    root = _project(tmp_path, _ref(sha))
    code, _, err = _lint(root, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 0, err
    return root, sha, base


def test_gp_5_a_cached_pin_loads_with_git_unavailable(tmp_path):
    root, _, _ = _cached_project(tmp_path)
    bin_dir, log = fake_git(tmp_path)
    code, report, _ = _lint(root, env={"PATH": f"{bin_dir}:{REAL_GIT}"})
    assert code == 0, report
    assert not log.exists(), "git ran although the pin was cached"


@pytest.mark.parametrize("how", ["flag", "env"])
def test_gp_5_offline_reads_the_cache_only_and_names_the_missing_pin(tmp_path, how):
    bin_dir, log = fake_git(tmp_path)
    sha = "d" * 40
    root = _project(tmp_path, _ref(sha))
    extra = ("--offline",) if how == "flag" else ()
    env = {"PATH": f"{bin_dir}:{REAL_GIT}"}
    if how == "env":
        env["COMPASS_OFFLINE"] = "1"
    code, report, _ = _lint(root, *extra, env=env)
    assert code == 1
    assert _codes(report) == ["L-PARENT-NOT-CACHED"], report
    assert not log.exists(), "git ran offline"
    assert sha in report["findings"][0]["message"]


def test_gp_5_a_reader_never_fetches_an_uncached_pin(tmp_path, monkeypatch):
    from compass_pkg import effective, parents
    root = _project(tmp_path, _ref("e" * 40))

    def forbidden(*args, **kwargs):
        raise AssertionError("a reader ran git")

    monkeypatch.setattr(parents, "_git", forbidden)
    monkeypatch.chdir(root)
    with pytest.raises(Exception) as caught:
        effective.effective_for(None)
    assert "L-PARENT-NOT-CACHED" in str(caught.value)


def test_gp_5_a_reader_loads_a_cached_pin_without_git(tmp_path, monkeypatch):
    from compass_pkg import effective, parents
    root, sha, _ = _cached_project(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("a reader ran git")

    monkeypatch.setattr(parents, "_git", forbidden)
    monkeypatch.chdir(root)
    view = effective.effective_for(None)
    assert view.versions["parents"][-1]["sha"] == sha


# --- GP-7: the cache never leaves .compass --------------------------------------------------

def _outside(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    return outside


@pytest.mark.parametrize("link", ["cache", "cache/parents"])
def test_gp_7_a_cache_folder_that_links_out_of_compass_is_refused(tmp_path, link):
    base = tmp_path / "remotes"
    sha = make_remote(base)
    root = _project(tmp_path, _ref(sha))
    outside = _outside(tmp_path)
    cache = root / ".compass" / "cache"
    if link == "cache":
        os.symlink(outside, cache)
    else:
        cache.mkdir()
        os.symlink(outside, cache / "parents")
    code, report, _ = _lint(root, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 1
    assert _codes(report) == ["L-PARENT-CACHE"], report
    assert list(outside.iterdir()) == [], "something was written outside .compass"


def test_gp_7_a_cache_folder_that_links_to_another_folder_inside_compass_is_refused(tmp_path):
    base = tmp_path / "remotes"
    sha = make_remote(base)
    root = _project(tmp_path, _ref(sha))
    inside = root / ".compass" / "elsewhere"
    inside.mkdir()
    os.symlink(inside, root / ".compass" / "cache")
    code, report, _ = _lint(root, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert _codes(report) == ["L-PARENT-CACHE"], report
    assert list(inside.iterdir()) == []


def test_gp_7_a_cached_commit_folder_that_is_a_link_is_refused(tmp_path):
    root, sha, _ = _cached_project(tmp_path)
    outside = _outside(tmp_path)
    (outside / "compass.yml").write_text(yaml.safe_dump(PARENT_DOC), encoding="utf-8")
    folder = _folder(root, sha)
    for child in folder.iterdir():
        child.unlink()
    folder.rmdir()
    os.symlink(outside, folder)
    code, report, _ = _lint(root, "--offline")
    assert code == 1
    assert _codes(report) == ["L-PARENT-CACHE"], report


def test_gp_7_a_cached_compass_yml_that_is_a_link_is_refused(tmp_path):
    root, sha, _ = _cached_project(tmp_path)
    outside = _outside(tmp_path)
    (outside / "real.yml").write_text(yaml.safe_dump(PARENT_DOC), encoding="utf-8")
    target = _folder(root, sha) / "compass.yml"
    target.unlink()
    os.symlink(outside / "real.yml", target)
    _, report, _ = _lint(root, "--offline")
    assert _codes(report) == ["L-PARENT-CACHE"], report


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


# --- GP-9: a parent is data only ------------------------------------------------------------

def _lint_parent(tmp_path, doc, *extra):
    base = tmp_path / "remotes"
    text = doc if isinstance(doc, str) else yaml.safe_dump(doc)
    sha = make_remote(base, files={"compass.yml": text})
    root = _project(tmp_path, _ref(sha))
    code, report, err = _lint(root, *extra, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    return code, report, err


DATA_ONLY = [
    ("autonomy", {"schema": 1, "autonomy": "autonomous"}, "L-SETTINGS-KEY"),
    ("allow_project_commands", {"schema": 1, "allow_project_commands": True}, "L-SETTINGS-KEY"),
    ("unlock", {"schema": 1, "checks": {"suite-passed": {"unlock": True}}},
     "L-UNLOCK-PLACEMENT"),
    ("impl", {"schema": 1, "checks": {"evil": {
        "name": "evil", "kind": "mechanical", "impl": "rm-rf", "blocking_when": "fail"}}},
     "L-IMPL-UNKNOWN"),
]


@pytest.mark.parametrize("name,doc,code", DATA_ONLY, ids=[d[0] for d in DATA_ONLY])
def test_gp_9_a_parent_cannot_hold_settings_unlocks_or_unknown_implementations(
        tmp_path, name, doc, code):
    exit_code, report, _ = _lint_parent(tmp_path, doc)
    assert exit_code == 1
    assert code in _codes(report), report
    assert report["stopped_after"] == "layer"
    blamed = next(f for f in report["findings"] if f["code"] == code)
    assert blamed["layer"].startswith("github:acme/bank@1.2.0#"), blamed


def test_gp_9_a_parent_that_is_not_a_mapping_is_a_finding_not_a_crash(tmp_path):
    code, report, err = _lint_parent(tmp_path, ["not", "a", "mapping"])
    assert code == 1 and "Traceback" not in err
    assert _codes(report) == ["L-SCHEMA"], report
    assert report["findings"][0]["layer"].startswith("github:acme/bank@1.2.0#")


def test_gp_9_a_parent_with_a_non_text_key_is_a_finding_not_a_crash(tmp_path):
    code, report, err = _lint_parent(tmp_path, "schema: 1\nowner: x\non: yes\n")
    assert code == 1 and "Traceback" not in err
    assert _codes(report) == ["L-KEY-NOT-TEXT"], report


def test_gp_2_a_refusal_names_each_layer_once(tmp_path):
    root = _project(tmp_path, "github:acme/bank@1.2.0")
    _, report, _ = _lint(root)
    names = [(layer["name"], layer["kind"]) for layer in report["layers"]]
    assert names == [("default", "parent"), ("project", "project")], names


# --- GP-10: policy effective shows the parent as a source -------------------------------------

EFFECTIVE_DOC = {"schema": 1, "owner": "platform-team", "checks": {"parent-check": {
    "statement": "A check the parent adds.", "kind": "deterministic", "impl": "suite-passed",
    "severity": "advisory", "on_skipped": "fail"}}}


def _effective(tmp_path, *extra):
    base = tmp_path / "remotes"
    sha = make_remote(base, files={"compass.yml": yaml.safe_dump(EFFECTIVE_DOC)})
    root = _project(tmp_path, _ref(sha))
    code, out, err = _run(root, "policy", "effective", *extra,
                          env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    return code, out, err, sha


def test_gp_10_a_field_the_parent_wrote_shows_the_parent_as_its_source(tmp_path):
    code, out, err, sha = _effective(tmp_path, "--json")
    assert code == 0, err
    document = json.loads(out)
    label = f"github:acme/bank@1.2.0#{sha[:7]}"
    rows = {row["path"]: row for row in document["fields"]}
    assert rows["owner"]["source"] == label
    assert rows["checks.parent-check.statement"]["source"] == label
    parent = next(layer for layer in document["layers"] if layer["name"] == label)
    assert parent["kind"] == "parent" and parent["version"] == "1.2.0"
    assert parent["digest"].startswith("sha256:")
    shipped = next(layer for layer in document["layers"] if layer["name"] == "default")
    assert shipped["version"] and shipped["version"] != "1.2.0"


def test_gp_10_the_text_view_names_the_parent_in_the_layers_and_the_source_column(tmp_path):
    code, out, err, sha = _effective(tmp_path)
    assert code == 0, err
    label = f"github:acme/bank@1.2.0#{sha[:7]}"
    assert f"{label}@1.2.0" in out.splitlines()[0]
    assert any(line.startswith("owner") and line.rstrip().endswith(f"{label} (add)")
               for line in out.splitlines()), out


# --- GP-11: a parent that names a git parent --------------------------------------------------

def test_gp_11_a_parent_that_names_a_git_parent_is_fetched_and_a_missing_one_is_refused(
        tmp_path):
    # Chains are built (issue `parent-chains`): the inner parent is fetched like any
    # other, and one the remote does not have is a fetch refusal on the naming parent.
    inner = "github:acme/inner@1.0.0#" + "f" * 40
    code, report, _ = _lint_parent(tmp_path, {"schema": 1, "extends": inner})
    assert code == 1
    assert _codes(report) == ["L-PARENT-FETCH"], report
    finding = report["findings"][0]
    assert finding["layer"].startswith("github:acme/bank@1.2.0#") and finding["path"] == "extends"


def test_gp_11_a_parent_with_a_bad_spelling_is_refused_in_its_own_layer(tmp_path):
    code, report, _ = _lint_parent(tmp_path, {"schema": 1, "extends": "github:-x/y@1#" + SHA})
    assert code == 1
    assert _codes(report) == ["L-PARENT-FORM"], report
    assert report["findings"][0]["layer"].startswith("github:acme/bank@1.2.0#")


def test_gp_11_a_parent_that_extends_the_shipped_default_is_accepted(tmp_path):
    code, report, err = _lint_parent(
        tmp_path, {"schema": 1, "extends": "compass:default@6", "owner": "platform-team"})
    assert code == 0, (report, err)


# --- GP-12: versions.yml records the parent ----------------------------------------------------

def test_gp_12_versions_yml_records_the_parent_ref_sha_version_and_digest(
        tmp_path, monkeypatch):
    from parent_fixtures import commit, issue_project
    base = tmp_path / "remotes"
    sha = make_remote(base, files={"compass.yml": yaml.safe_dump(EFFECTIVE_DOC)})
    root, task_dir = issue_project(tmp_path, _ref(sha))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    monkeypatch.chdir(root)
    assert commit(task_dir).committed
    stored = yaml.safe_load((task_dir / "generations" / "1" / "versions.yml")
                            .read_text(encoding="utf-8"))
    assert [p["source"] for p in stored["parents"]] == ["shipped", "git"]
    assert stored["parents"][0]["ref"] == "compass:default@6"
    # The classification block is pinned in test_preset_interfaces.py (PI-3).
    held = dict(stored["parents"][1])
    assert held.pop("classification")["against"] == "compass:default@6"
    assert held == {
        "ref": "github:acme/bank@1.2.0", "sha": sha, "version": "1.2.0",
        "digest": stored["parents"][1]["digest"], "source": "git"}
    assert stored["parents"][1]["digest"].startswith("sha256:")
    resolved = yaml.safe_load((task_dir / "generations" / "1" / "resolved.yml")
                              .read_text(encoding="utf-8"))
    assert resolved["checks"]["parent-check"]["statement"] == "A check the parent adds."


def test_gp_12_a_project_with_the_shipped_default_records_no_git_parent(tmp_path, monkeypatch):
    from parent_fixtures import commit, issue_project
    root, task_dir = issue_project(tmp_path, "compass:default@6")
    monkeypatch.chdir(root)
    assert commit(task_dir).committed
    stored = yaml.safe_load((task_dir / "generations" / "1" / "versions.yml")
                            .read_text(encoding="utf-8"))
    assert [p["source"] for p in stored["parents"]] == ["shipped"]


def test_gp_12_assessing_an_issue_fetches_the_pin_and_stores_the_parent(tmp_path):
    from parent_fixtures import issue_project
    base = tmp_path / "remotes"
    sha = make_remote(base)
    root, task_dir = issue_project(tmp_path, _ref(sha))
    code, out, err = _run(root, "approach", "evaluate", "--issue", "feature", "--write",
                          env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 0, err
    stored = yaml.safe_load((task_dir / "generations" / "1" / "versions.yml")
                            .read_text(encoding="utf-8"))
    assert stored["parents"][-1]["sha"] == sha
    assert (_folder(root, sha) / "compass.yml").is_file()


def test_gp_12_checking_an_issue_never_fetches_an_uncached_pin(tmp_path):
    from parent_fixtures import issue_project
    bin_dir, log = fake_git(tmp_path)
    root, _ = issue_project(tmp_path, _ref("9" * 40))
    code, out, err = _run(root, "check", "--issue", "feature",
                          env={"PATH": f"{bin_dir}:{REAL_GIT}"})
    assert code != 0 and "L-PARENT-NOT-CACHED" in err + out
    assert not log.exists(), "compass check ran git"


# --- GP-14: a short sha ----------------------------------------------------------------------

def test_gp_14_a_short_sha_resolves_against_exactly_one_cached_commit(tmp_path):
    root, sha, _ = _cached_project(tmp_path)
    (root / "compass.yml").write_text(
        yaml.safe_dump({"schema": 1, "extends": _ref(sha[:7])}), encoding="utf-8")
    bin_dir, log = fake_git(tmp_path)
    code, out, err = _run(root, "policy", "effective", "--json", env={"PATH": f"{bin_dir}:{REAL_GIT}"})
    assert code == 0, err
    assert not log.exists()
    assert any(layer["name"].endswith(f"#{sha[:7]}") for layer in json.loads(out)["layers"])


def test_gp_14_a_short_sha_that_names_two_cached_commits_is_ambiguous(tmp_path):
    root = _project(tmp_path, _ref("abcdef0"))
    for tail in ("1" * 33, "2" * 33):
        folder = _folder(root, "abcdef0" + tail)
        folder.mkdir(parents=True)
        (folder / "compass.yml").write_text(yaml.safe_dump(PARENT_DOC), encoding="utf-8")
    code, report, _ = _lint(root, "--offline")
    assert code == 1
    assert _codes(report) == ["L-PARENT-SHA-AMBIGUOUS"], report


def test_gp_14_a_short_sha_that_is_not_cached_asks_for_the_full_sha(tmp_path):
    bin_dir, log = fake_git(tmp_path)
    root = _project(tmp_path, _ref("abcdef0"))
    code, report, _ = _lint(root, env={"PATH": f"{bin_dir}:{REAL_GIT}"})
    assert code == 1
    assert _codes(report) == ["L-PARENT-FORM"], report
    assert "40" in report["findings"][0]["message"]
    assert not log.exists(), "git cannot fetch a short sha, so it must not be run"


# --- GP-3 (content): what a parent must hold -----------------------------------------------------

@pytest.mark.parametrize("files", [
    {"README.md": "no parent file"},
    {"compass.yml/inner.yml": "schema: 1\n"},
    {"compass.yml": "# " + "x" * (1024 * 1024 + 1) + "\nschema: 1\n"},
], ids=["missing", "a-folder", "too-large"])
def test_gp_3_a_repository_without_a_usable_compass_yml_is_refused(tmp_path, files):
    base = tmp_path / "remotes"
    sha = make_remote(base, files=files)
    root = _project(tmp_path, _ref(sha))
    code, report, _ = _lint(root, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 1
    assert _codes(report) == ["L-PARENT-CONTENT"], report
    assert not (_folder(root, sha)).exists()


def test_gp_3_a_submodule_in_place_of_compass_yml_is_not_a_parent_file(tmp_path):
    from parent_fixtures import _git
    base = tmp_path / "remotes"
    make_remote(base, files={"README.md": "x"})
    repo = base / "acme" / "bank.git"
    _git(repo, "update-index", "--add", "--cacheinfo", f"160000,{'1' * 40},compass.yml")
    _git(repo, "commit", "--quiet", "-m", "gitlink")
    sha = _git(repo, "rev-parse", "HEAD")
    root = _project(tmp_path, _ref(sha))
    _, report, _ = _lint(root, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert _codes(report) == ["L-PARENT-CONTENT"], report
    assert "has no compass.yml" in report["findings"][0]["message"]


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


def test_gp_15_the_lint_doc_lists_the_codes_and_the_flag():
    doc = _text("docs", "policy-lint.md")
    for code in _parent_codes():
        assert code in doc, code
    assert "--offline" in doc and "git-parents.md" in doc


def test_gp_15_the_generation_doc_describes_a_git_parent_entry():
    doc = _text("docs", "generation-store.md")
    assert "source: git" in doc and "git-parents.md" in doc


@pytest.mark.parametrize("verb", ["lint", "effective"])
def test_gp_15_help_describes_the_flag_and_the_git_parent(tmp_path, verb):
    from compass_pkg import verb_help
    text = verb_help.VERB_DESCRIPTIONS[f"policy {verb}"]
    assert "git parent" in text and "--offline" in text
    code, out, _ = _run(tmp_path, "policy", verb, "--help")
    assert code == 0 and "--offline" in out and "COMPASS_OFFLINE" in out


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


def test_gp_15_seen_yml_and_the_versions_entry_have_the_pinned_keys(tmp_path):
    root, sha, _ = _cached_project(tmp_path)
    seen = yaml.safe_load((_cache(root) / "seen.yml").read_text(encoding="utf-8"))
    assert list(seen) == ["refs", "schema"] or sorted(seen) == ["refs", "schema"]
    assert sorted(seen["refs"]["github:acme/bank@1.2.0"]) == [
        "content_digest", "fetched", "sha", "version"]


# --- GP-16: the README and security.md say the fetch happens -------------------------------------

def test_gp_16_the_readme_lists_the_git_fetch_and_no_longer_says_it_has_one_web_request():
    readme = _text("README.md")
    section = readme.split("## What Compass runs, sends and fetches")[1].split("\n## ")[0]
    flat = " ".join(section.split())
    assert "only web request" not in flat
    for needle in ("git parent", "compass policy lint", "compass policy effective",
                   "compass approach evaluate --write", "never `compass check`", "--offline",
                   "COMPASS_OFFLINE", "COMPASS_PARENT_REMOTE_BASE"):
        assert needle in flat, needle


def test_gp_16_security_says_a_parent_is_data_and_is_fetched():
    doc = " ".join(_text("docs", "security.md").split())
    assert "git parent" in doc and "is data" in doc and "fetch" in doc
    assert "git-parents.md" in doc


# --- GP-17: the cache is keyed by repository and sha -----------------------------------------------

def test_gp_17_another_repository_never_loads_a_cached_commit(tmp_path):
    root, sha, _ = _cached_project(tmp_path)
    (root / "compass.yml").write_text(
        yaml.safe_dump({"schema": 1, "extends": _ref(sha, owner="someone", repo="else")}),
        encoding="utf-8")
    bin_dir, log = fake_git(tmp_path)
    code, report, _ = _lint(root, "--offline", env={"PATH": f"{bin_dir}:{REAL_GIT}"})
    assert code == 1
    assert _codes(report) == ["L-PARENT-NOT-CACHED"], report
    assert not log.exists()


def test_gp_17_a_short_sha_matches_cached_commits_of_the_same_repository_only(tmp_path):
    root = _project(tmp_path, _ref("abcdef0", owner="other", repo="repo"))
    folder = _folder(root, "abcdef0" + "1" * 33)
    folder.mkdir(parents=True)
    (folder / "compass.yml").write_text(yaml.safe_dump(PARENT_DOC), encoding="utf-8")
    code, report, _ = _lint(root, "--offline")
    assert code == 1
    assert _codes(report) == ["L-PARENT-FORM"], report


def test_gp_17_the_cache_keeps_a_commit_under_owner_repository_and_sha(tmp_path):
    root, sha, _ = _cached_project(tmp_path)
    assert (_cache(root) / "acme" / "bank" / sha / "compass.yml").is_file()
    assert not (_cache(root) / sha).exists()


# --- GP-18: what git sees ---------------------------------------------------------------------

def test_gp_18_the_doc_says_the_users_credential_helper_runs_and_ci_needs_credentials():
    doc = " ".join(_text("docs", "git-parents.md").split())
    for needle in ("credential helper", "insteadOf", "GIT_CONFIG_GLOBAL", "GIT_ASKPASS",
                   "CI", "ref label is not checked", "without warning"):
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

def test_gp_20_compass_yml_below_the_root_is_not_a_parent_file(tmp_path):
    base = tmp_path / "remotes"
    sha = make_remote(base, files={"sub/compass.yml": yaml.safe_dump(PARENT_DOC)})
    root = _project(tmp_path, _ref(sha))
    _, report, _ = _lint(root, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert _codes(report) == ["L-PARENT-CONTENT"], report


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


def test_gp_20_the_content_digest_is_the_digest_of_the_cached_bytes(tmp_path):
    import hashlib
    root, sha, _ = _cached_project(tmp_path)
    raw = (_folder(root, sha) / "compass.yml").read_bytes()
    seen = yaml.safe_load((_cache(root) / "seen.yml").read_text(encoding="utf-8"))
    assert seen["refs"]["github:acme/bank@1.2.0"]["content_digest"] \
        == "sha256:" + hashlib.sha256(raw).hexdigest()


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


def test_gp_20_the_short_sha_filter_ignores_names_that_are_not_full_shas(tmp_path):
    root = _project(tmp_path, _ref("abcdef0"))
    good = _folder(root, "abcdef0" + "1" * 33)
    good.mkdir(parents=True)
    (good / "compass.yml").write_text(yaml.safe_dump(PARENT_DOC), encoding="utf-8")
    for name in ("abcdef0" + "g" * 33, "abcdef0" + "2" * 32, "ABCDEF0" + "2" * 33):
        (_folder(root, name)).mkdir(parents=True)
    code, report, err = _lint(root, "--offline")
    assert code == 0, (report, err)


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


def test_gp_21_a_tree_sha_in_place_of_a_commit_is_a_spelling_fault(tmp_path):
    from parent_fixtures import _git
    base = tmp_path / "remotes"
    make_remote(base)
    tree = _git(base / "acme" / "bank.git", "rev-parse", "HEAD^{tree}")
    root = _project(tmp_path, _ref(tree))
    code, report, _ = _lint(root, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 1
    assert _codes(report) in (["L-PARENT-FORM"],), report
    assert "commit" in report["findings"][0]["message"]


# --- GP-22: a waiver in a git parent answers to the parent's owner --------------------------------

def _chain_report(parent_owner, approver, project_owner="project-owner"):
    from compass_pkg import layers, policy_lint
    sys.path.insert(0, str(ROOT / "tests"))
    import waiver_fixtures as fx
    default, _ = policy_lint.load_parent()
    doc = {"schema": 1, "checks": {"dor-summary-filled": {
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
