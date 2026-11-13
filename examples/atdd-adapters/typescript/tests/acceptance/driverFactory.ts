/**
 * The driver factory: one DSL per specification file, with a new driver for each scenario.
 *
 * `run.ts` chooses the driver once, when the run starts, and passes its name
 * in ACCEPTANCE_DRIVER. The `beforeEach` hook imports the chosen driver's
 * module. The import is inside the hook on purpose: while a driver does not
 * exist yet, each scenario fails in its hook, and node:test still runs every
 * scenario and writes its JUnit report.
 */
import { after, before, beforeEach } from "node:test";
import { Dsl } from "./dsl.ts";
import type { TodoDriver } from "./drivers/index.ts";
import { RunningSystem } from "./system.ts";

function setting(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is not set: start the suite with tests/acceptance/run.ts`);
  }
  return value;
}

export function useDsl(): Dsl {
  const dsl = new Dsl();
  let system: RunningSystem | null = null;
  before(() => {
    system = new RunningSystem(setting("TODO_DATA_DIR"));
  });
  beforeEach(async () => {
    const module = await import(`./drivers/${setting("ACCEPTANCE_DRIVER")}.ts`);
    const driver: TodoDriver = new module.Driver(system);
    dsl.begin(driver);
  });
  after(async () => {
    await system?.stop();
  });
  return dsl;
}
