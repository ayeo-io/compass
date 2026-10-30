"""A person keeps a list of todos: adds them, completes them and archives them.

Executable specifications. The docstring holds the scenario as a person
reads it, and each Given, When or Then line below it is one DSL call.
"""
from __future__ import annotations


def test_a_new_todo_is_open(dsl):
    """
    Given an account
    When they add a todo "Buy milk"
    Then "Buy milk" is open
    """
    dsl.user.hasAccount()
    dsl.todo.add("Buy milk")
    dsl.todo.confirmOpen("Buy milk")


def test_completing_a_todo_moves_it_to_completed(dsl):
    """
    Given an account
    And an open todo "Buy milk"
    When they complete it
    Then "Buy milk" is completed
    """
    dsl.user.hasAccount()
    dsl.todo.hasOpen("Buy milk")
    dsl.todo.complete("Buy milk")
    dsl.todo.confirmCompleted("Buy milk")


def test_a_completed_todo_can_be_archived(dsl):
    """
    Given an account
    And a completed todo "Buy milk"
    When they archive it
    Then "Buy milk" is archived
    """
    dsl.user.hasAccount()
    dsl.todo.hasCompleted("Buy milk")
    dsl.todo.archive("Buy milk")
    dsl.todo.confirmArchived("Buy milk")


def test_an_open_todo_cannot_be_archived(dsl):
    """
    Given an account
    And an open todo "Buy milk"
    When they archive it
    Then the archive is refused, saying it is not completed
    And "Buy milk" is still open
    """
    dsl.user.hasAccount()
    dsl.todo.hasOpen("Buy milk")
    dsl.todo.archive("Buy milk")
    dsl.todo.confirmRefused("not completed")
    dsl.todo.confirmOpen("Buy milk")


def test_one_account_does_not_see_another_accounts_todos(dsl):
    """
    Given an account "bob@example.com"
    And an account "ann@example.com"
    When they add a todo "Buy milk"
    Then "Buy milk" is not in the todos of "bob@example.com"
    """
    dsl.user.hasAccount("bob@example.com")
    dsl.user.hasAccount("ann@example.com")
    dsl.todo.add("Buy milk")
    dsl.todo.confirmNotListed("Buy milk", owner="bob@example.com")
