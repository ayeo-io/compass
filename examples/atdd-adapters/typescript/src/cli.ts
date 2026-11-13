/**
 * The todo service's command line.
 *
 *     node src/cli.ts --data-dir DATA account EMAIL
 *     node src/cli.ts --data-dir DATA add EMAIL NAME
 *     node src/cli.ts --data-dir DATA complete EMAIL NAME
 *     node src/cli.ts --data-dir DATA archive EMAIL NAME
 *     node src/cli.ts --data-dir DATA list EMAIL [--state open|completed|archived]
 *
 * Run it with `node --experimental-strip-types`. `list` prints one name a
 * line. A refused request exits 1 and prints `error: <reason>` on standard
 * error.
 */
import { parseArgs } from "node:util";
import { TodoError, TodoService } from "./service.ts";

function main(argv: string[]): number {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      "data-dir": { type: "string", default: process.env.TODO_DATA_DIR },
      state: { type: "string", default: "open" },
    },
  });
  const dataDir = values["data-dir"];
  if (!dataDir) {
    process.stderr.write("error: give --data-dir or set TODO_DATA_DIR\n");
    return 2;
  }
  const [command, email, name] = positionals;
  const needs: Record<string, number> = { account: 2, add: 3, complete: 3, archive: 3, list: 2 };
  if (!command || needs[command] === undefined || positionals.length !== needs[command]) {
    process.stderr.write(`error: usage: ${Object.keys(needs).join("|")} EMAIL [NAME]\n`);
    return 2;
  }
  const service = new TodoService(dataDir);
  try {
    if (command === "account") {
      service.createAccount(email);
    } else if (command === "list") {
      for (const todo of service.todos(email, String(values.state))) {
        process.stdout.write(`${todo}\n`);
      }
    } else if (command === "add") {
      service.add(email, name);
    } else if (command === "complete") {
      service.complete(email, name);
    } else {
      service.archive(email, name);
    }
  } catch (refusal) {
    if (refusal instanceof TodoError) {
      process.stderr.write(`error: ${refusal.message}\n`);
      return 1;
    }
    throw refusal;
  } finally {
    service.close();
  }
  return 0;
}

process.exitCode = main(process.argv.slice(2));
