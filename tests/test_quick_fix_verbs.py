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

Every test here runs on the four-stage path (ADR-092). A quick fix there owes
the common evidence, `start` writes the acceptance criteria and no devlog, and
`finish` commits once a person has approved (ADR-099).
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
# The person who approves answers each request as a person at a terminal does.
_spec = importlib.util.spec_from_file_location(
    "two_command_e2e", ROOT / "scripts" / "two-command-e2e.py")
e2e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e2e)
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]

#: What every change owes on the path (ADR-099 decision 4).
COMMON = ["request", "scenarios", "red-before-green", "suite-green", "correctness",
          "governance", "traceability", "ship-approval"]


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
    # finish commits through the CLI, not through _git, so the identity must
    # live in the repository: a CI runner has no global git identity.
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
    # Assess records who asked and the link to the request (#356), so the check
    # `request-recorded` passes once the change lands. `request=False` leaves it out.
    if over.get("request", True):
        args += ["--request", "https://example.com/requests/" + slug,
                 "--requester", "Test fixture"]
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

#: The release line every finish here gives: a quick fix on the shipped default owes one,
#: and a landing refuses it without (ADR-065).
RELEASE_NOTE = ("--release-note", "Greetings now say hello.")

#: The candidate and client an outer-loop green names where the four-layer
#: acceptance strategy applies (ADR-085). An in-scope quick fix records the outer
#: loop; finish takes the two and does not write them on the inner loop.
NAMED = ("--candidate", "local", "--client", "cli")


def _finish(root, slug, *extra, command=GREET_CMD):
    note = () if "--release-note" in extra else RELEASE_NOTE
    named = () if "--candidate" in extra else NAMED
    return _run(root, "quick-fix", "finish", "--issue", slug, "-m",
                "Say hello properly", *note, *named, *extra, *command)


def _land(root, slug, *extra, command=GREET_CMD):
    """`finish`, the person's ship approval, and `finish` again: the second run
    commits (ADR-099 decision 7). Returns the last result."""
    first = _finish(root, slug, *extra, command=command)
    if first.returncode != 0 or "Nothing is committed" not in first.stdout:
        return first
    assert e2e.person_approves(root), first.stdout
    return _finish(root, slug, *extra, command=command)


def _base_greeting(root):
    """The code and its test as a project has them before a fix begins:
    committed. `finish` refuses a file that was already changed or
    untracked when the quick fix started, so a test's setup must not
    leave one."""
    _write_greeting(root, "Hi, %s!")
    _write_greeting_test(root)
    _git(root, "add", "data/greeting.txt", "tests/test_greeting.py")
    _git(root, "commit", "-q", "-m", "greeting")


def _ready_to_finish(root, slug, scenario_id="TRC-001", request=True):
    """A started quick fix with a red on record and the fix written, not yet
    finished - `finish` records the green itself. The state every QFO-5
    refusal test starts from before it breaks exactly one condition."""
    _base_greeting(root)
    start = _start(root, slug, scenario_id=scenario_id, request=request)
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
    # ADR-092 decisions: no approaches and no stage modes. The 8.x quick fix, with
    # its collapsed refine, is the light evidence row and has no `stages:` map.
    assert manifest["delivery_approach"] == "delivery"
    assert manifest["evidence_required"] == COMMON
    assert manifest["assessment"]["risk"] == "trivial"
    assert manifest["assessment"]["familiarity"] == "brownfield-mapped"
    assert manifest["assessment"]["size"] == "atomic"
    assert "stages" not in manifest

    scenarios = manifest.get("scenarios") or []
    assert len(scenarios) == 1
    assert scenarios[0]["id"] == "TRC-001"
    assert scenarios[0]["intent"] == "INT-1"
    assert scenarios[0]["tests"] == [
        "tests/test_greeting.py::test_greeting_says_hello"]

    # 9.0.0 writes no delivery-approach.md and registers no document (ADR-091). On
    # the path the acceptance criteria hold the intent and the scenario, and start
    # writes no devlog (ADR-092 decision 12).
    assert "artifacts" not in manifest
    assert not (repo / ".compass" / "work" / "greet-fix" / "devlog.md").exists()
    written = sorted(p.relative_to(repo).as_posix()
                     for p in (repo / "docs" / "compass").rglob("*") if p.is_file())
    assert len(written) == 1 and written[0].endswith("-greet-fix/acceptance-criteria.md"), \
        written
    criteria = (repo / written[0]).read_text()
    assert "INT-1 | quick-fix start | " in criteria
    assert "traceability id: TRC-001" in criteria and "serves: INT-1" in criteria

    current_task = (repo / ".compass" / "current-task").read_text().strip()
    assert current_task == "greet-fix"


