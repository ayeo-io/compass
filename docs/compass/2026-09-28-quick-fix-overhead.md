# Quick-fix cost - before and after `compass quick-fix`

On each scenario's mean, a quick fix under Compass now costs 1.4 to 1.9
times what it costs under Superpowers, down from 6.6 to 8.6 times. Every
session after the change passed its hidden tests and its three gates. Before it, two of the four
Compass sessions ended with their gates still pending.

## Results

Two B6 scenarios, two sessions each, model `claude-opus-5-5`.
Superpowers is pinned at `8ca22dba` (v6.4.2). The "before" and rival
sessions are the published B6 runs (`2026-09-28-eval-comparison.md`), with
Compass at `99dfa86`. The "after" sessions ran Compass at `85bce9e`.
Tokens count every token each model call reported. Hidden tests are the
scenario's own, which the session never sees.

| Scenario | Condition | Session | Tokens | Calls | Hidden tests | Gates |
|---|---|---|---|---|---|---|
| `cmp-small-fix` | no framework | 1 | 69,929 | 4 | 2/2 | - |
| `cmp-small-fix` | no framework | 2 | 68,561 | 4 | 2/2 | - |
| `cmp-small-fix` | superpowers | 1 | 120,451 | 6 | 2/2 | - |
| `cmp-small-fix` | superpowers | 2 | 99,032 | 5 | 2/2 | - |
| `cmp-small-fix` | compass before | 1 | 668,052 | 19 | 2/2 | pass |
| `cmp-small-fix` | compass before | 2 | 788,153 | 21 | 2/2 | pending |
| `cmp-small-fix` | compass after | 1 | 150,502 | 7 | 2/2 | pass |
| `cmp-small-fix` | compass after | 2 | 150,013 | 7 | 2/2 | pass |
| `cmp-feature` | no framework | 1 | 70,301 | 4 | 3/3 | - |
| `cmp-feature` | no framework | 2 | 69,958 | 4 | 3/3 | - |
| `cmp-feature` | superpowers | 1 | 102,269 | 5 | 3/3 | - |
| `cmp-feature` | superpowers | 2 | 78,599 | 4 | 3/3 | - |
| `cmp-feature` | compass before | 1 | 818,973 | 22 | 3/3 | pass |
| `cmp-feature` | compass before | 2 | 736,380 | 19 | 3/3 | pending |
| `cmp-feature` | compass after | 1 | 196,426 | 8 | 3/3 | pass |
| `cmp-feature` | compass after | 2 | 142,626 | 6 | 3/3 | pass |

Means, and Compass after against Superpowers:

| Scenario | No framework | Superpowers | Compass before | Compass after | After / Superpowers |
|---|---|---|---|---|---|
| `cmp-small-fix` | 69,245 | 109,742 | 728,103 | 150,258 | 1.37 |
| `cmp-feature` | 70,130 | 90,434 | 777,677 | 169,526 | 1.87 |

One session, `cmp-feature` 1, is 2.17 times Superpowers' mean. It spent
one call reading `compass quick-fix start --help` before using the flags
the command had already shown it.

## Calls by step

A model call re-reads the whole context, so a session's cost is about its
calls times its context. Each call is counted under its first tool.

| Step | Before, calls per session | After, calls per session |
|---|---|---|
| Read the code | 0 to 2 | 0 |
| Load a command or skill | 1 to 2 | 1 |
| Assess and record the approach | 7 to 9 | 2 to 3 |
| Test and code | 2 to 6 | 1 to 3 |
| Check, evidence, gates, trace, devlog, commit | 4 to 8 | 0 to 1 |
| Final reply | 1 | 1 |

Before, the agent drove each mechanical step itself: it read the manifest
and approach templates in full (about 19,500 characters, re-read by every
later call), wrote the manifest, evaluated, wrote and registered the
record, traced files, ran the check, recorded it, passed three gates,
wrote the devlog and committed. After, `compass quick-fix start` does the
first half in one call and `compass quick-fix finish` the second half in
one call, usually the same call as the fix. `/compass:assess`, which a
session opens first, carries the three commands, so the session does not
load a second command.

## What this does not show

- Two sessions per cell. One extra call moves a session by about 25,000
  tokens, and the feature scenario's two sessions differ by 54,000.
- The rival figures are from the B6 run, not re-run alongside.
- `finish` ran with `--no-commit` in every session after, because no
  session was asked for a commit. The commit path is tested, not measured.
- Three earlier versions of the change were run and replaced as the
  design changed. Their records show why: a session that stopped before
  `finish` because it would commit, sessions that loaded both commands,
  and one that never learned `finish` existed.
- Only these two scenarios. The heavier routes are unchanged.
