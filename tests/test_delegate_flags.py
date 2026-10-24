"""Typing a delegation with flags (issue `delegation-everywhere`, group A).

`/compass:delegate [--agent <name>] [--until <time>] [--on <issues>] [--for <forms>]
[--max <n>]`, every flag optional and in any order. With no `--agent` a delegation
covers the typing session's agents; with no `--until` it lasts until revoked.

Scenario ids: `TRC-001` to `TRC-019`. Each test name starts with its scenario id.
In this step the store is still the session's own `.compass/` folder.
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import event, project  # noqa: E402
from test_delegation_limits import _write_dl  # noqa: E402

ARCHITECT = "compass:architect"
FLAG_FORM = ("/compass:delegate [--agent <name>] [--until <time>] [--on <issues>] "
             "[--for <forms>] [--max <n>]")
DEFAULT_FORMS = ["checks", "documents", "checkpoints", "decisions"]


def _store(root):
    return root / ".compass" / "delegations"


def _delegations(root):
    folder = _store(root)
    return {p.stem: yaml.safe_load(p.read_text(encoding="utf-8"))
            for p in sorted(folder.glob("DL-*.yml"))} if folder.is_dir() else {}


def _type(root, args, command="compass:delegate", session="sess-1", **kw):
    from compass_pkg import prompt_approval
    return prompt_approval.handle(event(root, command=command, args=args, session=session,
                                        **kw), {}, plugin_root=str(ROOT))


@pytest.fixture
def clock(monkeypatch):
    """A fixed local time of 2026-10-23 10:00."""
    from compass_pkg import delegations
    fixed = datetime.datetime(2026, 10, 23, 10, 0).astimezone()
    monkeypatch.setattr(delegations, "_now", lambda: fixed)
    return fixed


def _until(dl):
    return datetime.datetime.fromisoformat(dl["until"].replace("Z", "+00:00"))


def _refused(root, args, *needles, **kw):
    result = _type(root, args, **kw)
    assert result.block, (args, result)
    for needle in needles:
        assert needle in result.message, (needle, result.message)
    assert not _delegations(root), (args, _delegations(root))
    return result


# --- defaults, flag order and --agent ------------------------------------------------------

def test_TRC_001_a_bare_compass_delegate_covers_this_session_every_issue_and_the_default(
        tmp_path):
    root = project(tmp_path)
    result = _type(root, "")
    assert not result.block, result
    found = _delegations(root)
    assert list(found) == ["DL-1"], found
    dl = found["DL-1"]
    assert dl["format"] == 2 and dl["covers_session"] == "sess-1"
    assert not dl.get("agent") and not dl.get("until") and not dl.get("issues")
    assert dl["forms"] == DEFAULT_FORMS
    for needle in ("DL-1", "this session", "every issue in the repository's worktrees",
                   "until you type /compass:revoke", "not the guardrail 5 sign-off",
                   "agents of other sessions are not covered", "--agent <name>"):
        assert needle in result.message, (needle, result.message)
    for needle in ("compass evidence approve", "--delegated", "--as", "own name"):
        assert needle in result.context, (needle, result.context)


@pytest.mark.parametrize("arguments", [
    f"--agent {ARCHITECT} --until 08:00 --on feature --for checks --max 2",
    f"--max 2 --for checks --on feature --until 08:00 --agent {ARCHITECT}",
    f"--on feature --agent {ARCHITECT} --max 2 --until 08:00 --for checks",
])
def test_TRC_002_the_flags_can_come_in_any_order(tmp_path, clock, arguments):
    root = project(tmp_path)
    result = _type(root, arguments)
    assert not result.block, result
    dl = _delegations(root)["DL-1"]
    end = datetime.datetime.combine((clock + datetime.timedelta(days=1)).date(),
                                    datetime.time(8, 0)).astimezone()
    assert dl["agent"] == ARCHITECT and _until(dl) == end
    assert dl["issues"] == {"feature": 1} and dl["forms"] == ["checks"]
    assert dl["max_uses"] == 2


def test_TRC_002_an_end_time_after_summer_time_ends_is_the_time_typed(
        tmp_path, monkeypatch):
    """08:00 typed the evening before the clocks change ends at 08:00 after the
    change, not at the offset that held when it was typed."""
    import time
    from compass_pkg import delegations
    monkeypatch.setenv("TZ", "Europe/London")
    time.tzset()
    try:
        fixed = datetime.datetime(2026, 10, 24, 22, 10).astimezone()
        monkeypatch.setattr(delegations, "_now", lambda: fixed)
        root = project(tmp_path)
        assert not _type(root, "--until 08:00").block
        end = _until(_delegations(root)["DL-1"])
        assert end == datetime.datetime(2026, 10, 25, 8, 0, tzinfo=datetime.timezone.utc)
    finally:
        monkeypatch.undo()
        time.tzset()


def test_TRC_003_agent_names_one_agent_exactly_as_claude_code_reports_it(tmp_path):
    root = project(tmp_path)
    result = _type(root, f"--agent {ARCHITECT}")
    assert not result.block, result
    dl = _delegations(root)["DL-1"]
    assert dl["agent"] == ARCHITECT and not dl.get("covers_session")
    assert ARCHITECT in result.message and "until you type /compass:revoke" in result.message


@pytest.mark.parametrize("name", ["any", "ANY"])
def test_TRC_004_agent_any_is_refused(tmp_path, name):
    root = project(tmp_path)
    _refused(root, f"--agent {name}", "names one agent", "'any' is refused")


# --- end time, --max, --for and the count in force -----------------------------------------

def test_TRC_005_until_has_no_upper_limit(tmp_path, clock):
    root = project(tmp_path)
    result = _type(root, "--until 2026-11-22T10:00")
    assert not result.block, result
    dl = _delegations(root)["DL-1"]
    assert _until(dl) == datetime.datetime(2026, 11, 22, 10, 0).astimezone()


@pytest.mark.parametrize("text", ["25:00", "tomorrow", "2026-10-22T10:00"])
def test_TRC_006_an_end_time_that_has_passed_or_cannot_be_read_is_refused(
        tmp_path, clock, text):
    root = project(tmp_path)
    _refused(root, f"--until {text}", f"'{text}'")


@pytest.mark.parametrize("n", ["0", "-1", "two", "1.5"])
def test_TRC_007_max_takes_a_whole_number_of_at_least_1(tmp_path, n):
    root = project(tmp_path)
    _refused(root, f"--max {n}", "--max takes a whole number of approvals", f"'{n}'")


def test_TRC_008_for_takes_only_the_forms_a_delegation_covers(tmp_path):
    root = project(tmp_path)
    _refused(root, "--for checks,everything", "'everything'", "g5", "checks", "documents",
             "checkpoints", "decisions", "check:<id>")


def test_TRC_009_a_sixth_delegation_in_force_is_accepted(tmp_path):
    root = project(tmp_path)
    for number in range(1, 6):
        _write_dl(root, number, until=None, format=2)
    result = _type(root, "--agent compass:planner")
    assert not result.block, result
    found = _delegations(root)
    assert sorted(found) == [f"DL-{n}" for n in range(1, 7)]
    assert found["DL-6"]["agent"] == "compass:planner"
    assert all(not found[f"DL-{n}"].get("revoked_at") for n in range(1, 6))


# --- what the parser refuses ---------------------------------------------------------------

def test_TRC_010_the_old_positional_form_is_refused_with_the_flag_form(tmp_path):
    root = project(tmp_path)
    _refused(root, f"{ARCHITECT} until 08:00 on feature", FLAG_FORM)


def test_TRC_011_labels_is_refused_with_a_pointer_to_on(tmp_path):
    root = project(tmp_path)
    _refused(root, "--labels auth", "--labels", "--on <issues>")


@pytest.mark.parametrize("arguments,flag", [
    ("--foo 1", "--foo"),
    (f"--agents {ARCHITECT}", "--agents"),
    (f"-a {ARCHITECT}", "-a"),
    ("--Until 08:00", "--Until"),
])
def test_TRC_012_an_unknown_flag_is_refused_and_named(tmp_path, arguments, flag):
    root = project(tmp_path)
    _refused(root, arguments, f"'{flag}'", FLAG_FORM)


def test_TRC_013_a_flag_given_twice_is_refused_and_named(tmp_path):
    root = project(tmp_path)
    _refused(root, "--until 08:00 --until 09:00", "--until is given twice")


@pytest.mark.parametrize("arguments,flag", [
    ("--until", "--until"),
    ("--agent --until 08:00", "--agent"),
    ("--for checks --on", "--on"),
])
def test_TRC_014_a_flag_with_no_value_is_refused(tmp_path, arguments, flag):
    root = project(tmp_path)
    _refused(root, arguments, f"{flag} needs a value")


def test_TRC_015_a_flag_joined_to_its_value_with_an_equals_sign_is_refused(tmp_path):
    root = project(tmp_path)
    _refused(root, "--until=08:00", "'--until=08:00'", "--until 08:00")


def test_TRC_016_a_word_that_belongs_to_no_flag_is_refused(tmp_path):
    root = project(tmp_path)
    _refused(root, f"--until 08:00 {ARCHITECT}", f"'{ARCHITECT}'", FLAG_FORM)


# --- session id and the guardrail 5 code ---------------------------------------------------

def test_TRC_017_a_delegation_with_no_agent_needs_a_session_id(tmp_path):
    root = project(tmp_path)
    _refused(root, "--until 08:00", "cannot name this session", "--agent <name>",
             session="")


def test_TRC_018_for_g5_with_no_end_time_waits_for_the_confirmation_code(tmp_path):
    root = project(tmp_path)
    result = _type(root, "--for g5")
    assert result.block, result
    assert "this session's agents" in result.message
    assert "sign off irreversible work" in result.message
    assert "until you type /compass:revoke" in result.message
    assert re.search(r"confirm [0-9a-f]{4}(-[0-9a-f]{4}){3}\b", result.message), result.message
    assert (_store(root) / "confirm-sess-1.yml").is_file()
    assert not _delegations(root)


def test_TRC_019_the_typed_back_code_writes_the_guardrail_5_delegation_with_no_end(
        tmp_path, monkeypatch):
    from compass_pkg import delegations
    root = project(tmp_path)
    first = _type(root, "--for g5", prompt_id="p-first")
    code = re.search(r"/compass:delegate confirm (\S+)", first.message).group(1)
    later = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=4)
    monkeypatch.setattr(delegations, "_now", lambda: later)
    done = _type(root, f"confirm {code}", prompt_id="p-second")
    assert not done.block, done
    dl = _delegations(root)["DL-1"]
    assert dl["covers_session"] == "sess-1" and "g5" in dl["forms"]
    assert not dl.get("until") and dl["requested_prompt_id"] == "p-first"
    assert not (_store(root) / "confirm-sess-1.yml").exists()
