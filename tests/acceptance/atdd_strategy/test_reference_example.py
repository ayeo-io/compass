"""The Python reference example of four-layer acceptance tests.

ayeo-io/compass-delivery#320, "Add a Python reference example of four-layer
acceptance tests", in the project's private delivery record. The example is
`examples/atdd-adapters/python/`. Compass never imports its code: each test
copies the example into a temporary folder, changes the copy where the
scenario says, and runs the example's own pytest there.

| Scenario | What it checks |
|---|---|
| `TRC-J1` | the specifications pass through the API driver and the CLI driver, and name neither |
| `TRC-J2` | the layering test fails each planted breach, naming the file, the line and the rule |
| `TRC-J3` | the layering test passes the example as shipped within 5 seconds |
| `TRC-J4` | renaming the module behind the todo API changes no specification and no DSL file |
| `TRC-F1` | a driver whose module does not exist is a setup error in the JUnit report, not exit 4 |
| `TRC-F2` | a driver name the factory does not know is refused at start-up |
| `TRC-F3` | the suite passes on two workers and one scenario twice, against one store |
| `TRC-F4` | a CI job runs the example through both drivers and its layering test |

Spec: atdd-python-example/acceptance-criteria.md.
"""
from __future__ import annotations

import ast
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples" / "atdd-adapters" / "python"
SPECS = "tests/acceptance/test_todos.py"
DSL = "tests/acceptance/dsl.py"
LAYERING = "tests/acceptance/test_layering.py"
WORKFLOW = ROOT / ".github" / "workflows" / "compass.yml"
JOB = "atdd-adapter-python"

RULE_NO_CHECK = "the DSL makes no check"
RULE_ALIAS = "every identifier goes through an alias"
RULE_ONE_CALL = "one DSL call per Given, When or Then line"


def _copy(tmp_path: Path) -> Path:
    folder = tmp_path / "example"
    shutil.copytree(EXAMPLE, folder, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".pytest_cache"))
    return folder


