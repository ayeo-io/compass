"""Read pytest's JUnit XML report to decide whether a run is a red.

pytest's exit code does not say a test failed. A collection error exits 2,
and `--continue-on-collection-errors` turns the same error into exit 1 while
no test runs. Its terminal output does not settle it either: `-qq` drops the
summary line, and anything a test prints lands in the same output as
pytest's own report. The JUnit XML report is pytest's built-in record of what
happened to each test, and it keeps printed output apart from the results.

One collection error is the most ordinary first red there is: a test that
imports a module of the project not written yet. That is an import red. A
missing module outside the project, or any other collection error, says the
test could not run, not that the behaviour is missing, so it is refused.

The outer loop, the acceptance suite, has one more first red. Its
driver-factory fixture imports the driver, which stage 1 has not written, so
pytest reports a setup error that names the missing module. For the outer loop
that is an import red too, under the same rule; for the inner loop it stays
refused. A `conftest.py` that imports the driver at module level makes pytest
exit 4 with no report, and the refusal names the fix (ADR-081).
"""
# DEPENDENCY: standard library only, plus compass_pkg itself.
from __future__ import annotations

import os
import re
import shlex
import tempfile
import xml.etree.ElementTree as ET

from compass_pkg.render import strip_ansi

DID_NOT_RUN = "DID NOT RUN"
NO_TEST_FAILED = "NO TEST FAILED"

_REPORT_FLAGS = ("--junitxml", "--junit-xml")
_MISSING = (re.compile(r"^E\s+ModuleNotFoundError: No module named '([^']+)'", re.M),
            re.compile(r"^E\s+ImportError: cannot import name '[^']+' from '([^']+)'",
                       re.M))
# Folders that hold other people's packages, so a name found there is not a
# module of this project.
_NOT_THE_PROJECT = frozenset({"node_modules", "site-packages", "venv", "env",
                              "__pycache__", "build", "dist"})
_TEST_FILE = re.compile(r"^(test_.*|.*_test|conftest)\.py$")


def with_report(command):
    """(extra environment, report path, is ours, mtime before the run).

    A command that names its own report keeps it, and Compass reads that
    one. Otherwise `--junitxml` goes in `PYTEST_ADDOPTS`, added to any value
    already set, pointing at a temporary file. pytest reads that variable
    wherever it starts - called directly, as `py.test`, or inside a
    `bash -c` string or a `make` target - so a wrapper still writes the
    report. A runner that is not pytest ignores it.
    """
    words = [str(c) for c in command]
    for i, word in enumerate(words):
        for flag in _REPORT_FLAGS:
            path = None
            if word.startswith(flag + "="):
                path = word.split("=", 1)[1]
            elif word == flag and i + 1 < len(words):
                path = words[i + 1]
            if path:
                return None, path, False, _mtime(path)
    fd, path = tempfile.mkstemp(prefix="compass-red-", suffix=".xml")
    os.close(fd)
    os.remove(path)   # pytest writes it; its absence afterwards means it did not
    addopts = os.environ.get("PYTEST_ADDOPTS", "").strip()
    flag = "--junitxml=" + shlex.quote(path)
    return ({"PYTEST_ADDOPTS": (addopts + " " + flag).strip()},
            path, True, None)


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def written(path, mtime_before):
    """Did this run write the report? A report the command names can be
    left over from an earlier run, so it must be new or changed."""
    after = _mtime(path)
    return after is not None and after != mtime_before


def _is_package(path):
    """A module file, a directory holding Python code other than tests, or
    an empty directory.

    An empty directory is a package being started. The pre-tool hook allows
    no code file before a red, so `mkdir` is how a new top-level package
    gets its first red.
    """
    if os.path.isfile(path + ".py"):
        return True
    if not os.path.isdir(path):
        return False
    names = [n for n in os.listdir(path) if n != "__pycache__"]
    return not names or any(n.endswith(".py") and not _TEST_FILE.match(n)
                            for n in names)


def in_project(module, project_root):
    """Is this module's top-level package a Python package of the project?

    A module not yet written cannot be told from a missing third-party
    package by its name, so the test is where its top-level package lives:
    a Python package or module up to three levels below the project root,
    outside folders of installed packages. A folder of tests, or of files
    that are not Python, does not count. Compass's own tests import `compass_pkg`
    from `cli/`, which is why the search goes below the root.
    """
    top = module.split(".")[0]
    if not top.isidentifier():
        return False
    root_depth = project_root.rstrip(os.sep).count(os.sep)
    for base, dirs, _files in os.walk(project_root):
        if _is_package(os.path.join(base, top)):
            return True
        if base.count(os.sep) - root_depth >= 2:
            dirs[:] = []
        else:
            dirs[:] = [d for d in dirs if d not in _NOT_THE_PROJECT
                       and not d.startswith(".")]
    return False


def _missing(text):
    found = [m.group(1) for p in _MISSING for m in p.finditer(strip_ansi(text))]
    return found[-1] if found else None


