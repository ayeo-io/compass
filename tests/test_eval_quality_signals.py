"""Static code-quality signals per condition in the eval comparison report.

`evals/quality.py` rebuilds a run's final code from the scenario seed and
the run's recorded diff, then measures the changed Python files outside
`tests/` with the standard library's `ast`: complexity added, duplicated
lines and lint findings. `evals/compare.py` shows them per cell and per
condition. No model and no third-party tool is used (issue #349; the
definitions are in the issue's technical design).

Scenario ids: QS-1 to QS-4 (issue `quality-static-signals`).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import pytest  # noqa: E402

import evals.compare as compare  # noqa: E402
import evals.quality as quality  # noqa: E402
from test_eval_compare import make_record  # noqa: E402

SCENARIOS = ROOT / "evals" / "scenarios"


@pytest.fixture(autouse=True)
def _fresh_cache():
    """`measure` caches one rebuild per record for the life of the process.
    Each test starts empty, so a test never reuses another's rebuild."""
    quality._CACHE.clear()
    yield
    quality._CACHE.clear()


GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


# --- QS-2: the measures ------------------------------------------------------

def test_qs_2_complexity_counts_functions_branches_and_operands():
    source = '''
def f(a, b, c):
    if a and b and c:
        return 1
    for x in range(3):
        while x:
            x -= 1
    try:
        pass
    except ValueError:
        pass
    with open("x") as fh:
        pass
    y = [i for i in range(3) if i]
    return 2 if a else 3

def g():
    def inner():
        pass
'''
    # f 1 + if 1 + and-operands 2 + for 1 + while 1 + except 1 + with 1
    # + comprehension if 1 + conditional 1 = 10; g 1; inner 1.
    assert quality.complexity(source) == 12


def test_qs_2_duplicated_lines_count_extra_windows_only():
    block = "a = 1\nb = 2\nc = 3\nd = 4\n"
    once = block
    twice = block + "# a comment\n\n" + block
    assert quality.duplicated_lines(once) == 0
    assert quality.duplicated_lines(twice) == 1


def test_qs_2_lint_findings():
    source = '''
from __future__ import annotations
import os
import sys
from json import *
__all__ = ["os"]

def f(x=[], y={}, z=list()):
    try:
        return sys.argv
    except:
        return None
'''
    # star import 1, three mutable defaults, bare except 1; os is in
    # __all__ and sys is read, so neither is unused.
    assert quality.lint_findings(source) == 5
    assert quality.lint_findings("import os\n") == 1


def test_qs_2_a_file_that_does_not_parse_has_no_measure():
    assert quality.complexity("def (:") is None


# --- QS-1: the rebuild ------------------------------------------------------

def _diff_for(tmp_path, scenario, edits, extra_files=None):
    """A diff of `edits` against `scenario`'s seed, as the harness records it."""
    work = tmp_path / "session"
    shutil.copytree(SCENARIOS / scenario / "seed", work)
    for rel, text in (extra_files or {}).items():
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_text(text)
    subprocess.run([*GIT, "init", "-q"], cwd=work, check=True)
    subprocess.run([*GIT, "add", "-A"], cwd=work, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "seed"], cwd=work, check=True)
    for rel, text in edits.items():
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_text(text)
    subprocess.run([*GIT, "add", "-A"], cwd=work, check=True)
    return subprocess.run([*GIT, "diff", "--cached", "--no-renames", "HEAD"],
                          cwd=work, capture_output=True, text=True,
                          check=True).stdout


_PAGING = (SCENARIOS / "cmp-edge-case" / "seed" / "src" / "paging.py").read_text()
_PAGE = _PAGING + '''

def page(items, number, size):
    if number < 1 or size < 1:
        raise ValueError("bad")
    start = (number - 1) * size
    return items[start:start + size]
'''


def test_qs_1_the_rebuild_measures_changed_python_outside_tests(tmp_path):
    diff = _diff_for(tmp_path, "cmp-edge-case",
                     {"src/paging.py": _PAGE,
                      "tests/test_paging.py": "def test_x():\n    if 1:\n        pass\n"})
    record = make_record(scenario="cmp-edge-case", condition="bare", diff=diff)
    m = quality.measure(record, SCENARIOS)
    # page: 1 function + if 1 + or-operands 1 = 3; the test file is ignored.
    assert m["complexity_added"] == 3, m
    assert m["files"] == ["src/paging.py"], m


def test_qs_1_an_install_owned_file_does_not_stop_the_rebuild(tmp_path):
    diff = _diff_for(tmp_path, "cmp-edge-case",
                     {"src/paging.py": _PAGE, ".compass/config.yml": "mode: advisory\n"},
                     extra_files={".compass/config.yml": "mode: enforced\n"})
    record = make_record(scenario="cmp-edge-case", condition="compass", diff=diff)
    m = quality.measure(record, SCENARIOS)
    assert m is not None and m["complexity_added"] == 3, m


def test_qs_1_a_diff_that_does_not_apply_gives_no_measure(tmp_path):
    diff = _diff_for(tmp_path, "cmp-edge-case", {"src/paging.py": _PAGE})
    broken = diff.replace("def page_count", "def page_total")
    record = make_record(scenario="cmp-edge-case", condition="bare", diff=broken)
    m = quality.measure(record, SCENARIOS)
    assert m is None or m.get("note"), m
    assert quality.complexity_added_of(record, SCENARIOS) is None


