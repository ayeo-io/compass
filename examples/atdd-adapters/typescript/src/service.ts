/**
 * Accounts, and todos that are open, completed or archived.
 *
 * The store is one SQLite file in a data folder. Several API servers and CLI
 * processes can open it at once, which is how the acceptance suite runs on
 * parallel workers against one system.
 */
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";

export const STATES = ["open", "completed", "archived"] as const;
export type State = (typeof STATES)[number];
const STORE = "todo.sqlite3";

/** A request the service refuses. `status` is the HTTP status the API gives it. */
export class TodoError extends Error {
  status = 400;
}

class Conflict extends TodoError {
  status = 409;
}

class NotFound extends TodoError {
  status = 404;
}

export class TodoService {
  private db: DatabaseSync;

  constructor(dataDir: string) {
    mkdirSync(dataDir, { recursive: true });
    this.db = new DatabaseSync(join(dataDir, STORE));
    // A long wait: another process may hold the write lock for a moment.
    this.db.exec("PRAGMA busy_timeout = 30000");
    this.db.exec("CREATE TABLE IF NOT EXISTS accounts (email TEXT PRIMARY KEY)");
    this.db.exec(
      "CREATE TABLE IF NOT EXISTS todos (email TEXT NOT NULL, name TEXT NOT NULL, " +
        "state TEXT NOT NULL, PRIMARY KEY (email, name))",
    );
  }

  close(): void {
    this.db.close();
  }

  createAccount(email: string): void {
    if (this.db.prepare("SELECT 1 FROM accounts WHERE email = ?").get(email)) {
      throw new Conflict(`account ${email} exists`);
    }
    try {
      this.db.prepare("INSERT INTO accounts (email) VALUES (?)").run(email);
    } catch {
      throw new Conflict(`account ${email} exists`);
    }
  }

  add(email: string, name: string): void {
    this.account(email);
    try {
      this.db.prepare("INSERT INTO todos (email, name, state) VALUES (?, ?, 'open')").run(email, name);
    } catch {
      throw new Conflict(`todo '${name}' exists`);
    }
  }

  complete(email: string, name: string): void {
    if (this.state(email, name) === "open") {
      this.setState(email, name, "completed");
    }
  }

  archive(email: string, name: string): void {
    if (this.state(email, name) === "open") {
      throw new Conflict(`todo '${name}' is not completed`);
    }
    this.setState(email, name, "archived");
  }

  todos(email: string, state: string): string[] {
    if (!(STATES as readonly string[]).includes(state)) {
      throw new TodoError(`no state '${state}': choose one of ${STATES.join(", ")}`);
    }
    this.account(email);
    const rows = this.db
      .prepare("SELECT name FROM todos WHERE email = ? AND state = ? ORDER BY name")
      .all(email, state);
    return rows.map((row) => String(row.name));
  }

  private account(email: string): void {
    if (!this.db.prepare("SELECT 1 FROM accounts WHERE email = ?").get(email)) {
      throw new NotFound(`no account ${email}`);
    }
  }

  private state(email: string, name: string): State {
    const row = this.db.prepare("SELECT state FROM todos WHERE email = ? AND name = ?").get(email, name);
    if (!row) {
      throw new NotFound(`no todo '${name}'`);
    }
    return String(row.state) as State;
  }

  private setState(email: string, name: string, state: State): void {
    this.db.prepare("UPDATE todos SET state = ? WHERE email = ? AND name = ?").run(state, email, name);
  }
}