# --- QFO-2 -------------------------------------------------------------

def test_qfo2_on_the_path_start_takes_heavier_work_and_names_what_it_owes(repo):
    """ADR-092 decision: the quick fix no longer refuses heavier work. Start records it, with its scenario, and the evidence
    the bigger change owes; the next step is the first thing it owes."""
    result = _start(repo, "bigger-change",
                    size="medium - several files and a design choice")
    assert result.returncode == 0, result.stdout + result.stderr

    manifest = _manifest(repo, "bigger-change")
    assert manifest["delivery_approach"] == "delivery"
    assert "stages" not in manifest
    # Size adds no review and no record (ADR-099 decision 4).
    assert manifest["evidence_required"] == COMMON
    assert [s["id"] for s in manifest["scenarios"]] == ["TRC-001"]
    assert all(g["status"] == "pending" for g in manifest["gates"])
    assert result.stdout.splitlines()[-1].startswith("next: "), result.stdout
    assert (repo / ".compass" / "current-task").read_text().strip() == "bigger-change"


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
    assert result.stdout.splitlines()[-1] == (
        'next: write the tests and the code, then compass quick-fix finish '
        '-m "<commit message>" -- <test command>')
    assert "compass tdd-red" not in result.stdout and "--no-commit" not in result.stdout


def test_qfo1_start_says_when_it_creates_a_directory(repo):
    result = _start(repo, "greet-new")
    assert result.returncode == 0, result.stderr
    created = [ln for ln in result.stdout.splitlines() if ln.strip().startswith("created:")]
    assert len(created) == 1 and ".compass/" in created[0], result.stdout
    assert "tell the user" in created[0], created
    # `start` prints no `record :` line: the acceptance criteria are named only
    # where a person must approve the scenarios (ADR-099).
    assert "record :" not in result.stdout
    spec = list((repo / "docs" / "compass").glob("*-greet-new/acceptance-criteria.md"))
    assert len(spec) == 1, spec


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

    finish = _land(repo, slug)
    assert finish.returncode == 0, finish.stdout + finish.stderr

    head_after = _git(repo, "rev-parse", "HEAD")
    assert head_after != head_before

    manifest = _manifest(repo, slug)
    assert manifest["status"] == "done" and manifest["close_reason"] == "completed"
    for gid in ("verify.correctness", "verify.governance",
                "verify.traceability"):
        gate = next(g for g in manifest["gates"] if g["id"] == gid)
        assert gate["status"] == "pass"
        assert gate["evidence"]

    changed = {cf["path"] for cf in manifest["changed_files"]}
    assert "data/greeting.txt" in changed
    # 9.0.0 writes no other document (ADR-091). On the path the acceptance
    # criteria start wrote are the issue's one document, and they land with it.
    docs = [p for p in changed if p.startswith("docs/compass/")]
    assert len(docs) == 1 and docs[0].endswith("-greet-ship/acceptance-criteria.md"), \
        changed

    check_evidence = next(e for e in manifest["evidence"]
                          if e["type"] == "command-output")
    assert (repo / ".compass" / "work" / slug
           / check_evidence["path"]).is_file()

    # The path writes no devlog (ADR-092 decision 12). The commit holds the
    # message, and every gate passed on evidence the manifest registers.
    assert not (repo / ".compass" / "work" / slug / "devlog.md").exists()
    assert "Say hello properly" in _git(repo, "log", "-1", "--format=%B")
    registered = {e["id"] for e in manifest["evidence"]}
    for gid in ("verify.correctness", "verify.governance", "verify.traceability"):
        gate = next(g for g in manifest["gates"] if g["id"] == gid)
        assert set(gate["evidence"]) <= registered, gate


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

    finish = _land(repo, slug, "-m", "Fix add", command=cmd)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert list(repo.rglob("*.pyc")), "the test run should leave a cache"

    changed = {cf["path"] for cf in _manifest(repo, slug)["changed_files"]}
    assert not [p for p in changed if "__pycache__" in p or p.endswith(".pyc")]
    committed = _git(repo, "show", "--name-only", "--format=", "HEAD")
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

    finish = _land(repo, slug, "-m", "Fix add", command=cmd)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    check = _run(repo, "check", "--issue", slug)
    assert check.returncode == 0, check.stdout + check.stderr


