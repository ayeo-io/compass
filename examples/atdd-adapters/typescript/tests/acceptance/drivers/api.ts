/** The API driver: reaches the todo service through its HTTP API, as a web client does. */
import { type Action, type State, TodoDriver } from "./index.ts";

const TIMEOUT_MS = 10_000;

export class Driver extends TodoDriver {
  protected async request(action: Action, email: string, name?: string): Promise<string | null> {
    const account = `/accounts/${encodeURIComponent(email)}`;
    let answer: [number, Record<string, unknown>];
    if (action === "account") {
      answer = await this.call("POST", "/accounts", { email });
    } else if (action === "add") {
      answer = await this.call("POST", `${account}/todos`, { name });
    } else {
      answer = await this.call("POST", `${account}/todos/${encodeURIComponent(name ?? "")}/${action}`, {});
    }
    const [status, payload] = answer;
    return status < 400 ? null : String(payload.error ?? `HTTP ${status}`);
  }

  protected async listed(email: string, state: State): Promise<string[]> {
    const [status, payload] = await this.call("GET", `/accounts/${encodeURIComponent(email)}/todos?state=${state}`);
    if (status !== 200) {
      throw new Error(`listing the ${state} todos of ${email} failed: ${status} ${JSON.stringify(payload)}`);
    }
    return payload.todos as string[];
  }

  private async call(method: string, path: string, body?: object): Promise<[number, Record<string, unknown>]> {
    const response = await fetch((await this.system.apiUrl()) + path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    const text = await response.text();
    return [response.status, text ? JSON.parse(text) : {}];
  }
}
