# Isolation: the alias helper

The detail behind the temporal level of isolation in `skills/atdd/SKILL.md`: each identifier that must be unique goes through an alias helper, so the same scenario can run again without meeting its old data.

The alias helper has three parts:

- a run ID, created once when the run starts;
- a counter shared by the whole run, safe to use from parallel tests;
- an alias map for each scenario, so that one name always gives the same alias inside that scenario.

`alias("user@test.com")` then returns a value such as `user@test.com-r8f3-17`, and returns the same value each time that scenario asks for it.

Alias identifiers such as email addresses, usernames, order numbers and item names. Give descriptive values such as passwords, roles and addresses a default in the DSL, so that a scenario states only the values its behavior depends on.

Do not clean up after each scenario. Aliased data cannot collide, so it can stay. If the test environment needs the space back, clear it once before a run starts.
