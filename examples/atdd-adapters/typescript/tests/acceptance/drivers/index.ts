/**
 * The driver interface, and the names of the drivers the factory knows.
 *
 * A driver is the only code that talks to the system, and it does so only the
 * way a real client does. It holds every check: a check passes by returning
 * and fails by throwing an `AssertionError` that says what it expected and
 * what it found. The public methods are the interface the DSL calls. Each
 * driver implements only the protocol: `request` asks the system to do one
 * thing, and `listed` asks it which todos an account has in one state.
 */
import { AssertionError } from "node:assert";
import type { RunningSystem } from "../system.ts";

/**
 * The drivers the factory in `driverFactory.ts` can choose. A name here whose
 * module does not exist yet is a failed beforeEach hook in each scenario.
 */
export const DRIVERS = ["api", "cli"] as const;

export type Action = "account" | "add" | "complete" | "archive";
export type State = "open" | "completed" | "archived";

/** A Given the system refused, so the scenario cannot start. */
export class SetupFailed extends Error {}

function fail(message: string): never {
  throw new AssertionError({ message });
}

export abstract class TodoDriver {
  protected system: RunningSystem;
  private refusal: string | null = null;

  constructor(system: RunningSystem) {
    this.system = system;
  }

  // --- the protocol, one per driver ------------------------------------------

  /** Ask the system to do `action`. Give null when it did, or the reason it gave when it refused. */
  protected abstract request(action: Action, email: string, name?: string): Promise<string | null>;

  /** The names of the account's todos in `state`, as the system lists them. */
  protected abstract listed(email: string, state: State): Promise<string[]>;

  // --- Given -----------------------------------------------------------------

  async hasAccount(email: string): Promise<void> {
    await this.must("account", email);
  }

  async hasOpen(email: string, name: string): Promise<void> {
    await this.must("add", email, name);
  }

  async hasCompleted(email: string, name: string): Promise<void> {
    await this.must("add", email, name);
    await this.must("complete", email, name);
  }

  // --- When ------------------------------------------------------------------

  async add(email: string, name: string): Promise<void> {
    this.refusal = await this.request("add", email, name);
  }

  async complete(email: string, name: string): Promise<void> {
    this.refusal = await this.request("complete", email, name);
  }

  async archive(email: string, name: string): Promise<void> {
    this.refusal = await this.request("archive", email, name);
  }

  // --- Then ------------------------------------------------------------------

  async confirmOpen(email: string, name: string): Promise<void> {
    await this.confirmListed(email, name, "open");
  }

  async confirmCompleted(email: string, name: string): Promise<void> {
    await this.confirmListed(email, name, "completed");
  }

  async confirmArchived(email: string, name: string): Promise<void> {
    await this.confirmListed(email, name, "archived");
  }

  async confirmNotListed(email: string, name: string): Promise<void> {
    for (const state of ["open", "completed", "archived"] as const) {
      const listed = await this.listed(email, state);
      if (listed.includes(name)) {
        fail(`Expected no todo '${name}' for ${email}, found it in ${state}: ${JSON.stringify(listed)}`);
      }
    }
  }

  async confirmRefused(reason: string): Promise<void> {
    if (this.refusal === null) {
      fail(`Expected a refusal saying '${reason}', but the request was done`);
    }
    if (!this.refusal.includes(reason)) {
      fail(`Expected a refusal saying '${reason}', got '${this.refusal}'`);
    }
  }

  // --- shared steps ----------------------------------------------------------

  private async must(action: Action, email: string, name?: string): Promise<void> {
    const refusal = await this.request(action, email, name);
    if (refusal !== null) {
      throw new SetupFailed(`${action} ${email} ${name ?? ""}: the system refused: ${refusal}`);
    }
  }

  private async confirmListed(email: string, name: string, state: State): Promise<void> {
    const listed = await this.listed(email, state);
    if (!listed.includes(name)) {
      const refused = this.refusal ? `; the last request was refused: ${this.refusal}` : "";
      fail(`Expected '${name}' in the ${state} todos of ${email}, found ${JSON.stringify(listed)}${refused}`);
    }
  }
}
