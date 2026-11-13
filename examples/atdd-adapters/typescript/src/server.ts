/**
 * The todo service's HTTP API.
 *
 *     node src/server.ts --data-dir DATA [--host 127.0.0.1] [--port 8000] [--exit-with-parent]
 *
 * Run it with `node --experimental-strip-types`. It prints
 * `listening on http://HOST:PORT` once it is ready. `--port 0` picks a free
 * port. With `--exit-with-parent` it stops when its standard input closes, so
 * a server a test run started cannot outlive the run.
 */
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";
import { parseArgs } from "node:util";
import { TodoError, TodoService } from "./service.ts";

type Action = "createAccount" | "add" | "complete" | "archive" | "todos";

const ENDPOINTS: [string, RegExp, Action][] = [
  ["POST", /^\/accounts$/, "createAccount"],
  ["POST", /^\/accounts\/(?<email>[^/]+)\/todos$/, "add"],
  ["POST", /^\/accounts\/(?<email>[^/]+)\/todos\/(?<name>[^/]+)\/complete$/, "complete"],
  ["POST", /^\/accounts\/(?<email>[^/]+)\/todos\/(?<name>[^/]+)\/archive$/, "archive"],
  ["GET", /^\/accounts\/(?<email>[^/]+)\/todos$/, "todos"],
];

async function body(request: IncomingMessage): Promise<Record<string, string>> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    chunks.push(chunk as Buffer);
  }
  const text = Buffer.concat(chunks).toString("utf8");
  return text ? JSON.parse(text) : {};
}

function answer(response: ServerResponse, status: number, payload: object): void {
  const data = JSON.stringify(payload);
  response.writeHead(status, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) });
  response.end(data);
}

async function serve(service: TodoService, request: IncomingMessage, response: ServerResponse): Promise<void> {
  const url = new URL(request.url ?? "/", "http://localhost");
  const endpoint = ENDPOINTS.find(([method, pattern]) => method === request.method && pattern.test(url.pathname));
  if (!endpoint) {
    return answer(response, 404, { error: `nothing answers ${request.method} ${url.pathname}` });
  }
  const [, pattern, action] = endpoint;
  const groups = pattern.exec(url.pathname)?.groups ?? {};
  const email = decodeURIComponent(groups.email ?? "");
  const name = decodeURIComponent(groups.name ?? "");
  const sent = request.method === "POST" ? await body(request) : {};
  try {
    if (action === "createAccount") {
      service.createAccount(sent.email ?? "");
      return answer(response, 201, {});
    }
    if (action === "add") {
      service.add(email, sent.name ?? "");
      return answer(response, 201, {});
    }
    if (action === "todos") {
      return answer(response, 200, { todos: service.todos(email, url.searchParams.get("state") ?? "open") });
    }
    service[action](email, name);
    return answer(response, 200, {});
  } catch (refusal) {
    if (refusal instanceof TodoError) {
      return answer(response, refusal.status, { error: refusal.message });
    }
    throw refusal;
  }
}

const { values } = parseArgs({
  options: {
    "data-dir": { type: "string" },
    host: { type: "string", default: "127.0.0.1" },
    port: { type: "string", default: "8000" },
    "exit-with-parent": { type: "boolean", default: false },
  },
});
if (!values["data-dir"]) {
  process.stderr.write("error: give --data-dir\n");
  process.exit(2);
}
const service = new TodoService(values["data-dir"]);
const server = createServer((request, response) => {
  serve(service, request, response).catch((error: unknown) => answer(response, 500, { error: String(error) }));
});
server.listen(Number(values.port), values.host, () => {
  const { port } = server.address() as AddressInfo;
  process.stdout.write(`listening on http://${values.host}:${port}\n`);
});
if (values["exit-with-parent"]) {
  process.stdin.resume();
  process.stdin.on("end", () => {
    server.close();
    server.closeAllConnections();
    service.close();
  });
}