def _files_in_head(root):
    # HEAD is the land commit: no living spec commit follows it (ADR-091).
    return set(_git(root, "show", "--name-only", "--format=", "HEAD").split())


def _left_out(finish):
    """The path(s) of the `left out :` line `finish` prints, or an empty string."""
    line = next((ln for ln in finish.stdout.splitlines()
                 if ln.strip().startswith("left out")), "")
    # The line also gives the remedy in brackets: `left out : <path> (changed before start; ...)`.
    return line.split(":", 1)[1].split(" (", 1)[0].strip() if ":" in line else ""


def test_fuu1_an_untracked_file_from_before_start_is_left_out_and_never_committed(repo):
    """A local file nobody traced must never be committed. This is how
    private notes reached a public branch. `finish` names it as left out."""
    (repo / "notes").mkdir()
    (repo / "notes" / "private.md").write_text("not for publishing\n")
    _ready_to_finish(repo, "greet-private")

    finish = _land(repo, "greet-private")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert _left_out(finish) == "notes/private.md", finish.stdout
    assert "notes/private.md" not in _files_in_head(repo)
    assert "notes/private.md" not in {
        cf["path"] for cf in _manifest(repo, "greet-private")["changed_files"]}
    assert (repo / "notes" / "private.md").read_text() == "not for publishing\n"
    assert "?? notes/" in _git(repo, "status", "--porcelain", "--untracked-files=normal")


def test_fuu2_a_tracked_file_modified_before_start_is_left_out_and_never_committed(repo):
    (repo / "README.md").write_text("an edit that is not this fix\n")
    _ready_to_finish(repo, "greet-dirty")

    finish = _land(repo, "greet-dirty")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert _left_out(finish) == "README.md", finish.stdout
    assert "README.md" not in _files_in_head(repo)
    assert (repo / "README.md").read_text() == "an edit that is not this fix\n"
    assert "M README.md" in _git(repo, "status", "--porcelain")


def test_fuu3_a_file_from_before_start_is_committed_once_traced(repo):
    (repo / "notes").mkdir()
    (repo / "notes" / "fix.md").write_text("part of this fix\n")
    _ready_to_finish(repo, "greet-traced")
    traced = _run(repo, "changed-file", "add", "notes/fix.md", "--issue",
                  "greet-traced", "--scenario", "TRC-001")
    assert traced.returncode == 0, traced.stderr

    finish = _land(repo, "greet-traced")
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

    finish = _land(repo, slug)
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


def test_fuu1_a_new_file_in_a_directory_untracked_before_start_is_left_out(repo):
    """A directory nobody tracks, such as a local `.claude/`, stays local:
    a file written into it after `start` is left out like one from before."""
    (repo / "local").mkdir()
    (repo / "local" / "old.md").write_text("private\n")
    _ready_to_finish(repo, "greet-local-dir")
    (repo / "local" / "old.md").unlink()
    (repo / "local" / "new.md").write_text("also private\n")

    finish = _land(repo, "greet-local-dir")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert _left_out(finish) == "local/new.md", finish.stdout
    assert "local/new.md" not in _files_in_head(repo)


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

    finish = _land(repo, "greet-ignored-dir")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert _left_out(finish) == "local/plan.md", finish.stdout
    assert "local/plan.md" not in _files_in_head(repo)


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

    finish = _land(repo, "greet-mixed-dir")
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

    finish = _land(repo, slug)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert "tests/test_greeting.py" in _files_in_head(repo)


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


