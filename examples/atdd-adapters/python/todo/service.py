"""Accounts, and todos that are open, completed or archived.

The store is one SQLite file in a data folder. Several API servers and CLI
processes can open it at once, which is how the acceptance suite runs on
parallel workers against one system.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

STATES = ("open", "completed", "archived")
STORE = "todo.sqlite3"


class TodoError(Exception):
    """A request the service refuses. `status` is the HTTP status the API gives it."""

    status = 400


class AccountExists(TodoError):
    status = 409


class TodoExists(TodoError):
    status = 409


class NotFound(TodoError):
    status = 404


class NotCompleted(TodoError):
    status = 409


class TodoService:
    def __init__(self, data_dir):
        folder = Path(data_dir)
        folder.mkdir(parents=True, exist_ok=True)
        self._path = folder / STORE
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS accounts (email TEXT PRIMARY KEY)")
            db.execute("CREATE TABLE IF NOT EXISTS todos ("
                       "email TEXT NOT NULL, name TEXT NOT NULL, state TEXT NOT NULL, "
                       "PRIMARY KEY (email, name))")

    @contextmanager
    def _db(self):
        # A long timeout: another process may hold the write lock for a moment.
        db = sqlite3.connect(self._path, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_account(self, email):
        with self._db() as db:
            try:
                db.execute("INSERT INTO accounts (email) VALUES (?)", (email,))
            except sqlite3.IntegrityError:
                raise AccountExists(f"account {email} exists") from None

    def add(self, email, name):
        with self._db() as db:
            self._account(db, email)
            try:
                db.execute("INSERT INTO todos (email, name, state) VALUES (?, ?, 'open')",
                           (email, name))
            except sqlite3.IntegrityError:
                raise TodoExists(f"todo {name!r} exists") from None

    def complete(self, email, name):
        with self._db() as db:
            if self._state(db, email, name) == "open":
                db.execute("UPDATE todos SET state = 'completed' WHERE email = ? AND name = ?",
                           (email, name))

    def archive(self, email, name):
        with self._db() as db:
            state = self._state(db, email, name)
            if state == "open":
                raise NotCompleted(f"todo {name!r} is not completed")
            db.execute("UPDATE todos SET state = 'archived' WHERE email = ? AND name = ?",
                       (email, name))

    def todos(self, email, state):
        if state not in STATES:
            raise TodoError(f"no state {state!r}: choose one of {', '.join(STATES)}")
        with self._db() as db:
            self._account(db, email)
            rows = db.execute("SELECT name FROM todos WHERE email = ? AND state = ? ORDER BY name",
                              (email, state))
            return [name for (name,) in rows]

    @staticmethod
    def _account(db, email):
        if db.execute("SELECT 1 FROM accounts WHERE email = ?", (email,)).fetchone() is None:
            raise NotFound(f"no account {email}")

    @staticmethod
    def _state(db, email, name):
        row = db.execute("SELECT state FROM todos WHERE email = ? AND name = ?",
                         (email, name)).fetchone()
        if row is None:
            raise NotFound(f"no todo {name!r}")
        return row[0]
