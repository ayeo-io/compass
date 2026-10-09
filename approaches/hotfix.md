# Delivery approach - Hotfix

> Something is broken in production now. Reproduce first, fix fast, follow-up
> properly. The clock is real - the default guardrails still aren't negotiable.

## Assess composes towards Hotfix when

- there is a live defect with user impact happening *now*, **and**
- size is `atomic` or `small` (a large fix is an incident, not a hotfix -
  assess it on the full approach under incident command), **and**
- risk is high `cross-cutting` (a `critical` risk value is floored to
  the full approach by RP-FLOOR-001, so it never composes as a hotfix, however
  urgent), **and**
- role is typically `engineer`, often paired with `qa`.

Hotfix is the one approach defined by *urgency* rather than by the size /
risk / familiarity composition. Assess still scores all four
dimensions - they shape the follow-up - but urgency is what selects the shape.

## Per-stage weight

| Stage | Weight on Hotfix |
|---|---|
| Assess | Fast but real. `delivery-approach.md` is written - even under time pressure, the audit trail starts here. |
| Define | **Reproduce-first.** The spec *is* a failing regression test that reproduces the defect. Writing that test is non-negotiable and comes before any fix - it is simultaneously the BDD scenario and the TDD red. |
| Refine | Collapsed - the reproduction resolves the ambiguity. The bug is unambiguous once it reproduces. |
| Plan | Collapsed to a one-line root-cause note in `delivery-approach.md`. (Root cause, not symptom - a hotfix that treats the symptom owes a follow-up initiative.) |
| Breakdown | Skipped. Solo. Speed and a single clear owner beat parallelism here. |
| Implement | Expedited TDD: the reproduction test is already red; make it green with the smallest correct change; refactor only if the refactor itself is low-risk. |
| Verify | **All Verify gates, no exceptions.** This is the stage Hotfix does *not* compress. The reproduction test passes, the full suite passes, regression is clean, output is pasted. |
| Ship | Ship the fix. Then the **mandatory follow-up** - see below. The issue is not closed until the follow-up is done. |

## Gate set

Thorough Verify gate. Review dimensions: `correctness`, `governance`,
`traceability`, `regression`, `security`. `clarity` is deferred to the
follow-up. The gate is *not* lighter than the regular approach's - Hotfix compresses the
stages *before* Verify, never Verify itself.

## Multiagent orchestration

Solo. No worktree.

## The mandatory follow-up - Hotfix's defining obligation

Hotfix defers the requirements review and plan until after the fix, and must
complete the follow-up before the issue closes. Before the issue closes,
shipping needs:

1. **`delivery-approach.md` completed** - the dimension assessment and root-cause note,
   filled in properly, not just the urgent stub.
2. **A real scenario** - the reproduction test is promoted into a proper
   Given/When/Then scenario in `acceptance-criteria.md`, traceable to the defect.
3. **A root-cause line in the devlog** - what allowed this defect to exist,
   and whether a follow-up issue is owed (e.g. "the missing scenario that would
   have caught this is now filed as issue #…").

A Hotfix that has not completed the follow-up is an open issue.
`/compass:status` flags it; `/compass:ship` refuses to close it.

## Hotfix may NOT

- Skip the reproduction test. "Fix first, test later" is not a Hotfix - it is
  the thing a hotfix exists to prevent. The tested-before-ship guardrail is
  not negotiable, and the red-before-green TDD strategy is how Hotfix meets it.
- Compress the Verify gate. The stages before Verify are compressed; Verify is
  not.
- Close without the follow-up. The follow-up must complete before the issue
  closes.
- Be used for a fix that is actually `medium`+ in size. That is an
  incident: assess it on the full approach, put someone in incident command, and
  use multiagent orchestration if it helps.