def _read(report_path):
    """(failed, collection errors, setup errors, ids of tests that failed or
    errored), or None. Each error is (where, missing module or None); a setup
    error is listed only when it names a missing module."""
    if not report_path:
        return None
    try:
        root = ET.parse(report_path).getroot()
    except (OSError, ET.ParseError):
        return None
    failed, collection, setup, broken = 0, [], [], set()
    for case in root.iter("testcase"):
        name = case.get("name") or "?"
        for outcome in case:
            message = outcome.get("message") or ""
            if outcome.tag in ("failure", "error"):
                broken.add(".".join(p for p in (case.get("classname"), name) if p))
            if outcome.tag == "failure":
                failed += 1
            elif outcome.tag == "error" and message == "collection failure":
                collection.append((name, _missing(outcome.text)))
            elif outcome.tag == "error" and message.startswith("failed on setup") \
                    and _missing(outcome.text):
                setup.append((name, _missing(outcome.text)))
    return failed, collection, setup, broken


def tests_ran(report_path):
    """How many tests the report says ran, or None when there is no report or it
    cannot be read. A skipped test did not run, so a run whose every test is
    skipped ran none. `compass layering record` reads it, so its own module
    holds no parser (ADR-086)."""
    if not report_path:
        return None
    try:
        root = ET.parse(report_path).getroot()
    except (OSError, ET.ParseError):
        return None
    return sum(1 for case in root.iter("testcase")
               if not any(child.tag == "skipped" for child in case))


def failed_tests(report_path):
    """The dotted ids, `classname.name`, of the tests the report shows failed or
    errored, a collection error included; None when there is no report."""
    read = _read(report_path)
    return None if read is None else read[3]


def covers(broken, test):
    """Did a test declared as `path::name` fail or error, by the ids
    `failed_tests` gives? A collection error of its file counts. The match is
    on a suffix, so a run whose root is below the project root still counts."""
    path, _, name = test.partition("::")
    module = path[:-3] if path.endswith(".py") else path
    module = module.replace("\\", "/").strip("/").replace("/", ".")
    wanted = ".".join(p for p in [module] + name.split("::") if p)

    def ends(case, tail):
        return case == tail or case.endswith("." + tail)
    for case in broken:
        case = re.sub(r"\[.*\]$", "", case)
        if ends(case, wanted) or ends(case, module) \
                or (not name and ("." + module + ".") in ("." + case)):
            return True
    return False


def missing_modules(report_path):
    """The missing modules a report's collection and setup errors name."""
    read = _read(report_path)
    if read is None:
        return []
    return sorted({m for _w, m in read[1] + read[2] if m})


def exit_4_reason(stderr, project_root):
    """Why an outer-loop exit 4 is not a red, quoting pytest's first error line.

    The text only words the refusal; exit 4 is never a red. When the first
    line says `conftest.py` failed to load and the error is a missing module of
    the project, the driver is imported at module level, and the reason names
    the fix.
    """
    lines = [x.strip() for x in strip_ansi(stderr or "").splitlines() if x.strip()]
    if not lines:
        return ("pytest exited 4, a setup error, not a red. pytest printed nothing "
                "on stderr, so there is no error line to quote")
    missing = _missing(stderr)
    if lines[0].startswith("ImportError while loading conftest") and missing \
            and in_project(missing, project_root):
        return ("conftest.py imports the module '%s', which is not written yet, at "
                "module level, so pytest stops before any test runs (exit 4) and "
                "writes no report. That is a setup error, not a red. To record the "
                "stage 1 red, import the driver inside the driver-factory fixture: "
                "pytest then reports a setup error that names the module" % missing)
    return ("pytest exited 4, a setup error, not a red. pytest's first error line: "
            "\"%s\"" % lines[0])


def judge(report_path, code, project_root, no_run_reasons, loop="inner"):
    """(red kind, None, None) for a red, or (None, heading, why) for a refusal.

    `no_run_reasons` maps the exit codes that mean no test ran to a reason.
    For the outer loop, a setup error for a missing module is read as a
    collection error is.
    """
    read = _read(report_path)
    if read is None:
        return None, DID_NOT_RUN, (
            "pytest exited %d and wrote no JUnit XML report. Compass adds "
            "--junitxml to see which tests failed, so a command that turns "
            "off pytest's junitxml plugin cannot record a red" % code)
    failed, collection, setup, _broken = read
    if loop == "outer" and setup:
        outside = sorted({m for _w, m in setup if not in_project(m, project_root)})
        if outside:
            named = ", ".join("'%s'" % m for m in outside)
            return None, NO_TEST_FAILED, (
                "a fixture could not set up: %s %s not a module of this project. "
                "A setup error for a missing package says it is not installed, "
                "not that the behavior is missing"
                % (named, "is" if len(outside) == 1 else "are"))
        if not collection:
            return "import", None, None
    if collection:
        outside = [(where, missing) for where, missing in collection
                   if not (missing and in_project(missing, project_root))]
        if outside:
            named = ", ".join("%s (%s)" % (where, "missing module '%s'" % missing
                                           if missing else "not a missing module")
                              for where, missing in outside)
            return None, NO_TEST_FAILED, (
                "a test file could not be collected: %s. An import red needs "
                "the missing module's top-level package to be a Python package "
                "of this project; for a new top-level package, create its "
                "directory first. Any other collection error is a test that "
                "could not run, not a test that failed" % named)
        return "import", None, None
    if code in no_run_reasons:
        return None, DID_NOT_RUN, no_run_reasons[code]
    if not failed:
        return None, NO_TEST_FAILED, (
            "pytest's report shows no failed test. An error in setup, or a "
            "flag that changes the exit code, is not a failing test")
    return "failure", None, None
