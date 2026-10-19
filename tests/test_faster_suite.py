"""The suite and the release run on parallel workers, and `make ci` checks
only recent issues by default: the faster-suite-and-release issue,
scenarios FS-A, FS-B and FS-D to FS-G. A scenario is in
`docs/system-spec.md` while current and in `docs/system-spec-archive.md`
once a later one supersedes it.

`make -n` prints the commands a target would run without running them, so
these tests read the flags each target passes. A stub `xdist` package on
PYTHONPATH stands in for an installed `pytest-xdist`.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
PARALLEL = "-p xdist.plugin -n auto"


def _make_n(target: str, tmp_path: Path, *, xdist: bool, **env) -> str:
    """The commands `make <target>` would run, with or without `xdist`."""
    stub = tmp_path / "stub"
    stub.mkdir(exist_ok=True)
    # The stub sits first on PYTHONPATH, so it wins over an installed copy:
    # an empty package stands in for pytest-xdist, and one that raises hides
    # a real install, as CI has.
    (stub / "xdist").mkdir(exist_ok=True)
    (stub / "xdist" / "__init__.py").write_text(
        "" if xdist else "raise ImportError('hidden by the test')\n")
    run_env = {k: v for k, v in os.environ.items()
               if k not in ("PYTHONPATH", "COMPASS_FULL_ARCHIVE")}
    run_env["PYTHONPATH"] = str(stub)
    run_env.update(env)
    r = subprocess.run(["make", "-n", target], cwd=ROOT, capture_output=True,
                       text=True, env=run_env)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_make_test_runs_on_parallel_workers_when_xdist_is_installed(tmp_path):
    """With pytest-xdist installed, make test runs the suite on parallel
    workers (FS-A)."""
    assert PARALLEL in _make_n("test", tmp_path, xdist=True)


def test_make_test_runs_in_series_without_xdist(tmp_path):
    """Without pytest-xdist, make test runs the suite in series, as before
    (FS-A)."""
    out = _make_n("test", tmp_path, xdist=False)
    assert "pytest tests/" in out and "xdist" not in out, out


def _latest_tag() -> str:
    r = subprocess.run(["git", "describe", "--tags", "--abbrev=0"], cwd=ROOT,
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def test_make_ci_checks_issues_since_the_latest_tag(tmp_path):
    """make ci passes the latest release tag to compass ci (FS-D)."""
    tag = _latest_tag()
    if not tag:
        pytest.skip("this checkout has no tag, so make ci checks every issue")
    out = _make_n("ci", tmp_path, xdist=False)
    assert f"compass ci --since {tag}" in out, out


def test_the_full_archive_opt_in_checks_every_issue(tmp_path):
    """COMPASS_FULL_ARCHIVE=1 makes make ci check every issue (FS-D)."""
    out = _make_n("ci", tmp_path, xdist=False, COMPASS_FULL_ARCHIVE="1")
    assert "compass ci" in out and "--since" not in out, out


def test_release_script_runs_the_suite_on_parallel_workers():
    """scripts/release.sh tests for xdist and passes the parallel flags when
    it imports (FS-E)."""
    text = (ROOT / "scripts" / "release.sh").read_text(encoding="utf-8")
    assert "import xdist" in text, "release.sh does not test for pytest-xdist"
    step = text[text.index('echo "[3] tests"'):text.index('echo "[4]')]
    assert "$XDIST" in step or "${XDIST}" in step, step


def _ci_job_text(job_id: str) -> str:
    """The steps of one job in the CI workflow, as one text."""
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "compass.yml")
                         .read_text(encoding="utf-8"))
    job = doc["jobs"][job_id]
    return "\n".join(step.get("run", "") for step in job.get("steps", []))


def test_ci_installs_xdist_and_runs_in_parallel():
    """The CI shard jobs, which run the parallel pass, install pytest-xdist
    and run the suite on parallel workers (FS-F)."""
    job = _ci_job_text("shard")
    # The job installs from a requirements file of exact versions (#99).
    req = re.search(r"pip install -r (\S+)", job)
    assert req, "the shard job installs no requirements file"
    pins = (ROOT / req.group(1)).read_text(encoding="utf-8")
    assert re.search(r"^pytest-xdist==", pins, re.M), "the shard job does not install pytest-xdist"
    assert f"pytest {PARALLEL}" in job, "the shard job does not run in parallel"


def test_releasing_md_names_xdist_and_the_full_archive_check():
    """docs/releasing.md says how to install pytest-xdist and names the
    full-archive check (FS-G)."""
    text = (ROOT / "docs" / "releasing.md").read_text(encoding="utf-8")
    assert "pip install pytest-xdist" in text
    assert "COMPASS_FULL_ARCHIVE=1" in text


ARCHIVE = ROOT / ".compass" / "work"


def _swept_slugs(module: str) -> list:
    """The issues the module sweeps, from the module's own list."""
    sys.path.insert(0, str(ROOT))
    try:
        if module.endswith("test_phase2_invariants.py"):
            from tests.test_phase2_invariants import _SLUGS
            return list(_SLUGS)
        from tests.test_record_keeping_integrity import _pre_existing_task_slugs
        return list(_pre_existing_task_slugs())
    finally:
        sys.path.remove(str(ROOT))


