# compass_pkg.delegation_tickets - the pre-tool hook's record of a delegated approval it read
"""A call ticket is what lets `compass evidence approve --delegated` know which
Claude Code session and agent made the call (issue delegation-everywhere).

Only a hook receives `session_id` from Claude Code. A command can set any
environment variable, so the CLI never reads the session from the environment.
Instead the pre-tool hook, on a Bash call that it reads and allows, writes a
ticket into the common store: `<store>/tickets/<random>.json`. The ticket holds
the session id, the caller (`approval_guard.caller`) and the SHA-256 of the
shell words after `evidence approve`. The CLI takes the one ticket whose words
and caller match its own, under the store lock, and deletes it. A call the hook
never read, such as a script, has no ticket, so the CLI refuses it.

A ticket is written only for a plain command: `compass evidence approve ...
--delegated --as <caller>` with no variable, glob, brace, tilde, backslash or
back-tick in its words, so the words the hook read are the words the CLI gets.
With no delegation in the store, no ticket is written. A ticket that cannot be
written blocks nothing: the CLI then finds no ticket and refuses.

A ticket lasts `TICKET_MINUTES`, because a permission prompt between the hook
and the run is also a person's answer. Expired tickets are deleted whenever one
is written or taken.

Standard library only, because the pre-tool hook imports it.
"""
# DEPENDENCY: standard library (hashlib, json, os, re, secrets, shlex, time);
# compass_pkg.approval_guard (the caller and the `--as` values it already
# checks), compass_pkg.worktree_lookup (the store).
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shlex
import time

TICKETS = "tickets"
TICKET_MINUTES = 10
#: A word that holds one of these is not read the same by the shell and by the
#: CLI, so no ticket is written for it.
UNSAFE = re.compile(r"[$`*?\[{~\\\n]")
OPERATORS = re.compile(r"[();<>|&]+")
#: The most evidence-approve commands one call can hold a ticket for.
MOST_PER_CALL = 5


class TicketRefused(Exception):
    """No ticket lets this call record an approval. The text says why."""


def words_digest(words):
    """The SHA-256 of the words, kept apart so that `a b` and `a`, `b` differ."""
    return hashlib.sha256("\x00".join(words).encode("utf-8", "surrogateescape")).hexdigest()


def _tokens(command):
    """The words of a command with each shell operator as a word of its own."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def approve_words(command):
    """The word lists that follow each `compass evidence approve` of a plain
    command, each cut at the first shell operator or comment. An empty list
    when the command is not plain."""
    try:
        tokens = _tokens(command.replace("\\\n", ""))
    except ValueError:
        return []
    found = []
    for i in range(1, len(tokens) - 1):
        if tokens[i] != "evidence" or tokens[i + 1] != "approve":
            continue
        if os.path.basename(tokens[i - 1]) != "compass":
            continue
        words = []
        for word in tokens[i + 2:]:
            if OPERATORS.fullmatch(word) or word.startswith("#"):
                break
            words.append(word)
        if any(UNSAFE.search(w) for w in words):
            return []
        found.append(words)
    return found[:MOST_PER_CALL]


def _folder(store):
    return os.path.join(store, TICKETS)


def _drop_expired(store, now):
    folder = _folder(store)
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        path = os.path.join(folder, name)
        try:
            with open(path, encoding="utf-8") as fh:
                issued = float(json.load(fh).get("issued_at"))
        except (OSError, ValueError, TypeError, AttributeError):
            continue
        if now - issued > TICKET_MINUTES * 60:
            try:
                os.remove(path)
            except OSError:
                pass


def write_ticket(store, session_id, caller, words, tool_use_id="", now=None):
    """Write one ticket into the store's folder. Returns its path."""
    now = time.time() if now is None else now
    folder = _folder(store)
    os.makedirs(folder, exist_ok=True)
    _drop_expired(store, now)
    path = os.path.join(folder, secrets.token_hex(16) + ".json")
    body = {"session_id": session_id, "caller": caller, "words_sha256": words_digest(words),
            "issued_at": now, "tool_use_id": tool_use_id}
    part = path + ".part"
    with open(part, "w", encoding="utf-8") as fh:
        json.dump(body, fh)
    os.replace(part, path)
    return path


def _has_delegation(store):
    try:
        return any(re.fullmatch(r"DL-\d+\.yml", n) for n in os.listdir(store))
    except OSError:
        return False


def issue(event, timeout=5):
    """Write a ticket for each delegated approval in a Bash call the hook reads
    and allows. Writes nothing for another call, for a command that is not
    plain, for one whose `--as` is not the caller, or when the store holds no
    delegation. Never raises: a call with no ticket is refused by the CLI."""
    try:
        _issue(event, timeout)
    except Exception:                                   # noqa: BLE001 - see the docstring
        return


def _issue(event, timeout):
    if event.get("tool_name") != "Bash":
        return
    tool_input = event.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or "--delegated" not in command:
        return
    from compass_pkg import approval_guard, worktree_lookup
    who = approval_guard.caller(event)
    wanted = [w for w in approve_words(command)
              if "--delegated" in w and approval_guard._as_values(w) == [who]]
    if not wanted or who is None:
        return
    cwd = str(event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or "")
    if not cwd:
        return
    store = worktree_lookup.common_store(worktree_lookup.project_folder(cwd), timeout=timeout)
    if store.folder is None or not _has_delegation(store.folder):
        return
    for words in wanted:
        write_ticket(store.folder, str(event.get("session_id") or ""), who, words,
                     str(event.get("tool_use_id") or ""))


def take(store, words, agent, now=None):
    """The ticket for these words and this caller, deleted as it is taken. The
    caller holds the store lock. Raises `TicketRefused` when there is none, or
    when tickets from two sessions match."""
    now = time.time() if now is None else now
    _drop_expired(store, now)
    folder = _folder(store)
    digest = words_digest(words)
    live = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        names = []
    for name in names:
        path = os.path.join(folder, name)
        try:
            with open(path, encoding="utf-8") as fh:
                body = json.load(fh)
            issued = float(body["issued_at"])
        except (OSError, ValueError, TypeError, KeyError):
            continue
        if (isinstance(body, dict) and body.get("words_sha256") == digest
                and body.get("caller") == agent):
            live.append((issued, path, body))
    if not live:
        raise TicketRefused(
            "the pre-tool hook did not read this call, so Compass cannot tell which "
            "session made it. Run it as a plain command in your Bash tool, with "
            "--issue <slug>, not from a script or another program.")
    if len({str(body.get("session_id") or "") for _, _, body in live}) > 1:
        raise TicketRefused(
            "tickets from more than one session match this call, so Compass cannot tell "
            "which session made it. Run it again.")
    issued, path, body = min(live, key=lambda item: item[0])
    os.remove(path)
    return {"session_id": str(body.get("session_id") or ""), "caller": agent}
