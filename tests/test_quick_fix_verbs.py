"""`compass quick-fix start` and `compass quick-fix finish`.

A B6 comparison session spent 19 to 22 model calls on a quick fix, most of
them mechanical steps an agent drove one at a time - init, write the
manifest from a template it read in full, evaluate, write the approach
record, register it, trace files, check, record the check, pass three
gates, devlog, commit. These two verbs do those same steps, through the
same code, in two calls.

Scenario ids: QFO-1 to QFO-5, in the acceptance criteria of the issue
quick-fix-overhead/acceptance-criteria.md. QFG-1 and QFG-2 are in the
acceptance criteria of quick-fix-finish-gaps/acceptance-criteria.md.
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


def _git(root, *args):
    return subprocess.run([*GIT, *args], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()


def _run(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True)


def _run_from(cwd, *args):
    """Like `_run`, but from a directory that need not be the project root
    (QFG-2)."""
    return subprocess.run([sys.executable, str(CLI), *args], cwd=cwd,
                          capture_output=True, text=True)


def _manifest(root, slug):
    return yaml.safe_load(
        (root / ".compass" / "work" / slug / "manifest.yml").read_text())


def _manifest_path(root, slug):
    return root / ".compass" / "work" / slug / "manifest.yml"


def _save_manifest(root, slug, manifest):
    (_manifest_path(root, slug)).write_text(
        yaml.safe_dump(manifest, sort_keys=False, default_flow_style=False))


def _gate_statuses(root, slug):
    return {g["id"]: g["status"] for g in _manifest(root, slug)["gates"]}


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    # The CLI commits in this repository with plain git, so it needs an
    # identity of its own: a CI runner has no global one to fall back on.
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("hello\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _start(root, slug, **over):
    args = [
        "quick-fix", "start", slug,
        "--risk", over.get("risk", "trivial - a one-line text change"),
        "--familiarity", over.get(
            "familiarity",
            "brownfield-mapped - the file and its test already exist"),
        "--size", over.get("size", "atomic - one file, one obvious change"),
        "--intent", over.get(
            "intent",
            "A quick fix ships with the same three gates and less overhead."),
        "--scenario", over.get(
            "scenario",
            "Given the greeting template, when it is read, then it says "
            "'Hello, %s!'."),
        "--scenario-id", over.get("scenario_id", "TRC-001"),
        "--test", over.get(
            "test", "tests/test_greeting.py::test_greeting_says_hello"),
    ]
    if "goal" in over:
        args += ["--goal", over["goal"]]
    if "role" in over:
        args += ["--role", over["role"]]
    return _run(root, *args)


def _write_greeting(root, text):
    d = root / "data"
    d.mkdir(exist_ok=True)
    (d / "greeting.txt").write_text(text)


def _write_greeting_test(root):
    d = root / "tests"
    d.mkdir(exist_ok=True)
    (d / "test_greeting.py").write_text(
        "import pathlib\n\n\n"
        "def test_greeting_says_hello():\n"
        "    p = (pathlib.Path(__file__).resolve().parent.parent / 'data' "
        "/ 'greeting.txt')\n"
        "    assert p.read_text().strip() == 'Hello, %s!'\n"
    )


GREET_CMD = ["--", "python3", "-m", "pytest", "-q",
             "tests/test_greeting.py::test_greeting_says_hello"]


def _finish(root, slug, *extra, command=GREET_CMD):
    return _run(root, "quick-fix", "finish", "--issue", slug, "-m",
                "Say hello properly", *extra, *command)


def _base_greeting(root):
    """The code and its test as a project has them before a fix begins:
    committed. `finish` refuses a file that was already changed or
    untracked when the quick fix started, so a test's setup must not
    leave one."""
    _write_greeting(root, "Hi, %s!")
    _write_greeting_test(root)
    _git(root, "add", "data/greeting.txt", "tests/test_greeting.py")
    _git(root, "commit", "-q", "-m", "greeting")


def _ready_to_finish(root, slug, scenario_id="TRC-001"):
    """A started quick fix with a red on record and the fix written, not yet
    finished - `finish` records the green itself. The state every QFO-5
    refusal test starts from before it breaks exactly one condition."""
    _base_greeting(root)
    start = _start(root, slug, scenario_id=scenario_id)
    assert start.returncode == 0, start.stderr

    red = _run(root, "tdd-red", "--issue", slug, "--scenario", scenario_id,
              "--", "python3", "-m", "pytest", "-q",
              "tests/test_greeting.py::test_greeting_says_hello")
    assert red.returncode == 0, red.stderr

    _write_greeting(root, "Hello, %s!")


# --- QFO-1 -------------------------------------------------------------

def test_qfo1_start_records_the_whole_assessment_in_one_call(repo):
    result = _start(repo, "greet-fix")
    assert result.returncode == 0, result.stderr

    manifest = _manifest(repo, "greet-fix")
    assert manifest["delivery_approach"] == "quick-fix"
    assert manifest["assessment"]["risk"] == "trivial"
    assert manifest["assessment"]["familiarity"] == "brownfield-mapped"
    assert manifest["assessment"]["size"] == "atomic"
    assert manifest["stages"]["refine"] == "collapsed"

    scenarios = manifest.get("scenarios") or []
    assert len(scenarios) == 1
    assert scenarios[0]["id"] == "TRC-001"
    assert scenarios[0]["intent"] == "INT-1"
    assert scenarios[0]["tests"] == [
        "tests/test_greeting.py::test_greeting_says_hello"]

    doc = (repo / "docs" / "compass" / f"{manifest['created']}-greet-fix"
           / "delivery-approach.md")
    assert doc.is_file()
    content = doc.read_text()
    assert "quick fix" in content.lower()
    assert "TRC-001" in content
    assert "INT-1" in content

    artifact = next(a for a in manifest["artifacts"]
                    if a["kind"] == "delivery-approach")
    assert artifact["status"] == "draft"

    current_task = (repo / ".compass" / "current-task").read_text().strip()
    assert current_task == "greet-fix"


# --- QFO-2 -------------------------------------------------------------

def test_qfo2_start_stops_when_the_approach_is_not_a_quick_fix(repo):
    result = _start(repo, "bigger-change",
                    size="standard - several files and a design choice")
    assert result.returncode == 1

    manifest = _manifest(repo, "bigger-change")
    assert manifest["delivery_approach"] == "feature"
    assert not (manifest.get("scenarios") or [])

    doc_dir = repo / "docs" / "compass"
    assert not (doc_dir.is_dir()
               and any(doc_dir.glob("*/delivery-approach.md")))

    heard = result.stdout + result.stderr
    assert "/compass:assess" in heard
    # The pointer stays where it was: nothing was started.
    assert not (repo / ".compass" / "current-task").is_file() or (
        (repo / ".compass" / "current-task").read_text().strip()
        != "bigger-change")


def test_qfo3_start_refuses_a_slug_that_is_not_one_segment(repo):
    result = _start(repo, "../../escaped")
    assert result.returncode != 0
    assert "one path segment" in (result.stdout + result.stderr)
    assert not (repo.parent.parent / "escaped").exists()
    assert not (repo / ".compass" / "current-task").is_file()


def test_qfo1_start_prints_the_rest_of_the_path(repo):
    # A session that reached start from /compass:assess has not read the
    # quick-fix command. The hand-off is where it learns how to finish.
    result = _start(repo, "greet-path")
    assert result.returncode == 0, result.stderr
    assert "compass tdd-red --scenario TRC-001" in result.stdout
    assert "compass quick-fix finish" in result.stdout
    assert "--no-commit" in result.stdout


def test_qfo1_start_says_when_it_creates_a_directory(repo):
    result = _start(repo, "greet-new")
    assert result.returncode == 0, result.stderr
    assert ".compass/" in result.stdout
    assert "docs/compass/" in result.stdout


# --- QFO-3 -------------------------------------------------------------

def test_qfo3_start_refuses_a_dimension_with_no_reason(repo):
    result = _start(repo, "no-reason-fix", risk="trivial")
    assert result.returncode != 0
    assert "risk" in (result.stdout + result.stderr).lower()
    assert not (repo / ".compass" / "work" / "no-reason-fix").exists()


def test_qfo3_start_refuses_a_value_the_policy_does_not_know(repo):
    result = _start(repo, "bad-value-fix", risk="dangerous - my own word")
    assert result.returncode != 0
    assert "risk" in (result.stdout + result.stderr).lower()
    assert not (repo / ".compass" / "work" / "bad-value-fix").exists()


# --- QFO-4 -------------------------------------------------------------

def test_qfo4_finish_traces_checks_passes_the_three_gates_and_lands(repo):
    slug = "greet-ship"
    _ready_to_finish(repo, slug)
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo, slug)
    assert finish.returncode == 0, finish.stderr

    head_after = _git(repo, "rev-parse", "HEAD")
    assert head_after != head_before

    manifest = _manifest(repo, slug)
    assert manifest["status"] == "landed"
    for gid in ("verify.correctness", "verify.governance",
                "verify.traceability"):
        gate = next(g for g in manifest["gates"] if g["id"] == gid)
        assert gate["status"] == "pass"
        assert gate["evidence"]

    changed = {cf["path"] for cf in manifest["changed_files"]}
    assert "data/greeting.txt" in changed
    doc_path = f"docs/compass/{manifest['created']}-{slug}/delivery-approach.md"
    assert doc_path in changed

    check_evidence = next(e for e in manifest["evidence"]
                          if e["type"] == "command-output")
    assert (repo / ".compass" / "work" / slug
           / check_evidence["path"]).is_file()

    devlog = (repo / ".compass" / "work" / slug / "devlog.md").read_text()
    assert "Say hello properly" in devlog
    assert any(e["id"] in devlog for e in manifest["evidence"])


def test_qfo4_finish_leaves_bytecode_caches_out_and_the_land_checks_clean(repo):
    # A Python fix leaves `__pycache__/` behind whenever the project has no
    # .gitignore for it. A cache is not a change: traced and committed, it
    # makes the landed files differ from the tested ones, and `compass
    # check` then fails the issue it has just landed.
    slug = "add-fix"
    (repo / "pytest.ini").write_text("[pytest]\npythonpath = .\n")
    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "calc")
    start = _start(repo, slug, test="tests/test_calc.py::test_add")
    assert start.returncode == 0, start.stderr
    (repo / "tests").mkdir()
    (repo / "tests" / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    cmd = ["--", "python3", "-m", "pytest", "-q", "tests/test_calc.py"]
    red = _run(repo, "tdd-red", "--issue", slug, "--scenario", "TRC-001", *cmd)
    assert red.returncode == 0, red.stderr
    # A different size from the broken line, so Python does not reuse the
    # bytecode it cached for that line within the same second.
    (repo / "calc.py").write_text("def add(a, b):\n    total = a + b\n    return total\n")
    green = _run(repo, "tdd-green", "--issue", slug, "--scenario", "TRC-001", *cmd)
    assert green.returncode == 0, green.stderr
    assert list(repo.rglob("*.pyc")), "the test run should leave a cache"

    finish = _run(repo, "quick-fix", "finish", "--issue", slug, "-m", "Fix add", *cmd)
    assert finish.returncode == 0, finish.stderr

    changed = {cf["path"] for cf in _manifest(repo, slug)["changed_files"]}
    assert not [p for p in changed if "__pycache__" in p or p.endswith(".pyc")]
    committed = _git(repo, "show", "--name-only", "--format=", "HEAD~1")
    assert "__pycache__" not in committed
    check = _run(repo, "check", "--issue", slug)
    assert check.returncode == 0, check.stdout + check.stderr


def test_qfo4_finish_lands_clean_when_every_changed_file_was_tracked(repo):
    # The test file exists before the fix, so tracing at finish adds no new
    # file to the git tree - only to the set of files the green covers. The
    # green finish re-runs over that set is a new assertion, not a retry of
    # a flaky test, and the landed issue must check clean.
    slug = "add-tracked"
    (repo / "pytest.ini").write_text("[pytest]\npythonpath = .\n")
    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_zero():\n    assert add(0, 0) == 0\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "calc")
    start = _start(repo, slug, test="tests/test_calc.py::test_add")
    assert start.returncode == 0, start.stderr
    with open(repo / "tests" / "test_calc.py", "a") as fh:
        fh.write("\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    cmd = ["--", "python3", "-m", "pytest", "-q", "tests/test_calc.py"]
    red = _run(repo, "tdd-red", "--issue", slug, "--scenario", "TRC-001", *cmd)
    assert red.returncode == 0, red.stderr
    (repo / "calc.py").write_text(
        "def add(a, b):\n    total = a + b\n    return total\n")
    green = _run(repo, "tdd-green", "--issue", slug, "--scenario", "TRC-001", *cmd)
    assert green.returncode == 0, green.stderr

    finish = _run(repo, "quick-fix", "finish", "--issue", slug, "-m", "Fix add", *cmd)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    check = _run(repo, "check", "--issue", slug)
    assert check.returncode == 0, check.stdout + check.stderr


def _files_in_head(root):
    return set(_git(root, "show", "--name-only", "--format=", "HEAD~1").split())


def test_fuu1_an_untracked_file_from_before_start_is_refused(repo):
    """A local file nobody traced must never be committed. This is how
    private notes reached a public branch."""
    (repo / "notes").mkdir()
    (repo / "notes" / "private.md").write_text("not for publishing\n")
    _ready_to_finish(repo, "greet-private")
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo, "greet-private")
    heard = finish.stdout + finish.stderr
    assert finish.returncode != 0, heard
    assert "notes/private.md" in heard
    assert "changed-file add" in heard
    assert all(v != "pass" for v in _gate_statuses(repo, "greet-private").values())
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_fuu2_a_tracked_file_modified_before_start_is_refused(repo):
    (repo / "README.md").write_text("an edit that is not this fix\n")
    _ready_to_finish(repo, "greet-dirty")
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo, "greet-dirty")
    assert finish.returncode != 0
    assert "README.md" in finish.stdout + finish.stderr
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_fuu3_a_file_from_before_start_is_committed_once_traced(repo):
    (repo / "notes").mkdir()
    (repo / "notes" / "fix.md").write_text("part of this fix\n")
    _ready_to_finish(repo, "greet-traced")
    traced = _run(repo, "changed-file", "add", "notes/fix.md", "--issue",
                  "greet-traced", "--scenario", "TRC-001")
    assert traced.returncode == 0, traced.stderr

    finish = _finish(repo, "greet-traced")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert "notes/fix.md" in _files_in_head(repo)


def test_fuu4_files_made_after_start_and_declared_tests_need_no_trace(repo):
    slug = "greet-new-files"
    _write_greeting(repo, "Hi, %s!")
    _git(repo, "add", "data/greeting.txt")
    _git(repo, "commit", "-q", "-m", "greeting")
    assert _start(repo, slug).returncode == 0
    _write_greeting_test(repo)                     # the declared test, new
    red = _run(repo, "tdd-red", "--issue", slug, "--scenario", "TRC-001",
               *GREET_CMD)
    assert red.returncode == 0, red.stderr
    _write_greeting(repo, "Hello, %s!")
    (repo / "data" / "helper.txt").write_text("made by the fix\n")

    finish = _finish(repo, slug)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    files = _files_in_head(repo)
    assert {"tests/test_greeting.py", "data/helper.txt",
            "data/greeting.txt"} <= files


def test_fuu1_the_start_record_names_no_local_file(repo):
    """The start record holds the names it protects, so it must never sit
    where a commit can take it: it lives inside the git directory, not with
    the issue's records, which a project may commit."""
    (repo / "notes").mkdir()
    (repo / "notes" / "acquisition-plan.md").write_text("private\n")
    _ready_to_finish(repo, "greet-names")
    records = repo / ".compass" / "work" / "greet-names"
    assert not any("acquisition" in f.read_text(errors="ignore")
                   for f in records.rglob("*") if f.is_file())
    git_record = repo / _git(repo, "rev-parse", "--git-path",
                             "compass/start-state/greet-names.json")
    assert ".git" in git_record.parts
    assert "acquisition-plan.md" in git_record.read_text()


