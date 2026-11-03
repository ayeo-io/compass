/**
 * The runner adapter: starts node:test on the acceptance suite, and writes its JUnit report.
 *
 *     node --experimental-strip-types tests/acceptance/run.ts [--driver api|cli]
 *         [--workers N] [--junit PATH] [TEST ...]
 *
 * `npm run acceptance --` runs it with those flags. Run it from the example's
 * root.
 *
 * - The driver is chosen once, when the run starts: `--driver`, or
 *   ACCEPTANCE_DRIVER when the option is not given, or `api`. A name that is
 *   not in DRIVERS stops the run before any scenario.
 * - Each TEST is a file, or `<file>::<test name>` for one scenario. With no
 *   TEST it runs every `*.spec.ts` file of this folder.
 * - `--workers N` runs up to N files at once, each in its own process.
 * - The JUnit report, written by `junitReporter.ts` so that each test names
 *   its file, goes to `--junit PATH`, or else to the path in
 *   COMPASS_JUNIT_REPORT, where `compass tdd-red` and the other record
 *   commands ask a runner that is not pytest to write it. The terminal shows
 *   node's spec report either way.
 *
 * Before the workers start, it makes the run id the alias helper reads
 * (ACCEPTANCE_RUN_ID), and picks the store every worker of the run shares:
 * TODO_DATA_DIR when it is set, so several runs can share one store, or else a
 * new folder, made once for the run.
 */
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdtempSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { DRIVERS } from "./drivers/index.ts";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const ROOT = fileURLToPath(new URL("../..", import.meta.url));

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    driver: { type: "string" },
    workers: { type: "string", default: "1" },
    junit: { type: "string" },
  },
});

const driver = values.driver ?? process.env.ACCEPTANCE_DRIVER ?? "api";
if (!(DRIVERS as readonly string[]).includes(driver)) {
  process.stderr.write(`no driver '${driver}': choose one of ${DRIVERS.join(", ")}\n`);
  process.exit(2);
}
process.env.ACCEPTANCE_DRIVER = driver;
process.env.ACCEPTANCE_RUN_ID = randomUUID().replace(/-/g, "").slice(0, 8);
process.env.TODO_DATA_DIR ||= mkdtempSync(join(tmpdir(), "todo-data-"));
process.stdout.write(`acceptance driver: ${driver}\ntodo store: ${process.env.TODO_DATA_DIR}\n`);

const files = new Set<string>();
const names: string[] = [];
for (const test of positionals) {
  const [file, name] = test.split("::");
  files.add(file);
  if (name !== undefined) {
    names.push(`^${escape(name)}$`);
  }
}
if (files.size === 0) {
  for (const file of readdirSync(HERE).filter((f) => f.endsWith(".spec.ts")).sort()) {
    files.add(relative(ROOT, join(HERE, file)));
  }
}

const report = values.junit ?? process.env.COMPASS_JUNIT_REPORT;
const args = [
  "--experimental-strip-types",
  "--disable-warning=ExperimentalWarning",
  "--test",
  `--test-concurrency=${values.workers}`,
  "--test-reporter=spec",
  "--test-reporter-destination=stdout",
  ...(report ? ["--test-reporter=./tests/acceptance/junitReporter.ts", `--test-reporter-destination=${report}`] : []),
  ...names.map((pattern) => `--test-name-pattern=${pattern}`),
  ...files,
];
const run = spawnSync(process.execPath, args, { cwd: ROOT, stdio: "inherit" });
process.exit(run.status ?? 1);
