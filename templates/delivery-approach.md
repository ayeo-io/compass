<!--
TEMPLATE: delivery-approach.md
Authority:   This is the audit centrepiece. It records the assessment, the
             delivery approach the policy computed, every policy rule that
             fired, and, as its own section, what was skipped and why it is safe.
             Rubric: the delivery-approach reference docs. Policy prose:
             ${CLAUDE_PLUGIN_ROOT}/governance/routing-policy.md (hard rules +
             soft biases); the rules in force are what `compass policy show`
             prints (an unmigrated 5.x project runs on its own copied
             governance/ until `compass policy migrate`).

On a spike, assess also writes a `.spike` marker file in the issue
directory so the pre-tool hook knows to suspend the TDD strategy.

Fill every {{PLACEHOLDER}}. A dimension with no justification is not an
assessment - ask the human instead. A stage with no "safe to skip because…"
line is not skippable - it runs.
-->

# Delivery approach - {{ISSUE_SLUG}}

<!-- compass:render document-header -->
<!-- /compass:render -->

<!-- On a re-assessment (`--reassess`), keep the prior revision below this
     line under a "## Superseded - revision <N-1>" heading so the history
     stays visible. -->

---

## The assessment

<!-- Written by `compass issue render` from the manifest's `assessment` and
     `justifications`: one row per dimension with its value and its reason, then the
     labels. Record each value and its reason with `compass approach evaluate
     --write --justify DIM=TEXT`. No justification: ask, do not guess. -->

<!-- compass:render assessment -->
<!-- /compass:render -->

<!-- compass:render readiness -->
<!-- /compass:render -->

---

## The composed candidate

<!-- The delivery approach assembled from the assessment, biased by the
     policy's soft defaults, BEFORE the hard rules are applied. Name the
     reference shape for shared vocabulary, then list deviations. -->

Candidate: **{{reference shape}}**, with these deviations from its reference form:

- {{e.g. "Test & review also runs the security dimension because the risk is cross-cutting." - or "none"}}

Candidate review dimensions: {{correctness, governance, traceability, … per the reference docs}}

---

## Policy rules that fired

<!-- Written by `compass issue render` from the manifest's `policy_rules_fired`: the
     policy line, the generation, and one row per rule that fired with its rationale
     quoted from the policy. This is the policy provenance: a reader months later can
     tell a light approach from one computed against stale governance. The version of
     routing-policy.yml and any policy drift (rules or checks missing against the
     framework) are reported by `compass policy lint`; if the CLI reported drift,
     record it in `devlog.md`. -->

<!-- compass:render policy-rules -->
<!-- /compass:render -->

---

## The final delivery approach

### Per-stage weight

<!-- compass:render stage-weights -->
<!-- /compass:render -->

### Gate set

<!-- compass:render gate-set -->
<!-- /compass:render -->

### Multiagent orchestration

- Orchestration: {{solo \| pair (2-3 subtasks) \| multiagent (4+ subtasks)}}
- Subtask count: {{N - from distribution-map.md, or "n/a (solo)"}}
- Worktree root: {{from `multiagent.worktree_root` in compass.yml (or .compass/config.yml without one), default ../.compass-worktrees}}
- Cap in effect: {{e.g. "critical risk → max_worktrees: 1" - from a hard cap in routing-policy.yml - or "none"}}
- Orchestrator agent: {{yes (multiagent) \| no - lead builder integrates (pair) \| n/a (solo)}}

---

## The de-scope ledger

<!-- THE AUDIT CENTREPIECE. Every stage or check that is collapsed or
     skipped, each with an explicit "safe to skip because…" line. A stage
     with no justification CANNOT be skipped - it runs. On full-approach scale
     work this table is empty by definition; cap-driven reductions go in
     the Multiagent orchestration section, not here. On a spike the standing justification for every
     row is the same: nothing ships from a spike. -->

| Stage / check | Action | Safe to skip / collapse because… |
|---|---|---|
| {{e.g. Requirements review}} | {{collapsed \| skipped}} | {{e.g. "The acceptance criteria are a single scenario certified unambiguous at assess - nothing to review."}} |
| {{e.g. Plan}} | {{collapsed to one-liner}} | {{e.g. "atomic size on familiar ground - no design decision; the plan is 'edit src/foo.ts'."}} |
| {{e.g. Breakdown}} | {{skipped}} | {{e.g. "One subtask of work - parallelism would be pure overhead."}} |

**One-line edit note (quick fix / hotfix collapsed design only):** {{which file(s) to edit, or root-cause note}}

**Spike question + timebox (spike collapsed stages only):** {{the question to answer, and the timebox}}

---

## Owed follow-ups

<!-- Work the issue deferred to go faster, which must be done at ship before
     the issue can close. A hotfix always owes one;
     other work owes whatever the de-scope ledger marked. A spike owes
     nothing - it ships nothing; its exit is graduate or discard. -->
<!-- absorbed: "<!-- Process weight borrowed from the front of the pipeline that must be settled" -->

- [ ] {{e.g. "Hotfix follow-up: this record completed properly, reproduction test promoted to a real scenario in acceptance-criteria.md, root-cause line in devlog.md."}}
- [ ] {{e.g. "none owed"}}

---

## Human overrides

<!-- The computed approach is advisory until confirmed. Any assessment value
     or the final approach may be overridden by a human - recorded here with
     who and why. What CANNOT be overridden: an immovable gate, or a floor
     (a hard policy rule is governance speaking; changing it means a
     reviewed change to the project's compass.yml (a loosening needs a waiver that
     the project's owner approves), not overriding one
     issue's approach). -->

| What was overridden | From → To | Who | Why |
|---|---|---|---|
| {{e.g. "Size"}} | {{medium → small}} | {{name}} | {{reason}} |

<!-- If none: "No human overrides. Approach confirmed as composed." -->

---

## Confirmation

- [ ] Approach presented to the invoker and confirmed (or overridden - see Human overrides).
- [ ] Every dimension in The assessment has a justification.
- [ ] Every skipped/collapsed stage in The de-scope ledger has a "safe to skip because…" line.
- [ ] On a spike: the `.spike` marker file is written to the issue directory.
- [ ] `devlog.md` opened with the assess entry.

Next stage: **define acceptance criteria** (`/compass:define`) - or explore, on a spike.