@pytest.mark.parametrize("module", ["tests/test_phase2_invariants.py",
                                    "tests/test_record_keeping_integrity.py"])
def test_each_archive_sweep_is_one_test_per_issue(module):
    """The two archive sweeps collect one test per issue, named after it
    (FS-B)."""
    if not ARCHIVE.is_dir():
        pytest.skip("no local issue archive to sweep")
    # `-o addopts=` drops pytest.ini's own `-q`; two of them print only counts.
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                        "-o", "addopts=", "-p", "no:cacheprovider", module], cwd=ROOT,
                       capture_output=True, text=True,
                       env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    ids = set(re.findall(r"\[([^\]]+)\]", r.stdout))
    expected = set(_swept_slugs(module))
    assert expected, f"{module}: no issue to sweep, so this check proves nothing"
    missing = sorted(expected - ids)
    assert not missing, f"{module}: these issues are not their own test: {missing[:10]}"


SERIAL_TESTS = {
    "tests/next/test_compass_next.py::TestNextLatency::test_next_latency_relative_to_reference",
    "tests/test_statusline.py::test_the_shim_is_fast_enough",
    "tests/test_board_speed.py::test_trc_a4_board_data_speed_on_realistic_archive",
    "tests/test_board_speed.py::test_trc_a5_commands_speed_on_full_archive",
    "tests/test_board_speed.py::test_trc_w6_worktrees_speed",
    "tests/test_delivery_board.py::test_db_5_the_board_is_quick_over_many_issues",
    "tests/test_manifest_parse_speed.py::test_trc_b1_flow_within_two_seconds_on_this_repository",
    "tests/test_manifest_parse_speed.py::test_trc_b2_flow_faster_than_one_parse_on_sample",
    "tests/test_manifest_parse_speed.py::test_trc_b3_cold_flow_within_ten_percent_of_before[no stored state]",
    "tests/test_manifest_parse_speed.py::test_trc_b3_cold_flow_within_ten_percent_of_before[stale stored state]",
    "tests/test_render_all.py::test_dcj_63_guard_fails_on_a_planted_archive_write",
    "tests/test_render_all.py::test_dcj_61_render_all_490_issues_within_bound",
    "tests/test_project_readiness.py::test_prc_37",
    "tests/test_readiness_override_assess.py::test_roa_9_policy_commands_load_compass_yml_in_this_repository",
    "tests/test_issue_dependencies.py::test_dbi_12_hook_cost_budget",
    "tests/test_issue_usage.py::test_arc_10_hook_budget",
    "tests/test_session_start_language.py::test_trc_066",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_bash_command_over_the_limit_is_refused_in_seconds",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_bash_command_at_the_limit_is_judged_as_before",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_repository_that_has_not_opted_in_is_not_refused_for_length",
    "tests/test_pre_tool_hook_time_bounded.py::test_an_over_limit_command_naming_approval_state_is_still_refused_where_compass_is_not_in_use[transcript]",
    "tests/test_pre_tool_hook_time_bounded.py::test_an_over_limit_command_naming_approval_state_is_still_refused_where_compass_is_not_in_use[delegation-file]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_long_allowed_command_under_the_limit_finishes_in_time",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_long_allowed_command_that_starts_with_a_variable_finishes_in_time",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_command_of_many_leading_statements_before_a_variable_finishes_in_time",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_reassigned_variable_before_a_heredoc_over_a_pipe_buffer_is_still_not_expanded",
    "tests/test_pre_tool_hook_time_bounded.py::test_many_unclosed_substitutions_under_the_limit_end_in_time",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_dense_command_of_closed_substitutions_is_refused_by_count",
    "tests/test_pre_tool_hook_time_bounded.py::test_many_distinct_write_targets_read_the_configuration_once",
    "tests/test_pre_tool_hook_time_bounded.py::test_identical_write_targets_end_in_time_with_one_verdict[allowed]",
    "tests/test_pre_tool_hook_time_bounded.py::test_identical_write_targets_end_in_time_with_one_verdict[refused]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_broken_configuration_reader_still_refuses_with_the_cache[plain-glob]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_broken_configuration_reader_still_refuses_with_the_cache[bracket-glob]",
    "tests/test_pre_tool_hook_time_bounded.py::test_more_than_400_distinct_write_targets_are_refused",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_worst_command_at_the_target_limit_ends_in_time",
    "tests/test_pre_tool_hook_time_bounded.py::test_more_than_700_substitution_openers_are_refused",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_worst_unclosed_command_at_the_opener_limit_ends_in_time",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_command_of_90_kb_with_many_line_continuations_ends_in_time",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_script_with_200_closed_substitutions_is_allowed_in_time",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_counts_do_not_apply_where_compass_is_not_in_use[targets]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_counts_do_not_apply_where_compass_is_not_in_use[openers]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_counts_do_not_apply_where_compass_is_not_in_use[unclosed]",
    "tests/test_pre_tool_hook_time_bounded.py::test_more_than_20_distinct_variable_names_are_refused",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_worst_commands_of_many_variable_names_end_in_time[400-names-90KB]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_worst_commands_of_many_variable_names_end_in_time[400-names-12KB]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_worst_commands_of_many_variable_names_end_in_time[400-unassigned-names]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_variable_name_cap_does_not_apply_where_compass_is_not_in_use",
    "tests/test_pre_tool_hook_time_bounded.py::test_globs_bash_cannot_decide_are_matched_in_one_python_start",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_worst_command_under_unsafe_globs_ends_in_time",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_first_enforced_target_is_named_when_globs_are_matched_together[glob-first]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_first_enforced_target_is_named_when_globs_are_matched_together[builtin-first]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_first_enforced_target_is_named_when_globs_are_matched_together[glob-in-the-middle]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_failed_matcher_refuses_the_command_with_unsafe_globs",
    "tests/test_pre_tool_hook_time_bounded.py::test_many_leading_statements_with_many_names_are_refused_or_end_in_time[40000-colons-1-name]",
    "tests/test_pre_tool_hook_time_bounded.py::test_many_leading_statements_with_many_names_are_refused_or_end_in_time[40000-colons-5-names]",
    "tests/test_pre_tool_hook_time_bounded.py::test_many_leading_statements_with_many_names_are_refused_or_end_in_time[4000-cd-20-names]",
    "tests/test_pre_tool_hook_time_bounded.py::test_many_leading_statements_with_many_names_are_refused_or_end_in_time[8000-cd-20-names]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_work_budget_has_a_boundary",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_scans_share_one_work_budget",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_work_budget_does_not_apply_where_compass_is_not_in_use",
    "tests/test_pre_tool_hook_time_bounded.py::test_10000_leading_lines_with_20_names_are_allowed_in_time",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_charged_work_matches_the_measured_time[10000-lines-20-names]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_charged_work_matches_the_measured_time[400-targets-90KB]",
    "tests/test_pre_tool_hook_time_bounded.py::test_many_assignments_with_names_targets_and_globs_end_in_time[5000-assigns-380-targets-30-globs]",
    "tests/test_pre_tool_hook_time_bounded.py::test_many_assignments_with_names_targets_and_globs_end_in_time[3000-assigns-150-targets-300-globs]",
    "tests/test_pre_tool_hook_time_bounded.py::test_many_assignments_with_names_targets_and_globs_end_in_time[8000-assigns-20-targets-1000-globs]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_wall_clock_fuse_stops_the_scan_of_a_project",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_wall_clock_fuse_only_skips_the_scan_where_compass_is_not_in_use",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_wall_clock_fuse_stops_a_slow_reader_before_the_timeout",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_single_write_target_over_2048_bytes_is_refused",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_worst_single_write_target_at_the_limit_ends_in_time[quotes]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_worst_single_write_target_at_the_limit_ends_in_time[segments]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_worst_single_write_target_at_the_limit_ends_in_time[braces]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_worst_single_write_target_at_the_limit_ends_in_time[dots]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_10_kb_write_target_is_refused_in_time[quotes-alone]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_10_kb_write_target_is_refused_in_time[quotes-before]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_10_kb_write_target_is_refused_in_time[quotes-after]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_10_kb_write_target_is_refused_in_time[segments-alone]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_10_kb_write_target_is_refused_in_time[segments-before]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_10_kb_write_target_is_refused_in_time[segments-after]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_10_kb_write_target_is_refused_in_time[braces-alone]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_10_kb_write_target_is_refused_in_time[braces-before]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_10_kb_write_target_is_refused_in_time[braces-after]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_target_limit_does_not_apply_where_compass_is_not_in_use[quotes]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_target_limit_does_not_apply_where_compass_is_not_in_use[segments]",
    "tests/test_pre_tool_hook_time_bounded.py::test_the_target_limit_does_not_apply_where_compass_is_not_in_use[braces]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_write_target_named_like_the_work_count_changes_nothing[5000000000000000000]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_write_target_named_like_the_work_count_changes_nothing[99999999999999999999]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_write_target_named_like_the_work_count_changes_nothing[4611686018427387905]",
    "tests/test_pre_tool_hook_time_bounded.py::test_a_write_target_named_like_the_work_count_changes_nothing[5000]",
    "tests/test_pre_tool_hook_time_bounded.py::test_marker_text_in_a_command_is_an_ordinary_write_target[compass-scan-budget-exceeded]",
    "tests/test_pre_tool_hook_time_bounded.py::test_marker_text_in_a_command_is_an_ordinary_write_target[compass-scan-work=7]",
    "tests/test_pre_tool_hook_time_bounded.py::test_marker_text_in_a_command_is_an_ordinary_write_target[Xcompass-scan-work=7]",
}