def _pytest(folder: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run the example's own pytest in `folder`. Plugin autoload is off and
    xdist is loaded by name, as in the Compass CI shards, so a plugin on the
    machine cannot change the result. The variables of an outer pytest run
    (an xdist worker id, a chosen driver, a data folder) are left out."""
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("PYTEST_", "ACCEPTANCE_", "TODO_"))}
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    # The example makes a new store under the temporary folder for each run
    # that names none; keep those stores inside this test's own folder.
    scratch = folder.parent / "tmp"
    scratch.mkdir(exist_ok=True)
    environment["TMPDIR"] = str(scratch)
    environment.update(env or {})
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "xdist.plugin", *args],
        cwd=folder, env=environment, capture_output=True, text=True, timeout=300)


def _output(run: subprocess.CompletedProcess) -> str:
    return f"exit {run.returncode}\n--- stdout\n{run.stdout}\n--- stderr\n{run.stderr}"


def _scenarios(folder: Path = EXAMPLE) -> list:
    tree = ast.parse((folder / SPECS).read_text(encoding="utf-8"))
    return [node.name for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]


def _passed(run: subprocess.CompletedProcess) -> int:
    found = re.search(r"(\d+) passed", run.stdout)
    return int(found.group(1)) if found else 0


# --- one specification through each driver (`TRC-J1`) ---------------------------------

@pytest.mark.parametrize("driver, chosen_by", [("api", "option"), ("cli", "environment")])
def test_trc_j1_one_specification_runs_through_each_driver(tmp_path, driver, chosen_by):
    folder = _copy(tmp_path)
    if chosen_by == "option":
        run = _pytest(folder, "-n", "2", "--driver", driver, SPECS)
    else:
        run = _pytest(folder, "-n", "2", SPECS, env={"ACCEPTANCE_DRIVER": driver})
    assert run.returncode == 0, _output(run)
    assert f"acceptance driver: {driver}" in run.stdout, _output(run)
    scenarios = _scenarios(folder)
    assert len(scenarios) >= 5, scenarios
    assert _passed(run) == len(scenarios), _output(run)


def test_trc_j1_no_specification_or_dsl_method_names_the_driver():
    # Words that belong to one client or one protocol. A specification or a
    # DSL that uses one is tied to that driver.
    driver_words = re.compile(
        r"\b(api|cli|http|https|urllib|subprocess|endpoint|stdout|stderr|"
        r"status code|exit code|argv|drivers\.api|drivers\.cli)\b", re.I)
    found = []
    for rel in (SPECS, DSL):
        for number, line in enumerate((EXAMPLE / rel).read_text(encoding="utf-8").splitlines(), 1):
            for word in driver_words.findall(line):
                found.append(f"{rel}:{number}: {word}")
    assert not found, "\n".join(found)


# --- the layering test fails each planted breach (`TRC-J2`) ---------------------------

def _function_span(lines: list, name: str) -> tuple:
    start = next(i for i, line in enumerate(lines) if re.match(rf"\s*def {name}\(", line))
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = start + 1
    while end < len(lines) and (not lines[end].strip()
                                or len(lines[end]) - len(lines[end].lstrip()) > indent):
        end += 1
    return start, end


def _insert_after_def(folder: Path, rel: str, method: str, planted: str) -> int:
    """Put `planted` on the line after `def <method>(`; return its line number."""
    path = folder / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    start, _ = _function_span(lines, method)
    lines.insert(start + 1, planted)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return start + 2


def _replace_in_function(folder: Path, rel: str, function: str, old: str, new: str) -> int:
    """Replace the one line of `function` that holds `old`; return its line number."""
    path = folder / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = _function_span(lines, function)
    hits = [i for i in range(start, end) if old in lines[i]]
    assert len(hits) == 1, f"{rel}: {function} holds {old!r} {len(hits)} times"
    lines[hits[0]] = lines[hits[0]].replace(old, new)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return hits[0] + 1


def _add_after_in_function(folder: Path, rel: str, function: str, after: str, new: str) -> int:
    """Put `new` on the line after the one line of `function` that holds `after`."""
    path = folder / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = _function_span(lines, function)
    hits = [i for i in range(start, end) if after in lines[i]]
    assert len(hits) == 1, f"{rel}: {function} holds {after!r} {len(hits)} times"
    lines.insert(hits[0] + 1, new)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return hits[0] + 2


def _plant_assert(folder):
    return DSL, _insert_after_def(folder, DSL, "complete",
                                  '        assert name, "a todo needs a name"'), RULE_NO_CHECK


def _plant_raise(folder):
    return DSL, _insert_after_def(folder, DSL, "complete",
                                  '        if not name: raise ValueError("a todo needs a name")'
                                  ), RULE_NO_CHECK


def _plant_fail(folder):
    return DSL, _insert_after_def(folder, DSL, "complete",
                                  '        if not name: pytest.fail("a todo needs a name")'
                                  ), RULE_NO_CHECK


def _plant_email(folder):
    return SPECS, _replace_in_function(folder, SPECS, "test_a_new_todo_is_open",
                                       'dsl.todo.add("Buy milk")',
                                       'dsl.todo.add("ann@example.com")'), RULE_ALIAS


def _plant_two_calls(folder):
    return SPECS, _add_after_in_function(folder, SPECS, "test_a_new_todo_is_open",
                                         'dsl.todo.confirmOpen("Buy milk")',
                                         '    dsl.todo.confirmOpen("Buy milk")'), RULE_ONE_CALL


def _plant_helper_assert(folder):
    """An assert in a module-level helper that a DSL method calls."""
    path = folder / DSL
    text = path.read_text(encoding="utf-8")
    anchor = "\n\nclass _Scenario:"
    helper = '\n\ndef _need(name):\n    assert name, "a todo needs a name"\n'
    assert text.count(anchor) == 1
    text = text.replace(anchor, helper + anchor)
    path.write_text(text, encoding="utf-8")
    line = text.splitlines().index('    assert name, "a todo needs a name"') + 1
    return DSL, line, RULE_NO_CHECK


def _plant_async_assert(folder):
    """An assert in an async DSL method."""
    path = folder / DSL
    text = path.read_text(encoding="utf-8")
    anchor = "\n\nclass Dsl:"
    method = ('\n    async def completeLater(self, name):\n'
              '        assert name, "a todo needs a name"\n')
    assert text.count(anchor) == 1
    text = text.replace(anchor, method + anchor)
    path.write_text(text, encoding="utf-8")
    line = text.splitlines().index('        assert name, "a todo needs a name"') + 1
    return DSL, line, RULE_NO_CHECK


def _plant_two_calls_in_a_class(folder):
    """A specification written as a method of a Test class, with two calls on its Then line."""
    path = folder / SPECS
    text = path.read_text(encoding="utf-8").rstrip("\n")
    text += ('\n\n\nclass TestTodos:\n'
             '    def test_a_new_todo_is_open(self, dsl):\n'
             '        """\n'
             '        Given an account\n'
             '        When they add a todo "Buy milk"\n'
             '        Then "Buy milk" is open\n'
             '        """\n'
             '        dsl.user.hasAccount()\n'
             '        dsl.todo.add("Buy milk")\n'
             '        dsl.todo.confirmOpen("Buy milk")\n'
             '        dsl.todo.confirmOpen("Buy milk")\n')
    path.write_text(text, encoding="utf-8")
    return SPECS, len(text.splitlines()), RULE_ONE_CALL


