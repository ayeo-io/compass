/** The CLI driver: reaches the todo service through its command line, as a person at a terminal does. */
import { spawnSync } from "node:child_process";
import { type Action, type State, TodoDriver } from "./index.ts";

const TIMEOUT_MS = 30_000;

export class Driver extends TodoDriver {
  protected async request(action: Action, email: string, name?: string): Promise<string | null> {
    const run = this.todo(action, email, ...(name === undefined ? [] : [name]));
    return run.status === 0 ? null : run.stderr.trim().replace(/^error: /, "");
  }

  protected async listed(email: string, state: State): Promise<string[]> {
    const run = this.todo("list", email, "--state", state);
    if (run.status !== 0) {
      throw new Error(`listing the ${state} todos of ${email} failed: ${run.stderr.trim()}`);
    }
    return run.stdout.split("\n").filter((line) => line !== "");
  }

  private todo(...args: string[]) {
    return spawnSync(
      process.execPath,
      ["--experimental-strip-types", "--disable-warning=ExperimentalWarning", "src/cli.ts",
        "--data-dir", this.system.dataDir, ...args],
      { cwd: this.system.root, encoding: "utf8", timeout: TIMEOUT_MS },
    );
  }
}