def test_fuu1_a_new_file_in_a_directory_untracked_before_start_is_refused(repo):
    """A directory nobody tracks, such as a local `.claude/`, stays local:
    a file written into it after `start` is refused like one from before."""
    (repo / "local").mkdir()
    (repo / "local" / "old.md").write_text("private\n")
    _ready_to_finish(repo, "greet-local-dir")
    (repo / "local" / "old.md").unlink()
    (repo / "local" / "new.md").write_text("also private\n")
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo, "greet-local-dir")
    assert finish.returncode != 0
    assert "local/new.md" in finish.stdout + finish.stderr
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_fuu1_a_directory_of_ignored_files_is_local_too(repo):
    """After Claude Code has run, `.claude/` often holds only an ignored
    `settings.local.json`. A plan written there after `start` is local."""
    (repo / ".gitignore").write_text("local/settings.json\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "ignore")
    (repo / "local").mkdir()
    (repo / "local" / "settings.json").write_text("{}\n")
    _ready_to_finish(repo, "greet-ignored-dir")
    (repo / "local" / "plan.md").write_text("private\n")

    finish = _finish(repo, "greet-ignored-dir")
    assert finish.returncode != 0
    assert "local/plan.md" in finish.stdout + finish.stderr


def test_fuu4_a_directory_holding_a_tracked_file_takes_new_files(repo):
    """A directory with a tracked file in it is the project's, so a new
    file the change writes there is committed, even when the directory
    also held an untracked file before `start`."""
    (repo / "data").mkdir()
    (repo / "data" / "keep.txt").write_text("tracked\n")
    _git(repo, "add", "data/keep.txt")
    _git(repo, "commit", "-q", "-m", "keep")
    (repo / "data" / "scratch.txt").write_text("untracked before start\n")
    _ready_to_finish(repo, "greet-mixed-dir")
    (repo / "data" / "scratch.txt").unlink()
    (repo / "data" / "extra.txt").write_text("made by the fix\n")

    finish = _finish(repo, "greet-mixed-dir")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert "data/extra.txt" in _files_in_head(repo)


def test_fuu4_a_declared_test_from_before_start_needs_no_trace(repo):
    """The test file the scenario declares may exist, untracked, before
    `start`: it is the change's by declaration."""
    slug = "greet-declared-early"
    _write_greeting(repo, "Hi, %s!")
    _git(repo, "add", "data/greeting.txt")
    _git(repo, "commit", "-q", "-m", "greeting")
    _write_greeting_test(repo)                     # untracked, before start
    assert _start(repo, slug).returncode == 0
    red = _run(repo, "tdd-red", "--issue", slug, "--scenario", "TRC-001",
               *GREET_CMD)
    assert red.returncode == 0, red.stderr
    _write_greeting(repo, "Hello, %s!")

    finish = _finish(repo, slug)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert "tests/test_greeting.py" in _files_in_head(repo)


def test_fuu2_the_refusal_gives_a_remedy_for_a_tracked_file(repo):
    (repo / "README.md").write_text("an edit that is not this fix\n")
    _ready_to_finish(repo, "greet-remedy")
    heard = _finish(repo, "greet-remedy")
    text = heard.stdout + heard.stderr
    assert "git restore" in text or "git stash" in text, text


def test_fuu5_with_no_start_state_an_undeclared_untracked_file_is_refused(repo):
    slug = "greet-no-state"
    _ready_to_finish(repo, slug)
    (repo / _git(repo, "rev-parse", "--git-path",
                 f"compass/start-state/{slug}.json")).unlink()
    (repo / "scratch.txt").write_text("whose is this?\n")

    finish = _finish(repo, slug)
    assert finish.returncode != 0
    heard = finish.stdout + finish.stderr
    assert "scratch.txt" in heard
    assert "before this quick fix started" not in heard, heard


def test_fuu6_finish_lists_every_file_it_commits(repo):
    _ready_to_finish(repo, "greet-list")
    finish = _finish(repo, "greet-list")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    listed = [l.split(":", 1)[1].strip() for l in finish.stdout.splitlines()
              if l.strip().startswith("commits")]
    records = ".compass/work/greet-list/"
    for path in _files_in_head(repo):
        if path.startswith(records):
            assert any(l.startswith(records) for l in listed), listed
        else:
            assert path in listed, (path, listed)


def test_fse1_a_new_file_with_an_unusual_name_lands(repo):
    slug = "greet-odd-names"
    _ready_to_finish(repo, slug)
    for name in ("notes with space.txt", "quote'd.txt", "caf\u00e9.txt"):
        (repo / "data" / name).write_text("made by the fix\n")

    finish = _finish(repo, slug)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    files = set(_git(repo, "show", "--name-only", "-z", "--format=",
                     "HEAD~1").split("\0"))
    for name in ("notes with space.txt", "quote'd.txt", "caf\u00e9.txt"):
        assert f"data/{name}" in files, files


def test_fse2_no_commit_reveals_a_local_path(repo):
    (repo / "notes").mkdir()
    (repo / "notes" / "acquisition-plan.md").write_text("private\n")
    _ready_to_finish(repo, "greet-no-trace")
    (repo / "notes" / "acquisition-plan.md").unlink()   # moved out
    finish = _finish(repo, "greet-no-trace")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    import hashlib
    digest = hashlib.sha256(b"notes/acquisition-plan.md").hexdigest()
    committed = _git(repo, "log", "-p", "--all", "--format=")
    assert "acquisition" not in committed
    assert digest not in committed
    assert not (repo / ".compass" / "work" / "greet-no-trace"
                / "start-state.json").exists()


def test_fse2_a_record_an_older_start_wrote_is_still_read(repo):
    import hashlib, json
    (repo / "notes").mkdir()
    (repo / "notes" / "old.md").write_text("private\n")
    _ready_to_finish(repo, "greet-old-record")
    task = repo / ".compass" / "work" / "greet-old-record"
    git_record = _git(repo, "rev-parse", "--git-path",
                      "compass/start-state/greet-old-record.json")
    (repo / git_record).unlink()
    (task / "start-state.json").write_text(json.dumps({
        "digest": "sha256",
        "changed_before_start": [hashlib.sha256(b"notes/old.md").hexdigest()],
        "untracked_dirs_before_start": []}))

    finish = _finish(repo, "greet-old-record")
    assert finish.returncode != 0
    assert "notes/old.md" in finish.stdout + finish.stderr


def test_fse3_every_commits_line_has_the_same_spacing(repo):
    _ready_to_finish(repo, "greet-spacing")
    (repo / "data" / "extra.txt").write_text("more\n")
    finish = _finish(repo, "greet-spacing")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    lines = [l for l in finish.stdout.splitlines()
             if l.strip().startswith("commits")]
    assert len(lines) >= 2
    assert len({l.index(":") for l in lines}) == 1, lines


def test_sjs2_a_differently_split_command_is_not_reused(repo):
    """Both commands join to `sh -c test a = a`. The first passes; the
    second runs `test` with no arguments and fails. Reusing the first
    green for the second would clear the gates on a command that fails."""
    slug = "greet-split"
    _ready_to_finish(repo, slug)
    first = _finish(repo, slug, "--no-commit",
                    command=["--", "sh", "-c", "test a = a"])
    assert first.returncode == 0, first.stdout + first.stderr
    second = _finish(repo, slug, "--no-commit",
                     command=["--", "sh", "-c", "test", "a", "=", "a"])
    assert second.returncode != 0, second.stdout


def test_sjs5_finish_lists_the_files_a_land_at_head_holds(repo):
    """When the agent committed the fix itself, `ship-commit` makes no
    commit and lands at HEAD; finish lists that commit's files, not the
    living spec's."""
    slug = "greet-precommitted"
    (repo / ".gitignore").write_text(".compass/\ndocs/\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "ignore records")
    _ready_to_finish(repo, slug)
    _git(repo, "add", "data/greeting.txt")
    _git(repo, "commit", "-q", "-m", "the fix, committed by hand")
    finish = _finish(repo, slug)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    listed = [l.split(":", 1)[1].strip() for l in finish.stdout.splitlines()
              if l.strip().startswith("commits")]
    assert "data/greeting.txt" in listed, listed


def test_sjs5_a_name_with_a_control_character_is_shown_quoted(repo):
    _ready_to_finish(repo, "greet-newline")
    (repo / "data" / "new\nline.txt").write_text("odd\n")
    finish = _finish(repo, "greet-newline")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert "'data/new\\nline.txt'" in finish.stdout, finish.stdout


def test_sjs6_the_start_record_is_gone_after_a_land(repo):
    _ready_to_finish(repo, "greet-cleanup")
    record = repo / _git(repo, "rev-parse", "--git-path",
                         "compass/start-state/greet-cleanup.json")
    assert record.exists()
    assert _finish(repo, "greet-cleanup").returncode == 0
    assert not record.exists()


def test_scf4_a_green_from_before_argv_is_reused(repo):
    """A quick fix finished with --no-commit before greens carried `argv`
    must still finish afterwards: rerunning the same command on the same
    tree is flagged as a rerun, so the old green has to be reused."""
    import json
    slug = "greet-old-green"
    _ready_to_finish(repo, slug)
    assert _finish(repo, slug, "--no-commit").returncode == 0
    record = (repo / ".compass" / "work" / slug / "evidence"
              / "green-TRC-001.json")
    data = json.loads(record.read_text())
    data.pop("argv", None)
    record.write_text(json.dumps(data))

    finish = _finish(repo, slug)
    assert finish.returncode == 0, finish.stdout + finish.stderr


# --- QFO-5 ---------------------------------------------------------------

def test_qfo5_finish_refuses_when_check_fails(repo):
    slug = "greet-ghost"
    _ready_to_finish(repo, slug)
    manifest = _manifest(repo, slug)
    # A changed file traced to a scenario the issue does not have: the
    # green passes, and `compass check`'s traceability guardrail fails.
    manifest.setdefault("changed_files", []).append(
        {"path": "data/greeting.txt", "scenarios": ["TRC-999"]})
    _save_manifest(repo, slug, manifest)
    before = _gate_statuses(repo, slug)
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo, slug)
    assert finish.returncode != 0
    heard = finish.stdout + finish.stderr
    assert "`compass check` failed" in heard, heard
    assert "Traceback" not in heard

    assert _gate_statuses(repo, slug) == before
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_qfo5_finish_refuses_when_another_gate_is_pending(repo):
    slug = "greet-extra-gate"
    _ready_to_finish(repo, slug)
    manifest = _manifest(repo, slug)
    manifest["gates"].append(
        {"id": "verify.clarity", "status": "pending", "evidence": []})
    _save_manifest(repo, slug, manifest)
    before = _gate_statuses(repo, slug)
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo, slug)
    assert finish.returncode != 0
    assert "verify.clarity" in (finish.stdout + finish.stderr)

    assert _gate_statuses(repo, slug) == before
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_qfo5_finish_refuses_when_no_red_is_on_record(repo):
    slug = "greet-no-red"
    _base_greeting(repo)
    start = _start(repo, slug)
    assert start.returncode == 0, start.stderr
    _write_greeting(repo, "Hello, %s!")
    before = _gate_statuses(repo, slug)
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo, slug)
    assert finish.returncode != 0
    assert "TRC-001" in (finish.stdout + finish.stderr)

    assert _gate_statuses(repo, slug) == before
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_qfo5_finish_refuses_without_a_test_command(repo):
    slug = "greet-no-cmd"
    _ready_to_finish(repo, slug)
    before = _gate_statuses(repo, slug)

    finish = _finish(repo, slug, command=[])
    assert finish.returncode != 0
    assert "--" in (finish.stdout + finish.stderr)
    assert _gate_statuses(repo, slug) == before


