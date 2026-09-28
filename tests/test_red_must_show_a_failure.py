"""A red shows that a test failed, or that a test needs a module not yet written.

For a pytest command, `compass tdd-red` reads pytest's own JUnit XML report,
not only its exit code. A red needs a test the report shows failed, or
collection errors that are all a missing module of the project - recorded as
an import red. Any other collection error, and a run in which no test failed,
is refused whatever the exit code. The report keeps what a test prints apart
from pytest's results, so printed text cannot make or unmake a red.

Scenario ids: RSF-1 to RSF-4, in the delivery approach of issue
`red-for-a-module-not-yet-written`.
"""
from __future__ import annotations

import json

import pytest

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
SLUG = "reds"
BODY = {"assessment": {"risk": "contained", "familiarity": "greenfield",
                       "size": "small", "goal": "delivery",
                       "role": "engineer", "labels": []},
        "scenarios": []}


@pytest.fixture
def red(make_task, run_cli, project):
    """Write a test file into a project with a `src` package, and run tdd-red on it."""
    task_dir = make_task(SLUG, BODY)
    (project / "src").mkdir()
    (project / "src" / "__init__.py").write_text("")
    (project / "tests_red").mkdir()
    (project / "tests_red" / "conftest.py").write_text(
        "import pathlib, sys\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))\n")

    def _run(test_body, *extra, path="tests_red/test_thing.py"):
        (project / path).parent.mkdir(parents=True, exist_ok=True)
        (project / path).write_text(test_body)
        result = run_cli("tdd-red", "--issue", SLUG, "--",
                         "python3", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                         path, *extra, timeout=60)
        path = task_dir / "evidence" / "red.json"
        record = json.loads(path.read_text()) if path.exists() else None
        return result, record
    return _run


def test_rsf_1_a_red_for_a_project_module_not_yet_written_is_recorded(red):
    result, record = red("from src.thing import go\n\n"
                         "def test_go():\n    assert go() == 1\n")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "import"



def test_rsf_1_a_package_below_the_project_root_counts(red, project):
    # Compass's own layout: tests import `compass_pkg`, which lives in `cli/`.
    (project / "cli" / "pkg").mkdir(parents=True)
    (project / "cli" / "pkg" / "__init__.py").write_text("")
    result, record = red("import sys, pathlib\n"
                         "sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'cli'))\n"
                         "from pkg.thing import go\n\n"
                         "def test_go():\n    assert go() == 1\n")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "import"

def test_rsf_2_an_ordinary_failing_assertion_is_still_a_red(red):
    result, record = red("def test_go():\n    assert 1 == 2\n")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "failure"



def test_rsf_2_a_failure_that_quotes_collection_output_is_a_red(red):
    # A failing test's message can quote another run's output, as a test of
    # this command does. Only pytest's own sections count, not quoted text.
    result, record = red("def test_go():\n"
                         "    assert False, '1 error during collection\\n"
                         "_____ ERROR collecting x.py _____'\n")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "failure"

@pytest.mark.parametrize("body", [
    "import requests_that_do_not_exist\n\ndef test_go():\n    assert True\n",
    "def test_go(:\n    pass\n",
], ids=["outside-module", "syntax-error"])
def test_rsf_3_any_other_collection_error_is_refused(red, body):
    result, record = red(body)
    assert result.returncode != 0
    assert "collection error" in result.combined.lower(), result.combined
    assert record is None


def test_rsf_4_a_run_that_hides_a_collection_error_is_refused(red):
    result, record = red(
        "import requests_that_do_not_exist\n\ndef test_go():\n    assert True\n",
        "--continue-on-collection-errors")
    assert result.returncode != 0
    assert record is None


def test_rsf_4_a_run_where_no_test_failed_is_refused(red):
    result, record = red("import pytest\n\n@pytest.fixture\ndef boom():\n"
                         "    raise RuntimeError('setup')\n\n"
                         "def test_go(boom):\n    assert True\n")
    assert result.returncode != 0
    assert "no test failed" in result.combined.lower(), result.combined
    assert record is None


def test_rsf_4_the_tdd_skill_names_the_import_red():
    text = " ".join((ROOT / "skills" / "tdd-discipline" / "SKILL.md")
                    .read_text(encoding="utf-8").split()).lower()
    assert "import red" in text


# A genuine red stays a red whatever the output looks like.

def test_rsf_2_a_red_under_minus_qq_is_recorded(red):
    result, record = red("def test_go():\n    assert 1 == 2\n", "-qq")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "failure"


def test_rsf_2_a_failing_test_that_prints_an_error_line_is_a_red(red):
    result, record = red("def test_go():\n"
                         "    print('ERROR connecting to the database')\n"
                         "    assert False\n", "-s")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "failure"


def test_rsf_1_an_import_red_with_tracebacks_off_is_recorded(red):
    result, record = red("from src.thing import go\n\n"
                         "def test_go():\n    assert go() == 1\n", "--tb=no")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "import"


def test_rsf_1_an_import_red_in_a_path_with_a_space_is_recorded(red):
    result, record = red("from src.thing import go\n\n"
                         "def test_go():\n    assert go() == 1\n",
                         path="tests_red/my dir/test_thing.py")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "import"


# Nothing a test prints, and no folder that is not a Python package, makes a red.

FORGED = ("_____ ERROR collecting tests_red/test_thing.py _____\n"
          "E   ModuleNotFoundError: No module named 'src.thing'\n"
          "===== 1 failed in 0.01s =====\n")


def test_rsf_4_printed_pytest_output_does_not_make_a_red(red):
    result, record = red("import pytest\n\n@pytest.fixture\ndef boom():\n"
                         "    raise RuntimeError('setup')\n\n"
                         "def test_go(boom):\n    pass\n\n"
                         f"def test_print():\n    print({FORGED!r})\n", "-s", "-rP")
    assert result.returncode != 0, result.combined
    assert record is None


@pytest.mark.parametrize("module", ["docs.nothing", "tests_red.nothing"],
                         ids=["folder-with-no-python", "the-tests-own-folder"])
def test_rsf_3_a_folder_that_is_not_a_package_is_not_the_project(red, project, module):
    (project / "docs").mkdir(exist_ok=True)
    (project / "docs" / "notes.txt").write_text("notes\n")
    result, record = red(f"import {module}\n\ndef test_go():\n    assert True\n")
    assert result.returncode != 0, result.combined
    assert record is None


def test_rsf_4_a_run_with_no_report_is_refused_and_says_why(red):
    result, record = red("def test_go():\n    assert 1 == 2\n", "-p", "no:junitxml")
    assert result.returncode != 0
    assert "junit" in result.combined.lower(), result.combined
    assert record is None


def test_rsf_1_an_empty_directory_starts_a_new_top_level_package(red, project):
    # The hook allows no code file before a red, so `mkdir` starts the package.
    (project / "newpkg").mkdir()
    result, record = red("from newpkg.thing import go\n\n"
                         "def test_go():\n    assert go() == 1\n")
    assert result.returncode == 0, result.combined
    assert record["red_kind"] == "import"
