---
name: quick-fix
description: "The light path: dimensions, red-green-refactor, gates. Load with /compass:quick-fix."
---

# Quick fix

What `/compass:quick-fix` needs to know, and nothing else. The heavier
approaches read fuller versions of the same subjects; this is the light
path's share of them.

## Scoring the four dimensions

A value and a one-line justification each. If a value cannot be justified,
ask - an unjustified value is worse than a question. `compass quick-fix
start` refuses a missing reason or an unknown value before writing anything,
so a bad score is caught, never silently applied.

### Risk - if this goes wrong, how bad and how wide?

| Value | Test |
|---|---|
| `trivial` | Wrong outcome is cosmetic or instantly obvious, and instantly reversible. No data, no money, no auth, no other team. |
| `contained` | Failure is annoying but bounded to one feature, recoverable without an incident, no data lost. |
| `cross-cutting` | Failure spreads across features or services, or degrades something many people touch. Recovery needs coordination. |
| `critical` | Failure can lose data, lose money, breach auth or privacy, or cannot be cleanly rolled back. |

Risk is about consequence, never effort - a one-character change can be
critical.

### Familiarity - new code or existing code, and how well described?

| Value | Test |
|---|---|
| `greenfield` | Net-new, with no existing behaviour to preserve. |
| `brownfield-mapped` | Existing code whose current behaviour is already in scenarios, or is trivially readable. |
| `brownfield-unmapped` | Existing code whose behaviour is not written down anywhere. |

`brownfield-unmapped` is not a quick fix: a policy floor forces the behaviour
to be described first - you cannot safely change what nobody wrote down.

### Size - how much work, honestly?

| Value | Test |
|---|---|
| `atomic` | One file, one obvious change, under about half an hour, no design decision. |
| `small` | One to three files, a solution pattern that already exists here, no new structure. |
| `standard` and above | Several files, a day or more, one or more design decisions. |

Size is the dimension most misread. When unsure, estimate up.

### Goal and role

`delivery` on this path, driven by an engineer. A product owner, marketer or
designer in play pulls the approach up out of quick fix. So does a goal of
`exploration` - "I cannot state this well enough to deliver it yet" - which
is a spike, not a small change.

The CLI composes the approach from these four; you record what you scored.

## Red, green, refactor

The guardrail is **tested before it lands**: no code reaches main without a
passing automated test it traces to. That never bends.

Red-before-green is the strategy that satisfies it, in full. What a light
approach adapts is how much *surface* the tests cover - the one scenario and
its obvious edges - never whether a test exists.

1. **Red.** Write the test for the behaviour and watch it fail *for the right
   reason*. A test that fails on a typo or a missing import is not a red - it
   has not described the behaviour yet.
2. **Green.** The smallest *correct* change that passes. Not the most
   general; generality is earned in refactor, under a green suite.
3. **Refactor.** Improve names, remove duplication, with the suite green. If
   the test has to change here, you were changing behaviour - go back to
   red.

`hooks/pre-tool.sh` enforces this mechanically: it blocks a code edit with no
failing test behind it. When it blocks you, the answer is to write the
failing test - never disable it, work around it, or edit its markers by
hand.

### When the change has no natural failing test

Some changes have no unit that can fail first - a config value, a
documentation string, a dependency bump. Reach for the guard that *can*
fail: a regression run, a type check, an end-to-end check. Run it, watch it
fail, then fix. `compass tdd-red --verified-by regression|e2e|typecheck|live`
records which kind of guard stood in. The guard must still genuinely fail
first - a sanctioned red is not an exemption from red.