def test_fuu6_finish_counts_every_file_it_commits(repo):
    _ready_to_finish(repo, "greet-list")
    finish = _land(repo, "greet-list")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    line = next(ln for ln in finish.stdout.splitlines() if ln.strip().startswith("committed:"))
    held = _files_in_head(repo)
    records = (".compass/", "docs/compass/")
    of_record = [p for p in held if p.startswith(records)]
    assert f"committed: {len(held)} file(s): {len(held) - len(of_record)} of the change, " \
        f"{len(of_record)} of the record" in line, (line, held)


def test_fse1_a_new_file_with_an_unusual_name_lands(repo):
    slug = "greet-odd-names"
    _ready_to_finish(repo, slug)
    for name in ("notes with space.txt", "quote'd.txt", "caf\u00e9.txt"):
        (repo / "data" / name).write_text("made by the fix\n")

    finish = _land(repo, slug)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    files = set(_git(repo, "show", "--name-only", "-z", "--format=",
                     "HEAD").split("\0"))
    for name in ("notes with space.txt", "quote'd.txt", "caf\u00e9.txt"):
        assert f"data/{name}" in files, files


def test_fse2_no_commit_reveals_a_local_path(repo):
    (repo / "notes").mkdir()
    (repo / "notes" / "acquisition-plan.md").write_text("private\n")
    _ready_to_finish(repo, "greet-no-trace")
    (repo / "notes" / "acquisition-plan.md").unlink()   # moved out
    finish = _land(repo, "greet-no-trace")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    import hashlib
    digest = hashlib.sha256(b"notes/acquisition-plan.md").hexdigest()
    committed = _git(repo, "log", "-p", "--all", "--format=")
    assert "acquisition" not in committed
    assert digest not in committed
    assert not (repo / ".compass" / "work" / "greet-no-trace"
                / "start-state.json").exists()


def test_fse3_every_detail_line_has_the_same_spacing(repo):
    _ready_to_finish(repo, "greet-spacing")
    (repo / "data" / "extra.txt").write_text("more\n")
    finish = _land(repo, "greet-spacing")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    lines = [l for l in finish.stdout.splitlines() if l.startswith("  ") and ":" in l]
    assert len(lines) >= 3
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


