# Review an existing suite

Start with two searches. They find the most common problems, and the ones that do the most damage.

1. Search the DSL for `assert`, `expect` and `should`. Each match is a violation, however small the suite. The check belongs in the driver.
2. Search the specifications for literal email addresses, usernames and entity names. Each one that skips the alias helper stops the suite from running twice or in parallel.

Then work through `skills/atdd/references/checklist.md` and report what you find, grouped by layer. The other common problems, roughly from most to least frequent, are:

- status codes or selectors in specifications;
- a stubbed internal database;
- cleanup after each scenario;
- a DSL that reads raw response payloads.