def test_qfo5_finish_refuses_again_after_a_failed_green(repo):
    # A refused call leaves its traces saved. A second call must still run
    # the green, and refuse again while the code is still broken.
    slug = "greet-twice"
    _ready_to_finish(repo, slug)
    _write_greeting(repo, "Still wrong, %s!")
    head_before = _git(repo, "rev-parse", "HEAD")

    first = _finish(repo, slug)
    assert first.returncode != 0
    second = _finish(repo, slug)
    assert second.returncode != 0
    assert "green" in (second.stdout + second.stderr)

    assert all(s != "pass" for s in _gate_statuses(repo, slug).values())
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_qfo5_finish_runs_the_command_exactly_as_given(repo):
    # A quoted `bash -c` command must run whole. Joined and split again it
    # would run `bash -c python3`, which passes without running a test.
    slug = "greet-quoted"
    _ready_to_finish(repo, slug)
    _write_greeting(repo, "Still wrong, %s!")
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo, slug, command=[
        "--", "bash", "-c",
        "python3 -m pytest -q tests/test_greeting.py::test_greeting_says_hello"])
    assert finish.returncode != 0
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_qfo4_finish_no_commit_passes_the_gates_and_leaves_the_change(repo):
    slug = "greet-no-commit"
    _ready_to_finish(repo, slug)
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo, slug, "--no-commit")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert "not committed" in finish.stdout

    assert set(_gate_statuses(repo, slug).values()) == {"pass"}
    assert _git(repo, "rev-parse", "HEAD") == head_before
    assert "data/greeting.txt" in _git(repo, "status", "--porcelain",
                                       "--untracked-files=all")