def test_sjs5_a_fix_the_agent_committed_by_hand_lands_once_traced(repo):
    """When the agent committed the fix itself, `finish` says so and takes the
    file once the agent traces it: a committed file is traced by the agent,
    never by finish on its own, because a commit after `start` may be another
    person's (`gdh2`)."""
    slug = "greet-precommitted"
    (repo / ".gitignore").write_text(".compass/\ndocs/\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "ignore records")
    _ready_to_finish(repo, slug)
    _git(repo, "add", "data/greeting.txt")
    _git(repo, "commit", "-q", "-m", "the fix, committed by hand")
    refused = _finish(repo, slug)
    assert refused.returncode != 0, refused.stdout
    assert "committed by hand" in refused.stderr and "data/greeting.txt" in refused.stderr
    traced = _run(repo, "changed-file", "add", "data/greeting.txt",
                  "--issue", slug, "--scenario", "TRC-001")
    assert traced.returncode == 0, traced.stderr
    finish = _land(repo, slug)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    traced = {cf["path"] for cf in _manifest(repo, slug)["changed_files"]}
    assert "data/greeting.txt" in traced, traced


def test_sjs5_a_name_with_a_control_character_is_shown_quoted(repo):
    (repo / "data").mkdir()
    (repo / "data" / "new\nline.txt").write_text("odd\n")       # before start: left out
    _ready_to_finish(repo, "greet-newline")
    finish = _land(repo, "greet-newline")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert "'data/new\\nline.txt'" in finish.stdout, finish.stdout


def test_sjs6_the_start_record_stays_after_a_land_for_the_next_finish(repo):
    """A feedback round runs `finish` again. The start record, in the git
    directory and never committed, still names the local files to leave out."""
    (repo / "notes").mkdir()
    (repo / "notes" / "private.md").write_text("not for publishing\n")
    _ready_to_finish(repo, "greet-cleanup")
    record = repo / _git(repo, "rev-parse", "--git-path",
                         "compass/start-state/greet-cleanup.json")
    assert record.exists()
    assert _land(repo, "greet-cleanup").returncode == 0
    assert record.exists()
    again = _finish(repo, "greet-cleanup")
    assert again.returncode == 0, again.stdout + again.stderr
    assert _left_out(again) == "notes/private.md", again.stdout
    assert "notes/private.md" not in _files_in_head(repo)


def test_scf4_a_green_from_before_argv_is_reused(repo):
    """A quick fix finished with --no-commit before greens carried `argv`
    must still finish afterwards: rerunning the same command on the same
    tree is flagged as a rerun, so the old green has to be reused."""
    import json
    slug = "greet-old-green"
    _ready_to_finish(repo, slug)
    assert _finish(repo, slug, "--no-commit").returncode == 0
    record = (repo / ".compass" / "work" / slug / "evidence" / "green-TRC-001.json")
    data = json.loads(record.read_text())
    data.pop("argv", None)
    # Stamped as the writer before `argv` stamped it, so the record is a
    # genuine older record, not an edited one.
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg.red_first import content_digest
    data["content_digest"] = content_digest(data)
    record.write_text(json.dumps(data))
    manifest = _manifest(repo, slug)
    for entry in manifest["evidence"]:
        if entry.get("path") == "evidence/green-TRC-001.json":
            entry["content_digest"] = data["content_digest"]
    _save_manifest(repo, slug, manifest)

    finish = _land(repo, slug)
    assert finish.returncode == 0, finish.stdout + finish.stderr


def test_scf1_finish_reports_a_land_that_ship_commit_refused(repo):
    """A git hook that stages an untested copy during the commit makes
    ship-commit leave the issue unlanded. finish must say so, not
    "shipped", and must keep the start record for the next try."""
    slug = "greet-hooked"
    _ready_to_finish(repo, slug)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nprintf 'untested\\n' > data/greeting.txt\n"
                    "git add data/greeting.txt\nexit 0\n")
    hook.chmod(0o755)
    record = repo / _git(repo, "rev-parse", "--git-path",
                         f"compass/start-state/{slug}.json")

    finish = _land(repo, slug)
    heard = finish.stdout + finish.stderr
    assert finish.returncode != 0, heard
    assert "shipped" not in heard, heard
    assert "data/greeting.txt" in heard, heard
    assert record.exists()


def test_gdh1_finish_refuses_an_edited_green(repo):
    """An edited green record fails compass check's identity check, so
    finish refuses rather than land on it."""
    import json
    slug = "greet-edited-green"
    _ready_to_finish(repo, slug)
    assert _finish(repo, slug, "--no-commit").returncode == 0
    record = (repo / ".compass" / "work" / slug / "evidence" / "green-TRC-001.json")
    data = json.loads(record.read_text())
    data["log_excerpt"] = "edited after it was written"
    record.write_text(json.dumps(data))
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo, slug)
    assert finish.returncode != 0, finish.stdout
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_gdh2_finish_does_not_trace_someone_elses_commit(repo):
    """A commit another person makes after `start` is not the change's:
    finish must not trace it, even though it is already committed."""
    slug = "greet-others"
    _ready_to_finish(repo, slug)
    (repo / "other.py").write_text("theirs = 1\n")
    _git(repo, "add", "other.py")
    _git(repo, "commit", "-q", "-m", "someone else's change")

    finish = _finish(repo, slug)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    traced = {cf["path"] for cf in _manifest(repo, slug)["changed_files"]}
    assert "other.py" not in traced, traced


