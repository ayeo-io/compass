# pytest-bdd reference adapter

A worked project showing the whole path from a Compass spec to a passing
acceptance suite. Copy the wiring, not the domain - the password-reset rule
here is three lines, on purpose.

**What this demonstrates:** the Gherkin an engineer writes in
`acceptance-criteria.md` is the same text a runner runs. The link between a
scenario and the test that satisfies it stops being a convention someone
maintains and becomes a fact the runner establishes.

---

## The four steps

### 1. Declare the runner in `compass.yml`

Use `.compass/config.yml` in a project that has no `compass.yml`.

```yaml
project:
  bdd_runner: pytest-bdd        # which runner; names this directory
  # bdd_features_dir: features  # where extract writes; unset = the issue dir
  bdd_steps_dir: tests/steps    # where your step definitions live
  bdd_run_command: "pytest tests/"
```

Only `bdd_run_command` and `bdd_steps_dir` matter to a human here;
`bdd_features_dir` is left unset so the extracted feature lands in the
issue's `.compass/work/` directory. In the shipped Compass config all four
are commented out - a project that edits nothing has opted into nothing.

### 2. Extract the Gherkin

```bash
compass bdd extract --issue reset-password
```

This reads `docs/compass/2026-08-03-reset-password/acceptance-criteria.md` and writes
`.compass/work/reset-password/acceptance-criteria.feature`:

```gherkin
# Derived from docs/compass/2026-08-03-reset-password/acceptance-criteria.md by `compass bdd extract`.
# Do not hand-edit - your edits are overwritten on the next extract.
# Edit the source spec instead.

Feature: reset-password

  @TRC-A1
  Scenario: a valid token should let the user set a new password
    Given a password reset token issued 1 hours ago
    When the user sets the new password "correct horse battery"
    Then the reset succeeds
    And the password change is recorded
```

Each scenario carries its traceability id as a tag, so a per-scenario result
maps straight back to `manifest.yml`. The output is deterministic: same spec, same
bytes, no timestamps and no absolute paths, so it is safe to commit and to
diff.

### 3. Bind the steps

```bash
pip install pytest-bdd
```

`tests/steps/test_reset_password_steps.py` points `scenarios()` at the
**extracted** file, never at the markdown:

```python
from pytest_bdd import scenarios, given, when, then, parsers

scenarios(".compass/work/reset-password/acceptance-criteria.feature")

@given(parsers.parse("a password reset token issued {hours:d} hours ago"),
       target_fixture="token")
def issued_token(hours):
    return Token(value="tok-123", age_hours=hours)

@when(parsers.parse('the user sets the new password "{password}"'))
def set_password(store, token, outcome, password):
    outcome["result"] = store.reset(token, password)

@then(parsers.parse('the reset is refused with "{reason}"'))
def reset_refused(outcome, reason):
    assert not outcome["result"].ok
    assert outcome["result"].error == reason
```

### 4. Run the acceptance suite

```bash
pytest tests/
```

```
tests/steps/test_reset_password_steps.py::test_a_valid_token_should_let_the_user_set_a_new_password PASSED
tests/steps/test_reset_password_steps.py::test_an_expired_token_should_be_rejected PASSED
tests/steps/test_reset_password_steps.py::test_a_password_below_the_length_floor_should_be_rejected PASSED
```

---

## Things worth knowing before you copy this

**Run extract before the tests.** The `.feature` file is derived. Regenerate it
whenever the spec changes - in CI, put `compass bdd extract` immediately before
the test command. Committing the extracted file is fine and often useful (the
output is deterministic), but it is never the source of truth.

**An unbound step fails with an error.** Delete a `@given` and pytest-bdd reports the
step text it could not find. That is the failure an adopter meets first, and it
names the thing to fix.

**pytest-bdd is a pytest plugin.** If your project sets
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` - a common fix for plugins that hang on
init in clean environments - pytest-bdd will not load, and your scenarios will
silently not run. The Compass repository itself does this, which is why its own
adapter check runs in a dedicated CI job with autoload on rather than in the
main suite. Check for it before concluding your steps are wrong.

**Keep the step text in the spec, not in the code.** The scenario is the
contract five roles read. If a step reads well as a test but badly as English,
the spec is what needs changing.

---

## Other runners

`cucumber-js`, `behave` and `godog` each have a worked adapter beside this one,
and a CI job runs each one on every pull request and every push to main. The same four steps apply to
all four; only step three, binding the steps, differs. `compass bdd extract`
emits plain Gherkin with standard `@tags`, which every one of them reads and
selects on.
