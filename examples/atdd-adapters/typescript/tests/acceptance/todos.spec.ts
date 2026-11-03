/**
 * A person keeps a list of todos: adds them, completes them and archives them.
 *
 * Executable specifications. The comment at the top of each scenario holds it
 * as a person reads it, and each Given, When or Then line is one DSL call
 * below it.
 */
import { test } from "node:test";
import { useDsl } from "./driverFactory.ts";

const dsl = useDsl();

test("a new todo is open", async () => {
  /*
    Given an account
    When they add a todo "Buy milk"
    Then "Buy milk" is open
  */
  await dsl.user.hasAccount();
  await dsl.todo.add("Buy milk");
  await dsl.todo.confirmOpen("Buy milk");
});

test("completing a todo moves it to completed", async () => {
  /*
    Given an account
    And an open todo "Buy milk"
    When they complete it
    Then "Buy milk" is completed
  */
  await dsl.user.hasAccount();
  await dsl.todo.hasOpen("Buy milk");
  await dsl.todo.complete("Buy milk");
  await dsl.todo.confirmCompleted("Buy milk");
});

test("a completed todo can be archived", async () => {
  /*
    Given an account
    And a completed todo "Buy milk"
    When they archive it
    Then "Buy milk" is archived
  */
  await dsl.user.hasAccount();
  await dsl.todo.hasCompleted("Buy milk");
  await dsl.todo.archive("Buy milk");
  await dsl.todo.confirmArchived("Buy milk");
});

test("an open todo cannot be archived", async () => {
  /*
    Given an account
    And an open todo "Buy milk"
    When they archive it
    Then the archive is refused, saying it is not completed
    And "Buy milk" is still open
  */
  await dsl.user.hasAccount();
  await dsl.todo.hasOpen("Buy milk");
  await dsl.todo.archive("Buy milk");
  await dsl.todo.confirmRefused("not completed");
  await dsl.todo.confirmOpen("Buy milk");
});
