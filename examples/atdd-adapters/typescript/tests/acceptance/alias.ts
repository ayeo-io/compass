/**
 * Aliases for the identifiers a scenario names.
 *
 * A scenario names an account `ann@example.com`; the system sees
 * `ann@example.com-3f9a1c2e-w4711-17`. The same scenario can then run twice,
 * or beside itself in another worker, without meeting its own earlier data.
 *
 * - The run id is made once, when the run starts, and every worker of the run
 *   reads it from ACCEPTANCE_RUN_ID (`run.ts` sets it before the workers
 *   start).
 * - The counter is shared by the worker: node:test runs each specification
 *   file in its own process, and the process id in the alias keeps two
 *   workers' numbers apart.
 * - Each scenario has its own map, so a name gives the same alias every time
 *   that scenario asks for it.
 */

/** Gives the alias of a name, the same one each time within one scenario. */
export type Alias = (name: string) => string;

let counter = 0;

function runId(): string {
  const id = process.env.ACCEPTANCE_RUN_ID;
  if (!id) {
    throw new Error("ACCEPTANCE_RUN_ID is not set: start the suite with tests/acceptance/run.ts");
  }
  return id;
}

/** The alias map of one scenario. */
export function aliases(): Alias {
  const names = new Map<string, string>();
  return (name: string): string => {
    let alias = names.get(name);
    if (alias === undefined) {
      counter += 1;
      alias = `${name}-${runId()}-w${process.pid}-${counter}`;
      names.set(name, alias);
    }
    return alias;
  };
}