def test_qs_1_a_run_that_changes_no_python_is_not_recorded(tmp_path):
    diff = _diff_for(tmp_path, "cmp-spike", {"FINDINGS.md": "Yes.\n"})
    record = make_record(scenario="cmp-spike", condition="bare", diff=diff)
    assert quality.complexity_added_of(record, SCENARIOS) is None


# --- QS-3: the report --------------------------------------------------------

def test_qs_3_the_report_shows_the_three_measures(tmp_path):
    diff = _diff_for(tmp_path, "cmp-edge-case", {"src/paging.py": _PAGE})
    a = make_record(scenario="cmp-edge-case", condition="bare", diff=diff)
    b = make_record(scenario="cmp-edge-case", condition="compass", run=1)
    report = compare.build_report([a, b], scenarios_dir=SCENARIOS)
    for label in ("Complexity added", "Duplicated lines", "Lint findings"):
        assert label in report, label
    summary = report.split("## Summary", 1)[1]
    row = next(l for l in summary.splitlines() if l.startswith("| Complexity added "))
    cells = [c.strip() for c in row.split("|")[2:-1]]
    assert cells == ["3 (total)", "not recorded"], cells


# --- QS-4: the rebuild is robust ----------------------------------------------

def _new_file_diff(tmp_path, files):
    return _diff_for(tmp_path, "cmp-edge-case", files)


def test_qs_4_paths_with_spaces_and_other_characters_are_measured(tmp_path):
    diff = _new_file_diff(tmp_path, {
        "src/a.py": "def a():\n    if 1:\n        pass\n",
        "src/b c.py": "def b():\n    if 1:\n        pass\n    if 2:\n        pass\n",
        "src/café.py": "def c():\n    pass\n"})
    record = make_record(scenario="cmp-edge-case", condition="bare", diff=diff)
    m = quality.measure(record, SCENARIOS)
    assert m["complexity_added"] == 2 + 3 + 1, m
    assert sorted(m["files"]) == ["src/a.py", "src/b c.py", "src/café.py"], m


def test_qs_4_the_git_environment_cannot_redirect_the_rebuild(tmp_path, monkeypatch):
    other = tmp_path / "other"
    other.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=other, check=True)
    diff = _new_file_diff(tmp_path, {"src/paging.py": _PAGE})
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(other / ".git" / "index"))
    record = make_record(scenario="cmp-edge-case", condition="bare", diff=diff)
    m = quality.measure(record, SCENARIOS)
    assert m and m.get("complexity_added") == 3, m
    log = subprocess.run([*GIT, "log", "--oneline"], cwd=other,
                         capture_output=True, text=True,
                         env={k: v for k, v in os.environ.items()
                              if not k.startswith("GIT_")})
    assert log.stdout == "", log.stdout


def test_qs_4_a_deleted_file_is_skipped(tmp_path):
    work = tmp_path / "session"
    shutil.copytree(SCENARIOS / "cmp-edge-case" / "seed", work)
    subprocess.run([*GIT, "init", "-q"], cwd=work, check=True)
    subprocess.run([*GIT, "add", "-A"], cwd=work, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "seed"], cwd=work, check=True)
    (work / "src" / "paging.py").unlink()
    subprocess.run([*GIT, "add", "-A"], cwd=work, check=True)
    deleted = subprocess.run([*GIT, "diff", "--cached", "HEAD"], cwd=work,
                             capture_output=True, text=True, check=True).stdout
    assert "deleted file mode" in deleted
    record = make_record(scenario="cmp-edge-case", condition="bare", diff=deleted)
    m = quality.measure(record, SCENARIOS)
    assert m is not None and "note" in m and "files" not in m, m


def test_qs_4_duplicated_lines_are_floored_per_file(tmp_path):
    """One file loses its duplication and another gains one window: the
    first counts 0, not -1, so the total is 1."""
    block = "a = 1\nb = 2\nc = 3\nd = 4\n"
    scenarios = tmp_path / "scenarios"
    seed = scenarios / "dup" / "seed" / "src"
    seed.mkdir(parents=True)
    (seed / "old.py").write_text(block + block)
    work = tmp_path / "session"
    shutil.copytree(scenarios / "dup" / "seed", work)
    subprocess.run([*GIT, "init", "-q"], cwd=work, check=True)
    subprocess.run([*GIT, "add", "-A"], cwd=work, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "seed"], cwd=work, check=True)
    (work / "src" / "old.py").write_text(block)
    (work / "src" / "new.py").write_text(block + block)
    subprocess.run([*GIT, "add", "-A"], cwd=work, check=True)
    diff = subprocess.run([*GIT, "diff", "--cached", "HEAD"], cwd=work,
                          capture_output=True, text=True, check=True).stdout
    record = make_record(scenario="dup", condition="bare", diff=diff)
    assert quality.measure(record, scenarios)["duplicated_lines"] == 1


def test_qs_4_an_unparsable_file_is_named_and_skipped(tmp_path):
    diff = _new_file_diff(tmp_path, {"src/paging.py": _PAGE, "src/bad.py": "def (:\n"})
    record = make_record(scenario="cmp-edge-case", condition="bare", diff=diff)
    m = quality.measure(record, SCENARIOS)
    assert m["complexity_added"] == 3 and m["skipped"] == ["src/bad.py"], m


def test_qs_4_a_nested_tests_directory_is_excluded(tmp_path):
    diff = _new_file_diff(tmp_path, {"src/paging.py": _PAGE,
                                     "src/tests/test_more.py": "def test_y():\n    if 1:\n        pass\n"})
    record = make_record(scenario="cmp-edge-case", condition="bare", diff=diff)
    m = quality.measure(record, SCENARIOS)
    assert m["files"] == ["src/paging.py"], m
