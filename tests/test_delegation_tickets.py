"""The call ticket the pre-tool hook writes for a delegated approval (issue
`delegation-everywhere`, and its threat model).

These cases pin what binds a ticket: the words after `evidence approve`, the
caller and a short life. They run on `delegation_tickets` directly, without a
repository. Whole-flow cases are in `tests/test_delegation_sessions.py`.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import delegation_tickets as tickets  # noqa: E402


@pytest.fixture
def store(tmp_path):
    folder = tmp_path / ".compass" / "delegations"
    folder.mkdir(parents=True)
    (folder / "DL-1.yml").write_text("id: DL-1\n", encoding="utf-8")
    return folder


def _call(command, tmp_path, session="sess-S", **extra):
    body = {"tool_name": "Bash", "session_id": session, "cwd": str(tmp_path),
            "tool_input": {"command": command}}
    body.update(extra)
    return body


def _tickets(store):
    folder = store / "tickets"
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


APPROVE = "compass evidence approve --check c --scope s --issue i --delegated --as main"


def test_ticket_taken_once_and_bound_to_its_words(store):
    words = ["--check", "c", "--issue", "i", "--delegated", "--as", "main"]
    tickets.write_ticket(str(store), "sess-S", "main", words)
    with pytest.raises(tickets.TicketRefused):
        tickets.take(str(store), [*words, "--scope", "other"], "main")
    got = tickets.take(str(store), words, "main")
    assert got == {"session_id": "sess-S", "caller": "main"}
    with pytest.raises(tickets.TicketRefused):
        tickets.take(str(store), words, "main")
    assert not _tickets(store)


def test_ticket_is_bound_to_its_caller(store):
    words = ["--check", "c", "--delegated", "--as", "compass:architect"]
    tickets.write_ticket(str(store), "sess-S", "compass:architect", words)
    with pytest.raises(tickets.TicketRefused):
        tickets.take(str(store), words, "compass:planner")


def test_ticket_expires(store):
    words = ["--check", "c", "--delegated", "--as", "main"]
    old = time.time() - (tickets.TICKET_MINUTES * 60 + 5)
    tickets.write_ticket(str(store), "sess-S", "main", words, now=old)
    with pytest.raises(tickets.TicketRefused):
        tickets.take(str(store), words, "main")
    assert not _tickets(store)


def test_tickets_of_two_sessions_for_the_same_words_are_refused(store):
    words = ["--check", "c", "--delegated", "--as", "main"]
    tickets.write_ticket(str(store), "sess-S", "main", words)
    tickets.write_ticket(str(store), "sess-T", "main", words)
    with pytest.raises(tickets.TicketRefused):
        tickets.take(str(store), words, "main")
    assert len(_tickets(store)) == 2


def test_the_hook_writes_a_ticket_for_a_plain_command_only(store, tmp_path):
    tickets.issue(_call(APPROVE, tmp_path))
    written = _tickets(store)
    assert len(written) == 1
    body = json.loads(written[0].read_text())
    assert body["session_id"] == "sess-S" and body["caller"] == "main"
    assert body["words_sha256"] == tickets.words_digest(
        ["--check", "c", "--scope", "s", "--issue", "i", "--delegated", "--as", "main"])


@pytest.mark.parametrize("command", [
    APPROVE.replace("--scope s", "--scope $HOME"),
    APPROVE.replace("--scope s", "--scope `id`"),
    APPROVE.replace("--scope s", "--scope *"),
    "echo " + APPROVE.replace("compass ", "", 1),
    "bash -c '" + APPROVE + "'",
    APPROVE.replace("--as main", "--as compass:architect"),
])
def test_the_hook_writes_no_ticket_for_a_call_it_cannot_read_the_same_way(
        store, tmp_path, command):
    tickets.issue(_call(command, tmp_path))
    assert not _tickets(store)


def test_the_hook_cuts_the_words_at_the_first_operator(store, tmp_path):
    tickets.issue(_call(APPROVE + "; rm -rf x", tmp_path))
    assert json.loads(_tickets(store)[0].read_text())["words_sha256"] == tickets.words_digest(
        ["--check", "c", "--scope", "s", "--issue", "i", "--delegated", "--as", "main"])


def test_the_hook_writes_no_ticket_for_another_tool_or_with_no_delegation(store, tmp_path):
    tickets.issue(_call(APPROVE, tmp_path, tool_name="Read"))
    assert not _tickets(store)
    (store / "DL-1.yml").unlink()
    tickets.issue(_call(APPROVE, tmp_path))
    assert not _tickets(store)


def test_a_ticket_that_cannot_be_written_raises_nothing(store, tmp_path, monkeypatch):
    def broken(*_a, **_k):
        raise OSError("disk full")
    monkeypatch.setattr(tickets, "write_ticket", broken)
    assert tickets.issue(_call(APPROVE, tmp_path)) is None
    assert not _tickets(store)