def test_qfo5_finish_refuses_an_untraced_path_with_several_scenarios(repo):
    slug = "greet-multi"
    _ready_to_finish(repo, slug)
    manifest = _manifest(repo, slug)
    manifest["scenarios"].append({
        "id": "TRC-002", "title": "a second scenario", "intent": "INT-1",
        "tests": ["tests/test_greeting.py::test_greeting_says_hello"],
    })
    manifest["evidence"].append({
        "id": "EV-T-TRC-002", "type": "test-run", "scenario": "TRC-002",
        "path": "evidence/green-TRC-001.json",
    })
    _save_manifest(repo, slug, manifest)
    # A second, untraced production change - ambiguous with two scenarios
    # on record, so it must not be guessed at.
    _write_greeting(repo, "Hello there, %s!")
    before = _gate_statuses(repo, slug)
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo, slug)
    assert finish.returncode != 0
    assert "data/greeting.txt" in (finish.stdout + finish.stderr)

    assert _gate_statuses(repo, slug) == before
    assert _git(repo, "rev-parse", "HEAD") == head_before


# --- QFG-1 ---------------------------------------------------------------

def test_qfg1_finish_after_no_commit_reuses_the_green_and_commits(repo):
    # `finish --no-commit` records a green and passes the gates. Asking for
    # the commit afterwards runs `finish` again with the same command on the
    # same tree - it must reuse that green rather than record a rerun, which
    # would fail `compass check` on the issue it has just landed.
    slug = "greet-nc-then-commit"
    _ready_to_finish(repo, slug)
    head_before = _git(repo, "rev-parse", "HEAD")

    first = _finish(repo, slug, "--no-commit")
    assert first.returncode == 0, first.stdout + first.stderr
    assert _git(repo, "rev-parse", "HEAD") == head_before

    second = _finish(repo, slug)
    assert second.returncode == 0, second.stdout + second.stderr
    assert _git(repo, "rev-parse", "HEAD") != head_before

    assert set(_gate_statuses(repo, slug).values()) == {"pass"}
    check = _run(repo, "check", "--issue", slug)
    assert check.returncode == 0, check.stdout + check.stderr


