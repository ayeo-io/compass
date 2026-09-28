---
name: quick-fix
description: "The light path: dimensions, red-green-refactor, gates. Load with /compass:quick-fix."
---

# Quick fix

What `/compass:quick-fix` needs to know, and nothing else. The heavier
delivery approaches
read fuller versions of all three subjects; this is the light path's share of
them.

## Scoring the four dimensions

A value and a one-line justification each. If a value cannot be justified,
ask - an unjustified value is worse than a question.

### Risk - if this goes wrong, how bad and how wide?

| Value | Test |
|---|---|
| `trivial` | Wrong outcome is cosmetic or instantly obvious, and instantly reversible. No data, no money, no auth, no other team. |
| `contained` | Failure is annoying but bounded to one feature, recoverable without an incident, no data lost. |
| `cross-cutting` | Failure spreads across features or services, or degrades something many people touch. Recovery needs coordination. |
| `critical` | Failure can lose data, lose money, breach auth or privacy, or cannot be cleanly rolled back. |

Risk is about consequence, never effort. A one-character change can be
critical, and that is the value this path most often gets wrong.

### Familiarity - new code or existing code, and how well described?

| Value | Test |
|---|---|
| `greenfield` | Net-new, with no existing behaviour to preserve. |
| `brownfield-mapped` | Existing code whose current behaviour is already in scenarios, or is trivially readable. |
| `brownfield-unmapped` | Existing code whose behaviour is not written down anywhere. |

`brownfield-unmapped` is not a quick fix: a policy floor forces the behaviour
to be described first, because you cannot safely change what nobody has
written down.

### Size - how much work, honestly?

| Value | Test |
|---|---|
| `atomic` | One file, one obvious change, under about half an hour, no design decision. |
| `small` | One to three files, a solution pattern that already exists here, no new structure. |
| `standard` and above | Several files, a day or more, one or more design decisions. |

Size is the dimension people misread most. When unsure, estimate up.

### Goal and role

`delivery` on this path, driven by an engineer. A product owner, marketer or
designer in play adds artifacts and gates and pulls the approach up out of
quick fix. So does a goal of `exploration` - "I cannot state this well enough
to deliver it yet" - which is a spike, not a small change.

The CLI composes the approach from these four. You record what you scored;
it applies the policy.

## Red, green, refactor

The guardrail is **tested before it lands**: no code reaches the main branch
without a passing automated test it traces to. That never bends.

Red-before-green is the strategy that satisfies it, and it applies here in
full. What a light approach adapts is how much *surface* the tests cover -
the one scenario plus its obvious edges - never whether a test exists.

1. **Red.** Write the test for the behaviour and watch it fail *for the right
   reason*. A test that fails on a typo or a missing import is not a red - it
   has not described the behaviour yet. The failure should read like the
   feature being absent.
2. **Green.** The smallest *correct* change that passes. Not the most general;
   generality is earned in refactor, under a green suite.
3. **Refactor.** Improve names, remove duplication, with the suite green. If
   the test has to change here, you were changing behaviour - go back to red.

`hooks/pre-tool.sh` enforces this mechanically: it blocks a code edit that has
no failing test behind it. When it blocks you, the answer is to write the
failing test. Disabling it, working around it or editing its markers by hand
is breaking the strategy, and there is no deadline that licenses it.

### When the change has no natural failing test

Some changes have no unit that can fail first - a config value, a
documentation string, a dependency bump. Reach for the guard that *can* fail:
a regression run, a type check, an end-to-end check. Run it, watch it fail,
then fix. `compass tdd-red --verified-by regression|e2e|typecheck|live`
records which kind of guard stood in for the unit test. The guard must still
genuinely fail first - a sanctioned red is not an exemption from red.

## What clears a gate

Evidence, never assertion. The test is simple: **could someone who does not
trust you check it from what you recorded?** If they would have to take your
word, it is an assertion and it clears nothing.

| Assertion - clears nothing | Evidence - clears the gate |
|---|---|
| "The tests pass." | The recorded runner output: the command, the counts, the green summary. |
| "No regressions." | The suite run, before and after, showing nothing that was green is now red. |
| "I checked the guardrails." | `compass check`'s recorded output. |

Real evidence has four properties:

- **reproducible** - it carries the command;
- **current** - from this change, not a remembered earlier run;
- **complete** - the whole output, not a hand-picked green line (a run with
  skipped tests is not a green run);
- **honest about gaps** - a scenario you could not run is reported, not
  omitted.

A quick fix carries three gates and they are the same three on every approach:

- **correctness** - the change satisfies the scenario. The scenario-bound
  green record is the evidence.
- **traceability** - the changed files name the scenario, and the scenario
  names an intent. `compass check` checks the chain.
- **governance** - the guardrails hold. `compass check` is the mechanical
  part; recording its output is what makes it evidence.

A gate is not "mostly passed". One unmet dimension sends the work back, to the
implement step or to a new assessment of the four dimensions.

### The check that inspected nothing

`compass check` prints a PASS line for a check that had nothing to look at -
"no changed_files recorded yet", "0/3 pass gates", "no README on this issue".
Those lines are honest and they are not progress. Read what each check
actually inspected before treating a green run as a cleared gate.

## What a quick fix must not do

- **Skip the test.** The approach adapts test surface, never test existence.
- **Skip the scenario.** One is the minimum. Zero is never a valid state.
- **Be used to get a change in past a heavier assessment.** The recorded
  assessment and the CLI's computed approach make that visible, which is what
  they are for.
