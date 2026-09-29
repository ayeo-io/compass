"""`compass quick-fix start` and `compass quick-fix finish`.

A B6 comparison session spent 19 to 22 model calls on a quick fix, most of
them mechanical steps an agent drove one at a time - init, write the
manifest from a template it read in full, evaluate, write the approach
record, register it, trace files, check, record the check, pass three
gates, devlog, commit. These two verbs do those same steps, through the
same code, in two calls.

Scenario ids: QFO-1 to QFO-5, in the acceptance criteria of the issue
quick-fix-overhead/acceptance-criteria.md.
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


def _ready_to_finish(root, slug, scenario_id="TRC-001"):
    """A started quick fix with a red on record and the fix written, not yet
    finished - `finish` records the green itself. The state every QFO-5
    refusal test starts from before it breaks exactly one condition."""
    _write_greeting(root, "Hi, %s!")
    _write_greeting_test(root)
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
    _write_greeting(repo, "Hi, %s!")
    _write_greeting_test(repo)
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