def test_qfg1_finish_succeeds_after_a_bad_trace_is_removed(repo):
    # A first call traces the files, records a green and then fails at
    # `compass check` for a reason outside the source tree - a trace to a
    # scenario the issue does not have. Fixing the manifest and calling
    # `finish` again, with the same command on the same tree, must reuse the
    # green rather than refuse it as a rerun; a third call with nothing
    # changed must succeed the same way.
    slug = "greet-badtrace"
    _ready_to_finish(repo, slug)
    manifest = _manifest(repo, slug)
    manifest.setdefault("changed_files", []).append(
        {"path": "data/greeting.txt", "scenarios": ["TRC-999"]})
    _save_manifest(repo, slug, manifest)
    head_before = _git(repo, "rev-parse", "HEAD")

    first = _finish(repo, slug, "--no-commit")
    assert first.returncode != 0
    assert "`compass check` failed" in (first.stdout + first.stderr)
    assert _git(repo, "rev-parse", "HEAD") == head_before

    manifest = _manifest(repo, slug)
    manifest["changed_files"] = [
        cf for cf in manifest["changed_files"]
        if cf.get("scenarios") != ["TRC-999"]]
    _save_manifest(repo, slug, manifest)

    second = _finish(repo, slug, "--no-commit")
    assert second.returncode == 0, second.stdout + second.stderr
    assert set(_gate_statuses(repo, slug).values()) == {"pass"}

    third = _finish(repo, slug, "--no-commit")
    assert third.returncode == 0, third.stdout + third.stderr
    assert set(_gate_statuses(repo, slug).values()) == {"pass"}
    check = _run(repo, "check", "--issue", slug)
    assert check.returncode == 0, check.stdout + check.stderr


# --- QFG-2 ---------------------------------------------------------------

def test_qfg2_finish_from_a_subdirectory_traces_stages_and_lands(repo):
    # A quick fix started at the project root, finished from `tests/` with a
    # test command written for that subdirectory. The command must run where
    # it was given; tracing, `compass check` and staging must run from the
    # project root, or `git add` on a root-relative path fails from `tests/`.
    slug = "greet-subdir"
    _ready_to_finish(repo, slug)
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _run_from(repo / "tests", "quick-fix", "finish",
                       "--issue", slug, "-m", "Say hello properly", "--",
                       "python3", "-m", "pytest", "-q",
                       "test_greeting.py::test_greeting_says_hello")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert _git(repo, "rev-parse", "HEAD") != head_before

    manifest = _manifest(repo, slug)
    assert manifest["status"] == "landed"
    assert set(_gate_statuses(repo, slug).values()) == {"pass"}
    changed = {cf["path"] for cf in manifest["changed_files"]}
    assert "data/greeting.txt" in changed
    check = _run(repo, "check", "--issue", slug)
    assert check.returncode == 0, check.stdout + check.stderr