# --- QFO-5 ---------------------------------------------------------------

def test_qfo5_finish_refuses_when_check_fails(repo):
    slug = "greet-ghost"
    _ready_to_finish(repo, slug)
    manifest = _manifest(repo, slug)
    # A scenario with no intent: the green passes, and `compass check` fails.
    # (`finish` writes the traces itself, so a wrong trace cannot be planted.)
    manifest["scenarios"][0]["intent"] = ""
    _save_manifest(repo, slug, manifest)
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo, slug)
    assert finish.returncode == 1, finish.stdout + finish.stderr
    heard = finish.stdout + finish.stderr
    assert "`compass check` fails" in heard, heard
    assert "Traceback" not in heard
    assert set(_gate_statuses(repo, slug).values()) == {"pending"}
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_qfo5_finish_refuses_when_another_gate_is_pending(repo):
    """A gate the project's settings add is pending: `finish` passes the three
    it owns, says what the project's settings still owe, and commits nothing."""
    slug = "greet-extra-gate"
    _ready_to_finish(repo, slug)
    manifest = _manifest(repo, slug)
    manifest["gates"].append(
        {"id": "verify.clarity", "status": "pending", "evidence": []})
    _save_manifest(repo, slug, manifest)
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo, slug)
    assert finish.returncode == 1, finish.stdout + finish.stderr
    heard = finish.stdout + finish.stderr
    assert "verify.clarity" in heard
    assert "owes 1 item(s) that the project's settings add" in heard, heard
    assert "next: compass gate pass verify.clarity --evidence <EV-id>" in heard, heard
    assert _gate_statuses(repo, slug)["verify.clarity"] == "pending"
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_qfo5_finish_proves_the_red_itself_when_none_is_on_record(repo):
    """No `tdd-red` was run: `finish` runs the tests on a copy of the base
    commit and they fail there, which is the red (ADR-099 decision 2)."""
    import json
    slug = "greet-no-red"
    _base_greeting(repo)
    start = _start(repo, slug)
    assert start.returncode == 0, start.stderr
    _write_greeting(repo, "Hello, %s!")

    finish = _finish(repo, slug)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert "the tests fail on the base commit" in finish.stdout, finish.stdout
    red = json.loads((repo / ".compass" / "work" / slug / "evidence"
                      / "red-TRC-001.json").read_text())
    assert red["proved_on"] == "base-copy" and red["passed"] is False


def test_qfo5_finish_refuses_when_the_tests_pass_on_the_base_commit(repo):
    """A change that leaves the tests passing without it proves nothing."""
    slug = "greet-passes-anyway"
    _write_greeting(repo, "Hello, %s!")
    _write_greeting_test(repo)
    _git(repo, "add", "data/greeting.txt", "tests/test_greeting.py")
    _git(repo, "commit", "-q", "-m", "greeting")
    assert _start(repo, slug).returncode == 0
    (repo / "data" / "extra.txt").write_text("a change the tests do not need\n")
    head_before = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo, slug)
    assert finish.returncode == 1, finish.stdout + finish.stderr
    assert "the tests pass on the base commit" in finish.stdout or \
        "the change holds no test file" in finish.stdout, finish.stdout
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
    # A refused call leaves its records saved. A second call must still run
    # the tests, and refuse again while the code is still broken.
    slug = "greet-twice"
    _ready_to_finish(repo, slug)
    _write_greeting(repo, "Still wrong, %s!")
    head_before = _git(repo, "rev-parse", "HEAD")

    first = _finish(repo, slug)
    assert first.returncode != 0
    second = _finish(repo, slug)
    assert second.returncode != 0
    assert "the tests fail on the working tree" in second.stdout

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
    assert "Nothing is committed" in finish.stdout

    assert set(_gate_statuses(repo, slug).values()) == {"pass"}
    assert _git(repo, "rev-parse", "HEAD") == head_before
    assert "data/greeting.txt" in _git(repo, "status", "--porcelain",
                                       "--untracked-files=all")


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

    second = _land(repo, slug)
    assert second.returncode == 0, second.stdout + second.stderr
    assert _git(repo, "rev-parse", "HEAD") != head_before

    assert set(_gate_statuses(repo, slug).values()) == {"pass"}
    check = _run(repo, "check", "--issue", slug)
    assert check.returncode == 0, check.stdout + check.stderr


