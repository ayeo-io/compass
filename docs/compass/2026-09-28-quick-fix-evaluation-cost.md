# Quick-fix cost - before and after `compass quick-fix`

Rival products appear as codes R1 to R9; the maintainer holds the key.

On each scenario's mean, a quick fix under Compass now costs 1.4 to 1.9
times what it costs under R1, down from 6.6 to 8.6 times. Every
session after the change passed its hidden tests and its three gates. Before it, two of the four
Compass sessions ended with at least one gate still pending.

## Results

Two B6 scenarios, two sessions each, model `claude-opus-5-5`.
R1 is pinned at `8ca22dba` (v6.4.2). The "before" and rival
sessions are the published B6 runs (`2026-09-28-eval-comparison.md`), with
Compass at `99dfa86`. The "after" sessions ran Compass at `85bce9e`.
Tokens count every token each model call reported. Hidden tests are the
scenario's own, which the session never sees.

| Scenario | Condition | Session | Tokens | Calls | Hidden tests | Gates |
|---|---|---|---|---|---|---|
| `cmp-small-fix` | no framework | 1 | 69,929 | 4 | 2/2 | - |
| `cmp-small-fix` | no framework | 2 | 68,561 | 4 | 2/2 | - |
| `cmp-small-fix` | R1 | 1 | 120,451 | 6 | 2/2 | - |
| `cmp-small-fix` | R1 | 2 | 99,032 | 5 | 2/2 | - |
| `cmp-small-fix` | compass before | 1 | 668,052 | 19 | 2/2 | pass |
| `cmp-small-fix` | compass before | 2 | 788,153 | 21 | 2/2 | pending |
| `cmp-small-fix` | compass after | 1 | 150,502 | 7 | 2/2 | pass |
| `cmp-small-fix` | compass after | 2 | 150,013 | 7 | 2/2 | pass |
| `cmp-feature` | no framework | 1 | 70,301 | 4 | 3/3 | - |
| `cmp-feature` | no framework | 2 | 69,958 | 4 | 3/3 | - |
| `cmp-feature` | R1 | 1 | 102,269 | 5 | 3/3 | - |
| `cmp-feature` | R1 | 2 | 78,599 | 4 | 3/3 | - |
| `cmp-feature` | compass before | 1 | 818,973 | 22 | 3/3 | pass |
| `cmp-feature` | compass before | 2 | 736,380 | 19 | 3/3 | pending |
| `cmp-feature` | compass after | 1 | 196,426 | 8 | 3/3 | pass |
| `cmp-feature` | compass after | 2 | 142,626 | 6 | 3/3 | pass |

Means, and Compass after against R1:

| Scenario | No framework | R1 | Compass before | Compass after | After / R1 |
|---|---|---|---|---|---|
| `cmp-small-fix` | 69,245 | 109,742 | 728,103 | 150,258 | 1.37 |
| `cmp-feature` | 70,130 | 90,434 | 777,677 | 169,526 | 1.87 |

One session, `cmp-feature` 1, is 2.17 times R1's mean. It spent
one call reading `compass quick-fix start --help` before using the flags
the command had already shown it.

## Calls by step

A model call re-reads the whole context, so a session's cost is about its
calls times its context. The table gives each step's calls per session
and its mean tokens across the four Compass sessions. A call that does
several things counts under the furthest step it reached, in the order
of the table: a call that runs `compass quick-fix start` and reads the
code counts as assessing.

| Step | Calls before | Tokens before | Calls after | Tokens after |
|---|---|---|---|---|
| Read the code | 1 to 3 | 73,221 | 0 | 0 |
| Load a command | 1 to 2 | 28,565 | 1 | 18,905 |
| Assess and record | 4 to 7 | 168,592 | 2 to 3 | 49,563 |
| Test and code | 4 to 6 | 187,413 | 1 to 2 | 40,389 |
| Check, gates and commit | 2 to 8 | 246,649 | 1 | 25,154 |
| Final reply | 1 | 48,450 | 1 | 25,881 |

After the change, sessions still read the code, but in the same call as
`quick-fix start`, so the table counts it there.

Before, the agent drove each mechanical step itself: it read the manifest
and approach templates in full (about 19,500 characters, re-read by every
later call), wrote the manifest, evaluated, wrote and registered the
record, traced files, ran the check, recorded it, passed three gates,
wrote the devlog and committed. After, `compass quick-fix start` does the
first half in one call and `compass quick-fix finish` the second half in
one call. The feature sessions opened `/compass:assess`, which now carries
the three commands, so they did not load a second command; the small-fix
sessions opened `/compass:quick-fix`.

## What this does not show

- Two sessions per cell. One extra call moves a session by about 25,000
  tokens, and the feature scenario's two sessions differ by 54,000.
- The rival figures are from the B6 run, not re-run alongside.
- `finish` ran with `--no-commit` in every session after, because no
  session was asked for a commit. The commit path is tested, not measured.
- Two earlier versions of the change, at `4b9ed53` and `246210a`, were
  run and replaced as the design changed. Their records show why: a session that stopped before
  `finish` because it would commit, sessions that loaded both commands,
  and one that never learned `finish` existed.
- Only these two scenarios. The heavier routes are unchanged.
