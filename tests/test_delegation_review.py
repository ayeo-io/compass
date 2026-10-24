"""Reviewing delegated approvals (issue `delegation-everywhere`, group E).

The summary hooks list the delegated approvals that wait for the person, from any
worktree, and write what each session was shown. `/compass:approve` with nothing
pending marks reviewed only the rows of the latest summary shown in its own
session, before the command, whose digest still matches. `/compass:reject
<record id>` searches every issue of every worktree.

Scenario ids: `TRC-059` to `TRC-067`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import CHECK, OWNER, SLUG  # noqa: E402
from delegation_support import (add_issue, add_worktree, copy_issue, delegated,  # noqa: E402
                                evidence_count, repo, type_)
from test_delegation import _hook_json  # noqa: E402

ARCH = "compass:architect"
WT = "wt-issue"
SESSION = "sess-S"


def _setup(tmp_path):
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    copy_issue(top, work, WT)
    (work / ".compass" / "current-task").write_text(WT + "\n", encoding="utf-8")
    assert not type_(top, "", session=SESSION).block
    return top, work


def _manifest(project, slug):
    return yaml.safe_load((project / ".compass" / "work" / slug / "manifest.yml").read_text())


def _approved(cwd, project, slug, scope="s"):
    """A delegated approval by a subagent of the session; returns its record id."""
    code, out, err = delegated(cwd, ARCH, "--check", CHECK, "--scope", scope, "--issue", slug,
                               session=SESSION)
    assert code == 0, out + err
    return _manifest(project, slug)["evidence"][-1]["id"]


def _record(project, slug, record_id):
    return next(r for r in _manifest(project, slug)["evidence"] if r["id"] == record_id)


def _summary(project, prompt_id, session=SESSION):
    from compass_pkg import delegations
    return delegations.summary_for_hook(str(project), session, prompt_id)


def _approve(project, session=SESSION, **kw):
    return type_(project, "", command="compass:approve", session=session, **kw)


def test_TRC_059_compass_approve_with_nothing_pending_marks_reviewed_only_what_the_last_summary(
        tmp_path):
    top, _ = _setup(tmp_path)
    shown = _approved(top, top, SLUG, "first")
    assert shown in _summary(top, "p-summary")
    later = _approved(top, top, SLUG, "second")
    result = _approve(top)
    assert not result.block, result
    assert _record(top, SLUG, shown)["reviewed_by"] == OWNER
    assert _record(top, SLUG, shown)["reviewed_at"]
    assert not _record(top, SLUG, later).get("reviewed_at")
    assert shown in result.message and later not in result.message, result.message


def test_TRC_060_an_approval_recorded_after_the_summary_appears_in_the_next_summary(
        tmp_path):
    top, _ = _setup(tmp_path)
    first = _approved(top, top, SLUG, "first")
    _summary(top, "p-1")
    second = _approved(top, top, SLUG, "second")
    assert not _approve(top).block
    text = _summary(top, "p-3")
    assert second in text and first not in text, text


def test_TRC_061_a_summary_shown_in_answer_to_the_compass_approve_prompt_itself_does(
        tmp_path):
    top, _ = _setup(tmp_path)
    first = _approved(top, top, SLUG, "first")
    _summary(top, "p-before")
    second = _approved(top, top, SLUG, "second")
    both = _summary(top, "p-approve")
    assert first in both and second in both
    assert not _approve(top, prompt_id="p-approve").block
    assert _record(top, SLUG, first).get("reviewed_at")
    assert not _record(top, SLUG, second).get("reviewed_at")


def test_TRC_062_the_summary_lists_delegated_approvals_on_issues_in_other_worktrees(
        tmp_path):
    top, work = _setup(tmp_path)
    record = _approved(work, work, WT)
    text = _summary(top, "p-1")
    for needle in (record, WT, str(work), ARCH, "DL-1"):
        assert needle in text, (needle, text)


def test_TRC_063_compass_approve_with_nothing_pending_marks_a_shown_approval_in_another_worktree(
        tmp_path):
    top, work = _setup(tmp_path)
    record = _approved(work, work, WT)
    _summary(top, "p-1")
    result = _approve(top)
    assert not result.block, result
    assert _record(work, WT, record)["reviewed_by"] == OWNER
    assert _record(work, WT, record)["reviewed_at"]


def test_TRC_064_a_summary_shown_in_another_session_does_not_count(tmp_path):
    top, _ = _setup(tmp_path)
    record = _approved(top, top, SLUG)
    assert record in _summary(top, "p-1", session="sess-T")
    result = _approve(top)
    assert result.block and "nothing was marked reviewed" in result.message, result
    assert not _record(top, SLUG, record).get("reviewed_at")


def test_TRC_065_compass_reject_record_id_overrules_a_delegated_approval_in_another_worktree(
        tmp_path):
    top, work = _setup(tmp_path)
    record = _approved(work, work, WT)
    result = type_(top, f"{record} the scope is wrong", command="compass:reject",
                   session=SESSION)
    assert not result.block, result
    last = _manifest(work, WT)["evidence"][-1]
    assert last["check"] == CHECK and last["decision"] == "rejected"
    assert last["overrules"] == record and last["reason"] == "the scope is wrong"
    assert WT in result.message and str(work) in result.message, result.message


def test_TRC_066_compass_reject_record_id_held_by_two_issues_is_refused_and_lists(tmp_path):
    top, work = _setup(tmp_path)
    one = _approved(top, top, SLUG)
    other = _approved(work, work, WT)
    assert one == other
    counts = (evidence_count(top / ".compass" / "work" / SLUG),
              evidence_count(work / ".compass" / "work" / WT))
    result = type_(top, f"{one} wrong", command="compass:reject", session=SESSION)
    assert result.block, result
    assert f"/compass:reject {one} <reason> --issue {SLUG}" in result.message, result.message
    assert f"/compass:reject {one} <reason> --issue {WT}" in result.message, result.message
    assert counts == (evidence_count(top / ".compass" / "work" / SLUG),
                      evidence_count(work / ".compass" / "work" / WT))


def test_TRC_067_with_no_delegation_file_the_summary_starts_no_git_process_and_reads(
        tmp_path):
    import subprocess
    top = repo(tmp_path)
    trees = [top, add_worktree(top, "w1"), add_worktree(top, "w2")]
    for number in range(20):
        add_issue(trees[number % 3], f"issue-{number}")
    spy = tmp_path / "spy"
    spy.mkdir()
    log = tmp_path / "spy.log"
    git = spy / "git"
    git.write_text(f'#!/bin/sh\necho "$@" >> "{log}"\nexit 1\n', encoding="utf-8")
    git.chmod(git.stat().st_mode | stat.S_IEXEC)
    (spy / "sitecustomize.py").write_text(
        "import sys\n"
        "def _watch(event, args):\n"
        "    if event == 'open' and str(args[0]).endswith('manifest.yml'):\n"
        f"        open({str(tmp_path / 'manifests.log')!r}, 'a').write(str(args[0]) + '\\n')\n"
        "sys.addaudithook(_watch)\n", encoding="utf-8")
    env = {"PATH": f"{spy}:" + os.environ.get("PATH", "/usr/bin:/bin"),
           "PYTHONPATH": str(spy), "HOME": str(top / ".home"), "LANG": "C.UTF-8",
           "CLAUDE_PROJECT_DIR": str(top), "PYTHONDONTWRITEBYTECODE": "1"}
    body = {"session_id": SESSION, "prompt_id": "p-1", "hook_event_name": "UserPromptSubmit",
            "prompt": "hello", "cwd": str(top)}
    done = subprocess.run(["bash", str(ROOT / "hooks" / "approval-summary.sh")],
                          input=json.dumps(body), cwd=top, env=env, capture_output=True,
                          text=True, timeout=60)
    assert done.returncode == 0 and done.stdout.strip() == "", (done.stdout, done.stderr)
    assert not log.exists(), log.read_text()
    assert not (tmp_path / "manifests.log").exists()


def test_the_summary_hooks_write_the_shown_list_and_keep_two_entries(tmp_path):
    top, _ = _setup(tmp_path)
    record = _approved(top, top, SLUG)
    start = _hook_json("session-start.sh", top, {"session_id": SESSION, "source": "startup"})
    assert record in start["systemMessage"]
    for number in (1, 2):
        _hook_json("approval-summary.sh", top,
                   {"session_id": SESSION, "prompt_id": f"p-{number}",
                    "hook_event_name": "UserPromptSubmit", "prompt": "x", "cwd": str(top)})
    shown = json.loads((top / ".compass" / "delegations" / "shown" / f"{SESSION}.json")
                       .read_text())
    assert [e["prompt_id"] for e in shown["entries"]] == ["p-1", "p-2"]
    row = shown["entries"][-1]["records"][0]
    assert row["id"] == record and row["issue"] == SLUG and row["digest"]