def test_timing_tests_are_marked_serial():
    """A wall-clock limit fails at random when parallel workers share the
    CPU, so each timing test carries the serial marker (TRC-001 of
    parallel-ci-flakes)."""
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                        "-o", "addopts=", "-p", "no:cacheprovider", "-m", "serial",
                        *sorted({t.split("::")[0] for t in SERIAL_TESTS})],
                       cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    collected = {line for line in r.stdout.splitlines() if "::" in line}
    assert SERIAL_TESTS <= collected, (SERIAL_TESTS - collected, r.stdout[-500:])


def test_make_test_runs_serial_tests_in_their_own_pass(tmp_path):
    """With pytest-xdist, make test runs the parallel pass without the serial
    tests, then the serial tests alone (TRC-001 of parallel-ci-flakes)."""
    out = _make_n("test", tmp_path, xdist=True)
    assert f'{PARALLEL} -m "not serial"' in out, out
    assert '-m serial' in out.replace('"not serial"', ""), out


def test_ci_runs_serial_tests_in_their_own_pass():
    """CI runs the parallel pass without the serial tests, and the serial
    tests alone in a job of their own (TRC-001 of parallel-ci-flakes)."""
    parallel = _ci_job_text("shard")
    assert f'{PARALLEL} -m "not serial"' in parallel, parallel
    assert "-m serial" not in parallel.replace('"not serial"', ""), parallel
    serial = _ci_job_text("serial")
    assert "pytest tests/ -m serial" in serial, serial
    assert "xdist" not in serial, serial


def test_every_serial_marked_test_is_listed():
    """DCJ-102: a serial test missing from `SERIAL_TESTS` is not covered by the
    guard above, so the guard lists every test that carries the marker."""
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                        "-o", "addopts=", "-p", "no:cacheprovider", "-m", "serial", "tests"],
                       cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    marked = {line for line in r.stdout.splitlines() if "::" in line}
    assert marked, r.stdout[-500:] + r.stderr[-500:]
    assert marked <= SERIAL_TESTS, sorted(marked - SERIAL_TESTS)