BREACHES = {
    "an assert statement in a DSL method": (_plant_assert, "test_the_dsl_makes_no_check"),
    "a raised exception in a DSL method": (_plant_raise, "test_the_dsl_makes_no_check"),
    "a call to the runner's fail in a DSL method": (_plant_fail, "test_the_dsl_makes_no_check"),
    "an email address in a specification that the DSL does not alias":
        (_plant_email, "test_every_identifier_goes_through_an_alias"),
    "a Then line in a specification that makes two DSL calls":
        (_plant_two_calls, "test_one_dsl_call_per_line"),
    "an assert statement in a helper a DSL method calls":
        (_plant_helper_assert, "test_the_dsl_makes_no_check"),
    "an assert statement in an async DSL method": (_plant_async_assert, "test_the_dsl_makes_no_check"),
    "a Then line in a specification of a test class that makes two DSL calls":
        (_plant_two_calls_in_a_class, "test_one_dsl_call_per_line"),
}


@pytest.mark.parametrize("breach", list(BREACHES))
def test_trc_j2_the_layering_test_fails_each_planted_breach(tmp_path, breach):
    folder = _copy(tmp_path)
    plant, layering_test = BREACHES[breach]
    rel, line, rule = plant(folder)
    run = _pytest(folder, LAYERING)
    assert run.returncode == 1, _output(run)
    assert f"{rel}:{line}: {rule}" in run.stdout, _output(run)
    # Exactly the rule the breach breaks fails, and no other.
    assert f"FAILED {LAYERING}::{layering_test}" in run.stdout, _output(run)
    assert re.search(r"\b1 failed\b", run.stdout), _output(run)


# --- the layering test passes within 5 seconds (`TRC-J3`) -----------------------------

@pytest.mark.serial
def test_trc_j3_the_layering_test_passes_the_example_within_5_seconds(tmp_path):
    folder = _copy(tmp_path)
    started = time.monotonic()
    run = _pytest(folder, LAYERING)
    elapsed = time.monotonic() - started
    assert run.returncode == 0, _output(run)
    assert _passed(run) >= 3, _output(run)
    assert elapsed < 5, f"the layering test took {elapsed:.1f} seconds"


# --- a refactor leaves the specification alone (`TRC-J4`) -----------------------------

def _git(folder: Path, *args: str) -> str:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    run = subprocess.run(["git", "-c", "user.name=example", "-c", "user.email=example@invalid",
                          "-c", "commit.gpgsign=false", *args],
                         cwd=folder, env=environment, capture_output=True, text=True, check=True)
    return run.stdout


def test_trc_j4_a_refactor_leaves_the_specification_alone(tmp_path):
    folder = _copy(tmp_path)
    _git(folder, "init", "-q")
    _git(folder, "add", "-A")
    _git(folder, "commit", "-q", "-m", "the example as shipped")
    specs_before = (folder / SPECS).read_text(encoding="utf-8")

    # The refactor: the module behind the todo API gets a new name, and every
    # import of it in the system under test follows.
    _git(folder, "mv", "todo/service.py", "todo/todos.py")
    for path in (folder / "todo").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("todo.service", "todo.todos"), encoding="utf-8")
    left = [str(p) for p in folder.rglob("*.py") if "todo.service" in p.read_text(encoding="utf-8")]
    assert not left, f"files that still import the old module: {left}"
    _git(folder, "add", "-A")
    _git(folder, "commit", "-q", "-m", "rename the module behind the todo API")

    changed = _git(folder, "diff", "--name-only", "HEAD~1", "HEAD").split()
    assert changed and all(path.startswith("todo/") for path in changed), changed
    assert SPECS not in changed and DSL not in changed, changed
    assert (folder / SPECS).read_text(encoding="utf-8") == specs_before

    for driver in ("api", "cli"):
        run = _pytest(folder, "-n", "2", "--driver", driver, SPECS)
        assert run.returncode == 0, _output(run)
        assert _passed(run) == len(_scenarios(folder)), _output(run)


# --- a missing driver is a setup error (`TRC-F1`) -------------------------------------

