/**
 * The todo system a run tests: its data folder, and its API server once a driver asks for it.
 *
 * The server starts on the first request for its address and stops when the
 * worker's scenarios end. It is started with `--exit-with-parent`, so it stops
 * even when the run is killed. Nothing is cleared between scenarios: aliased
 * data cannot collide, so it stays.
 */
import { type ChildProcess, spawn } from "node:child_process";
import { once } from "node:events";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("../..", import.meta.url));
const START_MS = 15_000;

export class RunningSystem {
  readonly root = ROOT;
  readonly dataDir: string;
  private server: ChildProcess | null = null;
  private url: Promise<string> | null = null;

  constructor(dataDir: string) {
    this.dataDir = dataDir;
  }

  apiUrl(): Promise<string> {
    this.url ??= this.start();
    return this.url;
  }

  async stop(): Promise<void> {
    const server = this.server;
    if (server === null || server.exitCode !== null) {
      return;
    }
    server.stdin?.end();
    const timer = setTimeout(() => server.kill(), 10_000);
    await once(server, "exit");
    clearTimeout(timer);
  }

  private start(): Promise<string> {
    const server = spawn(
      process.execPath,
      ["--experimental-strip-types", "--disable-warning=ExperimentalWarning", "src/server.ts",
        "--data-dir", this.dataDir, "--port", "0", "--exit-with-parent"],
      { cwd: this.root, stdio: ["pipe", "pipe", "pipe"] },
    );
    this.server = server;
    let log = "";
    server.stderr?.on("data", (chunk) => (log += chunk));
    // Wait for the line that says where it listens, with a limit: a server
    // that never says it is ready must fail the run, not hang it.
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        server.kill();
        reject(new Error(`the todo server did not start within ${START_MS / 1000} seconds\n${log}`));
      }, START_MS);
      let first = "";
      server.stdout?.on("data", (chunk) => {
        first += chunk;
        const line = first.split("\n")[0];
        if (first.includes("\n")) {
          clearTimeout(timer);
          if (line.startsWith("listening on ")) {
            resolve(line.slice("listening on ".length));
          } else {
            reject(new Error(`the todo server did not start: '${line}'\n${log}`));
          }
        }
      });
      server.on("exit", (code) => {
        clearTimeout(timer);
        reject(new Error(`the todo server exited ${code} before it was ready\n${log}`));
      });
    });
  }
}
