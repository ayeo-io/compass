"""The Stop hook stays fast on a project with many issues.

The hook runs at the end of every turn. It used to start Python twice for
each issue folder, so a project with 515 issues waited 513 seconds per turn
and read 264 warnings, most of them about issues closed long ago
(ayeo-io/compass-delivery-record#218). Two things keep it fast now:

  * a closed issue is not checked, so it gives no warning; and
  * the open issues are checked in one Python process, so the number of
    Python start-ups does not grow with the number of issues.

The start-ups are counted with a `python3` wrapper placed first on PATH,
which is a measure that does not depend on how fast the machine is. The
time limit is a second check, set well above the hook's real run time.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "stop.sh"
BASE_PATH = "/usr/bin:/bin:/usr/local/bin"

# A run over CLOSED + OPEN issues must end inside this many seconds. Before
# the fix one run over this fixture took over a minute.
TIME_LIMIT = 15
CLOSED = 200
OPEN = 20

# Closed in each of the ways a manifest can say so: the stored word since
# 6.0.0, with each close reason, and the two retired closing words.
CLOSED_STATUSES = (
    "status: done\nclose_reason: completed\n",
    "status: done\nclose_reason: not-planned\n",
    "status: landed\n",
    "status: abandoned\n",
)


def _issue(work, slug, status_lines):
    task = work / slug
    task.mkdir()
    (task / "manifest.yml").write_text(
        "schema_version: '3.0'\nissue: %s\n%sdelivery_approach: quick-fix\n"
        % (slug, status_lines), encoding="utf-8")
    (task / "delivery-approach.md").write_text(
        "# Delivery approach\n", encoding="utf-8")
    # A failing-test marker: the hook warns about it on any issue it checks.
    (task / ".red").write_text("", encoding="utf-8")


def _project(tmp_path, *, closed, open_):
    work = tmp_path / ".compass" / "work"
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text(
        "version: 1.0.0\n", encoding="utf-8")
    for n in range(closed):
        _issue(work, "closed-%03d" % n, CLOSED_STATUSES[n % len(CLOSED_STATUSES)])
    for n in range(open_):
        _issue(work, "open-%03d" % n, "")
    return tmp_path


def _counting_path(tmp_path):
    """A PATH whose python3 records each start in a file, then runs the
    real interpreter."""
    real = shutil.which("python3", path=BASE_PATH)
    assert real, "python3 is not on %s" % BASE_PATH
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    count_file = tmp_path / "python-starts"
    shim = shim_dir / "python3"
    shim.write_text(
        '#!/bin/sh\necho start >> "%s"\nexec "%s" "$@"\n' % (count_file, real),
        encoding="utf-8")
    shim.chmod(0o755)
    return "%s:%s" % (shim_dir, BASE_PATH), count_file


def _run(project, path=BASE_PATH):
    started = time.monotonic()
    try:
        result = subprocess.run(
            ["bash", str(HOOK)], input="{}", cwd=str(project),
            capture_output=True, text=True, timeout=TIME_LIMIT * 4,
            env={"PATH": path, "HOME": str(project),
                 "CLAUDE_PROJECT_DIR": str(project)},
        )
    except subprocess.TimeoutExpired:
        raise AssertionError(
            "the Stop hook did not finish in %d seconds" % (TIME_LIMIT * 4))
    return result, time.monotonic() - started


def _starts(tmp_path, *, closed, open_):
    project = _project(tmp_path / "project", closed=closed, open_=open_)
    path, count_file = _counting_path(tmp_path)
    result, _ = _run(project, path)
    assert result.returncode == 0, result.stderr
    return len(count_file.read_text(encoding="utf-8").splitlines())


def test_python_starts_do_not_grow_with_the_issue_count(tmp_path):
    few = _starts(tmp_path / "few", closed=0, open_=1)
    many = _starts(tmp_path / "many", closed=40, open_=20)
    assert many == few, (
        "the Stop hook started Python %d times for 1 issue and %d times for "
        "60 issues - it still starts Python for each issue" % (few, many))


def test_many_issues_finish_inside_the_time_limit(tmp_path):
    project = _project(tmp_path, closed=CLOSED, open_=OPEN)
    result, elapsed = _run(project)
    assert result.returncode == 0, result.stderr
    assert elapsed < TIME_LIMIT, (
        "the Stop hook took %.1f seconds over %d issues; the limit is %d"
        % (elapsed, CLOSED + OPEN, TIME_LIMIT))


def test_closed_issues_give_no_warning(tmp_path):
    project = _project(tmp_path, closed=len(CLOSED_STATUSES), open_=2)
    result, _ = _run(project)
    out = result.stderr
    assert "[closed-" not in out, (
        "the Stop hook warned about a closed issue:\n%s" % out)
    for slug in ("open-000", "open-001"):
        assert "[%s] .red marker" % slug in out, (
            "the Stop hook did not warn about the open issue %s:\n%s"
            % (slug, out))
