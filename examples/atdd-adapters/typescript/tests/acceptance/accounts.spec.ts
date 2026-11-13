/**
 * Each account sees only its own todos.
 *
 * Executable specifications, written as in `todos.spec.ts`. They are in a
 * file of their own so that a run on two workers runs two files at once.
 */
import { test } from "node:test";
import { useDsl } from "./driverFactory.ts";

const dsl = useDsl();

test("one account does not see another account's todos", async () => {
  /*
    Given an account "bob@example.com"
    And an account "ann@example.com"
    When they add a todo "Buy milk"
    Then "Buy milk" is not in the todos of "bob@example.com"
  */
  await dsl.user.hasAccount("bob@example.com");
  await dsl.user.hasAccount("ann@example.com");
  await dsl.todo.add("Buy milk");
  await dsl.todo.confirmNotListed("Buy milk", "bob@example.com");
});