def test_trc_f1_a_missing_driver_is_a_setup_error(tmp_path):
    folder = _copy(tmp_path)
    (folder / "tests" / "acceptance" / "drivers" / "cli.py").unlink()
    report = tmp_path / "report.xml"
    run = _pytest(folder, "--driver", "cli", f"--junitxml={report}", SPECS)
    assert run.returncode == 1, _output(run)
    cases = ET.parse(report).getroot().iter("testcase")
    errors = {case.get("name"): [e.get("message", "") for e in case.findall("error")]
              for case in cases}
    assert sorted(errors) == sorted(_scenarios(folder)), errors
    for name, messages in errors.items():
        assert len(messages) == 1, (name, messages)
        assert "setup" in messages[0], (name, messages)
        assert "tests.acceptance.drivers.cli" in messages[0], (name, messages)


# --- an unknown driver is refused at start-up (`TRC-F2`) ------------------------------

def test_trc_f2_an_unknown_driver_is_refused_at_start_up(tmp_path):
    folder = _copy(tmp_path)
    run = _pytest(folder, "--driver", "web", SPECS)
    assert run.returncode not in (0, 1), _output(run)
    assert "passed" not in run.stdout and "failed" not in run.stdout, _output(run)
    message = run.stdout + run.stderr
    assert "'web'" in message and "api" in message and "cli" in message, _output(run)


# --- parallel runs and repeat runs share one store (`TRC-F3`) -------------------------

def test_trc_f3_the_suite_passes_in_parallel_and_twice_against_one_store(tmp_path):
    folder = _copy(tmp_path)
    store = tmp_path / "store"
    shared = {"TODO_DATA_DIR": str(store)}
    for driver in ("api", "cli"):
        run = _pytest(folder, "-n", "2", "--driver", driver, SPECS, env=shared)
        assert run.returncode == 0, _output(run)
        assert _passed(run) == len(_scenarios(folder)), _output(run)
    one = f"{SPECS}::test_a_completed_todo_can_be_archived"
    for _ in range(2):
        run = _pytest(folder, "--driver", "api", one, env=shared)
        assert run.returncode == 0, _output(run)
        assert _passed(run) == 1, _output(run)
    # Nothing cleared the store between runs: every account the runs made
    # is still there, and none collided.
    emails = _accounts(store)
    assert len(emails) >= 2 * len(_scenarios(folder)) + 2, emails
    # One run id for each run, however many workers it had: four runs.
    run_ids = {re.fullmatch(r".+-(\w+)-gw\d+-\d+", email).group(1) for email in emails}
    assert len(run_ids) == 4, sorted(emails)


def _accounts(store: Path) -> list:
    with sqlite3.connect(store / "todo.sqlite3") as db:
        return [email for (email,) in db.execute("SELECT email FROM accounts")]


def test_trc_f3_the_workers_of_one_run_share_one_store(tmp_path):
    folder = _copy(tmp_path)
    run = _pytest(folder, "-n", "2", "--driver", "api", SPECS)
    assert run.returncode == 0, _output(run)
    store = re.search(r"^todo store: (.+)$", run.stdout, re.M)
    assert store, _output(run)
    workers = {re.fullmatch(r".+-gw(\d+)-\d+", email).group(1)
               for email in _accounts(Path(store.group(1)))}
    assert workers == {"0", "1"}, workers


# --- the CI job (`TRC-F4`) ------------------------------------------------------------

def test_trc_f4_a_ci_job_runs_the_example():
    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    assert JOB in jobs, sorted(jobs)
    steps = jobs[JOB]["steps"]
    runs = [step.get("run", "") for step in steps]
    folder = "examples/atdd-adapters/python"
    assert any(f"pip install -r {folder}/requirements.txt" in run for run in runs), runs
    in_folder = [step.get("run", "") for step in steps
                 if step.get("working-directory") == folder]
    for driver in ("api", "cli"):
        assert any(f"--driver {driver}" in run and "-n 2" in run for run in in_folder), in_folder
    assert any(LAYERING in run for run in in_folder), in_folder

    self_check = jobs["self-check"]
    assert JOB in self_check["needs"], self_check["needs"]
    aggregate = next(step["run"] for step in self_check["steps"]
                     if "ci-self-check.py aggregate" in step.get("run", ""))
    needed = re.search(r"--needed (\S+)", aggregate).group(1).split(",")
    assert JOB in needed, needed

    lines = [line.strip() for line in (EXAMPLE / "requirements.txt").read_text(
        encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    loose = [line for line in lines if not re.fullmatch(r"[A-Za-z0-9._-]+==[0-9][\w.]*", line)]
    assert not loose, f"requirements that do not pin one exact version: {loose}"
    names = {line.split("==")[0].lower() for line in lines}
    assert {"pytest", "pytest-xdist"} <= names, names