def test_qfg1_finish_succeeds_after_a_failed_check_is_fixed(repo):
    # A first call records a green and then fails at `compass check` for a
    # reason outside the source tree - the scenario names no intent (a missing
    # request would not do: it is not a stop, #356). Fixing the record
    # and calling `finish` again, with the same command on the same tree, must
    # reuse the green rather than refuse it as a rerun; a third call with
    # nothing changed must succeed the same way.
    slug = "greet-badtrace"
    _ready_to_finish(repo, slug)
    manifest = _manifest(repo, slug)
    intent = manifest["scenarios"][0]["intent"]
    manifest["scenarios"][0]["intent"] = ""
    _save_manifest(repo, slug, manifest)
    head_before = _git(repo, "rev-parse", "HEAD")

    first = _finish(repo, slug, "--no-commit")
    assert first.returncode != 0
    assert "`compass check`" in (first.stdout + first.stderr)
    assert _git(repo, "rev-parse", "HEAD") == head_before

    manifest = _manifest(repo, slug)
    manifest["scenarios"][0]["intent"] = intent
    _save_manifest(repo, slug, manifest)

    second = _finish(repo, slug, "--no-commit")
    assert second.returncode == 0, second.stdout + second.stderr
    assert set(_gate_statuses(repo, slug).values()) == {"pass"}

    third = _finish(repo, slug, "--no-commit")
    assert third.returncode == 0, third.stdout + third.stderr
    assert set(_gate_statuses(repo, slug).values()) == {"pass"}
    assert e2e.person_approves(repo)
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

    argv = ["quick-fix", "finish", "--issue", slug, "-m", "Say hello properly",
            *RELEASE_NOTE, "--", "python3", "-m", "pytest", "-q",
            "test_greeting.py::test_greeting_says_hello"]
    first = _run_from(repo / "tests", *argv)
    assert first.returncode == 0, first.stdout + first.stderr
    assert e2e.person_approves(repo)
    finish = _run_from(repo / "tests", *argv)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert _git(repo, "rev-parse", "HEAD") != head_before

    manifest = _manifest(repo, slug)
    assert manifest["status"] == "done" and manifest["close_reason"] == "completed"
    assert set(_gate_statuses(repo, slug).values()) == {"pass"}
    changed = {cf["path"] for cf in manifest["changed_files"]}
    assert "data/greeting.txt" in changed
    check = _run(repo, "check", "--issue", slug)
    assert check.returncode == 0, check.stdout + check.stderr


def test_finish_traces_a_hand_edit_of_the_living_spec(repo):
    """quick-fix finish traces the living spec like any other file. Before
    9.0.0 ship-commit derived the living spec at landing, so finish left it out;
    nothing derives it now (ADR-091), so a change to it is the fix's own and
    lands with it (#358)."""
    docs = repo / "docs"
    docs.mkdir()
    (docs / "system-spec.md").write_text("# spec\n")
    _git(repo, "add", "docs")
    _git(repo, "commit", "-q", "-m", "spec")
    slug = "greet-spec"
    _ready_to_finish(repo, slug)
    (docs / "system-spec.md").write_text("# spec, edited by hand\n")

    finish = _land(repo, slug)
    assert finish.returncode == 0, finish.stdout + finish.stderr

    changed = {cf["path"] for cf in _manifest(repo, slug)["changed_files"]}
    assert "docs/system-spec.md" in changed, changed
    assert "docs/system-spec.md" in _git(repo, "show", "--name-only", "--format=", "HEAD")
    check = _run(repo, "check", "--issue", slug)
    assert check.returncode == 0, check.stdout
