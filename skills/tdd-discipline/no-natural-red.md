# When the change has no natural red

Covers config edits, pure refactors and dead-code removal, not the ordinary cycle.

Some legitimate changes have no behavioural red to write, and pretending
otherwise is what produces dishonest tests. A compose `mem_limit`, a CI
`exit-code`, a Prometheus rule, a Terraform runbook, a dead-code removal: for a
refactor in particular, the *whole point* is that behaviour does not change, so
there is no new behaviour to be absent.

Authors have satisfied
the hook with a red like

```
compass tdd-red --verified-by regression -- '! grep -q "_ = is_unique" solver.py'
```

which asserts that a **string appears in a file**. That is the "testing
implementation, not behaviour" anti-pattern in `anti-patterns.md`, that only
looks compliant.

**Declare an acceptance instead.** State what would convince a reviewer, before
the change:

```
compass acceptance start --kind validation -- promtool check rules alerts.yml
compass acceptance start --kind refactor   -- pytest -q
# ... make the change ...
compass acceptance record -- <the same command>
```

- **`validation`** - a validator must pass after the change: `docker compose
  config`, `promtool check rules`, `terraform validate`, a schema parse. There
  may be no meaningful "before" (a new rules file has none), so no baseline is
  needed. On a quick fix, `acceptance start` refuses a validation when files
  have already changed since `quick-fix start`, staged or not: the change came
  first. The scenario's own test files do not count, and neither do commits.
  An output file from an earlier validator run counts as a change: delete it
  or ignore it before declaring. A change to an ignored path, such as `.env`,
  is not seen, so declare before making it.
- **`refactor`** - a command that passes now must **still** pass afterwards,
  across a source tree that demonstrably changed. Behaviour preservation is the
  contract, so the baseline is needed, and green-then-green with an unchanged
  tree is refused: that is two runs, not a refactor.

It writes its own `.acceptance` marker, which the hook honours. `.red` keeps
meaning exactly one thing - a real failure was observed here - and the recorded
acceptance counts as the issue's run, so there is nothing left to gain by faking
a red.

This is not an exemption for ordinary code. A change that *does* have a
natural behavioural red still owes one; reaching for `acceptance` because the
red is inconvenient is the same bypass as any other.

