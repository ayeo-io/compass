"""An interactive quick fix records the tokens spent in each stage.

Only `compass run` sessions recorded cost; an interactive session recorded
none, so the token premium of the quick-fix path could be sized but not
located (#375, the token-cost requirement added on 3 October). `quick-fix finish` now reads the
session's own Claude Code transcript and records tokens per stage.

The transcripts here are written by the test in Claude Code's shape, with
invented text. Their shape was checked against a real transcript on
2026-10-04: assistant lines carry `type`, `timestamp`, `requestId`,
`message.id`, `message.model` and `message.usage`, a request can span several
lines, and subagent transcripts sit in `<session>/subagents/`.

Scenario ids: TS-1 to TS-7 (issue `tokens-per-stage-interactive`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "evals"))

try:
    from compass_pkg import session_usage  # noqa: E402
except ImportError:  # before the module exists, each test fails on its own
    session_usage = None

from test_quick_fix_verbs import (  # noqa: E402,F401
    _finish, _git, _manifest, _ready_to_finish, repo)

SESSION = "00000000-1111-2222-3333-444444444444"
SENTINEL = "The quick brown sentinel jumps over the lazy transcript."


def _line(at, request, model="claude-test-1", inp=10, out=5, cw=100, cr=1000,
          text=SENTINEL):
    return json.dumps({
        "type": "assistant", "timestamp": at, "requestId": request,
        "sessionId": SESSION, "cwd": "/somewhere/private",
        "message": {"id": "msg_" + request, "model": model,
                    "content": [{"type": "text", "text": text}],
                    "usage": {"input_tokens": inp, "output_tokens": out,
                              "cache_creation_input_tokens": cw,
                              "cache_read_input_tokens": cr}}})


def _transcripts(config_dir, main_lines, subagent_lines=()):
    folder = config_dir / "projects" / "-somewhere-private"
    folder.mkdir(parents=True)
    user = json.dumps({"type": "user", "timestamp": "2026-10-04T09:00:00Z",
                       "message": {"content": SENTINEL}})
    (folder / f"{SESSION}.jsonl").write_text(
        "\n".join([user, *main_lines, "{not json"]) + "\n", encoding="utf-8")
    if subagent_lines:
        sub = folder / SESSION / "subagents"
        sub.mkdir(parents=True)
        (sub / "agent-1.jsonl").write_text("\n".join(subagent_lines) + "\n",
                                           encoding="utf-8")


@pytest.fixture
def claude_home(tmp_path, monkeypatch):
    home = tmp_path / "claude-home"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SESSION)
    return home


# --- TS-1: the reader -------------------------------------------------------

def test_ts_1_each_request_counts_once_with_its_highest_counts(claude_home):
    _transcripts(claude_home, [
        _line("2026-10-04T09:01:00Z", "req_a", out=5),
        _line("2026-10-04T09:01:02Z", "req_a", out=40),   # the same request
        _line("2026-10-04T09:02:00Z", "req_b"),
    ], [_line("2026-10-04T09:01:30Z", "req_sub", model="claude-test-2")])
    found = session_usage.requests(session_usage.transcript_paths(SESSION))
    by_id = {r["at"]: r for r in found}
    assert len(found) == 3
    assert by_id["2026-10-04T09:01:00+00:00"]["output"] == 40
    assert by_id["2026-10-04T09:01:30+00:00"]["model"] == "claude-test-2"


# --- TS-2 and TS-4: stage windows and cost ----------------------------------

def _manifest_with_times(**times):
    return {"issue": "fix", "started_at": "2026-10-04T09:01:00+00:00",
            "finish_started_at": "2026-10-04T09:05:00+00:00",
            "committed_at": "2026-10-04T09:06:00+00:00",
            "usage": {"session": SESSION}, **times}


def test_ts_2_tokens_fall_into_the_stage_whose_window_holds_them(claude_home, tmp_path):
    _transcripts(claude_home, [
        _line("2026-10-04T09:00:30Z", "assess"),
        _line("2026-10-04T09:02:00Z", "implement1"),
        _line("2026-10-04T09:04:00Z", "implement2"),
        _line("2026-10-04T09:05:30Z", "verify"),
        _line("2026-10-04T09:06:10Z", "ship"),
    ])
    usage = session_usage.stage_usage(
        tmp_path, _manifest_with_times(), other_manifests=[],
        now="2026-10-04T09:06:30+00:00", prices={})
    stages = usage["stages"]
    assert [stages[s]["requests"] for s in ("assess", "implement")] == [1, 2]
    assert stages["implement"]["input"] == 20
    assert stages["implement"]["cache_read"] == 2000
    # Both happen inside one finish call, where the model makes no requests.
    for stage in ("verify", "ship"):
        assert stages[stage]["measured"] is False and "requests" not in stages[stage]
    assert usage["source"] == "claude-code"


def test_ts_2_a_request_on_a_boundary_belongs_to_the_later_stage(claude_home, tmp_path):
    _transcripts(claude_home, [_line("2026-10-04T09:01:00Z", "on-the-start")])
    usage = session_usage.stage_usage(
        tmp_path, _manifest_with_times(), other_manifests=[],
        now="2026-10-04T09:06:30+00:00", prices={})
    assert usage["stages"]["implement"]["requests"] == 1
    assert usage["stages"]["assess"]["requests"] == 0


def test_ts_2_times_with_offsets_sort_as_times(claude_home):
    # 09:30 at +02:00 is 07:30 UTC, earlier than 08:00 UTC, though it sorts
    # later as text.
    _transcripts(claude_home, [_line("2026-10-04T08:00:00Z", "later"),
                               _line("2026-10-04T09:30:00+02:00", "earlier")])
    found = session_usage.requests(session_usage.transcript_paths(SESSION))
    assert [r["at"] for r in found] == ["2026-10-04T07:30:00+00:00",
                                        "2026-10-04T08:00:00+00:00"]


def test_ts_4_cost_only_where_the_project_prices_the_model(claude_home, tmp_path):
    _transcripts(claude_home, [
        _line("2026-10-04T09:00:30Z", "b", model="claude-unpriced"),
        _line("2026-10-04T09:02:00Z", "a", inp=1_000_000, out=0, cw=0, cr=0),
    ])
    usage = session_usage.stage_usage(
        tmp_path, _manifest_with_times(), other_manifests=[],
        now="2026-10-04T09:06:30+00:00",
        prices={"claude-test-1": {"input": 3.0, "output": 15.0,
                                  "cache_write": 3.75, "cache_read": 0.3}})
    assert usage["stages"]["implement"]["cost_usd"] == pytest.approx(3.0)
    assert usage["stages"]["assess"]["cost_usd"] is None


def test_ts_2_finish_records_usage_with_no_commit(repo, claude_home):
    _transcripts(claude_home, [_line("2026-10-04T09:00:30Z", "early")])
    _ready_to_finish(repo, "fix")
    assert _manifest(repo, "fix").get("started_at")
    result = _finish(repo, "fix", "--no-commit")
    assert result.returncode == 0, result.stdout + result.stderr
    usage = _manifest(repo, "fix")["usage"]
    assert usage["session"] == SESSION
    assert set(usage["stages"]) == {"assess", "implement", "verify", "ship"}
    assert SENTINEL.lower() not in (result.stdout + result.stderr).lower()


def test_ts_2_a_committing_finish_commits_the_usage(repo, claude_home):
    _transcripts(claude_home, [_line("2026-10-04T09:00:30Z", "early")])
    _ready_to_finish(repo, "fix")
    result = _finish(repo, "fix")
    assert result.returncode == 0, result.stdout + result.stderr
    committed = yaml.safe_load(_git(repo, "show",
                                    "HEAD:.compass/work/fix/manifest.yml"))
    assert committed["usage"]["session"] == SESSION
    assert "stages" in committed["usage"]


# --- TS-3: no transcript, no failure ----------------------------------------

def test_ts_3_finish_outside_claude_code_says_why(repo, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    _ready_to_finish(repo, "fix")
    result = _finish(repo, "fix", "--no-commit")
    assert result.returncode == 0, result.stdout + result.stderr
    usage = _manifest(repo, "fix")["usage"]
    assert usage["recorded"] is False and usage["reason"] == "not-claude-code"


@pytest.mark.parametrize("bad", ["*", "../../elsewhere/x", "a b", ""])
def test_ts_3_a_session_id_that_is_not_plain_reads_nothing(claude_home, bad):
    _transcripts(claude_home, [_line("2026-10-04T09:02:00Z", "a")])
    assert session_usage.transcript_paths(bad) == []


def test_ts_3_a_missing_transcript_is_a_fixed_reason(claude_home, tmp_path):
    usage = session_usage.stage_usage(
        tmp_path, _manifest_with_times(), other_manifests=[],
        now="2026-10-04T09:06:30+00:00", prices={})
    assert usage == {"recorded": False, "reason": "no-transcript",
                     "session": SESSION, "source": "claude-code"}


# --- TS-6: two issues in one session ----------------------------------------

def test_ts_6_assess_starts_after_the_other_issue_in_this_session(claude_home, tmp_path):
    _transcripts(claude_home, [
        _line("2026-10-04T08:50:00Z", "other-issue-work"),
        _line("2026-10-04T08:58:00Z", "this-assess"),
        _line("2026-10-04T09:02:00Z", "both-at-once"),
    ])
    other = {"issue": "other", "started_at": "2026-10-04T08:40:00+00:00",
             "land_timestamp": "2026-10-04T08:55:00+00:00",
             "usage": {"session": SESSION}}
    unrelated = {"issue": "elsewhere", "land_timestamp": "2026-10-04T08:59:00+00:00",
                 "usage": {"session": "another-session"}}
    usage = session_usage.stage_usage(
        tmp_path, _manifest_with_times(), other_manifests=[other, unrelated],
        now="2026-10-04T09:06:30+00:00", prices={})
    assert usage["stages"]["assess"]["requests"] == 1
    assert "shared" not in usage["stages"]["assess"]
    overlapping = dict(other, land_timestamp="2026-10-04T09:03:00+00:00")
    usage = session_usage.stage_usage(
        tmp_path, _manifest_with_times(), other_manifests=[overlapping],
        now="2026-10-04T09:06:30+00:00", prices={})
    assert usage["stages"]["implement"].get("shared") is True


def test_ts_6_an_issue_finished_without_a_commit_still_bounds_the_next(claude_home, tmp_path):
    _transcripts(claude_home, [
        _line("2026-10-04T08:45:00Z", "other-implement"),
        _line("2026-10-04T08:58:00Z", "this-assess"),
    ])
    other = {"issue": "other", "started_at": "2026-10-04T08:40:00+00:00",
             "finish_started_at": "2026-10-04T08:50:00+00:00",
             "committed_at": "2026-10-04T08:50:05+00:00",
             "usage": {"session": SESSION}}
    usage = session_usage.stage_usage(
        tmp_path, _manifest_with_times(), other_manifests=[other],
        now="2026-10-04T09:06:30+00:00", prices={})
    assert usage["stages"]["assess"]["requests"] == 1
    assert "shared" not in usage["stages"]["assess"]


# --- TS-7: numbers only -----------------------------------------------------

def test_ts_7_no_text_or_path_leaves_the_reader(claude_home, tmp_path):
    _transcripts(claude_home, [_line("2026-10-04T09:02:00Z", "a")])
    found = session_usage.requests(session_usage.transcript_paths(SESSION))
    usage = session_usage.stage_usage(
        tmp_path, _manifest_with_times(), other_manifests=[],
        now="2026-10-04T09:06:30+00:00", prices={})
    dumped = json.dumps(found) + yaml.safe_dump(usage)
    for leak in ("sentinel", "/somewhere/private", "claude-home"):
        assert leak not in dumped.lower(), leak


# --- TS-5: the comparison report --------------------------------------------

def test_ts_5_the_report_shows_tokens_by_stage_per_condition():
    import compare
    stages = {s: {"requests": 1, "input": 10, "output": 5, "cache_write": 0,
                  "cache_read": 100, "cost_usd": None}
              for s in ("assess", "implement")}
    stages.update({s: {"measured": False} for s in ("verify", "ship")})
    record = {"scenario": "s", "condition": "compass", "run": 1,
              "seconds": 1.0, "contained": True,
              "manifests": {".compass/work/fix/manifest.yml":
                            yaml.safe_dump({"usage": {"stages": stages}})}}
    double = {s: (dict(c, input=c["input"] * 3) if "input" in c else c)
              for s, c in stages.items()}
    second = dict(record, run=2, manifests={".compass/work/fix/manifest.yml":
                                            yaml.safe_dump({"usage": {"stages": double}})})
    report = compare.build_report([record, second, dict(record, condition="bare",
                                                        manifests={})])
    assert "Tokens by stage" in report
    assert "assess 125" in report          # (115 + 135) / 2
    assert "verify and ship not recorded" in report   # no session total
    bare_row = next(line for line in report.splitlines()
                    if line.startswith("| Tokens by stage"))
    assert bare_row.rstrip(" |").endswith("not recorded"), bare_row


def test_ts_5_the_harness_leaves_the_transcript_where_claude_writes_it(tmp_path, monkeypatch):
    import harness
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "elsewhere"))
    env = harness._build_child_env("compass", tmp_path)
    assert env["HOME"] == str(tmp_path)
    assert "CLAUDE_CONFIG_DIR" not in env


def test_ts_5_a_measured_stage_with_no_counts_is_not_recorded():
    import compare
    stages = {"assess": {"requests": 1, "input": 10, "output": 5,
                         "cache_write": 0, "cache_read": 0},
              "implement": {"requests": 0, "input": None, "output": None,
                            "cache_write": None, "cache_read": None},
              "verify": {"measured": False}, "ship": {"measured": False}}
    record = {"manifests": {"m": yaml.safe_dump({"usage": {"stages": stages}})}}
    shown = compare._tokens_by_stage([record])
    assert "implement not recorded" in shown and "verify and ship not recorded" in shown
