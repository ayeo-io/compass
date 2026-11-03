/**
 * The vocabulary the todo specifications are written in.
 *
 * Each method is one Given, When or Then line. Set-up methods start `has`,
 * actions use the person's own verb and checks start `confirm`. The DSL fills
 * in defaults, puts every account email through the alias helper and passes
 * the call on. It makes no check itself: each `confirm` is the driver's, and so
 * is each failure. A method here has the same name as the driver method it
 * calls.
 */
import type { Alias } from "./alias.ts";
import { aliases } from "./alias.ts";
import type { TodoDriver } from "./drivers/index.ts";

/** The account a scenario works in when it names none. */
const DEFAULT_EMAIL = "user@example.com";

/** Who the scenario acts as: the account its latest Given made. */
class Scenario {
  account = "";
}

class Part {
  protected driver: TodoDriver;
  protected alias: Alias;
  protected scenario: Scenario;

  constructor(driver: TodoDriver, alias: Alias, scenario: Scenario) {
    this.driver = driver;
    this.alias = alias;
    this.scenario = scenario;
  }
}

/** The person who uses the todo service. */
export class User extends Part {
  async hasAccount(email: string = DEFAULT_EMAIL): Promise<void> {
    this.scenario.account = this.alias(email);
    await this.driver.hasAccount(this.scenario.account);
  }
}

/** The todos of the account the scenario acts as. */
export class Todo extends Part {
  async hasOpen(name: string): Promise<void> {
    await this.driver.hasOpen(this.scenario.account, name);
  }

  async hasCompleted(name: string): Promise<void> {
    await this.driver.hasCompleted(this.scenario.account, name);
  }

  async add(name: string): Promise<void> {
    await this.driver.add(this.scenario.account, name);
  }

  async complete(name: string): Promise<void> {
    await this.driver.complete(this.scenario.account, name);
  }

  async archive(name: string): Promise<void> {
    await this.driver.archive(this.scenario.account, name);
  }

  async confirmOpen(name: string): Promise<void> {
    await this.driver.confirmOpen(this.scenario.account, name);
  }

  async confirmCompleted(name: string): Promise<void> {
    await this.driver.confirmCompleted(this.scenario.account, name);
  }

  async confirmArchived(name: string): Promise<void> {
    await this.driver.confirmArchived(this.scenario.account, name);
  }

  async confirmNotListed(name: string, owner?: string): Promise<void> {
    const account = owner ? this.alias(owner) : this.scenario.account;
    await this.driver.confirmNotListed(account, name);
  }

  async confirmRefused(reason: string): Promise<void> {
    await this.driver.confirmRefused(reason);
  }
}

/** One per specification file. `begin` gives each scenario its own aliases and its own account. */
export class Dsl {
  user!: User;
  todo!: Todo;

  begin(driver: TodoDriver): void {
    const alias = aliases();
    const scenario = new Scenario();
    this.user = new User(driver, alias, scenario);
    this.todo = new Todo(driver, alias, scenario);
  }
}
